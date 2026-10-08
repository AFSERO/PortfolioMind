"""Investment Intelligence models for PortfolioMind.

Stores the canonical, latest AI-generated investment state, protocol review audit history,
and technical plans linked to Instrument.
"""

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
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

if TYPE_CHECKING:
    from app.models.instrument import Instrument


# ============================================================================
# Enums matching the Finance System
# ============================================================================


class ThesisStatus(str, enum.Enum):
    STRONGER = "STRONGER"
    UNCHANGED = "UNCHANGED"
    WEAKER = "WEAKER"
    INVALIDATED = "INVALIDATED"


class ValuationStatus(str, enum.Enum):
    ATTRACTIVE = "ATTRACTIVE"
    FAIR = "FAIR"
    EXPENSIVE = "EXPENSIVE"
    UNKNOWN = "UNKNOWN"
    N_A = "N_A"


class TechnicalStatus(str, enum.Enum):
    ON_TRACK = "ON_TRACK"
    PULLBACK = "PULLBACK"
    EXTENDED = "EXTENDED"
    BREAKDOWN = "BREAKDOWN"
    NEUTRAL = "NEUTRAL"
    DEVIATED = "DEVIATED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNKNOWN = "UNKNOWN"
    N_A = "N_A"


class Recommendation(str, enum.Enum):
    ADD = "ADD"
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    SELL = "SELL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ExecutionStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    RESTRICTED = "RESTRICTED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class FundQuality(str, enum.Enum):
    STRONG = "STRONG"
    ACCEPTABLE = "ACCEPTABLE"
    WEAK = "WEAK"
    POOR = "POOR"
    UNKNOWN = "UNKNOWN"


class ProtocolRunStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ============================================================================
# Models
# ============================================================================


class InstrumentIntelligenceState(Base):
    """Latest aggregated investment intelligence state for an Instrument.

    Represents the current investment thesis status, valuation status,
    technical status, recommendation, and brief for fast dashboard/detail consumption.
    """

    __tablename__ = "instrument_intelligence_states"
    __table_args__ = (
        Index("ix_intelligence_states_instrument_id", "instrument_id", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    thesis_status: Mapped[Optional[ThesisStatus]] = mapped_column(
        SAEnum(ThesisStatus, native_enum=False, length=20), nullable=True
    )
    valuation_status: Mapped[Optional[ValuationStatus]] = mapped_column(
        SAEnum(ValuationStatus, native_enum=False, length=20), nullable=True
    )
    technical_status: Mapped[Optional[TechnicalStatus]] = mapped_column(
        SAEnum(TechnicalStatus, native_enum=False, length=20), nullable=True
    )
    recommendation: Mapped[Optional[Recommendation]] = mapped_column(
        SAEnum(Recommendation, native_enum=False, length=20), nullable=True
    )

    last_review_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_monitoring_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_review_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    human_brief: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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

    instrument: Mapped["Instrument"] = relationship(
        "Instrument", back_populates="intelligence_state"
    )


class IntelligenceReview(Base):
    """Historical audit trail of AI protocol execution runs and reviews for an Instrument."""

    __tablename__ = "intelligence_reviews"
    __table_args__ = (
        Index("ix_intelligence_reviews_instrument_id", "instrument_id"),
        Index("ix_intelligence_reviews_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    protocol: Mapped[str] = mapped_column(String(128), nullable=False)
    run_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[ProtocolRunStatus] = mapped_column(
        SAEnum(ProtocolRunStatus, native_enum=False, length=20),
        nullable=False,
        default=ProtocolRunStatus.COMPLETED,
    )
    machine_record: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    human_brief: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    research_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_run_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    instrument: Mapped["Instrument"] = relationship(
        "Instrument", back_populates="reviews"
    )


class TechnicalPlan(Base):
    """Technical trading/investing plan for an Instrument."""

    __tablename__ = "technical_plans"
    __table_args__ = (
        Index("ix_technical_plans_instrument_id", "instrument_id"),
        Index("ix_technical_plans_active", "active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    reference_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    reference_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 6), nullable=True
    )
    trend_expectation: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    entry_zones: Mapped[Optional[list[Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    support_zones: Mapped[Optional[list[Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    resistance_zones: Mapped[Optional[list[Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    review_or_invalidation_zones: Mapped[Optional[list[Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    profit_taking_or_reassessment_zones: Mapped[Optional[list[Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

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

    instrument: Mapped["Instrument"] = relationship(
        "Instrument", back_populates="technical_plans"
    )
