"""Tests for Part 5A: Machine Record Validation & Explicit State Application Gate."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from investment_intelligence.enums import (
    ProtocolRunStatus,
    Recommendation,
    TechnicalStatus,
    ThesisStatus,
    ValuationStatus,
)
from investment_intelligence.records import IntelligenceStateRecord
from investment_intelligence.repositories import (
    InstrumentRepository,
    IntelligenceStateRepository,
    NotFoundError,
)
from investment_intelligence.services import ProtocolRunService
from investment_intelligence.state_application import (
    InvalidRunStateError,
    StaleProtocolRunError,
    StateApplicationPreview,
    StateApplicationService,
    UnapprovedStateApplicationError,
    apply_state_application,
    preview_state_application,
)
from investment_intelligence.validation import (
    MachineRecordValidationError,
    ThesisReviewRecord,
    UnsupportedProtocolError,
    validate_machine_record,
    validate_thesis_review_record,
)

pytestmark = pytest.mark.postgres

T1 = datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)
T3 = datetime(2026, 9, 20, 14, 0, tzinfo=timezone.utc)


# ============================================================================
# 1. Machine Record Validation Tests
# ============================================================================


def test_validate_thesis_review_record_success():
    """Verify valid Thesis Review machine record parsing and typing."""
    raw = {
        "thesis_status": "STRONGER",
        "recommendation": "ADD",
        "material_changes": ["Accelerating cloud revenue", "Operating margin expansion"],
        "open_questions": ["Hardware capex timeline"],
        "extra_untyped_field": {"arbitrary": 123},
    }
    validated = validate_thesis_review_record(raw)
    assert isinstance(validated, ThesisReviewRecord)
    assert validated.thesis_status == ThesisStatus.STRONGER
    assert validated.recommendation == Recommendation.ADD
    assert len(validated.material_changes) == 2
    assert validated.material_changes[0] == "Accelerating cloud revenue"
    assert validated.open_questions == ("Hardware capex timeline",)
    assert validated.raw_record["extra_untyped_field"] == {"arbitrary": 123}


def test_validate_thesis_review_record_minimal():
    """Verify Thesis Review machine record with only required fields."""
    raw = {
        "thesis_status": "UNCHANGED",
        "recommendation": "HOLD",
    }
    validated = validate_thesis_review_record(raw)
    assert validated.thesis_status == ThesisStatus.UNCHANGED
    assert validated.recommendation == Recommendation.HOLD
    assert validated.material_changes == ()
    assert validated.open_questions == ()


def test_validate_thesis_review_record_invalid_thesis_enum():
    """Verify rejection of invalid thesis_status."""
    with pytest.raises(MachineRecordValidationError, match="Invalid thesis_status 'STRONG_BUY'"):
        validate_thesis_review_record({
            "thesis_status": "STRONG_BUY",
            "recommendation": "HOLD",
        })


def test_validate_thesis_review_record_invalid_recommendation_enum():
    """Verify rejection of invalid recommendation."""
    with pytest.raises(MachineRecordValidationError, match="Invalid recommendation 'BUY'"):
        validate_thesis_review_record({
            "thesis_status": "STRONGER",
            "recommendation": "BUY",
        })


def test_validate_thesis_review_record_missing_required_fields():
    """Verify rejection of missing required fields."""
    with pytest.raises(MachineRecordValidationError, match="Missing required field 'thesis_status'"):
        validate_thesis_review_record({"recommendation": "HOLD"})

    with pytest.raises(MachineRecordValidationError, match="Missing required field 'recommendation'"):
        validate_thesis_review_record({"thesis_status": "UNCHANGED"})


def test_validate_thesis_review_record_invalid_list_types():
    """Verify rejection of non-list or non-string list elements."""
    with pytest.raises(MachineRecordValidationError, match="material_changes must be a list"):
        validate_thesis_review_record({
            "thesis_status": "UNCHANGED",
            "recommendation": "HOLD",
            "material_changes": "Not a list",
        })

    with pytest.raises(MachineRecordValidationError, match="All items in open_questions must be strings"):
        validate_thesis_review_record({
            "thesis_status": "UNCHANGED",
            "recommendation": "HOLD",
            "open_questions": ["Valid string", 12345],
        })


def test_validate_machine_record_dispatcher():
    """Verify dispatcher routes correctly and rejects unsupported protocols."""
    valid = validate_machine_record("thesis-review", {
        "thesis_status": "WEAKER",
        "recommendation": "REDUCE",
    })
    assert valid.thesis_status == ThesisStatus.WEAKER

    # Normalization check
    valid_normalized = validate_machine_record("THESIS_REVIEW", {
        "thesis_status": "INVALIDATED",
        "recommendation": "SELL",
    })
    assert valid_normalized.thesis_status == ThesisStatus.INVALIDATED

    with pytest.raises(UnsupportedProtocolError, match="does not have a Machine Record validator"):
        validate_machine_record("earnings-review", {"some": "data"})


# ============================================================================
# 2. Preview Tests
# ============================================================================


def test_preview_state_application(session: Session):
    """Verify preview accurately reports proposed mutations and does not alter DB."""
    inst_repo = InstrumentRepository(session)
    state_repo = IntelligenceStateRepository(session)
    protocol_svc = ProtocolRunService(session)

    with session.begin():
        inst = inst_repo.create(symbol="CRM", name="Salesforce", instrument_type="equity", currency="USD")
        state_repo.create_initial(inst.id)
        original_state = state_repo.update(
            inst.id,
            thesis_status=ThesisStatus.STRONGER,
            recommendation=Recommendation.ADD,
            valuation_status=ValuationStatus.ATTRACTIVE,
            technical_status=TechnicalStatus.ON_TRACK,
            last_review_at=T1,
        )

        run = protocol_svc.start("thesis-review", instrument_id=inst.id, started_at=T1)
        protocol_svc.complete(
            run.id,
            machine_record={
                "thesis_status": "UNCHANGED",
                "recommendation": "HOLD",
                "material_changes": ["Growth normalized"],
            },
            human_brief="Growth consistent with mature targets.",
            completed_at=T2,
        )

    preview = preview_state_application(session, run.id)
    assert isinstance(preview, StateApplicationPreview)
    assert preview.protocol_run_id == run.id
    assert preview.instrument_id == inst.id
    assert preview.protocol_name == "thesis-review"

    assert preview.current["thesis_status"] == "STRONGER"
    assert preview.current["recommendation"] == "ADD"

    assert preview.proposed["thesis_status"] == "UNCHANGED"
    assert preview.proposed["recommendation"] == "HOLD"

    assert preview.changes["thesis_status"] == {"from": "STRONGER", "to": "UNCHANGED"}
    assert preview.changes["recommendation"] == {"from": "ADD", "to": "HOLD"}

    assert preview.is_stale is False
    assert preview.has_changes is True

    # Ensure DB was NOT mutated by preview
    current_state = state_repo.get(inst.id)
    assert current_state.thesis_status == original_state.thesis_status
    assert current_state.recommendation == original_state.recommendation
    assert current_state.updated_at == original_state.updated_at


# ============================================================================
# 3. Explicit Apply Tests
# ============================================================================


def test_apply_state_application_success(session: Session):
    """Verify explicit application updates thesis, recommendation, and last_review_at."""
    inst_repo = InstrumentRepository(session)
    state_repo = IntelligenceStateRepository(session)
    protocol_svc = ProtocolRunService(session)

    with session.begin():
        inst = inst_repo.create(symbol="ORCL", name="Oracle Corp", instrument_type="equity", currency="USD")
        state_repo.create_initial(inst.id)
        original_state = state_repo.update(
            inst.id,
            thesis_status=ThesisStatus.UNCHANGED,
            recommendation=Recommendation.HOLD,
            valuation_status=ValuationStatus.FAIR,
            technical_status=TechnicalStatus.NEUTRAL,
            last_review_at=T1,
        )

        run = protocol_svc.start("thesis-review", instrument_id=inst.id, started_at=T1)
        protocol_svc.complete(
            run.id,
            machine_record={
                "thesis_status": "STRONGER",
                "recommendation": "ADD",
                "material_changes": ["Cloud infrastructure growth exceeded expectations"],
            },
            human_brief="Significant OCI acceleration.",
            completed_at=T2,
        )

    updated_state = apply_state_application(session, run.id, approved=True)

    assert isinstance(updated_state, IntelligenceStateRecord)
    assert updated_state.thesis_status == ThesisStatus.STRONGER
    assert updated_state.recommendation == Recommendation.ADD
    assert updated_state.last_review_at == T2

    # CRITICAL: valuation and technical dimensions must remain untouched
    assert updated_state.valuation_status == original_state.valuation_status
    assert updated_state.technical_status == original_state.technical_status

    # Verify directly from repository
    db_state = state_repo.get(inst.id)
    assert db_state.thesis_status == ThesisStatus.STRONGER
    assert db_state.recommendation == Recommendation.ADD
    assert db_state.last_review_at == T2
    assert db_state.valuation_status == ValuationStatus.FAIR
    assert db_state.technical_status == TechnicalStatus.NEUTRAL


def test_apply_without_approval_rejected(session: Session):
    """Verify state application fails if approved=True is not explicitly provided."""
    inst_repo = InstrumentRepository(session)
    state_repo = IntelligenceStateRepository(session)
    protocol_svc = ProtocolRunService(session)

    with session.begin():
        inst = inst_repo.create(symbol="ADBE", name="Adobe Inc", instrument_type="equity", currency="USD")
        state_repo.create_initial(inst.id)
        original_state = state_repo.update(
            inst.id,
            thesis_status=ThesisStatus.UNCHANGED,
            recommendation=Recommendation.HOLD,
            last_review_at=T1,
        )

        run = protocol_svc.start("thesis-review", instrument_id=inst.id, started_at=T1)
        protocol_svc.complete(
            run.id,
            machine_record={"thesis_status": "WEAKER", "recommendation": "REDUCE"},
            human_brief="Creative Cloud headwinds.",
            completed_at=T2,
        )

    service = StateApplicationService(session)

    # Calling without approved=True
    with pytest.raises(UnapprovedStateApplicationError, match="requires explicit approval"):
        service.apply(run.id)

    # Calling with approved=False
    with pytest.raises(UnapprovedStateApplicationError, match="requires explicit approval"):
        service.apply(run.id, approved=False)

    # State in DB must be untouched
    current_state = state_repo.get(inst.id)
    assert current_state.thesis_status == original_state.thesis_status
    assert current_state.recommendation == original_state.recommendation


# ============================================================================
# 4. Missing IntelligenceState Handling
# ============================================================================


def test_missing_intelligence_state_preview_and_apply(session: Session):
    """Verify handling when an instrument does not yet have an IntelligenceState row."""
    inst_repo = InstrumentRepository(session)
    state_repo = IntelligenceStateRepository(session)
    protocol_svc = ProtocolRunService(session)

    with session.begin():
        inst = inst_repo.create(symbol="SNOW", name="Snowflake Inc", instrument_type="equity", currency="USD")
        # Notice: IntelligenceState is NOT created!

        run = protocol_svc.start("thesis-review", instrument_id=inst.id, started_at=T1)
        protocol_svc.complete(
            run.id,
            machine_record={"thesis_status": "STRONGER", "recommendation": "ADD"},
            human_brief="Initial thesis confirmed.",
            completed_at=T1,
        )

    # 1. Preview with missing state
    preview = preview_state_application(session, run.id)
    assert preview.current["thesis_status"] is None
    assert preview.current["recommendation"] is None
    assert preview.proposed["thesis_status"] == "STRONGER"
    assert preview.proposed["recommendation"] == "ADD"

    # Confirm preview did NOT create state row
    assert state_repo.get(inst.id) is None

    # 2. Approved apply creates initial state and updates atomically
    applied_state = apply_state_application(session, run.id, approved=True)
    assert applied_state.instrument_id == inst.id
    assert applied_state.thesis_status == ThesisStatus.STRONGER
    assert applied_state.recommendation == Recommendation.ADD
    assert applied_state.last_review_at == T1
    assert applied_state.valuation_status is None
    assert applied_state.technical_status is None

    # Confirm in DB
    db_state = state_repo.get(inst.id)
    assert db_state is not None
    assert db_state.thesis_status == ThesisStatus.STRONGER


# ============================================================================
# 5. Stale Run Protection & Idempotency
# ============================================================================


def test_stale_run_cannot_overwrite_newer_state(session: Session):
    """Verify that an older run cannot overwrite a state that has a newer last_review_at."""
    inst_repo = InstrumentRepository(session)
    state_repo = IntelligenceStateRepository(session)
    protocol_svc = ProtocolRunService(session)

    with session.begin():
        inst = inst_repo.create(symbol="CSCO", name="Cisco Systems", instrument_type="equity", currency="USD")
        state_repo.create_initial(inst.id)

        # Older Run A (Sep 10)
        run_a = protocol_svc.start("thesis-review", instrument_id=inst.id, started_at=T1)
        protocol_svc.complete(
            run_a.id,
            machine_record={"thesis_status": "WEAKER", "recommendation": "REDUCE"},
            human_brief="Supply chain slowdown.",
            completed_at=T1,  # 2026-09-10
        )

        # Newer Run B (Sep 20)
        run_b = protocol_svc.start("thesis-review", instrument_id=inst.id, started_at=T3)
        protocol_svc.complete(
            run_b.id,
            machine_record={"thesis_status": "STRONGER", "recommendation": "ADD"},
            human_brief="AI networking demand surging.",
            completed_at=T3,  # 2026-09-20
        )

    # Apply Newer Run B first
    apply_state_application(session, run_b.id, approved=True)

    state_after_b = state_repo.get(inst.id)
    assert state_after_b.thesis_status == ThesisStatus.STRONGER
    assert state_after_b.last_review_at == T3

    # Now attempt to apply older Run A
    with pytest.raises(StaleProtocolRunError, match="older than current state last_review_at"):
        apply_state_application(session, run_a.id, approved=True)

    # State must remain the newer Run B's state!
    current_state = state_repo.get(inst.id)
    assert current_state.thesis_status == ThesisStatus.STRONGER
    assert current_state.recommendation == Recommendation.ADD
    assert current_state.last_review_at == T3


def test_idempotent_reapplication(session: Session):
    """Verify re-applying the identical run with same timestamp is an idempotent no-op."""
    inst_repo = InstrumentRepository(session)
    state_repo = IntelligenceStateRepository(session)
    protocol_svc = ProtocolRunService(session)

    with session.begin():
        inst = inst_repo.create(symbol="IBM", name="IBM Corp", instrument_type="equity", currency="USD")
        state_repo.create_initial(inst.id)

        run = protocol_svc.start("thesis-review", instrument_id=inst.id, started_at=T2)
        protocol_svc.complete(
            run.id,
            machine_record={"thesis_status": "UNCHANGED", "recommendation": "HOLD"},
            human_brief="Mainframe cycle steady.",
            completed_at=T2,
        )

    # First apply
    state1 = apply_state_application(session, run.id, approved=True)
    assert state1.thesis_status == ThesisStatus.UNCHANGED
    assert state1.last_review_at == T2

    # Second apply (idempotent re-apply)
    state2 = apply_state_application(session, run.id, approved=True)
    assert state2.thesis_status == ThesisStatus.UNCHANGED
    assert state2.last_review_at == T2
    assert state2.updated_at == state1.updated_at


# ============================================================================
# 6. Safety & Run Eligibility Rejections
# ============================================================================


def test_cannot_apply_running_or_failed_run(session: Session):
    """Verify RUNNING and FAILED runs are rejected by preview and apply."""
    inst_repo = InstrumentRepository(session)
    state_repo = IntelligenceStateRepository(session)
    protocol_svc = ProtocolRunService(session)

    with session.begin():
        inst = inst_repo.create(symbol="NFLX", name="Netflix Inc", instrument_type="equity", currency="USD")
        state_repo.create_initial(inst.id)

        running_run = protocol_svc.start("thesis-review", instrument_id=inst.id)
        failed_run = protocol_svc.start("thesis-review", instrument_id=inst.id)
        protocol_svc.fail(failed_run.id, reason="Simulated AI execution timeout")

    # RUNNING run rejection
    with pytest.raises(InvalidRunStateError, match="has status 'RUNNING'; only COMPLETED"):
        preview_state_application(session, running_run.id)

    with pytest.raises(InvalidRunStateError, match="has status 'RUNNING'; only COMPLETED"):
        apply_state_application(session, running_run.id, approved=True)

    # FAILED run rejection
    with pytest.raises(InvalidRunStateError, match="has status 'FAILED'; only COMPLETED"):
        preview_state_application(session, failed_run.id)

    with pytest.raises(InvalidRunStateError, match="has status 'FAILED'; only COMPLETED"):
        apply_state_application(session, failed_run.id, approved=True)


def test_cannot_apply_portfolio_level_run(session: Session):
    """Verify portfolio-level runs (instrument_id is None) are rejected."""
    protocol_svc = ProtocolRunService(session)

    with session.begin():
        run = protocol_svc.start("thesis-review", instrument_id=None, started_at=T1)
        protocol_svc.complete(
            run.id,
            machine_record={"thesis_status": "UNCHANGED", "recommendation": "HOLD"},
            human_brief="Portfolio review brief.",
            completed_at=T1,
        )

    with pytest.raises(InvalidRunStateError, match="portfolio-level; state application requires an instrument-level run"):
        apply_state_application(session, run.id, approved=True)


def test_cannot_apply_unsupported_protocol_run(session: Session):
    """Verify runs for other protocols are rejected."""
    inst_repo = InstrumentRepository(session)
    protocol_svc = ProtocolRunService(session)

    with session.begin():
        inst = inst_repo.create(symbol="DIS", name="Walt Disney Co", instrument_type="equity", currency="USD")
        run = protocol_svc.start("portfolio-fit", instrument_id=inst.id, started_at=T1)
        protocol_svc.complete(
            run.id,
            machine_record={"some": "record"},
            human_brief="Fit analysis.",
            completed_at=T1,
        )

    with pytest.raises(UnsupportedProtocolError, match="is not supported for state application"):
        apply_state_application(session, run.id, approved=True)


def test_cannot_apply_invalid_machine_record(session: Session):
    """Verify runs with invalid machine records cannot be applied."""
    inst_repo = InstrumentRepository(session)
    protocol_svc = ProtocolRunService(session)

    with session.begin():
        inst = inst_repo.create(symbol="INTC", name="Intel Corp", instrument_type="equity", currency="USD")
        run = protocol_svc.start("thesis-review", instrument_id=inst.id, started_at=T1)
        # Invalid: missing thesis_status
        protocol_svc.complete(
            run.id,
            machine_record={"recommendation": "HOLD"},
            human_brief="Incomplete record.",
            completed_at=T1,
        )

    with pytest.raises(MachineRecordValidationError, match="Missing required field 'thesis_status'"):
        apply_state_application(session, run.id, approved=True)


# ============================================================================
# 7. ProtocolRun History Immutability
# ============================================================================


def test_protocol_run_history_immutable_after_apply(session: Session):
    """Verify ProtocolRun record remains completely unmodified after state application."""
    inst_repo = InstrumentRepository(session)
    state_repo = IntelligenceStateRepository(session)
    protocol_svc = ProtocolRunService(session)

    with session.begin():
        inst = inst_repo.create(symbol="QCOM", name="Qualcomm Inc", instrument_type="equity", currency="USD")
        state_repo.create_initial(inst.id)

        original_machine_record = {
            "thesis_status": "STRONGER",
            "recommendation": "ADD",
            "material_changes": ["Handset recovery", "Automotive silicon share gains"],
            "open_questions": ["Custom CPU licensing"],
            "extra_raw_metric": 42,
        }
        run = protocol_svc.start("thesis-review", instrument_id=inst.id, started_at=T1)
        completed_run = protocol_svc.complete(
            run.id,
            machine_record=original_machine_record,
            human_brief="Strong automotive and handset catalysts.",
            confidence="HIGH",
            completed_at=T2,
        )

    # Apply state
    apply_state_application(session, run.id, approved=True)

    # Query the ProtocolRun directly and assert exact immutability
    post_apply_run = protocol_svc.get(run.id)
    assert post_apply_run is not None
    assert post_apply_run.id == completed_run.id
    assert post_apply_run.status == completed_run.status
    assert post_apply_run.started_at == completed_run.started_at
    assert post_apply_run.completed_at == completed_run.completed_at
    assert post_apply_run.confidence == completed_run.confidence
    assert post_apply_run.human_brief == completed_run.human_brief
    assert post_apply_run.machine_record == original_machine_record
