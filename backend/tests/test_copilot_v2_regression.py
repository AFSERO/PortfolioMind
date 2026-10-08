"""Regression test suite for Copilot V2 behavior fixes.

Ensures:
1. get_asset_context safely parses DecisionLogEntry attributes (title, summary,
   user_rationale, confidence, expectation) without AttributeError.
2. Standardized tool contracts include status="success" on success.
3. Owned assets return is_owned=True with correct holding statistics.
4. Non-owned assets return is_owned=False cleanly.
5. FAST Orchestrator prompt enforces asset visibility tool routing and fresh data precedence.
6. Fresh deterministic tool result precedence overrides prior conversational error claims.
7. Reasoner engine prompt contains fresh deterministic data precedence.
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock
import uuid

import pytest
from sqlalchemy import select

from app.models.asset import Asset, AssetType
from app.models.cash import CashAccount
from app.models.decision_log import DecisionEventType, DecisionLogEntry
from app.models.instrument import Instrument
from app.models.intelligence import InstrumentIntelligenceState, Recommendation, ThesisStatus
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.services.copilot_v2.adapter import CodexV2ExecutionResult
from app.services.copilot_v2.contracts import (
    ModelProfile,
    OrchestratorAction,
    ReasoningEffort,
)
from app.services.copilot_v2.orchestrator import (
    FAST_ORCHESTRATOR_SYSTEM_PROMPT,
    FastOrchestrator,
)
from app.services.copilot_v2.reasoner import REASONER_SYSTEM_PROMPT, ReasonerEngine
from app.services.copilot_v2.telemetry import ExecutionTrace
from app.services.copilot_v2.tools.builtins import (
    get_asset_context_handler,
    get_briefing_handler,
    get_holdings_handler,
    get_portfolio_summary_handler,
)


async def _create_test_user(db_session, prefix: str = "reg_user") -> User:
    user = User(
        email=f"{prefix}_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="test_pw_hash",
        display_name="Regression Test User",
        base_currency="TRY",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_get_asset_context_with_decision_logs_no_attribute_error(db_session):
    """Verify get_asset_context handles DecisionLogEntry without rationales/user_notes crash."""
    user = await _create_test_user(db_session, "dl_test")

    inst = Instrument(
        symbol="THF",
        name="TERA PORTFÖY HİSSE SENEDİ (TL) FONU (HİSSE SENEDİ YOĞUN FON)",
        asset_type=AssetType.FUND,
        currency="TRY",
    )
    db_session.add(inst)
    await db_session.flush()

    asset = Asset(
        user_id=user.id,
        instrument_id=inst.id,
        asset_type=AssetType.FUND,
        symbol="THF",
        name="TERA PORTFÖY HİSSE SENEDİ (TL) FONU (HİSSE SENEDİ YOĞUN FON)",
        current_price=Decimal("0.768118"),
        current_price_currency="TRY",
    )
    db_session.add(asset)
    await db_session.flush()

    tx = Transaction(
        asset_id=asset.id,
        transaction_type=TransactionType.BUY,
        quantity=Decimal("34671.947898"),
        price_per_unit=Decimal("0.768118"),
        total_amount=Decimal("100000.0"),
        transaction_currency="TRY",
        transaction_date=datetime.now(timezone.utc).date(),
    )
    db_session.add(tx)

    # Attach real DecisionLogEntry records with valid schema attributes
    dl1 = DecisionLogEntry(
        user_id=user.id,
        instrument_id=inst.id,
        event_type=DecisionEventType.POSITION_OPENED,
        title="THF Fon Alımı",
        summary="Yüksek hisse yoğun fon yatırımı yapıldı.",
        user_rationale="BIST büyüme beklentisi nedeniyle tercih edildi.",
        confidence="HIGH",
        expectation="Yıllık %60 getiri hedefi.",
        occurred_at=datetime.now(timezone.utc),
    )
    dl2 = DecisionLogEntry(
        user_id=user.id,
        instrument_id=inst.id,
        event_type=DecisionEventType.POSITION_ADDED,
        title="Performans Değerlendirmesi",
        summary="Piyasa dalgalanması takip ediliyor.",
        user_rationale="Kısa vadeli düzeltme bekleniyor.",
        confidence="MEDIUM",
        expectation="Sabit tutulacak.",
        occurred_at=datetime.now(timezone.utc),
    )
    db_session.add_all([dl1, dl2])
    await db_session.commit()

    # Execute get_asset_context_handler
    ctx = await get_asset_context_handler(db=db_session, user_id=user.id, symbol="THF")

    # Contract checks
    assert ctx["status"] == "success"
    assert ctx["query_symbol"] == "THF"
    assert ctx["instrument"]["symbol"] == "THF"

    # User holding checks
    holding = ctx["user_holding"]
    assert holding is not None
    assert holding["is_owned"] is True
    assert pytest.approx(holding["quantity"], 0.001) == 34671.947898
    assert pytest.approx(holding["current_price"], 0.0001) == 0.768118
    assert holding["market_value"] is not None

    # Decision logs checks (must be safely extracted without AttributeError)
    decisions = ctx["recent_decisions"]
    assert len(decisions) == 2
    assert decisions[0]["title"] in ["THF Fon Alımı", "Performans Değerlendirmesi"]
    assert "user_rationale" in decisions[0]
    assert "confidence" in decisions[0]
    assert "expectation" in decisions[0]


@pytest.mark.asyncio
async def test_get_asset_context_unowned_asset(db_session):
    """Verify get_asset_context for unowned asset returns status=success and is_owned=False."""
    user = await _create_test_user(db_session, "unowned_test")

    inst = Instrument(
        symbol="EREGL",
        name="Ereğli Demir Çelik",
        asset_type=AssetType.STOCK,
        currency="TRY",
    )
    db_session.add(inst)
    await db_session.commit()

    ctx = await get_asset_context_handler(db=db_session, user_id=user.id, symbol="EREGL")
    assert ctx["status"] == "success"
    assert ctx["instrument"]["symbol"] == "EREGL"
    assert ctx["user_holding"]["is_owned"] is False
    assert "quantity" not in ctx["user_holding"]


@pytest.mark.asyncio
async def test_all_builtin_tools_return_status_success(db_session):
    """Verify standard tool response contract across builtins includes status='success'."""
    user = await _create_test_user(db_session, "status_test")

    # 1. get_portfolio_summary
    cash = CashAccount(
        user_id=user.id,
        currency="TRY",
        balance=Decimal("25000.0"),
    )
    db_session.add(cash)
    await db_session.commit()

    summary = await get_portfolio_summary_handler(db=db_session, user_id=user.id)
    assert summary["status"] == "success"
    assert "net_worth" in summary
    assert "total_value" in summary

    # 2. get_holdings
    holdings = await get_holdings_handler(db=db_session, user_id=user.id)
    assert holdings["status"] == "success"
    assert isinstance(holdings["holdings"], list)

    # 3. get_briefing
    briefing = await get_briefing_handler(db=db_session, user_id=user.id)
    assert briefing["status"] == "success"
    assert isinstance(briefing["items"], list)


def test_orchestrator_prompt_contains_routing_rules_and_fresh_precedence():
    """Verify FAST orchestrator system prompt contains the explicit routing rules and precedence."""
    assert "CRITICAL TOOL ROUTING RULE" in FAST_ORCHESTRATOR_SYSTEM_PROMPT
    assert "Do NOT call `get_briefing` or `search_news` for simple ownership" in FAST_ORCHESTRATOR_SYSTEM_PROMPT
    assert "FRESH DETERMINISTIC DATA PRECEDENCE" in FAST_ORCHESTRATOR_SYSTEM_PROMPT
    assert "FRESH DETERMINISTIC DATA PRECEDENCE" in REASONER_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_orchestrator_fresh_data_precedence_in_execution(db_session):
    """Verify orchestrator returns FINAL_RESPONSE when tool returns valid data, ignoring prior error."""
    user = await _create_test_user(db_session, "precedence_test")

    inst = Instrument(
        symbol="THF",
        name="TERA PORTFÖY HİSSE SENEDİ (TL) FONU (HİSSE SENEDİ YOĞUN FON)",
        asset_type=AssetType.FUND,
        currency="TRY",
    )
    db_session.add(inst)
    await db_session.flush()

    asset = Asset(
        user_id=user.id,
        instrument_id=inst.id,
        asset_type=AssetType.FUND,
        symbol="THF",
        name="TERA PORTFÖY HİSSE SENEDİ (TL) FONU (HİSSE SENEDİ YOĞUN FON)",
        current_price=Decimal("0.768118"),
        current_price_currency="TRY",
    )
    db_session.add(asset)
    await db_session.commit()

    # Mock adapter simulating:
    # 1. First invocation: Requests get_asset_context(symbol="THF")
    # 2. Second invocation: Tool returned valid data -> Returns FINAL_RESPONSE confirming ownership
    call_1 = CodexV2ExecutionResult(
        raw_output='{"action": "TOOL_CALL", "tool_calls": [{"tool": "get_asset_context", "args": {"symbol": "THF"}}]}',
        parsed_json={
            "action": "TOOL_CALL",
            "tool_calls": [{"tool": "get_asset_context", "args": {"symbol": "THF"}}],
        },
        session_id="mock-session-001",
        duration_ms=120.0,
        model_used="gpt-5.6-luna",
        reasoning_effort_used="low",
    )
    call_2 = CodexV2ExecutionResult(
        raw_output='{"action": "FINAL_RESPONSE", "answer": "Evet, THF fonu portföyünüzde bulunuyor. Sistem kayıtlarına göre 34.671 payınız var."}',
        parsed_json={
            "action": "FINAL_RESPONSE",
            "answer": "Evet, THF fonu portföyünüzde bulunuyor. Sistem kayıtlarına göre 34.671 payınız var.",
        },
        session_id="mock-session-001",
        duration_ms=130.0,
        model_used="gpt-5.6-luna",
        reasoning_effort_used="low",
    )

    mock_adapter = MagicMock()
    mock_adapter.execute.side_effect = [call_1, call_2]

    trace = ExecutionTrace(starting_profile=ModelProfile.FAST)
    orchestrator = FastOrchestrator(adapter=mock_adapter)

    # Conversation history contains a previous turn claiming "teknik hata"
    context_str = (
        "User: bu thf fonunu gördün mü\n"
        "Assistant: Şu an THF fonuyla ilgili teknik bir hata oluştu; bu nedenle bilgi veremiyorum."
    )

    result = await orchestrator.run(
        db=db_session,
        user_id=user.id,
        user_message="bu thf fonunu gördün mü",
        trace=trace,
        conversation_context=context_str,
    )

    assert result.action == OrchestratorAction.FINAL_RESPONSE
    assert "Evet, THF fonu portföyünüzde bulunuyor" in result.final_answer
    assert "teknik hata" not in result.final_answer.lower()
    assert trace.codex_invocation_count == 2
    assert "get_asset_context" in trace.tools_called
    assert "get_briefing" not in trace.tools_called
