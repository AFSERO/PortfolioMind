"""Instrument identity and its optional, current intelligence snapshot."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Index, Numeric, String, Text, false, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from investment_intelligence.database import Base, UTCDateTime
from investment_intelligence.enums import (
    ProtocolRunStatus,
    Recommendation,
    TechnicalStatus,
    ThesisStatus,
    ValuationStatus,
)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Instrument(Timestamps, Base):
    __tablename__ = "instruments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    instrument_type: Mapped[str] = mapped_column(String(64))
    venue: Mapped[str | None] = mapped_column(String(128))
    currency: Mapped[str] = mapped_column(String(16))

    intelligence_state: Mapped["IntelligenceState | None"] = relationship(
        back_populates="instrument", cascade="all, delete-orphan", passive_deletes=True
    )
    protocol_runs: Mapped[list["ProtocolRun"]] = relationship(
        back_populates="instrument", passive_deletes="all"
    )
    research_artifacts: Mapped[list["ResearchArtifact"]] = relationship(
        back_populates="instrument", passive_deletes="all"
    )
    technical_plans: Mapped[list["TechnicalPlan"]] = relationship(
        back_populates="instrument", passive_deletes="all"
    )


class IntelligenceState(Timestamps, Base):
    __tablename__ = "intelligence_states"

    instrument_id: Mapped[UUID] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), primary_key=True
    )
    thesis_status: Mapped[ThesisStatus | None] = mapped_column(
        Enum(ThesisStatus, name="thesis_status", validate_strings=True)
    )
    valuation_status: Mapped[ValuationStatus | None] = mapped_column(
        Enum(ValuationStatus, name="valuation_status", validate_strings=True)
    )
    technical_status: Mapped[TechnicalStatus | None] = mapped_column(
        Enum(TechnicalStatus, name="technical_status", validate_strings=True)
    )
    recommendation: Mapped[Recommendation | None] = mapped_column(
        Enum(Recommendation, name="recommendation", validate_strings=True)
    )
    last_review_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_monitoring_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    next_review_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    instrument: Mapped[Instrument] = relationship(back_populates="intelligence_state")


class ProtocolRun(Base):
    """Generic execution history; terminal records are immutable (migration 0002)."""

    __tablename__ = "protocol_runs"
    __table_args__ = (
        CheckConstraint(
            "(status = 'RUNNING' AND completed_at IS NULL) OR "
            "(status IN ('COMPLETED', 'FAILED') AND completed_at IS NOT NULL)",
            name="ck_protocol_runs_completion",
        ),
        CheckConstraint("completed_at >= started_at", name="ck_protocol_runs_time_order"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("instruments.id", ondelete="RESTRICT"), index=True
    )
    protocol_name: Mapped[str] = mapped_column(String(128))
    status: Mapped[ProtocolRunStatus] = mapped_column(
        Enum(ProtocolRunStatus, name="protocol_run_status", validate_strings=True),
        server_default=ProtocolRunStatus.RUNNING.value,
    )
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    machine_record: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    human_brief: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())

    instrument: Mapped[Instrument | None] = relationship(back_populates="protocol_runs")
    research_artifacts: Mapped[list["ResearchArtifact"]] = relationship(
        back_populates="protocol_run", passive_deletes="all"
    )


class ResearchArtifact(Base):
    """Reference to a versioned file; report content stays in the research folder."""

    __tablename__ = "research_artifacts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID] = mapped_column(
        ForeignKey("instruments.id", ondelete="RESTRICT"), index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(64))
    path: Mapped[str] = mapped_column(Text)
    version: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    protocol_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("protocol_runs.id", ondelete="RESTRICT"), index=True
    )
    # Declarative reserves the Python name 'metadata'; retain it as the SQL name.
    artifact_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB(none_as_null=True)
    )

    instrument: Mapped[Instrument] = relationship(back_populates="research_artifacts")
    protocol_run: Mapped[ProtocolRun | None] = relationship(back_populates="research_artifacts")


class ThesisSnapshot(Base):
    """Append-only compact thesis history; detailed research stays on disk."""

    __tablename__ = "thesis_snapshots"
    __table_args__ = (Index("ix_thesis_snapshots_baseline", "instrument_id", "as_of", "created_at", "id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID] = mapped_column(ForeignKey("instruments.id", ondelete="RESTRICT"))
    as_of: Mapped[datetime] = mapped_column(UTCDateTime())
    core_investment_rationale: Mapped[str] = mapped_column(Text)
    key_assumptions: Mapped[list] = mapped_column(JSONB)
    growth_drivers: Mapped[list] = mapped_column(JSONB)
    moat_or_competitive_assumptions: Mapped[list] = mapped_column(JSONB)
    key_risks: Mapped[list] = mapped_column(JSONB)
    invalidation_conditions: Mapped[list] = mapped_column(JSONB)
    key_kpis: Mapped[list] = mapped_column(JSONB)
    catalysts: Mapped[list] = mapped_column(JSONB)
    open_questions: Mapped[list] = mapped_column(JSONB)
    confidence: Mapped[str | None] = mapped_column(String(32))
    source_protocol_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("protocol_runs.id", ondelete="RESTRICT"))
    source_artifact_references: Mapped[list] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())


class TechnicalPlan(Timestamps, Base):
    """Separate rows retain earlier technical plans; activation is explicit."""

    __tablename__ = "technical_plans"
    __table_args__ = (
        Index("uq_technical_plans_active_instrument", "instrument_id", unique=True,
              postgresql_where=text("active")),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID] = mapped_column(
        ForeignKey("instruments.id", ondelete="RESTRICT"), index=True
    )
    reference_at: Mapped[datetime] = mapped_column(UTCDateTime())
    reference_price: Mapped[Decimal | None] = mapped_column(Numeric(28, 12))
    trend_expectation: Mapped[str | None] = mapped_column(Text)
    entry_zones: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB(none_as_null=True))
    support_zones: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB(none_as_null=True))
    resistance_zones: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB(none_as_null=True))
    review_or_invalidation_zones: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB(none_as_null=True))
    profit_taking_or_reassessment_zones: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB(none_as_null=True))
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, server_default=false())

    instrument: Mapped[Instrument] = relationship(back_populates="technical_plans")
