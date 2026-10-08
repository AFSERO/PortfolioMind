"""Deterministic Portfolio Simulation Service (Phase 3.2).

Provides purely functional, in-memory financial scenario projections:
1. Operates strictly on copies/snapshots — zero mutations, zero commits, zero flushes.
2. Canonical entity resolution via EntityResolver.
3. Strict net-worth preservation invariants (reallocation of assets <-> cash).
4. Deterministic percentage and weight calculations without LLM arithmetic.
"""

from decimal import Decimal
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.asset import Asset, AssetType
from app.models.cash import CashAccount
from app.models.instrument import Instrument
from app.models.transaction import Transaction
from app.schemas.portfolio_simulation import (
    PriceSource,
    SimulationAllocationSnapshot,
    SimulationAssumptions,
    SimulationCashSnapshot,
    SimulationInstrumentInfo,
    SimulationPortfolioSnapshot,
    SimulationPositionSnapshot,
    SimulationResult,
    SimulationTransactionSpec,
    SimulationType,
    SimulationValidation,
)
from app.services.copilot_v2.entity_resolver import EntityResolver
from app.services.dashboard import (
    _collect_currencies,
    _current_value_in,
    _effective_price_and_currency,
    _load_assets_with_stats,
    _load_cash_accounts,
    _total_cash_in,
)
from app.services.portfolio_stats import compute_stats
from app.utils.currency import build_rate_map, convert

logger = logging.getLogger(__name__)

ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")


def _to_f(d: Optional[Decimal]) -> float:
    """Helper converting Decimal to rounded float for schema boundary."""
    if d is None:
        return 0.0
    return float(round(d, 4))


def parse_fraction(val: Union[float, str, Decimal, None]) -> Optional[Decimal]:
    """Parse flexible fraction/percentage inputs (e.g., 0.5, 50, '50%', '1/2', 'yarisi')."""
    if val is None:
        return None
    if isinstance(val, (int, float, Decimal)):
        d = Decimal(str(val))
        if d > 1 and d <= 100:
            return d / ONE_HUNDRED
        return d

    text = str(val).strip().lower()
    norm = (
        text.replace("ı", "i")
        .replace("ğ", "g")
        .replace("ü", "u")
        .replace("ş", "s")
        .replace("ö", "o")
        .replace("ç", "c")
    )
    if norm in ("yarisi", "yarisini", "yarim", "half", "1/2") or text in ("yarısı", "yarısını", "yarim", "1/2"):
        return Decimal("0.5")
    if norm in ("tamami", "tamamini", "hepsi", "tumunu", "tumu", "all", "full", "1/1") or text in ("tamamı", "tümü"):
        return Decimal("1.0")
    if norm in ("ceyregi", "ceyrek", "1/4") or text in ("çeyreği", "çeyrek"):
        return Decimal("0.25")
    if norm in ("ucte biri", "1/3") or text in ("üçte biri",):
        return Decimal("0.333333")

    # Percentage string e.g. "25%" or "%25"
    text = text.replace("%", "").strip()
    match = re.match(r"^(\d+(?:\.\d+)?)(?:/(\d+(?:\.\d+)?))?$", text)
    if match:
        num = Decimal(match.group(1))
        denom = Decimal(match.group(2)) if match.group(2) else None
        if denom:
            return num / denom
        if num > 1 and num <= 100:
            return num / ONE_HUNDRED
        return num

    try:
        d = Decimal(text)
        if d > 1 and d <= 100:
            return d / ONE_HUNDRED
        return d
    except Exception:
        return None


class PortfolioSimulationService:
    """Pure, deterministic portfolio simulation engine."""

    @classmethod
    async def simulate_transaction(
        cls,
        db: AsyncSession,
        user_id: UUID,
        instrument_query: str,
        transaction_type: Union[SimulationType, str] = SimulationType.SELL,
        quantity: Optional[Union[float, Decimal]] = None,
        quantity_fraction: Optional[Union[float, str, Decimal]] = None,
        amount: Optional[Union[float, Decimal]] = None,
        price: Optional[Union[float, Decimal]] = None,
        fee: Optional[Union[float, Decimal]] = 0.0,
        base_currency: str = "TRY",
    ) -> SimulationResult:
        """Simulate a BUY or SELL transaction and compute hypothetical portfolio impact.

        INVARIANT: ZERO application mutations. Pure in-memory calculation.
        """
        # Normalize transaction type
        tx_type = (
            transaction_type
            if isinstance(transaction_type, SimulationType)
            else SimulationType(str(transaction_type).upper())
        )

        fraction_input = parse_fraction(quantity_fraction)
        qty_input = None
        if quantity is not None:
            try:
                qty_input = Decimal(str(quantity))
            except Exception:
                if fraction_input is None:
                    fraction_input = parse_fraction(quantity)

        amount_input = None
        if amount is not None:
            try:
                amount_input = Decimal(str(amount))
            except Exception:
                amount_input = None

        price_input = None
        if price is not None:
            try:
                p_dec = Decimal(str(price))
                if p_dec > 0:
                    price_input = p_dec
            except Exception:
                price_input = None

        fee_input = ZERO
        if fee is not None:
            try:
                f_dec = Decimal(str(fee))
                if f_dec >= 0:
                    fee_input = f_dec
            except Exception:
                fee_input = ZERO

        warnings: List[str] = []

        # ---------------------------------------------------------------------
        # 1. Canonical Entity Resolution
        # ---------------------------------------------------------------------
        resolved = await EntityResolver.resolve(db, query=instrument_query, user_id=user_id)
        if resolved.is_ambiguous:
            return cls._make_error_result(
                tx_type=tx_type,
                query=instrument_query,
                reason="AMBIGUOUS_INSTRUMENT",
                message=f"'{instrument_query}' sorgusu birden fazla enstrümanla eşleşti; netleştirme gerekiyor.",
                base_currency=base_currency,
            )

        if not resolved.is_resolved:
            return cls._make_error_result(
                tx_type=tx_type,
                query=instrument_query,
                reason="INSTRUMENT_NOT_FOUND",
                message=f"'{instrument_query}' enstrümanı sistemde bulunamadı.",
                base_currency=base_currency,
            )

        display_symbol = resolved.symbol or instrument_query.upper()
        display_name = resolved.canonical_name or display_symbol
        inst = resolved.canonical_instrument
        asset_obj = resolved.asset

        # Determine asset currency and asset type
        asset_currency = (
            (asset_obj.current_price_currency if asset_obj else None)
            or (inst.currency if inst else None)
            or "TRY"
        )
        raw_asset_type = (
            (asset_obj.asset_type.value if asset_obj else None)
            or (inst.asset_type.value if inst else None)
            or "STOCK"
        )

        instrument_info = SimulationInstrumentInfo(
            symbol=display_symbol,
            name=display_name,
            instrument_id=str(resolved.canonical_instrument_id) if resolved.canonical_instrument_id else None,
            asset_id=str(asset_obj.id) if asset_obj else None,
            asset_type=raw_asset_type,
            currency=asset_currency,
            is_owned=resolved.is_owned,
        )

        # ---------------------------------------------------------------------
        # 2. Baseline Portfolio Snapshot Loading
        # ---------------------------------------------------------------------
        pairs = await _load_assets_with_stats(db, user_id)
        cash_accounts = await _load_cash_accounts(db, user_id)

        # Exchange rate map
        all_currencies = (
            _collect_currencies(pairs)
            | {a.currency for a in cash_accounts}
            | {asset_currency, base_currency}
        )
        rate_map = await build_rate_map(all_currencies, base_currency, db)

        # Baseline position stats for target instrument
        baseline_holding_qty = ZERO
        matching_pair: Optional[Tuple[Asset, Dict[str, Any]]] = None

        if asset_obj:
            for p_asset, p_stats in pairs:
                if p_asset.id == asset_obj.id:
                    matching_pair = (p_asset, p_stats)
                    baseline_holding_qty = Decimal(str(p_stats.get("total_quantity") or 0))
                    break
        elif resolved.canonical_instrument_id:
            for p_asset, p_stats in pairs:
                if p_asset.instrument_id == resolved.canonical_instrument_id:
                    matching_pair = (p_asset, p_stats)
                    baseline_holding_qty = Decimal(str(p_stats.get("total_quantity") or 0))
                    break

        # ---------------------------------------------------------------------
        # 3. Price Determination
        # ---------------------------------------------------------------------
        ref_price: Optional[Decimal] = price_input
        price_source = PriceSource.EXPLICIT_SCENARIO_PRICE

        if ref_price is None:
            # Fallback to current asset price or instrument price
            cand_price = None
            if asset_obj and asset_obj.current_price is not None and asset_obj.current_price > 0:
                cand_price = asset_obj.current_price
            elif matching_pair and matching_pair[1].get("avg_cost") is not None:
                cand_price = matching_pair[1]["avg_cost"]
                warnings.append("Piyasa fiyatı bulunamadığı için pozisyonun ortalama maliyet fiyatı referans alındı.")

            if cand_price is None or cand_price <= ZERO:
                # Attempt to retrieve cached or live price for instrument
                try:
                    from app.services.price import get_live_price
                    live_data = await get_live_price(db, symbol=display_symbol, asset_type=raw_asset_type)
                    if live_data and live_data.get("price") and float(live_data["price"]) > 0:
                        cand_price = Decimal(str(live_data["price"]))
                        if live_data.get("currency"):
                            asset_currency = live_data["currency"]
                except Exception as p_err:
                    logger.debug("Failed to retrieve live price for %s in simulation: %s", display_symbol, p_err)

            if cand_price is not None and cand_price > 0:
                ref_price = cand_price
                price_source = PriceSource.CURRENT_REFERENCE_PRICE
            else:
                price_source = PriceSource.UNKNOWN


        if ref_price is None or ref_price <= ZERO:
            return cls._make_error_result(
                tx_type=tx_type,
                query=instrument_query,
                reason="MISSING_PRICE",
                message=f"'{display_symbol}' için güncel veya belirtilmiş bir referans fiyatı bulunamadı. Simülasyon için fiyat gereklidir.",
                instrument_info=instrument_info,
                base_currency=base_currency,
            )

        # ---------------------------------------------------------------------
        # 4. Quantity and Monetary Specifications
        # ---------------------------------------------------------------------
        sim_quantity = ZERO
        gross_value = ZERO

        if tx_type == SimulationType.SELL:
            if not resolved.is_owned or baseline_holding_qty <= ZERO:
                return cls._make_error_result(
                    tx_type=tx_type,
                    query=instrument_query,
                    reason="INSUFFICIENT_HOLDING",
                    message=f"Portföyünüzde '{display_symbol}' bulunmuyor. Sahip olunmayan varlık için satış simülasyonu yapılamaz.",
                    instrument_info=instrument_info,
                    base_currency=base_currency,
                )

            if fraction_input is not None:
                sim_quantity = baseline_holding_qty * fraction_input
            elif qty_input is not None:
                sim_quantity = qty_input
            elif amount_input is not None:
                sim_quantity = amount_input / ref_price
            else:
                # Default to 100% full position if not specified
                sim_quantity = baseline_holding_qty
                warnings.append("Satış miktarı belirtilmediği için tüm pozisyon (%100) simüle edildi.")

            if sim_quantity > baseline_holding_qty:
                return cls._make_error_result(
                    tx_type=tx_type,
                    query=instrument_query,
                    reason="INSUFFICIENT_HOLDING",
                    message=(
                        f"Satılmak istenen miktar ({_to_f(sim_quantity):,.4f}), mevcut portföy bakiyenizden "
                        f"({_to_f(baseline_holding_qty):,.4f}) fazladır. Negatif bakiye simüle edilemez."
                    ),
                    instrument_info=instrument_info,
                    base_currency=base_currency,
                )

            if sim_quantity <= ZERO:
                return cls._make_error_result(
                    tx_type=tx_type,
                    query=instrument_query,
                    reason="INVALID_QUANTITY",
                    message="Satış miktarı sıfırdan büyük olmalıdır.",
                    instrument_info=instrument_info,
                    base_currency=base_currency,
                )

            gross_value = sim_quantity * ref_price
            net_cash_delta = gross_value - fee_input
            post_holding_qty = baseline_holding_qty - sim_quantity

        else:  # BUY
            if amount_input is not None:
                gross_value = amount_input
                sim_quantity = gross_value / ref_price
            elif qty_input is not None:
                sim_quantity = qty_input
                gross_value = sim_quantity * ref_price
            else:
                return cls._make_error_result(
                    tx_type=tx_type,
                    query=instrument_query,
                    reason="MISSING_QUANTITY_OR_AMOUNT",
                    message=f"'{display_symbol}' alımı için miktar (adet) veya toplam tutar belirtilmelidir.",
                    instrument_info=instrument_info,
                    base_currency=base_currency,
                )

            if sim_quantity <= ZERO or gross_value <= ZERO:
                return cls._make_error_result(
                    tx_type=tx_type,
                    query=instrument_query,
                    reason="INVALID_QUANTITY",
                    message="Alış miktarı ve tutarı sıfırdan büyük olmalıdır.",
                    instrument_info=instrument_info,
                    base_currency=base_currency,
                )

            net_cash_delta = -(gross_value + fee_input)
            post_holding_qty = baseline_holding_qty + sim_quantity

        # ---------------------------------------------------------------------
        # 5. Baseline Aggregations
        # ---------------------------------------------------------------------
        baseline_asset_vals_base: Dict[str, Decimal] = {}
        for p_asset, p_stats in pairs:
            val_base = _current_value_in(p_asset, p_stats, base_currency, rate_map)
            baseline_asset_vals_base[str(p_asset.id)] = val_base

        baseline_cash_balances: Dict[str, Decimal] = {
            ca.currency: ca.balance or ZERO for ca in cash_accounts
        }
        baseline_total_cash_base = _total_cash_in(cash_accounts, base_currency, rate_map)
        baseline_invested_base = sum(baseline_asset_vals_base.values(), ZERO)
        baseline_total_portfolio_base = baseline_invested_base + baseline_total_cash_base

        # Target asset baseline values
        target_baseline_val_asset_curr = baseline_holding_qty * ref_price
        target_baseline_val_base = convert(target_baseline_val_asset_curr, asset_currency, base_currency, rate_map)
        target_baseline_weight = (
            (target_baseline_val_base / baseline_total_portfolio_base * ONE_HUNDRED)
            if baseline_total_portfolio_base > ZERO
            else ZERO
        )

        # Relevant cash account check
        matching_cash_acc = next((ca for ca in cash_accounts if ca.currency == asset_currency), None)
        cash_account_exists = matching_cash_acc is not None
        current_currency_cash = matching_cash_acc.balance if matching_cash_acc else ZERO

        cash_baseline_weight = (
            (baseline_total_cash_base / baseline_total_portfolio_base * ONE_HUNDRED)
            if baseline_total_portfolio_base > ZERO
            else ZERO
        )

        # Affordability check for BUY
        is_affordable = True
        cash_shortfall = ZERO
        if tx_type == SimulationType.BUY:
            required_cash = gross_value + fee_input
            if required_cash > current_currency_cash:
                is_affordable = False
                cash_shortfall = required_cash - current_currency_cash
                warnings.append(
                    f"Nakit uyarısı: Gerekli tutar {_to_f(required_cash):,.2f} {asset_currency}, "
                    f"mevcut nakit bakiyeniz {_to_f(current_currency_cash):,.2f} {asset_currency}. "
                    f"Açık: {_to_f(cash_shortfall):,.2f} {asset_currency}."
                )

        if not cash_account_exists and tx_type == SimulationType.BUY:
            warnings.append(f"{asset_currency} cinsinden kayıtlı nakit hesabı bulunamadı; sanal bakiye baz alındı.")

        # ---------------------------------------------------------------------
        # 6. Post-Scenario Aggregations & Invariant Proof
        # ---------------------------------------------------------------------
        gross_value_base = convert(gross_value, asset_currency, base_currency, rate_map)
        net_cash_delta_base = convert(net_cash_delta, asset_currency, base_currency, rate_map)
        fee_base = convert(fee_input, asset_currency, base_currency, rate_map)

        post_target_val_asset_curr = post_holding_qty * ref_price
        post_target_val_base = convert(post_target_val_asset_curr, asset_currency, base_currency, rate_map)

        # Simulated Cash
        sim_cash_balances = dict(baseline_cash_balances)
        sim_cash_balances[asset_currency] = sim_cash_balances.get(asset_currency, ZERO) + net_cash_delta

        post_total_cash_base = sum(
            (convert(bal, cur, base_currency, rate_map) for cur, bal in sim_cash_balances.items()),
            ZERO,
        )

        # Simulated Invested Assets
        # Start from baseline, replace target asset value
        sim_invested_assets_base = ZERO
        target_accounted_for = False

        for p_asset, p_stats in pairs:
            is_target = (
                (asset_obj and p_asset.id == asset_obj.id)
                or (resolved.canonical_instrument_id and p_asset.instrument_id == resolved.canonical_instrument_id)
            )
            if is_target:
                sim_invested_assets_base += post_target_val_base
                target_accounted_for = True
            else:
                sim_invested_assets_base += baseline_asset_vals_base[str(p_asset.id)]

        if not target_accounted_for:
            # Asset was newly bought
            sim_invested_assets_base += post_target_val_base

        post_total_portfolio_base = sim_invested_assets_base + post_total_cash_base

        post_target_weight = (
            (post_target_val_base / post_total_portfolio_base * ONE_HUNDRED)
            if post_total_portfolio_base > ZERO
            else ZERO
        )
        post_cash_weight = (
            (post_total_cash_base / post_total_portfolio_base * ONE_HUNDRED)
            if post_total_portfolio_base > ZERO
            else ZERO
        )

        # ---------------------------------------------------------------------
        # 7. Allocation Breakdowns (Before & After)
        # ---------------------------------------------------------------------
        alloc_before = cls._compute_allocation_snapshot(
            pairs=pairs,
            cash_balances=baseline_cash_balances,
            total_portfolio_base=baseline_total_portfolio_base,
            base_currency=base_currency,
            rate_map=rate_map,
        )

        alloc_after = cls._compute_simulated_allocation_snapshot(
            pairs=pairs,
            sim_cash_balances=sim_cash_balances,
            target_symbol=display_symbol,
            target_name=display_name,
            target_asset_type=raw_asset_type,
            target_post_val_base=post_target_val_base,
            target_asset_id=str(asset_obj.id) if asset_obj else None,
            target_instrument_id=str(resolved.canonical_instrument_id) if resolved.canonical_instrument_id else None,
            total_portfolio_base=post_total_portfolio_base,
            base_currency=base_currency,
            rate_map=rate_map,
        )

        # ---------------------------------------------------------------------
        # 8. Assemble Result Contract
        # ---------------------------------------------------------------------
        assumptions = SimulationAssumptions(
            price=_to_f(ref_price),
            price_currency=asset_currency,
            price_source=price_source,
            price_timestamp=None,
            fee=_to_f(fee_input),
            fee_currency=asset_currency,
            affects_cash=True,
            notes=f"Referans fiyat kaynağı: {price_source.value}",
        )

        before_snapshot = SimulationPortfolioSnapshot(
            total_value_base=_to_f(baseline_total_portfolio_base),
            total_invested_assets_base=_to_f(baseline_invested_base),
            base_currency=base_currency,
            target_position=SimulationPositionSnapshot(
                quantity=_to_f(baseline_holding_qty),
                position_value=_to_f(target_baseline_val_asset_curr),
                position_value_base=_to_f(target_baseline_val_base),
                weight_pct=_to_f(target_baseline_weight),
            ),
            cash=SimulationCashSnapshot(
                balance=_to_f(current_currency_cash),
                currency=asset_currency,
                total_cash_base=_to_f(baseline_total_cash_base),
                cash_weight_pct=_to_f(cash_baseline_weight),
                cash_account_exists=cash_account_exists,
            ),
        )

        tx_spec = SimulationTransactionSpec(
            transaction_type=tx_type,
            quantity=_to_f(sim_quantity),
            gross_value=_to_f(gross_value),
            gross_value_base=_to_f(gross_value_base),
            fee=_to_f(fee_input),
            net_cash_delta=_to_f(net_cash_delta),
            net_cash_delta_base=_to_f(net_cash_delta_base),
            currency=asset_currency,
            is_affordable=is_affordable,
            cash_shortfall=_to_f(cash_shortfall),
        )

        after_snapshot = SimulationPortfolioSnapshot(
            total_value_base=_to_f(post_total_portfolio_base),
            total_invested_assets_base=_to_f(sim_invested_assets_base),
            base_currency=base_currency,
            target_position=SimulationPositionSnapshot(
                quantity=_to_f(post_holding_qty),
                position_value=_to_f(post_target_val_asset_curr),
                position_value_base=_to_f(post_target_val_base),
                weight_pct=_to_f(post_target_weight),
            ),
            cash=SimulationCashSnapshot(
                balance=_to_f(sim_cash_balances.get(asset_currency, ZERO)),
                currency=asset_currency,
                total_cash_base=_to_f(post_total_cash_base),
                cash_weight_pct=_to_f(post_cash_weight),
                cash_account_exists=cash_account_exists,
            ),
        )

        return SimulationResult(
            status="success" if is_affordable else "warning",
            simulation_type=tx_type,
            instrument=instrument_info,
            assumptions=assumptions,
            validation=SimulationValidation(is_valid=True),
            before=before_snapshot,
            transaction=tx_spec,
            after=after_snapshot,
            allocation_before=alloc_before,
            allocation_after=alloc_after,
            warnings=warnings,
        )

    # -----------------------------------------------------------------------
    # Allocation Calculation Helpers
    # -----------------------------------------------------------------------

    @classmethod
    def _compute_allocation_snapshot(
        cls,
        pairs: List[Tuple[Asset, Dict[str, Any]]],
        cash_balances: Dict[str, Decimal],
        total_portfolio_base: Decimal,
        base_currency: str,
        rate_map: Any,
    ) -> SimulationAllocationSnapshot:
        by_type_map: Dict[str, Decimal] = {}
        by_asset_list: List[Dict[str, Any]] = []

        for asset, stats in pairs:
            val_base = _current_value_in(asset, stats, base_currency, rate_map)
            atype = asset.asset_type.value if hasattr(asset.asset_type, "value") else str(asset.asset_type)
            by_type_map[atype] = by_type_map.get(atype, ZERO) + val_base

            pct = (val_base / total_portfolio_base * ONE_HUNDRED) if total_portfolio_base > ZERO else ZERO
            by_asset_list.append({
                "asset_id": str(asset.id),
                "symbol": asset.symbol,
                "name": asset.name,
                "asset_type": atype,
                "value": _to_f(val_base),
                "percentage": _to_f(pct),
            })

        total_cash_base = sum(
            (convert(bal, cur, base_currency, rate_map) for cur, bal in cash_balances.items()),
            ZERO,
        )
        if total_cash_base != ZERO:
            by_type_map["CASH"] = total_cash_base

        by_type_list: List[Dict[str, Any]] = []
        for atype, val in by_type_map.items():
            pct = (val / total_portfolio_base * ONE_HUNDRED) if total_portfolio_base > ZERO else ZERO
            by_type_list.append({
                "asset_type": atype,
                "value": _to_f(val),
                "percentage": _to_f(pct),
            })

        return SimulationAllocationSnapshot(by_type=by_type_list, by_asset=by_asset_list)

    @classmethod
    def _compute_simulated_allocation_snapshot(
        cls,
        pairs: List[Tuple[Asset, Dict[str, Any]]],
        sim_cash_balances: Dict[str, Decimal],
        target_symbol: str,
        target_name: str,
        target_asset_type: str,
        target_post_val_base: Decimal,
        target_asset_id: Optional[str],
        target_instrument_id: Optional[str],
        total_portfolio_base: Decimal,
        base_currency: str,
        rate_map: Any,
    ) -> SimulationAllocationSnapshot:
        by_type_map: Dict[str, Decimal] = {}
        by_asset_list: List[Dict[str, Any]] = []
        target_processed = False

        for asset, stats in pairs:
            is_target = (
                (target_asset_id and str(asset.id) == target_asset_id)
                or (target_instrument_id and str(asset.instrument_id) == target_instrument_id)
            )
            atype = asset.asset_type.value if hasattr(asset.asset_type, "value") else str(asset.asset_type)

            if is_target:
                val_base = target_post_val_base
                target_processed = True
            else:
                val_base = _current_value_in(asset, stats, base_currency, rate_map)

            by_type_map[atype] = by_type_map.get(atype, ZERO) + val_base

            pct = (val_base / total_portfolio_base * ONE_HUNDRED) if total_portfolio_base > ZERO else ZERO
            by_asset_list.append({
                "asset_id": str(asset.id),
                "symbol": asset.symbol,
                "name": asset.name,
                "asset_type": atype,
                "value": _to_f(val_base),
                "percentage": _to_f(pct),
            })

        if not target_processed:
            # Newly bought asset
            val_base = target_post_val_base
            by_type_map[target_asset_type] = by_type_map.get(target_asset_type, ZERO) + val_base
            pct = (val_base / total_portfolio_base * ONE_HUNDRED) if total_portfolio_base > ZERO else ZERO
            by_asset_list.append({
                "asset_id": target_asset_id,
                "symbol": target_symbol,
                "name": target_name,
                "asset_type": target_asset_type,
                "value": _to_f(val_base),
                "percentage": _to_f(pct),
            })

        total_cash_base = sum(
            (convert(bal, cur, base_currency, rate_map) for cur, bal in sim_cash_balances.items()),
            ZERO,
        )
        if total_cash_base != ZERO:
            by_type_map["CASH"] = total_cash_base

        by_type_list: List[Dict[str, Any]] = []
        for atype, val in by_type_map.items():
            pct = (val / total_portfolio_base * ONE_HUNDRED) if total_portfolio_base > ZERO else ZERO
            by_type_list.append({
                "asset_type": atype,
                "value": _to_f(val),
                "percentage": _to_f(pct),
            })

        return SimulationAllocationSnapshot(by_type=by_type_list, by_asset=by_asset_list)

    @classmethod
    def _make_error_result(
        cls,
        tx_type: SimulationType,
        query: str,
        reason: str,
        message: str,
        instrument_info: Optional[SimulationInstrumentInfo] = None,
        base_currency: str = "TRY",
    ) -> SimulationResult:
        inst = instrument_info or SimulationInstrumentInfo(
            symbol=query.upper(),
            name=query,
            asset_type="CUSTOM",
            currency="TRY",
            is_owned=False,
        )
        empty_pos = SimulationPositionSnapshot(quantity=0.0, position_value=0.0, position_value_base=0.0, weight_pct=0.0)
        empty_cash = SimulationCashSnapshot(balance=0.0, currency="TRY", total_cash_base=0.0, cash_weight_pct=0.0)
        empty_snap = SimulationPortfolioSnapshot(
            total_value_base=0.0,
            total_invested_assets_base=0.0,
            base_currency=base_currency,
            target_position=empty_pos,
            cash=empty_cash,
        )
        empty_tx = SimulationTransactionSpec(
            transaction_type=tx_type,
            quantity=0.0,
            gross_value=0.0,
            gross_value_base=0.0,
            net_cash_delta=0.0,
            net_cash_delta_base=0.0,
            currency="TRY",
            is_affordable=False,
        )
        return SimulationResult(
            status="error",
            simulation_type=tx_type,
            instrument=inst,
            assumptions=SimulationAssumptions(price_source=PriceSource.UNKNOWN),
            validation=SimulationValidation(is_valid=False, reason=reason, message=message),
            before=empty_snap,
            transaction=empty_tx,
            after=empty_snap,
            allocation_before=SimulationAllocationSnapshot(),
            allocation_after=SimulationAllocationSnapshot(),
            warnings=[message],
        )
