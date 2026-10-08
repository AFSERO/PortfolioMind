from datetime import datetime, timedelta, timezone, tzinfo
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import delete, inspect, select, text, update
from sqlalchemy.exc import DataError, IntegrityError, StatementError
from sqlalchemy.orm import Session

from investment_intelligence.enums import (
    Recommendation, TechnicalStatus, ThesisStatus, ValuationStatus,
)
from investment_intelligence.models import Instrument, IntelligenceState

pytestmark = pytest.mark.postgres


def instrument():
    return Instrument(symbol="TEST", name="Test Instrument", instrument_type="equity", currency="USD")


def test_instrument_create_read_without_position_or_state(session):
    item = instrument()
    session.add(item)
    session.commit()
    identity = item.id
    session.expunge_all()
    stored = session.get(Instrument, identity)
    assert (stored.symbol, stored.name, stored.instrument_type, stored.currency) == (
        "TEST", "Test Instrument", "equity", "USD"
    )
    assert stored.venue is None
    assert stored.intelligence_state is None
    assert stored.created_at.tzinfo is not None
    assert stored.updated_at.tzinfo is not None


def test_nullable_initial_state_and_relationship(session):
    item = instrument()
    item.intelligence_state = IntelligenceState()
    session.add(item)
    session.commit()
    identity = item.id
    session.expunge_all()
    state = session.get(IntelligenceState, identity)
    assert state.instrument.id == identity
    assert state.instrument.intelligence_state is state
    for field in ("thesis_status", "valuation_status", "technical_status", "recommendation",
                  "last_review_at", "last_monitoring_at", "next_review_at"):
        assert getattr(state, field) is None
    assert state.created_at.tzinfo is not None


def test_review_state_roundtrip_and_update_timestamp(session):
    item = instrument()
    review_at = datetime(2026, 9, 15, 10, 30, tzinfo=timezone.utc)
    item.intelligence_state = IntelligenceState(
        thesis_status=ThesisStatus.UNCHANGED, valuation_status=ValuationStatus.FAIR,
        technical_status=TechnicalStatus.ON_TRACK, recommendation=Recommendation.HOLD,
        last_review_at=review_at, last_monitoring_at=review_at, next_review_at=review_at,
    )
    session.add(item)
    session.commit()
    identity = item.id
    session.expunge_all()
    state = session.get(IntelligenceState, identity)
    assert state.thesis_status is ThesisStatus.UNCHANGED
    assert state.valuation_status is ValuationStatus.FAIR
    assert state.technical_status is TechnicalStatus.ON_TRACK
    assert state.recommendation is Recommendation.HOLD
    assert state.last_review_at == state.last_monitoring_at == state.next_review_at == review_at
    # Verify onupdate without sleeps or transaction-clock assumptions.
    old = datetime(2000, 1, 1, tzinfo=timezone.utc)
    state.updated_at = old
    session.commit()
    state.recommendation = Recommendation.REVIEW_REQUIRED
    session.commit()
    session.refresh(state)
    assert state.updated_at > old


@pytest.mark.parametrize("field,enum", [
    ("thesis_status", ThesisStatus), ("valuation_status", ValuationStatus),
    ("technical_status", TechnicalStatus), ("recommendation", Recommendation),
])
def test_enum_validation_in_python_orm_and_postgresql(session, field, enum):
    with pytest.raises(ValueError):
        enum("INVALID")
    item = instrument()
    item.intelligence_state = IntelligenceState()
    session.add(item)
    session.commit()
    identity = item.id
    for value in enum:
        setattr(item.intelligence_state, field, value)
        session.commit()
        session.refresh(item.intelligence_state)
        assert getattr(item.intelligence_state, field) is value
    with pytest.raises(StatementError):
        with session.begin_nested():
            setattr(item.intelligence_state, field, "INVALID")
            session.flush()
    with pytest.raises(DataError):
        with session.begin_nested():
            session.execute(text(
                f"UPDATE intelligence_states SET {field} = 'INVALID' WHERE instrument_id = :id"
            ), {"id": identity})


def test_state_requires_instrument_and_is_one_to_one(session):
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            session.add(IntelligenceState(instrument_id=uuid4()))
            session.flush()
    item = instrument()
    item.intelligence_state = IntelligenceState()
    session.add(item)
    session.commit()
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            session.execute(text(
                "INSERT INTO intelligence_states (instrument_id) VALUES (:id)"
            ), {"id": item.id})


def test_database_delete_cascades_to_current_state(session):
    item = instrument()
    item.intelligence_state = IntelligenceState()
    session.add(item)
    session.commit()
    identity = item.id
    session.execute(text("DELETE FROM instruments WHERE id = :id"), {"id": identity})
    session.commit()
    assert session.scalar(select(IntelligenceState.instrument_id).where(
        IntelligenceState.instrument_id == identity
    )) is None


def test_migration_roundtrip_and_metadata_match(pg_engine, migration_config):
    with pg_engine.begin() as connection:
        migration_config.attributes["connection"] = connection
        try:
            assert set(inspect(connection).get_table_names()) == {
                "alembic_version", "instruments", "intelligence_states",
                "protocol_runs", "research_artifacts", "technical_plans", "thesis_snapshots",
            }
            command.check(migration_config)
            command.downgrade(migration_config, "0001")
            assert set(inspect(connection).get_table_names()) == {
                "alembic_version", "instruments", "intelligence_states"
            }
            assert "protocol_run_status" not in {e["name"] for e in inspect(connection).get_enums()}
            for function in ("ii_guard_protocol_run()", "ii_preserve_technical_plan()",
                             "ii_check_artifact_run_instrument()", "ii_guard_thesis_snapshot()"):
                assert connection.scalar(text("SELECT to_regprocedure(:name)"), {"name": function}) is None
            # A populated Part 1 database upgrades without losing its current state.
            identity = uuid4()
            connection.execute(text(
                "INSERT INTO instruments (id, symbol, name, instrument_type, currency) "
                "VALUES (:id, 'UPGRADE', 'Existing asset', 'equity', 'USD')"
            ), {"id": identity})
            connection.execute(text(
                "INSERT INTO intelligence_states (instrument_id, recommendation) VALUES (:id, 'HOLD')"
            ), {"id": identity})
            command.upgrade(migration_config, "head")
            assert connection.scalar(text(
                "SELECT recommendation FROM intelligence_states WHERE instrument_id = :id"
            ), {"id": identity}) == "HOLD"
            command.check(migration_config)
            command.downgrade(migration_config, "base")
            assert set(inspect(connection).get_table_names()) == {"alembic_version"}
            assert inspect(connection).get_enums() == []
            command.upgrade(migration_config, "head")
            command.check(migration_config)
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0004"
        finally:
            migration_config.attributes.pop("connection", None)


class NoOffsetTimezone(tzinfo):
    def utcoffset(self, dt):
        return None


@pytest.mark.parametrize("field", [
    "last_review_at", "last_monitoring_at", "next_review_at", "created_at", "updated_at",
])
@pytest.mark.parametrize("zone", [None, NoOffsetTimezone()])
def test_naive_state_datetime_rejected_on_flush(session, field, zone):
    item = instrument()
    item.intelligence_state = IntelligenceState(**{
        field: datetime(2026, 9, 15, 12, tzinfo=zone)
    })
    session.add(item)
    with pytest.raises(StatementError, match="Timezone-aware datetime required"):
        session.flush()


@pytest.mark.parametrize("field", ["created_at", "updated_at"])
def test_naive_instrument_datetime_rejected(session, field):
    item = instrument()
    setattr(item, field, datetime(2026, 9, 15, 12))
    session.add(item)
    with pytest.raises(StatementError, match="Timezone-aware datetime required"):
        session.flush()


def test_typed_bulk_update_cannot_bypass_datetime_validation(session):
    item = instrument()
    item.intelligence_state = IntelligenceState()
    session.add(item)
    session.flush()
    with pytest.raises(StatementError, match="Timezone-aware datetime required"):
        session.execute(update(IntelligenceState).where(
            IntelligenceState.instrument_id == item.id
        ).values(next_review_at=datetime(2026, 9, 15, 12)))


@pytest.mark.parametrize("offset", [0, 3, -5])
def test_aware_datetime_roundtrip_preserves_instant_in_utc(session, offset):
    assert session.scalar(text("SHOW TIME ZONE")) == "UTC"
    instant = datetime(2026, 9, 15, 12, 30, tzinfo=timezone.utc)
    incoming = instant.astimezone(timezone(timedelta(hours=offset)))
    item = instrument()
    item.intelligence_state = IntelligenceState(
        last_review_at=incoming, last_monitoring_at=incoming, next_review_at=incoming
    )
    session.add(item)
    session.commit()
    identity = item.id
    session.expunge_all()
    stored = session.get(Instrument, identity)
    for field in ("last_review_at", "last_monitoring_at", "next_review_at"):
        actual = getattr(stored.intelligence_state, field)
        assert actual == instant
        assert actual.utcoffset() == timedelta(0)
    for obj in (stored, stored.intelligence_state):
        assert obj.created_at.utcoffset() == timedelta(0)
        assert obj.updated_at.utcoffset() == timedelta(0)


def test_real_commit_and_rollback_across_connections(pg_engine):
    committed_id, rolled_back_id = uuid4(), uuid4()
    try:
        with pg_engine.connect() as writer_connection, pg_engine.connect() as reader_connection:
            with Session(writer_connection) as writer, Session(reader_connection) as reader:
                item = instrument()
                item.id = committed_id
                item.intelligence_state = IntelligenceState()
                writer.add(item)
                writer.flush()
                assert reader.get(Instrument, committed_id) is None
                reader.rollback()
                writer.commit()
                assert reader.get(Instrument, committed_id) is not None
                assert reader.get(IntelligenceState, committed_id) is not None
                reader.rollback()

                discarded = instrument()
                discarded.id = rolled_back_id
                discarded.intelligence_state = IntelligenceState()
                writer.add(discarded)
                writer.flush()
                writer.rollback()
                assert reader.get(Instrument, rolled_back_id) is None
                assert reader.get(IntelligenceState, rolled_back_id) is None
    finally:
        # This test commits real data; remove only its own identities.
        with pg_engine.begin() as connection:
            connection.execute(delete(Instrument).where(
                Instrument.id.in_([committed_id, rolled_back_id])
            ))


@pytest.mark.parametrize("loaded", [False, True])
def test_orm_delete_cleans_current_state(session, loaded):
    item = instrument()
    item.intelligence_state = IntelligenceState()
    session.add(item)
    session.commit()
    identity = item.id
    session.expunge_all()
    stored = session.get(Instrument, identity)
    assert "intelligence_state" in inspect(stored).unloaded
    if loaded:
        assert stored.intelligence_state is not None
        assert "intelligence_state" not in inspect(stored).unloaded
    session.delete(stored)
    session.commit()
    session.expunge_all()
    assert session.get(Instrument, identity) is None
    assert session.get(IntelligenceState, identity) is None


def test_symbol_can_repeat_across_venues_and_types(session):
    items = [
        Instrument(symbol="SAME", name="Example", instrument_type=kind, venue=venue, currency="USD")
        for kind, venue in [("equity", "XNAS"), ("equity", "XNYS"), ("fund", "XNAS"), ("crypto", None)]
    ]
    session.add_all(items)
    session.commit()
    identities = {item.id for item in items}
    session.expunge_all()
    stored = session.scalars(select(Instrument).where(Instrument.id.in_(identities))).all()
    assert len(stored) == 4
    assert {item.symbol for item in stored} == {"SAME"}
