"""Pydantic schemas and contracts for Investor Profile & Assessment.

Covers:
- Assessment question definitions & options
- Raw user answers & submission
- Structured profile draft with review queues & issues
- Analysis readiness and meaningful completeness
- Confirmed material profile versions
"""

from datetime import datetime
from decimal import Decimal
import enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------
class KnowledgeState(str, enum.Enum):
    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"
    NOT_ASKED = "NOT_ASKED"
    SKIPPED = "SKIPPED"
    DECLINED = "DECLINED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class SourceKind(str, enum.Enum):
    EXPLICIT = "EXPLICIT"
    AI_INTERPRETED = "AI_INTERPRETED"
    CALCULATED = "CALCULATED"


class ConfidenceLevel(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNASSESSED = "UNASSESSED"


class ReviewState(str, enum.Enum):
    DRAFT = "DRAFT"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class ToleranceSummary(str, enum.Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class CapacityStatus(str, enum.Enum):
    CONSTRAINED = "CONSTRAINED"
    CONDITIONAL = "CONDITIONAL"
    LESS_CONSTRAINED = "LESS_CONSTRAINED"
    UNKNOWN = "UNKNOWN"


class LiquiditySummary(str, enum.Enum):
    NONE_PLANNED = "NONE_PLANNED"
    KNOWN_NEEDS = "KNOWN_NEEDS"
    UNQUANTIFIED_NEEDS = "UNQUANTIFIED_NEEDS"
    UNKNOWN = "UNKNOWN"


class ResilienceSummary(str, enum.Enum):
    VULNERABLE = "VULNERABLE"
    BUFFERED = "BUFFERED"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class ReadinessStatus(str, enum.Enum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    LIMITED = "LIMITED"
    UNAVAILABLE = "UNAVAILABLE"


# -----------------------------------------------------------------------------
# Question Catalog Schemas
# -----------------------------------------------------------------------------
class QuestionOption(BaseModel):
    code: str
    label: str
    description: Optional[str] = None
    exclusive: bool = False


class QuestionDefinition(BaseModel):
    id: str  # e.g. "C01", "C02"
    section: str  # e.g. "goals_context", "resilience", "risk", "preferences", "policy"
    layer: str  # "core", "conditional", "extended", "advanced"
    priority: str  # "essential", "recommended", "optional"
    text: str
    helper_text: Optional[str] = None
    question_type: str  # "single_choice", "multi_choice", "composite", "numeric"
    options: List[QuestionOption] = Field(default_factory=list)
    has_other: bool = False
    dependencies: List[str] = Field(default_factory=list)
    affects_dimensions: List[str] = Field(default_factory=list)


class SectionDefinition(BaseModel):
    id: str
    title: str
    description: str
    question_ids: List[str]


# -----------------------------------------------------------------------------
# Assessment Submission & Answers
# -----------------------------------------------------------------------------
class AnswerSubmitRequest(BaseModel):
    question_id: str
    item_id: Optional[str] = None
    knowledge_state: KnowledgeState = KnowledgeState.KNOWN
    selected_options: List[str] = Field(default_factory=list)
    numeric_inputs: Dict[str, Any] = Field(default_factory=dict)
    raw_text: Optional[str] = None
    locale: str = "en"


class AnswerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question_id: str
    item_id: Optional[str] = None
    knowledge_state: str
    selected_options: List[Any]
    numeric_inputs: Dict[str, Any]
    raw_text: Optional[str] = None
    locale: str
    answered_at: datetime


class AssessmentStateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    status: str
    questionnaire_version: str
    resume_question_id: Optional[str] = None
    answers: List[AnswerResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# -----------------------------------------------------------------------------
# Issue & Readiness Schemas
# -----------------------------------------------------------------------------
class ProfileIssue(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    rule_id: str  # e.g. "X01", "X02", "X04"
    field_paths: List[str]
    severity: str = "CONFLICT"  # "VALIDATION", "CONFLICT", "CLARIFY", "LIMITATION"
    state: str = "OPEN"  # "OPEN", "ACKNOWLEDGED", "RESOLVED"
    explanation: str


class ProfileCompleteness(BaseModel):
    overall_pct: float
    domains: Dict[str, float] = Field(default_factory=dict)
    missing_field_paths: List[str] = Field(default_factory=list)


class CapabilityReadiness(BaseModel):
    risk_analysis: ReadinessStatus = ReadinessStatus.UNAVAILABLE
    capacity_analysis: ReadinessStatus = ReadinessStatus.UNAVAILABLE
    target_allocation_analysis: ReadinessStatus = ReadinessStatus.UNAVAILABLE
    portfolio_fit: ReadinessStatus = ReadinessStatus.UNAVAILABLE
    liquidity_analysis: ReadinessStatus = ReadinessStatus.UNAVAILABLE
    copilot_support: ReadinessStatus = ReadinessStatus.LIMITED
    research_relevance: ReadinessStatus = ReadinessStatus.UNAVAILABLE


# -----------------------------------------------------------------------------
# Structured Profile Entities
# -----------------------------------------------------------------------------
class GoalItem(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    kind: str  # C01 code e.g. GROW, RETIREMENT, PURCHASE
    horizon: Optional[str] = None  # C02 code e.g. LT_1Y, Y1_3, GE_10Y
    target_date: Optional[str] = None
    flexibility: Optional[str] = None  # FIXED, SOME, FLEXIBLE
    priority: Optional[str] = None  # ESSENTIAL, IMPORTANT, ASPIRATIONAL
    target_size: Optional[Dict[str, Any]] = None
    loss_consequence: Optional[str] = None  # ESSENTIALS, GOAL_UNAFFORDABLE, ADJUST_GOAL, LITTLE_EFFECT
    expectation: Optional[Dict[str, Any]] = None


class WithdrawalNeed(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    goal_id: Optional[str] = None
    timing_band: Optional[str] = None  # NOW, LT_12M, M12_36, GE_36M
    date: Optional[str] = None
    size: Optional[Dict[str, Any]] = None
    recurrence: Optional[str] = None  # ONCE, MONTHLY, QUARTERLY, YEARLY
    end_date: Optional[str] = None
    coverage: Optional[str] = None  # INVESTMENTS, OUTSIDE, PARTIAL, UNKNOWN
    uncovered_size: Optional[Dict[str, Any]] = None


class GoalsAndContext(BaseModel):
    items: List[GoalItem] = Field(default_factory=list)
    withdrawals: List[WithdrawalNeed] = Field(default_factory=list)
    withdrawal_pattern: Optional[str] = None
    reserve_months_band: Optional[str] = None
    cashflow: Optional[str] = None
    income_reliability: Optional[str] = None
    obligation_pressure: Optional[str] = None
    expected_changes: List[Dict[str, Any]] = Field(default_factory=list)
    spending_currencies: List[str] = Field(default_factory=list)
    jurisdiction_mode: Optional[str] = None
    jurisdictions: List[str] = Field(default_factory=list)
    jurisdiction_note: Optional[str] = None


class CapacityByGoal(BaseModel):
    goal_id: str
    status: CapacityStatus
    reason_codes: List[str] = Field(default_factory=list)
    affected_size: Optional[Dict[str, Any]] = None


class RiskProfile(BaseModel):
    drawdown_comfort: Optional[str] = None
    custom_drawdown_pct: Optional[float] = None
    stress_response: Optional[str] = None
    observed_response: Optional[str] = None
    tolerance_summary: ToleranceSummary = ToleranceSummary.UNKNOWN
    capacity_by_goal: List[CapacityByGoal] = Field(default_factory=list)
    liquidity_summary: LiquiditySummary = LiquiditySummary.UNKNOWN
    resilience_summary: ResilienceSummary = ResilienceSummary.UNKNOWN
    horizon_by_goal: Dict[str, Any] = Field(default_factory=dict)


class InvestmentPolicy(BaseModel):
    restriction_topics: List[str] = Field(default_factory=list)
    constraints: List[Dict[str, Any]] = Field(default_factory=list)
    allocation_mode: Optional[str] = None
    allocations: List[Dict[str, Any]] = Field(default_factory=list)
    concentration_limits: List[Dict[str, Any]] = Field(default_factory=list)
    leverage_stance: Optional[str] = None
    leverage_uses: List[str] = Field(default_factory=list)
    gross_exposure_limit_pct: Optional[float] = None
    rebalance_triggers: List[str] = Field(default_factory=list)
    rebalance_interval: Optional[str] = None
    rebalance_drift_pp: Optional[float] = None
    liquidity_floor: Optional[Dict[str, Any]] = None
    implementation_priorities: List[str] = Field(default_factory=list)
    implementation_note: Optional[str] = None
    review_cadence: Optional[str] = None
    review_events: List[str] = Field(default_factory=list)
    success_measures: List[str] = Field(default_factory=list)
    benchmark_reference: Optional[str] = None
    benchmark_currency: Optional[str] = None


class InvestorPreferences(BaseModel):
    experience: List[Dict[str, Any]] = Field(default_factory=list)
    involvement: Optional[str] = None
    styles: List[str] = Field(default_factory=list)
    attention: Optional[str] = None
    asset_interests: List[str] = Field(default_factory=list)
    market_mode: Optional[str] = None
    markets: List[str] = Field(default_factory=list)
    research_priorities: List[str] = Field(default_factory=list)
    monitor_topics: List[str] = Field(default_factory=list)
    custom_alerts: List[Dict[str, Any]] = Field(default_factory=list)
    alert_cadence: Optional[str] = None
    alert_channels: List[str] = Field(default_factory=list)
    quiet_hours: Optional[Dict[str, Any]] = None
    explanation_depth: Optional[str] = None
    language: Optional[str] = None
    copilot_stance: Optional[str] = None


# -----------------------------------------------------------------------------
# Draft & Confirmed Profile Schemas
# -----------------------------------------------------------------------------
class InvestorProfileDraftResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    assessment_id: Optional[uuid.UUID] = None
    base_version_id: Optional[uuid.UUID] = None
    goals: GoalsAndContext
    risk: RiskProfile
    policy: InvestmentPolicy
    preferences: InvestorPreferences
    issues: List[ProfileIssue] = Field(default_factory=list)
    completeness: ProfileCompleteness
    readiness: CapabilityReadiness
    created_at: datetime
    updated_at: datetime


class ProfileConfirmRequest(BaseModel):
    draft_id: Optional[uuid.UUID] = None
    change_reason: Optional[str] = "Profile confirmed by user"
    change_source: Optional[str] = "ONBOARDING"


class InvestorProfileResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    version_number: Optional[int] = None
    active_version_id: Optional[uuid.UUID] = None
    completeness_overall_pct: float
    analysis_readiness: Dict[str, Any]
    goals: Dict[str, Any]
    risk: Dict[str, Any]
    policy: Dict[str, Any]
    preferences: Dict[str, Any]
    issues: List[Dict[str, Any]] = Field(default_factory=list)
    confirmed_at: Optional[datetime] = None
    updated_at: datetime


class InvestorProfileVersionSummary(BaseModel):
    id: uuid.UUID
    version_number: int
    change_reason: str
    change_source: str
    confirmed_at: datetime
