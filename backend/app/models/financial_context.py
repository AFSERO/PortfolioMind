import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FinancialScope(str, enum.Enum):
    INDIVIDUAL = "INDIVIDUAL"
    PERSONAL_SHARE_OF_HOUSEHOLD = "PERSONAL_SHARE_OF_HOUSEHOLD"


class IncomeStability(str, enum.Enum):
    PREDICTABLE = "PREDICTABLE"
    VARIABLE = "VARIABLE"
    AT_RISK = "AT_RISK"
    TEMPORARY = "TEMPORARY"
    UNKNOWN = "UNKNOWN"


class GoalType(str, enum.Enum):
    RETIREMENT = "RETIREMENT"
    HOME_PURCHASE = "HOME_PURCHASE"
    EDUCATION = "EDUCATION"
    EMERGENCY_RESERVE = "EMERGENCY_RESERVE"
    WEALTH_GROWTH = "WEALTH_GROWTH"
    FINANCIAL_INDEPENDENCE = "FINANCIAL_INDEPENDENCE"
    CAPITAL_PRESERVATION = "CAPITAL_PRESERVATION"
    INCOME_GENERATION = "INCOME_GENERATION"
    BUSINESS_CAPITAL = "BUSINESS_CAPITAL"
    TRAVEL = "TRAVEL"
    OTHER = "OTHER"


class GoalMode(str, enum.Enum):
    TARGET_AMOUNT = "TARGET_AMOUNT"
    TARGET_INCOME = "TARGET_INCOME"
    OPEN_ENDED = "OPEN_ENDED"


class GoalPriority(str, enum.Enum):
    ESSENTIAL = "ESSENTIAL"
    IMPORTANT = "IMPORTANT"
    ASPIRATIONAL = "ASPIRATIONAL"


class Flexibility(str, enum.Enum):
    FIXED = "FIXED"
    LIMITED = "LIMITED"
    FLEXIBLE = "FLEXIBLE"
    UNKNOWN = "UNKNOWN"


class GoalStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ACHIEVED = "ACHIEVED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"


class MandateType(str, enum.Enum):
    RESERVE = "RESERVE"
    PRESERVATION = "PRESERVATION"
    INCOME = "INCOME"
    GROWTH = "GROWTH"
    SPECULATIVE = "SPECULATIVE"
    CUSTOM = "CUSTOM"


class RiskCapacity(str, enum.Enum):
    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class MandateStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CLOSED = "CLOSED"


class ResourceAssignmentType(str, enum.Enum):
    ASSET = "ASSET"
    CASH_ACCOUNT = "CASH_ACCOUNT"


class FinancialContext(Base):
    """User-level financial context, declared flows, and circumstances.
    Does NOT store real balances (those reside in Asset, CashAccount, Liability).
    """

    __tablename__ = "financial_contexts"
    __table_args__ = (
        Index("ix_financial_contexts_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    financial_scope: Mapped[FinancialScope] = mapped_column(
        SAEnum(FinancialScope, name="financialscope", native_enum=False),
        default=FinancialScope.INDIVIDUAL,
        nullable=False,
    )
    planning_currency: Mapped[str] = mapped_column(String(3), default="TRY", nullable=False)
    spending_currencies: Mapped[List[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=lambda: ["TRY"], nullable=False
    )
    monthly_net_income: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 6), nullable=True
    )
    income_sources: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=list, nullable=False
    )
    income_stability: Mapped[IncomeStability] = mapped_column(
        SAEnum(IncomeStability, name="incomestability", native_enum=False),
        default=IncomeStability.UNKNOWN,
        nullable=False,
    )
    monthly_essential_expenses: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 6), nullable=True
    )
    monthly_discretionary_expenses: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 6), nullable=True
    )
    non_debt_obligations: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=list, nullable=False
    )
    dependents_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    external_support: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    expected_changes: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=list, nullable=False
    )
    coverage_declarations: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    reserve_self_report: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    user_surplus_estimate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 6), nullable=True
    )
    provenance: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    last_confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class FinancialGoal(Base):
    """A financial goal representing the outcome or future need ('Why / When')."""

    __tablename__ = "financial_goals"
    __table_args__ = (
        Index("ix_financial_goals_user_id", "user_id"),
        Index("ix_financial_goals_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    goal_type: Mapped[GoalType] = mapped_column(
        SAEnum(GoalType, name="goaltype", native_enum=False), nullable=False
    )
    mode: Mapped[GoalMode] = mapped_column(
        SAEnum(GoalMode, name="goalmode", native_enum=False), default=GoalMode.TARGET_AMOUNT, nullable=False
    )
    target_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 6), nullable=True
    )
    target_currency: Mapped[str] = mapped_column(String(3), default="TRY", nullable=False)
    target_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    horizon_band: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    priority: Mapped[GoalPriority] = mapped_column(
        SAEnum(GoalPriority, name="goalpriority", native_enum=False),
        default=GoalPriority.IMPORTANT,
        nullable=False,
    )
    date_flexibility: Mapped[Flexibility] = mapped_column(
        SAEnum(Flexibility, name="flexibility", native_enum=False, create_constraint=False),
        default=Flexibility.UNKNOWN,
        nullable=False,
    )
    amount_flexibility: Mapped[Flexibility] = mapped_column(
        SAEnum(Flexibility, name="amount_flexibility_enum", native_enum=False, create_constraint=False),
        default=Flexibility.UNKNOWN,
        nullable=False,
    )
    status: Mapped[GoalStatus] = mapped_column(
        SAEnum(GoalStatus, name="goalstatus", native_enum=False),
        default=GoalStatus.ACTIVE,
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    mandates: Mapped[List["InvestmentMandate"]] = relationship(
        "InvestmentMandate",
        back_populates="goal",
        lazy="selectin",
    )


class InvestmentMandate(Base):
    """An investment mandate representing a scoped investment policy and capital pool ('How')."""

    __tablename__ = "investment_mandates"
    __table_args__ = (
        Index("ix_investment_mandates_user_id", "user_id"),
        Index("ix_investment_mandates_goal_id", "goal_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    goal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("financial_goals.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    mandate_type: Mapped[MandateType] = mapped_column(
        SAEnum(MandateType, name="mandatetype", native_enum=False),
        default=MandateType.GROWTH,
        nullable=False,
    )
    purpose: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    horizon_override: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    risk_capacity: Mapped[Optional[RiskCapacity]] = mapped_column(
        SAEnum(RiskCapacity, name="riskcapacity", native_enum=False),
        nullable=True,
    )
    target_allocation: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    concentration_limits: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    policy_rules: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    status: Mapped[MandateStatus] = mapped_column(
        SAEnum(MandateStatus, name="mandatestatus", native_enum=False),
        default=MandateStatus.ACTIVE,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    goal: Mapped[Optional["FinancialGoal"]] = relationship(
        "FinancialGoal",
        back_populates="mandates",
        lazy="selectin",
    )
    assignments: Mapped[List["CapitalAssignment"]] = relationship(
        "CapitalAssignment",
        back_populates="mandate",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class CapitalAssignment(Base):
    """Virtual earmark layer connecting physical assets/cash accounts to mandates.
    Holds asset units (assigned_quantity) or native cash amount (assigned_amount).
    """

    __tablename__ = "capital_assignments"
    __table_args__ = (
        Index("ix_capital_assignments_mandate_id", "mandate_id"),
        Index("ix_capital_assignments_asset_id", "asset_id"),
        Index("ix_capital_assignments_cash_account_id", "cash_account_id"),
        Index("ix_capital_assignments_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    mandate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("investment_mandates.id", ondelete="CASCADE"), nullable=False
    )
    resource_type: Mapped[ResourceAssignmentType] = mapped_column(
        SAEnum(ResourceAssignmentType, name="resourceassignmenttype", native_enum=False),
        nullable=False,
    )
    asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("assets.id", ondelete="CASCADE"), nullable=True
    )
    cash_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("cash_accounts.id", ondelete="CASCADE"), nullable=True
    )
    assigned_quantity: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), default=Decimal("0"), nullable=False
    )
    assigned_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), default=Decimal("0"), nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    mandate: Mapped["InvestmentMandate"] = relationship(
        "InvestmentMandate",
        back_populates="assignments",
        lazy="selectin",
    )
    asset: Mapped[Optional["Asset"]] = relationship(
        "Asset",
        lazy="selectin",
    )
    cash_account: Mapped[Optional["CashAccount"]] = relationship(
        "CashAccount",
        lazy="selectin",
    )
