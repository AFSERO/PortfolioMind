"""Tests for Part 4C: Protocol Runner & AI Execution Contract."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from investment_intelligence.context import ContextBuilder
from investment_intelligence.enums import (
    ProtocolRunStatus,
    Recommendation,
    TechnicalStatus,
    ThesisStatus,
    ValuationStatus,
)
from investment_intelligence.execution import (
    AIExecutionError,
    AIExecutionRequest,
    AIExecutionResult,
    AIProvider,
    ProtocolRunExecution,
    ProtocolRunner,
    StaticAIProvider,
    run_asset_protocol,
)
from investment_intelligence.protocols import (
    ExecutionError,
    ProtocolDefinition,
    ProtocolNotFoundError,
    list_available_protocols,
    load_protocol,
)
from investment_intelligence.repositories import (
    InstrumentRepository,
    IntelligenceStateRepository,
    ResearchArtifactRepository,
)
from investment_intelligence.services import ProtocolRunService, TechnicalPlanService

pytestmark = pytest.mark.postgres
NOW = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)


# ============================================================================
# 1. Protocol Loader Tests
# ============================================================================


def test_load_protocol_success():
    """Verify loading an existing Markdown protocol by name."""
    proto = load_protocol("thesis-review")
    assert isinstance(proto, ProtocolDefinition)
    assert proto.canonical_name == "thesis-review"
    assert len(proto.content) > 0
    assert "thesis" in proto.content.lower() or "review" in proto.content.lower()
    assert proto.path.endswith("thesis-review.md")


def test_load_protocol_name_normalization():
    """Verify underscore normalization and case-insensitivity."""
    proto1 = load_protocol("thesis_review")
    proto2 = load_protocol("THESIS-REVIEW")
    proto3 = load_protocol("  thesis_review  ")
    assert proto1.canonical_name == "thesis-review"
    assert proto2.canonical_name == "thesis-review"
    assert proto3.canonical_name == "thesis-review"
    assert proto1.content == proto2.content == proto3.content


def test_load_protocol_not_found():
    """Verify ProtocolNotFoundError when protocol file does not exist."""
    with pytest.raises(ProtocolNotFoundError, match="not found"):
        load_protocol("non-existent-protocol-xyz")


@pytest.mark.parametrize(
    "invalid_name",
    [
        "",
        "   ",
        "../thesis-review",
        "../../etc/passwd",
        "protocols/thesis-review",
        "protocols\\thesis-review",
        "thesis\0review",
        "thesis;rm -rf",
        "thesis*review",
        "thesis$review",
    ],
)
def test_load_protocol_path_traversal_rejection(invalid_name):
    """Verify strict rejection of path traversal, separators, and special characters."""
    with pytest.raises(ProtocolNotFoundError):
        load_protocol(invalid_name)


def test_list_available_protocols():
    """Verify listing available protocols."""
    protos = list_available_protocols()
    assert isinstance(protos, list)
    assert len(protos) >= 5
    assert "thesis-review" in protos
    assert "deep-research" in protos
    assert "technical-review" in protos


def test_list_available_protocols_non_existent_dir(tmp_path):
    """Verify empty list when protocols directory does not exist."""
    missing_dir = tmp_path / "missing_subdir"
    assert list_available_protocols(missing_dir) == []


# ============================================================================
# 2. AI Execution Request & Result Validation
# ============================================================================


def test_ai_execution_request_json_serialization():
    """Verify AIExecutionRequest enforces JSON serializability."""
    valid_request = AIExecutionRequest(
        protocol_name="thesis-review",
        protocol_text="# Title",
        persistent_context={"instrument": {"symbol": "AAPL"}},
        supplemental_context={"notes": "Q3 earnings"},
        execution_metadata={"model": "test-model"},
    )
    assert valid_request.protocol_name == "thesis-review"

    # Non-serializable persistent_context
    with pytest.raises(ValueError, match="persistent_context must be JSON-serializable"):
        AIExecutionRequest(
            protocol_name="thesis-review",
            protocol_text="# Title",
            persistent_context={"bad_value": {1, 2, 3}},  # set is not JSON-serializable
        )

    # Non-serializable supplemental_context
    with pytest.raises(ValueError, match="supplemental_context must be JSON-serializable"):
        AIExecutionRequest(
            protocol_name="thesis-review",
            protocol_text="# Title",
            persistent_context={"valid": True},
            supplemental_context={"unserializable": object()},
        )

    # Non-serializable execution_metadata
    with pytest.raises(ValueError, match="execution_metadata must be JSON-serializable"):
        AIExecutionRequest(
            protocol_name="thesis-review",
            protocol_text="# Title",
            persistent_context={"valid": True},
            execution_metadata={"bad": object()},
        )


def test_ai_execution_result_validation():
    """Verify AIExecutionResult enforces dict machine_record and non-empty human_brief."""
    valid_result = AIExecutionResult(
        machine_record={"action": "HOLD", "score": 85},
        human_brief="Thesis holds up well.",
        confidence="HIGH",
    )
    assert valid_result.confidence == "HIGH"

    # Non-dict machine_record
    with pytest.raises(ValueError, match="machine_record must be a dictionary"):
        AIExecutionResult(
            machine_record="not a dict",  # type: ignore
            human_brief="Brief text",
        )

    # Non-serializable machine_record
    with pytest.raises(ValueError, match="machine_record must be JSON-serializable"):
        AIExecutionResult(
            machine_record={"bad": {1, 2}},
            human_brief="Brief text",
        )

    # Empty human_brief
    with pytest.raises(ValueError, match="human_brief must be non-empty text"):
        AIExecutionResult(
            machine_record={"action": "HOLD"},
            human_brief="",
        )

    with pytest.raises(ValueError, match="human_brief must be non-empty text"):
        AIExecutionResult(
            machine_record={"action": "HOLD"},
            human_brief="   \n\t  ",
        )


def test_static_ai_provider():
    """Verify StaticAIProvider records requests and yields deterministic output."""
    provider = StaticAIProvider()
    request = AIExecutionRequest(
        protocol_name="thesis-review",
        protocol_text="# Protocol",
        persistent_context={"symbol": "NVDA"},
    )
    result = provider.execute(request)
    assert isinstance(result, AIExecutionResult)
    assert len(provider.recorded_requests) == 1
    assert provider.recorded_requests[0].persistent_context["symbol"] == "NVDA"

    # Test failure simulation
    provider.simulate_failure()
    with pytest.raises(AIExecutionError, match="Simulated AI execution failure"):
        provider.execute(request)


# ============================================================================
# 3. Protocol Runner Integration Tests
# ============================================================================


def test_runner_successful_execution(session: Session):
    """Verify end-to-end execution: RUNNING -> COMPLETED, records persisted accurately."""
    inst_repo = InstrumentRepository(session)
    state_repo = IntelligenceStateRepository(session)

    with session.begin():
        inst = inst_repo.create(
            symbol="NVDA",
            name="Nvidia Corp.",
            instrument_type="equity",
            currency="USD",
            venue="NASDAQ",
        )
        state_repo.create_initial(inst.id)

    ai_result = AIExecutionResult(
        machine_record={"thesis_status": "STRONGER", "key_catalysts": ["Blackwell ramp"]},
        human_brief="Thesis remains exceptionally strong with ongoing AI datacenter demand.",
        confidence="HIGH",
    )
    ai_provider = StaticAIProvider(default_result=ai_result)
    runner = ProtocolRunner(session, ai_provider)

    execution = runner.run_asset_protocol(
        inst.id,
        "thesis-review",
        supplemental_context={"focus": "Datacenter revenue"},
        execution_metadata={"model": "test-deterministic-v1"},
    )

    # Unpack support
    run_rec, res = execution
    assert run_rec.id is not None
    assert run_rec.instrument_id == inst.id
    assert run_rec.protocol_name == "thesis-review"
    assert run_rec.status == ProtocolRunStatus.COMPLETED
    assert run_rec.machine_record == ai_result.machine_record
    assert run_rec.human_brief == ai_result.human_brief
    assert run_rec.confidence == "HIGH"
    assert run_rec.completed_at is not None
    assert run_rec.completed_at.tzinfo == timezone.utc
    assert run_rec.started_at <= run_rec.completed_at

    # Check request received by provider
    assert len(ai_provider.recorded_requests) == 1
    req = ai_provider.recorded_requests[0]
    assert req.protocol_name == "thesis-review"
    assert req.persistent_context["instrument"]["symbol"] == "NVDA"
    assert req.supplemental_context == {"focus": "Datacenter revenue"}
    assert req.execution_metadata == {"model": "test-deterministic-v1"}


def test_runner_transaction_boundary_isolation(session: Session):
    """Verify that during AI execution, no active DB transaction/lock is held."""
    inst_repo = InstrumentRepository(session)
    with session.begin():
        inst = inst_repo.create(
            symbol="MSFT",
            name="Microsoft Corp.",
            instrument_type="equity",
            currency="USD",
        )

    class TransactionSpyAIProvider(AIProvider):
        def __init__(self, target_session: Session):
            self.target_session = target_session
            self.transaction_was_active: bool | None = None

        def execute(self, request: AIExecutionRequest) -> AIExecutionResult:
            # In SQLAlchemy 2.0 with savepoint nesting, in_nested_transaction() is True
            # if a nested transaction block (savepoint) is active.
            self.transaction_was_active = self.target_session.in_nested_transaction()
            return AIExecutionResult(
                machine_record={"status": "verified"},
                human_brief="Boundary verified.",
                confidence="HIGH",
            )

    spy_provider = TransactionSpyAIProvider(session)
    runner = ProtocolRunner(session, spy_provider)

    execution = runner.run_asset_protocol(inst.id, "thesis-review")
    assert execution.run.status == ProtocolRunStatus.COMPLETED
    # The transaction block (savepoint) opened in Transaction 1 was committed before execute()
    assert spy_provider.transaction_was_active is False


def test_runner_ai_failure_handling(session: Session):
    """Verify failure path: RUNNING -> FAILED, sanitized human_brief, exception raised."""
    inst_repo = InstrumentRepository(session)
    protocol_svc = ProtocolRunService(session)

    with session.begin():
        inst = inst_repo.create(
            symbol="AMD",
            name="Advanced Micro Devices",
            instrument_type="equity",
            currency="USD",
        )

    failing_provider = StaticAIProvider(
        should_fail=True,
        failure_error=RuntimeError("Internal API key expired with token secret_xyz_123"),
    )
    runner = ProtocolRunner(session, failing_provider)

    with pytest.raises(AIExecutionError, match="AI execution failed: RuntimeError"):
        runner.run_asset_protocol(inst.id, "thesis-review")

    # Verify ProtocolRun record was persisted as FAILED with sanitized human_brief
    runs = protocol_svc.recent(instrument_id=inst.id)
    assert len(runs) == 1
    failed_run = runs[0]
    assert failed_run.status == ProtocolRunStatus.FAILED
    assert failed_run.completed_at is not None
    assert failed_run.completed_at >= failed_run.started_at
    # Sanitized reason: must NOT leak the sensitive internal token
    assert "secret_xyz_123" not in (failed_run.human_brief or "")
    assert failed_run.human_brief == "AI execution failed: RuntimeError"


def test_runner_prevalidation_rejection_no_db_pollution(session: Session):
    """Verify that invalid inputs fail before Transaction 1 starts (no RUNNING run left)."""
    inst_repo = InstrumentRepository(session)
    protocol_svc = ProtocolRunService(session)

    with session.begin():
        inst = inst_repo.create(
            symbol="INTC",
            name="Intel Corp.",
            instrument_type="equity",
            currency="USD",
        )

    ai_provider = StaticAIProvider()
    runner = ProtocolRunner(session, ai_provider)

    # 1. Invalid protocol name
    with pytest.raises(ProtocolNotFoundError):
        runner.run_asset_protocol(inst.id, "non_existent_protocol_foo_bar")

    # 2. Non-serializable supplemental context
    with pytest.raises(ValueError, match="supplemental_context must be JSON-serializable"):
        runner.run_asset_protocol(
            inst.id,
            "thesis-review",
            supplemental_context={"unserializable": {1, 2, 3}},
        )

    # Check that zero protocol runs were created
    runs = protocol_svc.recent(instrument_id=inst.id)
    assert len(runs) == 0


def test_runner_does_not_mutate_intelligence_state(session: Session):
    """CRITICAL INVARIANT: Protocol runs NEVER automatically mutate IntelligenceState."""
    inst_repo = InstrumentRepository(session)
    state_repo = IntelligenceStateRepository(session)

    with session.begin():
        inst = inst_repo.create(
            symbol="GOOGL",
            name="Alphabet Inc.",
            instrument_type="equity",
            currency="USD",
        )
        state_repo.create_initial(inst.id)
        original_state = state_repo.update(
            inst.id,
            thesis_status=ThesisStatus.UNCHANGED,
            recommendation=Recommendation.HOLD,
            valuation_status=ValuationStatus.FAIR,
            technical_status=TechnicalStatus.NEUTRAL,
            last_review_at=NOW,
        )

    # AI returns aggressive BUY and STRONGER
    ai_result = AIExecutionResult(
        machine_record={
            "recommendation": "STRONG_BUY",
            "thesis_status": "STRONGER",
            "action": "ADD_IMMEDIATELY",
        },
        human_brief="Upgrade recommendation to STRONG BUY.",
        confidence="HIGH",
    )
    ai_provider = StaticAIProvider(default_result=ai_result)
    runner = ProtocolRunner(session, ai_provider)

    runner.run_asset_protocol(inst.id, "thesis-review")

    # Query the state directly and verify it was NOT mutated
    current_state = state_repo.get(inst.id)
    assert current_state is not None
    assert current_state.recommendation == Recommendation.HOLD
    assert current_state.thesis_status == ThesisStatus.UNCHANGED
    assert current_state.valuation_status == ValuationStatus.FAIR
    assert current_state.technical_status == TechnicalStatus.NEUTRAL
    assert current_state.last_review_at == original_state.last_review_at
    assert current_state.updated_at == original_state.updated_at


def test_runner_instrument_data_isolation(session: Session):
    """Verify that context sent to AI is strictly isolated to target instrument."""
    inst_repo = InstrumentRepository(session)
    artifact_repo = ResearchArtifactRepository(session)
    protocol_svc = ProtocolRunService(session)

    with session.begin():
        inst_a = inst_repo.create(
            symbol="ALPHA",
            name="Alpha Corp",
            instrument_type="equity",
            currency="USD",
        )
        inst_b = inst_repo.create(
            symbol="BETA",
            name="Beta Corp",
            instrument_type="equity",
            currency="USD",
        )
        run_b = protocol_svc.start("thesis-review", instrument_id=inst_b.id)
        protocol_svc.complete(run_b.id, human_brief="Beta analysis")
        artifact_repo.create(
            instrument_id=inst_b.id,
            artifact_type="research_memo",
            path="beta.md",
            metadata={"title": "Confidential Beta Research"},
        )

    ai_provider = StaticAIProvider()
    runner = ProtocolRunner(session, ai_provider)

    runner.run_asset_protocol(inst_a.id, "thesis-review")

    req = ai_provider.recorded_requests[0]
    p_context = req.persistent_context
    assert p_context["instrument"]["symbol"] == "ALPHA"
    assert p_context["instrument"]["id"] == str(inst_a.id)

    # Ensure Beta data is completely absent from Alpha's context
    context_json = json.dumps(p_context)
    assert "BETA" not in context_json
    assert "Confidential Beta Research" not in context_json


def test_run_asset_protocol_convenience_function(session: Session):
    """Verify top-level run_asset_protocol helper function."""
    inst_repo = InstrumentRepository(session)
    with session.begin():
        inst = inst_repo.create(
            symbol="AMZN",
            name="Amazon.com Inc.",
            instrument_type="equity",
            currency="USD",
        )

    ai_provider = StaticAIProvider()
    execution = run_asset_protocol(
        session,
        inst.id,
        "thesis-review",
        ai_provider,
        supplemental_context={"memo": "Convenience function test"},
    )
    assert isinstance(execution, ProtocolRunExecution)
    assert execution.run.status == ProtocolRunStatus.COMPLETED
    assert execution.run.instrument_id == inst.id
    assert execution.result is not None
