"""Application-facing snapshots, independent of ORM/session lifetime."""

from copy import deepcopy
from dataclasses import dataclass, fields
from datetime import datetime
from decimal import Decimal
from typing import Any, TypeVar
from uuid import UUID

from investment_intelligence.enums import (
    ProtocolRunStatus, Recommendation, TechnicalStatus, ThesisStatus, ValuationStatus,
)


@dataclass(frozen=True)
class InstrumentRecord:
    id: UUID
    symbol: str
    name: str
    instrument_type: str
    venue: str | None
    currency: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class IntelligenceStateRecord:
    instrument_id: UUID
    thesis_status: ThesisStatus | None
    valuation_status: ValuationStatus | None
    technical_status: TechnicalStatus | None
    recommendation: Recommendation | None
    last_review_at: datetime | None
    last_monitoring_at: datetime | None
    next_review_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ProtocolRunRecord:
    id: UUID
    instrument_id: UUID | None
    protocol_name: str
    status: ProtocolRunStatus
    started_at: datetime
    completed_at: datetime | None
    machine_record: dict[str, Any] | None
    human_brief: str | None
    confidence: str | None
    created_at: datetime


@dataclass(frozen=True)
class ResearchArtifactRecord:
    id: UUID
    instrument_id: UUID
    artifact_type: str
    path: str
    version: str | None
    created_at: datetime
    protocol_run_id: UUID | None
    artifact_metadata: dict[str, Any] | None


@dataclass(frozen=True)
class TechnicalPlanRecord:
    id: UUID
    instrument_id: UUID
    reference_at: datetime
    reference_price: Decimal | None
    trend_expectation: str | None
    entry_zones: list[dict[str, Any]] | None
    support_zones: list[dict[str, Any]] | None
    resistance_zones: list[dict[str, Any]] | None
    review_or_invalidation_zones: list[dict[str, Any]] | None
    profit_taking_or_reassessment_zones: list[dict[str, Any]] | None
    notes: str | None
    active: bool
    created_at: datetime
    updated_at: datetime


Record = TypeVar("Record")


def _snapshot(record_type: type[Record], model: Any) -> Record:
    # Nested JSON must never share mutable objects with SQLAlchemy's identity map.
    return record_type(**{field.name: deepcopy(getattr(model, field.name))
                          for field in fields(record_type)})
