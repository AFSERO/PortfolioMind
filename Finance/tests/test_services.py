"""Service and repository layer tests; exercises application persistence API."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from queue import Queue
from threading import Event
from time import monotonic
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from investment_intelligence.enums import (
    ProtocolRunStatus,
    Recommendation,
    TechnicalStatus,
    ThesisStatus,
    ValuationStatus,
)
from investment_intelligence.models import Instrument, TechnicalPlan
from investment_intelligence.records import (
    InstrumentRecord,
    IntelligenceStateRecord,
    ProtocolRunRecord,
    ResearchArtifactRecord,
    TechnicalPlanRecord,
)
from investment_intelligence.repositories import (
    ArtifactRunMismatchError,
    InstrumentNotFoundError,
    InstrumentRepository,
    IntelligenceStateRepository,
    NotFoundError,
    ResearchArtifactRepository,
    StateAlreadyExistsError,
)
from investment_intelligence.services import (
    InvalidProtocolLifecycleError,
    ProtocolRunService,
    TechnicalPlanActivationConflictError,
    TechnicalPlanService,
)

pytestmark = pytest.mark.postgres
NOW = datetime(2026, 9, 15, 15, 0, tzinfo=timezone.utc)


# ============================================================================
# 1. Instrument Repository Tests
# ============================================================================


def test_instrument_create_and_get(session):
    repo = InstrumentRepository(session)
    with session.begin():
        created = repo.create(
            symbol="MSFT",
            name="Microsoft Corporation",
            instrument_type="equity",
            currency="USD",
            venue="NASDAQ",
        )

    assert isinstance(created, InstrumentRecord)
    assert created.symbol == "MSFT"
    assert created.name == "Microsoft Corporation"
    assert created.instrument_type == "equity"
    assert created.currency == "USD"
    assert created.venue == "NASDAQ"
    assert created.created_at.tzinfo is not None
    assert created.updated_at.tzinfo is not None

    fetched = repo.get(created.id)
    assert fetched == created

    # Can also look up by record object with .id
    fetched_by_rec = repo.get(created)
    assert fetched_by_rec == created

    # Non-existent ID returns None
    assert repo.get(uuid4()) is None


def test_instrument_same_symbol_across_venues_and_types(session):
    repo = InstrumentRepository(session)
    with session.begin():
        inst1 = repo.create(
            symbol="ETH",
            name="Ethereum Spot",
            instrument_type="crypto",
            currency="USD",
            venue="BINANCE",
        )
        inst2 = repo.create(
            symbol="ETH",
            name="Ether ETF",
            instrument_type="etf",
            currency="USD",
            venue=None,
        )

    assert inst1.id != inst2.id
    assert inst1.symbol == inst2.symbol == "ETH"
    assert inst1.venue == "BINANCE"
    assert inst2.venue is None


def test_instrument_update_metadata_and_validation(session):
    repo = InstrumentRepository(session)
    with session.begin():
        inst = repo.create(
            symbol="GOOG",
            name="Google Inc",
            instrument_type="equity",
            currency="USD",
        )

    with session.begin():
        updated = repo.update(inst.id, name="Alphabet Inc.", venue="NASDAQ")

    assert updated.name == "Alphabet Inc."
    assert updated.venue == "NASDAQ"
    assert updated.updated_at >= inst.updated_at

    # Updating non-existent instrument raises InstrumentNotFoundError
    with pytest.raises(InstrumentNotFoundError):
        with session.begin():
            repo.update(uuid4(), name="Does not exist")

    # Disallowed attribute raises ValueError
    with pytest.raises(ValueError, match="metadata"):
        with session.begin():
            repo.update(inst.id, non_existent_column="xyz")

    # Empty text raises ValueError
    with pytest.raises(ValueError, match="name"):
        with session.begin():
            repo.update(inst.id, name="   ")


def test_instrument_list_and_filters(session):
    repo = InstrumentRepository(session)
    with session.begin():
        repo.create(symbol="AAPL", name="Apple Inc.", instrument_type="equity", currency="USD", venue="NASDAQ")
        repo.create(symbol="AMZN", name="Amazon.com Inc.", instrument_type="equity", currency="USD", venue="NASDAQ")
        repo.create(symbol="BTC", name="Bitcoin", instrument_type="crypto", currency="USD", venue=None)

    # Filter by symbol
    aapl_list = repo.list(symbol="AAPL")
    assert len(aapl_list) == 1
    assert aapl_list[0].symbol == "AAPL"

    # Filter by instrument_type
    crypto_list = repo.list(instrument_type="crypto")
    assert len(crypto_list) == 1
    assert crypto_list[0].symbol == "BTC"

    # Filter by venue is None
    no_venue_list = repo.list(venue=None)
    assert any(i.symbol == "BTC" for i in no_venue_list)

    # Filter by name icontains
    inc_list = repo.list(name="Amazon")
    assert len(inc_list) == 1
    assert inc_list[0].symbol == "AMZN"

    # Pagination validation
    with pytest.raises(ValueError):
        repo.list(limit=0)
    with pytest.raises(ValueError):
        repo.list(limit=250)
    with pytest.raises(ValueError):
        repo.list(offset=-1)


# ============================================================================
# 2. IntelligenceState Repository Tests
# ============================================================================


def test_intelligence_state_create_initial_and_get(session):
    inst_repo = InstrumentRepository(session)
    state_repo = IntelligenceStateRepository(session)

    with session.begin():
        inst = inst_repo.create(symbol="NVDA", name="NVIDIA", instrument_type="equity", currency="USD")
        state = state_repo.create_initial(inst.id)

    assert isinstance(state, IntelligenceStateRecord)
    assert state.instrument_id == inst.id
    assert state.thesis_status is None
    assert state.valuation_status is None
    assert state.technical_status is None
    assert state.recommendation is None
    assert state.last_review_at is None
    assert state.last_monitoring_at is None
    assert state.next_review_at is None
    assert state.created_at.tzinfo is not None

    fetched = state_repo.get(inst.id)
    assert fetched == state

    # Lookup using InstrumentRecord object directly
    fetched_by_obj = state_repo.get(inst)
    assert fetched_by_obj == state


def test_intelligence_state_duplicate_create_rejected(session):
    inst_repo = InstrumentRepository(session)
    state_repo = IntelligenceStateRepository(session)

    with session.begin():
        inst = inst_repo.create(symbol="AMD", name="Advanced Micro Devices", instrument_type="equity", currency="USD")
        state_repo.create_initial(inst.id)

    with pytest.raises(StateAlreadyExistsError):
        with session.begin():
            state_repo.create_initial(inst.id)


def test_intelligence_state_create_initial_missing_instrument(session):
    state_repo = IntelligenceStateRepository(session)
    with pytest.raises(InstrumentNotFoundError):
        with session.begin():
            state_repo.create_initial(uuid4())


def test_intelligence_state_explicit_update_persistence(session):
    inst_repo = InstrumentRepository(session)
    state_repo = IntelligenceStateRepository(session)

    with session.begin():
        inst = inst_repo.create(symbol="TSLA", name="Tesla Inc.", instrument_type="equity", currency="USD")
        state_repo.create_initial(inst.id)

    review_time = datetime(2026, 9, 15, 16, 30, tzinfo=timezone.utc)
    with session.begin():
        updated = state_repo.update(
            inst.id,
            thesis_status=ThesisStatus.STRONGER,
            valuation_status=ValuationStatus.ATTRACTIVE,
            technical_status=TechnicalStatus.ON_TRACK,
            recommendation=Recommendation.ADD,
            next_review_at=review_time,
        )

    assert updated.thesis_status is ThesisStatus.STRONGER
    assert updated.valuation_status is ValuationStatus.ATTRACTIVE
    assert updated.technical_status is TechnicalStatus.ON_TRACK
    assert updated.recommendation is Recommendation.ADD
    assert updated.next_review_at == review_time

    # Explicitly clearing a field with None
    with session.begin():
        cleared = state_repo.update(inst.id, recommendation=None)
    assert cleared.recommendation is None
    assert cleared.thesis_status is ThesisStatus.STRONGER

    # Updating non-existent state raises NotFoundError
    with pytest.raises(NotFoundError):
        with session.begin():
            state_repo.update(uuid4(), recommendation=Recommendation.HOLD)


def test_intelligence_state_mark_reviewed_and_monitored(session):
    inst_repo = InstrumentRepository(session)
    state_repo = IntelligenceStateRepository(session)

    with session.begin():
        inst = inst_repo.create(symbol="META", name="Meta Platforms", instrument_type="equity", currency="USD")
        state_repo.create_initial(inst.id)

    with session.begin():
        rev = state_repo.mark_reviewed(inst.id)
    assert rev.last_review_at is not None
    assert rev.last_review_at.tzinfo is not None

    with session.begin():
        mon = state_repo.mark_monitored(inst.id)
    assert mon.last_monitoring_at is not None
    assert mon.last_monitoring_at.tzinfo is not None


# ============================================================================
# 3. ProtocolRun Service Tests
# ============================================================================


def test_protocol_run_lifecycle_instrument_level(session):
    inst_repo = InstrumentRepository(session)
    protocol_svc = ProtocolRunService(session)

    with session.begin():
        inst = inst_repo.create(symbol="UBER", name="Uber Technologies", instrument_type="equity", currency="USD")
        run = protocol_svc.start("thesis_review", instrument_id=inst.id, started_at=NOW)

    assert isinstance(run, ProtocolRunRecord)
    assert run.protocol_name == "thesis_review"
    assert run.instrument_id == inst.id
    assert run.status is ProtocolRunStatus.RUNNING
    assert run.started_at == NOW
    assert run.completed_at is None

    # Complete the run
    done_time = datetime(2026, 9, 15, 15, 10, tzinfo=timezone.utc)
    machine_rec = {"thesis": "unchanged", "catalysts": ["autonomous rollout"]}
    with session.begin():
        completed = protocol_svc.complete(
            run.id,
            machine_record=machine_rec,
            human_brief="Thesis on track.",
            confidence="HIGH",
            completed_at=done_time,
        )

    assert completed.status is ProtocolRunStatus.COMPLETED
    assert completed.completed_at == done_time
    assert completed.machine_record == machine_rec
    assert completed.human_brief == "Thesis on track."
    assert completed.confidence == "HIGH"


def test_protocol_run_lifecycle_portfolio_level_and_fail(session):
    protocol_svc = ProtocolRunService(session)

    with session.begin():
        run = protocol_svc.start("portfolio_monitoring", instrument_id=None)

    assert run.instrument_id is None
    assert run.status is ProtocolRunStatus.RUNNING

    with session.begin():
        failed = protocol_svc.fail(run.id, reason="Provider timeout during calculation")

    assert failed.status is ProtocolRunStatus.FAILED
    assert failed.completed_at is not None
    assert failed.human_brief == "Provider timeout during calculation"


def test_protocol_run_terminal_runs_are_immutable(session):
    protocol_svc = ProtocolRunService(session)

    with session.begin():
        run = protocol_svc.start("screening")
        protocol_svc.complete(run.id, human_brief="Screening completed")

    # Cannot complete again
    with pytest.raises(InvalidProtocolLifecycleError):
        with session.begin():
            protocol_svc.complete(run.id, human_brief="Completed twice?")

    # Cannot fail a completed run
    with pytest.raises(InvalidProtocolLifecycleError):
        with session.begin():
            protocol_svc.fail(run.id, reason="Should not fail")


def test_protocol_run_start_missing_instrument(session):
    protocol_svc = ProtocolRunService(session)
    with pytest.raises(InstrumentNotFoundError):
        with session.begin():
            protocol_svc.start("test_protocol", instrument_id=uuid4())


def test_protocol_run_recent_listing_and_filtering(session):
    inst_repo = InstrumentRepository(session)
    protocol_svc = ProtocolRunService(session)

    with session.begin():
        inst1 = inst_repo.create(symbol="I1", name="Inst 1", instrument_type="equity", currency="USD")
        inst2 = inst_repo.create(symbol="I2", name="Inst 2", instrument_type="equity", currency="USD")

        r1 = protocol_svc.start("scan", instrument_id=inst1.id)
        r2 = protocol_svc.start("review", instrument_id=inst2.id)
        r3 = protocol_svc.start("global_scan", instrument_id=None)

    # Filter by specific instrument
    runs_i1 = protocol_svc.recent(instrument_id=inst1.id)
    assert len(runs_i1) == 1
    assert runs_i1[0].id == r1.id

    # Filter portfolio-level runs (instrument_id is None)
    portfolio_runs = protocol_svc.recent(instrument_id=None)
    assert any(r.id == r3.id for r in portfolio_runs)
    assert all(r.instrument_id is None for r in portfolio_runs)

    # Filter by protocol name
    scan_runs = protocol_svc.recent(protocol_name="scan")
    assert len(scan_runs) == 1
    assert scan_runs[0].id == r1.id


# ============================================================================
# 4. ResearchArtifact Repository Tests
# ============================================================================


def test_research_artifact_create_and_list(session):
    inst_repo = InstrumentRepository(session)
    protocol_svc = ProtocolRunService(session)
    artifact_repo = ResearchArtifactRepository(session)

    with session.begin():
        inst = inst_repo.create(symbol="CRM", name="Salesforce", instrument_type="equity", currency="USD")
        run = protocol_svc.start("deep_research", instrument_id=inst.id)
        meta = {"sections": ["thesis", "moat", "valuation"], "analyst": "codex"}
        artifact = artifact_repo.create(
            inst.id,
            artifact_type="research_report",
            path="research/CRM/2026-09-15/report.md",
            version="v1",
            protocol_run_id=run.id,
            metadata=meta,
        )

    assert isinstance(artifact, ResearchArtifactRecord)
    assert artifact.instrument_id == inst.id
    assert artifact.protocol_run_id == run.id
    assert artifact.artifact_type == "research_report"
    assert artifact.path == "research/CRM/2026-09-15/report.md"
    assert artifact.version == "v1"
    assert artifact.artifact_metadata == meta
    assert artifact.created_at.tzinfo is not None

    # Fetch by ID
    assert artifact_repo.get(artifact.id) == artifact

    # List for instrument
    inst_artifacts = artifact_repo.list_for_instrument(inst.id)
    assert len(inst_artifacts) == 1
    assert inst_artifacts[0].id == artifact.id

    # List for run
    run_artifacts = artifact_repo.list_for_run(run.id)
    assert len(run_artifacts) == 1
    assert run_artifacts[0].id == artifact.id


def test_research_artifact_instrument_level_mismatch_rejected(session):
    inst_repo = InstrumentRepository(session)
    protocol_svc = ProtocolRunService(session)
    artifact_repo = ResearchArtifactRepository(session)

    with session.begin():
        inst_a = inst_repo.create(symbol="AAA", name="Asset A", instrument_type="equity", currency="USD")
        inst_b = inst_repo.create(symbol="BBB", name="Asset B", instrument_type="equity", currency="USD")
        run_a = protocol_svc.start("run_a", instrument_id=inst_a.id)

    # Creating artifact for inst_b tied to run_a (which belongs to inst_a) must be rejected
    with pytest.raises(ArtifactRunMismatchError):
        with session.begin():
            artifact_repo.create(
                inst_b.id,
                artifact_type="memo",
                path="research/BBB/memo.md",
                protocol_run_id=run_a.id,
            )


def test_research_artifact_portfolio_run_allows_different_instruments(session):
    inst_repo = InstrumentRepository(session)
    protocol_svc = ProtocolRunService(session)
    artifact_repo = ResearchArtifactRepository(session)

    with session.begin():
        inst_a = inst_repo.create(symbol="PAAA", name="Portfolio Asset A", instrument_type="equity", currency="USD")
        inst_b = inst_repo.create(symbol="PBBB", name="Portfolio Asset B", instrument_type="equity", currency="USD")
        portfolio_run = protocol_svc.start("portfolio_overview", instrument_id=None)

        art_a = artifact_repo.create(
            inst_a.id,
            artifact_type="memo",
            path="research/PAAA/memo.md",
            protocol_run_id=portfolio_run.id,
        )
        art_b = artifact_repo.create(
            inst_b.id,
            artifact_type="memo",
            path="research/PBBB/memo.md",
            protocol_run_id=portfolio_run.id,
        )

    assert art_a.protocol_run_id == portfolio_run.id
    assert art_b.protocol_run_id == portfolio_run.id
    run_artifacts = artifact_repo.list_for_run(portfolio_run.id)
    assert len(run_artifacts) == 2


def test_research_artifact_metadata_deepcopy_isolation(session):
    inst_repo = InstrumentRepository(session)
    artifact_repo = ResearchArtifactRepository(session)

    metadata_input = {"tags": ["growth", "ai"], "params": {"p": 1}}
    with session.begin():
        inst = inst_repo.create(symbol="ISOL", name="Isolation Test", instrument_type="equity", currency="USD")
        art = artifact_repo.create(
            inst.id,
            artifact_type="data",
            path="research/ISOL/data.json",
            metadata=metadata_input,
        )

    # Mutate the original dictionary in Python
    metadata_input["tags"].append("mutated")
    metadata_input["params"]["p"] = 999

    stored = artifact_repo.get(art.id)
    assert stored.artifact_metadata == {"tags": ["growth", "ai"], "params": {"p": 1}}


# ============================================================================
# 5. TechnicalPlan Service Tests
# ============================================================================


def test_technical_plan_lifecycle_and_atomic_switch(session):
    inst_repo = InstrumentRepository(session)
    plan_svc = TechnicalPlanService(session)

    with session.begin():
        inst = inst_repo.create(symbol="PLTR", name="Palantir", instrument_type="equity", currency="USD")
        assert plan_svc.get_active_technical_plan(inst.id) is None

        # 1. Create inactive plan 1
        p1 = plan_svc.create_inactive(
            inst.id,
            reference_at=NOW,
            reference_price=Decimal("25.50"),
            trend_expectation="Bullish breakout",
            entry_zones=[{"low": "24.0", "high": "25.0"}],
            support_zones=[{"level": "23.5"}],
            resistance_zones=[{"level": "28.0"}],
            notes="Initial plan",
        )

        assert isinstance(p1, TechnicalPlanRecord)
        assert p1.active is False
        assert plan_svc.get_active_technical_plan(inst.id) is None

        # 2. Activate plan 1
        act1 = plan_svc.activate_technical_plan(p1.id)
        assert act1.active is True
        current_active = plan_svc.get_active_technical_plan(inst.id)
        assert current_active is not None
        assert current_active.id == p1.id
        assert current_active.active is True

        # 3. Create inactive plan 2 (New analysis -> new plan row)
        plan2_time = datetime(2026, 9, 15, 17, 0, tzinfo=timezone.utc)
        p2 = plan_svc.create_inactive(
            inst.id,
            reference_at=plan2_time,
            reference_price=Decimal("27.80"),
            trend_expectation="Consolidation above resistance",
            notes="Updated plan",
        )
        assert p2.active is False
        # Plan 1 remains active until plan 2 is explicitly activated
        assert plan_svc.get_active_technical_plan(inst.id).id == p1.id

        # 4. Activate plan 2: atomic switch (p1 -> inactive, p2 -> active)
        act2 = plan_svc.activate_technical_plan(p2.id)
        assert act2.active is True
        new_active = plan_svc.get_active_technical_plan(inst.id)
        assert new_active.id == p2.id
        assert new_active.active is True

        # Old plan is now inactive
        old_p1 = plan_svc.get(p1.id)
        assert old_p1.active is False

        # 5. Plan history preserved
        history = plan_svc.list_history(inst.id)
        assert len(history) == 2
        assert history[0].id == p2.id  # Ordered by reference_at desc
        assert history[1].id == p1.id
        assert history[0].active is True
        assert history[1].active is False

    # Verify visible outside transaction
    active_after = plan_svc.get_active_technical_plan(inst.id)
    assert active_after is not None
    assert active_after.id == p2.id


def test_technical_plan_activate_already_active_is_safe(session):
    inst_repo = InstrumentRepository(session)
    plan_svc = TechnicalPlanService(session)

    with session.begin():
        inst = inst_repo.create(symbol="SNOW", name="Snowflake", instrument_type="equity", currency="USD")
        plan = plan_svc.create_inactive(inst.id, reference_at=NOW)
        plan_svc.activate_technical_plan(plan.id)

    with session.begin():
        reactivated = plan_svc.activate_technical_plan(plan.id)

    assert reactivated.active is True
    assert plan_svc.get_active_technical_plan(inst.id).id == plan.id


def test_technical_plan_activate_missing_plan_raises(session):
    plan_svc = TechnicalPlanService(session)
    with pytest.raises(NotFoundError):
        with session.begin():
            plan_svc.activate_technical_plan(uuid4())


def test_technical_plan_failed_activation_rollback(isolated_history_engine):
    """When a transaction fails during/after activation, the previous active plan remains active."""
    engine = isolated_history_engine
    with Session(engine) as session:
        inst_repo = InstrumentRepository(session)
        plan_svc = TechnicalPlanService(session)
        with session.begin():
            inst = inst_repo.create(symbol="ROLL", name="Rollback Test", instrument_type="equity", currency="USD")
            p1 = plan_svc.create_inactive(inst.id, reference_at=NOW)
            plan_svc.activate_technical_plan(p1.id)
            p2 = plan_svc.create_inactive(inst.id, reference_at=NOW)
        inst_id, p1_id, p2_id = inst.id, p1.id, p2.id

    with Session(engine) as session:
        plan_svc = TechnicalPlanService(session)
        with pytest.raises(RuntimeError, match="Simulated caller failure"):
            with session.begin():
                plan_svc.activate_technical_plan(p2_id)
                raise RuntimeError("Simulated caller failure after activation before commit")

    # Verify that p1 remains active and p2 remains inactive
    with Session(engine) as session:
        plan_svc = TechnicalPlanService(session)
        active = plan_svc.get_active_technical_plan(inst_id)
        assert active.id == p1_id
        assert active.active is True
        assert plan_svc.get(p2_id).active is False


def test_technical_plan_concurrent_activation_conflict(isolated_history_engine):
    """Concurrent activation across two separate DB connections triggers conflict error."""
    engine = isolated_history_engine
    with Session(engine) as session:
        inst_repo = InstrumentRepository(session)
        plan_svc = TechnicalPlanService(session)
        with session.begin():
            inst = inst_repo.create(symbol="CONC", name="Concurrency Test", instrument_type="equity", currency="USD")
            p1 = plan_svc.create_inactive(inst.id, reference_at=NOW)
            p2 = plan_svc.create_inactive(inst.id, reference_at=NOW)
        inst_id, p1_id, p2_id = inst.id, p1.id, p2.id

    second_pid = Queue()

    def activate_p2():
        with Session(engine) as s2:
            s2.execute(text("SET LOCAL lock_timeout = '8s'"))
            s2.execute(text("SET LOCAL statement_timeout = '10s'"))
            second_pid.put(s2.scalar(text("SELECT pg_backend_pid()")))
            svc2 = TechnicalPlanService(s2)
            try:
                svc2.activate_technical_plan(p2_id)
                s2.commit()
                return "committed"
            except TechnicalPlanActivationConflictError:
                s2.rollback()
                return "conflict_detected"

    with ThreadPoolExecutor(max_workers=1) as executor:
        with Session(engine) as s1:
            s1.begin()
            s1_pid = s1.scalar(text("SELECT pg_backend_pid()"))
            svc1 = TechnicalPlanService(s1)
            svc1.activate_technical_plan(p1_id)

            pending = executor.submit(activate_p2)
            try:
                p2_worker_pid = second_pid.get(timeout=5)
                assert p2_worker_pid != s1_pid

                # Wait until s2 blocks waiting for s1's index entry/locks
                deadline = monotonic() + 5
                while True:
                    blockers = s1.scalar(text("SELECT pg_blocking_pids(:pid)"), {"pid": p2_worker_pid})
                    if s1_pid in blockers:
                        break
                    assert monotonic() < deadline, "Contender never blocked on first transaction"
                    Event().wait(0.01)

                s1.commit()
            except Exception:
                s1.rollback()
                raise

            assert pending.result(timeout=10) == "conflict_detected"

    # Only p1 is active
    with Session(engine) as reader:
        svc = TechnicalPlanService(reader)
        active = svc.get_active_technical_plan(inst_id)
        assert active.id == p1_id
        assert active.active is True
        assert svc.get(p2_id).active is False


# ============================================================================
# 6. Transaction Contract & Boundary Tests
# ============================================================================


def test_transaction_success_commits(session):
    repo = InstrumentRepository(session)
    with session.begin():
        inst = repo.create(symbol="TX1", name="Tx Success", instrument_type="equity", currency="USD")
        identity = inst.id

    # Verify visible
    fetched = repo.get(identity)
    assert fetched is not None
    assert fetched.symbol == "TX1"


def test_transaction_failure_rolls_back_partial_mutations(session):
    repo = InstrumentRepository(session)
    state_repo = IntelligenceStateRepository(session)

    inst_id = None
    with pytest.raises(ValueError, match="Intentional failure"):
        with session.begin():
            inst = repo.create(symbol="TXFAIL", name="Tx Fail", instrument_type="equity", currency="USD")
            inst_id = inst.id
            state_repo.create_initial(inst.id)
            raise ValueError("Intentional failure before commit")

    assert inst_id is not None
    assert repo.get(inst_id) is None


def test_savepoint_isolation_preserves_earlier_work_in_same_transaction(session):
    inst_repo = InstrumentRepository(session)
    state_repo = IntelligenceStateRepository(session)

    with session.begin():
        # 1. Valid operation
        inst = inst_repo.create(symbol="SP1", name="Savepoint Test", instrument_type="equity", currency="USD")
        state_repo.create_initial(inst.id)

        # 2. Invalid operation handled gracefully by caller
        try:
            state_repo.create_initial(inst.id)  # Will fail with StateAlreadyExistsError
        except StateAlreadyExistsError:
            pass  # Handled: savepoint rolled back, outer transaction remains healthy

        # 3. Another valid operation in the same transaction
        updated = state_repo.update(inst.id, recommendation=Recommendation.ADD)

    # Outer transaction committed successfully
    assert updated.recommendation is Recommendation.ADD
    assert inst_repo.get(inst.id) is not None


def test_write_outside_transaction_raises_value_error(pg_engine):
    """Calling write methods without caller-owned transaction (session.begin) is rejected."""
    with Session(pg_engine) as session:
        repo = InstrumentRepository(session)
        with pytest.raises(ValueError, match="Writes require a caller-owned transaction"):
            repo.create(symbol="NOTX", name="No Tx", instrument_type="equity", currency="USD")


def test_dirty_session_raises_value_error(session):
    """Un-flushed raw ORM changes trigger session purity check."""
    raw_orm = Instrument(symbol="RAW", name="Raw ORM", instrument_type="equity", currency="USD")
    session.add(raw_orm)  # Raw un-flushed ORM mutation

    repo = InstrumentRepository(session)
    with pytest.raises(ValueError, match="clean Session"):
        repo.get(uuid4())
