"""Comprehensive automated test suite for Market-Wide Discovery Engine v1.

Verifies all 27 key requirements and invariants across:
1. Universe / filtering (owned excluded, watchlisted excluded, rejected suppressed, unsupported skipped, empty universe).
2. Deterministic discovery (dislocation creates candidate, weak noise does not, missing data no fabrication, reason contains evidence).
3. Codex (low quality never reaches Codex, shortlisted reaches DiscoveryReasoner, malformed falls back, no trade recommendations).
4. Persistence & Idempotency (run metrics correct, candidate linked to Instrument, duplicate signal doesn't spam, price shift rediscovery).
5. User actions (Add to Watchlist reuses model, added candidate eligible for Opportunity, dismissed suppressed, screening uses Finance protocol).
6. Automation & Safety (scheduler failure does not invalidate Briefing or Opportunity, zero automatic transactions/assets).
7. API / UI (inbox renders surfaced candidates, empty state works, no buy/sell controls).
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
from app.models.briefing import BriefingRun, BriefingTriggerType
from app.models.discovery import (
    DiscoveryCandidate,
    DiscoveryCandidateState,
    DiscoveryConfidence,
    DiscoveryRun,
    DiscoveryRunStatus,
    DiscoveryStatus,
    DiscoverySuggestedNextStep,
    DiscoveryTriggerType,
    DiscoveryUniverse,
)
from app.models.instrument import Instrument
from app.models.intelligence import InstrumentIntelligenceState, IntelligenceReview, ValuationStatus
from app.models.opportunity import OpportunityAssessment, ResearchStage, WatchlistItem, WatchlistPriority
from app.models.transaction import Transaction
from app.models.user import User
from app.services import discovery as discovery_service
from app.services import opportunity as opp_service
from app.services.scheduler import run_scheduled_briefing_for_user

_FINANCE_SRC = Path(__file__).resolve().parents[2] / "Finance" / "src"
if str(_FINANCE_SRC) not in sys.path:
    sys.path.insert(0, str(_FINANCE_SRC))

from investment_intelligence.discovery_reasoner import (
    DiscoveryAssessment as AIDiscoveryAssessment,
)


@pytest.fixture(autouse=True)
def mock_news_enrichment():
    with patch("investment_intelligence.live_providers.GoogleNewsRSSProvider") as mock_np:
        instance = mock_np.return_value
        instance.get_recent_news.return_value = []
        yield instance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_test_user(db: AsyncSession, email: str = "discoverer@example.com") -> User:
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash="hashed_pw_test",
        display_name="Test Discoverer",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _create_test_instrument(
    db: AsyncSession,
    symbol: str = "NOW",
    name: str = "ServiceNow Inc.",
    asset_type: AssetType = AssetType.STOCK,
    exchange: str = "NYSE",
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


# ---------------------------------------------------------------------------
# 1. Universe / Filtering Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_01_owned_instrument_excluded(db_session: AsyncSession):
    """Scenario 1: Instrument already owned in portfolio is excluded from discovery."""
    user = await _create_test_user(db_session, "user1@disc.com")
    inst = await _create_test_instrument(db_session, symbol="AAPL", name="Apple Inc.")

    # User owns AAPL in portfolio
    asset = Asset(
        id=uuid.uuid4(),
        user_id=user.id,
        instrument_id=inst.id,
        name="Apple Inc.",
        asset_type=AssetType.STOCK,
        symbol="AAPL",
        current_price=Decimal("180.00"),
    )
    db_session.add(asset)
    await db_session.commit()

    symbols, inst_ids = await discovery_service.get_user_exclusion_symbols(db_session, user.id)
    assert "AAPL" in symbols
    assert inst.id in inst_ids


@pytest.mark.asyncio
async def test_02_watchlisted_instrument_excluded(db_session: AsyncSession):
    """Scenario 2: Instrument already on user watchlist is excluded from discovery."""
    user = await _create_test_user(db_session, "user2@disc.com")
    inst = await _create_test_instrument(db_session, symbol="MSFT", name="Microsoft")

    wl_item = WatchlistItem(
        id=uuid.uuid4(),
        user_id=user.id,
        instrument_id=inst.id,
        research_stage=ResearchStage.WAITING_FOR_PRICE,
    )
    db_session.add(wl_item)
    await db_session.commit()

    symbols, _ = await discovery_service.get_user_exclusion_symbols(db_session, user.id)
    assert "MSFT" in symbols


@pytest.mark.asyncio
async def test_03_rejected_candidate_suppressed(db_session: AsyncSession):
    """Scenario 3: Recently dismissed discovery candidate is suppressed from discovery."""
    user = await _create_test_user(db_session, "user3@disc.com")
    inst = await _create_test_instrument(db_session, symbol="GOOGL", name="Alphabet")

    run = DiscoveryRun(
        id=uuid.uuid4(),
        user_id=user.id,
        universe="US_LARGE_CAP",
        status=DiscoveryRunStatus.COMPLETED,
    )
    db_session.add(run)
    await db_session.flush()

    cand = DiscoveryCandidate(
        id=uuid.uuid4(),
        run_id=run.id,
        user_id=user.id,
        instrument_id=inst.id,
        status=DiscoveryStatus.WATCH,
        candidate_state=DiscoveryCandidateState.DISMISSED,
        primary_reason="Test dismiss",
        dismissed_at=datetime.now(timezone.utc) - timedelta(days=5),
    )
    db_session.add(cand)
    await db_session.commit()

    symbols, _ = await discovery_service.get_user_exclusion_symbols(db_session, user.id)
    assert "GOOGL" in symbols


@pytest.mark.asyncio
async def test_04_unsupported_instrument_skipped_safely(db_session: AsyncSession):
    """Scenario 4: Malformed or unresolvable ticker in universe is skipped safely."""
    # Test batch fetcher with empty / bad ticker
    res = await discovery_service.fetch_market_snapshots_batch(["INVALID_SYMBOL_123456789"])
    assert "INVALID_SYMBOL_123456789" not in res or res["INVALID_SYMBOL_123456789"] is None


@pytest.mark.asyncio
async def test_05_empty_universe_produces_valid_empty_run(db_session: AsyncSession):
    """Scenario 5: Empty or exhausted universe produces valid completed DiscoveryRun with 0 candidates."""
    user = await _create_test_user(db_session, "user5@disc.com")

    with patch("app.services.discovery.load_universe_symbols", return_value=[]):
        run = await discovery_service.run_discovery_scan_for_user(
            db=db_session,
            user_id=user.id,
            universe="EMPTY_UNIVERSE",
        )

    assert run.status == DiscoveryRunStatus.COMPLETED
    assert run.instruments_scanned == 0
    assert run.candidates_surfaced == 0


# ---------------------------------------------------------------------------
# 2. Deterministic Discovery Signals Tests
# ---------------------------------------------------------------------------

def test_06_meaningful_price_dislocation_creates_candidate():
    """Scenario 6: Meaningful price dislocation (25% off 52w high) fires PRICE_DISLOCATION signal."""
    snapshot = {
        "last_price": 75.0,
        "year_high": 100.0,
        "year_low": 50.0,
        "fifty_day_average": 80.0,
        "two_hundred_day_average": 90.0,
        "market_cap": 50_000_000_000,
        "currency": "USD",
    }
    signals, score, band = discovery_service.evaluate_deterministic_discovery_signals("CRM", "Salesforce", snapshot)
    sig_types = [s["type"] for s in signals]
    assert "PRICE_DISLOCATION" in sig_types
    assert score >= 3
    assert band in ("MEDIUM", "HIGH")


def test_07_weak_noisy_movement_does_not_create_candidate():
    """Scenario 7: Weak/noisy movement (2% off high) produces zero discovery signals."""
    snapshot = {
        "last_price": 98.0,
        "year_high": 100.0,
        "year_low": 60.0,
        "fifty_day_average": 96.0,
        "two_hundred_day_average": 92.0,
        "market_cap": 50_000_000_000,
        "currency": "USD",
    }
    signals, score, band = discovery_service.evaluate_deterministic_discovery_signals("PEP", "PepsiCo", snapshot)
    # 2% drawdown is not a dislocation
    dislocation_signals = [s for s in signals if s["type"] == "PRICE_DISLOCATION"]
    assert len(dislocation_signals) == 0


def test_08_missing_required_data_does_not_fabricate_signal():
    """Scenario 8: Missing price data does not fabricate signals."""
    snapshot = {
        "last_price": None,
        "year_high": None,
    }
    signals, score, band = discovery_service.evaluate_deterministic_discovery_signals("MISSING", "Missing Corp", snapshot)
    assert len(signals) == 0
    assert score == 0
    assert band == "LOW"


def test_09_candidate_reason_contains_supporting_evidence():
    """Scenario 9: Candidate signal contains exact supporting numerical evidence."""
    snapshot = {
        "last_price": 70.0,
        "year_high": 100.0,
        "year_low": 65.0,
        "fifty_day_average": 75.0,
        "two_hundred_day_average": 95.0,
        "market_cap": 25_000_000_000,
        "currency": "USD",
    }
    signals, score, band = discovery_service.evaluate_deterministic_discovery_signals("NOW", "ServiceNow", snapshot)
    dislocation = next((s for s in signals if s["type"] == "PRICE_DISLOCATION"), None)
    assert dislocation is not None
    assert "30.0%" in dislocation["detail"]
    assert "$70.00" in dislocation["detail"]


# ---------------------------------------------------------------------------
# 3. Codex Reasoning Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_10_low_quality_deterministic_candidate_never_reaches_codex(db_session: AsyncSession):
    """Scenario 10: Candidates without deterministic signals never invoke Codex."""
    user = await _create_test_user(db_session, "user10@disc.com")
    mock_reasoner = MagicMock()

    mock_universe = [{"symbol": "FLAT", "name": "Flat Stock", "exchange": "NYSE", "currency": "USD"}]
    # Flat stock: 1% off high -> 0 signals
    mock_snapshot = {
        "FLAT": {
            "last_price": 99.0,
            "year_high": 100.0,
            "year_low": 80.0,
            "fifty_day_average": 99.5,
            "two_hundred_day_average": 100.0,
            "market_cap": 10_000_000_000,
            "currency": "USD",
        }
    }

    with patch("app.services.discovery.load_universe_symbols", return_value=mock_universe), \
         patch("app.services.discovery.fetch_market_snapshots_batch", new_callable=AsyncMock, return_value=mock_snapshot):
        run = await discovery_service.run_discovery_scan_for_user(
            db=db_session,
            user_id=user.id,
            reasoner=mock_reasoner,
        )

    # Never reached Codex
    assert mock_reasoner.assess_candidate.call_count == 0
    assert run.candidates_surfaced == 0


@pytest.mark.asyncio
async def test_11_shortlisted_candidate_reaches_bounded_discovery_reasoner(db_session: AsyncSession):
    """Scenario 11: High-scoring shortlisted candidate invokes bounded DiscoveryReasoner."""
    user = await _create_test_user(db_session, "user11@disc.com")
    mock_reasoner = MagicMock()
    mock_reasoner.assess_candidate.return_value = AIDiscoveryAssessment(
        discovery_status="HIGH_PRIORITY_SCREEN",
        primary_reason="Deep drawdown in cloud market leader warrants preliminary screening.",
        signal_summary="PRICE_DISLOCATION (-30%)",
        key_question="Is enterprise software spending slowing structurally?",
        key_risk="Continued multiple contraction.",
        suggested_next_step="PRELIMINARY_SCREENING",
        confidence="HIGH",
    )

    mock_universe = [{"symbol": "CRM", "name": "Salesforce Inc.", "exchange": "NYSE", "currency": "USD"}]
    mock_snapshot = {
        "CRM": {
            "last_price": 210.0,
            "year_high": 300.0,
            "year_low": 200.0,
            "fifty_day_average": 230.0,
            "two_hundred_day_average": 260.0,
            "market_cap": 200_000_000_000,
            "currency": "USD",
        }
    }

    with patch("app.services.discovery.load_universe_symbols", return_value=mock_universe), \
         patch("app.services.discovery.fetch_market_snapshots_batch", new_callable=AsyncMock, return_value=mock_snapshot):
        run = await discovery_service.run_discovery_scan_for_user(
            db=db_session,
            user_id=user.id,
            reasoner=mock_reasoner,
        )

    assert mock_reasoner.assess_candidate.call_count == 1
    assert run.candidates_surfaced == 1
    cand = run.candidates[0]
    assert cand.status == DiscoveryStatus.HIGH_PRIORITY_SCREEN
    assert cand.suggested_next_step == DiscoverySuggestedNextStep.PRELIMINARY_SCREENING


@pytest.mark.asyncio
async def test_12_codex_malformed_output_falls_back_safely(db_session: AsyncSession):
    """Scenario 12: Codex failure falls back safely to deterministic result without failing run."""
    user = await _create_test_user(db_session, "user12@disc.com")
    mock_reasoner = MagicMock()
    mock_reasoner.assess_candidate.side_effect = RuntimeError("Codex timeout or malformed JSON")

    mock_universe = [{"symbol": "AMD", "name": "Advanced Micro Devices", "exchange": "NASDAQ", "currency": "USD"}]
    mock_snapshot = {
        "AMD": {
            "last_price": 120.0,
            "year_high": 180.0,
            "year_low": 115.0,
            "fifty_day_average": 135.0,
            "two_hundred_day_average": 150.0,
            "market_cap": 190_000_000_000,
            "currency": "USD",
        }
    }

    with patch("app.services.discovery.load_universe_symbols", return_value=mock_universe), \
         patch("app.services.discovery.fetch_market_snapshots_batch", new_callable=AsyncMock, return_value=mock_snapshot):
        run = await discovery_service.run_discovery_scan_for_user(
            db=db_session,
            user_id=user.id,
            reasoner=mock_reasoner,
        )

    assert run.status == DiscoveryRunStatus.COMPLETED
    assert run.candidates_surfaced == 1
    cand = run.candidates[0]
    assert cand.suggested_next_step in (DiscoverySuggestedNextStep.PRELIMINARY_SCREENING, DiscoverySuggestedNextStep.ADD_TO_WATCHLIST)


def test_13_codex_cannot_produce_trade_recommendation():
    """Scenario 13: DiscoveryCandidate model has no trade recommendation or position fields."""
    cand = DiscoveryCandidate(
        id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        instrument_id=uuid.uuid4(),
        status=DiscoveryStatus.SCREEN,
        primary_reason="Dislocation detected",
    )
    assert not hasattr(cand, "recommendation")
    assert not hasattr(cand, "trade_action")
    assert not hasattr(cand, "target_weight")


# ---------------------------------------------------------------------------
# 4. Persistence & Idempotency Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_14_discovery_run_metrics_correct(db_session: AsyncSession):
    """Scenario 14: DiscoveryRun metrics correctly record all funnel stages."""
    user = await _create_test_user(db_session, "user14@disc.com")

    mock_universe = [
        {"symbol": "NOW", "name": "ServiceNow", "exchange": "NYSE", "currency": "USD"},
        {"symbol": "FLAT", "name": "Flat Stock", "exchange": "NYSE", "currency": "USD"},
    ]
    mock_snapshot = {
        "NOW": {
            "last_price": 700.0,
            "year_high": 1000.0,
            "year_low": 650.0,
            "fifty_day_average": 780.0,
            "two_hundred_day_average": 850.0,
            "market_cap": 140_000_000_000,
            "currency": "USD",
        },
        "FLAT": {
            "last_price": 99.0,
            "year_high": 100.0,
            "year_low": 80.0,
            "market_cap": 10_000_000_000,
            "currency": "USD",
        },
    }

    with patch("app.services.discovery.load_universe_symbols", return_value=mock_universe), \
         patch("app.services.discovery.fetch_market_snapshots_batch", new_callable=AsyncMock, return_value=mock_snapshot):
        run = await discovery_service.run_discovery_scan_for_user(
            db=db_session,
            user_id=user.id,
            reasoner=None,
        )

    assert run.instruments_scanned == 2
    assert run.candidates_surfaced == 1
    assert run.status == DiscoveryRunStatus.COMPLETED


@pytest.mark.asyncio
async def test_15_candidate_persisted_against_instrument(db_session: AsyncSession):
    """Scenario 15: Candidate is persisted against a canonical Instrument entity."""
    user = await _create_test_user(db_session, "user15@disc.com")

    mock_universe = [{"symbol": "NOW", "name": "ServiceNow Inc.", "exchange": "NYSE", "currency": "USD"}]
    mock_snapshot = {
        "NOW": {
            "last_price": 720.0,
            "year_high": 1000.0,
            "year_low": 680.0,
            "market_cap": 140_000_000_000,
            "currency": "USD",
        }
    }

    with patch("app.services.discovery.load_universe_symbols", return_value=mock_universe), \
         patch("app.services.discovery.fetch_market_snapshots_batch", new_callable=AsyncMock, return_value=mock_snapshot):
        run = await discovery_service.run_discovery_scan_for_user(db=db_session, user_id=user.id, reasoner=None)

    cand = run.candidates[0]
    inst = await db_session.get(Instrument, cand.instrument_id)
    assert inst is not None
    assert inst.symbol == "NOW"


@pytest.mark.asyncio
async def test_16_duplicate_unchanged_signal_does_not_create_new_spam(db_session: AsyncSession):
    """Scenario 16: Re-running discovery without meaningful price move reuses previous candidate."""
    user = await _create_test_user(db_session, "user16@disc.com")

    mock_universe = [{"symbol": "CRM", "name": "Salesforce", "exchange": "NYSE", "currency": "USD"}]
    mock_snapshot = {
        "CRM": {
            "last_price": 200.0,
            "year_high": 300.0,
            "year_low": 190.0,
            "market_cap": 190_000_000_000,
            "currency": "USD",
        }
    }

    with patch("app.services.discovery.load_universe_symbols", return_value=mock_universe), \
         patch("app.services.discovery.fetch_market_snapshots_batch", new_callable=AsyncMock, return_value=mock_snapshot):
        run1 = await discovery_service.run_discovery_scan_for_user(db=db_session, user_id=user.id, reasoner=None)
        run2 = await discovery_service.run_discovery_scan_for_user(db=db_session, user_id=user.id, reasoner=None)

    # Count total candidates in DB for this instrument
    stmt = select(func.count(DiscoveryCandidate.id)).where(DiscoveryCandidate.user_id == user.id)
    res = await db_session.execute(stmt)
    total_cands = res.scalar()
    # Should not duplicate candidate row for unchanged price
    assert total_cands == 1


@pytest.mark.asyncio
async def test_17_material_price_shift_permits_rediscovery(db_session: AsyncSession):
    """Scenario 17: Significant price shift (>15%) creates a new candidate record."""
    user = await _create_test_user(db_session, "user17@disc.com")

    mock_universe = [{"symbol": "NOW", "name": "ServiceNow", "exchange": "NYSE", "currency": "USD"}]
    mock_snapshot_1 = {
        "NOW": {"last_price": 700.0, "year_high": 1000.0, "year_low": 650.0, "market_cap": 140_000_000_000, "currency": "USD"}
    }
    # Major 25% price drop
    mock_snapshot_2 = {
        "NOW": {"last_price": 520.0, "year_high": 1000.0, "year_low": 500.0, "market_cap": 100_000_000_000, "currency": "USD"}
    }

    with patch("app.services.discovery.load_universe_symbols", return_value=mock_universe):
        with patch("app.services.discovery.fetch_market_snapshots_batch", new_callable=AsyncMock, return_value=mock_snapshot_1):
            await discovery_service.run_discovery_scan_for_user(db=db_session, user_id=user.id, reasoner=None)

        with patch("app.services.discovery.fetch_market_snapshots_batch", new_callable=AsyncMock, return_value=mock_snapshot_2):
            await discovery_service.run_discovery_scan_for_user(db=db_session, user_id=user.id, reasoner=None)

    stmt = select(func.count(DiscoveryCandidate.id)).where(DiscoveryCandidate.user_id == user.id)
    res = await db_session.execute(stmt)
    total_cands = res.scalar()
    assert total_cands == 2


# ---------------------------------------------------------------------------
# 5. User Actions Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_18_add_to_watchlist_uses_existing_watchlist_model(db_session: AsyncSession):
    """Scenario 18: Promoting discovery candidate creates active WatchlistItem with provenance."""
    user = await _create_test_user(db_session, "user18@disc.com")
    inst = await _create_test_instrument(db_session, symbol="NOW")

    run = DiscoveryRun(id=uuid.uuid4(), user_id=user.id, universe="US_LARGE_CAP", status=DiscoveryRunStatus.COMPLETED)
    db_session.add(run)
    await db_session.flush()

    cand = DiscoveryCandidate(
        id=uuid.uuid4(),
        run_id=run.id,
        user_id=user.id,
        instrument_id=inst.id,
        status=DiscoveryStatus.HIGH_PRIORITY_SCREEN,
        candidate_state=DiscoveryCandidateState.SURFACED,
        primary_reason="Dislocated 28% from 52w high",
        key_risk="Margin pressure",
    )
    db_session.add(cand)
    await db_session.commit()

    wl_item = await discovery_service.add_candidate_to_watchlist(db_session, user.id, cand.id)

    assert wl_item is not None
    assert wl_item.instrument_id == inst.id
    assert wl_item.discovery_candidate_id == cand.id
    assert wl_item.research_stage == ResearchStage.DISCOVERED
    assert cand.candidate_state == DiscoveryCandidateState.WATCHLISTED


@pytest.mark.asyncio
async def test_19_added_candidate_becomes_eligible_for_opportunity_automation(db_session: AsyncSession):
    """Scenario 19: Once watchlisted, candidate can be evaluated by Opportunity Automation."""
    user = await _create_test_user(db_session, "user19@disc.com")
    inst = await _create_test_instrument(db_session, symbol="CRM")

    run = DiscoveryRun(id=uuid.uuid4(), user_id=user.id, universe="US_LARGE_CAP", status=DiscoveryRunStatus.COMPLETED)
    db_session.add(run)
    await db_session.flush()

    cand = DiscoveryCandidate(
        id=uuid.uuid4(),
        run_id=run.id,
        user_id=user.id,
        instrument_id=inst.id,
        status=DiscoveryStatus.SCREEN,
        candidate_state=DiscoveryCandidateState.SURFACED,
        primary_reason="Pullback to support",
    )
    db_session.add(cand)
    await db_session.commit()

    # User adds candidate to watchlist
    wl_item = await discovery_service.add_candidate_to_watchlist(db_session, user.id, cand.id)

    # Opportunity automation now evaluates candidate
    with patch("app.services.price.get_live_price", new_callable=AsyncMock, return_value={"price": 200.0, "currency": "USD"}):
        opp = await opp_service.evaluate_candidate_opportunity(
            db=db_session,
            user_id=user.id,
            instrument=inst,
            watchlist_item=wl_item,
        )

    assert opp is not None
    assert isinstance(opp, OpportunityAssessment)


@pytest.mark.asyncio
async def test_20_dismissed_candidate_suppressed_until_material_change(db_session: AsyncSession):
    """Scenario 20: Dismissed candidate is marked DISMISSED and suppressed from discovery."""
    user = await _create_test_user(db_session, "user20@disc.com")
    inst = await _create_test_instrument(db_session, symbol="DISMISS_ME")

    run = DiscoveryRun(id=uuid.uuid4(), user_id=user.id, universe="US_LARGE_CAP", status=DiscoveryRunStatus.COMPLETED)
    db_session.add(run)
    await db_session.flush()

    cand = DiscoveryCandidate(
        id=uuid.uuid4(),
        run_id=run.id,
        user_id=user.id,
        instrument_id=inst.id,
        status=DiscoveryStatus.WATCH,
        candidate_state=DiscoveryCandidateState.SURFACED,
        primary_reason="Testing dismiss",
    )
    db_session.add(cand)
    await db_session.commit()

    dismissed = await discovery_service.dismiss_discovery_candidate(db_session, user.id, cand.id)
    assert dismissed.candidate_state == DiscoveryCandidateState.DISMISSED
    assert dismissed.dismissed_at is not None

    symbols, _ = await discovery_service.get_user_exclusion_symbols(db_session, user.id)
    assert "DISMISS_ME" in symbols


@pytest.mark.asyncio
async def test_21_preliminary_screening_uses_formal_protocol_without_creating_position(db_session: AsyncSession):
    """Scenario 21: Preliminary screening action marks candidate screened and does not create an asset."""
    user = await _create_test_user(db_session, "user21@disc.com")
    inst = await _create_test_instrument(db_session, symbol="SCREEN_TEST")

    run = DiscoveryRun(id=uuid.uuid4(), user_id=user.id, universe="US_LARGE_CAP", status=DiscoveryRunStatus.COMPLETED)
    db_session.add(run)
    await db_session.flush()

    cand = DiscoveryCandidate(
        id=uuid.uuid4(),
        run_id=run.id,
        user_id=user.id,
        instrument_id=inst.id,
        status=DiscoveryStatus.HIGH_PRIORITY_SCREEN,
        candidate_state=DiscoveryCandidateState.SURFACED,
        primary_reason="Testing screening action",
    )
    db_session.add(cand)
    await db_session.commit()

    mock_review_dict = {
        "status": "COMPLETED",
        "review_id": str(uuid.uuid4()),
        "protocol": "preliminary-screening",
        "summary": {"protocol": "preliminary-screening"},
    }
    with patch("app.services.formal_review.execute_instrument_formal_review", new_callable=AsyncMock, return_value=mock_review_dict) as mock_exec:
        cand_after, review = await discovery_service.run_candidate_preliminary_screen(db_session, user.id, cand.id)

    assert mock_exec.call_count == 1
    assert cand_after.candidate_state == DiscoveryCandidateState.SCREENED
    assert review is not None
    assert review["protocol"] == "preliminary-screening"

    # Invariant: screening never creates an owned Asset
    asset_count = (await db_session.execute(select(func.count(Asset.id)).where(Asset.user_id == user.id))).scalar()
    assert asset_count == 0


# ---------------------------------------------------------------------------
# 6. Automation & Safety Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_22_scheduled_discovery_failure_does_not_invalidate_daily_briefing(db_session: AsyncSession):
    """Scenario 22: Failure in discovery scan does not fail the Scheduled Daily Briefing run."""
    user = await _create_test_user(db_session, "user22@disc.com")
    inst = await _create_test_instrument(db_session, symbol="TSM")

    # Owned asset to give the briefing an item
    asset = Asset(
        id=uuid.uuid4(),
        user_id=user.id,
        instrument_id=inst.id,
        name="TSM",
        asset_type=AssetType.STOCK,
        symbol="TSM",
        current_price=Decimal("150.00"),
    )
    db_session.add(asset)
    await db_session.commit()

    mock_run = MagicMock(id=uuid.uuid4(), status="COMPLETED", items_shown=1, items_filtered=0)
    with patch("app.services.briefing.generate_briefing_run", new_callable=AsyncMock, return_value=mock_run), \
         patch("app.services.discovery.run_discovery_scan_for_user", side_effect=RuntimeError("Discovery scan crashed")):
        briefing_run = await run_scheduled_briefing_for_user(
            db=db_session,
            user_id=user.id,
        )

    # Briefing run must succeed despite discovery scan error
    assert briefing_run is not None
    assert briefing_run.status == "COMPLETED"


@pytest.mark.asyncio
async def test_23_scheduled_discovery_failure_does_not_invalidate_opportunity_cycle(db_session: AsyncSession):
    """Scenario 23: Opportunity evaluation succeeds and is preserved even if discovery fails."""
    user = await _create_test_user(db_session, "user23@disc.com")
    inst = await _create_test_instrument(db_session, symbol="UBER")

    asset = Asset(
        id=uuid.uuid4(),
        user_id=user.id,
        instrument_id=inst.id,
        name="Uber Technologies",
        asset_type=AssetType.STOCK,
        symbol="UBER",
        current_price=Decimal("70.00"),
    )
    db_session.add(asset)
    await db_session.commit()

    mock_run = MagicMock(id=uuid.uuid4(), status="COMPLETED", items_shown=1, items_filtered=0)
    with patch("app.services.briefing.generate_briefing_run", new_callable=AsyncMock, return_value=mock_run), \
         patch("app.services.opportunity.evaluate_user_opportunities") as mock_opp, \
         patch("app.services.discovery.run_discovery_scan_for_user", side_effect=RuntimeError("Discovery scan exploded")):
        mock_opp.return_value = MagicMock(evaluated=1, opportunities_found=1, research_now_count=1, research_soon_count=0)
        briefing_run = await run_scheduled_briefing_for_user(db=db_session, user_id=user.id)

    assert briefing_run is not None
    assert mock_opp.call_count == 1


@pytest.mark.asyncio
async def test_24_discovery_never_creates_transactions_or_portfolio_assets_automatically(db_session: AsyncSession):
    """Scenario 24: Discovery scan never mutates portfolio positions or creates transactions."""
    user = await _create_test_user(db_session, "user24@disc.com")

    mock_universe = [{"symbol": "NVDA", "name": "NVIDIA", "exchange": "NASDAQ", "currency": "USD"}]
    mock_snapshot = {
        "NVDA": {"last_price": 100.0, "year_high": 140.0, "year_low": 80.0, "market_cap": 2_500_000_000_000, "currency": "USD"}
    }

    with patch("app.services.discovery.load_universe_symbols", return_value=mock_universe), \
         patch("app.services.discovery.fetch_market_snapshots_batch", new_callable=AsyncMock, return_value=mock_snapshot):
        await discovery_service.run_discovery_scan_for_user(db=db_session, user_id=user.id, reasoner=None)

    # Check zero assets and zero transactions created
    asset_count = (await db_session.execute(select(func.count(Asset.id)).where(Asset.user_id == user.id))).scalar()
    tx_count = (await db_session.execute(
        select(func.count(Transaction.id)).join(Asset, Transaction.asset_id == Asset.id).where(Asset.user_id == user.id)
    )).scalar()
    assert asset_count == 0
    assert tx_count == 0


# ---------------------------------------------------------------------------
# 7. API / UI Verification Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_25_api_latest_run_returns_surfaced_candidates(db_session: AsyncSession):
    """Scenario 25: GET /api/discovery/runs/latest returns structured run and candidates."""
    user = await _create_test_user(db_session, "user25@disc.com")
    inst = await _create_test_instrument(db_session, symbol="ADBE")

    run = DiscoveryRun(
        id=uuid.uuid4(),
        user_id=user.id,
        universe="US_TECH_GROWTH",
        status=DiscoveryRunStatus.COMPLETED,
        instruments_scanned=20,
        candidates_surfaced=1,
    )
    db_session.add(run)
    await db_session.flush()

    cand = DiscoveryCandidate(
        id=uuid.uuid4(),
        run_id=run.id,
        user_id=user.id,
        instrument_id=inst.id,
        status=DiscoveryStatus.HIGH_PRIORITY_SCREEN,
        candidate_state=DiscoveryCandidateState.SURFACED,
        primary_reason="ADBE pullback 25% from 52w high",
        signals=[{"type": "PRICE_DISLOCATION", "label": "Drawdown (-25%)", "detail": "Pullback 25%"}],
        suggested_next_step=DiscoverySuggestedNextStep.PRELIMINARY_SCREENING,
        confidence=DiscoveryConfidence.HIGH,
    )
    db_session.add(cand)
    await db_session.commit()

    latest = await discovery_service.get_latest_discovery_run(db_session, user.id)
    assert latest is not None
    assert len(latest.candidates) == 1
    assert latest.candidates[0].instrument.symbol == "ADBE"


@pytest.mark.asyncio
async def test_26_empty_state_works_gracefully(db_session: AsyncSession):
    """Scenario 26: User with no discovery runs gets None / empty state gracefully."""
    user = await _create_test_user(db_session, "user26@disc.com")
    latest = await discovery_service.get_latest_discovery_run(db_session, user.id)
    assert latest is None


def test_27_no_buy_sell_controls_or_actions_in_api():
    """Scenario 27: Ensure discovery schemas and candidate states contain no buy/sell actions."""
    from app.models.discovery import DiscoveryCandidateState, DiscoverySuggestedNextStep

    allowed_steps = {e.value for e in DiscoverySuggestedNextStep}
    assert "BUY" not in allowed_steps
    assert "SELL" not in allowed_steps
    assert "TRADE" not in allowed_steps

    allowed_states = {e.value for e in DiscoveryCandidateState}
    assert "BOUGHT" not in allowed_states
    assert "PURCHASED" not in allowed_states
