"""Protocol lifecycle and atomic plan activation; no execution or hidden commits."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from investment_intelligence.enums import ProtocolRunStatus
from investment_intelligence.models import Instrument, ProtocolRun, TechnicalPlan
from investment_intelligence.records import ProtocolRunRecord, TechnicalPlanRecord, _snapshot
from investment_intelligence.repositories import (
    _UNSET, RepositoryError, _Unset, _id, _load, _require, _rows, _saved, _text, _write,
)


class InvalidProtocolLifecycleError(RepositoryError, ValueError):
    """A terminal protocol run cannot be completed or failed again."""


class TechnicalPlanActivationConflictError(RepositoryError, ValueError):
    """Concurrent activation hit the database's single-active-plan constraint."""


class ProtocolRunService:
    def __init__(self, session: Session):
        self.session = session

    def start(self, protocol_name: str, *, instrument_id: UUID | None = None,
              started_at: datetime | None = None) -> ProtocolRunRecord:
        with _write(self.session):
            if instrument_id is not None:
                _require(self.session, Instrument, instrument_id)
            row = ProtocolRun(protocol_name=_text(protocol_name, "protocol_name"),
                              instrument_id=instrument_id, status=ProtocolRunStatus.RUNNING,
                              started_at=started_at if started_at is not None else datetime.now(timezone.utc))
            self.session.add(row)
            return _saved(self.session, row, ProtocolRunRecord)

    def complete(self, run_id: UUID, *, machine_record: dict[str, Any] | None = None,
                 human_brief: str | None = None, confidence: str | None = None,
                 completed_at: datetime | None = None) -> ProtocolRunRecord:
        return self._finish(run_id, ProtocolRunStatus.COMPLETED, machine_record,
                            human_brief, confidence, completed_at)

    def fail(self, run_id: UUID, *, reason: str, machine_record: dict[str, Any] | None = None,
             confidence: str | None = None, completed_at: datetime | None = None) -> ProtocolRunRecord:
        # Minimal failure information reuses the human_brief column.
        return self._finish(run_id, ProtocolRunStatus.FAILED, machine_record,
                            _text(reason, "reason"), confidence, completed_at)

    def _finish(self, run_id, status, machine_record, human_brief, confidence, completed_at):
        with _write(self.session):
            # The row lock makes concurrent terminal transitions observe the winner.
            row = _require(self.session, ProtocolRun, run_id, lock=True)
            if row.status is not ProtocolRunStatus.RUNNING:
                raise InvalidProtocolLifecycleError(f"Run {run_id} is already {row.status}")
            row.status = status
            row.completed_at = completed_at if completed_at is not None else datetime.now(timezone.utc)
            row.machine_record = machine_record
            row.human_brief = human_brief
            row.confidence = confidence
            return _saved(self.session, row, ProtocolRunRecord)

    def get(self, run_id: UUID) -> ProtocolRunRecord | None:
        row = _load(self.session, ProtocolRun, run_id)
        return _snapshot(ProtocolRunRecord, row) if row is not None else None

    def recent(self, *, instrument_id: UUID | None | _Unset = _UNSET,
               protocol_name: str | None = None, limit: int = 50, offset: int = 0) -> list[ProtocolRunRecord]:
        query = select(ProtocolRun)
        if instrument_id is not _UNSET:
            query = query.where(ProtocolRun.instrument_id == instrument_id)
        if protocol_name is not None:
            query = query.where(ProtocolRun.protocol_name == protocol_name)
        return _rows(self.session, query.order_by(ProtocolRun.started_at.desc(), ProtocolRun.id.desc()),
                     ProtocolRunRecord, limit, offset)


class TechnicalPlanService:
    def __init__(self, session: Session):
        self.session = session

    def create_inactive(self, instrument_id: UUID, *, reference_at: datetime,
                        reference_price: Decimal | None = None, trend_expectation: str | None = None,
                        entry_zones: list[dict[str, Any]] | None = None,
                        support_zones: list[dict[str, Any]] | None = None,
                        resistance_zones: list[dict[str, Any]] | None = None,
                        review_or_invalidation_zones: list[dict[str, Any]] | None = None,
                        profit_taking_or_reassessment_zones: list[dict[str, Any]] | None = None,
                        notes: str | None = None) -> TechnicalPlanRecord:
        with _write(self.session):
            _require(self.session, Instrument, instrument_id)
            row = TechnicalPlan(
                instrument_id=instrument_id, reference_at=reference_at,
                reference_price=reference_price, trend_expectation=trend_expectation,
                entry_zones=entry_zones, support_zones=support_zones, resistance_zones=resistance_zones,
                review_or_invalidation_zones=review_or_invalidation_zones,
                profit_taking_or_reassessment_zones=profit_taking_or_reassessment_zones,
                notes=notes, active=False,
            )
            self.session.add(row)
            return _saved(self.session, row, TechnicalPlanRecord)

    def get(self, plan_id: UUID) -> TechnicalPlanRecord | None:
        row = _load(self.session, TechnicalPlan, plan_id)
        return _snapshot(TechnicalPlanRecord, row) if row is not None else None

    def get_active_technical_plan(self, instrument_id: UUID) -> TechnicalPlanRecord | None:
        rows = _rows(self.session, select(TechnicalPlan).where(
            TechnicalPlan.instrument_id == _id(instrument_id), TechnicalPlan.active.is_(True)
        ), TechnicalPlanRecord, 1, 0)
        return rows[0] if rows else None

    def list_history(self, instrument_id: UUID, *, limit: int = 50, offset: int = 0) -> list[TechnicalPlanRecord]:
        return _rows(self.session, select(TechnicalPlan).where(
            TechnicalPlan.instrument_id == _id(instrument_id)
        ).order_by(TechnicalPlan.reference_at.desc(), TechnicalPlan.id.desc()),
            TechnicalPlanRecord, limit, offset)

    def activate_technical_plan(self, plan_id: UUID) -> TechnicalPlanRecord:
        try:
            with _write(self.session):
                target = _require(self.session, TechnicalPlan, plan_id)
                self.session.execute(update(TechnicalPlan).where(
                    TechnicalPlan.instrument_id == target.instrument_id,
                    TechnicalPlan.active.is_(True), TechnicalPlan.id != target.id,
                ).values(active=False))
                self.session.execute(update(TechnicalPlan).where(
                    TechnicalPlan.id == target.id
                ).values(active=True))
                self.session.expire_all()
                return _saved(self.session, target, TechnicalPlanRecord)
        except IntegrityError as error:
            orig = getattr(error, "orig", None)
            sqlstate = getattr(orig, "sqlstate", None)
            diag = getattr(orig, "diag", None)
            constraint_name = getattr(diag, "constraint_name", None)
            if sqlstate == "23505" and constraint_name == "uq_technical_plans_active_instrument":
                raise TechnicalPlanActivationConflictError(f"Activation conflict for plan {plan_id}") from error
            raise
