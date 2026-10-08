import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.financial_context import (
    FinancialScope,
    Flexibility,
    GoalMode,
    GoalPriority,
    GoalStatus,
    GoalType,
    IncomeStability,
    MandateStatus,
    MandateType,
    ResourceAssignmentType,
    RiskCapacity,
)


# --- Supporting Models ---
class IncomeSource(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    label: Optional[str] = None
    source_type: str = "EMPLOYMENT"  # EMPLOYMENT, FREELANCE, BUSINESS_DRAW, PENSION, BENEFIT, RENT, INVESTMENT_DISTRIBUTION, SUPPORT, OTHER
    amount: Optional[Decimal] = None
    currency: str = "TRY"
    stability: IncomeStability = IncomeStability.UNKNOWN
    availability: str = "AVAILABLE"  # AVAILABLE, RESTRICTED, UNKNOWN


class NonDebtObligation(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    label: Optional[str] = None
    obligation_type: str = "SUPPORT"  # SUPPORT, RENT, TAX, CONTRACTUAL, OTHER
    amount: Optional[Decimal] = None
    currency: str = "TRY"
    is_essential: bool = True


class ExpectedChange(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    change_type: str = "INCOME"  # INCOME, EXPENSE, SUPPORT, MOVE, RETIREMENT, OTHER
    expected_date: Optional[str] = None
    estimated_impact: Optional[Decimal] = None
    notes: Optional[str] = None


# --- Financial Context Schemas ---
class FinancialContextBase(BaseModel):
    financial_scope: FinancialScope = FinancialScope.INDIVIDUAL
    planning_currency: str = "TRY"
    spending_currencies: List[str] = Field(default_factory=lambda: ["TRY"])
    monthly_net_income: Optional[Decimal] = None
    income_sources: List[IncomeSource] = Field(default_factory=list)
    income_stability: IncomeStability = IncomeStability.UNKNOWN
    monthly_essential_expenses: Optional[Decimal] = None
    monthly_discretionary_expenses: Optional[Decimal] = None
    non_debt_obligations: List[NonDebtObligation] = Field(default_factory=list)
    dependents_count: Optional[int] = None
    external_support: Optional[Dict[str, Any]] = None
    expected_changes: List[ExpectedChange] = Field(default_factory=list)
    coverage_declarations: Optional[Dict[str, Any]] = None
    reserve_self_report: Optional[str] = None
    user_surplus_estimate: Optional[Decimal] = None
    provenance: Optional[Dict[str, Any]] = None


class FinancialContextCreate(FinancialContextBase):
    pass


class FinancialContextUpdate(BaseModel):
    financial_scope: Optional[FinancialScope] = None
    planning_currency: Optional[str] = None
    spending_currencies: Optional[List[str]] = None
    monthly_net_income: Optional[Decimal] = None
    income_sources: Optional[List[IncomeSource]] = None
    income_stability: Optional[IncomeStability] = None
    monthly_essential_expenses: Optional[Decimal] = None
    monthly_discretionary_expenses: Optional[Decimal] = None
    non_debt_obligations: Optional[List[NonDebtObligation]] = None
    dependents_count: Optional[int] = None
    external_support: Optional[Dict[str, Any]] = None
    expected_changes: Optional[List[ExpectedChange]] = None
    coverage_declarations: Optional[Dict[str, Any]] = None
    reserve_self_report: Optional[str] = None
    user_surplus_estimate: Optional[Decimal] = None
    provenance: Optional[Dict[str, Any]] = None


class FinancialContextResponse(FinancialContextBase):
    id: uuid.UUID
    user_id: uuid.UUID
    last_confirmed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Capital Assignment Schemas ---
class CapitalAssignmentBase(BaseModel):
    mandate_id: uuid.UUID
    resource_type: ResourceAssignmentType
    asset_id: Optional[uuid.UUID] = None
    cash_account_id: Optional[uuid.UUID] = None
    assigned_quantity: Decimal = Decimal("0")
    assigned_amount: Decimal = Decimal("0")
    notes: Optional[str] = None


class CapitalAssignmentCreate(CapitalAssignmentBase):
    pass


class CapitalAssignmentResponse(CapitalAssignmentBase):
    id: uuid.UUID
    user_id: uuid.UUID
    current_market_value: Optional[Decimal] = None
    resource_symbol: Optional[str] = None
    resource_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CapitalTransferRequest(BaseModel):
    from_mandate_id: uuid.UUID
    to_mandate_id: uuid.UUID
    resource_type: ResourceAssignmentType
    asset_id: Optional[uuid.UUID] = None
    cash_account_id: Optional[uuid.UUID] = None
    quantity: Optional[Decimal] = None
    amount: Optional[Decimal] = None


class ResolveAssignmentReviewRequest(BaseModel):
    asset_id: uuid.UUID
    mandate_adjustments: Dict[str, Decimal]


# --- Investment Mandate Schemas ---
class InvestmentMandateBase(BaseModel):
    name: str
    goal_id: Optional[uuid.UUID] = None
    mandate_type: MandateType = MandateType.GROWTH
    purpose: Optional[str] = None
    horizon_override: Optional[str] = None
    risk_capacity: Optional[RiskCapacity] = None
    target_allocation: Optional[Dict[str, Any]] = None
    concentration_limits: Optional[Dict[str, Any]] = None
    policy_rules: Optional[Dict[str, Any]] = None
    status: MandateStatus = MandateStatus.ACTIVE


class InvestmentMandateCreate(InvestmentMandateBase):
    pass


class InvestmentMandateUpdate(BaseModel):
    name: Optional[str] = None
    goal_id: Optional[uuid.UUID] = None
    mandate_type: Optional[MandateType] = None
    purpose: Optional[str] = None
    horizon_override: Optional[str] = None
    risk_capacity: Optional[RiskCapacity] = None
    target_allocation: Optional[Dict[str, Any]] = None
    concentration_limits: Optional[Dict[str, Any]] = None
    policy_rules: Optional[Dict[str, Any]] = None
    status: Optional[MandateStatus] = None


class MandateSummary(BaseModel):
    id: uuid.UUID
    name: str
    mandate_type: MandateType
    status: MandateStatus
    risk_capacity: Optional[RiskCapacity] = None
    assigned_market_value: Decimal = Decimal("0")

    model_config = ConfigDict(from_attributes=True)


class InvestmentMandateResponse(InvestmentMandateBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    assignments: List[CapitalAssignmentResponse] = Field(default_factory=list)
    total_assigned_value: Decimal = Decimal("0")

    model_config = ConfigDict(from_attributes=True)


# --- Financial Goal Schemas ---
class FinancialGoalBase(BaseModel):
    name: str
    goal_type: GoalType
    mode: GoalMode = GoalMode.TARGET_AMOUNT
    target_amount: Optional[Decimal] = None
    target_currency: str = "TRY"
    target_date: Optional[date] = None
    horizon_band: Optional[str] = None
    priority: GoalPriority = GoalPriority.IMPORTANT
    date_flexibility: Flexibility = Flexibility.UNKNOWN
    amount_flexibility: Flexibility = Flexibility.UNKNOWN
    status: GoalStatus = GoalStatus.ACTIVE
    notes: Optional[str] = None


class FinancialGoalCreate(FinancialGoalBase):
    pass


class FinancialGoalUpdate(BaseModel):
    name: Optional[str] = None
    goal_type: Optional[GoalType] = None
    mode: Optional[GoalMode] = None
    target_amount: Optional[Decimal] = None
    target_currency: Optional[str] = None
    target_date: Optional[date] = None
    horizon_band: Optional[str] = None
    priority: Optional[GoalPriority] = None
    date_flexibility: Optional[Flexibility] = None
    amount_flexibility: Optional[Flexibility] = None
    status: Optional[GoalStatus] = None
    notes: Optional[str] = None


class FinancialGoalResponse(FinancialGoalBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    mandates: List[MandateSummary] = Field(default_factory=list)
    current_funding: Decimal = Decimal("0")
    funded_ratio: Optional[Decimal] = None
    remaining_amount: Optional[Decimal] = None
    months_remaining: Optional[int] = None
    time_remaining_text: Optional[str] = None
    required_monthly_contribution: Optional[Decimal] = None
    projection_assumptions: str = (
        "Assuming 0% nominal return. No investment returns are assumed or projected."
    )
    status_assessment: str = "IN_PROGRESS"  # FUNDED_NOW, ON_TRACK, SENSITIVE, SHORTFALL, NOT_TARGETED, UNASSIGNED

    model_config = ConfigDict(from_attributes=True)


# --- Derived Financial Intelligence Schemas ---
class GoalProgressDetail(BaseModel):
    goal_id: uuid.UUID
    goal_name: str
    goal_type: GoalType
    target_amount: Optional[Decimal] = None
    target_currency: str
    target_date: Optional[date] = None
    current_funding: Decimal
    funded_ratio: Optional[Decimal] = None
    remaining_amount: Optional[Decimal] = None
    months_remaining: Optional[int] = None
    time_remaining_text: Optional[str] = None
    required_monthly_contribution: Optional[Decimal] = None
    projection_assumptions: str = (
        "Assuming 0% nominal return. No investment returns are assumed or projected."
    )
    shortfall: Optional[Decimal] = None
    status_assessment: str
    mandate_count: int


class FinancialIntelligenceSummary(BaseModel):
    reporting_currency: str = "TRY"
    net_worth: Decimal
    liquid_net_worth: Decimal
    total_assets_value: Decimal
    total_cash_value: Decimal
    total_liabilities_value: Decimal
    
    # Flows & Ratios
    monthly_net_income: Optional[Decimal] = None
    monthly_essential_expenses: Optional[Decimal] = None
    monthly_discretionary_expenses: Optional[Decimal] = None
    monthly_surplus: Optional[Decimal] = None
    savings_rate_pct: Optional[Decimal] = None
    emergency_coverage_months: Optional[Decimal] = None
    debt_to_income_pct: Optional[Decimal] = None
    debt_stock_multiple: Optional[Decimal] = None
    
    # Speculation & Policy
    speculative_exposure_value: Decimal = Decimal("0")
    speculative_exposure_pct: Optional[Decimal] = None
    speculative_cap_pct: Optional[Decimal] = None
    speculative_cap_breached: bool = False
    
    # Capital Earmarks
    total_assigned_capital: Decimal = Decimal("0")
    unassigned_assets_value: Decimal = Decimal("0")
    unassigned_cash_value: Decimal = Decimal("0")
    
    # Goals Breakdown
    goals: List[GoalProgressDetail] = Field(default_factory=list)
    
    # Disclosures & Limitations
    coverage_state: Dict[str, str] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)


class FinancialProfileSynthesis(BaseModel):
    generated_at: datetime
    freshness_status: str  # CURRENT, REVIEW_DUE, STALE, UNKNOWN
    is_authoritative: bool = False
    disclaimer: str = (
        "This synthesis is an automated analytical summary for informational and planning assistance only. "
        "It is non-authoritative and does not constitute formal financial advice."
    )
    
    investor_profile_summary: Dict[str, Any]
    cash_flow_and_surplus_summary: Dict[str, Any]
    emergency_reserve_adequacy: Dict[str, Any]
    goal_architecture_summary: Dict[str, Any]
    debt_posture_summary: Dict[str, Any]
    mandate_alignment_summary: Dict[str, Any]
    open_questions_and_gaps: List[str] = Field(default_factory=list)
    source_traceability: Dict[str, Any] = Field(default_factory=dict)
    confidence_limitations: List[str] = Field(default_factory=list)

