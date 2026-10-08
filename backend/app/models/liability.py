import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LiabilityType(str, enum.Enum):
    CREDIT_CARD = "credit_card"
    PERSONAL_LOAN = "personal_loan"
    MORTGAGE = "mortgage"
    STUDENT_LOAN = "student_loan"
    OTHER = "other"


class Liability(Base):
    """A manually maintained user-owned debt balance."""

    __tablename__ = "liabilities"
    __table_args__ = (
        CheckConstraint(
            "current_balance >= 0", name="ck_liabilities_current_balance_nonnegative"
        ),
        CheckConstraint(
            "original_balance IS NULL OR original_balance >= 0",
            name="ck_liabilities_original_balance_nonnegative",
        ),
        CheckConstraint(
            "interest_rate IS NULL OR interest_rate >= 0",
            name="ck_liabilities_interest_rate_nonnegative",
        ),
        CheckConstraint(
            "minimum_payment IS NULL OR minimum_payment >= 0",
            name="ck_liabilities_minimum_payment_nonnegative",
        ),
        Index("ix_liabilities_user_active", "user_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    liability_type: Mapped[LiabilityType] = mapped_column(
        SAEnum(
            LiabilityType,
            values_callable=lambda values: [item.value for item in values],
            native_enum=False,
            create_constraint=True,
            name="liability_type_enum",
            length=20,
        ),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    current_balance: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    original_balance: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 6), nullable=True
    )
    interest_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 6), nullable=True
    )
    minimum_payment: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 6), nullable=True
    )
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
