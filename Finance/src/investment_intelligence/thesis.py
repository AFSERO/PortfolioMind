"""Bounded thesis persistence. Caller owns transactions; no state application."""

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from investment_intelligence.models import Instrument, ProtocolRun, ThesisSnapshot
from investment_intelligence.records import _snapshot
from investment_intelligence.repositories import _clean, _id, _require, _saved, _write

LIST_FIELDS = (
    "key_assumptions", "growth_drivers", "moat_or_competitive_assumptions",
    "key_risks", "invalidation_conditions", "key_kpis", "catalysts",
    "open_questions", "source_artifact_references",
)
MAX_CONTENT_BYTES = 12000


def aware_utc(value):
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("Timezone-aware datetime required")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ThesisSnapshotRecord:
    id: UUID
    instrument_id: UUID
    as_of: datetime
    core_investment_rationale: str
    key_assumptions: list
    growth_drivers: list
    moat_or_competitive_assumptions: list
    key_risks: list
    invalidation_conditions: list
    key_kpis: list
    catalysts: list
    open_questions: list
    confidence: str | None
    source_protocol_run_id: UUID | None
    source_artifact_references: list
    created_at: datetime


def compact_snapshot(record):
    if record is None:
        return None
    payload = asdict(record)
    for field in ("id", "instrument_id", "source_protocol_run_id"):
        payload[field] = str(payload[field]) if payload[field] is not None else None
    for field in ("as_of", "created_at"):
        payload[field] = aware_utc(payload[field]).isoformat()
    return payload


class ThesisSnapshotRepository:
    def __init__(self, session):
        self.session = session

    def create(self, instrument_id, *, as_of, core_investment_rationale,
               confidence=None, source_protocol_run_id=None, **fields):
        as_of = aware_utc(as_of)
        if not isinstance(core_investment_rationale, str) or not core_investment_rationale.strip():
            raise ValueError("core_investment_rationale must be non-empty text")
        if fields.keys() - set(LIST_FIELDS):
            raise ValueError("Unknown thesis fields")
        content = {name: fields.get(name, []) for name in LIST_FIELDS}
        if any(not isinstance(value, list) or len(value) > 20 for value in content.values()):
            raise ValueError("Structured fields must be lists of at most 20 items")
        content["core_investment_rationale"] = core_investment_rationale
        if len(json.dumps(content, ensure_ascii=False, allow_nan=False).encode("utf-8")) > MAX_CONTENT_BYTES:
            raise ValueError("Compact thesis content exceeds 12000 bytes")
        if confidence is not None and (not isinstance(confidence, str) or len(confidence) > 32):
            raise ValueError("confidence must be a short label")
        with _write(self.session):
            inst = _require(self.session, Instrument, instrument_id)
            if source_protocol_run_id is not None:
                run = _require(self.session, ProtocolRun, source_protocol_run_id)
                if run.instrument_id is not None and run.instrument_id != inst.id:
                    raise ValueError("Snapshot source run must match instrument")
            row = ThesisSnapshot(instrument_id=inst.id, as_of=as_of,
                                 confidence=confidence, source_protocol_run_id=source_protocol_run_id,
                                 **content)
            self.session.add(row)
            return _saved(self.session, row, ThesisSnapshotRecord)

    def latest(self, instrument_id, *, applicable_at=None):
        _clean(self.session)
        cutoff = aware_utc(applicable_at) if applicable_at is not None else datetime.now(timezone.utc)
        row = self.session.scalar(select(ThesisSnapshot).where(
            ThesisSnapshot.instrument_id == _id(instrument_id), ThesisSnapshot.as_of <= cutoff,
        ).order_by(ThesisSnapshot.as_of.desc(), ThesisSnapshot.created_at.desc(),
                   ThesisSnapshot.id.desc()).limit(1))
        return _snapshot(ThesisSnapshotRecord, row) if row is not None else None
