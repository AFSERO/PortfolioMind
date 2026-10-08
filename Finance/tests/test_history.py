"""Part 2 persistence invariants on PostgreSQL, including direct SQL writes."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import DataError, IntegrityError, StatementError

from investment_intelligence.enums import ProtocolRunStatus, Recommendation
from investment_intelligence.models import (
    Instrument, IntelligenceState, ProtocolRun, ResearchArtifact, TechnicalPlan,
)

pytestmark = pytest.mark.postgres
INSTANT = datetime(2026, 9, 15, 12, tzinfo=timezone.utc)
ZONE_FIELDS = (
    "entry_zones", "support_zones", "resistance_zones", "review_or_invalidation_zones",
    "profit_taking_or_reassessment_zones",
)


def asset():
    return Instrument(symbol="HISTORY", name="Test asset", instrument_type="equity", currency="USD")


@pytest.mark.parametrize("instrument_level", [False, True])
@pytest.mark.parametrize("status", [ProtocolRunStatus.COMPLETED, ProtocolRunStatus.FAILED])
def test_protocol_run_roundtrip_and_current_state_separation(session, instrument_level, status):
    item = asset() if instrument_level else None
    if item:
        item.intelligence_state = IntelligenceState(recommendation=Recommendation.HOLD)
    record = {"thesis": {"status": "UNCHANGED"}, "risks": ["Evidence gap"], "value": None}
    run = ProtocolRun(instrument=item, protocol_name="deep_research", started_at=INSTANT)
    session.add(run)
    session.flush()
    assert run.status is ProtocolRunStatus.RUNNING
    run.status = status
    run.completed_at = INSTANT + timedelta(minutes=3)
    run.machine_record = record
    run.human_brief = "Araştırma kapsamı tamamlandı."
    run.confidence = "MEDIUM"
    session.commit()
    identity = run.id
    session.expunge_all()
    stored = session.get(ProtocolRun, identity)
    assert stored.status is status
    assert stored.machine_record == record
    assert stored.human_brief == "Araştırma kapsamı tamamlandı."
    assert stored.confidence == "MEDIUM"
    if instrument_level:
        assert stored.instrument.protocol_runs == [stored]
        assert stored.instrument.intelligence_state.recommendation is Recommendation.HOLD
    else:
        assert stored.instrument_id is None
        assert stored.instrument is None


def test_run_does_not_create_current_state(session):
    run = ProtocolRun(instrument=asset(), protocol_name="screening", started_at=INSTANT)
    session.add(run)
    session.flush()
    assert session.get(IntelligenceState, run.instrument_id) is None


@pytest.mark.parametrize("status", [ProtocolRunStatus.COMPLETED, ProtocolRunStatus.FAILED])
def test_terminal_runs_reject_sql_updates_and_deletes(session, status):
    run = ProtocolRun(protocol_name="review", status=status, started_at=INSTANT, completed_at=INSTANT)
    session.add(run)
    session.flush()
    identity = run.id
    for sql in (
        "UPDATE protocol_runs SET human_brief = 'rewrite' WHERE id = :id",
        "UPDATE protocol_runs SET machine_record = '{\"changed\": true}'::jsonb WHERE id = :id",
        "UPDATE protocol_runs SET status = 'RUNNING', completed_at = NULL WHERE id = :id",
        "DELETE FROM protocol_runs WHERE id = :id",
    ):
        with pytest.raises(IntegrityError):
            with session.begin_nested():
                session.execute(text(sql), {"id": identity})


def test_running_run_cannot_lose_its_identity_or_be_deleted(session):
    run = ProtocolRun(instrument=asset(), protocol_name="review", started_at=INSTANT)
    session.add(run)
    session.flush()
    for sql in (
        "UPDATE protocol_runs SET instrument_id = NULL WHERE id = :id",
        "UPDATE protocol_runs SET started_at = started_at + interval '1 second' WHERE id = :id",
        "DELETE FROM protocol_runs WHERE id = :id",
    ):
        with pytest.raises(IntegrityError):
            with session.begin_nested():
                session.execute(text(sql), {"id": run.id})


def test_run_status_validation(session):
    with pytest.raises(ValueError):
        ProtocolRunStatus("SCHEDULED")
    with pytest.raises(StatementError):
        with session.begin_nested():
            session.add(ProtocolRun(protocol_name="review", status="SCHEDULED"))
            session.flush()
    with pytest.raises(DataError):
        with session.begin_nested():
            session.execute(text(
                "INSERT INTO protocol_runs (id, protocol_name, status) VALUES (:id, 'review', 'SCHEDULED')"
            ), {"id": uuid4()})


@pytest.mark.parametrize("status,completion", [
    (ProtocolRunStatus.RUNNING, INSTANT),
    (ProtocolRunStatus.COMPLETED, None),
    (ProtocolRunStatus.FAILED, INSTANT - timedelta(seconds=1)),
])
def test_run_completion_consistency(session, status, completion):
    session.add(ProtocolRun(protocol_name="review", status=status,
                            started_at=INSTANT, completed_at=completion))
    with pytest.raises(IntegrityError):
        session.flush()


@pytest.mark.parametrize("run_kind", ["none", "instrument", "portfolio"])
def test_artifact_reference_and_metadata(session, run_kind):
    item = asset()
    run = None if run_kind == "none" else ProtocolRun(
        protocol_name="review", instrument=item if run_kind == "instrument" else None,
        started_at=INSTANT,
    )
    metadata = {"sources": [{"identifier": "filing-1", "verified": True}], "language": "tr"}
    artifact = ResearchArtifact(
        instrument=item, protocol_run=run, artifact_type="source_register",
        path="research/HISTORY/2026-09-15/source-register.md", version="v1",
        artifact_metadata=metadata,
    )
    session.add(artifact)
    session.commit()
    identity = artifact.id
    session.expunge_all()
    stored = session.get(ResearchArtifact, identity)
    assert stored.path == "research/HISTORY/2026-09-15/source-register.md"
    assert stored.version == "v1"
    assert stored.artifact_metadata == metadata
    assert stored.instrument.research_artifacts == [stored]
    if run_kind == "none":
        assert stored.protocol_run is None
    else:
        assert stored.protocol_run.research_artifacts == [stored]


@pytest.mark.parametrize("operation", ["insert", "change_instrument", "change_run"])
def test_artifact_run_mismatch_rejected_in_database(session, operation):
    first, second = asset(), asset()
    run = ProtocolRun(instrument=first, protocol_name="review", started_at=INSTANT)
    session.add_all([run, second])
    session.flush()
    artifact = ResearchArtifact(
        instrument_id=first.id if operation == "change_instrument" else second.id,
        protocol_run_id=run.id if operation == "change_instrument" else None,
        artifact_type="report", path="research/example.md",
    )
    if operation != "insert":
        session.add(artifact)
        session.flush()
    with pytest.raises(IntegrityError) as error:
        with session.begin_nested():
            if operation == "insert":
                sql = "INSERT INTO research_artifacts (id, instrument_id, protocol_run_id, artifact_type, path) VALUES (:id, :instrument, :run, 'report', 'research/example.md')"
            elif operation == "change_instrument":
                sql = "UPDATE research_artifacts SET instrument_id = :instrument WHERE id = :id"
            else:
                sql = "UPDATE research_artifacts SET protocol_run_id = :run WHERE id = :id"
            session.execute(text(sql), {
                "id": artifact.id or uuid4(), "instrument": second.id, "run": run.id,
            })
    assert error.value.orig.sqlstate == "23514"
    assert error.value.orig.diag.constraint_name == "artifact_run_instrument_match"


def test_portfolio_run_accepts_multiple_instruments(session):
    run = ProtocolRun(protocol_name="portfolio_review", started_at=INSTANT)
    artifacts = [ResearchArtifact(instrument=asset(), protocol_run=run,
                                 artifact_type="report", path=f"research/example-{i}.md")
                 for i in range(2)]
    session.add_all(artifacts)
    session.commit()
    identity = run.id
    session.expunge_all()
    stored = session.get(ProtocolRun, identity)
    assert stored.instrument_id is None
    assert len({a.instrument_id for a in stored.research_artifacts}) == 2


def test_jsonb_replacement_assignment_persists(session):
    item = asset()
    run = ProtocolRun(instrument=item, protocol_name="review", machine_record={"stage": "initial"})
    artifact = ResearchArtifact(instrument=item, protocol_run=run, artifact_type="report",
                                path="research/example.md", artifact_metadata={"version": 1})
    plan = TechnicalPlan(instrument=item, reference_at=INSTANT,
                         **{field: [{"low": "10"}] for field in ZONE_FIELDS})
    session.add_all([artifact, plan])
    session.commit()
    run_id, artifact_id, plan_id = run.id, artifact.id, plan.id
    run.machine_record = {"stage": "updated", "nested": {"verified": True}}
    artifact.artifact_metadata = {"version": 2, "sources": ["filing"]}
    for field in ZONE_FIELDS:
        setattr(plan, field, [{"low": "20", "high": "25", "label": field}])
    session.commit()
    session.expunge_all()
    assert session.get(ProtocolRun, run_id).machine_record == {
        "stage": "updated", "nested": {"verified": True}
    }
    assert session.get(ResearchArtifact, artifact_id).artifact_metadata == {
        "version": 2, "sources": ["filing"]
    }
    stored = session.get(TechnicalPlan, plan_id)
    for field in ZONE_FIELDS:
        assert getattr(stored, field) == [{"low": "20", "high": "25", "label": field}]


def test_json_optionals_are_sql_null(session):
    item = asset()
    run = ProtocolRun(protocol_name="review", machine_record=None)
    artifact = ResearchArtifact(instrument=item, artifact_type="report", path="research/example.md", artifact_metadata=None)
    plan = TechnicalPlan(instrument=item, reference_at=INSTANT)
    session.add_all([run, artifact, plan])
    session.flush()
    for table, column, identity in (
        ("protocol_runs", "machine_record", run.id),
        ("research_artifacts", "metadata", artifact.id),
        *(("technical_plans", field, plan.id) for field in ZONE_FIELDS),
    ):
        assert session.scalar(text(f"SELECT {column} IS NULL FROM {table} WHERE id = :id"), {"id": identity})


def test_technical_plan_history_and_single_active_index(session):
    item = asset()
    zones = [{"low": "65.25", "high": "70.50", "note": "Example zone"}]
    old = TechnicalPlan(instrument=item, reference_at=INSTANT, active=True,
                        reference_price=Decimal("72.123456789012"), trend_expectation="range",
                        notes="Historical plan", **{field: zones for field in ZONE_FIELDS})
    next_plan = TechnicalPlan(instrument=item, reference_at=INSTANT + timedelta(days=1))
    session.add_all([old, next_plan])
    session.flush()
    assert next_plan.active is False
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            # Direct SQL proves the invariant doesn't depend on the ORM.
            session.execute(text("UPDATE technical_plans SET active = TRUE WHERE id = :id"), {"id": next_plan.id})
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            session.add(TechnicalPlan(instrument_id=item.id, reference_at=INSTANT, active=True))
            session.flush()
    old.active = False
    session.flush()  # Release the partial unique key before activating its replacement.
    next_plan.active = True
    other = TechnicalPlan(instrument=asset(), reference_at=INSTANT, active=True)
    session.add(other)
    session.commit()
    old_id, next_id, item_id = old.id, next_plan.id, item.id
    session.expunge_all()
    stored = session.get(TechnicalPlan, old_id)
    assert stored.active is False
    assert session.get(TechnicalPlan, next_id).active is True
    assert stored.reference_price == Decimal("72.123456789012")
    for field in ZONE_FIELDS:
        assert getattr(stored, field) == zones
    assert stored.notes == "Historical plan"
    assert len(session.get(Instrument, item_id).technical_plans) == 2


def test_technical_plan_delete_is_rejected(session):
    plan = TechnicalPlan(instrument=asset(), reference_at=INSTANT, active=False)
    session.add(plan)
    session.flush()
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            session.delete(plan)
            session.flush()


@pytest.mark.parametrize("kind", ["run", "artifact", "plan"])
@pytest.mark.parametrize("loaded", [False, True])
def test_history_prevents_instrument_deletion(session, kind, loaded):
    item = asset()
    if kind == "run":
        child = ProtocolRun(instrument=item, protocol_name="review")
        relation = "protocol_runs"
    elif kind == "artifact":
        child = ResearchArtifact(instrument=item, artifact_type="report", path="research/example.md")
        relation = "research_artifacts"
    else:
        child = TechnicalPlan(instrument=item, reference_at=INSTANT)
        relation = "technical_plans"
    session.add(child)
    session.commit()
    identity = item.id
    session.expunge_all()
    stored = session.get(Instrument, identity)
    assert relation in inspect(stored).unloaded
    if loaded:
        assert len(getattr(stored, relation)) == 1
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            session.delete(stored)
            session.flush()
    assert session.get(Instrument, identity) is not None


@pytest.mark.parametrize("kind", ["run", "artifact", "plan", "artifact_run"])
def test_missing_foreign_keys_rejected(session, kind):
    if kind == "run":
        child = ProtocolRun(instrument_id=uuid4(), protocol_name="review")
    elif kind == "artifact":
        child = ResearchArtifact(instrument_id=uuid4(), artifact_type="report", path="research/example.md")
    elif kind == "artifact_run":
        child = ResearchArtifact(instrument=asset(), protocol_run_id=uuid4(), artifact_type="report", path="research/example.md")
    else:
        child = TechnicalPlan(instrument_id=uuid4(), reference_at=INSTANT)
    session.add(child)
    with pytest.raises(IntegrityError):
        session.flush()


TIME_CASES = [
    (ProtocolRun, "started_at"), (ProtocolRun, "completed_at"), (ProtocolRun, "created_at"),
    (ResearchArtifact, "created_at"), (TechnicalPlan, "reference_at"),
    (TechnicalPlan, "created_at"), (TechnicalPlan, "updated_at"),
]


def timed_record(model):
    if model is ProtocolRun:
        return ProtocolRun(protocol_name="review", status=ProtocolRunStatus.COMPLETED,
                           started_at=INSTANT, completed_at=INSTANT)
    if model is ResearchArtifact:
        return ResearchArtifact(instrument=asset(), artifact_type="report", path="research/example.md")
    return TechnicalPlan(instrument=asset(), reference_at=INSTANT)


@pytest.mark.parametrize("model,field", TIME_CASES)
def test_new_datetime_fields_reject_naive(session, model, field):
    record = timed_record(model)
    setattr(record, field, INSTANT.replace(tzinfo=None))
    session.add(record)
    with pytest.raises(StatementError, match="Timezone-aware datetime required"):
        session.flush()


@pytest.mark.parametrize("model,field", TIME_CASES)
@pytest.mark.parametrize("offset", [3, -5])
def test_new_datetime_fields_roundtrip_utc(session, model, field, offset):
    record = timed_record(model)
    setattr(record, field, INSTANT.astimezone(timezone(timedelta(hours=offset))))
    session.add(record)
    session.commit()
    identity = record.id
    session.expunge_all()
    stored = session.get(model, identity)
    assert getattr(stored, field) == INSTANT
    assert getattr(stored, field).utcoffset() == timedelta(0)
    assert stored.created_at.utcoffset() == timedelta(0)


def test_consistency_migration_checks_legacy_data_and_preserves_it(isolated_history_engine, migration_config):
    with isolated_history_engine.begin() as connection:
        migration_config.attributes["connection"] = connection
        try:
            command.downgrade(migration_config, "0002")
            first, second, run_id, artifact_id = (uuid4() for _ in range(4))
            connection.execute(Instrument.__table__.insert(), [
                {"id": identity, "symbol": "LEGACY", "name": "Legacy", "instrument_type": "equity", "currency": "USD"}
                for identity in (first, second)
            ])
            connection.execute(ProtocolRun.__table__.insert().values(
                id=run_id, instrument_id=first, protocol_name="review"
            ))
            connection.execute(ResearchArtifact.__table__.insert().values(
                id=artifact_id, instrument_id=second, protocol_run_id=run_id,
                artifact_type="report", path="research/legacy.md"
            ))
            with pytest.raises(IntegrityError, match="Existing artifact/run instrument mismatch"):
                with connection.begin_nested():
                    command.upgrade(migration_config, "head")
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002"
            assert connection.scalar(text(
                "SELECT instrument_id FROM research_artifacts WHERE id = :id"
            ), {"id": artifact_id}) == second  # No silent history rewriting.
            connection.execute(text(
                "UPDATE research_artifacts SET instrument_id = :instrument WHERE id = :id"
            ), {"instrument": first, "id": artifact_id})
            command.upgrade(migration_config, "head")
            command.check(migration_config)
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0004"
            assert connection.scalar(text(
                "SELECT path FROM research_artifacts WHERE id = :id"
            ), {"id": artifact_id}) == "research/legacy.md"
            command.downgrade(migration_config, "0002")
            assert connection.scalar(text(
                "SELECT to_regprocedure('ii_check_artifact_run_instrument()')"
            )) is None
            assert connection.scalar(text(
                "SELECT instrument_id FROM research_artifacts WHERE id = :id"
            ), {"id": artifact_id}) == first
            command.upgrade(migration_config, "head")
        finally:
            migration_config.attributes.pop("connection", None)
