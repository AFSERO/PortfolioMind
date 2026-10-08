"""Small persistence APIs. Caller owns the transaction; methods never commit."""

from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from investment_intelligence.enums import Recommendation, TechnicalStatus, ThesisStatus, ValuationStatus
from investment_intelligence.models import Instrument, IntelligenceState, ProtocolRun, ResearchArtifact
from investment_intelligence.records import (
    InstrumentRecord, IntelligenceStateRecord, ResearchArtifactRecord, _snapshot,
)


class RepositoryError(Exception):
    """Base error for repository and service operations."""


class NotFoundError(RepositoryError, LookupError):
    """Requested entity does not exist."""


class InstrumentNotFoundError(NotFoundError):
    """Target instrument does not exist."""


class StateAlreadyExistsError(RepositoryError, ValueError):
    """Initial state creation would replace an existing current state."""


class ArtifactRunMismatchError(RepositoryError, ValueError):
    """Artifact and instrument-level run refer to different instruments."""


class _Unset(Enum):
    VALUE = "unset"


_UNSET = _Unset.VALUE


def _clean(session: Session) -> None:
    if not session.is_active:
        raise ValueError("Session has a failed transaction; caller must roll it back")
    if session.new or session.dirty or session.deleted:
        raise ValueError("Use a clean Session without pending direct ORM changes")


@contextmanager
def _write(session: Session):
    _clean(session)
    if not session.in_transaction():
        raise ValueError("Writes require a caller-owned transaction: with session.begin()")
    # A failed operation rolls back only its changes, preserving earlier caller work.
    with session.begin_nested():
        yield


def _id(identity: Any) -> UUID:
    if hasattr(identity, "id"):
        return identity.id
    if hasattr(identity, "instrument_id"):
        return identity.instrument_id
    if isinstance(identity, str):
        return UUID(identity)
    return identity


def _load(session: Session, model, identity, *, lock=False):
    _clean(session)
    identity = _id(identity)
    key = model.instrument_id if model is IntelligenceState else model.id
    query = select(model).where(key == identity).execution_options(populate_existing=True)
    if lock:
        query = query.with_for_update()
    return session.scalar(query)


def _require(session: Session, model, identity, *, lock=False):
    identity = _id(identity)
    value = _load(session, model, identity, lock=lock)
    if value is None:
        if model is Instrument:
            raise InstrumentNotFoundError(f"Instrument {identity} not found")
        raise NotFoundError(f"{model.__name__} {identity} not found")
    return value


def _saved(session: Session, model, record_type):
    session.flush()
    session.refresh(model)  # Include defaults and canonical UTC timestamps.
    return _snapshot(record_type, model)


def _page(limit: int, offset: int) -> None:
    if type(limit) is not int or not 1 <= limit <= 200 or type(offset) is not int or offset < 0:
        raise ValueError("limit must be 1..200 and offset a non-negative integer")


def _rows(session: Session, query, record_type, limit: int, offset: int):
    _clean(session)
    _page(limit, offset)
    return [_snapshot(record_type, row) for row in session.scalars(
        query.limit(limit).offset(offset).execution_options(populate_existing=True)
    )]


def _text(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text")
    return value


class InstrumentRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, *, symbol: str, name: str, instrument_type: str,
               currency: str, venue: str | None = None) -> InstrumentRecord:
        with _write(self.session):
            row = Instrument(symbol=_text(symbol, "symbol"), name=_text(name, "name"),
                             instrument_type=_text(instrument_type, "instrument_type"),
                             currency=_text(currency, "currency"), venue=venue)
            self.session.add(row)
            return _saved(self.session, row, InstrumentRecord)

    def get(self, instrument_id: UUID) -> InstrumentRecord | None:
        row = _load(self.session, Instrument, instrument_id)
        return _snapshot(InstrumentRecord, row) if row is not None else None

    def list(self, *, symbol: str | None = None, instrument_type: str | None = None,
             venue: str | None | _Unset = _UNSET, name: str | None = None,
             limit: int = 50, offset: int = 0) -> list[InstrumentRecord]:
        query = select(Instrument)
        if symbol is not None:
            query = query.where(Instrument.symbol == symbol)
        if instrument_type is not None:
            query = query.where(Instrument.instrument_type == instrument_type)
        if venue is not _UNSET:
            query = query.where(Instrument.venue == venue)
        if name is not None:
            query = query.where(Instrument.name.icontains(name, autoescape=True))
        return _rows(self.session, query.order_by(Instrument.symbol, Instrument.id),
                     InstrumentRecord, limit, offset)

    def update(self, instrument_id: UUID, **changes: Any) -> InstrumentRecord:
        allowed = {"symbol", "name", "instrument_type", "currency", "venue"}
        if set(changes) - allowed:
            raise ValueError("Only basic instrument metadata can be updated")
        with _write(self.session):
            row = _require(self.session, Instrument, instrument_id)
            for key, value in changes.items():
                setattr(row, key, value if key == "venue" and value is None else _text(value, key))
            return _saved(self.session, row, InstrumentRecord)


class IntelligenceStateRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, instrument_id: UUID) -> IntelligenceStateRecord | None:
        row = _load(self.session, IntelligenceState, instrument_id)
        return _snapshot(IntelligenceStateRecord, row) if row is not None else None

    def create_initial(self, instrument_id: UUID) -> IntelligenceStateRecord:
        try:
            with _write(self.session):
                _require(self.session, Instrument, instrument_id)
                if _load(self.session, IntelligenceState, instrument_id) is not None:
                    raise StateAlreadyExistsError(f"State already exists for {instrument_id}")
                row = IntelligenceState(instrument_id=instrument_id)
                self.session.add(row)
                return _saved(self.session, row, IntelligenceStateRecord)
        except IntegrityError as error:
            orig = getattr(error, "orig", None)
            sqlstate = getattr(orig, "sqlstate", None)
            diag = getattr(orig, "diag", None)
            constraint_name = getattr(diag, "constraint_name", None)
            if sqlstate == "23505" and constraint_name == "intelligence_states_pkey":
                raise StateAlreadyExistsError(f"State already exists for {instrument_id}") from error
            raise

    def update(self, instrument_id: UUID, *,
               thesis_status: ThesisStatus | None | _Unset = _UNSET,
               valuation_status: ValuationStatus | None | _Unset = _UNSET,
               technical_status: TechnicalStatus | None | _Unset = _UNSET,
               recommendation: Recommendation | None | _Unset = _UNSET,
               last_review_at: datetime | None | _Unset = _UNSET,
               last_monitoring_at: datetime | None | _Unset = _UNSET,
               next_review_at: datetime | None | _Unset = _UNSET) -> IntelligenceStateRecord:
        changes = {
            "thesis_status": thesis_status, "valuation_status": valuation_status,
            "technical_status": technical_status, "recommendation": recommendation,
            "last_review_at": last_review_at, "last_monitoring_at": last_monitoring_at,
            "next_review_at": next_review_at,
        }
        enum_types = {"thesis_status": ThesisStatus, "valuation_status": ValuationStatus,
                      "technical_status": TechnicalStatus, "recommendation": Recommendation}
        with _write(self.session):
            row = _require(self.session, IntelligenceState, instrument_id)
            for key, value in changes.items():
                if value is not _UNSET:
                    if key in enum_types and value is not None:
                        value = enum_types[key](value)
                    setattr(row, key, value)
            return _saved(self.session, row, IntelligenceStateRecord)

    def mark_reviewed(self, instrument_id: UUID, *, at: datetime | None = None) -> IntelligenceStateRecord:
        return self.update(instrument_id, last_review_at=at if at is not None else datetime.now(timezone.utc))

    def mark_monitored(self, instrument_id: UUID, *, at: datetime | None = None) -> IntelligenceStateRecord:
        return self.update(instrument_id, last_monitoring_at=at if at is not None else datetime.now(timezone.utc))


class ResearchArtifactRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, instrument_id: UUID, *, artifact_type: str, path: str,
               version: str | None = None, protocol_run_id: UUID | None = None,
               metadata: dict[str, Any] | None = None) -> ResearchArtifactRecord:
        with _write(self.session):
            _require(self.session, Instrument, instrument_id)
            if protocol_run_id is not None:
                run = _require(self.session, ProtocolRun, protocol_run_id)
                if run.instrument_id is not None and run.instrument_id != instrument_id:
                    raise ArtifactRunMismatchError("Artifact must match the instrument-level run")
            row = ResearchArtifact(instrument_id=instrument_id, protocol_run_id=protocol_run_id,
                                   artifact_type=_text(artifact_type, "artifact_type"),
                                   path=_text(path, "path"), version=version, artifact_metadata=metadata)
            self.session.add(row)
            return _saved(self.session, row, ResearchArtifactRecord)

    def get(self, artifact_id: UUID) -> ResearchArtifactRecord | None:
        row = _load(self.session, ResearchArtifact, artifact_id)
        return _snapshot(ResearchArtifactRecord, row) if row is not None else None

    def list_for_instrument(self, instrument_id: UUID, *, limit: int = 50, offset: int = 0) -> list[ResearchArtifactRecord]:
        return _rows(self.session, select(ResearchArtifact).where(
            ResearchArtifact.instrument_id == _id(instrument_id)
        ).order_by(ResearchArtifact.created_at.desc(), ResearchArtifact.id.desc()),
            ResearchArtifactRecord, limit, offset)

    def list_for_run(self, run_id: UUID, *, limit: int = 50, offset: int = 0) -> list[ResearchArtifactRecord]:
        return _rows(self.session, select(ResearchArtifact).where(
            ResearchArtifact.protocol_run_id == _id(run_id)
        ).order_by(ResearchArtifact.created_at.desc(), ResearchArtifact.id.desc()),
            ResearchArtifactRecord, limit, offset)
