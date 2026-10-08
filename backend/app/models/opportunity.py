"""Watchlist and Opportunity Assessment models for PortfolioMind.

Stores user-specific watchlist candidates, research pipeline stages,
and persisted opportunity assessments.
"""

from datetime import datetime, timezone
from decimal import Decimal
import enum
from typing import Any, Optional, TYPE_CHECKING
import uuid

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.instrument import Instrument
    from app.models.user import User


class ResearchStage(str, enum.Enum):
    DISCOVERED = "DISCOVERED"
    SCREENED = "SCREENED"
    RESEARCHING = "RESEARCHING"
    VALUED = "VALUED"
    READY = "READY"
    WAITING_FOR_PRICE = "WAITING_FOR_PRICE"
    OWNED = "OWNED"
    REJECTED = "REJECTED"


class WatchlistPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class OpportunityStatus(str, enum.Enum):
    NO_CHANGE = "NO_CHANGE"
    WATCH = "WATCH"
    RESEARCH_SOON = "RESEARCH_SOON"
    RESEARCH_NOW = "RESEARCH_NOW"


class OpportunityDriver(str, enum.Enum):
    VALUATION = "VALUATION"
    FUNDAMENTAL = "FUNDAMENTAL"
    CATALYST = "CATALYST"
    PRICE_MOVE = "PRICE_MOVE"
    RESEARCH_STALENESS = "RESEARCH_STALENESS"
    OTHER = "OTHER"


class ValuationSignal(str, enum.Enum):
    ATTRACTIVE = "ATTRACTIVE"
    FAIR = "FAIR"
    EXPENSIVE = "EXPENSIVE"
    UNKNOWN = "UNKNOWN"


class ResearchFreshness(str, enum.Enum):
    FRESH = "FRESH"
    REVIEW = "REVIEW"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class SuggestedNextStep(str, enum.Enum):
    NONE = "NONE"
    SCREENING = "SCREENING"
    DEEP_RESEARCH = "DEEP_RESEARCH"
    VALUATION_UPDATE = "VALUATION_UPDATE"
    THESIS_REVIEW = "THESIS_REVIEW"
    PRICE_REVIEW = "PRICE_REVIEW"


class OpportunityConfidence(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class WatchlistItem(Base):
    """User-specific watchlist candidate tracking."""

    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "instrument_id", name="uq_watchlist_items_user_instrument"
        ),
        Index("ix_watchlist_items_user_id", "user_id"),
        Index("ix_watchlist_items_instrument_id", "instrument_id"),
        Index("ix_watchlist_items_research_stage", "research_stage"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    research_stage: Mapped[ResearchStage] = mapped_column(
        SAEnum(ResearchStage, native_enum=False, length=32),
        default=ResearchStage.DISCOVERED,
        nullable=False,
    )
    priority: Mapped[WatchlistPriority] = mapped_column(
        SAEnum(WatchlistPriority, native_enum=False, length=16),
        default=WatchlistPriority.MEDIUM,
        nullable=False,
    )
    why_interesting: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_entry_min: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 6), nullable=True
    )
    target_entry_max: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 6), nullable=True
    )
    key_catalyst: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    key_risk: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    next_expected_event: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    discovery_candidate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("discovery_candidates.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["User"] = relationship("User")
    instrument: Mapped["Instrument"] = relationship("Instrument", lazy="joined")


class OpportunityAssessment(Base):
    """Persisted opportunity assessment for a candidate instrument."""

    __tablename__ = "opportunity_assessments"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "instrument_id",
            name="uq_opportunity_assessments_user_instrument",
        ),
        Index("ix_opportunity_assessments_user_id", "user_id"),
        Index("ix_opportunity_assessments_instrument_id", "instrument_id"),
        Index("ix_opportunity_assessments_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[OpportunityStatus] = mapped_column(
        SAEnum(OpportunityStatus, native_enum=False, length=32),
        nullable=False,
        default=OpportunityStatus.NO_CHANGE,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    primary_driver: Mapped[OpportunityDriver] = mapped_column(
        SAEnum(OpportunityDriver, native_enum=False, length=32),
        nullable=False,
        default=OpportunityDriver.OTHER,
    )
    valuation_signal: Mapped[ValuationSignal] = mapped_column(
        SAEnum(ValuationSignal, native_enum=False, length=32),
        nullable=False,
        default=ValuationSignal.UNKNOWN,
    )
    research_freshness: Mapped[ResearchFreshness] = mapped_column(
        SAEnum(ResearchFreshness, native_enum=False, length=32),
        nullable=False,
        default=ResearchFreshness.UNKNOWN,
    )
    suggested_next_step: Mapped[SuggestedNextStep] = mapped_column(
        SAEnum(SuggestedNextStep, native_enum=False, length=32),
        nullable=False,
        default=SuggestedNextStep.NONE,
    )
    confidence: Mapped[OpportunityConfidence] = mapped_column(
        SAEnum(OpportunityConfidence, native_enum=False, length=16),
        nullable=False,
        default=OpportunityConfidence.MEDIUM,
    )
    source_references: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    assessment_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["User"] = relationship("User")
    instrument: Mapped["Instrument"] = relationship("Instrument", lazy="joined")
