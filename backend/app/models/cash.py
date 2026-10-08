import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CashMovementType(str, enum.Enum):
    DEPOSIT = "DEPOSIT"
    WITHDRAW = "WITHDRAW"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    BUY = "BUY"
    SELL = "SELL"
    ADJUSTMENT = "ADJUSTMENT"


class CashAccount(Base):
    __tablename__ = "cash_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "currency", name="uq_cash_accounts_user_currency"),
        Index("ix_cash_accounts_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CashMovement(Base):
    __tablename__ = "cash_movements"
    __table_args__ = (
        Index("ix_cash_movements_cash_account_id", "cash_account_id"),
        Index(
            "ix_cash_movements_related_transaction_id", "related_transaction_id"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cash_account_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("cash_accounts.id", ondelete="CASCADE"), nullable=False
    )
    movement_type: Mapped[CashMovementType] = mapped_column(
        SAEnum(CashMovementType, native_enum=False, length=20), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    related_transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
