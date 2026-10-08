"""Explicit, repeatable bootstrap from the reviewed, dated UBER research extraction."""

import argparse
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from investment_intelligence.database import create_db_engine
from investment_intelligence.models import Instrument, ThesisSnapshot
from investment_intelligence.thesis import ThesisSnapshotRepository, ThesisSnapshotRecord
from investment_intelligence.records import _snapshot
from investment_intelligence.repositories import _require

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "system/database/seeds/uber-thesis-2026-09-14.json"


def bootstrap_uber(session, instrument_id, *, root=ROOT):
    """Caller owns transaction. Same dated content is a no-op; conflict fails closed."""
    inst = _require(session, Instrument, instrument_id, lock=True)
    if (inst.symbol, inst.instrument_type, inst.currency) != ("UBER", "equity", "USD"):
        raise ValueError("Explicit instrument must be UBER equity in USD")
    payload = json.loads((root / SEED.relative_to(ROOT)).read_text(encoding="utf-8"))
    for ref in payload["source_artifact_references"]:
        if not (root / ref["path"]).is_file():
            raise ValueError("Missing source artifact: " + ref["path"])
    payload["as_of"] = datetime.fromisoformat(payload["as_of"])
    rows = session.scalars(select(ThesisSnapshot).where(
        ThesisSnapshot.instrument_id == inst.id, ThesisSnapshot.as_of == payload["as_of"],
    )).all()
    if rows:
        for row in rows:
            record = _snapshot(ThesisSnapshotRecord, row)
            values = asdict(record)
            if all(values[k] == v for k, v in payload.items()) and record.source_protocol_run_id is None:
                return record, False
        raise ValueError("Existing dated UBER thesis differs; history will not be overwritten")
    return ThesisSnapshotRepository(session).create(inst.id, **payload), True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instrument-id", type=UUID, required=True)
    args = parser.parse_args()
    engine = create_db_engine()
    try:
        with Session(engine) as session, session.begin():
            record, created = bootstrap_uber(session, args.instrument_id)
        print(json.dumps({"snapshot_id": str(record.id), "created": created,
                          "as_of": record.as_of.isoformat()}))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
