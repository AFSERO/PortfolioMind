"""Dashboard business logic — summary, allocation, timeline, snapshots.

After the transaction-model refactor, each asset's cost basis and quantity
come from ``portfolio_stats.compute_stats`` over its transactions.  Values
are converted to the user's base currency via the forex rate map.

Convention:
    unrealized_pl = current_market_value − cost_basis_of_remaining_position
    realized_pl   = cumulative gain/loss from SELL transactions (in avg_cost_currency)
    total_pl      = unrealized_pl + realized_pl
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.asset import Asset, AssetType
from app.models.cash import CashAccount
from app.models.liability import Liability
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.transaction import Transaction
from app.services.portfolio_stats import compute_stats
from app.utils.currency import (
    build_rate_map,
    convert,
    exchange_rate_metadata,
    require_rates,
)

ZERO = Decimal("0")


def _f(d: Decimal) -> float:
    return float(d)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


async def _load_assets_with_stats(
    db: AsyncSession, user_id: UUID
) -> list[tuple[Asset, dict]]:
    """Return (Asset, stats) pairs for every asset owned by *user_id*."""
    result = await db.execute(
        select(Asset)
        .options(selectinload(Asset.opening_position))
        .where(Asset.user_id == user_id)
    )
    assets = list(result.scalars().all())
    if not assets:
        return []

    asset_ids = [a.id for a in assets]
    tx_result = await db.execute(
        select(Transaction).where(Transaction.asset_id.in_(asset_ids))
    )
    txns_by_asset: dict[UUID, list[Transaction]] = {aid: [] for aid in asset_ids}
    for tx in tx_result.scalars().all():
        txns_by_asset[tx.asset_id].append(tx)

    return [
        (a, compute_stats(txns_by_asset[a.id], opening_position=a.opening_position))
        for a in assets
    ]


# ---------------------------------------------------------------------------
# Per-asset value / cost helpers
# ---------------------------------------------------------------------------


def _effective_price_and_currency(
    asset: Asset, stats: dict
) -> tuple[Decimal, Optional[str]]:
    """Return (price_per_unit, currency) — prefer current_price, else avg_cost."""
    if asset.current_price is not None and asset.current_price_currency:
        return asset.current_price, asset.current_price_currency
    if stats["avg_cost"] is not None and stats["avg_cost_currency"]:
        return stats["avg_cost"], stats["avg_cost_currency"]
    return ZERO, None


def _current_value_in(
    asset: Asset, stats: dict, base_currency: str, rate_map: dict[str, Decimal]
) -> Decimal:
    price, cur = _effective_price_and_currency(asset, stats)
    if cur is None:
        return ZERO
    value = price * stats["total_quantity"]
    return convert(value, cur, base_currency, rate_map)


def _cost_basis_in(
    stats: dict, base_currency: str, rate_map: dict[str, Decimal]
) -> Decimal:
    cur = stats["avg_cost_currency"]
    if cur is None:
        return ZERO
    return convert(stats["total_cost"] or ZERO, cur, base_currency, rate_map)


def _realized_pl_in(
    stats: dict, base_currency: str, rate_map: dict[str, Decimal]
) -> Decimal:
    cur = stats["avg_cost_currency"]
    if cur is None:
        return ZERO
    return convert(stats["realized_pl"] or ZERO, cur, base_currency, rate_map)


def _collect_currencies(pairs: list[tuple[Asset, dict]]) -> set[str]:
    currencies: set[str] = set()
    for asset, stats in pairs:
        if asset.current_price_currency:
            currencies.add(asset.current_price_currency)
        if stats["avg_cost_currency"]:
            currencies.add(stats["avg_cost_currency"])
    return currencies


async def _load_cash_accounts(
    db: AsyncSession, user_id: UUID
) -> list[CashAccount]:
    result = await db.execute(
        select(CashAccount).where(CashAccount.user_id == user_id)
    )
    return list(result.scalars().all())


def _cash_currencies(accounts: list[CashAccount]) -> set[str]:
    return {a.currency for a in accounts if (a.balance or ZERO) != ZERO}


def _total_cash_in(
    accounts: list[CashAccount],
    base_currency: str,
    rate_map: dict[str, Decimal],
) -> Decimal:
    total = ZERO
    for a in accounts:
        balance = a.balance or ZERO
        if balance == ZERO:
            continue
        total += convert(balance, a.currency, base_currency, rate_map)
    return total


async def _load_active_liabilities(
    db: AsyncSession, user_id: UUID
) -> list[Liability]:
    result = await db.execute(
        select(Liability).where(
            Liability.user_id == user_id,
            Liability.is_active.is_(True),
        )
    )
    return list(result.scalars().all())


def _liability_currencies(liabilities: list[Liability]) -> set[str]:
    return {
        liability.currency
        for liability in liabilities
        if (liability.current_balance or ZERO) != ZERO
    }


def _total_liabilities_in(
    liabilities: list[Liability],
    base_currency: str,
    rate_map: dict[str, Decimal],
) -> Decimal:
    total = ZERO
    for liability in liabilities:
        balance = liability.current_balance or ZERO
        if balance == ZERO:
            continue
        total += convert(balance, liability.currency, base_currency, rate_map)
    return total


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


async def get_summary(
    db: AsyncSession, user_id: UUID, base_currency: str = "TRY"
) -> dict:
    pairs = await _load_assets_with_stats(db, user_id)
    cash_accounts = await _load_cash_accounts(db, user_id)
    liabilities = await _load_active_liabilities(db, user_id)

    if (
        not pairs
        and not _cash_currencies(cash_accounts)
        and not _liability_currencies(liabilities)
    ):
        return {
            "total_value": 0.0,
            "total_assets": 0.0,
            "total_liabilities": 0.0,
            "net_worth": 0.0,
            "total_cost": 0.0,
            "total_pl": 0.0,
            "total_pl_pct": 0.0,
            "unrealized_pl": 0.0,
            "realized_pl": 0.0,
            "total_cash": 0.0,
            "asset_count": 0,
            "liability_count": len(liabilities),
            "best_performer": None,
            "worst_performer": None,
            "by_type_summary": [],
            "base_currency": base_currency,
            "exchange_rates": {"status": "complete", "rates": []},
        }

    currencies = (
        _collect_currencies(pairs)
        | _cash_currencies(cash_accounts)
        | _liability_currencies(liabilities)
    )
    rate_map = await build_rate_map(currencies, base_currency, db)
    require_rates(currencies, base_currency, rate_map)

    total_value = ZERO
    total_cost = ZERO
    total_realized = ZERO
    best: Optional[dict] = None
    worst: Optional[dict] = None
    type_buckets: dict[str, dict] = {}
    unknown_cost = any(s["total_cost"] is None for _, s in pairs)

    for asset, stats in pairs:
        val = _current_value_in(asset, stats, base_currency, rate_map)
        cost = _cost_basis_in(stats, base_currency, rate_map)
        realized = _realized_pl_in(stats, base_currency, rate_map)
        unreal = val - cost
        pl = unreal + realized
        pl_pct = (pl / cost * Decimal("100")) if cost != ZERO else ZERO

        total_value += val
        total_cost += cost
        total_realized += realized

        perf = {
            "asset_id": str(asset.id),
            "name": asset.name,
            "symbol": asset.symbol,
            "pl": pl,
            "pl_pct": pl_pct,
        }
        if stats["total_cost"] is not None and (best is None or pl_pct > best["pl_pct"]):
            best = perf
        if stats["total_cost"] is not None and (worst is None or pl_pct < worst["pl_pct"]):
            worst = perf

        atype = asset.asset_type.value
        bucket = type_buckets.setdefault(
            atype, {"value": ZERO, "cost": ZERO, "realized": ZERO, "count": 0}
        )
        bucket["value"] += val
        bucket["cost"] += cost
        bucket["realized"] += realized
        bucket["count"] += 1
        bucket["unknown"] = bucket.get("unknown", False) or stats["total_cost"] is None

    total_unrealized = total_value - total_cost
    total_pl = total_unrealized + total_realized
    total_pl_pct = (
        (total_pl / total_cost * Decimal("100")) if total_cost != ZERO else ZERO
    )

    total_cash = _total_cash_in(cash_accounts, base_currency, rate_map)
    total_assets = total_value + total_cash
    total_liabilities = _total_liabilities_in(
        liabilities, base_currency, rate_map
    )
    net_worth = total_assets - total_liabilities

    by_type = []
    for atype, b in type_buckets.items():
        bunreal = b["value"] - b["cost"]
        bpl = bunreal + b["realized"]
        bpct = (bpl / b["cost"] * Decimal("100")) if b["cost"] != ZERO else ZERO
        by_type.append(
            {
                "asset_type": atype,
                "total_value": _f(b["value"]),
                "total_cost": None if b.get("unknown") else _f(b["cost"]),
                "pl": None if b.get("unknown") else _f(bpl),
                "pl_pct": None if b.get("unknown") else _f(bpct),
                "count": b["count"],
            }
        )

    if best is not None:
        best = {**best, "pl": _f(best["pl"]), "pl_pct": _f(best["pl_pct"])}
    if worst is not None:
        worst = {**worst, "pl": _f(worst["pl"]), "pl_pct": _f(worst["pl_pct"])}

    return {
        # Backward-compatible alias: total_value remains gross assets.
        "total_value": _f(total_assets),
        "total_assets": _f(total_assets),
        "total_liabilities": _f(total_liabilities),
        "net_worth": _f(net_worth),
        "total_cost": None if unknown_cost else _f(total_cost),
        "total_pl": None if unknown_cost else _f(total_pl),
        "total_pl_pct": None if unknown_cost else _f(total_pl_pct),
        "unrealized_pl": None if unknown_cost else _f(total_unrealized),
        "realized_pl": None if unknown_cost else _f(total_realized),
        "total_cash": _f(total_cash),
        "asset_count": len(pairs),
        "liability_count": len(liabilities),
        "best_performer": best,
        "worst_performer": worst,
        "by_type_summary": by_type,
        "base_currency": base_currency,
        "exchange_rates": exchange_rate_metadata(rate_map),
    }


# ---------------------------------------------------------------------------
# Allocation
# ---------------------------------------------------------------------------


async def get_allocation(
    db: AsyncSession, user_id: UUID, base_currency: str = "TRY"
) -> dict:
    pairs = await _load_assets_with_stats(db, user_id)
    cash_accounts = await _load_cash_accounts(db, user_id)

    currencies = _collect_currencies(pairs) | _cash_currencies(cash_accounts)
    rate_map = await build_rate_map(currencies, base_currency, db)
    require_rates(currencies, base_currency, rate_map)

    total_value = ZERO
    by_type: dict[str, Decimal] = {}
    by_asset_raw: list[tuple[Asset, Decimal]] = []

    for asset, stats in pairs:
        val = _current_value_in(asset, stats, base_currency, rate_map)
        total_value += val
        atype = asset.asset_type.value
        by_type[atype] = by_type.get(atype, ZERO) + val
        by_asset_raw.append((asset, val))

    total_cash = _total_cash_in(cash_accounts, base_currency, rate_map)
    if total_cash != ZERO:
        by_type["CASH"] = total_cash
    total_value = total_value + total_cash

    type_alloc = []
    for atype, val in by_type.items():
        pct = (val / total_value * Decimal("100")) if total_value != ZERO else ZERO
        type_alloc.append(
            {"asset_type": atype, "value": _f(val), "percentage": _f(pct)}
        )

    by_asset = []
    for asset, val in by_asset_raw:
        pct = (val / total_value * Decimal("100")) if total_value != ZERO else ZERO
        by_asset.append(
            {
                "asset_id": str(asset.id),
                "name": asset.name,
                "symbol": asset.symbol,
                "asset_type": asset.asset_type.value,
                "value": _f(val),
                "percentage": _f(pct),
            }
        )

    return {
        "total_value": _f(total_value),
        "by_type": type_alloc,
        "by_asset": by_asset,
        "base_currency": base_currency,
        "exchange_rates": exchange_rate_metadata(rate_map),
    }


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------


async def get_timeline(
    db: AsyncSession, user_id: UUID, days: int = 90
) -> list[dict]:
    cutoff_date = datetime.now(timezone.utc).date() - timedelta(days=max(0, days - 1))
    result = await db.execute(
        select(PortfolioSnapshot)
        .where(
            PortfolioSnapshot.user_id == user_id,
            PortfolioSnapshot.snapshot_date >= cutoff_date,
        )
        .order_by(PortfolioSnapshot.snapshot_date.asc())
    )
    snapshots = list(result.scalars().all())
    return [
        {
            "date": s.snapshot_date.isoformat(),
            "total_value_try": _f(s.total_value_try),
            "total_value_usd": _f(s.total_value_usd),
            "total_assets_try": _f(s.total_assets_try)
            if s.total_assets_try is not None
            else None,
            "total_assets_usd": _f(s.total_assets_usd)
            if s.total_assets_usd is not None
            else None,
            "total_liabilities_try": _f(s.total_liabilities_try)
            if s.total_liabilities_try is not None
            else None,
            "total_liabilities_usd": _f(s.total_liabilities_usd)
            if s.total_liabilities_usd is not None
            else None,
            "net_worth_try": _f(s.net_worth_try)
            if s.net_worth_try is not None
            else None,
            "net_worth_usd": _f(s.net_worth_usd)
            if s.net_worth_usd is not None
            else None,
            "value_semantics": "net_worth"
            if s.net_worth_try is not None and s.net_worth_usd is not None
            else "gross_assets",
        }
        for s in snapshots
    ]


# ---------------------------------------------------------------------------
# Daily snapshot creation
# ---------------------------------------------------------------------------


async def create_daily_snapshot(
    db: AsyncSession,
    user_id: UUID,
    snapshot_date: Optional[date] = None,
) -> Optional[tuple[PortfolioSnapshot, dict]]:
    if snapshot_date is None:
        snapshot_date = datetime.now(timezone.utc).date()

    pairs = await _load_assets_with_stats(db, user_id)
    cash_accounts = await _load_cash_accounts(db, user_id)
    liabilities = await _load_active_liabilities(db, user_id)
    nonzero_cash = [a for a in cash_accounts if (a.balance or ZERO) != ZERO]
    nonzero_liabilities = [
        liability
        for liability in liabilities
        if (liability.current_balance or ZERO) != ZERO
    ]
    if not pairs and not nonzero_cash and not nonzero_liabilities:
        return None

    currencies = (
        _collect_currencies(pairs)
        | _cash_currencies(cash_accounts)
        | _liability_currencies(liabilities)
    )
    rate_map_try = await build_rate_map(currencies, "TRY", db)
    rate_map_usd = await build_rate_map(currencies, "USD", db)
    require_rates(currencies, "TRY", rate_map_try)
    require_rates(currencies, "USD", rate_map_usd)

    total_assets_try = ZERO
    total_assets_usd = ZERO
    for asset, stats in pairs:
        total_assets_try += _current_value_in(asset, stats, "TRY", rate_map_try)
        total_assets_usd += _current_value_in(asset, stats, "USD", rate_map_usd)
    total_assets_try += _total_cash_in(cash_accounts, "TRY", rate_map_try)
    total_assets_usd += _total_cash_in(cash_accounts, "USD", rate_map_usd)
    total_liabilities_try = _total_liabilities_in(
        liabilities, "TRY", rate_map_try
    )
    total_liabilities_usd = _total_liabilities_in(
        liabilities, "USD", rate_map_usd
    )
    net_worth_try = total_assets_try - total_liabilities_try
    net_worth_usd = total_assets_usd - total_liabilities_usd

    existing_result = await db.execute(
        select(PortfolioSnapshot).where(
            PortfolioSnapshot.user_id == user_id,
            PortfolioSnapshot.snapshot_date == snapshot_date,
        )
    )
    snapshot = existing_result.scalar_one_or_none()

    if snapshot is not None:
        snapshot.total_value_try = total_assets_try
        snapshot.total_value_usd = total_assets_usd
        snapshot.total_assets_try = total_assets_try
        snapshot.total_assets_usd = total_assets_usd
        snapshot.total_liabilities_try = total_liabilities_try
        snapshot.total_liabilities_usd = total_liabilities_usd
        snapshot.net_worth_try = net_worth_try
        snapshot.net_worth_usd = net_worth_usd
    else:
        snapshot = PortfolioSnapshot(
            user_id=user_id,
            # Keep the legacy columns gross-assets compatible.
            total_value_try=total_assets_try,
            total_value_usd=total_assets_usd,
            total_assets_try=total_assets_try,
            total_assets_usd=total_assets_usd,
            total_liabilities_try=total_liabilities_try,
            total_liabilities_usd=total_liabilities_usd,
            net_worth_try=net_worth_try,
            net_worth_usd=net_worth_usd,
            snapshot_date=snapshot_date,
        )
        db.add(snapshot)

    try:
        await db.commit()
    except IntegrityError:
        # Another concurrent request inserted today's snapshot right before us.
        # Safely rollback, load the committed row, update it, and commit.
        await db.rollback()
        retry_result = await db.execute(
            select(PortfolioSnapshot).where(
                PortfolioSnapshot.user_id == user_id,
                PortfolioSnapshot.snapshot_date == snapshot_date,
            )
        )
        snapshot = retry_result.scalar_one_or_none()
        if snapshot is not None:
            snapshot.total_value_try = total_assets_try
            snapshot.total_value_usd = total_assets_usd
            snapshot.total_assets_try = total_assets_try
            snapshot.total_assets_usd = total_assets_usd
            snapshot.total_liabilities_try = total_liabilities_try
            snapshot.total_liabilities_usd = total_liabilities_usd
            snapshot.net_worth_try = net_worth_try
            snapshot.net_worth_usd = net_worth_usd
            await db.commit()
        else:
            raise
    except Exception:
        await db.rollback()
        raise
    await db.refresh(snapshot)
    return snapshot, {
        "TRY": exchange_rate_metadata(rate_map_try),
        "USD": exchange_rate_metadata(rate_map_usd),
    }

