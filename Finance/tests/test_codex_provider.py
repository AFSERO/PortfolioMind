"""Tests for Part 5B: Real Codex CLI AI Provider adapter."""

import json
from pathlib import Path
import subprocess
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from investment_intelligence.codex_provider import (
    CodexCLIProvider,
    _extract_json_object,
    _kill_process_tree,
    _resolve_codex_executable,
    is_deep_research_protocol,
    resolve_protocol_timeout,
)
from investment_intelligence.enums import (
    ProtocolRunStatus,
    Recommendation,
    ThesisStatus,
)
from investment_intelligence.execution import (
    AIExecutionError,
    AIExecutionRequest,
    AIExecutionResult,
    ProtocolRunner,
)
from investment_intelligence.repositories import (
    InstrumentRepository,
    IntelligenceStateRepository,
)

pytestmark = pytest.mark.postgres


@pytest.fixture
def sample_request() -> AIExecutionRequest:
    return AIExecutionRequest(
        protocol_name="thesis-review",
        protocol_text="# Thesis Review Protocol\nAnalyze whether thesis holds.",
        persistent_context={
            "instrument": {"symbol": "MSFT", "name": "Microsoft Corp."},
            "intelligence_state": {"thesis_status": "UNCHANGED", "recommendation": "HOLD"},
        },
        supplemental_context={
            "market": {"status": "available", "current_quote": {"price": 425.0}},
            "recent_news": [{"title": "Cloud growth solid"}],
            "portfolio_position": {"quantity": 50},
        },
        execution_metadata={"workflow": "thesis-review"},
    )


# ============================================================================
# 1. Prompt and JSON Extraction Tests
# ============================================================================


def test_extract_json_object_variants():
    """Verify robust extraction of JSON from code fences or surrounding text."""
    # 1. Clean JSON
    assert _extract_json_object('{"a": 1}') == '{"a": 1}'

    # 2. Markdown fences
    fenced = "```json\n{\n  \"thesis_status\": \"UNCHANGED\"\n}\n```"
    assert json.loads(_extract_json_object(fenced)) == {"thesis_status": "UNCHANGED"}

    # 3. Surrounding prose
    prose = "Here is the completed analysis:\n{\"recommendation\": \"HOLD\"}\nHope this helps!"
    assert json.loads(_extract_json_object(prose)) == {"recommendation": "HOLD"}


def test_build_prompt_structure(sample_request):
    """Verify build_prompt organizes protocol, context, and output requirements clearly."""
    provider = CodexCLIProvider(executable="codex", cwd=Path.cwd())
    prompt = provider.build_prompt(sample_request)

    assert "=== PROTOCOL INSTRUCTIONS ===" in prompt
    assert "thesis-review" in prompt
    assert "=== PERSISTENT ASSET CONTEXT ===" in prompt
    assert "MSFT" in prompt
    assert "=== SUPPLEMENTAL CONTEXT ===" in prompt
    assert "Cloud growth solid" in prompt
    assert "=== OUTPUT REQUIREMENTS ===" in prompt
    assert "machine_record" in prompt
    assert "human_brief" in prompt


# ============================================================================
# 2. Mocked Process Execution Tests
# ============================================================================


def test_codex_provider_success(sample_request):
    """Verify successful Codex CLI execution with structured output in output file."""
    valid_output = {
        "machine_record": {
            "thesis_status": "STRONGER",
            "recommendation": "ADD",
            "material_changes": ["Accelerating Azure AI adoption"],
            "open_questions": [],
        },
        "human_brief": "Thesis güçlendi. Bulut büyümesi beklentileri aştı.",
        "confidence": "HIGH",
    }

    provider = CodexCLIProvider(executable="codex", cwd=Path.cwd())

    def fake_subprocess_run(cmd, **kwargs):
        # Verify safe command invocation
        assert kwargs["shell"] is False
        assert kwargs["cwd"] == str(provider.cwd)
        assert cmd[-1] == "-"  # prompt passed via stdin
        assert "-o" in cmd
        out_file_idx = cmd.index("-o") + 1
        out_file_path = Path(cmd[out_file_idx])

        # Write model output directly to designated output file
        out_file_path.write_text(json.dumps(valid_output), encoding="utf-8")

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Codex banner and token usage info"
        mock_proc.stderr = ""
        return mock_proc

    with patch("subprocess.run", side_effect=fake_subprocess_run):
        result = provider.execute(sample_request)

    assert isinstance(result, AIExecutionResult)
    assert result.machine_record["thesis_status"] == "STRONGER"
    assert result.machine_record["recommendation"] == "ADD"
    assert result.human_brief == "Thesis güçlendi. Bulut büyümesi beklentileri aştı."
    assert result.confidence == "HIGH"


def test_codex_provider_fallback_to_stdout(sample_request):
    """Verify fallback to stdout if output file was empty but stdout had valid JSON."""
    valid_output = {
        "machine_record": {"thesis_status": "UNCHANGED", "recommendation": "HOLD"},
        "human_brief": "Değişiklik yok.",
        "confidence": "MEDIUM",
    }

    provider = CodexCLIProvider(executable="codex", cwd=Path.cwd())

    def fake_subprocess_run(cmd, **kwargs):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = f"```json\n{json.dumps(valid_output)}\n```"
        mock_proc.stderr = ""
        return mock_proc

    with patch("subprocess.run", side_effect=fake_subprocess_run):
        result = provider.execute(sample_request)

    assert result.machine_record["thesis_status"] == "UNCHANGED"
    assert result.human_brief == "Değişiklik yok."


def test_codex_provider_non_zero_exit_raises_error(sample_request):
    """Verify non-zero exit code raises sanitized AIExecutionError without leaking sensitive stderr."""
    provider = CodexCLIProvider(executable="codex", cwd=Path.cwd())

    def fake_subprocess_run(cmd, **kwargs):
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        mock_proc.stderr = "Fatal error: token sk-secret-12345 expired at /internal/auth/path"
        return mock_proc

    with patch("subprocess.run", side_effect=fake_subprocess_run):
        with pytest.raises(AIExecutionError, match="failed with exit code 1") as exc_info:
            provider.execute(sample_request)

    # Sanitize check: sensitive token from stderr must NOT leak into error message
    assert "sk-secret-12345" not in str(exc_info.value)


def test_codex_provider_timeout_raises_error(sample_request):
    """Verify process timeout terminates and raises AIExecutionError."""
    provider = CodexCLIProvider(executable="codex", timeout=30.0, cwd=Path.cwd())

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="codex", timeout=30.0)):
        with pytest.raises(AIExecutionError, match="timed out after 30.0 seconds"):
            provider.execute(sample_request)


def test_codex_provider_malformed_json_raises_error(sample_request):
    """Verify invalid JSON response raises AIExecutionError."""
    provider = CodexCLIProvider(executable="codex", cwd=Path.cwd())

    def fake_subprocess_run(cmd, **kwargs):
        out_file_idx = cmd.index("-o") + 1
        Path(cmd[out_file_idx]).write_text("Not JSON at all, just plain english text.", encoding="utf-8")
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""
        return mock_proc

    with patch("subprocess.run", side_effect=fake_subprocess_run):
        with pytest.raises(AIExecutionError, match="could not be parsed as JSON"):
            provider.execute(sample_request)


def test_codex_provider_missing_fields_raises_error(sample_request):
    """Verify missing required fields in JSON output raises AIExecutionError."""
    provider = CodexCLIProvider(executable="codex", cwd=Path.cwd())

    # Missing human_brief
    def fake_missing_brief(cmd, **kwargs):
        out_file_idx = cmd.index("-o") + 1
        Path(cmd[out_file_idx]).write_text(json.dumps({"machine_record": {"status": "ok"}}), encoding="utf-8")
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        return mock_proc

    with patch("subprocess.run", side_effect=fake_missing_brief):
        with pytest.raises(AIExecutionError, match="missing required non-empty string field 'human_brief'"):
            provider.execute(sample_request)

    # Missing machine_record
    def fake_missing_record(cmd, **kwargs):
        out_file_idx = cmd.index("-o") + 1
        Path(cmd[out_file_idx]).write_text(json.dumps({"human_brief": "Valid brief"}), encoding="utf-8")
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        return mock_proc

    with patch("subprocess.run", side_effect=fake_missing_record):
        with pytest.raises(AIExecutionError, match="missing required dictionary field 'machine_record'"):
            provider.execute(sample_request)


# ============================================================================
# 3. Integration with ProtocolRunner
# ============================================================================


def test_protocol_timeout_resolution_standard_and_deep_research():
    """Verify that light protocols resolve to 180s and deep-research protocols resolve to 600s."""
    # Standard light protocols
    assert resolve_protocol_timeout("thesis-review") == 180.0
    assert resolve_protocol_timeout("valuation-update") == 180.0
    assert resolve_protocol_timeout("earnings-review") == 180.0
    assert resolve_protocol_timeout("technical-review") == 180.0
    assert resolve_protocol_timeout("preliminary-screening") == 180.0

    # Four heavy deep research protocols + generic
    assert resolve_protocol_timeout("deep-research-fund") == 600.0
    assert resolve_protocol_timeout("deep-research-equity") == 600.0
    assert resolve_protocol_timeout("deep-research-crypto") == 600.0
    assert resolve_protocol_timeout("deep-research-gold") == 600.0
    assert resolve_protocol_timeout("deep-research") == 600.0

    # Custom timeouts
    assert resolve_protocol_timeout("thesis-review", default_timeout=120.0) == 120.0
    assert resolve_protocol_timeout("deep-research-fund", deep_research_timeout=900.0) == 900.0


def test_codex_provider_resolve_timeout_integration():
    """Verify provider.resolve_timeout respects request overrides, protocol defaults, and explicit init timeouts."""
    provider = CodexCLIProvider(
        executable="codex",
        default_timeout=180.0,
        deep_research_timeout=600.0,
        cwd=Path.cwd(),
    )

    # 1. Normal protocol uses default 180s
    req_thesis = AIExecutionRequest(
        protocol_name="thesis-review",
        protocol_text="Review thesis",
        persistent_context={"symbol": "MSFT"},
    )
    assert provider.resolve_timeout(req_thesis) == 180.0

    # 2. Deep research protocols use 600s
    for proto in [
        "deep-research-fund",
        "deep-research-equity",
        "deep-research-crypto",
        "deep-research-gold",
    ]:
        req_deep = AIExecutionRequest(
            protocol_name=proto,
            protocol_text="Deep research",
            persistent_context={"symbol": "THF"},
        )
        assert provider.resolve_timeout(req_deep) == 600.0

    # 3. Request-level explicit override
    req_override = AIExecutionRequest(
        protocol_name="deep-research-fund",
        protocol_text="Deep research",
        persistent_context={"symbol": "THF"},
        timeout=450.0,
    )
    assert provider.resolve_timeout(req_override) == 450.0


def test_codex_provider_deep_research_timeout_error_message():
    """Verify that timeout during Deep Research produces the descriptive 'Deep Research exceeded...' error message."""
    provider = CodexCLIProvider(
        executable="codex", deep_research_timeout=600.0, cwd=Path.cwd()
    )
    req_fund = AIExecutionRequest(
        protocol_name="deep-research-fund",
        protocol_text="Deep research fund",
        persistent_context={"symbol": "THF"},
    )

    with patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="codex", timeout=600.0),
    ):
        with pytest.raises(AIExecutionError) as exc_info:
            provider.execute(req_fund)

    err_str = str(exc_info.value)
    assert "Deep Research exceeded the 600-second execution limit" in err_str


def test_kill_process_tree_cleanly_terminates():
    """Verify _kill_process_tree terminates process without error."""
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None
    mock_proc.pid = 99999

    _kill_process_tree(mock_proc)
    mock_proc.kill.assert_called_once()
    mock_proc.wait.assert_called_once()


def test_codex_provider_integration_with_runner(session: Session, sample_request):
    """Verify CodexCLIProvider works seamlessly within ProtocolRunner without altering invariants."""
    inst_repo = InstrumentRepository(session)
    state_repo = IntelligenceStateRepository(session)

    with session.begin():
        inst = inst_repo.create(symbol="GOOG", name="Alphabet Inc", instrument_type="equity", currency="USD")
        state_repo.create_initial(inst.id)
        original_state = state_repo.update(
            inst.id,
            thesis_status=ThesisStatus.UNCHANGED,
            recommendation=Recommendation.HOLD,
        )

    codex_output = {
        "machine_record": {
            "thesis_status": "STRONGER",
            "recommendation": "ADD",
            "material_changes": ["Search momentum"],
            "open_questions": [],
        },
        "human_brief": "Search büyümesi beklentilerin üzerinde gerçekleşti.",
        "confidence": "HIGH",
    }

    provider = CodexCLIProvider(executable="codex", cwd=Path.cwd())

    def fake_subprocess_run(cmd, **kwargs):
        out_file_idx = cmd.index("-o") + 1
        Path(cmd[out_file_idx]).write_text(json.dumps(codex_output), encoding="utf-8")
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = ""
        return mock_proc

    runner = ProtocolRunner(session, provider)

    with patch("subprocess.run", side_effect=fake_subprocess_run):
        execution = runner.run_asset_protocol(inst.id, "thesis-review")

    # Run is persisted and COMPLETED
    assert execution.run.status == ProtocolRunStatus.COMPLETED
    assert execution.run.machine_record["thesis_status"] == "STRONGER"
    assert execution.run.human_brief == "Search büyümesi beklentilerin üzerinde gerçekleşti."

    # Invariant check: IntelligenceState was NOT automatically updated!
    current_state = state_repo.get(inst.id)
    assert current_state.thesis_status == ThesisStatus.UNCHANGED
    assert current_state.recommendation == Recommendation.HOLD
    assert current_state.updated_at == original_state.updated_at
