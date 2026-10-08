"""Model-facing action proposal tools for PortfolioMind Copilot V2.

CORE SAFETY INVARIANTS:
1. Classification is PROPOSAL: AI NEVER directly mutates portfolio or financial state.
2. Proposal tools only create a PENDING CopilotActionProposal record.
3. Every proposal requires explicit user confirmation via authenticated UI/API.
4. Execution is performed ONLY by deterministic domain services in ActionExecutor.
5. Entity resolution is strictly enforced via EntityResolver: no unverified UUIDs or mixed instruments.
6. Product boundary: mutations are internal PortfolioMind bookkeeping records, not broker/exchange orders.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.asset import Asset, AssetType
from app.models.copilot import CopilotActionProposal
from app.models.instrument import Instrument
from app.models.opportunity import WatchlistItem, WatchlistPriority
from app.models.transaction import Transaction
from app.services.copilot_v2.action_contracts import (
    ACTION_PROPOSAL_TTL,
    ActionProposalStatusV2,
    ActionProposalType,
    DecisionNoteProposalParams,
    TransactionProposalParams,
    WatchlistProposalParams,
)
from app.services.copilot_v2.entity_resolver import EntityResolver
from app.services.portfolio_stats import compute_stats

logger = logging.getLogger(__name__)


async def _get_current_asset_holding_qty(db: AsyncSession, asset: Asset) -> Decimal:
    """Calculate the current total quantity held for an asset."""
    stmt = (
        select(Asset)
        .options(selectinload(Asset.opening_position))
        .where(Asset.id == asset.id)
    )
    asset_obj = (await db.execute(stmt)).scalar_one_or_none() or asset

    tx_stmt = select(Transaction).where(Transaction.asset_id == asset.id)
    txns = list((await db.execute(tx_stmt)).scalars().all())
    stats = compute_stats(txns, opening_position=asset_obj.opening_position)
    return Decimal(str(stats.get("total_quantity", "0")))


# ---------------------------------------------------------------------------
# Tool 1: propose_transaction_record
# ---------------------------------------------------------------------------


async def propose_transaction_record_handler(
    db: AsyncSession,
    user_id: UUID,
    symbol_or_name: str,
    transaction_type: str,
    quantity: float,
    price: Optional[float] = None,
    currency: Optional[str] = "TRY",
    transaction_date: Optional[str] = None,
    notes: Optional[str] = None,
    affects_cash: bool = True,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Propose creating an internal portfolio transaction bookkeeping record.

    Validates entity resolution, quantity, holding sufficiency for SELL, and stages
    a PENDING CopilotActionProposal requiring explicit user confirmation.
    """
    if quantity <= 0:
        return {
            "status": "error",
            "message": "İşlem adedi sıfırdan büyük olmalıdır.",
        }

    tx_type_upper = transaction_type.strip().upper()
    if tx_type_upper not in ("BUY", "SELL"):
        return {
            "status": "error",
            "message": "Geçersiz işlem tipi. Yalnızca 'BUY' veya 'SELL' desteklenir.",
        }

    # 1. Canonical Entity Resolution
    resolved = await EntityResolver.resolve(db, query=symbol_or_name, user_id=user_id)
    if resolved.is_ambiguous:
        candidate_names = [f"{c['symbol']} ({c['name']})" for c in resolved.ambiguous_candidates]
        return {
            "status": "ambiguous",
            "message": f"'{symbol_or_name}' için birden fazla enstrüman bulundu: {', '.join(candidate_names)}. Lütfen tam sembolü belirtiniz.",
            "candidates": resolved.ambiguous_candidates,
        }

    # 2. Holdings Check & Price Resolution
    warnings: List[str] = []
    current_qty = Decimal("0")
    asset: Optional[Asset] = resolved.asset

    if asset is not None:
        current_qty = await _get_current_asset_holding_qty(db, asset)
    elif resolved.is_owned:
        current_qty = Decimal("0")

    # If selling, verify ownership and holding quantity
    qty_decimal = Decimal(str(quantity))
    if tx_type_upper == "SELL":
        if not resolved.is_owned or asset is None:
            return {
                "status": "error",
                "message": f"Portföyünüzde '{symbol_or_name}' bulunmuyor. Sahip olunmayan varlık için satış kaydı oluşturulamaz.",
            }
        if qty_decimal > current_qty:
            warnings.append(
                f"Satılmak istenen miktar ({qty_decimal:,.4f}), mevcut portföy bakiyenizden ({current_qty:,.4f}) fazladır. "
                "İşlem uygulandığında negatif bakiye oluşabilir."
            )

    # Price fallback if not explicitly provided
    resolved_currency = currency or (asset.current_price_currency if asset else "TRY") or "TRY"
    resolved_price = Decimal(str(price)) if (price is not None and price > 0) else None

    if resolved_price is None:
        if asset and asset.current_price and asset.current_price > 0:
            resolved_price = Decimal(str(asset.current_price))
            warnings.append(
                f"İşlem fiyatı belirtilmedi; güncel piyasa fiyatı ({resolved_price:,.2f} {resolved_currency}) baz alındı."
            )
        else:
            return {
                "status": "error",
                "message": f"'{symbol_or_name}' için işlem birim fiyatı belirtilmedi ve kayıtlı bir piyasa fiyatı bulunamadı. Lütfen işlem fiyatını belirtiniz.",
            }

    # 3. Compute deterministic impact
    prev_qty_val = float(current_qty)
    new_qty_val = float(current_qty + qty_decimal) if tx_type_upper == "BUY" else float(current_qty - qty_decimal)
    total_amt = float(qty_decimal * resolved_price)
    cash_delta = -total_amt if (tx_type_upper == "BUY" and affects_cash) else (total_amt if affects_cash else 0.0)

    # 4. Human-readable summary
    action_label = "ALIŞ" if tx_type_upper == "BUY" else "SATIŞ"
    display_symbol = resolved.symbol or symbol_or_name.upper()
    display_name = resolved.canonical_name or display_symbol
    summary = (
        f"{float(qty_decimal):,.4f} adet {display_name} ({display_symbol}) için "
        f"{float(resolved_price):,.2f} {resolved_currency} fiyattan {action_label} kaydı "
        f"(Toplam: {total_amt:,.2f} {resolved_currency})"
    )

    parsed_date = transaction_date or str(date.today())

    # 5. Build and validate payload
    try:
        params = TransactionProposalParams(
            symbol=display_symbol,
            name=display_name,
            transaction_type=tx_type_upper,
            quantity=qty_decimal,
            price=resolved_price,
            currency=resolved_currency,
            transaction_date=parsed_date,
            notes=notes,
            affects_cash=affects_cash,
            asset_id=str(asset.id) if asset else None,
            instrument_id=str(resolved.canonical_instrument_id) if resolved.canonical_instrument_id else None,
        )
    except Exception as val_err:
        return {"status": "error", "message": f"Geçersiz işlem parametreleri: {str(val_err)}"}

    expected_impact = {
        "previous_quantity": prev_qty_val,
        "new_quantity": new_qty_val,
        "total_amount": total_amt,
        "cash_delta": cash_delta,
        "currency": resolved_currency,
    }

    current_snapshot = {
        "current_quantity": prev_qty_val,
        "current_price": float(resolved_price),
        "is_owned": resolved.is_owned,
    }

    proposal = CopilotActionProposal(
        user_id=user_id,
        action_type=ActionProposalType.TRANSACTION_RECORD.value,
        permission_level="REQUIRES_CONFIRMATION",
        status=ActionProposalStatusV2.PENDING.value,
        parameters=params.model_dump(mode="json"),
        expected_impact=expected_impact,
        current_state_snapshot=current_snapshot,
        human_readable_summary=summary,
        warnings=warnings,
        idempotency_key=f"tx_prop_{uuid.uuid4()}",
        expires_at=datetime.now(timezone.utc) + ACTION_PROPOSAL_TTL,
    )
    db.add(proposal)
    await db.flush()

    return {
        "status": "success",
        "proposal_id": str(proposal.id),
        "action_type": ActionProposalType.TRANSACTION_RECORD.value,
        "proposal_status": ActionProposalStatusV2.PENDING.value,
        "summary": summary,
        "expected_impact": expected_impact,
        "warnings": warnings,
        "notice": "Bu bir borsa/kurum emri değildir; yalnızca PortfolioMind içi portföy kayıtlarınızı günceller.",
    }


# ---------------------------------------------------------------------------
# Tool 2: propose_watchlist_change
# ---------------------------------------------------------------------------


async def propose_watchlist_change_handler(
    db: AsyncSession,
    user_id: UUID,
    symbol_or_name: str,
    action: str,
    priority: str = "MEDIUM",
    notes: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Propose adding or removing an instrument from the user's watchlist."""
    action_upper = action.strip().upper()
    if action_upper not in ("ADD", "REMOVE"):
        return {
            "status": "error",
            "message": "Geçersiz izleme listesi eylemi. Yalnızca 'ADD' veya 'REMOVE' desteklenir.",
        }

    resolved = await EntityResolver.resolve(db, query=symbol_or_name, user_id=user_id)
    if resolved.is_ambiguous:
        candidates = [f"{c['symbol']} ({c['name']})" for c in resolved.ambiguous_candidates]
        return {
            "status": "ambiguous",
            "message": f"'{symbol_or_name}' için birden fazla enstrüman bulundu: {', '.join(candidates)}.",
            "candidates": resolved.ambiguous_candidates,
        }

    # Verify Instrument existence
    inst_id = resolved.canonical_instrument_id
    if not inst_id and resolved.asset and resolved.asset.instrument_id:
        inst_id = resolved.asset.instrument_id

    display_symbol = resolved.symbol or symbol_or_name.upper()
    display_name = resolved.canonical_name or display_symbol

    warnings: List[str] = []
    is_on_watchlist = False

    if inst_id:
        wl_stmt = select(WatchlistItem).where(
            WatchlistItem.user_id == user_id,
            WatchlistItem.instrument_id == inst_id,
        )
        existing_wl = (await db.execute(wl_stmt)).scalar_one_or_none()
        is_on_watchlist = existing_wl is not None

    if action_upper == "ADD" and is_on_watchlist:
        warnings.append(f"{display_symbol} zaten izleme listenizde yer alıyor.")
    elif action_upper == "REMOVE" and not is_on_watchlist:
        warnings.append(f"{display_symbol} şu anda izleme listenizde bulunmuyor.")

    action_label = "eklenmesi" if action_upper == "ADD" else "çıkarılması"
    summary = f"{display_name} ({display_symbol}) enstrümanının izleme listesine {action_label}"
    if action_upper == "ADD" and priority:
        summary += f" (Öncelik: {priority.upper()})"

    params = WatchlistProposalParams(
        symbol=display_symbol,
        name=display_name,
        action=action_upper,
        priority=priority.upper(),
        notes=notes,
        instrument_id=str(inst_id) if inst_id else None,
    )

    proposal = CopilotActionProposal(
        user_id=user_id,
        action_type=ActionProposalType.WATCHLIST_CHANGE.value,
        permission_level="REQUIRES_CONFIRMATION",
        status=ActionProposalStatusV2.PENDING.value,
        parameters=params.model_dump(mode="json"),
        expected_impact={"action": action_upper, "symbol": display_symbol, "name": display_name},
        current_state_snapshot={"is_on_watchlist": is_on_watchlist},
        human_readable_summary=summary,
        warnings=warnings,
        idempotency_key=f"wl_prop_{uuid.uuid4()}",
        expires_at=datetime.now(timezone.utc) + ACTION_PROPOSAL_TTL,
    )
    db.add(proposal)
    await db.flush()

    return {
        "status": "success",
        "proposal_id": str(proposal.id),
        "action_type": ActionProposalType.WATCHLIST_CHANGE.value,
        "proposal_status": ActionProposalStatusV2.PENDING.value,
        "summary": summary,
        "expected_impact": {"action": action_upper, "symbol": display_symbol},
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Tool 3: propose_decision_note
# ---------------------------------------------------------------------------


async def propose_decision_note_handler(
    db: AsyncSession,
    user_id: UUID,
    title: str,
    notes: str,
    symbol_or_name: Optional[str] = None,
    event_type: str = "NOTE",
    expectation: Optional[str] = None,
    confidence: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Propose recording an investment thesis or rationale note in the decision log."""
    resolved_symbol = None
    resolved_inst_id = None
    warnings: List[str] = []

    if symbol_or_name and symbol_or_name.strip():
        resolved = await EntityResolver.resolve(db, query=symbol_or_name, user_id=user_id)
        if resolved.is_resolved:
            resolved_symbol = resolved.symbol
            resolved_inst_id = resolved.canonical_instrument_id
        elif resolved.is_ambiguous:
            warnings.append(f"'{symbol_or_name}' için birden fazla enstrüman bulundu; genel not olarak ilişkilendirilecek.")

    display_label = f" ({resolved_symbol})" if resolved_symbol else ""
    summary = f"Karar Günlüğüne not eklenmesi{display_label}: '{title}'"

    params = DecisionNoteProposalParams(
        title=title.strip(),
        notes=notes.strip(),
        symbol=resolved_symbol,
        instrument_id=str(resolved_inst_id) if resolved_inst_id else None,
        event_type=event_type.upper(),
        expectation=expectation,
        confidence=confidence,
    )

    proposal = CopilotActionProposal(
        user_id=user_id,
        action_type=ActionProposalType.DECISION_NOTE.value,
        permission_level="REQUIRES_CONFIRMATION",
        status=ActionProposalStatusV2.PENDING.value,
        parameters=params.model_dump(mode="json"),
        expected_impact={"title": title, "symbol": resolved_symbol},
        current_state_snapshot={},
        human_readable_summary=summary,
        warnings=warnings,
        idempotency_key=f"dec_prop_{uuid.uuid4()}",
        expires_at=datetime.now(timezone.utc) + ACTION_PROPOSAL_TTL,
    )
    db.add(proposal)
    await db.flush()

    return {
        "status": "success",
        "proposal_id": str(proposal.id),
        "action_type": ActionProposalType.DECISION_NOTE.value,
        "proposal_status": ActionProposalStatusV2.PENDING.value,
        "summary": summary,
        "expected_impact": {"title": title, "symbol": resolved_symbol},
        "warnings": warnings,
    }


def register_proposal_tools(registry: Any) -> None:
    """Register Phase 3 proposal tools into the tool registry."""
    from app.services.copilot_v2.tools.registry import ToolClassification, ToolDefinition

    registry.register(
        ToolDefinition(
            name="propose_transaction_record",
            description=(
                "Stage a proposal to record an internal portfolio BUY or SELL transaction for user confirmation. "
                "ONLY call when user explicitly intends to record a trade/transaction (e.g. 'THF sattım kaydet', '100 adet THYAO aldım'). "
                "DO NOT call for hypothetical or analytical questions ('satsam ne olur?')."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "symbol_or_name": {
                        "type": "string",
                        "description": "Asset symbol or name (e.g. 'THF', 'THYAO.IS', 'BTC')",
                    },
                    "transaction_type": {
                        "type": "string",
                        "description": "'BUY' or 'SELL'",
                        "enum": ["BUY", "SELL"],
                    },
                    "quantity": {
                        "type": "number",
                        "description": "Quantity/units to buy or sell (must be > 0)",
                    },
                    "price": {
                        "type": "number",
                        "description": "Unit price (optional; if omitted, current known price will be used)",
                    },
                    "currency": {
                        "type": "string",
                        "description": "Currency code (default: TRY)",
                        "default": "TRY",
                    },
                    "transaction_date": {
                        "type": "string",
                        "description": "ISO date (YYYY-MM-DD); defaults to today",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional notes or user rationale",
                    },
                    "affects_cash": {
                        "type": "boolean",
                        "description": "Whether transaction affects cash balance (default: true)",
                        "default": True,
                    },
                },
                "required": ["symbol_or_name", "transaction_type", "quantity"],
            },
            classification=ToolClassification.PROPOSAL,
            handler=propose_transaction_record_handler,
        )
    )

    registry.register(
        ToolDefinition(
            name="propose_watchlist_change",
            description=(
                "Stage a proposal to add or remove an instrument from the user's watchlist for user confirmation. "
                "ONLY call when the user explicitly requests adding or removing an item from the watchlist."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "symbol_or_name": {
                        "type": "string",
                        "description": "Symbol or instrument name to add/remove",
                    },
                    "action": {
                        "type": "string",
                        "description": "'ADD' or 'REMOVE'",
                        "enum": ["ADD", "REMOVE"],
                    },
                    "priority": {
                        "type": "string",
                        "description": "Watchlist priority ('LOW', 'MEDIUM', 'HIGH')",
                        "enum": ["LOW", "MEDIUM", "HIGH"],
                        "default": "MEDIUM",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional reason for tracking",
                    },
                },
                "required": ["symbol_or_name", "action"],
            },
            classification=ToolClassification.PROPOSAL,
            handler=propose_watchlist_change_handler,
        )
    )

    registry.register(
        ToolDefinition(
            name="propose_decision_note",
            description=(
                "Stage a proposal to log an investment thesis, rationale, or review note in the user's formal Decision Log. "
                "Requires explicit user confirmation before recording."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Short title or summary of the decision/rationale",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Full thesis, analysis notes, or rationale",
                    },
                    "symbol_or_name": {
                        "type": "string",
                        "description": "Optional associated asset symbol",
                    },
                    "event_type": {
                        "type": "string",
                        "description": "Event type (e.g. 'NOTE', 'THESIS_UPDATE', 'REVIEW')",
                        "default": "NOTE",
                    },
                    "expectation": {
                        "type": "string",
                        "description": "Optional expected outcome or target timeline",
                    },
                    "confidence": {
                        "type": "string",
                        "description": "Confidence level ('HIGH', 'MEDIUM', 'LOW')",
                    },
                },
                "required": ["title", "notes"],
            },
            classification=ToolClassification.PROPOSAL,
            handler=propose_decision_note_handler,
        )
    )

