"""Transaction CRUD — BUY/SELL events that drive an asset's computed stats.

All monetary arithmetic uses Decimal.  Negative-holding checks are enforced
by re-simulating the running quantity across the asset's transaction history.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.models.decision_log import DecisionEventType
from app.models.opening_position import OpeningPosition
from app.models.transaction import Transaction, TransactionType
from app.schemas.transaction import TransactionCreateRequest, TransactionUpdateRequest
from app.services import cash as cash_service
from app.services.decision_log import log_decision_event


ZERO = Decimal("0")


class NegativeHoldingsError(ValueError):
    """Raised when a create/update/delete would push total_quantity below 0."""


def _resolve_qty_total(
    quantity: Optional[Decimal],
    total_amount: Optional[Decimal],
    price_per_unit: Decimal,
) -> tuple[Decimal, Decimal]:
    """Return (quantity, total_amount), computing whichever was omitted."""
    if quantity is not None:
        return quantity, quantity * price_per_unit
    assert total_amount is not None  # schema guarantees one is set
    return total_amount / price_per_unit, total_amount


async def _load_asset_txns(db: AsyncSession, asset_id: UUID) -> list[Transaction]:
    result = await db.execute(
        select(Transaction).where(Transaction.asset_id == asset_id)
    )
    return list(result.scalars().all())


def _sorted(txns: list[Transaction]) -> list[Transaction]:
    return sorted(
        txns,
        key=lambda t: (
            t.transaction_date,
            t.created_at.date() if t.created_at is not None else t.transaction_date,
        ),
    )


async def _load_asset_initial_qty(db: AsyncSession, asset_id: UUID) -> Decimal:
    result = await db.execute(
        select(OpeningPosition.quantity).where(OpeningPosition.asset_id == asset_id)
    )
    val = result.scalar_one_or_none()
    return val if val is not None else ZERO


def _check_non_negative(txns: list[Transaction], initial_qty: Decimal = ZERO) -> None:
    """Walk transactions chronologically; raise if running qty ever goes < 0."""
    qty = initial_qty
    for t in _sorted(txns):
        if t.transaction_type == TransactionType.BUY:
            qty += t.quantity
        else:
            qty -= t.quantity
            if qty < ZERO:
                raise NegativeHoldingsError(
                    "Transaction would result in negative holdings."
                )


async def stage_transaction(
    db: AsyncSession,
    asset_id: UUID,
    data: TransactionCreateRequest,
    user_id: Optional[UUID] = None,
) -> Transaction:
    """Validate and stage a transaction and its cash effect without committing."""
    qty, total = _resolve_qty_total(data.quantity, data.total_amount, data.price_per_unit)

    tx = Transaction(
        asset_id=asset_id,
        transaction_type=data.transaction_type,
        quantity=qty,
        price_per_unit=data.price_per_unit,
        total_amount=total,
        transaction_currency=data.transaction_currency,
        transaction_date=data.transaction_date,
        notes=data.notes,
        affects_cash=data.affects_cash,
    )

    # Validate against existing txns + initial opening quantity + the new one
    existing = await _load_asset_txns(db, asset_id)
    initial_qty = await _load_asset_initial_qty(db, asset_id)
    _check_non_negative(existing + [tx], initial_qty=initial_qty)

    db.add(tx)
    await db.flush()

    if user_id is not None:
        await cash_service.apply_transaction_effect(db, user_id, tx)

    # Auto-log decision entry for portfolio activity
    stmt = select(Asset).where(Asset.id == asset_id)
    asset_res = await db.execute(stmt)
    asset = asset_res.scalar_one_or_none()
    effective_user_id = user_id or (asset.user_id if asset else None)
    if effective_user_id is not None:
        if data.transaction_type == TransactionType.SELL:
            from app.services.financial_context.assignment_service import AssignmentService
            await AssignmentService.reconcile_post_sell(
                session=db,
                user_id=effective_user_id,
                asset_id=asset_id,
                mandate_id=getattr(data, "mandate_id", None),
                sold_quantity=qty,
            )

        prev_qty = sum(
            t.quantity if t.transaction_type == TransactionType.BUY else -t.quantity
            for t in existing
        )
        new_qty = prev_qty + (qty if data.transaction_type == TransactionType.BUY else -qty)

        asset_label = (asset.symbol or asset.name) if asset else "Asset"
        if data.transaction_type == TransactionType.BUY:
            if prev_qty == ZERO:
                event_type = DecisionEventType.POSITION_OPENED
                title = f"Opened position in {asset_label}"
            else:
                event_type = DecisionEventType.POSITION_ADDED
                title = f"Added to position in {asset_label}"
        else:
            if new_qty == ZERO:
                event_type = DecisionEventType.POSITION_CLOSED
                title = f"Closed position in {asset_label}"
            else:
                event_type = DecisionEventType.POSITION_REDUCED
                title = f"Reduced position in {asset_label}"

        summary = f"{data.transaction_type.value} {qty} @ {data.price_per_unit} {data.transaction_currency}"

        await log_decision_event(
            db=db,
            user_id=effective_user_id,
            event_type=event_type,
            title=title,
            summary=summary,
            instrument_id=asset.instrument_id if asset else None,
            asset_id=asset_id,
            user_rationale=data.notes if data.notes else None,
            related_transaction_id=tx.id,
            metadata={
                "quantity": str(qty),
                "price_per_unit": str(data.price_per_unit),
                "currency": data.transaction_currency,
                "previous_quantity": str(prev_qty),
                "new_quantity": str(new_qty),
            },
            occurred_at=datetime.combine(
                data.transaction_date, datetime.min.time(), tzinfo=timezone.utc
            ),
        )

    return tx


async def create_transaction(
    db: AsyncSession,
    asset_id: UUID,
    data: TransactionCreateRequest,
    user_id: Optional[UUID] = None,
) -> Transaction:
    """Create a transaction and cash effect as one atomic unit of work."""
    try:
        tx = await stage_transaction(db, asset_id, data, user_id=user_id)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    await db.refresh(tx)
    return tx


async def list_transactions(db: AsyncSession, asset_id: UUID) -> list[Transaction]:
    result = await db.execute(
        select(Transaction)
        .where(Transaction.asset_id == asset_id)
        .order_by(Transaction.transaction_date.asc(), Transaction.created_at.asc())
    )
    return list(result.scalars().all())


async def get_transaction(
    db: AsyncSession, tx_id: UUID, user_id: UUID
) -> Optional[Transaction]:
    """Fetch a transaction, verifying ownership via its asset's user_id."""
    result = await db.execute(
        select(Transaction)
        .join(Asset, Transaction.asset_id == Asset.id)
        .where(Transaction.id == tx_id, Asset.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def update_transaction(
    db: AsyncSession,
    tx: Transaction,
    data: TransactionUpdateRequest,
    user_id: Optional[UUID] = None,
) -> Transaction:
    """Apply partial updates, recomputing qty/total as needed."""
    old_snapshot = cash_service.snapshot_tx(tx) if user_id is not None else None
    fields = data.model_fields_set

    try:
        new_price = (
            data.price_per_unit if "price_per_unit" in fields else tx.price_per_unit
        )

        # Resolve qty/total across patch + existing state
        if "quantity" in fields and data.quantity is not None:
            new_qty = data.quantity
            new_total = new_qty * new_price
        elif "total_amount" in fields and data.total_amount is not None:
            new_total = data.total_amount
            new_qty = new_total / new_price
        elif "price_per_unit" in fields:
            # Price changed but qty/total not supplied — keep quantity, recompute total
            new_qty = tx.quantity
            new_total = new_qty * new_price
        else:
            new_qty = tx.quantity
            new_total = tx.total_amount

        tx.quantity = new_qty
        tx.total_amount = new_total
        tx.price_per_unit = new_price
        if "transaction_type" in fields and data.transaction_type is not None:
            tx.transaction_type = data.transaction_type
        if "transaction_currency" in fields and data.transaction_currency is not None:
            tx.transaction_currency = data.transaction_currency
        if "transaction_date" in fields and data.transaction_date is not None:
            tx.transaction_date = data.transaction_date
        if "notes" in fields:
            tx.notes = data.notes
        if "affects_cash" in fields and data.affects_cash is not None:
            tx.affects_cash = data.affects_cash

        all_txns = await _load_asset_txns(db, tx.asset_id)
        # The loaded list contains the now-mutated tx from this session.
        initial_qty = await _load_asset_initial_qty(db, tx.asset_id)
        _check_non_negative(all_txns, initial_qty=initial_qty)

        if user_id is not None and old_snapshot is not None:
            await cash_service.reverse_transaction_effect(db, user_id, old_snapshot)
            await cash_service.apply_transaction_effect(db, user_id, tx)

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    await db.refresh(tx)
    return tx


async def delete_transaction(
    db: AsyncSession, tx: Transaction, user_id: Optional[UUID] = None
) -> None:
    """Remove a transaction; rejects if deletion would invalidate later SELLs."""
    try:
        remaining = [
            t for t in await _load_asset_txns(db, tx.asset_id) if t.id != tx.id
        ]
        initial_qty = await _load_asset_initial_qty(db, tx.asset_id)
        _check_non_negative(remaining, initial_qty=initial_qty)
        snapshot = cash_service.snapshot_tx(tx) if user_id is not None else None

        if user_id is not None and snapshot is not None:
            await cash_service.reverse_transaction_effect(
                db,
                user_id,
                snapshot,
                link_to_transaction=False,
            )

        await db.delete(tx)
        await db.flush()
        await db.commit()
    except Exception:
        await db.rollback()
        raise
