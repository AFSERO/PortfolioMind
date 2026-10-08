"""Cash account operations — deposits, withdrawals, transfers, transaction effects.

Balances may go negative (treated as debt in UI). A cash account is auto-created
on demand if a transaction arrives in a currency the user has no account for.
"""

from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cash import CashAccount, CashMovement, CashMovementType
from app.models.transaction import Transaction, TransactionType


ZERO = Decimal("0")
DEFAULT_CURRENCIES = ("TRY", "USD", "EUR")


async def get_account(
    db: AsyncSession, user_id: UUID, currency: str
) -> Optional[CashAccount]:
    result = await db.execute(
        select(CashAccount).where(
            CashAccount.user_id == user_id,
            CashAccount.currency == currency.upper(),
        )
    )
    return result.scalar_one_or_none()


async def get_or_create_account(
    db: AsyncSession, user_id: UUID, currency: str
) -> CashAccount:
    currency = currency.upper()
    account = await get_account(db, user_id, currency)
    if account is not None:
        return account
    account = CashAccount(user_id=user_id, currency=currency, balance=ZERO)
    db.add(account)
    await db.flush()
    return account


async def list_accounts(db: AsyncSession, user_id: UUID) -> list[CashAccount]:
    result = await db.execute(
        select(CashAccount)
        .where(CashAccount.user_id == user_id)
        .order_by(CashAccount.currency.asc())
    )
    return list(result.scalars().all())


async def list_movements(
    db: AsyncSession, user_id: UUID, limit: int = 100
) -> list[CashMovement]:
    result = await db.execute(
        select(CashMovement)
        .join(CashAccount, CashMovement.cash_account_id == CashAccount.id)
        .where(CashAccount.user_id == user_id)
        .order_by(CashMovement.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


def _apply_movement(
    db: AsyncSession,
    account: CashAccount,
    amount: Decimal,
    movement_type: CashMovementType,
    *,
    related_transaction_id: Optional[UUID] = None,
    notes: Optional[str] = None,
) -> CashMovement:
    """Mutate balance and queue an audit row. Caller commits."""
    account.balance = (account.balance or ZERO) + amount
    movement = CashMovement(
        cash_account_id=account.id,
        movement_type=movement_type,
        amount=amount,
        currency=account.currency,
        related_transaction_id=related_transaction_id,
        notes=notes,
    )
    db.add(movement)
    return movement


async def create_default_accounts(db: AsyncSession, user_id: UUID) -> None:
    """Create TRY/USD/EUR accounts with zero balance if missing. Idempotent."""
    existing = {a.currency for a in await list_accounts(db, user_id)}
    for currency in DEFAULT_CURRENCIES:
        if currency in existing:
            continue
        db.add(CashAccount(user_id=user_id, currency=currency, balance=ZERO))
    await db.flush()


async def deposit(
    db: AsyncSession,
    user_id: UUID,
    currency: str,
    amount: Decimal,
    notes: Optional[str] = None,
) -> CashAccount:
    account = await get_or_create_account(db, user_id, currency)
    _apply_movement(
        db, account, amount, CashMovementType.DEPOSIT, notes=notes
    )
    await db.commit()
    await db.refresh(account)
    return account


async def withdraw(
    db: AsyncSession,
    user_id: UUID,
    currency: str,
    amount: Decimal,
    notes: Optional[str] = None,
) -> CashAccount:
    account = await get_or_create_account(db, user_id, currency)
    _apply_movement(
        db, account, -amount, CashMovementType.WITHDRAW, notes=notes
    )
    await db.commit()
    await db.refresh(account)
    return account


async def transfer(
    db: AsyncSession,
    user_id: UUID,
    from_currency: str,
    to_currency: str,
    from_amount: Decimal,
    rate: Decimal,
    notes: Optional[str] = None,
) -> tuple[CashAccount, CashAccount]:
    to_amount = from_amount * rate
    from_account = await get_or_create_account(db, user_id, from_currency)
    to_account = await get_or_create_account(db, user_id, to_currency)
    _apply_movement(
        db, from_account, -from_amount, CashMovementType.TRANSFER_OUT, notes=notes
    )
    _apply_movement(
        db, to_account, to_amount, CashMovementType.TRANSFER_IN, notes=notes
    )
    await db.commit()
    await db.refresh(from_account)
    await db.refresh(to_account)
    return from_account, to_account


# ---------------------------------------------------------------------------
# Transaction lifecycle hooks
# ---------------------------------------------------------------------------


def _tx_sign(transaction_type: TransactionType) -> Decimal:
    """BUY removes cash, SELL adds cash."""
    return Decimal("-1") if transaction_type == TransactionType.BUY else Decimal("1")


async def apply_transaction_effect(
    db: AsyncSession, user_id: UUID, tx: Transaction
) -> None:
    """Stage a BUY/SELL cash effect; the calling use-case owns commit/rollback."""
    if not tx.affects_cash:
        return
    sign = _tx_sign(tx.transaction_type)
    amount = sign * tx.total_amount
    account = await get_or_create_account(db, user_id, tx.transaction_currency)
    movement_type = (
        CashMovementType.BUY
        if tx.transaction_type == TransactionType.BUY
        else CashMovementType.SELL
    )
    _apply_movement(
        db, account, amount, movement_type, related_transaction_id=tx.id
    )
    await db.flush()


async def reverse_transaction_effect(
    db: AsyncSession,
    user_id: UUID,
    snapshot: dict,
    *,
    link_to_transaction: bool = True,
) -> None:
    """Stage reversal of a prior cash effect; the caller owns the unit of work.

    snapshot keys: id, transaction_type, total_amount, transaction_currency,
    affects_cash.
    """
    if not snapshot.get("affects_cash"):
        return
    sign = _tx_sign(snapshot["transaction_type"])
    reverse_amount = -sign * snapshot["total_amount"]
    account = await get_or_create_account(
        db, user_id, snapshot["transaction_currency"]
    )
    _apply_movement(
        db,
        account,
        reverse_amount,
        CashMovementType.ADJUSTMENT,
        related_transaction_id=snapshot.get("id") if link_to_transaction else None,
    )
    await db.flush()


def snapshot_tx(tx: Transaction) -> dict:
    return {
        "id": tx.id,
        "transaction_type": tx.transaction_type,
        "total_amount": tx.total_amount,
        "transaction_currency": tx.transaction_currency,
        "affects_cash": tx.affects_cash,
    }
