"""Real independent connections; no service layer or savepoint-only commits."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from queue import Queue
from threading import Event
from time import monotonic

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from investment_intelligence.models import Instrument, TechnicalPlan

pytestmark = pytest.mark.postgres


def seed_plans(engine, *, active=False):
    with Session(engine) as session:
        item = Instrument(symbol="RACE", name="Concurrency test", instrument_type="equity", currency="USD")
        first = TechnicalPlan(instrument=item, reference_at=datetime.now(timezone.utc), active=active)
        second = TechnicalPlan(instrument=item, reference_at=datetime.now(timezone.utc))
        session.add_all([first, second])
        session.flush()
        identities = item.id, first.id, second.id
        session.commit()
        return identities


def test_concurrent_activation_cannot_commit_two_active_plans(isolated_history_engine):
    engine = isolated_history_engine
    instrument_id, first_id, second_id = seed_plans(engine)
    second_pid = Queue()

    def activate_second():
        with Session(engine) as session:
            session.execute(text("SET LOCAL lock_timeout = '8s'"))
            session.execute(text("SET LOCAL statement_timeout = '10s'"))
            second_pid.put(session.scalar(text("SELECT pg_backend_pid()")))
            try:
                session.get(TechnicalPlan, second_id).active = True
                session.commit()
                return "committed"
            except IntegrityError as error:
                session.rollback()
                return error.orig.sqlstate

    with ThreadPoolExecutor(max_workers=1) as executor:
        with Session(engine) as first:
            first_pid = first.scalar(text("SELECT pg_backend_pid()"))
            first.get(TechnicalPlan, first_id).active = True
            first.flush()  # Hold the uncommitted unique-index entry.
            pending = executor.submit(activate_second)
            try:
                contender_pid = second_pid.get(timeout=5)
                assert contender_pid != first_pid
                # Observe real lock contention; thread scheduling alone is not proof.
                deadline = monotonic() + 5
                while True:
                    blockers = first.scalar(text("SELECT pg_blocking_pids(:pid)"), {"pid": contender_pid})
                    if first_pid in blockers:
                        break
                    assert monotonic() < deadline, "Second activation never waited on first transaction"
                    Event().wait(0.01)
                first.commit()
            finally:
                first.rollback()  # Release the lock even if an assertion fails.
            assert pending.result(timeout=10) == "23505"

    with Session(engine) as reader:
        active_ids = reader.scalars(select(TechnicalPlan.id).where(
            TechnicalPlan.instrument_id == instrument_id, TechnicalPlan.active.is_(True)
        )).all()
        assert active_ids == [first_id]
        assert reader.get(TechnicalPlan, second_id).active is False


def test_failed_activation_rolls_back_old_plan_deactivation(isolated_history_engine):
    engine = isolated_history_engine
    _, old_id, new_id = seed_plans(engine, active=True)
    with Session(engine) as writer:
        old = writer.get(TechnicalPlan, old_id)
        new = writer.get(TechnicalPlan, new_id)
        old.active = False
        writer.flush()
        # Another connection must still see the last committed active plan.
        with Session(engine) as reader:
            assert reader.get(TechnicalPlan, old_id).active is True
        new.active = True
        new.reference_at = None  # Invalid activation payload: genuine DB failure.
        with pytest.raises(IntegrityError) as error:
            writer.flush()
        assert error.value.orig.sqlstate == "23502"
        writer.rollback()  # Full transaction rollback, not a savepoint rollback.

    with Session(engine) as reader:
        assert reader.get(TechnicalPlan, old_id).active is True
        restored_new = reader.get(TechnicalPlan, new_id)
        assert restored_new.active is False
        assert restored_new.reference_at is not None
