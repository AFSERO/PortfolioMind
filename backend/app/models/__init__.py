# SQLAlchemy models — import all models here so Alembic can detect them
from .user import User  # noqa: F401
from .instrument import Instrument  # noqa: F401
from .asset import Asset, AssetType  # noqa: F401
from .price_history import PriceHistory  # noqa: F401
from .portfolio_snapshot import PortfolioSnapshot  # noqa: F401
from .forex_rate import ForexRate  # noqa: F401
from .transaction import Transaction, TransactionType  # noqa: F401
from .cash import CashAccount, CashMovement, CashMovementType  # noqa: F401
from .refresh_session import RefreshSession  # noqa: F401
from .liability import Liability, LiabilityType  # noqa: F401
from .liability_statement import (  # noqa: F401
    InstallmentPlan,
    InstallmentPlanStatus,
    LiabilityStatement,
    StatementSource,
    StatementStatus,
    StatementTransaction,
    StatementTransactionType,
)
from .intelligence import (  # noqa: F401
    InstrumentIntelligenceState,
    IntelligenceReview,
    ProtocolRunStatus,
    Recommendation,
    TechnicalPlan,
    TechnicalStatus,
    ThesisStatus,
    ValuationStatus,
)
from .decision_log import (  # noqa: F401
    DecisionEventType,
    DecisionLogEntry,
)
from .briefing import (  # noqa: F401
    BriefingCategory,
    BriefingImpact,
    BriefingItem,
    BriefingMateriality,
    BriefingRun,
    BriefingThesisImpact,
    BriefingTimeHorizon,
)
from .opportunity import (  # noqa: F401
    OpportunityAssessment,
    OpportunityConfidence,
    OpportunityDriver,
    OpportunityStatus,
    ResearchFreshness,
    ResearchStage,
    SuggestedNextStep,
    ValuationSignal,
    WatchlistItem,
    WatchlistPriority,
)
from .discovery import (  # noqa: F401
    DiscoveryCandidate,
    DiscoveryCandidateState,
    DiscoveryConfidence,
    DiscoveryRun,
    DiscoveryRunStatus,
    DiscoveryStatus,
    DiscoverySuggestedNextStep,
    DiscoveryTriggerType,
    DiscoveryUniverse,
)
from .copilot import (  # noqa: F401
    CopilotActionProposal,
    CopilotAuditLog,
    CopilotConversation,
    CopilotMessage,
)
from .opening_position import OpeningPosition  # noqa: F401
from .portfolio_import import (  # noqa: F401
    PortfolioImportBatch,
    PortfolioImportItem,
)
from .investor_profile import (  # noqa: F401
    InvestorProfile,
    InvestorProfileAssessment,
    InvestorProfileAnswer,
    InvestorProfileVersion,
    InvestorProfileDraft,
)
from .financial_context import (  # noqa: F401
    CapitalAssignment,
    FinancialContext,
    FinancialGoal,
    FinancialScope,
    Flexibility,
    GoalMode,
    GoalPriority,
    GoalStatus,
    GoalType,
    IncomeStability,
    InvestmentMandate,
    MandateStatus,
    MandateType,
    ResourceAssignmentType,
    RiskCapacity,
)




