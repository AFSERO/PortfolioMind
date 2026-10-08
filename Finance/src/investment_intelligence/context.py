"""Compact, JSON-serializable AI context builder for investment protocols."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from investment_intelligence.records import InstrumentRecord
from investment_intelligence.repositories import (
    InstrumentNotFoundError,
    InstrumentRepository,
    IntelligenceStateRepository,
    ResearchArtifactRepository,
)
from investment_intelligence.services import ProtocolRunService, TechnicalPlanService

from investment_intelligence.thesis import ThesisSnapshotRepository, compact_snapshot

DEFAULT_RUNS_LIMIT = 5
DEFAULT_ARTIFACTS_LIMIT = 5


def _iso_utc(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).isoformat()
    return dt.astimezone(timezone.utc).isoformat()


class ContextJSONEncoder(json.JSONEncoder):
    """Fallback encoder for UUIDs, datetimes, enums, and Decimals."""

    def default(self, o: Any) -> Any:
        if isinstance(o, UUID):
            return str(o)
        if isinstance(o, datetime):
            return _iso_utc(o)
        if isinstance(o, Enum):
            return o.value
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def serialize_context(context: dict[str, Any], *, indent: int | None = None) -> str:
    """Serialize asset context directly to deterministic JSON string."""
    return json.dumps(context, cls=ContextJSONEncoder, indent=indent)


class ContextBuilder:
    """Builds bounded, compact JSON-ready contexts without direct ORM exposure."""

    def __init__(self, session: Session):
        self.session = session
        self.instrument_repo = InstrumentRepository(session)
        self.state_repo = IntelligenceStateRepository(session)
        self.protocol_svc = ProtocolRunService(session)
        self.artifact_repo = ResearchArtifactRepository(session)
        self.plan_svc = TechnicalPlanService(session)

    def build_asset_context(
        self,
        instrument_id: UUID | InstrumentRecord | str,
        *,
        runs_limit: int = DEFAULT_RUNS_LIMIT,
        artifacts_limit: int = DEFAULT_ARTIFACTS_LIMIT,
    ) -> dict[str, Any]:
        """Produce compact, JSON-serializable asset context for AI protocol execution.

        Raises InstrumentNotFoundError if the instrument does not exist.
        Missing state, technical plan, protocol history, or artifacts are represented
        as null or empty lists without failing.
        """
        if runs_limit < 0 or artifacts_limit < 0:
            raise ValueError("runs_limit and artifacts_limit must be non-negative")

        inst = self.instrument_repo.get(instrument_id)
        if inst is None:
            raise InstrumentNotFoundError(f"Instrument {instrument_id} not found")

        # 1. Current Intelligence State
        state = self.state_repo.get(inst.id)
        state_payload = None
        if state is not None:
            state_payload = {
                "thesis_status": state.thesis_status.value if state.thesis_status else None,
                "valuation_status": state.valuation_status.value if state.valuation_status else None,
                "technical_status": state.technical_status.value if state.technical_status else None,
                "recommendation": state.recommendation.value if state.recommendation else None,
                "last_review_at": _iso_utc(state.last_review_at),
                "last_monitoring_at": _iso_utc(state.last_monitoring_at),
                "next_review_at": _iso_utc(state.next_review_at),
            }

        # 2. Active Technical Plan (Historical plans are omitted)
        active_plan = self.plan_svc.get_active_technical_plan(inst.id)
        plan_payload = None
        if active_plan is not None:
            plan_payload = {
                "id": str(active_plan.id),
                "reference_at": _iso_utc(active_plan.reference_at),
                "reference_price": float(active_plan.reference_price)
                if active_plan.reference_price is not None
                else None,
                "trend_expectation": active_plan.trend_expectation,
                "entry_zones": active_plan.entry_zones,
                "support_zones": active_plan.support_zones,
                "resistance_zones": active_plan.resistance_zones,
                "review_or_invalidation_zones": active_plan.review_or_invalidation_zones,
                "profit_taking_or_reassessment_zones": active_plan.profit_taking_or_reassessment_zones,
                "notes": active_plan.notes,
            }

        # 3. Bounded Recent Protocol Runs (Instrument-scoped only)
        recent_runs = self.protocol_svc.recent(instrument_id=inst.id, limit=runs_limit) if runs_limit > 0 else []
        runs_payload = [
            {
                "id": str(run.id),
                "protocol_name": run.protocol_name,
                "status": run.status.value,
                "started_at": _iso_utc(run.started_at),
                "completed_at": _iso_utc(run.completed_at),
                "machine_record": run.machine_record,
                "human_brief": run.human_brief,
                "confidence": run.confidence,
            }
            for run in recent_runs
        ]

        # 4. Bounded Research Artifact References (Instrument-scoped, file contents omitted)
        artifacts = (
            self.artifact_repo.list_for_instrument(inst.id, limit=artifacts_limit)
            if artifacts_limit > 0
            else []
        )
        artifacts_payload = [
            {
                "id": str(art.id),
                "artifact_type": art.artifact_type,
                "path": art.path,
                "version": art.version,
                "created_at": _iso_utc(art.created_at),
                "protocol_run_id": str(art.protocol_run_id) if art.protocol_run_id else None,
                "artifact_metadata": art.artifact_metadata,
            }
            for art in artifacts
        ]

        return {
            "instrument": {
                "id": str(inst.id),
                "symbol": inst.symbol,
                "name": inst.name,
                "instrument_type": inst.instrument_type,
                "venue": inst.venue,
                "currency": inst.currency,
            },
            "intelligence_state": state_payload,
            "thesis_snapshot": compact_snapshot(ThesisSnapshotRepository(self.session).latest(inst.id)),
            "active_technical_plan": plan_payload,
            "recent_protocol_runs": runs_payload,
            "research_artifacts": artifacts_payload,
        }


def build_asset_context(
    session: Session,
    instrument_id: UUID | InstrumentRecord | str,
    *,
    runs_limit: int = DEFAULT_RUNS_LIMIT,
    artifacts_limit: int = DEFAULT_ARTIFACTS_LIMIT,
) -> dict[str, Any]:
    """Convenience function to build compact asset context for an instrument."""
    return ContextBuilder(session).build_asset_context(
        instrument_id, runs_limit=runs_limit, artifacts_limit=artifacts_limit
    )
