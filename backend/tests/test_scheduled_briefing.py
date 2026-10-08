"""Automated test suite for Scheduled Daily Briefing + Event-Driven Monitoring.

Verifies:
1. Default configuration settings.
2. SCHEDULED trigger provenance on BriefingRun.
3. Incremental evidence windowing (last_run - 2h) vs bootstrap (now - 48h).
4. Per-user in-flight concurrency lock.
5. Multi-user cycle and fault isolation.
6. Zero state mutation invariant.
7. Zero automatic formal reviews invariant.
8. Needs Attention surfacing and resolution upon review completion.
9. Scheduler lifecycle and trigger conditions.
"""

import asyncio
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
from decimal import Decimal
import uuid
import zoneinfo

from pytest import mark
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.asset import Asset
from app.models.briefing import (
    BriefingCategory,
    BriefingImpact,
    BriefingItem,
    BriefingMateriality,
    BriefingRun,
    BriefingThesisImpact,
    BriefingTimeHorizon,
    BriefingTriggerType,
)
from app.models.decision_log import DecisionEventType, DecisionLogEntry
from app.models.instrument import Instrument
from app.models.intelligence import (
    InstrumentIntelligenceState,
    IntelligenceReview,
    Recommendation,
    TechnicalStatus,
    ThesisStatus,
    ValuationStatus,
)
from app.models.transaction import Transaction, TransactionType
from app.schemas.briefing import BriefingRunResponse
from app.services import briefing as briefing_service
from app.services.formal_review import execute_briefing_formal_review
from app.services.scheduler import (
    BriefingScheduler,
    run_scheduled_briefing_cycle,
    run_scheduled_briefing_for_user,
    scheduler,
)
from tests.conftest import _TestSession

# Ensure Finance/src is in sys.path
_FINANCE_SRC = Path(__file__).resolve().parents[2] / "Finance" / "src"
if str(_FINANCE_SRC) not in sys.path:
    sys.path.insert(0, str(_FINANCE_SRC))

from investment_intelligence.briefing_reasoner import BriefingAssessment
from investment_intelligence.execution import AIExecutionResult


class MockNewsRecord:
    def __init__(self, title: str, summary: str = "", published_at: datetime = None, source: str = "Test News"):
        self.title = title
        self.summary = summary or title
        self.published_at = published_at or datetime.now(timezone.utc)
        self.source = source
        self.url = "https://news.example.com/item"
        self.source_quality = "PRIMARY"


async def _create_test_user(client: AsyncClient, prefix: str = "sched") -> tuple[uuid.UUID, dict]:
    email = f"{prefix}_{uuid.uuid4().hex[:6]}@example.com"
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Sched Tester"},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    token = data["access_token"]
    user_id = uuid.UUID(data["user"]["id"])
    headers = {"Authorization": f"Bearer {token}"}
    return user_id, headers


async def _create_test_asset(client: AsyncClient, headers: dict, symbol: str = "AAPL") -> uuid.UUID:
    resp = await client.post(
        "/api/assets",
        json={
            "asset_type": "STOCK",
            "symbol": symbol,
            "name": f"{symbol} Inc",
            "current_price_currency": "USD",
            "initial_transaction": {
                "transaction_type": "BUY",
                "quantity": "5",
                "price_per_unit": "150.00",
                "transaction_currency": "USD",
                "transaction_date": "2024-01-10",
            },
        },
        headers=headers,
    )
    assert resp.status_code == 201
    return uuid.UUID(resp.json()["data"]["instrument_id"])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_scheduler_config_defaults():
    """Verify default scheduler settings adhere to specification."""
    assert settings.BRIEFING_SCHEDULER_ENABLED is False
    assert settings.BRIEFING_SCHEDULE_HOUR == 8
    assert settings.BRIEFING_SCHEDULE_MINUTE == 0
    assert settings.BRIEFING_SCHEDULE_TIMEZONE == "Europe/Istanbul"
    assert settings.BRIEFING_SCHEDULE_CHECK_INTERVAL_SECONDS == 60


@pytest.mark.asyncio
async def test_run_scheduled_briefing_for_user_provenance(client: AsyncClient, db_session: AsyncSession):
    """Verify run_scheduled_briefing_for_user tags the run with SCHEDULED trigger_type."""
    user_id, headers = await _create_test_user(client, "prov")
    inst_id = await _create_test_asset(client, headers, "MSFT")

    mock_news = [
        MockNewsRecord(
            title="Microsoft expands cloud infrastructure in Europe",
            summary="Microsoft today announced expansion of data centers.",
        )
    ]

    with patch("app.services.briefing.GoogleNewsRSSProvider") as MockNewsProvider, \
         patch("app.services.briefing.SECDisclosureProvider") as MockSecProvider:
        instance_news = MagicMock()
        instance_news.get_recent_news.return_value = mock_news
        MockNewsProvider.return_value = instance_news

        instance_sec = MagicMock()
        instance_sec.get_recent_disclosures.return_value = []
        MockSecProvider.return_value = instance_sec

        run_resp = await run_scheduled_briefing_for_user(db=db_session, user_id=user_id)

    assert run_resp is not None
    assert run_resp.trigger_type == BriefingTriggerType.SCHEDULED
    assert run_resp.status == "COMPLETED"

    # Verify DB persistence
    stmt = select(BriefingRun).where(BriefingRun.id == run_resp.id)
    db_run = (await db_session.execute(stmt)).scalar_one()
    assert db_run.trigger_type == BriefingTriggerType.SCHEDULED


@pytest.mark.asyncio
async def test_scheduled_briefing_evidence_window_incremental(client: AsyncClient, db_session: AsyncSession):
    """Verify incremental window calculation uses last_run.generated_at - 2 hours."""
    user_id, headers = await _create_test_user(client, "window_inc")
    await _create_test_asset(client, headers, "GOOGL")

    # Seed an earlier briefing run
    earlier_time = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)
    prior_run = BriefingRun(
        user_id=user_id,
        generated_at=earlier_time,
        scope="PORTFOLIO_AND_WATCHLIST",
        status="COMPLETED",
        trigger_type=BriefingTriggerType.SCHEDULED,
        items_found=0,
        items_shown=0,
        items_filtered=0,
    )
    db_session.add(prior_run)
    await db_session.commit()

    captured_since = []

    with patch("app.services.briefing.GoogleNewsRSSProvider") as MockNewsProvider, \
         patch("app.services.briefing.SECDisclosureProvider") as MockSecProvider:
        instance_news = MagicMock()
        def mock_news(inst, since, until, limit):
            captured_since.append(since)
            return []
        instance_news.get_recent_news.side_effect = mock_news
        MockNewsProvider.return_value = instance_news

        instance_sec = MagicMock()
        instance_sec.get_recent_disclosures.return_value = []
        MockSecProvider.return_value = instance_sec

        await run_scheduled_briefing_for_user(db=db_session, user_id=user_id)

    assert len(captured_since) > 0
    expected_since = earlier_time - timedelta(hours=2)
    # The first captured_since should match the earlier_time - 2h
    assert abs((captured_since[0] - expected_since).total_seconds()) < 5


@pytest.mark.asyncio
async def test_scheduled_briefing_evidence_window_bootstrap(client: AsyncClient, db_session: AsyncSession):
    """Verify bootstrap window calculation uses now - 48 hours when no prior run exists."""
    user_id, headers = await _create_test_user(client, "window_boot")
    await _create_test_asset(client, headers, "AMZN")

    captured_since = []

    with patch("app.services.briefing.GoogleNewsRSSProvider") as MockNewsProvider, \
         patch("app.services.briefing.SECDisclosureProvider") as MockSecProvider:
        instance_news = MagicMock()
        def mock_news(inst, since, until, limit):
            captured_since.append(since)
            return []
        instance_news.get_recent_news.side_effect = mock_news
        MockNewsProvider.return_value = instance_news

        instance_sec = MagicMock()
        instance_sec.get_recent_disclosures.return_value = []
        MockSecProvider.return_value = instance_sec

        t_before = datetime.now(timezone.utc)
        await run_scheduled_briefing_for_user(db=db_session, user_id=user_id)
        t_after = datetime.now(timezone.utc)

    assert len(captured_since) > 0
    expected_since = t_before - timedelta(hours=48)
    assert abs((captured_since[0] - expected_since).total_seconds()) < 10


@pytest.mark.asyncio
async def test_concurrency_lock_prevents_simultaneous_runs(client: AsyncClient, db_session: AsyncSession):
    """Verify in-flight guard prevents multiple concurrent runs for the same user."""
    user_id, headers = await _create_test_user(client, "concurrent")
    await _create_test_asset(client, headers, "TSLA")

    # Manually place user in active set
    async with briefing_service._briefing_generation_lock:
        briefing_service._active_generating_users.add(user_id)

    try:
        # Concurrent request should be rejected with 409 when no prior run exists
        with pytest.raises(Exception) as exc_info:
            await briefing_service.generate_briefing_run(
                db=db_session,
                user_id=user_id,
                force_refresh=True,
            )
        assert "409" in str(exc_info.value) or "already in progress" in str(exc_info.value).lower()
    finally:
        async with briefing_service._briefing_generation_lock:
            briefing_service._active_generating_users.discard(user_id)


@pytest.mark.asyncio
async def test_scheduler_cycle_across_users(client: AsyncClient, db_session: AsyncSession):
    """Verify run_scheduled_briefing_cycle processes multiple users in isolated sessions."""
    u1, h1 = await _create_test_user(client, "cycle1")
    u2, h2 = await _create_test_user(client, "cycle2")
    await _create_test_asset(client, h1, "META")
    await _create_test_asset(client, h2, "NFLX")

    with patch("app.services.briefing.GoogleNewsRSSProvider") as MockNewsProvider, \
         patch("app.services.briefing.SECDisclosureProvider") as MockSecProvider:
        instance_news = MagicMock()
        instance_news.get_recent_news.return_value = []
        MockNewsProvider.return_value = instance_news

        instance_sec = MagicMock()
        instance_sec.get_recent_disclosures.return_value = []
        MockSecProvider.return_value = instance_sec

        # Target only our two test users to keep test hermetic
        runs_u1 = await run_scheduled_briefing_cycle(session_factory=_TestSession, target_user_id=u1)
        runs_u2 = await run_scheduled_briefing_cycle(session_factory=_TestSession, target_user_id=u2)

    assert len(runs_u1) == 1
    assert len(runs_u2) == 1
    assert runs_u1[0].user_id == u1
    assert runs_u2[0].user_id == u2
    assert runs_u1[0].trigger_type == BriefingTriggerType.SCHEDULED
    assert runs_u2[0].trigger_type == BriefingTriggerType.SCHEDULED


@pytest.mark.asyncio
async def test_scheduler_cycle_fault_isolation(client: AsyncClient, db_session: AsyncSession):
    """Verify that an error in one user's run does not crash the cycle or affect other users."""
    u1, _ = await _create_test_user(client, "fault1")
    u2, h2 = await _create_test_user(client, "fault2")
    await _create_test_asset(client, h2, "NVDA")

    call_count = 0

    async def mock_gen(db, user_id, **kwargs):
        nonlocal call_count
        call_count += 1
        if user_id == u1:
            raise RuntimeError("Database connection glitch for user 1")
        # For user 2, return dummy response
        return BriefingRunResponse(
            id=uuid.uuid4(),
            user_id=u2,
            generated_at=datetime.now(timezone.utc),
            scope="PORTFOLIO_AND_WATCHLIST",
            status="COMPLETED",
            trigger_type=BriefingTriggerType.SCHEDULED,
            items_found=0,
            items_shown=0,
            items_filtered=0,
            created_at=datetime.now(timezone.utc),
            items=[],
        )

    with patch("app.services.scheduler.briefing_service.generate_briefing_run", side_effect=mock_gen):
        # Run cycle for u1 -> fails gracefully, returns None
        r1 = await run_scheduled_briefing_for_user(db=db_session, user_id=u1)
        assert r1 is None

        # Run cycle for u2 -> succeeds
        r2 = await run_scheduled_briefing_for_user(db=db_session, user_id=u2)
        assert r2 is not None
        assert r2.user_id == u2


@pytest.mark.asyncio
async def test_scheduler_zero_state_mutations_and_zero_auto_reviews(client: AsyncClient, db_session: AsyncSession):
    """Verify that scheduled briefing runs NEVER mutate intelligence state or auto-trigger formal reviews."""
    user_id, headers = await _create_test_user(client, "nomut")
    inst_id = await _create_test_asset(client, headers, "ORCL")

    # Set up initial persistent intelligence state
    state = InstrumentIntelligenceState(
        instrument_id=inst_id,
        thesis_status=ThesisStatus.UNCHANGED,
        valuation_status=ValuationStatus.FAIR,
        recommendation=Recommendation.HOLD,
        technical_status=TechnicalStatus.ON_TRACK,
    )
    db_session.add(state)
    await db_session.commit()

    # News event with critical keywords that flag review_required
    mock_news = [
        MockNewsRecord(
            title="ORCL Oracle faces major antitrust investigation and accounting probe",
            summary="DOJ launched antitrust lawsuit and regulatory investigation into Oracle cloud practices.",
        )
    ]

    mock_reasoner = MagicMock()
    mock_reasoner.assess_event.return_value = MagicMock(
        impact="NEGATIVE",
        materiality="HIGH",
        time_horizon="LONG",
        thesis_impact="WEAKER",
        review_required=True,
        confidence="HIGH",
        recommended_review="THESIS_REVIEW",
        why_it_matters="Major antitrust action requiring formal review.",
    )

    with patch("app.services.briefing.GoogleNewsRSSProvider") as MockNewsProvider, \
         patch("app.services.briefing.SECDisclosureProvider") as MockSecProvider:
        instance_news = MagicMock()
        instance_news.get_recent_news.return_value = mock_news
        MockNewsProvider.return_value = instance_news

        instance_sec = MagicMock()
        instance_sec.get_recent_disclosures.return_value = []
        MockSecProvider.return_value = instance_sec

        run_resp = await run_scheduled_briefing_for_user(
            db=db_session, user_id=user_id, reasoner=mock_reasoner
        )

    assert run_resp is not None
    assert len(run_resp.items) == 1
    item = run_resp.items[0]
    assert item.review_required is True

    # 1. State must be completely untouched!
    await db_session.refresh(state)
    assert state.thesis_status == ThesisStatus.UNCHANGED
    assert state.valuation_status == ValuationStatus.FAIR
    assert state.recommendation == Recommendation.HOLD
    assert state.technical_status == TechnicalStatus.ON_TRACK

    # 2. Zero automatic formal reviews created!
    rev_count = (await db_session.execute(
        select(IntelligenceReview).where(IntelligenceReview.instrument_id == inst_id)
    )).scalars().all()
    assert len(rev_count) == 0


@pytest.mark.asyncio
async def test_needs_attention_surfacing_and_resolution(client: AsyncClient, db_session: AsyncSession):
    """Verify that an item requiring review surfaces in attention stats, and is resolved when reviewed."""
    user_id, headers = await _create_test_user(client, "atten_res")
    inst_id = await _create_test_asset(client, headers, "ADBE")

    mock_news = [
        MockNewsRecord(
            title="ADBE Adobe earnings miss revenue expectations and cuts annual guidance",
            summary="Adobe reported lower than expected Q3 revenue and reduced fiscal guidance.",
        )
    ]

    with patch("app.services.briefing.GoogleNewsRSSProvider") as MockNewsProvider, \
         patch("app.services.briefing.SECDisclosureProvider") as MockSecProvider:
        instance_news = MagicMock()
        instance_news.get_recent_news.return_value = mock_news
        MockNewsProvider.return_value = instance_news

        instance_sec = MagicMock()
        instance_sec.get_recent_disclosures.return_value = []
        MockSecProvider.return_value = instance_sec

        run_resp = await run_scheduled_briefing_for_user(db=db_session, user_id=user_id)

    assert run_resp is not None
    item = run_resp.items[0]
    assert item.review_required is True

    # Step A: Check attention_count in stats endpoint -> should be 1
    stats_resp = await client.get("/api/briefing/stats", headers=headers)
    assert stats_resp.status_code == 200
    assert stats_resp.json()["data"]["attention_count"] == 1

    # Step B: Also verify service function directly
    att_count = await briefing_service.get_briefing_attention_count(db_session, user_id)
    assert att_count == 1

    # Step C: Complete a formal review for this briefing item
    mock_ai_result = AIExecutionResult(
        machine_record={
            "protocol": "earnings-review",
            "thesis_status": "UNCHANGED",
            "valuation_status": "FAIR",
            "technical_status": "ON_TRACK",
            "recommendation": "HOLD",
        },
        human_brief="Thesis remains solid post earnings update.",
        confidence="HIGH",
    )

    with patch("app.services.formal_review.load_protocol") as mock_load, \
         patch("app.services.formal_review.CodexCLIProvider") as MockProvider:
        proto_mock = MagicMock()
        proto_mock.canonical_name = "earnings-review"
        proto_mock.protocol_type = "deep_reasoning"
        proto_mock.description = "Earnings Review"
        mock_load.return_value = proto_mock

        provider_instance = MagicMock()
        provider_instance.execute.return_value = mock_ai_result
        MockProvider.return_value = provider_instance

        review_result = await execute_briefing_formal_review(
            db=db_session,
            briefing_item_id=item.id,
            user_id=user_id,
        )
        assert review_result["status"] == "COMPLETED"

    # Step D: Attention must now be resolved (count drops to 0)!
    stats_resp_after = await client.get("/api/briefing/stats", headers=headers)
    assert stats_resp_after.status_code == 200
    assert stats_resp_after.json()["data"]["attention_count"] == 0

    att_count_after = await briefing_service.get_briefing_attention_count(db_session, user_id)
    assert att_count_after == 0


@pytest.mark.asyncio
async def test_scheduler_lifecycle_and_should_trigger():
    """Verify scheduler lifecycle methods and time trigger evaluation."""
    test_sched = BriefingScheduler()
    assert test_sched.is_running is False

    # Start and immediately stop
    test_sched.start()
    assert test_sched.is_running is True
    await test_sched.stop()
    assert test_sched.is_running is False

    # Test trigger logic in configured timezone (Europe/Istanbul)
    target_hour = settings.BRIEFING_SCHEDULE_HOUR
    target_min = settings.BRIEFING_SCHEDULE_MINUTE
    tz = zoneinfo.ZoneInfo(settings.BRIEFING_SCHEDULE_TIMEZONE)

    # Same hour/min in configured timezone -> should trigger
    matching_dt = datetime(2026, 9, 17, target_hour, target_min, 0, tzinfo=tz)
    assert test_sched.should_trigger(matching_dt) is True

    # After firing once on that date, must NOT fire again on same date (at most once per day)
    test_sched._last_cycle_date = matching_dt.date()
    assert test_sched.should_trigger(matching_dt) is False

    # Different minute -> should not trigger
    different_min_dt = datetime(2026, 9, 18, target_hour, (target_min + 5) % 60, 0, tzinfo=tz)
    assert test_sched.should_trigger(different_min_dt) is False


# ============================================================================
# Regression Suite: Hardening Pass — Review Attention vs Decision Attention
# ============================================================================


def test_regression_01_hold_review_resolved():
    """1. HOLD review with intact thesis resolves attention to RESOLVED."""
    source_meta = {
        "review_status": "COMPLETED",
        "review_summary": {
            "protocol": "earnings-review",
            "recommendation": "HOLD",
            "thesis_status": "UNCHANGED",
            "valuation_status": "FAIR",
            "technical_status": "ON_TRACK",
        },
    }
    assert briefing_service.compute_item_attention_state(True, source_meta) == "RESOLVED"


def test_regression_02_review_required_still_requires_attention():
    """2. REVIEW_REQUIRED review retains review attention as REVIEWED_BUT_STILL_REQUIRES_ATTENTION."""
    source_meta = {
        "review_status": "COMPLETED",
        "review_summary": {
            "protocol": "valuation-update",
            "recommendation": "REVIEW_REQUIRED",
            "thesis_status": "UNCHANGED",
            "valuation_status": "FAIR",
        },
    }
    assert briefing_service.compute_item_attention_state(True, source_meta) == "REVIEWED_BUT_STILL_REQUIRES_ATTENTION"


def test_regression_03_add_review_decision_required():
    """3. ADD review produces actionable DECISION_REQUIRED state."""
    source_meta = {
        "review_status": "COMPLETED",
        "review_summary": {
            "protocol": "earnings-review",
            "recommendation": "ADD",
            "thesis_status": "STRONGER",
            "valuation_status": "ATTRACTIVE",
        },
    }
    assert briefing_service.compute_item_attention_state(True, source_meta) == "DECISION_REQUIRED"


def test_regression_04_buy_review_decision_required():
    """4. BUY review produces actionable DECISION_REQUIRED state."""
    source_meta = {
        "review_status": "COMPLETED",
        "review_summary": {
            "protocol": "thesis-review",
            "recommendation": "BUY",
            "thesis_status": "UNCHANGED",
            "valuation_status": "ATTRACTIVE",
        },
    }
    assert briefing_service.compute_item_attention_state(True, source_meta) == "DECISION_REQUIRED"


def test_regression_05_reduce_review_decision_required():
    """5. REDUCE review produces actionable DECISION_REQUIRED state."""
    source_meta = {
        "review_status": "COMPLETED",
        "review_summary": {
            "protocol": "valuation-update",
            "recommendation": "REDUCE",
            "thesis_status": "UNCHANGED",
            "valuation_status": "EXPENSIVE",
        },
    }
    assert briefing_service.compute_item_attention_state(True, source_meta) == "DECISION_REQUIRED"


def test_regression_06_sell_review_decision_required():
    """6. SELL review produces actionable DECISION_REQUIRED state."""
    source_meta = {
        "review_status": "COMPLETED",
        "review_summary": {
            "protocol": "thesis-review",
            "recommendation": "SELL",
            "thesis_status": "UNCHANGED",
            "valuation_status": "EXPENSIVE",
        },
    }
    assert briefing_service.compute_item_attention_state(True, source_meta) == "DECISION_REQUIRED"


def test_regression_07_weaker_thesis_still_requires_attention():
    """7. WEAKER thesis status requires review attention as REVIEWED_BUT_STILL_REQUIRES_ATTENTION."""
    source_meta = {
        "review_status": "COMPLETED",
        "review_summary": {
            "protocol": "earnings-review",
            "recommendation": "HOLD",
            "thesis_status": "WEAKER",
            "valuation_status": "FAIR",
        },
    }
    assert briefing_service.compute_item_attention_state(True, source_meta) == "REVIEWED_BUT_STILL_REQUIRES_ATTENTION"

    # Even if recommendation is ADD, a WEAKER thesis requires ongoing review attention
    source_meta["review_summary"]["recommendation"] = "ADD"
    assert briefing_service.compute_item_attention_state(True, source_meta) == "REVIEWED_BUT_STILL_REQUIRES_ATTENTION"


def test_regression_08_invalidated_thesis_still_requires_attention():
    """8. INVALIDATED thesis status requires review attention as REVIEWED_BUT_STILL_REQUIRES_ATTENTION."""
    source_meta = {
        "review_status": "COMPLETED",
        "review_summary": {
            "protocol": "thesis-review",
            "recommendation": "HOLD",
            "thesis_status": "INVALIDATED",
            "valuation_status": "EXPENSIVE",
        },
    }
    assert briefing_service.compute_item_attention_state(True, source_meta) == "REVIEWED_BUT_STILL_REQUIRES_ATTENTION"


@pytest.mark.asyncio
async def test_regression_09_system_recommendation_changed_does_not_resolve_decision_required(
    client: AsyncClient, db_session: AsyncSession
):
    """9. System-generated RECOMMENDATION_CHANGED alone does NOT resolve DECISION_REQUIRED."""
    user_id, headers = await _create_test_user(client, "sys_event_user")
    inst_id = await _create_test_asset(client, headers, "SYS_EVT")
    now = datetime.now(timezone.utc)
    review_time = now + timedelta(seconds=2)

    run = BriefingRun(
        user_id=user_id,
        generated_at=now,
        scope="PORTFOLIO_AND_WATCHLIST",
        status="COMPLETED",
        trigger_type=BriefingTriggerType.SCHEDULED,
        items_found=1,
        items_shown=1,
        items_filtered=0,
    )
    db_session.add(run)
    await db_session.flush()

    # Item with completed ADD review
    item = BriefingItem(
        briefing_run_id=run.id,
        user_id=user_id,
        instrument_id=inst_id,
        headline="Material growth breakout",
        summary="Company reports massive growth.",
        why_it_matters="Thesis acceleration.",
        impact=BriefingImpact.POSITIVE,
        materiality=BriefingMateriality.HIGH,
        time_horizon=BriefingTimeHorizon.MEDIUM,
        thesis_impact=BriefingThesisImpact.STRONGER,
        review_required=True,
        category=BriefingCategory.EARNINGS,
        source_metadata={
            "review_status": "COMPLETED",
            "triggered_at": review_time.isoformat(),
            "review_summary": {
                "protocol": "thesis-review",
                "recommendation": "ADD",
                "thesis_status": "STRONGER",
            },
        },
        is_portfolio=True,
    )
    db_session.add(item)

    # System-generated audit event logged at review completion
    system_log = DecisionLogEntry(
        user_id=user_id,
        instrument_id=inst_id,
        event_type=DecisionEventType.RECOMMENDATION_CHANGED,
        title="Recommendation changed to ADD",
        summary="Automated review result synced.",
        occurred_at=review_time + timedelta(seconds=5),
    )
    db_session.add(system_log)
    await db_session.commit()

    states = await briefing_service.resolve_item_attention_states(db_session, user_id, [item])
    assert states[item.id] == "DECISION_REQUIRED"


@pytest.mark.asyncio
async def test_regression_10_explicit_user_decision_note_resolves_decision_required(
    client: AsyncClient, db_session: AsyncSession
):
    """10. Explicit user decision note (MANUAL_DECISION_NOTE) after review resolves DECISION_REQUIRED."""
    user_id, headers = await _create_test_user(client, "user_note_user")
    inst_id = await _create_test_asset(client, headers, "NOTE_INST")
    now = datetime.now(timezone.utc)
    review_time = now - timedelta(minutes=15)

    run = BriefingRun(
        user_id=user_id,
        generated_at=now,
        scope="PORTFOLIO_AND_WATCHLIST",
        status="COMPLETED",
        trigger_type=BriefingTriggerType.SCHEDULED,
        items_found=1,
        items_shown=1,
        items_filtered=0,
    )
    db_session.add(run)
    await db_session.flush()

    item = BriefingItem(
        briefing_run_id=run.id,
        user_id=user_id,
        instrument_id=inst_id,
        headline="Breakout upside",
        summary="Positive momentum.",
        why_it_matters="Thesis growth.",
        impact=BriefingImpact.POSITIVE,
        materiality=BriefingMateriality.HIGH,
        time_horizon=BriefingTimeHorizon.MEDIUM,
        thesis_impact=BriefingThesisImpact.STRONGER,
        review_required=True,
        category=BriefingCategory.EARNINGS,
        source_metadata={
            "review_status": "COMPLETED",
            "triggered_at": review_time.isoformat(),
            "review_summary": {
                "protocol": "earnings-review",
                "recommendation": "ADD",
                "thesis_status": "STRONGER",
            },
        },
        is_portfolio=True,
    )
    db_session.add(item)

    # User manually records a decision note after review
    user_note = DecisionLogEntry(
        user_id=user_id,
        instrument_id=inst_id,
        event_type=DecisionEventType.MANUAL_DECISION_NOTE,
        title="Decided to maintain current allocation without adding",
        summary="Acknowledged recommendation, choosing not to add due to portfolio sizing limits.",
        occurred_at=review_time + timedelta(minutes=5),
    )
    db_session.add(user_note)
    await db_session.commit()

    states = await briefing_service.resolve_item_attention_states(db_session, user_id, [item])
    assert states[item.id] == "RESOLVED"


@pytest.mark.asyncio
async def test_regression_11_matching_transaction_resolves_decision_required(
    client: AsyncClient, db_session: AsyncSession
):
    """11. Matching transaction (BUY for ADD/BUY, SELL for REDUCE/SELL) after review resolves DECISION_REQUIRED."""
    user_id, headers = await _create_test_user(client, "tx_matching_user")
    inst_id = await _create_test_asset(client, headers, "TX_INST")
    now = datetime.now(timezone.utc)
    review_time = now - timedelta(minutes=20)

    # Get asset created for user
    stmt = select(Asset).where(Asset.user_id == user_id, Asset.instrument_id == inst_id)
    res = await db_session.execute(stmt)
    asset = res.scalar_one()

    run = BriefingRun(
        user_id=user_id,
        generated_at=now,
        scope="PORTFOLIO_AND_WATCHLIST",
        status="COMPLETED",
        trigger_type=BriefingTriggerType.SCHEDULED,
        items_found=2,
        items_shown=2,
        items_filtered=0,
    )
    db_session.add(run)
    await db_session.flush()

    # Item with ADD recommendation
    item_add = BriefingItem(
        briefing_run_id=run.id,
        user_id=user_id,
        instrument_id=inst_id,
        headline="Expansion into new market",
        summary="Growth expansion.",
        why_it_matters="Thesis intact.",
        impact=BriefingImpact.POSITIVE,
        materiality=BriefingMateriality.HIGH,
        time_horizon=BriefingTimeHorizon.MEDIUM,
        thesis_impact=BriefingThesisImpact.STRONGER,
        review_required=True,
        category=BriefingCategory.OPERATIONAL,
        source_metadata={
            "review_status": "COMPLETED",
            "triggered_at": review_time.isoformat(),
            "review_summary": {
                "protocol": "thesis-review",
                "recommendation": "ADD",
                "thesis_status": "STRONGER",
            },
        },
        is_portfolio=True,
    )
    db_session.add(item_add)

    # Matching BUY transaction executed after review
    tx = Transaction(
        asset_id=asset.id,
        transaction_type=TransactionType.BUY,
        quantity=Decimal("10"),
        price_per_unit=Decimal("100"),
        total_amount=Decimal("1000"),
        transaction_currency="USD",
        transaction_date=now.date(),
        created_at=review_time + timedelta(minutes=10),
    )
    db_session.add(tx)
    await db_session.commit()

    states = await briefing_service.resolve_item_attention_states(db_session, user_id, [item_add])
    assert states[item_add.id] == "RESOLVED"

    # Also test SELL transaction resolving REDUCE
    item_reduce = BriefingItem(
        briefing_run_id=run.id,
        user_id=user_id,
        instrument_id=inst_id,
        headline="Margin compression alert",
        summary="Margins compress significantly.",
        why_it_matters="Position trim suggested.",
        impact=BriefingImpact.NEGATIVE,
        materiality=BriefingMateriality.HIGH,
        time_horizon=BriefingTimeHorizon.MEDIUM,
        thesis_impact=BriefingThesisImpact.WEAKER,
        review_required=True,
        category=BriefingCategory.EARNINGS,
        source_metadata={
            "review_status": "COMPLETED",
            "triggered_at": review_time.isoformat(),
            "review_summary": {
                "protocol": "valuation-update",
                "recommendation": "REDUCE",
                "thesis_status": "UNCHANGED",
            },
        },
        is_portfolio=True,
    )
    db_session.add(item_reduce)

    tx_sell = Transaction(
        asset_id=asset.id,
        transaction_type=TransactionType.SELL,
        quantity=Decimal("5"),
        price_per_unit=Decimal("100"),
        total_amount=Decimal("500"),
        transaction_currency="USD",
        transaction_date=now.date(),
        created_at=review_time + timedelta(minutes=12),
    )
    db_session.add(tx_sell)
    await db_session.commit()

    states_reduce = await briefing_service.resolve_item_attention_states(db_session, user_id, [item_reduce])
    assert states_reduce[item_reduce.id] == "RESOLVED"


@pytest.mark.asyncio
async def test_regression_12_historical_transaction_before_review_does_not_resolve_decision_required(
    client: AsyncClient, db_session: AsyncSession
):
    """12. Historical transaction occurring before review does NOT resolve DECISION_REQUIRED."""
    user_id, headers = await _create_test_user(client, "hist_tx_user")
    inst_id = await _create_test_asset(client, headers, "HIST_TX")
    now = datetime.now(timezone.utc)
    review_time = now + timedelta(seconds=2)

    stmt = select(Asset).where(Asset.user_id == user_id, Asset.instrument_id == inst_id)
    res = await db_session.execute(stmt)
    asset = res.scalar_one()

    # Historical BUY transaction from yesterday
    tx_hist = Transaction(
        asset_id=asset.id,
        transaction_type=TransactionType.BUY,
        quantity=Decimal("5"),
        price_per_unit=Decimal("50"),
        total_amount=Decimal("250"),
        transaction_currency="USD",
        transaction_date=(now - timedelta(days=1)).date(),
        created_at=now - timedelta(days=1),
    )
    db_session.add(tx_hist)

    run12 = BriefingRun(
        user_id=user_id,
        generated_at=now,
        scope="PORTFOLIO_AND_WATCHLIST",
        status="COMPLETED",
        trigger_type=BriefingTriggerType.SCHEDULED,
        items_found=1,
        items_shown=1,
        items_filtered=0,
    )
    db_session.add(run12)
    await db_session.flush()

    item = BriefingItem(
        briefing_run_id=run12.id,
        user_id=user_id,
        instrument_id=inst_id,
        headline="Fresh valuation milestone",
        summary="Valuation shows upside.",
        why_it_matters="Entry opportunity.",
        impact=BriefingImpact.POSITIVE,
        materiality=BriefingMateriality.HIGH,
        time_horizon=BriefingTimeHorizon.MEDIUM,
        thesis_impact=BriefingThesisImpact.STRONGER,
        review_required=True,
        category=BriefingCategory.EARNINGS,
        source_metadata={
            "review_status": "COMPLETED",
            "triggered_at": review_time.isoformat(),
            "review_summary": {
                "protocol": "valuation-update",
                "recommendation": "BUY",
                "thesis_status": "UNCHANGED",
            },
        },
        is_portfolio=True,
    )
    db_session.add(item)
    await db_session.commit()

    states = await briefing_service.resolve_item_attention_states(db_session, user_id, [item])
    assert states[item.id] == "DECISION_REQUIRED"


@pytest.mark.asyncio
async def test_regression_13_subsequent_hold_review_clears_stale_decision_attention(
    client: AsyncClient, db_session: AsyncSession
):
    """13. Subsequent authoritative review updating state to HOLD clears stale decision attention."""
    user_id, headers = await _create_test_user(client, "hold_clears_user")
    inst_id = await _create_test_asset(client, headers, "CLEAR_INST")
    now = datetime.now(timezone.utc)
    old_review_time = now - timedelta(days=2)
    new_review_time = now - timedelta(hours=1)

    run13 = BriefingRun(
        user_id=user_id,
        generated_at=now,
        scope="PORTFOLIO_AND_WATCHLIST",
        status="COMPLETED",
        trigger_type=BriefingTriggerType.SCHEDULED,
        items_found=1,
        items_shown=1,
        items_filtered=0,
    )
    db_session.add(run13)
    await db_session.flush()

    item = BriefingItem(
        briefing_run_id=run13.id,
        user_id=user_id,
        instrument_id=inst_id,
        headline="Old event that recommended REDUCE",
        summary="Temporary headwind.",
        why_it_matters="Position adjustment suggested.",
        impact=BriefingImpact.NEGATIVE,
        materiality=BriefingMateriality.HIGH,
        time_horizon=BriefingTimeHorizon.MEDIUM,
        thesis_impact=BriefingThesisImpact.WEAKER,
        review_required=True,
        category=BriefingCategory.EARNINGS,
        source_metadata={
            "review_status": "COMPLETED",
            "triggered_at": old_review_time.isoformat(),
            "review_summary": {
                "protocol": "valuation-update",
                "recommendation": "REDUCE",
                "thesis_status": "UNCHANGED",
            },
        },
        is_portfolio=True,
    )
    db_session.add(item)

    # Subsequent formal review at new_review_time settled recommendation back to HOLD
    state = InstrumentIntelligenceState(
        instrument_id=inst_id,
        recommendation=Recommendation.HOLD,
        thesis_status=ThesisStatus.UNCHANGED,
        valuation_status=ValuationStatus.FAIR,
        technical_status=TechnicalStatus.ON_TRACK,
        last_review_at=new_review_time,
    )
    db_session.add(state)
    await db_session.commit()

    states = await briefing_service.resolve_item_attention_states(db_session, user_id, [item])
    assert states[item.id] == "RESOLVED"


@pytest.mark.asyncio
async def test_regression_14_dashboard_attention_count_includes_decision_required(
    client: AsyncClient, db_session: AsyncSession
):
    """14. Dashboard attention count includes OPEN, REVIEWED_BUT_STILL_REQUIRES_ATTENTION, and DECISION_REQUIRED."""
    user_id, headers = await _create_test_user(client, "count_all_states")
    inst_id = await _create_test_asset(client, headers, "COUNT_ALL")
    now = datetime.now(timezone.utc)

    run = BriefingRun(
        user_id=user_id,
        generated_at=now,
        scope="PORTFOLIO_AND_WATCHLIST",
        status="COMPLETED",
        trigger_type=BriefingTriggerType.SCHEDULED,
        items_found=5,
        items_shown=5,
        items_filtered=0,
    )
    db_session.add(run)
    await db_session.flush()

    # 1. OPEN
    item1 = BriefingItem(
        briefing_run_id=run.id,
        user_id=user_id,
        instrument_id=inst_id,
        headline="Item 1: Open",
        summary="S1",
        why_it_matters="W1",
        impact=BriefingImpact.NEGATIVE,
        materiality=BriefingMateriality.HIGH,
        time_horizon=BriefingTimeHorizon.MEDIUM,
        thesis_impact=BriefingThesisImpact.WEAKER,
        review_required=True,
        category=BriefingCategory.EARNINGS,
        source_metadata=None,
        is_portfolio=True,
    )
    # 2. REVIEWED_BUT_STILL_REQUIRES_ATTENTION
    item2 = BriefingItem(
        briefing_run_id=run.id,
        user_id=user_id,
        instrument_id=inst_id,
        headline="Item 2: Needs Review Attention",
        summary="S2",
        why_it_matters="W2",
        impact=BriefingImpact.NEGATIVE,
        materiality=BriefingMateriality.HIGH,
        time_horizon=BriefingTimeHorizon.MEDIUM,
        thesis_impact=BriefingThesisImpact.WEAKER,
        review_required=True,
        category=BriefingCategory.EARNINGS,
        source_metadata={
            "review_status": "COMPLETED",
            "review_summary": {
                "recommendation": "REVIEW_REQUIRED",
                "thesis_status": "UNCHANGED",
            },
        },
        is_portfolio=True,
    )
    # 3. DECISION_REQUIRED
    item3 = BriefingItem(
        briefing_run_id=run.id,
        user_id=user_id,
        instrument_id=inst_id,
        headline="Item 3: Decision Needed",
        summary="S3",
        why_it_matters="W3",
        impact=BriefingImpact.POSITIVE,
        materiality=BriefingMateriality.HIGH,
        time_horizon=BriefingTimeHorizon.MEDIUM,
        thesis_impact=BriefingThesisImpact.STRONGER,
        review_required=True,
        category=BriefingCategory.EARNINGS,
        source_metadata={
            "review_status": "COMPLETED",
            "review_summary": {
                "recommendation": "ADD",
                "thesis_status": "STRONGER",
            },
        },
        is_portfolio=True,
    )
    # 4. RESOLVED
    item4 = BriefingItem(
        briefing_run_id=run.id,
        user_id=user_id,
        instrument_id=inst_id,
        headline="Item 4: Resolved",
        summary="S4",
        why_it_matters="W4",
        impact=BriefingImpact.POSITIVE,
        materiality=BriefingMateriality.HIGH,
        time_horizon=BriefingTimeHorizon.MEDIUM,
        thesis_impact=BriefingThesisImpact.STRONGER,
        review_required=True,
        category=BriefingCategory.EARNINGS,
        source_metadata={
            "review_status": "COMPLETED",
            "review_summary": {
                "recommendation": "HOLD",
                "thesis_status": "UNCHANGED",
            },
        },
        is_portfolio=True,
    )
    # 5. NONE
    item5 = BriefingItem(
        briefing_run_id=run.id,
        user_id=user_id,
        instrument_id=inst_id,
        headline="Item 5: News only",
        summary="S5",
        why_it_matters="W5",
        impact=BriefingImpact.NEUTRAL,
        materiality=BriefingMateriality.MEDIUM,
        time_horizon=BriefingTimeHorizon.MEDIUM,
        thesis_impact=BriefingThesisImpact.NOT_EVALUATED,
        review_required=False,
        category=BriefingCategory.GENERAL,
        source_metadata=None,
        is_portfolio=True,
    )
    db_session.add_all([item1, item2, item3, item4, item5])
    await db_session.commit()

    count = await briefing_service.get_briefing_attention_count(db_session, user_id)
    assert count == 3  # item1 (OPEN) + item2 (REVIEWED_BUT_STILL_REQUIRES_ATTENTION) + item3 (DECISION_REQUIRED)

    stats_resp = await client.get("/api/briefing/stats", headers=headers)
    assert stats_resp.status_code == 200
    assert stats_resp.json()["data"]["attention_count"] == 3


@pytest.mark.asyncio
async def test_regression_15_overlapping_scheduled_runs_preserve_decision_attention_state(
    client: AsyncClient, db_session: AsyncSession
):
    """15. Overlapping scheduled runs preserve decision attention state without reverting to OPEN."""
    user_id, headers = await _create_test_user(client, "overlap_decision_user")
    inst_id = await _create_test_asset(client, headers, "OVERLAP_DEC")

    mock_news = [
        MockNewsRecord(
            title="OVERLAP_DEC reports earnings beat and increases fiscal guidance",
            summary="Strong quarterly earnings beat reported with increased guidance.",
        )
    ]
    mock_assessment = BriefingAssessment(
        event_summary="Strong fundamentals and customer growth acceleration reported.",
        impact="POSITIVE",
        materiality="HIGH",
        time_horizon="MEDIUM",
        thesis_impact="STRONGER",
        review_required=True,
        why_it_matters="Breakthrough strengthens bull thesis.",
        recommended_review="thesis-review",
        confidence="HIGH",
    )
    mock_reasoner = MagicMock()
    mock_reasoner.assess_event.return_value = mock_assessment

    with patch("app.services.briefing.GoogleNewsRSSProvider") as MockNewsProvider, \
         patch("app.services.briefing.SECDisclosureProvider") as MockSecProvider:
        inst_news = MagicMock()
        inst_news.get_recent_news.return_value = mock_news
        MockNewsProvider.return_value = inst_news

        inst_sec = MagicMock()
        inst_sec.get_recent_disclosures.return_value = []
        MockSecProvider.return_value = inst_sec

        # 1. Initial run
        run1 = await briefing_service.generate_briefing_run(
            db=db_session, user_id=user_id, force_refresh=True, reasoner=mock_reasoner
        )
        item1 = run1.items[0]
        assert item1.attention_state == "OPEN"

        # 2. Run formal review producing actionable ADD
        mock_ai_result = AIExecutionResult(
            machine_record={
                "protocol": "thesis-review",
                "thesis_status": "STRONGER",
                "valuation_status": "ATTRACTIVE",
                "technical_status": "ON_TRACK",
                "recommendation": "ADD",
            },
            human_brief="Thesis strengthened; add to position recommended.",
            confidence="HIGH",
        )
        with patch("app.services.formal_review.load_protocol") as mock_load, \
             patch("app.services.formal_review.CodexCLIProvider") as MockProvider:
            proto_mock = MagicMock()
            proto_mock.canonical_name = "thesis-review"
            proto_mock.protocol_type = "deep_reasoning"
            proto_mock.description = "Thesis Review"
            mock_load.return_value = proto_mock

            provider_inst = MagicMock()
            provider_inst.execute.return_value = mock_ai_result
            MockProvider.return_value = provider_inst

            rev = await execute_briefing_formal_review(
                db=db_session, briefing_item_id=item1.id, user_id=user_id
            )
            assert rev["status"] == "COMPLETED"

        # 3. Subsequent run carries over completed review metadata and maintains DECISION_REQUIRED
        run2 = await briefing_service.generate_briefing_run(
            db=db_session,
            user_id=user_id,
            force_refresh=True,
            trigger_type=BriefingTriggerType.SCHEDULED,
            reasoner=mock_reasoner,
        )
        item2 = next(i for i in run2.items if i.headline == item1.headline)
        assert item2.attention_state == "DECISION_REQUIRED"
        assert item2.source_metadata.get("review_status") == "COMPLETED"


def test_timezone_validation_startup_rejects_invalid_iana():
    """7. ZoneInfo validation rejects invalid IANA timezone string with validation error."""
    from pydantic import ValidationError
    from app.config import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings(BRIEFING_SCHEDULE_TIMEZONE="Mars/Olympus")
    err_str = str(exc_info.value)
    assert "Invalid timezone" in err_str or "valid IANA timezone" in err_str


def test_scheduler_timezone_aware_trigger():
    """8. Scheduler evaluates trigger condition against configured Europe/Istanbul time."""
    test_sched = BriefingScheduler()
    tz_istanbul = zoneinfo.ZoneInfo("Europe/Istanbul")

    # 08:00 Istanbul time = 05:00 UTC
    dt_istanbul = datetime(2026, 9, 17, 8, 0, 0, tzinfo=tz_istanbul)
    dt_utc = dt_istanbul.astimezone(timezone.utc)

    # Both must evaluate to True when passed
    assert test_sched.should_trigger(dt_istanbul) is True
    assert test_sched.should_trigger(dt_utc) is True

    # 08:00 UTC = 11:00 Istanbul -> must NOT trigger
    dt_utc_8am = datetime(2026, 9, 17, 8, 0, 0, tzinfo=timezone.utc)
    assert test_sched.should_trigger(dt_utc_8am) is False


@pytest.mark.asyncio
async def test_cross_process_at_most_once_scheduled_run_skipped(
    client: AsyncClient, db_session: AsyncSession
):
    """9. A second scheduled run for the same user on the same calendar day returns the existing run."""
    user_id, headers = await _create_test_user(client, "at_most_once")
    await _create_test_asset(client, headers, "GOOGL")

    mock_news = [
        MockNewsRecord(
            title="Google announces cloud innovations",
            summary="Alphabet announced new AI cloud features.",
        )
    ]

    with patch("app.services.briefing.GoogleNewsRSSProvider") as MockNewsProvider, \
         patch("app.services.briefing.SECDisclosureProvider") as MockSecProvider:
        inst_news = MagicMock()
        inst_news.get_recent_news.return_value = mock_news
        MockNewsProvider.return_value = inst_news

        inst_sec = MagicMock()
        inst_sec.get_recent_disclosures.return_value = []
        MockSecProvider.return_value = inst_sec

        # First scheduled run: executes and creates run
        first_run = await run_scheduled_briefing_for_user(db=db_session, user_id=user_id)
        assert first_run is not None

        # Second scheduled run: detects existing run and skips re-execution
        second_run = await run_scheduled_briefing_for_user(db=db_session, user_id=user_id)
        assert second_run is not None
        assert second_run.id == first_run.id

        # Total scheduled runs in DB for this user must be exactly 1
        all_runs = (await db_session.execute(
            select(BriefingRun).where(
                BriefingRun.user_id == user_id,
                BriefingRun.trigger_type == BriefingTriggerType.SCHEDULED,
            )
        )).scalars().all()
        assert len(all_runs) == 1


@pytest.mark.asyncio
async def test_cross_process_at_most_once_does_not_block_manual_runs(
    client: AsyncClient, db_session: AsyncSession
):
    """10. Manual on-demand runs can still be triggered even after a scheduled run was executed today."""
    user_id, headers = await _create_test_user(client, "man_not_blocked")
    await _create_test_asset(client, headers, "AMZN")

    mock_news = [
        MockNewsRecord(
            title="Amazon launches new robotics system in warehouses",
            summary="Amazon announced automation advancements.",
        )
    ]

    with patch("app.services.briefing.GoogleNewsRSSProvider") as MockNewsProvider, \
         patch("app.services.briefing.SECDisclosureProvider") as MockSecProvider:
        inst_news = MagicMock()
        inst_news.get_recent_news.return_value = mock_news
        MockNewsProvider.return_value = inst_news

        inst_sec = MagicMock()
        inst_sec.get_recent_disclosures.return_value = []
        MockSecProvider.return_value = inst_sec

        # 1. Run scheduled cycle
        sched_run = await run_scheduled_briefing_for_user(db=db_session, user_id=user_id)
        assert sched_run is not None

        # 2. Manual run via API with force_refresh=True must NOT be blocked
        manual_resp = await client.post(
            "/api/briefing/generate",
            json={"scope": "PORTFOLIO_AND_WATCHLIST", "force_refresh": True},
            headers=headers,
        )
        assert manual_resp.status_code == 200
        manual_run = manual_resp.json()["data"]
        assert manual_run["id"] != str(sched_run.id)
        assert manual_run["trigger_type"] == "MANUAL"


@pytest.mark.asyncio
async def test_overlapping_evidence_window_carries_over_review_state(
    client: AsyncClient, db_session: AsyncSession
):
    """11. When an item is re-scanned in the 2h overlap window, its review_status is carried over."""
    user_id, headers = await _create_test_user(client, "overlap_carry")
    inst_id = await _create_test_asset(client, headers, "NVDA")

    mock_news = [
        MockNewsRecord(
            title="NVDA Nvidia reports earnings miss and cuts guidance significantly",
            summary="Nvidia quarterly earnings report showed revenue miss.",
        )
    ]

    mock_reasoner = MagicMock()
    mock_reasoner.assess_event.return_value = MagicMock(
        impact="NEGATIVE",
        materiality="HIGH",
        time_horizon="MEDIUM",
        thesis_impact="WEAKER",
        review_required=True,
        confidence="HIGH",
        recommended_review="EARNINGS_REVIEW",
        why_it_matters="Material guidance cut affecting thesis.",
    )

    with patch("app.services.briefing.GoogleNewsRSSProvider") as MockNewsProvider, \
         patch("app.services.briefing.SECDisclosureProvider") as MockSecProvider:
        inst_news = MagicMock()
        inst_news.get_recent_news.return_value = mock_news
        MockNewsProvider.return_value = inst_news

        inst_sec = MagicMock()
        inst_sec.get_recent_disclosures.return_value = []
        MockSecProvider.return_value = inst_sec

        # 1. Generate first briefing
        run1 = await briefing_service.generate_briefing_run(
            db=db_session, user_id=user_id, force_refresh=True, reasoner=mock_reasoner
        )
        assert len(run1.items) == 1
        item1 = run1.items[0]
        assert item1.attention_state == "OPEN"

        # 2. Complete review with resolving outcome (HOLD + UNCHANGED)
        mock_ai_result = AIExecutionResult(
            machine_record={
                "protocol": "earnings-review",
                "thesis_status": "UNCHANGED",
                "valuation_status": "FAIR",
                "technical_status": "ON_TRACK",
                "recommendation": "HOLD",
            },
            human_brief="Thesis confirmed post earnings update.",
            confidence="HIGH",
        )
        with patch("app.services.formal_review.load_protocol") as mock_load, \
             patch("app.services.formal_review.CodexCLIProvider") as MockProvider:
            proto_mock = MagicMock()
            proto_mock.canonical_name = "earnings-review"
            proto_mock.protocol_type = "deep_reasoning"
            proto_mock.description = "Earnings Review"
            mock_load.return_value = proto_mock

            provider_inst = MagicMock()
            provider_inst.execute.return_value = mock_ai_result
            MockProvider.return_value = provider_inst

            rev = await execute_briefing_formal_review(
                db=db_session, briefing_item_id=item1.id, user_id=user_id
            )
            assert rev["status"] == "COMPLETED"

        # 3. Simulate overlapping run 30 minutes later (same news item reappears in feed)
        run2 = await briefing_service.generate_briefing_run(
            db=db_session,
            user_id=user_id,
            force_refresh=True,
            trigger_type=BriefingTriggerType.MANUAL,
            reasoner=mock_reasoner,
        )
        # Item in run2 must have carried over the completed review and be RESOLVED, NOT revert to OPEN!
        item2 = next(i for i in run2.items if i.headline == item1.headline)
        assert item2.attention_state == "RESOLVED"
        assert item2.source_metadata.get("review_status") == "COMPLETED"
        assert item2.source_metadata.get("review_summary") is not None


def test_scheduler_info_metadata():
    """12. get_schedule_info() returns timezone, local target, UTC target, and next execution."""
    test_sched = BriefingScheduler()
    info = test_sched.get_schedule_info()
    assert info["timezone"] == "Europe/Istanbul"
    assert "08:00 Europe/Istanbul" in info["local_target"]
    assert "UTC" in info["utc_target"]
    assert "next_local_execution" in info
    assert "next_utc_execution" in info
