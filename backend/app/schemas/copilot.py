"""Pydantic schemas and contracts for PortfolioMind Copilot."""

from datetime import datetime
import enum
from typing import Any, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class IntentType(str, enum.Enum):
    """Canonical intent taxonomy for PortfolioMind Copilot."""

    GENERAL_QUESTION = "GENERAL_QUESTION"
    PORTFOLIO_ANALYSIS = "PORTFOLIO_ANALYSIS"
    ASSET_ANALYSIS = "ASSET_ANALYSIS"
    RESEARCH_REQUEST = "RESEARCH_REQUEST"
    POLICY_DISCUSSION = "POLICY_DISCUSSION"
    POLICY_CHANGE = "POLICY_CHANGE"
    PORTFOLIO_CHANGE = "PORTFOLIO_CHANGE"
    TRANSACTION_ENTRY = "TRANSACTION_ENTRY"
    WATCHLIST_UPDATE = "WATCHLIST_UPDATE"
    JOURNAL_ENTRY = "JOURNAL_ENTRY"
    PORTFOLIO_IMPORT = "PORTFOLIO_IMPORT"
    PORTFOLIO_IMPORT_UPDATE = "PORTFOLIO_IMPORT_UPDATE"
    IMPORT_REQUEST = "IMPORT_REQUEST"
    FINANCIAL_ANALYSIS = "FINANCIAL_ANALYSIS"
    GOAL_PROGRESS = "GOAL_PROGRESS"
    UPDATE_FINANCIAL_CONTEXT = "UPDATE_FINANCIAL_CONTEXT"
    CREATE_GOAL = "CREATE_GOAL"
    UPDATE_GOAL = "UPDATE_GOAL"
    CREATE_MANDATE = "CREATE_MANDATE"
    UPDATE_MANDATE = "UPDATE_MANDATE"
    ASSIGN_CAPITAL = "ASSIGN_CAPITAL"
    TRANSFER_CAPITAL = "TRANSFER_CAPITAL"
    FINANCIAL_DISCOVERY = "FINANCIAL_DISCOVERY"
    UNKNOWN = "UNKNOWN"


class ActionProposalStatus(str, enum.Enum):
    """Lifecycle states for Copilot action proposals."""

    DRAFT = "DRAFT"
    NEEDS_INPUT = "NEEDS_INPUT"
    READY_FOR_CONFIRMATION = "READY_FOR_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    APPLIED = "APPLIED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


class ProposalPermissionLevel(str, enum.Enum):
    """Write permission classification."""

    LEVEL_1_LOW_RISK = "LEVEL_1_LOW_RISK"
    LEVEL_2_CONFIRMATION_REQUIRED = "LEVEL_2_CONFIRMATION_REQUIRED"
    LEVEL_3_HIGH_RISK = "LEVEL_3_HIGH_RISK"
    LEVEL_3_STRONG_CONFIRMATION = "LEVEL_3_STRONG_CONFIRMATION"


class ActionType(str, enum.Enum):
    """Supported narrow write operations for Copilot Phase 2, 3 & 4.1."""

    BUY_TRANSACTION = "BUY_TRANSACTION"
    SELL_TRANSACTION = "SELL_TRANSACTION"
    RECEIVE_ASSET = "RECEIVE_ASSET"
    ADD_WATCHLIST = "ADD_WATCHLIST"
    REMOVE_WATCHLIST = "REMOVE_WATCHLIST"
    CREATE_JOURNAL_ENTRY = "CREATE_JOURNAL_ENTRY"
    PORTFOLIO_IMPORT = "PORTFOLIO_IMPORT"
    UPDATE_INVESTOR_PROFILE = "UPDATE_INVESTOR_PROFILE"
    UPDATE_FINANCIAL_CONTEXT = "UPDATE_FINANCIAL_CONTEXT"
    CREATE_FINANCIAL_GOAL = "CREATE_FINANCIAL_GOAL"
    UPDATE_FINANCIAL_GOAL = "UPDATE_FINANCIAL_GOAL"
    CREATE_MANDATE = "CREATE_MANDATE"
    UPDATE_MANDATE = "UPDATE_MANDATE"
    ASSIGN_CAPITAL = "ASSIGN_CAPITAL"
    TRANSFER_CAPITAL = "TRANSFER_CAPITAL"


class ExecutionMode(str, enum.Enum):
    """Execution authority classification."""

    READ_ONLY = "READ_ONLY"
    AUTO_APPLY = "AUTO_APPLY"
    PROPOSE = "PROPOSE"
    NEEDS_INPUT = "NEEDS_INPUT"


class ContextGroup(str, enum.Enum):
    """Categorical source groupings for Copilot context."""

    USER_PROFILE = "USER_PROFILE"
    INVESTMENT_POLICY = "INVESTMENT_POLICY"
    PORTFOLIO_SUMMARY = "PORTFOLIO_SUMMARY"
    PORTFOLIO_HOLDINGS = "PORTFOLIO_HOLDINGS"
    ASSET = "ASSET"
    EXISTING_HOLDING = "EXISTING_HOLDING"
    PRICE_CONTEXT = "PRICE_CONTEXT"
    INSTRUMENT = "INSTRUMENT"
    INTELLIGENCE_STATE = "INTELLIGENCE_STATE"
    FINANCIAL_CONTEXT = "FINANCIAL_CONTEXT"
    FINANCIAL_GOALS = "FINANCIAL_GOALS"
    MANDATES = "MANDATES"
    FINANCIAL_INTELLIGENCE = "FINANCIAL_INTELLIGENCE"
    RESEARCH_HISTORY = "RESEARCH_HISTORY"
    WATCHLIST = "WATCHLIST"
    DISCOVERY_PROVENANCE = "DISCOVERY_PROVENANCE"
    DECISION_HISTORY = "DECISION_HISTORY"
    BRIEFING = "BRIEFING"
    RECENT_CONVERSATION = "RECENT_CONVERSATION"


class SemanticFinancialMeaning(str, enum.Enum):
    """Explicit financial semantic meaning to prevent unit price vs total value conflation."""

    TOTAL_MARKET_VALUE = "TOTAL_MARKET_VALUE"
    CURRENT_UNIT_PRICE = "CURRENT_UNIT_PRICE"
    AVERAGE_COST = "AVERAGE_COST"
    DERIVED_FROM_MARKET_VALUE = "DERIVED_FROM_MARKET_VALUE"
    TRANSACTION_PRICE = "TRANSACTION_PRICE"
    CASH_OUTFLOW = "CASH_OUTFLOW"


class SemanticFinancialValue(BaseModel):
    """Enforces semantic disambiguation, unit provenance, and currency tagging."""

    value: Any
    currency: str
    meaning: SemanticFinancialMeaning
    source: str
    freshness: Optional[str] = "CURRENT"
    formatted: Optional[str] = None
    notes: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)


class AcquisitionType(str, enum.Enum):
    """Financial acquisition semantics distinguishing cash purchases from gifts/transfers."""

    PURCHASE = "PURCHASE"
    SALE = "SALE"
    GIFT_IN = "GIFT_IN"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    OPENING_BALANCE = "OPENING_BALANCE"


class PendingActionDraft(BaseModel):
    """Multi-turn action draft state preserved across conversation turns."""

    draft_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_type: str  # e.g. "ADD_TRANSACTION", "RECEIVE_ASSET"
    acquisition_type: str = AcquisitionType.PURCHASE.value
    symbol: Optional[str] = None
    instrument_name: Optional[str] = None
    asset_id: Optional[str] = None
    instrument_id: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    currency: Optional[str] = None
    total_amount: Optional[float] = None
    affects_cash: bool = True
    cash_outflow: float = 0.0
    transaction_date: Optional[str] = None  # YYYY-MM-DD
    notes: Optional[str] = None
    is_complete: bool = False
    missing_fields: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore", use_enum_values=True)


class IntentResult(BaseModel):
    """Structured result returned by Intent Detection."""

    intent: IntentType
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    entities: dict[str, Any] = Field(default_factory=dict)
    requires_context: List[str] = Field(default_factory=list)
    execution_mode: ExecutionMode
    missing_information: List[str] = Field(default_factory=list)
    reason: str

    model_config = ConfigDict(use_enum_values=True)


class ContextProvenanceItem(BaseModel):
    """Provenance tracking for an individual piece of context delivered to Codex."""

    source_type: str
    source_id: Optional[str] = None
    title: str
    updated_at: Optional[str] = None
    freshness: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class CopilotPageContext(BaseModel):
    """Optional UI location context hook."""

    page_type: Optional[str] = None  # e.g. "DASHBOARD", "ASSET_DETAIL", "RESEARCH", "WATCHLIST"
    instrument_id: Optional[uuid.UUID] = None
    asset_id: Optional[uuid.UUID] = None


class CopilotConversationCreateRequest(BaseModel):
    """Payload to create a new Copilot conversation."""

    title: Optional[str] = None


class CopilotMessageCreateRequest(BaseModel):
    """Payload to send a message to Copilot."""

    content: str = Field(min_length=1)
    page_context: Optional[CopilotPageContext] = None


class CopilotMessageResponse(BaseModel):
    """Message presentation schema."""

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    raw_content: str
    intent: Optional[str] = None
    structured_metadata: Optional[dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CopilotConversationResponse(BaseModel):
    """Conversation summary presentation schema."""

    id: uuid.UUID
    user_id: uuid.UUID
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    messages: Optional[List[CopilotMessageResponse]] = None

    model_config = ConfigDict(from_attributes=True)


class CopilotResponseType(str, enum.Enum):
    """Standardized response kinds for Copilot execution."""

    ANSWER = "ANSWER"
    NEEDS_INPUT = "NEEDS_INPUT"
    ACTION_INTENT = "ACTION_INTENT"
    PROPOSAL = "PROPOSAL"


class ActionProposalResponse(BaseModel):
    """Schema for presenting an action proposal to the user or API client."""

    id: uuid.UUID
    user_id: uuid.UUID
    conversation_id: Optional[uuid.UUID] = None
    action_type: str
    permission_level: str
    status: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    expected_impact: Optional[dict[str, Any]] = None
    current_state_snapshot: Optional[dict[str, Any]] = None
    human_readable_summary: str
    warnings: List[str] = Field(default_factory=list)
    idempotency_key: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None
    execution_result: Optional[dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class ActionProposalConfirmRequest(BaseModel):
    confirmation_text: Optional[str] = None
    """Payload to confirm and execute a staged action proposal."""

    idempotency_key: Optional[str] = None


class ActionProposalCancelRequest(BaseModel):
    """Payload to explicitly cancel an action proposal."""

    reason: Optional[str] = None


class CopilotStructuredResponse(BaseModel):
    """Contract for Copilot assistant response envelopes."""

    response_type: CopilotResponseType
    answer: Optional[str] = None
    question: Optional[str] = None
    intent: str
    execution_mode: Optional[str] = None
    missing_fields: Optional[List[str]] = None
    action: Optional[dict[str, Any]] = None
    action_draft: Optional[PendingActionDraft] = None
    proposal: Optional[ActionProposalResponse] = None
    import_batch: Optional[Any] = None  # PortfolioImportBatchResponse
    financial_values: Optional[List[SemanticFinancialValue]] = None
    context_used: List[ContextProvenanceItem] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore", use_enum_values=True)


