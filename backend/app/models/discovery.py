"""Database models for Market-Wide Discovery Engine v1."""

from datetime import datetime, timezone
import enum
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


class DiscoveryUniverse(str, enum.Enum):
    US_LARGE_CAP = "US_LARGE_CAP"
    US_TECH_GROWTH = "US_TECH_GROWTH"
    BIST_LIQUID = "BIST_LIQUID"
    CUSTOM = "CUSTOM"


class DiscoveryStatus(str, enum.Enum):
    HIGH_PRIORITY_SCREEN = "HIGH_PRIORITY_SCREEN"
    SCREEN = "SCREEN"
    WATCH = "WATCH"
    IGNORE = "IGNORE"


class DiscoveryCandidateState(str, enum.Enum):
    SURFACED = "SURFACED"
    WATCHLISTED = "WATCHLISTED"
    DISMISSED = "DISMISSED"
    SCREENED = "SCREENED"


class DiscoverySuggestedNextStep(str, enum.Enum):
    NONE = "NONE"
    ADD_TO_WATCHLIST = "ADD_TO_WATCHLIST"
    PRELIMINARY_SCREENING = "PRELIMINARY_SCREENING"


class DiscoveryConfidence(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DiscoveryRunStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DiscoveryTriggerType(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    MANUAL = "MANUAL"


class DiscoveryRun(Base):
    """Execution run record for market-wide candidate discovery."""

    __tablename__ = "discovery_runs"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    universe = Column(String(64), nullable=False, default=DiscoveryUniverse.US_LARGE_CAP.value)
    trigger_type = Column(
        Enum(DiscoveryTriggerType, native_enum=False, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=DiscoveryTriggerType.MANUAL,
    )
    status = Column(
        Enum(DiscoveryRunStatus, native_enum=False, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=DiscoveryRunStatus.RUNNING,
    )
    instruments_scanned = Column(Integer, nullable=False, default=0)
    candidates_filtered = Column(Integer, nullable=False, default=0)
    candidates_reasoned = Column(Integer, nullable=False, default=0)
    candidates_surfaced = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    diagnostics = Column(JSONType, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", backref="discovery_runs")
    candidates = relationship(
        "DiscoveryCandidate",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="desc(DiscoveryCandidate.created_at)",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_discovery_runs_user_id", "user_id"),
        Index("ix_discovery_runs_status", "status"),
        Index("ix_discovery_runs_created_at", "created_at"),
    )


class DiscoveryCandidate(Base):
    """An individual investment opportunity surfaced by the Discovery Engine."""

    __tablename__ = "discovery_candidates"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id = Column(Uuid, ForeignKey("discovery_runs.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    instrument_id = Column(Uuid, ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False)

    status = Column(
        Enum(DiscoveryStatus, native_enum=False, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=DiscoveryStatus.WATCH,
    )
    candidate_state = Column(
        Enum(DiscoveryCandidateState, native_enum=False, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=DiscoveryCandidateState.SURFACED,
    )

    primary_reason = Column(Text, nullable=False)
    signals = Column(JSONType, nullable=False, default=list)
    key_question = Column(Text, nullable=True)
    key_risk = Column(Text, nullable=True)

    suggested_next_step = Column(
        Enum(DiscoverySuggestedNextStep, native_enum=False, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=DiscoverySuggestedNextStep.NONE,
    )
    confidence = Column(
        Enum(DiscoveryConfidence, native_enum=False, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=DiscoveryConfidence.MEDIUM,
    )
    score_band = Column(String(16), nullable=True)

    current_price = Column(Numeric(18, 6), nullable=True)
    current_price_currency = Column(String(8), nullable=True)
    market_data_snapshot = Column(JSONType, nullable=False, default=dict)
    source_metadata = Column(JSONType, nullable=False, default=dict)

    dismissed_at = Column(DateTime(timezone=True), nullable=True)
    watchlisted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    run = relationship("DiscoveryRun", back_populates="candidates")
    user = relationship("User", backref="discovery_candidates")
    instrument = relationship("Instrument", backref="discovery_candidates", lazy="selectin")

    __table_args__ = (
        Index("ix_discovery_candidates_user_id", "user_id"),
        Index("ix_discovery_candidates_run_id", "run_id"),
        Index("ix_discovery_candidates_instrument_id", "instrument_id"),
        Index("ix_discovery_candidates_status", "status"),
        Index("ix_discovery_candidates_state", "candidate_state"),
    )
