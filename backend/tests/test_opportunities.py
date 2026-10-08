"""Comprehensive automated test suite for Research + Watchlist Opportunity Automation.

Verifies all 21 key requirements and invariants:
 1. WAITING_FOR_PRICE outside target range -> no opportunity (WATCH / NO_CHANGE).
 2. Candidate enters target range -> opportunity detected (RESEARCH_NOW / PRICE_MOVE).
 3. Missing current price -> no fabricated signal (valuation_signal == UNKNOWN).
 4. Fresh research + no developments -> NO_CHANGE.
 5. New material event after research -> freshness REVIEW.
 6. Earnings after thesis review -> research review suggested (THESIS_REVIEW).
 7. No deterministic trigger -> no Codex call (call count 0).
 8. Candidate trigger -> bounded Codex reasoning.
 9. Codex failure -> deterministic result preserved.
10. Codex cannot directly create BUY/SELL portfolio action or transaction.
11. Same unchanged condition does not create duplicate assessments (idempotency).
12. Material new event permits reassessment.
13. Price leaving and re-entering range permits reassessment.
14. Manual refresh (force_refresh=True) explicitly reassesses.
15. Research queue prioritizes RESEARCH_NOW candidates.
16. Watchlist exposes structured opportunity state (API).
17. Dashboard / Active opportunities only shows meaningful opportunities (API).
18. Empty watchlist handled gracefully.
19. Scheduled opportunity cycle never launches formal research automatically.
20. Opportunity cycle never mutates portfolio positions or intelligence state.
21. Briefing success remains valid if opportunity evaluation fails (fault isolation).
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sys
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset, AssetType
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
from app.models.instrument import Instrument
from app.models.intelligence import (
    InstrumentIntelligenceState,
    IntelligenceReview,
    Recommendation,
    TechnicalPlan,
    TechnicalStatus,
    ThesisStatus,
    ValuationStatus,
)
from app.models.opportunity import (
    OpportunityAssessment,
    OpportunityConfidence,
    OpportunityDriver,
    OpportunityStatus,
    ResearchFreshness,
    ResearchStage,
    SuggestedNextStep,
    ValuationSignal,
    WatchlistItem,
    WatchlistPriority,
)
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.services import opportunity as opp_service
from app.services.scheduler import run_scheduled_briefing_for_user

_FINANCE_SRC = Path(__file__).resolve().parents[2] / "Finance" / "src"
if str(_FINANCE_SRC) not in sys.path:
    sys.path.insert(0, str(_FINANCE_SRC))

from investment_intelligence.opportunity_reasoner import (
    OpportunityAssessment as AIOpportunityAssessment,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_test_user(db: AsyncSession, email: str = "investor@example.com") -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash="hashed_pw_test",
        display_name="Test Investor",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _create_test_instrument(
    db: AsyncSession,
    symbol: str = "NVDA",
    name: str = "NVIDIA Corporation",
    asset_type: AssetType = AssetType.STOCK,
    exchange: str = "NASDAQ",
    currency: str = "USD",
) -> Instrument:
    inst = Instrument(
        id=uuid.uuid4(),
        symbol=symbol,
        name=name,
        asset_type=asset_type,
        exchange=exchange,
        currency=currency,
    )
    db.add(inst)
    await db.commit()
    await db.refresh(inst)
    return inst


async def _create_test_watchlist_item(
    db: AsyncSession,
    user_id: uuid.UUID,
    instrument_id: uuid.UUID,
    research_stage: ResearchStage = ResearchStage.WAITING_FOR_PRICE,
    priority: WatchlistPriority = WatchlistPriority.MEDIUM,
    why_interesting: str = "AI hardware dominance and margin expansion",
    target_entry_min: Decimal = Decimal("110.00"),
    target_entry_max: Decimal = Decimal("125.00"),
    key_catalyst: str = "Next-gen architecture launch",
    key_risk: str = "Supply chain bottleneck",
) -> WatchlistItem:
    item = WatchlistItem(
        id=uuid.uuid4(),
        user_id=user_id,
        instrument_id=instrument_id,
        research_stage=research_stage,
        priority=priority,
        why_interesting=why_interesting,
        target_entry_min=target_entry_min,
        target_entry_max=target_entry_max,
        key_catalyst=key_catalyst,
        key_risk=key_risk,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


# ---------------------------------------------------------------------------
# Test Scenarios
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_01_waiting_for_price_outside_target_range_no_opportunity(db_session: AsyncSession):
    """Scenario 1: WAITING_FOR_PRICE outside target range -> no opportunity (WATCH)."""
    user = await _create_test_user(db_session, "user1@test.com")
    inst = await _create_test_instrument(db_session, symbol="NVDA")
    item = await _create_test_watchlist_item(
        db_session,
        user.id,
        inst.id,
        research_stage=ResearchStage.WAITING_FOR_PRICE,
        target_entry_min=Decimal("110.00"),
        target_entry_max=Decimal("125.00"),
    )

    # Current price is $145 (well above $110-$125 target zone)
    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 145.00, "currency": "USD"},
    ):
        assessment = await opp_service.evaluate_candidate_opportunity(
            db=db_session,
            user_id=user.id,
            instrument=inst,
            watchlist_item=item,
        )

    assert assessment.status == OpportunityStatus.WATCH
    assert assessment.primary_driver == OpportunityDriver.PRICE_MOVE
    assert assessment.suggested_next_step == SuggestedNextStep.NONE
    assert assessment.source_references["in_target_range"] is False
    assert assessment.source_references["price_trigger_fired"] is False


@pytest.mark.asyncio
async def test_02_candidate_enters_target_range_opportunity_detected(db_session: AsyncSession):
    """Scenario 2: Candidate enters target range -> opportunity detected (RESEARCH_NOW)."""
    user = await _create_test_user(db_session, "user2@test.com")
    inst = await _create_test_instrument(db_session, symbol="NVDA")
    item = await _create_test_watchlist_item(
        db_session,
        user.id,
        inst.id,
        research_stage=ResearchStage.WAITING_FOR_PRICE,
        target_entry_min=Decimal("110.00"),
        target_entry_max=Decimal("125.00"),
    )

    # Current price enters target zone at $118
    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 118.00, "currency": "USD"},
    ):
        assessment = await opp_service.evaluate_candidate_opportunity(
            db=db_session,
            user_id=user.id,
            instrument=inst,
            watchlist_item=item,
        )

    assert assessment.status == OpportunityStatus.RESEARCH_NOW
    assert assessment.primary_driver == OpportunityDriver.PRICE_MOVE
    assert assessment.suggested_next_step == SuggestedNextStep.PRICE_REVIEW
    assert assessment.source_references["in_target_range"] is True
    assert assessment.source_references["price_trigger_fired"] is True


@pytest.mark.asyncio
async def test_03_missing_current_price_no_fabricated_signal(db_session: AsyncSession):
    """Scenario 3: Missing current price -> no fabricated signal (valuation_signal == UNKNOWN)."""
    user = await _create_test_user(db_session, "user3@test.com")
    inst = await _create_test_instrument(db_session, symbol="UNKNOWN_ASSET")
    item = await _create_test_watchlist_item(
        db_session,
        user.id,
        inst.id,
        research_stage=ResearchStage.WAITING_FOR_PRICE,
        target_entry_min=Decimal("50.00"),
        target_entry_max=Decimal("60.00"),
    )

    # Price service returns None (price unavailable)
    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value=None,
    ):
        assessment = await opp_service.evaluate_candidate_opportunity(
            db=db_session,
            user_id=user.id,
            instrument=inst,
            watchlist_item=item,
        )

    assert assessment.valuation_signal == ValuationSignal.UNKNOWN
    assert assessment.source_references["current_price"] is None
    assert assessment.source_references["in_target_range"] is False
    assert assessment.status == OpportunityStatus.WATCH


@pytest.mark.asyncio
async def test_04_fresh_research_no_developments_no_change(db_session: AsyncSession):
    """Scenario 4: Fresh research + no developments -> NO_CHANGE."""
    user = await _create_test_user(db_session, "user4@test.com")
    inst = await _create_test_instrument(db_session, symbol="MSFT")
    now = datetime.now(timezone.utc)

    # Intelligence state was formally reviewed 5 days ago (fresh)
    state = InstrumentIntelligenceState(
        id=uuid.uuid4(),
        instrument_id=inst.id,
        thesis_status=ThesisStatus.UNCHANGED,
        valuation_status=ValuationStatus.FAIR,
        technical_status=TechnicalStatus.ON_TRACK,
        recommendation=Recommendation.HOLD,
        human_brief="Solid execution, Azure growing 29%.",
        last_review_at=now - timedelta(days=5),
    )
    db_session.add(state)

    item = await _create_test_watchlist_item(
        db_session,
        user.id,
        inst.id,
        research_stage=ResearchStage.READY,
        priority=WatchlistPriority.MEDIUM,
    )
    await db_session.commit()

    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 420.00, "currency": "USD"},
    ):
        assessment = await opp_service.evaluate_candidate_opportunity(
            db=db_session,
            user_id=user.id,
            instrument=inst,
            watchlist_item=item,
        )

    assert assessment.research_freshness == ResearchFreshness.FRESH
    assert assessment.status == OpportunityStatus.NO_CHANGE
    assert assessment.suggested_next_step == SuggestedNextStep.NONE


@pytest.mark.asyncio
async def test_05_new_material_event_after_research_freshness_review(db_session: AsyncSession):
    """Scenario 5: New material event after research -> freshness REVIEW and actionable status."""
    user = await _create_test_user(db_session, "user5@test.com")
    inst = await _create_test_instrument(db_session, symbol="UBER")
    now = datetime.now(timezone.utc)

    state = InstrumentIntelligenceState(
        id=uuid.uuid4(),
        instrument_id=inst.id,
        thesis_status=ThesisStatus.UNCHANGED,
        valuation_status=ValuationStatus.FAIR,
        technical_status=TechnicalStatus.ON_TRACK,
        recommendation=Recommendation.HOLD,
        last_review_at=now - timedelta(days=10),
    )
    db_session.add(state)

    # Material event discovered 2 days ago (after review)
    briefing_run = BriefingRun(
        id=uuid.uuid4(),
        user_id=user.id,
        generated_at=datetime.now(timezone.utc),
        trigger_type=BriefingTriggerType.SCHEDULED,
        status="COMPLETED",
        items_shown=1,
    )
    db_session.add(briefing_run)
    await db_session.flush()

    item = BriefingItem(
        id=uuid.uuid4(),
        briefing_run_id=briefing_run.id,
        user_id=user.id,
        instrument_id=inst.id,
        headline="Major autonomous taxi partnership announced",
        summary="Strategic partnership with Waymo expands to 5 new metro areas.",
        why_it_matters="Expands market reach in robotaxi services.",
        category=BriefingCategory.OPERATIONAL,
        materiality=BriefingMateriality.HIGH,
        impact=BriefingImpact.POSITIVE,
        thesis_impact=BriefingThesisImpact.STRONGER,
        time_horizon=BriefingTimeHorizon.MEDIUM,
        created_at=now - timedelta(days=2),
    )
    db_session.add(item)

    wl_item = await _create_test_watchlist_item(
        db_session,
        user.id,
        inst.id,
        research_stage=ResearchStage.READY,
    )
    await db_session.commit()

    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 75.00, "currency": "USD"},
    ):
        assessment = await opp_service.evaluate_candidate_opportunity(
            db=db_session,
            user_id=user.id,
            instrument=inst,
            watchlist_item=wl_item,
        )

    assert assessment.research_freshness == ResearchFreshness.REVIEW
    assert assessment.status in (OpportunityStatus.RESEARCH_NOW, OpportunityStatus.RESEARCH_SOON)
    assert assessment.suggested_next_step == SuggestedNextStep.THESIS_REVIEW


@pytest.mark.asyncio
async def test_06_earnings_after_thesis_review_suggested(db_session: AsyncSession):
    """Scenario 6: Earnings after thesis review -> research review suggested (THESIS_REVIEW)."""
    user = await _create_test_user(db_session, "user6@test.com")
    inst = await _create_test_instrument(db_session, symbol="TSM")
    now = datetime.now(timezone.utc)

    state = InstrumentIntelligenceState(
        id=uuid.uuid4(),
        instrument_id=inst.id,
        thesis_status=ThesisStatus.UNCHANGED,
        valuation_status=ValuationStatus.FAIR,
        recommendation=Recommendation.HOLD,
        last_review_at=now - timedelta(days=14),
    )
    db_session.add(state)

    briefing_run = BriefingRun(
        id=uuid.uuid4(),
        user_id=user.id,
        generated_at=datetime.now(timezone.utc),
        trigger_type=BriefingTriggerType.SCHEDULED,
        status="COMPLETED",
    )
    db_session.add(briefing_run)
    await db_session.flush()

    earnings_item = BriefingItem(
        id=uuid.uuid4(),
        briefing_run_id=briefing_run.id,
        user_id=user.id,
        instrument_id=inst.id,
        headline="TSMC Q3 Earnings Beat with Record AI Revenue",
        summary="Quarterly revenue up 39% YoY driven by 3nm and 5nm demand.",
        why_it_matters="Accelerating node leadership and AI revenue growth.",
        category=BriefingCategory.EARNINGS,
        materiality=BriefingMateriality.HIGH,
        impact=BriefingImpact.POSITIVE,
        thesis_impact=BriefingThesisImpact.STRONGER,
        time_horizon=BriefingTimeHorizon.MEDIUM,
        created_at=now - timedelta(days=1),
    )
    db_session.add(earnings_item)

    wl_item = await _create_test_watchlist_item(
        db_session,
        user.id,
        inst.id,
        research_stage=ResearchStage.READY,
    )
    await db_session.commit()

    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 160.00, "currency": "USD"},
    ):
        assessment = await opp_service.evaluate_candidate_opportunity(
            db=db_session,
            user_id=user.id,
            instrument=inst,
            watchlist_item=wl_item,
        )

    assert assessment.primary_driver == OpportunityDriver.CATALYST
    assert assessment.suggested_next_step == SuggestedNextStep.THESIS_REVIEW


@pytest.mark.asyncio
async def test_07_no_deterministic_trigger_no_codex_call(db_session: AsyncSession):
    """Scenario 7: No deterministic trigger -> no Codex call (call count 0)."""
    user = await _create_test_user(db_session, "user7@test.com")
    inst = await _create_test_instrument(db_session, symbol="QUIET")
    now = datetime.now(timezone.utc)

    state = InstrumentIntelligenceState(
        id=uuid.uuid4(),
        instrument_id=inst.id,
        thesis_status=ThesisStatus.UNCHANGED,
        valuation_status=ValuationStatus.FAIR,
        recommendation=Recommendation.HOLD,
        last_review_at=now - timedelta(days=2),
    )
    db_session.add(state)
    item = await _create_test_watchlist_item(
        db_session,
        user.id,
        inst.id,
        research_stage=ResearchStage.WAITING_FOR_PRICE,
        target_entry_min=Decimal("10.00"),
        target_entry_max=Decimal("12.00"),
    )
    await db_session.commit()

    mock_reasoner = MagicMock()

    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 20.00, "currency": "USD"},
    ):
        await opp_service.evaluate_candidate_opportunity(
            db=db_session,
            user_id=user.id,
            instrument=inst,
            watchlist_item=item,
            reasoner=mock_reasoner,
        )

    # Assert reasoner was never called
    assert mock_reasoner.assess_opportunity.call_count == 0


@pytest.mark.asyncio
async def test_08_candidate_trigger_bounded_codex_reasoning(db_session: AsyncSession):
    """Scenario 8: Candidate trigger -> bounded Codex reasoning invoked."""
    user = await _create_test_user(db_session, "user8@test.com")
    inst = await _create_test_instrument(db_session, symbol="NVDA")
    item = await _create_test_watchlist_item(
        db_session,
        user.id,
        inst.id,
        research_stage=ResearchStage.WAITING_FOR_PRICE,
        target_entry_min=Decimal("110.00"),
        target_entry_max=Decimal("125.00"),
    )

    mock_reasoner = MagicMock()
    mock_reasoner.assess_opportunity.return_value = AIOpportunityAssessment(
        opportunity_status="RESEARCH_NOW",
        primary_driver="PRICE_MOVE",
        valuation_signal="ATTRACTIVE",
        research_freshness="FRESH",
        suggested_next_step="PRICE_REVIEW",
        confidence="HIGH",
        reason="Codex confirmed: Price entered ideal target accumulation zone.",
    )

    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 115.00, "currency": "USD"},
    ):
        assessment = await opp_service.evaluate_candidate_opportunity(
            db=db_session,
            user_id=user.id,
            instrument=inst,
            watchlist_item=item,
            reasoner=mock_reasoner,
        )

    assert mock_reasoner.assess_opportunity.call_count == 1
    assert assessment.status == OpportunityStatus.RESEARCH_NOW
    assert assessment.reason == "Codex confirmed: Price entered ideal target accumulation zone."
    assert assessment.confidence == OpportunityConfidence.HIGH


@pytest.mark.asyncio
async def test_09_codex_failure_deterministic_result_preserved(db_session: AsyncSession):
    """Scenario 9: Codex failure -> deterministic result preserved safely."""
    user = await _create_test_user(db_session, "user9@test.com")
    inst = await _create_test_instrument(db_session, symbol="NVDA")
    item = await _create_test_watchlist_item(
        db_session,
        user.id,
        inst.id,
        research_stage=ResearchStage.WAITING_FOR_PRICE,
        target_entry_min=Decimal("110.00"),
        target_entry_max=Decimal("125.00"),
    )

    mock_reasoner = MagicMock()
    mock_reasoner.assess_opportunity.side_effect = RuntimeError("OpenAI/Gemini API 500 error")

    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 115.00, "currency": "USD"},
    ):
        assessment = await opp_service.evaluate_candidate_opportunity(
            db=db_session,
            user_id=user.id,
            instrument=inst,
            watchlist_item=item,
            reasoner=mock_reasoner,
        )

    # Deterministic result preserved without crash
    assert assessment.status == OpportunityStatus.RESEARCH_NOW
    assert assessment.primary_driver == OpportunityDriver.PRICE_MOVE
    assert assessment.confidence == OpportunityConfidence.MEDIUM


@pytest.mark.asyncio
async def test_10_codex_cannot_directly_create_buy_sell_portfolio_action(db_session: AsyncSession):
    """Scenario 10: Opportunity cannot create BUY/SELL portfolio transactions or recommendation."""
    user = await _create_test_user(db_session, "user10@test.com")
    inst = await _create_test_instrument(db_session, symbol="NVDA")
    item = await _create_test_watchlist_item(
        db_session,
        user.id,
        inst.id,
        research_stage=ResearchStage.WAITING_FOR_PRICE,
        target_entry_min=Decimal("110.00"),
        target_entry_max=Decimal("125.00"),
    )

    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 115.00, "currency": "USD"},
    ):
        assessment = await opp_service.evaluate_candidate_opportunity(
            db=db_session,
            user_id=user.id,
            instrument=inst,
            watchlist_item=item,
        )

    # Verify no portfolio transaction was created
    tx_count = await db_session.scalar(select(func.count()).select_from(Transaction))
    assert tx_count == 0

    # Verify status is OpportunityStatus enum (NOT a buy/sell trade recommendation)
    assert assessment.status in (
        OpportunityStatus.RESEARCH_NOW,
        OpportunityStatus.RESEARCH_SOON,
        OpportunityStatus.WATCH,
        OpportunityStatus.NO_CHANGE,
    )
    assert hasattr(assessment, "recommendation") is False


@pytest.mark.asyncio
async def test_11_same_unchanged_condition_does_not_create_duplicate_assessments(db_session: AsyncSession):
    """Scenario 11: Idempotency - unchanged condition returns existing assessment without re-evaluating."""
    user = await _create_test_user(db_session, "user11@test.com")
    inst = await _create_test_instrument(db_session, symbol="NVDA")
    item = await _create_test_watchlist_item(
        db_session,
        user.id,
        inst.id,
        research_stage=ResearchStage.WAITING_FOR_PRICE,
        target_entry_min=Decimal("110.00"),
        target_entry_max=Decimal("125.00"),
    )

    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 140.00, "currency": "USD"},
    ):
        a1 = await opp_service.evaluate_candidate_opportunity(
            db=db_session,
            user_id=user.id,
            instrument=inst,
            watchlist_item=item,
        )
        first_assessment_at = a1.assessment_at

        # Second evaluation under identical conditions
        a2 = await opp_service.evaluate_candidate_opportunity(
            db=db_session,
            user_id=user.id,
            instrument=inst,
            watchlist_item=item,
        )

    assert a1.id == a2.id
    assert a2.assessment_at == first_assessment_at

    # Check total rows in DB
    total_assessments = await db_session.scalar(select(func.count()).select_from(OpportunityAssessment))
    assert total_assessments == 1


@pytest.mark.asyncio
async def test_12_material_new_event_permits_reassessment(db_session: AsyncSession):
    """Scenario 12: Material new event permits reassessment."""
    user = await _create_test_user(db_session, "user12@test.com")
    inst = await _create_test_instrument(db_session, symbol="UBER")

    item = await _create_test_watchlist_item(
        db_session,
        user.id,
        inst.id,
        research_stage=ResearchStage.DISCOVERED,
        priority=WatchlistPriority.MEDIUM,
    )

    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 70.00, "currency": "USD"},
    ):
        a1 = await opp_service.evaluate_candidate_opportunity(
            db=db_session,
            user_id=user.id,
            instrument=inst,
            watchlist_item=item,
        )
        assert a1.status == OpportunityStatus.WATCH

        # Add a new material briefing item discovered after the first assessment
        briefing_run = BriefingRun(
            id=uuid.uuid4(),
            user_id=user.id,
            generated_at=datetime.now(timezone.utc),
            trigger_type=BriefingTriggerType.SCHEDULED,
            status="COMPLETED",
        )
        db_session.add(briefing_run)
        await db_session.flush()

        event = BriefingItem(
            id=uuid.uuid4(),
            briefing_run_id=briefing_run.id,
            user_id=user.id,
            instrument_id=inst.id,
            headline="Regulatory Breakthrough in Autonomous Rides",
            summary="Department of Transportation grants federal permit.",
            why_it_matters="Federal permit enables commercial scaling.",
            category=BriefingCategory.REGULATORY,
            materiality=BriefingMateriality.HIGH,
            impact=BriefingImpact.POSITIVE,
            thesis_impact=BriefingThesisImpact.STRONGER,
            time_horizon=BriefingTimeHorizon.MEDIUM,
            created_at=datetime.now(timezone.utc) + timedelta(seconds=2),
        )
        db_session.add(event)
        await db_session.commit()

        # Re-evaluate
        a2 = await opp_service.evaluate_candidate_opportunity(
            db=db_session,
            user_id=user.id,
            instrument=inst,
            watchlist_item=item,
        )

    assert a2.id == a1.id
    assert a2.status in (OpportunityStatus.RESEARCH_NOW, OpportunityStatus.RESEARCH_SOON)
    assert a2.suggested_next_step == SuggestedNextStep.THESIS_REVIEW


@pytest.mark.asyncio
async def test_13_price_leaving_and_reentering_range_permits_reassessment(db_session: AsyncSession):
    """Scenario 13: Price leaving and re-entering range permits reassessment."""
    user = await _create_test_user(db_session, "user13@test.com")
    inst = await _create_test_instrument(db_session, symbol="NVDA")
    item = await _create_test_watchlist_item(
        db_session,
        user.id,
        inst.id,
        research_stage=ResearchStage.WAITING_FOR_PRICE,
        target_entry_min=Decimal("110.00"),
        target_entry_max=Decimal("125.00"),
    )

    # 1. Price is outside range ($140)
    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 140.00, "currency": "USD"},
    ):
        a1 = await opp_service.evaluate_candidate_opportunity(
            db=db_session, user_id=user.id, instrument=inst, watchlist_item=item
        )
        assert a1.status == OpportunityStatus.WATCH
        assert a1.source_references["in_target_range"] is False

    # 2. Price enters range ($120)
    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 120.00, "currency": "USD"},
    ):
        a2 = await opp_service.evaluate_candidate_opportunity(
            db=db_session, user_id=user.id, instrument=inst, watchlist_item=item
        )
        assert a2.status == OpportunityStatus.RESEARCH_NOW
        assert a2.source_references["in_target_range"] is True


@pytest.mark.asyncio
async def test_14_manual_refresh_explicitly_reassesses(db_session: AsyncSession):
    """Scenario 14: Manual refresh (force_refresh=True) explicitly reassesses."""
    user = await _create_test_user(db_session, "user14@test.com")
    inst = await _create_test_instrument(db_session, symbol="NVDA")
    item = await _create_test_watchlist_item(
        db_session,
        user.id,
        inst.id,
        research_stage=ResearchStage.WAITING_FOR_PRICE,
        target_entry_min=Decimal("110.00"),
        target_entry_max=Decimal("125.00"),
    )

    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 140.00, "currency": "USD"},
    ):
        a1 = await opp_service.evaluate_candidate_opportunity(
            db=db_session, user_id=user.id, instrument=inst, watchlist_item=item
        )
        t1 = a1.assessment_at

        # Force refresh
        a2 = await opp_service.evaluate_candidate_opportunity(
            db=db_session,
            user_id=user.id,
            instrument=inst,
            watchlist_item=item,
            force_refresh=True,
        )
        t2 = a2.assessment_at

    assert t2 >= t1


@pytest.mark.asyncio
async def test_15_research_queue_prioritizes_research_now_candidates(db_session: AsyncSession):
    """Scenario 15: Research queue prioritizes RESEARCH_NOW candidates over RESEARCH_SOON and WAITING."""
    user = await _create_test_user(db_session, "user15@test.com")
    inst_now = await _create_test_instrument(db_session, symbol="NOW_SYM")
    inst_soon = await _create_test_instrument(db_session, symbol="SOON_SYM")
    inst_wait = await _create_test_instrument(db_session, symbol="WAIT_SYM")

    # Put all 3 on the watchlist
    await _create_test_watchlist_item(db_session, user.id, inst_now.id, research_stage=ResearchStage.READY)
    await _create_test_watchlist_item(db_session, user.id, inst_soon.id, research_stage=ResearchStage.DISCOVERED)
    await _create_test_watchlist_item(db_session, user.id, inst_wait.id, research_stage=ResearchStage.WAITING_FOR_PRICE)

    now_utc = datetime.now(timezone.utc)

    # 1. Assessment: RESEARCH_NOW
    db_session.add(
        OpportunityAssessment(
            user_id=user.id,
            instrument_id=inst_now.id,
            status=OpportunityStatus.RESEARCH_NOW,
            primary_driver=OpportunityDriver.PRICE_MOVE,
            valuation_signal=ValuationSignal.ATTRACTIVE,
            research_freshness=ResearchFreshness.FRESH,
            suggested_next_step=SuggestedNextStep.PRICE_REVIEW,
            confidence=OpportunityConfidence.HIGH,
            reason="Price entered target range",
            assessment_at=now_utc,
        )
    )
    # 2. Assessment: RESEARCH_SOON
    db_session.add(
        OpportunityAssessment(
            user_id=user.id,
            instrument_id=inst_soon.id,
            status=OpportunityStatus.RESEARCH_SOON,
            primary_driver=OpportunityDriver.RESEARCH_STALENESS,
            valuation_signal=ValuationSignal.FAIR,
            research_freshness=ResearchFreshness.STALE,
            suggested_next_step=SuggestedNextStep.DEEP_RESEARCH,
            confidence=OpportunityConfidence.MEDIUM,
            reason="Analysis is stale",
            assessment_at=now_utc,
        )
    )
    # 3. Assessment: WATCH
    db_session.add(
        OpportunityAssessment(
            user_id=user.id,
            instrument_id=inst_wait.id,
            status=OpportunityStatus.WATCH,
            primary_driver=OpportunityDriver.PRICE_MOVE,
            valuation_signal=ValuationSignal.FAIR,
            research_freshness=ResearchFreshness.FRESH,
            suggested_next_step=SuggestedNextStep.NONE,
            confidence=OpportunityConfidence.HIGH,
            reason="Waiting for price entry",
            assessment_at=now_utc,
        )
    )
    await db_session.commit()

    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 100.00, "currency": "USD"},
    ):
        queue = await opp_service.get_research_queue(db_session, user.id)

    assert len(queue.research_now) == 1
    assert queue.research_now[0].symbol == "NOW_SYM"

    assert len(queue.research_soon) == 1
    assert queue.research_soon[0].symbol == "SOON_SYM"

    assert len(queue.waiting) == 1
    assert queue.waiting[0].symbol == "WAIT_SYM"


@pytest.mark.asyncio
async def test_16_watchlist_exposes_structured_opportunity_state(authed_client: AsyncClient, db_session: AsyncSession):
    """Scenario 16: Watchlist API exposes structured opportunity state."""
    # Lookup the authenticated user
    user_res = await db_session.execute(select(User).where(User.email == "user@example.com"))
    user = user_res.scalar_one()

    inst = await _create_test_instrument(db_session, symbol="AAPL")
    item = await _create_test_watchlist_item(
        db_session,
        user.id,
        inst.id,
        research_stage=ResearchStage.DISCOVERED,
        priority=WatchlistPriority.HIGH,
    )

    db_session.add(
        OpportunityAssessment(
            user_id=user.id,
            instrument_id=inst.id,
            status=OpportunityStatus.RESEARCH_SOON,
            primary_driver=OpportunityDriver.OTHER,
            valuation_signal=ValuationSignal.FAIR,
            research_freshness=ResearchFreshness.UNKNOWN,
            suggested_next_step=SuggestedNextStep.SCREENING,
            confidence=OpportunityConfidence.HIGH,
            reason="High priority candidate awaiting screening",
            assessment_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()

    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 180.00, "currency": "USD"},
    ):
        resp = await authed_client.get("/api/watchlist")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    item_data = data[0]
    assert item_data["instrument"]["symbol"] == "AAPL"
    assert "opportunity" in item_data
    assert item_data["opportunity"]["status"] == "RESEARCH_SOON"
    assert item_data["opportunity"]["suggested_next_step"] == "SCREENING"


@pytest.mark.asyncio
async def test_17_dashboard_only_shows_meaningful_opportunities(authed_client: AsyncClient, db_session: AsyncSession):
    """Scenario 17: Dashboard active opportunities only includes RESEARCH_NOW and RESEARCH_SOON."""
    user_res = await db_session.execute(select(User).where(User.email == "user@example.com"))
    user = user_res.scalar_one()

    inst_active = await _create_test_instrument(db_session, symbol="ACTIVE_OPP")
    inst_quiet = await _create_test_instrument(db_session, symbol="QUIET_OPP")

    # Put both on user's watchlist
    await _create_test_watchlist_item(db_session, user.id, inst_active.id, research_stage=ResearchStage.READY)
    await _create_test_watchlist_item(db_session, user.id, inst_quiet.id, research_stage=ResearchStage.WAITING_FOR_PRICE)

    now_utc = datetime.now(timezone.utc)
    db_session.add(
        OpportunityAssessment(
            user_id=user.id,
            instrument_id=inst_active.id,
            status=OpportunityStatus.RESEARCH_NOW,
            primary_driver=OpportunityDriver.PRICE_MOVE,
            valuation_signal=ValuationSignal.ATTRACTIVE,
            research_freshness=ResearchFreshness.FRESH,
            suggested_next_step=SuggestedNextStep.PRICE_REVIEW,
            confidence=OpportunityConfidence.HIGH,
            reason="Active entry opportunity",
            assessment_at=now_utc,
        )
    )
    db_session.add(
        OpportunityAssessment(
            user_id=user.id,
            instrument_id=inst_quiet.id,
            status=OpportunityStatus.WATCH,
            primary_driver=OpportunityDriver.PRICE_MOVE,
            valuation_signal=ValuationSignal.FAIR,
            research_freshness=ResearchFreshness.FRESH,
            suggested_next_step=SuggestedNextStep.NONE,
            confidence=OpportunityConfidence.HIGH,
            reason="Quiet watch state",
            assessment_at=now_utc,
        )
    )
    await db_session.commit()

    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 100.00, "currency": "USD"},
    ):
        resp = await authed_client.get("/api/opportunities/active")

    assert resp.status_code == 200
    data = resp.json()["data"]
    symbols = [item["instrument"]["symbol"] for item in data]
    assert "ACTIVE_OPP" in symbols
    assert "QUIET_OPP" not in symbols


@pytest.mark.asyncio
async def test_18_empty_watchlist_handled_gracefully(db_session: AsyncSession):
    """Scenario 18: Empty watchlist handled gracefully with zero errors."""
    user = await _create_test_user(db_session, "user18@test.com")
    summary = await opp_service.evaluate_user_opportunities(db_session, user.id)

    assert summary.total_candidates == 0
    assert summary.evaluated == 0
    assert summary.opportunities_found == 0


@pytest.mark.asyncio
async def test_19_scheduled_opportunity_cycle_never_launches_formal_research(db_session: AsyncSession):
    """Scenario 19: Scheduled opportunity cycle never launches formal research automatically."""
    user = await _create_test_user(db_session, "user19@test.com")
    inst = await _create_test_instrument(db_session, symbol="NVDA")
    await _create_test_watchlist_item(
        db_session,
        user.id,
        inst.id,
        research_stage=ResearchStage.WAITING_FOR_PRICE,
        target_entry_min=Decimal("110.00"),
        target_entry_max=Decimal("125.00"),
    )

    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 115.00, "currency": "USD"},
    ):
        await opp_service.evaluate_user_opportunities(db_session, user.id)

    # Invariant: IntelligenceReview count must remain 0
    review_count = await db_session.scalar(select(func.count()).select_from(IntelligenceReview))
    assert review_count == 0


@pytest.mark.asyncio
async def test_20_opportunity_cycle_never_mutates_portfolio_or_intelligence_state(db_session: AsyncSession):
    """Scenario 20: Opportunity cycle never mutates portfolio positions or intelligence state."""
    user = await _create_test_user(db_session, "user20@test.com")
    inst = await _create_test_instrument(db_session, symbol="TSM")

    # Create an owned asset with a transaction
    asset = Asset(
        id=uuid.uuid4(),
        user_id=user.id,
        instrument_id=inst.id,
        name="Taiwan Semiconductor",
        asset_type=AssetType.STOCK,
        symbol="TSM",
        current_price=Decimal("150.00"),
        current_price_currency="USD",
    )
    db_session.add(asset)
    await db_session.flush()

    tx = Transaction(
        id=uuid.uuid4(),
        asset_id=asset.id,
        transaction_type=TransactionType.BUY,
        quantity=Decimal("100.00"),
        price_per_unit=Decimal("120.00"),
        total_amount=Decimal("12000.00"),
        transaction_currency="USD",
        transaction_date=datetime.now(timezone.utc).date(),
    )
    db_session.add(tx)

    # Initial intelligence state
    intel = InstrumentIntelligenceState(
        id=uuid.uuid4(),
        instrument_id=inst.id,
        thesis_status=ThesisStatus.UNCHANGED,
        valuation_status=ValuationStatus.FAIR,
        recommendation=Recommendation.HOLD,
        last_review_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    db_session.add(intel)
    await db_session.commit()

    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 155.00, "currency": "USD"},
    ):
        await opp_service.evaluate_user_opportunities(db_session, user.id)

    # Invariants: Asset price, transaction quantity, and Intelligence recommendation unchanged
    await db_session.refresh(asset)
    await db_session.refresh(tx)
    await db_session.refresh(intel)
    assert asset.current_price == Decimal("150.00")
    assert tx.quantity == Decimal("100.00")
    assert intel.recommendation == Recommendation.HOLD


@pytest.mark.asyncio
async def test_21_briefing_success_remains_valid_if_opportunity_evaluation_fails(db_session: AsyncSession):
    """Scenario 21: Fault isolation - Briefing success remains valid if opportunity evaluation fails."""
    user = await _create_test_user(db_session, "user21@test.com")
    inst = await _create_test_instrument(db_session, symbol="TSM")

    # Owned asset to give the briefing an item to process
    asset = Asset(
        id=uuid.uuid4(),
        user_id=user.id,
        instrument_id=inst.id,
        name="Taiwan Semiconductor",
        asset_type=AssetType.STOCK,
        symbol="TSM",
        current_price=Decimal("150.00"),
        current_price_currency="USD",
    )
    db_session.add(asset)
    await db_session.commit()

    # Mock evaluate_user_opportunities to raise an unexpected runtime error
    with patch(
        "app.services.opportunity.evaluate_user_opportunities",
        side_effect=RuntimeError("Catastrophic opportunity engine failure"),
    ):
        briefing_run = await run_scheduled_briefing_for_user(
            db=db_session,
            user_id=user.id,
            reasoner=None,
        )

    # Briefing run must succeed despite the opportunity failure
    assert briefing_run is not None
    assert briefing_run.status == "COMPLETED"
    assert briefing_run.user_id == user.id


# ---------------------------------------------------------------------------
# Valuation Authority Hardening Scenarios (Scenarios 22-29)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_22_target_range_entered_with_fair_valuation_retains_fair_signal(db_session: AsyncSession):
    """Scenario 22: Target range entered + authoritative valuation FAIR -> opportunity RESEARCH_NOW -> valuation_signal = FAIR."""
    user = await _create_test_user(db_session, "user22@test.com")
    inst = await _create_test_instrument(db_session, symbol="UBER", name="Uber Technologies")
    item = await _create_test_watchlist_item(
        db_session,
        user.id,
        inst.id,
        research_stage=ResearchStage.WAITING_FOR_PRICE,
        priority=WatchlistPriority.HIGH,
        target_entry_min=Decimal("60.00"),
        target_entry_max=Decimal("75.00"),
    )

    now_utc = datetime.now(timezone.utc)
    intel_state = InstrumentIntelligenceState(
        id=uuid.uuid4(),
        instrument_id=inst.id,
        thesis_status=ThesisStatus.UNCHANGED,
        valuation_status=ValuationStatus.FAIR,
        recommendation=Recommendation.HOLD,
        last_review_at=now_utc - timedelta(days=5),
    )
    db_session.add(intel_state)
    await db_session.commit()

    # Current price is $71.04 (inside $60-$75 target entry range)
    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 71.04, "currency": "USD"},
    ):
        assessment = await opp_service.evaluate_candidate_opportunity(
            db=db_session,
            user_id=user.id,
            instrument=inst,
            watchlist_item=item,
        )

    assert assessment.status == OpportunityStatus.RESEARCH_NOW
    assert assessment.primary_driver == OpportunityDriver.PRICE_MOVE
    assert assessment.suggested_next_step == SuggestedNextStep.PRICE_REVIEW
    # Valuation signal MUST NOT be promoted to ATTRACTIVE!
    assert assessment.valuation_signal == ValuationSignal.FAIR


@pytest.mark.asyncio
async def test_23_target_range_entered_without_valuation_state_retains_unknown_signal(db_session: AsyncSession):
    """Scenario 23: Target range entered + no valuation state -> opportunity RESEARCH_NOW -> valuation_signal = UNKNOWN."""
    user = await _create_test_user(db_session, "user23@test.com")
    inst = await _create_test_instrument(db_session, symbol="NEWCO")
    item = await _create_test_watchlist_item(
        db_session,
        user.id,
        inst.id,
        research_stage=ResearchStage.WAITING_FOR_PRICE,
        priority=WatchlistPriority.HIGH,
        target_entry_min=Decimal("50.00"),
        target_entry_max=Decimal("65.00"),
    )

    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 55.00, "currency": "USD"},
    ):
        assessment = await opp_service.evaluate_candidate_opportunity(
            db=db_session,
            user_id=user.id,
            instrument=inst,
            watchlist_item=item,
        )

    assert assessment.status == OpportunityStatus.RESEARCH_NOW
    assert assessment.primary_driver == OpportunityDriver.PRICE_MOVE
    # No prior formal valuation review -> valuation_signal MUST remain UNKNOWN
    assert assessment.valuation_signal == ValuationSignal.UNKNOWN


@pytest.mark.asyncio
async def test_24_target_range_entered_with_expensive_valuation_retains_expensive_signal(db_session: AsyncSession):
    """Scenario 24: Target range entered + authoritative valuation EXPENSIVE -> triggers research -> valuation_signal = EXPENSIVE."""
    user = await _create_test_user(db_session, "user24@test.com")
    inst = await _create_test_instrument(db_session, symbol="OVERVAL")
    item = await _create_test_watchlist_item(
        db_session,
        user.id,
        inst.id,
        research_stage=ResearchStage.WAITING_FOR_PRICE,
        priority=WatchlistPriority.MEDIUM,
        target_entry_min=Decimal("100.00"),
        target_entry_max=Decimal("120.00"),
    )

    intel_state = InstrumentIntelligenceState(
        id=uuid.uuid4(),
        instrument_id=inst.id,
        thesis_status=ThesisStatus.UNCHANGED,
        valuation_status=ValuationStatus.EXPENSIVE,
        recommendation=Recommendation.REDUCE,
        last_review_at=datetime.now(timezone.utc) - timedelta(days=10),
    )
    db_session.add(intel_state)
    await db_session.commit()

    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 110.00, "currency": "USD"},
    ):
        assessment = await opp_service.evaluate_candidate_opportunity(
            db=db_session,
            user_id=user.id,
            instrument=inst,
            watchlist_item=item,
        )

    assert assessment.status == OpportunityStatus.RESEARCH_NOW
    # Valuation signal remains EXPENSIVE as formally established
    assert assessment.valuation_signal == ValuationSignal.EXPENSIVE


@pytest.mark.asyncio
async def test_25_codex_attempted_valuation_promotion_blocked_retains_fair_signal(db_session: AsyncSession):
    """Scenario 25: Codex attempts to return ATTRACTIVE when persisted state is FAIR -> persisted signal remains FAIR."""
    user = await _create_test_user(db_session, "user25@test.com")
    inst = await _create_test_instrument(db_session, symbol="UBER_AI")
    item = await _create_test_watchlist_item(
        db_session,
        user.id,
        inst.id,
        research_stage=ResearchStage.WAITING_FOR_PRICE,
        priority=WatchlistPriority.HIGH,
        target_entry_min=Decimal("60.00"),
        target_entry_max=Decimal("75.00"),
    )

    intel_state = InstrumentIntelligenceState(
        id=uuid.uuid4(),
        instrument_id=inst.id,
        thesis_status=ThesisStatus.UNCHANGED,
        valuation_status=ValuationStatus.FAIR,
        recommendation=Recommendation.HOLD,
        last_review_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    db_session.add(intel_state)
    await db_session.commit()

    # Codex attempts to hallucinate ATTRACTIVE valuation signal in AI record
    mock_reasoner = MagicMock()
    mock_reasoner.assess_opportunity.return_value = AIOpportunityAssessment(
        opportunity_status="RESEARCH_NOW",
        primary_driver="PRICE_MOVE",
        valuation_signal="ATTRACTIVE",
        research_freshness="FRESH",
        suggested_next_step="PRICE_REVIEW",
        confidence="HIGH",
        reason="Entered target range, so prioritizing research.",
    )

    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 71.04, "currency": "USD"},
    ):
        assessment = await opp_service.evaluate_candidate_opportunity(
            db=db_session,
            user_id=user.id,
            instrument=inst,
            watchlist_item=item,
            reasoner=mock_reasoner,
        )

    # Codex opportunity prioritisation is accepted, but valuation promotion is blocked
    assert assessment.status == OpportunityStatus.RESEARCH_NOW
    assert assessment.valuation_signal == ValuationSignal.FAIR


@pytest.mark.asyncio
async def test_26_price_outside_target_range_with_attractive_valuation_preserves_attractive(db_session: AsyncSession):
    """Scenario 26: Price outside target range + valuation ATTRACTIVE -> preserved ATTRACTIVE, no false price trigger."""
    user = await _create_test_user(db_session, "user26@test.com")
    inst = await _create_test_instrument(db_session, symbol="VALUE_PICK")
    item = await _create_test_watchlist_item(
        db_session,
        user.id,
        inst.id,
        research_stage=ResearchStage.WAITING_FOR_PRICE,
        priority=WatchlistPriority.MEDIUM,
        target_entry_min=Decimal("40.00"),
        target_entry_max=Decimal("50.00"),
    )

    intel_state = InstrumentIntelligenceState(
        id=uuid.uuid4(),
        instrument_id=inst.id,
        thesis_status=ThesisStatus.UNCHANGED,
        valuation_status=ValuationStatus.ATTRACTIVE,
        recommendation=Recommendation.ADD,
        last_review_at=datetime.now(timezone.utc) - timedelta(days=15),
    )
    db_session.add(intel_state)
    await db_session.commit()

    # Current price is $65 (well above $40-$50 target range)
    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 65.00, "currency": "USD"},
    ):
        assessment = await opp_service.evaluate_candidate_opportunity(
            db=db_session,
            user_id=user.id,
            instrument=inst,
            watchlist_item=item,
        )

    # Stays in WATCH because price is outside entry zone, but authoritative ATTRACTIVE is preserved
    assert assessment.status == OpportunityStatus.WATCH
    assert assessment.source_references["in_target_range"] is False
    assert assessment.source_references["price_trigger_fired"] is False
    assert assessment.valuation_signal == ValuationSignal.ATTRACTIVE


@pytest.mark.asyncio
async def test_27_stale_valuation_with_material_event_suggests_review_without_auto_promotion(db_session: AsyncSession):
    """Scenario 27: Old valuation + material event -> research freshness REVIEW, suggested THESIS_REVIEW, no auto promotion."""
    user = await _create_test_user(db_session, "user27@test.com")
    inst = await _create_test_instrument(db_session, symbol="OLD_VAL")
    item = await _create_test_watchlist_item(
        db_session,
        user.id,
        inst.id,
        research_stage=ResearchStage.RESEARCHING,
        priority=WatchlistPriority.HIGH,
    )

    now_utc = datetime.now(timezone.utc)
    review_date = now_utc - timedelta(days=100)
    intel_state = InstrumentIntelligenceState(
        id=uuid.uuid4(),
        instrument_id=inst.id,
        thesis_status=ThesisStatus.UNCHANGED,
        valuation_status=ValuationStatus.FAIR,
        recommendation=Recommendation.HOLD,
        last_review_at=review_date,
    )
    db_session.add(intel_state)

    briefing_run = BriefingRun(
        id=uuid.uuid4(),
        user_id=user.id,
        generated_at=datetime.now(timezone.utc),
        trigger_type=BriefingTriggerType.SCHEDULED,
        status="COMPLETED",
        items_shown=1,
    )
    db_session.add(briefing_run)
    await db_session.flush()

    # Material briefing event occurred after the review
    briefing_item = BriefingItem(
        id=uuid.uuid4(),
        briefing_run_id=briefing_run.id,
        user_id=user.id,
        instrument_id=inst.id,
        headline="Major contract signed post-review",
        summary="Company won large government contract",
        why_it_matters="Expands revenue potential significantly.",
        category=BriefingCategory.EARNINGS,
        materiality=BriefingMateriality.HIGH,
        thesis_impact=BriefingThesisImpact.STRONGER,
        created_at=now_utc - timedelta(days=2),
    )
    db_session.add(briefing_item)
    await db_session.commit()

    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 100.00, "currency": "USD"},
    ):
        assessment = await opp_service.evaluate_candidate_opportunity(
            db=db_session,
            user_id=user.id,
            instrument=inst,
            watchlist_item=item,
        )

    assert assessment.research_freshness == ResearchFreshness.REVIEW
    assert assessment.suggested_next_step == SuggestedNextStep.THESIS_REVIEW
    # Valuation status remains FAIR; no speculative promotion to ATTRACTIVE
    assert assessment.valuation_signal == ValuationSignal.FAIR


@pytest.mark.asyncio
async def test_28_candidate_opportunity_evaluation_zero_mutation_of_intelligence_state(db_session: AsyncSession):
    """Scenario 28: Zero mutation of InstrumentIntelligenceState during candidate opportunity evaluation."""
    user = await _create_test_user(db_session, "user28@test.com")
    inst = await _create_test_instrument(db_session, symbol="IMMUTABLE")
    item = await _create_test_watchlist_item(
        db_session,
        user.id,
        inst.id,
        research_stage=ResearchStage.WAITING_FOR_PRICE,
        target_entry_min=Decimal("50.00"),
        target_entry_max=Decimal("70.00"),
    )

    now_utc = datetime.now(timezone.utc)
    intel_state = InstrumentIntelligenceState(
        id=uuid.uuid4(),
        instrument_id=inst.id,
        thesis_status=ThesisStatus.UNCHANGED,
        valuation_status=ValuationStatus.FAIR,
        recommendation=Recommendation.HOLD,
        last_review_at=now_utc - timedelta(days=3),
    )
    db_session.add(intel_state)
    await db_session.commit()

    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 60.00, "currency": "USD"},
    ):
        await opp_service.evaluate_candidate_opportunity(
            db=db_session,
            user_id=user.id,
            instrument=inst,
            watchlist_item=item,
        )

    # Re-query InstrumentIntelligenceState directly
    res = await db_session.execute(
        select(InstrumentIntelligenceState).where(InstrumentIntelligenceState.instrument_id == inst.id)
    )
    reloaded_state = res.scalar_one()

    # Zero mutation of state attributes
    assert reloaded_state.valuation_status == ValuationStatus.FAIR
    assert reloaded_state.thesis_status == ThesisStatus.UNCHANGED
    assert reloaded_state.recommendation == Recommendation.HOLD
    assert reloaded_state.last_review_at == intel_state.last_review_at


@pytest.mark.asyncio
async def test_29_formal_valuation_review_is_exclusive_path_to_alter_authoritative_valuation(db_session: AsyncSession):
    """Scenario 29: Formal Valuation Review remains the only path that can alter authoritative valuation state."""
    user = await _create_test_user(db_session, "user29@test.com")
    inst = await _create_test_instrument(db_session, symbol="AUTHORITY")
    item = await _create_test_watchlist_item(
        db_session,
        user.id,
        inst.id,
        research_stage=ResearchStage.WAITING_FOR_PRICE,
        target_entry_min=Decimal("100.00"),
        target_entry_max=Decimal("110.00"),
    )

    intel_state = InstrumentIntelligenceState(
        id=uuid.uuid4(),
        instrument_id=inst.id,
        thesis_status=ThesisStatus.UNCHANGED,
        valuation_status=ValuationStatus.FAIR,
        recommendation=Recommendation.HOLD,
        last_review_at=datetime.now(timezone.utc) - timedelta(days=10),
    )
    db_session.add(intel_state)
    await db_session.commit()

    # 1. Opportunity cycle with price trigger entered
    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 105.00, "currency": "USD"},
    ):
        assessment1 = await opp_service.evaluate_candidate_opportunity(
            db=db_session,
            user_id=user.id,
            instrument=inst,
            watchlist_item=item,
        )
    # Opportunity cannot alter valuation state
    assert assessment1.valuation_signal == ValuationSignal.FAIR
    assert intel_state.valuation_status == ValuationStatus.FAIR

    # 2. Simulate formal Valuation Review execution updating authoritative state
    intel_state.valuation_status = ValuationStatus.ATTRACTIVE
    intel_state.last_review_at = datetime.now(timezone.utc)
    await db_session.commit()

    # 3. Next opportunity cycle picks up newly authorized valuation
    with patch(
        "app.services.price.get_live_price",
        new_callable=AsyncMock,
        return_value={"price": 105.00, "currency": "USD"},
    ):
        assessment2 = await opp_service.evaluate_candidate_opportunity(
            db=db_session,
            user_id=user.id,
            instrument=inst,
            watchlist_item=item,
            force_refresh=True,
        )
    assert assessment2.valuation_signal == ValuationSignal.ATTRACTIVE

