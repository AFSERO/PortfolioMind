"""Explicit state application gate for protocol results (Part 5A)."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from investment_intelligence.enums import ProtocolRunStatus
from investment_intelligence.providers import _as_uuid
from investment_intelligence.records import IntelligenceStateRecord, ProtocolRunRecord
from investment_intelligence.repositories import (
    IntelligenceStateRepository,
    NotFoundError,
)
from investment_intelligence.services import ProtocolRunService
from investment_intelligence.validation import (
    MachineRecordValidationError,
    ThesisReviewRecord,
    UnsupportedProtocolError,
    validate_machine_record,
)


# ============================================================================
# 1. State Application Errors
# ============================================================================


class StateApplicationError(Exception):
    """Base exception for state application gate failures."""


class UnapprovedStateApplicationError(StateApplicationError):
    """State application was invoked without explicit human approval (approved=True)."""


class StaleProtocolRunError(StateApplicationError):
    """Protocol run is stale; its completion timestamp is older than current review state."""


class InvalidRunStateError(StateApplicationError):
    """Protocol run is not eligible for state application (e.g. RUNNING, FAILED, portfolio-level)."""


# ============================================================================
# 2. State Application Preview Structure
# ============================================================================


@dataclass(frozen=True)
class StateApplicationPreview:
    """Read-only preview of proposed IntelligenceState mutations before approval."""

    protocol_run_id: UUID
    instrument_id: UUID
    protocol_name: str
    current: dict[str, Any]
    proposed: dict[str, Any]
    changes: dict[str, dict[str, Any]]
    is_stale: bool = False
    has_changes: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol_run_id": str(self.protocol_run_id),
            "instrument_id": str(self.instrument_id),
            "protocol_name": self.protocol_name,
            "current": self.current,
            "proposed": self.proposed,
            "changes": self.changes,
            "is_stale": self.is_stale,
            "has_changes": self.has_changes,
        }


# ============================================================================
# 3. State Application Service
# ============================================================================


class StateApplicationService:
    """Manages the explicit, human-approved application of protocol outputs to state.

    Core Invariants:
    1. ProtocolRun completion NEVER automatically mutates IntelligenceState.
    2. State application requires explicit approval (approved=True).
    3. Stale runs (completed_at < current.last_review_at) cannot overwrite newer state.
    4. Re-application of the identical run is an idempotent no-op.
    5. Only instrument-level COMPLETED runs with valid Machine Records can be applied.
    6. Thesis Review strictly updates thesis_status and recommendation; valuation and
       technical dimensions remain untouched.
    7. Preview is strictly read-only and never writes to or creates rows in the DB.
    """

    def __init__(self, session: Session):
        self.session = session
        self.protocol_svc = ProtocolRunService(session)
        self.state_repo = IntelligenceStateRepository(session)

    def _require_valid_run(self, run_id: UUID) -> tuple[ProtocolRunRecord, Any]:
        """Load and validate a ProtocolRun for state application."""
        run = self.protocol_svc.get(run_id)
        if run is None:
            raise NotFoundError(f"ProtocolRun {run_id} not found")

        if run.instrument_id is None:
            raise InvalidRunStateError(
                f"ProtocolRun {run_id} is portfolio-level; state application requires an instrument-level run"
            )

        if run.status != ProtocolRunStatus.COMPLETED:
            raise InvalidRunStateError(
                f"ProtocolRun {run_id} has status '{run.status.value}'; only COMPLETED runs can be applied"
            )

        canonical_proto = run.protocol_name.strip().lower().replace("_", "-")
        if canonical_proto != "thesis-review":
            raise UnsupportedProtocolError(
                f"Protocol '{run.protocol_name}' is not supported for state application"
            )

        if run.machine_record is None:
            raise MachineRecordValidationError(
                f"ProtocolRun {run_id} has no machine_record"
            )

        validated = validate_machine_record(run.protocol_name, run.machine_record)
        return run, validated

    def preview(self, run_id: UUID | str) -> StateApplicationPreview:
        """Preview state mutations proposed by a completed protocol run (read-only)."""
        rid = _as_uuid(run_id)

        # Wrap in transaction block if bare session to prevent uncommitted autobegin state
        if not self.session.in_transaction():
            with self.session.begin():
                return self._preview_internal(rid)
        return self._preview_internal(rid)

    def _preview_internal(self, run_id: UUID) -> StateApplicationPreview:
        run, validated = self._require_valid_run(run_id)
        assert run.instrument_id is not None

        current_state = self.state_repo.get(run.instrument_id)

        if current_state is not None:
            cur_thesis = (
                current_state.thesis_status.value
                if current_state.thesis_status
                else None
            )
            cur_rec = (
                current_state.recommendation.value
                if current_state.recommendation
                else None
            )
            last_review = current_state.last_review_at
            is_stale = bool(
                last_review is not None
                and run.completed_at is not None
                and run.completed_at < last_review
            )
        else:
            cur_thesis = None
            cur_rec = None
            last_review = None
            is_stale = False

        if isinstance(validated, ThesisReviewRecord):
            proposed_thesis = validated.thesis_status.value
            proposed_rec = validated.recommendation.value
        else:
            raise UnsupportedProtocolError(
                f"Unsupported validated record type: {type(validated).__name__}"
            )

        changes = {
            "thesis_status": {"from": cur_thesis, "to": proposed_thesis},
            "recommendation": {"from": cur_rec, "to": proposed_rec},
        }
        has_changes = cur_thesis != proposed_thesis or cur_rec != proposed_rec

        return StateApplicationPreview(
            protocol_run_id=run.id,
            instrument_id=run.instrument_id,
            protocol_name=run.protocol_name,
            current={"thesis_status": cur_thesis, "recommendation": cur_rec},
            proposed={"thesis_status": proposed_thesis, "recommendation": proposed_rec},
            changes=changes,
            is_stale=is_stale,
            has_changes=has_changes,
        )

    def apply(
        self,
        run_id: UUID | str,
        *,
        approved: bool = False,
    ) -> IntelligenceStateRecord:
        """Apply validated protocol run results to IntelligenceState with explicit approval."""
        if not approved:
            raise UnapprovedStateApplicationError(
                "State application requires explicit approval; pass approved=True"
            )

        rid = _as_uuid(run_id)

        if not self.session.in_transaction():
            with self.session.begin():
                return self._apply_internal(rid)
        return self._apply_internal(rid)

    def _apply_internal(self, run_id: UUID) -> IntelligenceStateRecord:
        run, validated = self._require_valid_run(run_id)
        assert run.instrument_id is not None

        current_state = self.state_repo.get(run.instrument_id)

        # Stale run protection
        if current_state is not None and current_state.last_review_at is not None:
            if run.completed_at is not None:
                if run.completed_at < current_state.last_review_at:
                    raise StaleProtocolRunError(
                        f"Cannot apply stale run {run.id}: completed at {run.completed_at} "
                        f"which is older than current state last_review_at {current_state.last_review_at}"
                    )
                if run.completed_at == current_state.last_review_at:
                    # Idempotent re-application of the same review run
                    if isinstance(validated, ThesisReviewRecord):
                        if (
                            current_state.thesis_status == validated.thesis_status
                            and current_state.recommendation == validated.recommendation
                        ):
                            return current_state
                    raise StaleProtocolRunError(
                        f"Run {run.id} has same completion timestamp as current last_review_at with conflicting state"
                    )

        # Missing IntelligenceState handling: create initial row if absent
        if current_state is None:
            current_state = self.state_repo.create_initial(run.instrument_id)

        # Apply mapped fields atomically
        if isinstance(validated, ThesisReviewRecord):
            updated_state = self.state_repo.update(
                run.instrument_id,
                thesis_status=validated.thesis_status,
                recommendation=validated.recommendation,
                last_review_at=run.completed_at,
            )
            return updated_state

        raise UnsupportedProtocolError(
            f"Unsupported validated record type: {type(validated).__name__}"
        )


# ============================================================================
# 4. Convenience Functions
# ============================================================================


def preview_state_application(
    session: Session,
    run_id: UUID | str,
) -> StateApplicationPreview:
    """Convenience helper to preview state mutations from a ProtocolRun."""
    service = StateApplicationService(session)
    return service.preview(run_id)


def apply_state_application(
    session: Session,
    run_id: UUID | str,
    *,
    approved: bool = False,
) -> IntelligenceStateRecord:
    """Convenience helper to explicitly apply a ProtocolRun to IntelligenceState."""
    service = StateApplicationService(session)
    return service.apply(run_id, approved=approved)
