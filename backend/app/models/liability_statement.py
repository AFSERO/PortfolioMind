import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _enum(enum_type: type[enum.Enum], name: str, length: int) -> SAEnum:
    return SAEnum(
        enum_type,
        values_callable=lambda values: [item.value for item in values],
        native_enum=False,
        create_constraint=True,
        name=name,
        length=length,
    )


class StatementStatus(str, enum.Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    OVERDUE = "overdue"


class StatementSource(str, enum.Enum):
    MANUAL = "manual"
    PDF_IMPORT = "pdf_import"
    CSV_IMPORT = "csv_import"


class StatementTransactionType(str, enum.Enum):
    PURCHASE = "purchase"
    PAYMENT = "payment"
    REFUND = "refund"
    FEE = "fee"
    INTEREST = "interest"
    CASH_ADVANCE = "cash_advance"
    INSTALLMENT = "installment"
    OTHER = "other"


class InstallmentPlanStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class LiabilityStatement(Base):
    """A single billing period for a user-owned credit-card liability."""

    __tablename__ = "liability_statements"
    __table_args__ = (
        CheckConstraint(
            "statement_period_start <= statement_period_end",
            name="ck_statement_period_order",
        ),
        CheckConstraint("due_date >= statement_date", name="ck_statement_due_date"),
        CheckConstraint("previous_balance >= 0", name="ck_statement_previous_balance"),
        CheckConstraint("payments_total >= 0", name="ck_statement_payments_total"),
        CheckConstraint("purchases_total >= 0", name="ck_statement_purchases_total"),
        CheckConstraint("fees_total >= 0", name="ck_statement_fees_total"),
        CheckConstraint("interest_total >= 0", name="ck_statement_interest_total"),
        CheckConstraint("refunds_total >= 0", name="ck_statement_refunds_total"),
        CheckConstraint("statement_balance >= 0", name="ck_statement_balance"),
        CheckConstraint("minimum_payment >= 0", name="ck_statement_minimum_payment"),
        CheckConstraint(
            "remaining_installments_total >= 0",
            name="ck_statement_remaining_installments",
        ),
        CheckConstraint(
            "applied_balance IS NULL OR applied_balance >= 0",
            name="ck_statement_applied_balance",
        ),
        UniqueConstraint(
            "liability_id",
            "statement_period_start",
            "statement_period_end",
            name="uq_liability_statement_period",
        ),
        UniqueConstraint(
            "liability_id", "statement_date", name="uq_liability_statement_date"
        ),
        UniqueConstraint(
            "user_id", "source_file_hash", name="uq_statement_source_file"
        ),
        Index("ix_statements_user_status", "user_id", "status"),
        Index("ix_statements_liability_date", "liability_id", "statement_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    liability_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("liabilities.id", ondelete="CASCADE"), nullable=False
    )
    statement_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    statement_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    statement_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    previous_balance: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    payments_total: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    purchases_total: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    fees_total: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    interest_total: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    refunds_total: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    statement_balance: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    minimum_payment: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    remaining_installments_total: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0")
    )
    status: Mapped[StatementStatus] = mapped_column(
        _enum(StatementStatus, "statement_status_enum", 20), nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[StatementSource] = mapped_column(
        _enum(StatementSource, "statement_source_enum", 16), nullable=False
    )
    source_file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    applied_to_liability_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    applied_balance: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 6), nullable=True
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


class InstallmentPlan(Base):
    """The complete purchase and schedule behind monthly statement installments."""

    __tablename__ = "installment_plans"
    __table_args__ = (
        CheckConstraint("original_amount > 0", name="ck_installment_original_amount"),
        CheckConstraint("installment_count >= 2", name="ck_installment_count"),
        CheckConstraint(
            "monthly_installment_amount > 0", name="ck_installment_monthly_amount"
        ),
        CheckConstraint(
            "completed_installment_count >= 0",
            name="ck_installment_completed_nonnegative",
        ),
        CheckConstraint(
            "completed_installment_count <= installment_count",
            name="ck_installment_completed_limit",
        ),
        UniqueConstraint(
            "user_id",
            "liability_id",
            "external_reference",
            name="uq_installment_external_ref",
        ),
        Index("ix_installments_user_status", "user_id", "status"),
        Index("ix_installments_liability_status", "liability_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    liability_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("liabilities.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    merchant_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    original_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    installment_count: Mapped[int] = mapped_column(Integer, nullable=False)
    monthly_installment_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False
    )
    first_installment_date: Mapped[date] = mapped_column(Date, nullable=False)
    completed_installment_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    status: Mapped[InstallmentPlanStatus] = mapped_column(
        _enum(InstallmentPlanStatus, "installment_plan_status_enum", 16),
        nullable=False,
    )
    external_reference: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
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


class StatementTransaction(Base):
    """A single line item appearing on one liability statement."""

    __tablename__ = "statement_transactions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_statement_tx_amount"),
        CheckConstraint(
            "(transaction_type = 'installment' AND installment_number IS NOT NULL "
            "AND installment_count IS NOT NULL AND installment_number >= 1 "
            "AND installment_count >= installment_number) OR "
            "(transaction_type <> 'installment' AND installment_plan_id IS NULL "
            "AND installment_number IS NULL AND installment_count IS NULL)",
            name="ck_statement_tx_installment_fields",
        ),
        UniqueConstraint(
            "user_id",
            "statement_id",
            "source_line_hash",
            name="uq_statement_tx_source_line",
        ),
        Index("ix_statement_tx_statement_date", "statement_id", "transaction_date"),
        Index("ix_statement_tx_user_date", "user_id", "transaction_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    statement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("liability_statements.id", ondelete="CASCADE"), nullable=False
    )
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    posting_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    merchant_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    transaction_type: Mapped[StatementTransactionType] = mapped_column(
        _enum(StatementTransactionType, "statement_transaction_type_enum", 16),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    installment_plan_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("installment_plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    installment_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    installment_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    external_reference: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    source_line_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
