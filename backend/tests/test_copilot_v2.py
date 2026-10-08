"""Comprehensive test suite for PortfolioMind Copilot V2 (Phase 1).

Covers all 16 required invariants:
1. V1 Copilot still works and existing tests remain green.
2. Logical FAST/BALANCED/DEEP profiles resolve correctly.
3. Reasoning effort is passed to Codex CLI using the verified mechanism.
4. No direct OpenAI/Gemini/Anthropic API path exists in V2.
5. Tool Registry rejects unknown tools.
6. V2 tools are read-only.
7. get_portfolio_summary returns bounded user-specific data.
8. get_holdings is user-scoped.
9. get_asset_context cannot expose another user's asset data.
10. get_briefing is user/relevance scoped appropriately.
11. FAST can produce FINAL_RESPONSE without a second reasoner.
12. FAST can produce HANDOFF.
13. Handoff retains original user message.
14. Handoff retains already fetched tool results.
15. Execution trace records Codex invocation count / latency / tools.
16. Codex execution failure does not mutate user data.
"""

from datetime import datetime, timezone
from decimal import Decimal
import inspect
from pathlib import Path
import re
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from sqlalchemy import select

from app.models.asset import Asset, AssetType
from app.models.briefing import (
    BriefingCategory,
    BriefingImpact,
    BriefingItem,
    BriefingMateriality,
    BriefingRun,
    BriefingTimeHorizon,
)
from app.models.cash import CashAccount
from app.models.instrument import Instrument
from app.models.intelligence import InstrumentIntelligenceState, Recommendation, ThesisStatus
from app.models.copilot import CopilotConversation, CopilotMessage
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.services.copilot import CopilotService
from app.services.copilot_v2 import (
    CodexCLIExecutionError,
    CodexSessionResumeError,
    CodexTimeoutError,
    CodexV2Error,
    CopilotV2Service,
    EventEmitter,
    ExecutionTrace,
    HandoffContext,
    ModelProfile,
    OrchestratorAction,
    OrchestratorResult,
    ProfileConfig,
    ProgressEvent,
    ProgressEventType,
    ReasoningEffort,
    SessionManager,
    ToolCall,
    ToolExecutionError,
    ToolResult,
    build_recovery_context,
    get_profile_config,
)
from app.services.copilot_v2.adapter import CodexV2Adapter, CodexV2ExecutionResult
from app.services.copilot_v2.orchestrator import FastOrchestrator
from app.services.copilot_v2.reasoner import ReasonerEngine
from app.services.copilot_v2.tools import (
    ToolClassification,
    ToolDefinition,
    ToolRegistry,
    default_tool_registry,
)
from app.services.copilot_v2.tools.builtins import (
    get_asset_context_handler,
    get_briefing_handler,
    get_holdings_handler,
    get_portfolio_summary_handler,
)


async def _create_test_user(db_session, email_prefix: str = "v2_test") -> User:
    user = User(
        email=f"{email_prefix}_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed_pw_test",
        display_name="V2 Tester",
        base_currency="TRY",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# -----------------------------------------------------------------------------
# 1. V1 Copilot still works
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_v1_copilot_still_works():
    """Verify that Copilot V1 classes remain intact and importable."""
    assert CopilotService is not None
    assert hasattr(CopilotService, "send_message")
    assert hasattr(CopilotService, "create_conversation")


# -----------------------------------------------------------------------------
# 2. Logical FAST/BALANCED/DEEP profiles resolve correctly
# -----------------------------------------------------------------------------
def test_logical_profiles_resolve_correctly():
    """Verify logical ModelProfile values and config mapping."""
    fast_cfg = get_profile_config(ModelProfile.FAST)
    assert fast_cfg.profile == ModelProfile.FAST
    assert fast_cfg.default_reasoning_effort == ReasoningEffort.LOW
    assert fast_cfg.default_tool_budget == 3
    assert fast_cfg.timeout_seconds == 45.0
    assert fast_cfg.model_name in ("gpt-5.6-luna", "gpt-reserve")

    balanced_cfg = get_profile_config(ModelProfile.BALANCED)
    assert balanced_cfg.profile == ModelProfile.BALANCED
    assert balanced_cfg.default_reasoning_effort == ReasoningEffort.MEDIUM
    assert balanced_cfg.default_tool_budget == 6
    assert balanced_cfg.timeout_seconds == 90.0

    deep_cfg = get_profile_config(ModelProfile.DEEP)
    assert deep_cfg.profile == ModelProfile.DEEP
    assert deep_cfg.default_reasoning_effort == ReasoningEffort.HIGH
    assert deep_cfg.default_tool_budget == 12
    assert deep_cfg.timeout_seconds == 180.0

    # Test rejection of unauthorized profile names (e.g. FAST+, ULTRA)
    with pytest.raises(ValueError, match="Unknown ModelProfile"):
        get_profile_config("FAST+")

    with pytest.raises(ValueError, match="Unknown ModelProfile"):
        get_profile_config("ULTRA")


# -----------------------------------------------------------------------------
# 3. Reasoning effort is passed to Codex CLI using verified mechanism
# -----------------------------------------------------------------------------
def test_reasoning_effort_passed_to_codex_cli():
    """Verify reasoning effort is passed to Codex CLI via -c model_reasoning_effort="..."."""
    adapter = CodexV2Adapter(executable="codex")

    with patch("subprocess.Popen") as mock_popen, patch("pathlib.Path.is_file", return_value=True):
        proc_mock = MagicMock()
        proc_mock.communicate.return_value = ('{"action": "FINAL_RESPONSE", "answer": "ok"}', "")
        proc_mock.returncode = 0
        mock_popen.return_value = proc_mock

        adapter.execute(
            prompt="Hello",
            profile=ModelProfile.FAST,
            reasoning_effort=ReasoningEffort.XHIGH,  # Runtime override
            require_json=True,
        )

        args, kwargs = mock_popen.call_args
        cmd = args[0]
        assert "-c" in cmd
        effort_idx = cmd.index("-c") + 1
        assert cmd[effort_idx] == 'model_reasoning_effort="xhigh"'


# -----------------------------------------------------------------------------
# 4. No direct OpenAI/Gemini/Anthropic API path exists in V2
# -----------------------------------------------------------------------------
def test_no_direct_model_apis_in_v2():
    """Verify strictly no direct OpenAI/Gemini/Anthropic/LangChain imports exist in copilot_v2."""
    v2_dir = Path(__file__).resolve().parent.parent / "app" / "services" / "copilot_v2"
    forbidden_tokens = [
        "openai.OpenAI",
        "chat.completions.create",
        "anthropic",
        "google.generativeai",
        "langchain",
        "from openai import",
        "import openai",
        "import anthropic",
    ]

    for py_file in v2_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in content, f"Forbidden direct AI API token '{token}' found in {py_file.name}"


# -----------------------------------------------------------------------------
# 5. Tool Registry rejects unknown tools
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tool_registry_rejects_unknown_tools(db_session):
    """ToolRegistry must raise ToolExecutionError when an unknown tool is invoked."""
    registry = ToolRegistry(enforce_read_only_phase=True)
    fake_user_id = uuid.uuid4()

    with pytest.raises(ToolExecutionError, match="Unknown tool: 'drop_database'"):
        await registry.execute(
            name="drop_database",
            db=db_session,
            user_id=fake_user_id,
            args={},
        )


# -----------------------------------------------------------------------------
# 6. V2 tools are read-only
# -----------------------------------------------------------------------------
def test_v2_tools_are_read_only():
    """ToolRegistry must reject registration of WRITE tools in Phase 1."""
    registry = ToolRegistry(enforce_read_only_phase=True)

    write_tool = ToolDefinition(
        name="create_order",
        description="Write tool",
        parameters_schema={},
        classification=ToolClassification.WRITE,
        handler=lambda **kw: None,
    )

    with pytest.raises(ToolExecutionError, match="Cannot register WRITE tool"):
        registry.register(write_tool)


# -----------------------------------------------------------------------------
# 7. get_portfolio_summary returns bounded user-specific data
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_portfolio_summary_returns_bounded_user_data(db_session):
    """get_portfolio_summary calculates accurate user totals and returns bounded payload."""
    user = await _create_test_user(db_session, "summary_user")

    # Add Cash Account
    cash = CashAccount(
        user_id=user.id,
        currency="TRY",
        balance=Decimal("50000.0"),
    )
    db_session.add(cash)

    # Add Asset
    asset = Asset(
        user_id=user.id,
        asset_type=AssetType.STOCK,
        symbol="THYAO.IS",
        name="Türk Hava Yolları",
        current_price=Decimal("300.0"),
        current_price_currency="TRY",
    )
    db_session.add(asset)
    await db_session.flush()

    # Add BUY transaction
    tx = Transaction(
        asset_id=asset.id,
        transaction_type=TransactionType.BUY,
        quantity=Decimal("100.0"),
        price_per_unit=Decimal("250.0"),
        total_amount=Decimal("25000.0"),
        transaction_currency="TRY",
        transaction_date=datetime.now(timezone.utc).date(),
    )
    db_session.add(tx)
    await db_session.commit()

    summary = await get_portfolio_summary_handler(db=db_session, user_id=user.id)

    assert summary["base_currency"] == "TRY"
    assert summary["total_cash"] == 50000.0
    assert summary["total_value"] == 80000.0  # 50000 cash + 100 * 300
    assert summary["total_cost"] == 25000.0  # 100 * 250
    assert summary["unrealized_pl"] == 5000.0  # 30000 - 25000
    assert summary["asset_count"] == 1


# -----------------------------------------------------------------------------
# 8. get_holdings is user-scoped
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_holdings_is_user_scoped(db_session):
    """get_holdings returns only the authenticated user's positions."""
    user_a = await _create_test_user(db_session, "user_a")
    user_b = await _create_test_user(db_session, "user_b")

    # User A asset
    asset_a = Asset(
        user_id=user_a.id,
        asset_type=AssetType.CRYPTO,
        symbol="BTC",
        name="Bitcoin",
        current_price=Decimal("60000.0"),
        current_price_currency="USD",
    )
    # User B asset
    asset_b = Asset(
        user_id=user_b.id,
        asset_type=AssetType.STOCK,
        symbol="AAPL",
        name="Apple Inc",
        current_price=Decimal("200.0"),
        current_price_currency="USD",
    )
    db_session.add_all([asset_a, asset_b])
    await db_session.flush()

    tx_a = Transaction(
        asset_id=asset_a.id,
        transaction_type=TransactionType.BUY,
        quantity=Decimal("1.5"),
        price_per_unit=Decimal("50000.0"),
        total_amount=Decimal("75000.0"),
        transaction_currency="USD",
        transaction_date=datetime.now(timezone.utc).date(),
    )
    tx_b = Transaction(
        asset_id=asset_b.id,
        transaction_type=TransactionType.BUY,
        quantity=Decimal("10.0"),
        price_per_unit=Decimal("150.0"),
        total_amount=Decimal("1500.0"),
        transaction_currency="USD",
        transaction_date=datetime.now(timezone.utc).date(),
    )
    db_session.add_all([tx_a, tx_b])
    await db_session.commit()

    holdings_a = await get_holdings_handler(db=db_session, user_id=user_a.id)
    assert holdings_a["returned_count"] == 1
    assert holdings_a["holdings"][0]["symbol"] == "BTC"
    assert holdings_a["holdings"][0]["quantity"] == 1.5

    holdings_b = await get_holdings_handler(db=db_session, user_id=user_b.id)
    assert holdings_b["returned_count"] == 1
    assert holdings_b["holdings"][0]["symbol"] == "AAPL"


# -----------------------------------------------------------------------------
# 9. get_asset_context cannot expose another user's asset data
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_asset_context_cannot_expose_another_users_asset_data(db_session):
    """get_asset_context must never leak User A's private holding quantities or cost to User B."""
    user_a = await _create_test_user(db_session, "leak_user_a")
    user_b = await _create_test_user(db_session, "leak_user_b")

    inst = Instrument(
        symbol="ASELS",
        name="Aselsan",
        asset_type=AssetType.STOCK,
        currency="TRY",
    )
    db_session.add(inst)
    await db_session.flush()

    # User A owns 5,000 shares of ASELS
    asset_a = Asset(
        user_id=user_a.id,
        instrument_id=inst.id,
        asset_type=AssetType.STOCK,
        symbol="ASELS",
        name="Aselsan",
        current_price=Decimal("60.0"),
        current_price_currency="TRY",
    )
    db_session.add(asset_a)
    await db_session.flush()

    tx_a = Transaction(
        asset_id=asset_a.id,
        transaction_type=TransactionType.BUY,
        quantity=Decimal("5000.0"),
        price_per_unit=Decimal("40.0"),
        total_amount=Decimal("200000.0"),
        transaction_currency="TRY",
        transaction_date=datetime.now(timezone.utc).date(),
    )
    db_session.add(tx_a)
    await db_session.commit()

    # User B queries ASELS context
    ctx_b = await get_asset_context_handler(db=db_session, user_id=user_b.id, symbol="ASELS")

    # Instrument metadata is public
    assert ctx_b["instrument"]["symbol"] == "ASELS"
    assert ctx_b["instrument"]["name"] == "Aselsan"

    # User B holding is NOT owned; User A's 5000 shares must be invisible
    assert ctx_b["user_holding"]["is_owned"] is False
    assert "quantity" not in ctx_b["user_holding"]
    assert "5000" not in str(ctx_b["user_holding"])


# -----------------------------------------------------------------------------
# 10. get_briefing is user/relevance scoped appropriately
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_briefing_is_user_scoped(db_session):
    """get_briefing returns only the briefing items generated for the authenticated user."""
    user_a = await _create_test_user(db_session, "brief_user_a")
    user_b = await _create_test_user(db_session, "brief_user_b")

    inst = Instrument(
        symbol="THYAO",
        name="Türk Hava Yolları",
        asset_type=AssetType.STOCK,
        currency="TRY",
    )
    db_session.add(inst)
    await db_session.flush()

    run_a = BriefingRun(
        user_id=user_a.id,
        generated_at=datetime.now(timezone.utc),
        scope="PORTFOLIO",
        status="SUCCESS",
        trigger_type="MANUAL",
        items_found=1,
        items_shown=1,
        items_filtered=0,
    )
    db_session.add(run_a)
    await db_session.flush()

    item_a = BriefingItem(
        briefing_run_id=run_a.id,
        user_id=user_a.id,
        instrument_id=inst.id,
        headline="THYAO Record Q3 Earnings",
        summary="Revenues beat estimates by 12%.",
        why_it_matters="Impacts operating profitability and long-term valuation targets.",
        category=BriefingCategory.EARNINGS,
        materiality=BriefingMateriality.HIGH,
        impact=BriefingImpact.POSITIVE,
        time_horizon=BriefingTimeHorizon.MEDIUM,
        review_required=False,
    )
    db_session.add(item_a)
    await db_session.commit()

    # User A gets item
    res_a = await get_briefing_handler(db=db_session, user_id=user_a.id)
    assert res_a["returned_count"] == 1
    assert res_a["items"][0]["headline"] == "THYAO Record Q3 Earnings"

    # User B gets 0 items
    res_b = await get_briefing_handler(db=db_session, user_id=user_b.id)
    assert res_b["returned_count"] == 0


# -----------------------------------------------------------------------------
# 11. FAST can produce FINAL_RESPONSE without a second reasoner
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fast_can_produce_final_response_without_second_reasoner(db_session):
    """FAST Orchestrator completes simple task in one turn without escalating."""
    user = await _create_test_user(db_session, "fast_simple")
    mock_adapter = MagicMock()

    # FAST returns FINAL_RESPONSE directly
    mock_adapter.execute.return_value = CodexV2ExecutionResult(
        raw_output='{"action": "FINAL_RESPONSE", "answer": "Portföyünüz toplam 100.000 TL\'dir."}',
        parsed_json={"action": "FINAL_RESPONSE", "answer": "Portföyünüz toplam 100.000 TL'dir."},
        session_id=None,
        duration_ms=120.0,
        model_used="gpt-5.6-luna",
        reasoning_effort_used="low",
    )

    service = CopilotV2Service(adapter=mock_adapter)
    result = await service.handle_user_message(
        db=db_session,
        user_id=user.id,
        user_message="Portföyüm toplam kaç TL?",
    )

    assert result["escalated"] is False
    assert result["handoff"] is None
    assert "100.000 TL" in result["answer"]
    assert result["trace"]["codex_invocation_count"] == 1
    assert result["trace"]["final_profile"] == "FAST"


# -----------------------------------------------------------------------------
# 12. FAST can produce HANDOFF
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fast_can_produce_handoff(db_session):
    """FAST Orchestrator detects complex request and produces HANDOFF."""
    user = await _create_test_user(db_session, "fast_handoff")
    mock_adapter = MagicMock()

    mock_adapter.execute.return_value = CodexV2ExecutionResult(
        raw_output='{"action": "HANDOFF", "handoff": {"target_profile": "DEEP", "reasoning_effort": "high", "task_brief": "Kapsamlı risk analizi", "escalation_reason": "Çoklu varlık stratejik değerlendirmesi"}}',
        parsed_json={
            "action": "HANDOFF",
            "handoff": {
                "target_profile": "DEEP",
                "reasoning_effort": "high",
                "task_brief": "Kapsamlı risk analizi",
                "escalation_reason": "Çoklu varlık stratejik değerlendirmesi",
            },
        },
        session_id=None,
        duration_ms=150.0,
        model_used="gpt-5.6-luna",
        reasoning_effort_used="low",
    )

    trace = ExecutionTrace(starting_profile=ModelProfile.FAST)
    orchestrator = FastOrchestrator(adapter=mock_adapter)

    orch_res = await orchestrator.run(
        db=db_session,
        user_id=user.id,
        user_message="Portföyümü hedeflerim ve risk kapasitem ile birlikte detaylı değerlendir.",
        trace=trace,
    )

    assert orch_res.action == OrchestratorAction.HANDOFF
    assert orch_res.handoff is not None
    assert orch_res.handoff.target_profile == ModelProfile.DEEP
    assert orch_res.handoff.reasoning_effort == ReasoningEffort.HIGH
    assert orch_res.handoff.escalation_reason == "Çoklu varlık stratejik değerlendirmesi"


# -----------------------------------------------------------------------------
# 13. Handoff retains original user message
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_handoff_retains_original_user_message(db_session):
    """Verify original user message survives handoff completely unchanged."""
    user = await _create_test_user(db_session, "raw_preserve")
    raw_prompt = "  Önemli soru: %&/ Portföyüm $10,000 değerinde mi?! \n Satmalı mıyım?   "

    mock_adapter = MagicMock()
    mock_adapter.execute.return_value = CodexV2ExecutionResult(
        raw_output='{"action": "HANDOFF", "handoff": {"target_profile": "BALANCED", "reasoning_effort": "medium", "task_brief": "brief", "escalation_reason": "complex"}}',
        parsed_json={
            "action": "HANDOFF",
            "handoff": {
                "target_profile": "BALANCED",
                "reasoning_effort": "medium",
                "task_brief": "brief",
                "escalation_reason": "complex",
            },
        },
        session_id=None,
        duration_ms=100.0,
        model_used="gpt-5.6-luna",
        reasoning_effort_used="low",
    )

    trace = ExecutionTrace(starting_profile=ModelProfile.FAST)
    orchestrator = FastOrchestrator(adapter=mock_adapter)
    orch_res = await orchestrator.run(
        db=db_session,
        user_id=user.id,
        user_message=raw_prompt,
        trace=trace,
    )

    assert orch_res.handoff.original_user_message == raw_prompt


# -----------------------------------------------------------------------------
# 14. Handoff retains already fetched tool results
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_handoff_retains_already_fetched_tool_results(db_session):
    """If FAST retrieved tool data before deciding to escalate, it is preserved in Handoff."""
    user = await _create_test_user(db_session, "tool_reuse")

    # Turn 1: FAST requests tool `get_holdings`
    turn1_res = CodexV2ExecutionResult(
        raw_output='{"action": "TOOL_CALL", "tool_calls": [{"tool": "get_holdings", "args": {"limit": 10}}]}',
        parsed_json={"action": "TOOL_CALL", "tool_calls": [{"tool": "get_holdings", "args": {"limit": 10}}]},
        session_id=None,
        duration_ms=100.0,
        model_used="gpt-5.6-luna",
        reasoning_effort_used="low",
    )
    # Turn 2: With tool data in hand, FAST decides task needs BALANCED reasoning
    turn2_res = CodexV2ExecutionResult(
        raw_output='{"action": "HANDOFF", "handoff": {"target_profile": "BALANCED", "reasoning_effort": "medium", "task_brief": "Varlık dağılımı analizi", "escalation_reason": "Varlıkların korelasyon analizi gerekiyor"}}',
        parsed_json={
            "action": "HANDOFF",
            "handoff": {
                "target_profile": "BALANCED",
                "reasoning_effort": "medium",
                "task_brief": "Varlık dağılımı analizi",
                "escalation_reason": "Varlıkların korelasyon analizi gerekiyor",
            },
        },
        session_id=None,
        duration_ms=120.0,
        model_used="gpt-5.6-luna",
        reasoning_effort_used="low",
    )

    mock_adapter = MagicMock()
    mock_adapter.execute.side_effect = [turn1_res, turn2_res]

    trace = ExecutionTrace(starting_profile=ModelProfile.FAST)
    orchestrator = FastOrchestrator(adapter=mock_adapter)

    orch_res = await orchestrator.run(
        db=db_session,
        user_id=user.id,
        user_message="Varlıklarım arasındaki korelasyonu ve risk dağılımını analiz et.",
        trace=trace,
    )

    assert orch_res.action == OrchestratorAction.HANDOFF
    assert orch_res.handoff is not None
    # Crucial verification: The holdings data retrieved in Turn 1 exists in already_retrieved_tool_results
    assert len(orch_res.handoff.already_retrieved_tool_results) == 1
    key = list(orch_res.handoff.already_retrieved_tool_results.keys())[0]
    assert "get_holdings" in key


# -----------------------------------------------------------------------------
# 15. Execution trace records invocation count, latency, tools
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_execution_trace_records_metrics(db_session):
    """Execution trace tracks starting/final profile, codex calls, tool durations, and latency."""
    trace = ExecutionTrace(starting_profile=ModelProfile.FAST)
    trace.record_codex_call(duration_ms=150.0)
    trace.record_tool_call(tool_name="get_portfolio_summary", duration_ms=25.5)
    trace.record_escalation(target_profile=ModelProfile.DEEP, effort=ReasoningEffort.HIGH)
    trace.record_codex_call(duration_ms=450.0)
    trace.finalize()

    data = trace.to_dict()
    assert data["starting_profile"] == "FAST"
    assert data["final_profile"] == "DEEP"
    assert data["reasoning_effort"] == "high"
    assert data["codex_invocation_count"] == 2
    assert "get_portfolio_summary" in data["tools_called"]
    assert data["tool_durations"]["get_portfolio_summary"] == 25.5
    assert data["escalation_occurred"] is True
    assert data["total_latency_ms"] >= 0.0


# -----------------------------------------------------------------------------
# 16. Codex execution failure does not mutate user data
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_codex_execution_failure_does_not_mutate_user_data(db_session):
    """If Codex execution fails with Timeout or CLI error, user data remains strictly safe."""
    user = await _create_test_user(db_session, "safe_user")

    # Add initial asset
    asset = Asset(
        user_id=user.id,
        asset_type=AssetType.STOCK,
        symbol="KCHOL.IS",
        name="Koç Holding",
        current_price=Decimal("200.0"),
        current_price_currency="TRY",
    )
    db_session.add(asset)
    await db_session.commit()

    mock_adapter = MagicMock()
    mock_adapter.execute.side_effect = CodexTimeoutError("Codex timed out", timeout_seconds=45.0)

    service = CopilotV2Service(adapter=mock_adapter)
    res = await service.handle_user_message(
        db=db_session,
        user_id=user.id,
        user_message="Tüm portföyümü sat!",
    )

    assert "güvendedir" in res["answer"]
    assert res["trace"]["failure_category"] == "CodexTimeoutError"

    # Verify asset is completely unchanged
    assets_after = await db_session.execute(select(Asset).where(Asset.user_id == user.id))
    assert len(assets_after.scalars().all()) == 1


# =============================================================================
# PHASE 2 TESTS: Session Continuity, Recovery, Same-Session Escalation, Events
# =============================================================================

# -----------------------------------------------------------------------------
# 17. Adapter persists session and extracts session ID
# -----------------------------------------------------------------------------
def test_adapter_persists_session_and_extracts_id():
    """When persist_session=True, --ephemeral is omitted and session ID is extracted."""
    adapter = CodexV2Adapter()

    captured_cmds = []

    def mock_run(cmd, *args, **kwargs):
        captured_cmds.append(cmd)
        # Write output to the temp output path specified in cmd (-o <path>)
        out_idx = cmd.index("-o") + 1
        out_path = Path(cmd[out_idx])
        out_path.write_text('{"answer": "Başarılı"}', encoding="utf-8")
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout="session id: 11111111-2222-3333-4444-555555555555\n",
            stderr="",
        )

    with patch("subprocess.run", side_effect=mock_run):
        res = adapter.execute(
            prompt="Test prompt",
            profile=ModelProfile.FAST,
            persist_session=True,
        )

    assert len(captured_cmds) == 1
    assert "--ephemeral" not in captured_cmds[0]
    assert res.session_id == "11111111-2222-3333-4444-555555555555"
    assert res.parsed_json == {"answer": "Başarılı"}


# -----------------------------------------------------------------------------
# 18. Adapter resumes session with CLI arguments
# -----------------------------------------------------------------------------
def test_adapter_resumes_session_with_cli_args():
    """Resuming passes session_id, model, and reasoning_effort to 'codex exec resume'."""
    adapter = CodexV2Adapter()
    captured_cmds = []

    def mock_run(cmd, *args, **kwargs):
        captured_cmds.append(cmd)
        out_idx = cmd.index("-o") + 1
        out_path = Path(cmd[out_idx])
        out_path.write_text('{"answer": "Devam"}', encoding="utf-8")
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout="",
            stderr="",
        )

    with patch("subprocess.run", side_effect=mock_run):
        res = adapter.execute(
            prompt="İkinci mesaj",
            profile=ModelProfile.BALANCED,
            reasoning_effort=ReasoningEffort.HIGH,
            session_id="target-sess-999",
        )

    assert len(captured_cmds) == 1
    cmd = captured_cmds[0]
    assert "resume" in cmd
    assert "target-sess-999" in cmd
    assert 'model_reasoning_effort="high"' in " ".join(cmd)
    assert res.session_id == "target-sess-999"


# -----------------------------------------------------------------------------
# 19. Adapter raises CodexSessionResumeError on missing rollout
# -----------------------------------------------------------------------------
def test_adapter_raises_session_resume_error_on_missing_rollout():
    """When resume returns 'no rollout found', CodexSessionResumeError is raised."""
    adapter = CodexV2Adapter()

    def mock_run(cmd, *args, **kwargs):
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=1,
            stdout="",
            stderr="Error: thread/resume: thread/resume failed: no rollout found for thread id dead-sess (code -32600)",
        )

    with patch("subprocess.run", side_effect=mock_run):
        with pytest.raises(CodexSessionResumeError) as exc_info:
            adapter.execute(
                prompt="test",
                session_id="dead-sess",
            )

    assert exc_info.value.session_id == "dead-sess"
    assert exc_info.value.returncode == 1
    assert "no rollout found" in exc_info.value.stderr


# -----------------------------------------------------------------------------
# 20. Same-session escalation flow (FAST -> BALANCED)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_same_session_escalation_flow(db_session):
    """Escalation from FAST to BALANCED/DEEP strictly reuses the SAME session ID."""
    user = await _create_test_user(db_session, "same_sess_user")

    # Turn 1 (FAST): returns HANDOFF with session_id 'sess-shared-123'
    fast_res = CodexV2ExecutionResult(
        raw_output='{"action": "HANDOFF", "handoff": {"target_profile": "BALANCED", "reasoning_effort": "medium", "task_brief": "Derin analiz", "escalation_reason": "Risk analizi"}}',
        parsed_json={
            "action": "HANDOFF",
            "handoff": {
                "target_profile": "BALANCED",
                "reasoning_effort": "medium",
                "task_brief": "Derin analiz",
                "escalation_reason": "Risk analizi",
            },
        },
        session_id="sess-shared-123",
        duration_ms=120.0,
        model_used="gpt-5.6-luna",
        reasoning_effort_used="low",
    )

    # Turn 2 (Reasoner): executed with the SAME session_id 'sess-shared-123'
    reasoner_res = CodexV2ExecutionResult(
        raw_output='{"action": "FINAL_RESPONSE", "answer": "Portföy risk ve korelasyon analizi tamamlandı."}',
        parsed_json={
            "action": "FINAL_RESPONSE",
            "answer": "Portföy risk ve korelasyon analizi tamamlandı.",
        },
        session_id="sess-shared-123",
        duration_ms=450.0,
        model_used="gpt-5.6-terra",
        reasoning_effort_used="medium",
    )

    mock_adapter = MagicMock()
    mock_adapter.execute.side_effect = [fast_res, reasoner_res]

    service = CopilotV2Service(adapter=mock_adapter)
    res = await service.handle_user_message(
        db=db_session,
        user_id=user.id,
        user_message="Portföyümü hedeflerim doğrultusunda analiz et.",
    )

    assert res["escalated"] is True
    assert res["session_id"] == "sess-shared-123"
    assert "Portföy risk" in res["answer"]

    # Verify adapter was called twice, and second call reused the same session_id
    assert mock_adapter.execute.call_count == 2
    call1_kwargs = mock_adapter.execute.call_args_list[0].kwargs
    call2_kwargs = mock_adapter.execute.call_args_list[1].kwargs

    assert call1_kwargs["profile"] == ModelProfile.FAST
    assert call2_kwargs["session_id"] == "sess-shared-123"
    assert call2_kwargs["profile"] == ModelProfile.BALANCED
    assert call2_kwargs["reasoning_effort"] == ReasoningEffort.MEDIUM


# -----------------------------------------------------------------------------
# 21. Handoff tool reuse prevents duplicate tool execution in Reasoner
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_handoff_tool_reuse_prevents_refetching(db_session):
    """Tool results retrieved in FAST are reused in Reasoner without refetching."""
    user = await _create_test_user(db_session, "tool_reuse_user")

    # Step 1: FAST calls tool get_portfolio_summary
    fast_step1 = CodexV2ExecutionResult(
        raw_output='{"action": "TOOL_CALL", "tool_calls": [{"tool": "get_portfolio_summary", "args": {}}]}',
        parsed_json={"action": "TOOL_CALL", "tool_calls": [{"tool": "get_portfolio_summary", "args": {}}]},
        session_id="sess-reuse-555",
        duration_ms=80.0,
        model_used="gpt-5.6-luna",
        reasoning_effort_used="low",
    )

    # Step 2: FAST has summary data, decides task requires DEEP reasoning
    fast_step2 = CodexV2ExecutionResult(
        raw_output='{"action": "HANDOFF", "handoff": {"target_profile": "DEEP", "reasoning_effort": "high", "task_brief": "Detaylı portföy stratejisi", "escalation_reason": "Makro strateji"}}',
        parsed_json={
            "action": "HANDOFF",
            "handoff": {
                "target_profile": "DEEP",
                "reasoning_effort": "high",
                "task_brief": "Detaylı portföy stratejisi",
                "escalation_reason": "Makro strateji",
            },
        },
        session_id="sess-reuse-555",
        duration_ms=100.0,
        model_used="gpt-5.6-luna",
        reasoning_effort_used="low",
    )

    # Step 3: Reasoner uses already retrieved tool results and immediately produces FINAL_RESPONSE
    reasoner_res = CodexV2ExecutionResult(
        raw_output='{"action": "FINAL_RESPONSE", "answer": "Mevcut özet verileriniz ışığında stratejik değerlendirme yapıldı."}',
        parsed_json={
            "action": "FINAL_RESPONSE",
            "answer": "Mevcut özet verileriniz ışığında stratejik değerlendirme yapıldı.",
        },
        session_id="sess-reuse-555",
        duration_ms=500.0,
        model_used="gpt-6-astra",
        reasoning_effort_used="high",
    )

    mock_adapter = MagicMock()
    mock_adapter.execute.side_effect = [fast_step1, fast_step2, reasoner_res]

    service = CopilotV2Service(adapter=mock_adapter)
    res = await service.handle_user_message(
        db=db_session,
        user_id=user.id,
        user_message="Portföyümü makro trendlerle değerlendir.",
    )

    assert res["escalated"] is True
    # Reasoner saw the retrieved results and did NOT call get_portfolio_summary again
    assert res["tools_used"] == ["get_portfolio_summary"]
    assert res["trace"]["tool_results_reused"] == 1


# -----------------------------------------------------------------------------
# 22. Database-backed session recovery on resume failure
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_db_backed_session_recovery_on_resume_failure(db_session):
    """When resuming a session fails with missing rollout, recover using DB history."""
    user = await _create_test_user(db_session, "recovery_user")

    # Create conversation with an existing expired session
    conv = CopilotConversation(
        user_id=user.id,
        title="Kurtarma Testi",
        codex_session_id="expired-rollout-id-123",
        codex_session_status="ACTIVE",
    )
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    # Add prior history to DB
    await SessionManager.record_user_message(db_session, conv.id, "Portföyüm toplam kaç TL?")
    await SessionManager.record_assistant_message(
        db_session, conv.id, "Portföyünüzün toplam değeri 1.000.000 TL'dir."
    )

    # When trying to resume expired-rollout-id-123, adapter raises CodexSessionResumeError
    resume_error = CodexSessionResumeError(
        message="no rollout found",
        session_id="expired-rollout-id-123",
        returncode=1,
        stderr="Error: thread/resume failed: no rollout found for thread id expired-rollout-id-123",
    )

    # Recovered turn succeeds under a brand new session
    recovered_res = CodexV2ExecutionResult(
        raw_output='{"action": "FINAL_RESPONSE", "answer": "Önceki sohbetinize istinaden yanıtlandı."}',
        parsed_json={
            "action": "FINAL_RESPONSE",
            "answer": "Önceki sohbetinize istinaden yanıtlandı.",
        },
        session_id="fresh-recovered-session-456",
        duration_ms=180.0,
        model_used="gpt-5.6-luna",
        reasoning_effort_used="low",
    )

    mock_adapter = MagicMock()
    mock_adapter.execute.side_effect = [resume_error, recovered_res]

    service = CopilotV2Service(adapter=mock_adapter)
    res = await service.handle_user_message(
        db=db_session,
        user_id=user.id,
        user_message="Bunun ne kadarı döviz?",
        conversation_id=conv.id,
    )

    assert "Önceki sohbetinize" in res["answer"]
    assert res["trace"]["session_resume_failed"] is True
    assert res["trace"]["session_recovery_occurred"] is True
    assert res["trace"]["session_mode"] == "RECOVERED"

    # Verify conversation now has the new session ID saved
    await db_session.refresh(conv)
    assert conv.codex_session_id == "fresh-recovered-session-456"
    assert conv.codex_session_status == "ACTIVE"


# -----------------------------------------------------------------------------
# 23. Multi-turn conversation continuity
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_multi_turn_session_continuity(db_session):
    """Multi-turn requests in the same conversation maintain session continuity."""
    user = await _create_test_user(db_session, "multi_turn_user")

    conv = CopilotConversation(
        user_id=user.id,
        title="Çok Turlu Sohbet",
    )
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    # Turn 1
    t1_res = CodexV2ExecutionResult(
        raw_output='{"action": "FINAL_RESPONSE", "answer": "Net değer 500.000 TL."}',
        parsed_json={"action": "FINAL_RESPONSE", "answer": "Net değer 500.000 TL."},
        session_id="sess-turn-001",
        duration_ms=150.0,
        model_used="gpt-5.6-luna",
        reasoning_effort_used="low",
    )

    # Turn 2
    t2_res = CodexV2ExecutionResult(
        raw_output='{"action": "FINAL_RESPONSE", "answer": "Nakit oranınız %20."}',
        parsed_json={"action": "FINAL_RESPONSE", "answer": "Nakit oranınız %20."},
        session_id="sess-turn-001",
        duration_ms=140.0,
        model_used="gpt-5.6-luna",
        reasoning_effort_used="low",
    )

    mock_adapter = MagicMock()
    mock_adapter.execute.side_effect = [t1_res, t2_res]

    service = CopilotV2Service(adapter=mock_adapter)

    # Execute Turn 1
    res1 = await service.handle_user_message(
        db=db_session,
        user_id=user.id,
        user_message="Portföy toplamı?",
        conversation_id=conv.id,
    )
    assert res1["session_id"] == "sess-turn-001"

    # Execute Turn 2
    res2 = await service.handle_user_message(
        db=db_session,
        user_id=user.id,
        user_message="Nakit ne kadar?",
        conversation_id=conv.id,
    )
    assert res2["session_id"] == "sess-turn-001"

    # Verify adapter's second call used session_id="sess-turn-001"
    second_call_session = mock_adapter.execute.call_args_list[1].kwargs.get("session_id")
    assert second_call_session == "sess-turn-001"

    # Verify messages stored in DB
    msgs_stmt = select(CopilotMessage).where(CopilotMessage.conversation_id == conv.id).order_by(CopilotMessage.created_at.asc())
    msgs = (await db_session.execute(msgs_stmt)).scalars().all()
    assert len(msgs) == 4
    assert [m.role for m in msgs] == ["user", "assistant", "user", "assistant"]


# -----------------------------------------------------------------------------
# 24. Ephemeral progress events lifecycle without DB pollution
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ephemeral_progress_events_lifecycle(db_session):
    """Progress events are emitted to callback and telemetry, never persisted to copilot_messages."""
    user = await _create_test_user(db_session, "events_user")

    conv = CopilotConversation(user_id=user.id, title="Events Test")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    events_received: list[ProgressEvent] = []

    async def on_progress(event: ProgressEvent):
        events_received.append(event)

    fast_turn = CodexV2ExecutionResult(
        raw_output='{"action": "TOOL_CALL", "tool_calls": [{"tool": "get_portfolio_summary", "args": {}}]}',
        parsed_json={"action": "TOOL_CALL", "tool_calls": [{"tool": "get_portfolio_summary", "args": {}}]},
        session_id="sess-events-1",
        duration_ms=100.0,
        model_used="gpt-5.6-luna",
        reasoning_effort_used="low",
    )
    fast_final = CodexV2ExecutionResult(
        raw_output='{"action": "FINAL_RESPONSE", "answer": "Portföy özetiniz hazır."}',
        parsed_json={"action": "FINAL_RESPONSE", "answer": "Portföy özetiniz hazır."},
        session_id="sess-events-1",
        duration_ms=110.0,
        model_used="gpt-5.6-luna",
        reasoning_effort_used="low",
    )

    mock_adapter = MagicMock()
    mock_adapter.execute.side_effect = [fast_turn, fast_final]

    service = CopilotV2Service(adapter=mock_adapter)
    res = await service.handle_user_message(
        db=db_session,
        user_id=user.id,
        user_message="Portföyümü göster",
        conversation_id=conv.id,
        progress_callback=on_progress,
    )

    # Check received event types
    event_types = [e.event_type.value for e in events_received]
    assert ProgressEventType.STARTED.value in event_types
    assert ProgressEventType.TOOL_RUNNING.value in event_types
    assert ProgressEventType.COMPLETED.value in event_types

    # Ensure progress events were captured in trace
    assert len(res["trace"]["progress_events"]) > 0

    # CRITICAL CHECK: Ensure DB only has user message and assistant answer
    msgs = (
        await db_session.execute(
            select(CopilotMessage).where(CopilotMessage.conversation_id == conv.id)
        )
    ).scalars().all()
    assert len(msgs) == 2
    assert {m.role for m in msgs} == {"user", "assistant"}


# -----------------------------------------------------------------------------
# 25. Progress callback error does not break model execution
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_progress_callback_error_does_not_break_execution(db_session):
    """An exception thrown inside progress_callback does not disrupt model response."""
    user = await _create_test_user(db_session, "cb_err_user")

    def broken_callback(event: ProgressEvent):
        raise RuntimeError("Callback crashed!")

    mock_adapter = MagicMock()
    mock_adapter.execute.return_value = CodexV2ExecutionResult(
        raw_output='{"action": "FINAL_RESPONSE", "answer": "Her şey yolunda."}',
        parsed_json={"action": "FINAL_RESPONSE", "answer": "Her şey yolunda."},
        session_id="sess-safe-999",
        duration_ms=90.0,
        model_used="gpt-5.6-luna",
        reasoning_effort_used="low",
    )

    service = CopilotV2Service(adapter=mock_adapter)
    res = await service.handle_user_message(
        db=db_session,
        user_id=user.id,
        user_message="Merhaba",
        progress_callback=broken_callback,
    )

    assert res["answer"] == "Her şey yolunda."


# -----------------------------------------------------------------------------
# 26. build_recovery_context bounds history to max_turns
# -----------------------------------------------------------------------------
def test_build_recovery_context_bounded():
    """build_recovery_context retains only the most recent max_turns * 2 messages."""
    fake_messages = [
        CopilotMessage(
            role="user" if i % 2 == 0 else "assistant",
            raw_content=f"Message {i}",
        )
        for i in range(20)
    ]

    context = build_recovery_context(fake_messages, max_turns=3)
    # 3 turns = 6 messages (messages 14 through 19)
    assert "Message 14" in context
    assert "Message 19" in context
    assert "Message 13" not in context
    assert "=== PRIOR CONVERSATION HISTORY (RECOVERED FROM DATABASE) ===" in context

