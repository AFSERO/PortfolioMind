"""Tests for Part 4D: First End-to-End Thesis Review Workflow."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from investment_intelligence.enums import (
    ProtocolRunStatus,
    Recommendation,
    TechnicalStatus,
    ThesisStatus,
    ValuationStatus,
)
from investment_intelligence.execution import (
    AIExecutionError,
    AIExecutionResult,
    StaticAIProvider,
)
from investment_intelligence.providers import (
    MarketQuoteRecord,
    NewsItemRecord,
    PositionSnapshotRecord,
    StaticMarketDataProvider,
    StaticNewsProvider,
    StaticPortfolioProvider,
)
from investment_intelligence.repositories import (
    InstrumentNotFoundError,
    InstrumentRepository,
    IntelligenceStateRepository,
)
from investment_intelligence.services import ProtocolRunService
from investment_intelligence.workflows import (
    ThesisReviewWorkflow,
    run_thesis_review,
)

pytestmark = pytest.mark.postgres
NOW = datetime(2026, 9, 15, 14, 0, tzinfo=timezone.utc)


def _setup_thesis_test_environment(session: Session):
    """Helper to set up standard instruments and providers for thesis review tests."""
    inst_repo = InstrumentRepository(session)
    state_repo = IntelligenceStateRepository(session)

    with session.begin():
        inst = inst_repo.create(
            symbol="MSFT",
            name="Microsoft Corporation",
            instrument_type="equity",
            currency="USD",
            venue="NASDAQ",
        )
        state_repo.create_initial(inst.id)
        original_state = state_repo.update(
            inst.id,
            thesis_status=ThesisStatus.UNCHANGED,
            valuation_status=ValuationStatus.FAIR,
            technical_status=TechnicalStatus.ON_TRACK,
            recommendation=Recommendation.HOLD,
            last_review_at=NOW,
        )

    market_prov = StaticMarketDataProvider()
    market_prov.set_quote(
        MarketQuoteRecord(
            instrument_id=inst.id,
            price=Decimal("420.50"),
            currency="USD",
            as_of=NOW,
            source="test_feed",
        )
    )

    news_prov = StaticNewsProvider()
    news_prov.add_news(
        NewsItemRecord(
            title="Microsoft Expands Azure AI Capabilities",
            published_at=NOW,
            source="TechWire",
            instrument_id=inst.id,
            summary="New infrastructure deployed for enterprise LLM workloads.",
        )
    )

    portfolio_prov = StaticPortfolioProvider()
    portfolio_prov.set_position(
        PositionSnapshotRecord(
            instrument_id=inst.id,
            quantity=Decimal("100"),
            average_cost=Decimal("380.00"),
            market_value=Decimal("42050.00"),
            portfolio_weight=Decimal("0.12"),
            unrealized_pnl=Decimal("4050.00"),
        )
    )

    ai_prov = StaticAIProvider(
        default_result=AIExecutionResult(
            machine_record={
                "thesis_status": "UNCHANGED",
                "recommendation": "HOLD",
                "material_changes": [],
                "open_questions": ["Monitor margin trend on AI hardware capex"],
            },
            human_brief="Thesis remains intact. Azure AI revenue growth offsets capex increase.",
            confidence="HIGH",
        )
    )

    return inst, original_state, market_prov, news_prov, portfolio_prov, ai_prov


# ============================================================================
# 1. Complete Success Flow
# ============================================================================


def test_thesis_review_complete_success(session: Session):
    """Verify full end-to-end Thesis Review workflow execution."""
    inst, _, market_prov, news_prov, portfolio_prov, ai_prov = (
        _setup_thesis_test_environment(session)
    )

    workflow = ThesisReviewWorkflow(
        session=session,
        ai_provider=ai_prov,
        market_provider=market_prov,
        news_provider=news_prov,
        portfolio_provider=portfolio_prov,
    )

    execution = workflow.run(inst.id)

    # Unpack support
    run_rec, res = execution
    assert run_rec.id is not None
    assert run_rec.instrument_id == inst.id
    assert run_rec.protocol_name == "thesis-review"
    assert run_rec.status == ProtocolRunStatus.COMPLETED
    assert run_rec.machine_record == {
        "thesis_status": "UNCHANGED",
        "recommendation": "HOLD",
        "material_changes": [],
        "open_questions": ["Monitor margin trend on AI hardware capex"],
    }
    assert "Azure AI revenue" in run_rec.human_brief
    assert run_rec.confidence == "HIGH"
    assert run_rec.completed_at is not None
    assert run_rec.started_at <= run_rec.completed_at

    # Verify AI execution request structure
    assert len(ai_prov.recorded_requests) == 1
    req = ai_prov.recorded_requests[0]
    assert req.protocol_name == "thesis-review"
    assert "# Thesis Review" in req.protocol_text
    assert req.persistent_context["instrument"]["symbol"] == "MSFT"

    supp = req.supplemental_context
    assert supp["market"]["status"] == "available"
    assert supp["market"]["current_quote"]["price"] == 420.50
    assert supp["market"]["current_quote"]["currency"] == "USD"
    assert len(supp["recent_news"]) == 1
    assert supp["recent_news"][0]["title"] == "Microsoft Expands Azure AI Capabilities"
    assert supp["portfolio_position"]["quantity"] == 100.0
    assert supp["portfolio_position"]["unrealized_pnl"] == 4050.0

    assert req.execution_metadata["workflow"] == "thesis-review"


# ============================================================================
# 2. Position Handling: Not Held in Portfolio
# ============================================================================


def test_thesis_review_no_position(session: Session):
    """Verify Thesis Review succeeds when instrument is not held in portfolio."""
    inst, _, market_prov, news_prov, portfolio_prov, ai_prov = (
        _setup_thesis_test_environment(session)
    )

    # Remove position so asset is not held
    portfolio_prov.remove_position(inst.id)

    execution = run_thesis_review(
        session=session,
        instrument_id=inst.id,
        ai_provider=ai_prov,
        market_provider=market_prov,
        news_provider=news_prov,
        portfolio_provider=portfolio_prov,
    )

    assert execution.run.status == ProtocolRunStatus.COMPLETED
    req = ai_prov.recorded_requests[0]
    assert req.supplemental_context["portfolio_position"] is None


# ============================================================================
# 3. News Handling: No Recent News
# ============================================================================


def test_thesis_review_no_news(session: Session):
    """Verify Thesis Review succeeds when no news items are available."""
    inst, _, market_prov, _, portfolio_prov, ai_prov = (
        _setup_thesis_test_environment(session)
    )

    empty_news_prov = StaticNewsProvider()

    workflow = ThesisReviewWorkflow(
        session=session,
        ai_provider=ai_prov,
        market_provider=market_prov,
        news_provider=empty_news_prov,
        portfolio_provider=portfolio_prov,
    )

    execution = workflow.run(inst.id)
    assert execution.run.status == ProtocolRunStatus.COMPLETED

    req = ai_prov.recorded_requests[0]
    assert req.supplemental_context["recent_news"] == []


# ============================================================================
# 4. Market Data Handling: Unavailable Quote
# ============================================================================


def test_thesis_review_market_data_unavailable(session: Session):
    """Verify Thesis Review succeeds safely when market quote is unavailable."""
    inst, _, _, news_prov, portfolio_prov, ai_prov = (
        _setup_thesis_test_environment(session)
    )

    # Provider has no quote for this instrument -> raises DataUnavailableError
    empty_market_prov = StaticMarketDataProvider()

    workflow = ThesisReviewWorkflow(
        session=session,
        ai_provider=ai_prov,
        market_provider=empty_market_prov,
        news_provider=news_prov,
        portfolio_provider=portfolio_prov,
    )

    execution = workflow.run(inst.id)
    assert execution.run.status == ProtocolRunStatus.COMPLETED

    req = ai_prov.recorded_requests[0]
    market_ctx = req.supplemental_context["market"]
    assert market_ctx["status"] == "unavailable"
    assert market_ctx["current_quote"] is None


# ============================================================================
# 5. Price History Discipline: Historical Bars Omitted
# ============================================================================


def test_thesis_review_omits_historical_price_bars(session: Session):
    """Verify Thesis Review does NOT fetch full OHLCV price history."""
    inst, _, market_prov, news_prov, portfolio_prov, ai_prov = (
        _setup_thesis_test_environment(session)
    )

    class SpyMarketDataProvider(StaticMarketDataProvider):
        def __init__(self, base: StaticMarketDataProvider):
            super().__init__()
            self._quotes = base._quotes
            self._bars = base._bars
            self.history_called = False

        def get_price_history(self, *args, **kwargs):
            self.history_called = True
            return super().get_price_history(*args, **kwargs)

    spy_market = SpyMarketDataProvider(market_prov)

    workflow = ThesisReviewWorkflow(
        session=session,
        ai_provider=ai_prov,
        market_provider=spy_market,
        news_provider=news_prov,
        portfolio_provider=portfolio_prov,
    )

    workflow.run(inst.id)
    assert spy_market.history_called is False


# ============================================================================
# 6. Multi-Instrument Isolation
# ============================================================================


def test_thesis_review_provider_isolation(session: Session):
    """Verify strict data isolation: data for other instruments does not leak."""
    inst_repo = InstrumentRepository(session)
    with session.begin():
        inst_a = inst_repo.create(
            symbol="AAPL",
            name="Apple Inc.",
            instrument_type="equity",
            currency="USD",
        )
        inst_b = inst_repo.create(
            symbol="NVDA",
            name="Nvidia Corp.",
            instrument_type="equity",
            currency="USD",
        )

    market_prov = StaticMarketDataProvider()
    market_prov.set_quote(
        MarketQuoteRecord(
            instrument_id=inst_a.id,
            price=Decimal("225.00"),
            currency="USD",
            as_of=NOW,
            source="aapl_feed",
        )
    )
    market_prov.set_quote(
        MarketQuoteRecord(
            instrument_id=inst_b.id,
            price=Decimal("120.00"),
            currency="USD",
            as_of=NOW,
            source="nvda_feed",
        )
    )

    news_prov = StaticNewsProvider()
    news_prov.add_news(
        NewsItemRecord(
            title="Apple announces new iPhone series",
            published_at=NOW,
            source="AppleNews",
            instrument_id=inst_a.id,
        )
    )
    news_prov.add_news(
        NewsItemRecord(
            title="Nvidia accelerates GPU production line",
            published_at=NOW,
            source="NvidiaNews",
            instrument_id=inst_b.id,
        )
    )

    portfolio_prov = StaticPortfolioProvider()
    portfolio_prov.set_position(
        PositionSnapshotRecord(
            instrument_id=inst_a.id,
            quantity=Decimal("50"),
            average_cost=Decimal("200.00"),
            market_value=Decimal("11250.00"),
        )
    )
    portfolio_prov.set_position(
        PositionSnapshotRecord(
            instrument_id=inst_b.id,
            quantity=Decimal("200"),
            average_cost=Decimal("90.00"),
            market_value=Decimal("24000.00"),
        )
    )

    ai_prov = StaticAIProvider()

    # Run for AAPL
    workflow = ThesisReviewWorkflow(
        session=session,
        ai_provider=ai_prov,
        market_provider=market_prov,
        news_provider=news_prov,
        portfolio_provider=portfolio_prov,
    )
    workflow.run(inst_a.id)

    req = ai_prov.recorded_requests[0]
    supp = req.supplemental_context

    # Verify AAPL data present
    assert supp["market"]["current_quote"]["price"] == 225.00
    assert len(supp["recent_news"]) == 1
    assert supp["recent_news"][0]["title"] == "Apple announces new iPhone series"
    assert supp["portfolio_position"]["quantity"] == 50.0

    # Ensure NVDA data is strictly absent from AAPL's context
    serialized = json.dumps(supp)
    assert "NVDA" not in serialized
    assert "Nvidia" not in serialized
    assert "120.0" not in serialized
    assert "24000.0" not in serialized


# ============================================================================
# 7. Critical Invariant: Current Intelligence State Never Auto-Mutates
# ============================================================================


def test_thesis_review_does_not_mutate_intelligence_state(session: Session):
    """CRITICAL INVARIANT: Even on extreme AI thesis downgrades, IntelligenceState is untouched."""
    inst, original_state, market_prov, news_prov, portfolio_prov, _ = (
        _setup_thesis_test_environment(session)
    )

    state_repo = IntelligenceStateRepository(session)
    assert original_state.thesis_status == ThesisStatus.UNCHANGED
    assert original_state.recommendation == Recommendation.HOLD

    # AI returns aggressive thesis downgrade
    downgrade_ai_prov = StaticAIProvider(
        default_result=AIExecutionResult(
            machine_record={
                "thesis_status": "WEAKER",
                "recommendation": "SELL",
                "material_changes": ["Major moat erosion"],
                "open_questions": ["Exit plan needed"],
            },
            human_brief="Downgrading thesis to WEAKER. Recommend SELL.",
            confidence="HIGH",
        )
    )

    workflow = ThesisReviewWorkflow(
        session=session,
        ai_provider=downgrade_ai_prov,
        market_provider=market_prov,
        news_provider=news_prov,
        portfolio_provider=portfolio_prov,
    )

    execution = workflow.run(inst.id)
    assert execution.run.status == ProtocolRunStatus.COMPLETED

    # Verify IntelligenceState in database was NOT modified
    current_state = state_repo.get(inst.id)
    assert current_state.thesis_status == ThesisStatus.UNCHANGED
    assert current_state.recommendation == Recommendation.HOLD
    assert current_state.valuation_status == original_state.valuation_status
    assert current_state.last_review_at == original_state.last_review_at
    assert current_state.updated_at == original_state.updated_at


# ============================================================================
# 8. Failure Path: AI Provider Error
# ============================================================================


def test_thesis_review_ai_failure_marks_run_failed(session: Session):
    """Verify AI execution failure results in FAILED run record and error raised."""
    inst, _, market_prov, news_prov, portfolio_prov, _ = (
        _setup_thesis_test_environment(session)
    )

    failing_ai = StaticAIProvider(
        should_fail=True,
        failure_error=RuntimeError("Provider timed out with secret_key_12345"),
    )

    workflow = ThesisReviewWorkflow(
        session=session,
        ai_provider=failing_ai,
        market_provider=market_prov,
        news_provider=news_prov,
        portfolio_provider=portfolio_prov,
    )

    with pytest.raises(AIExecutionError, match="AI execution failed: RuntimeError"):
        workflow.run(inst.id)

    # Check ProtocolRun history
    protocol_svc = ProtocolRunService(session)
    runs = protocol_svc.recent(instrument_id=inst.id)
    assert len(runs) == 1
    failed_run = runs[0]
    assert failed_run.status == ProtocolRunStatus.FAILED
    assert failed_run.completed_at is not None
    assert "secret_key_12345" not in (failed_run.human_brief or "")
    assert failed_run.human_brief == "AI execution failed: RuntimeError"


# ============================================================================
# 9. Pre-Validation & Bounds
# ============================================================================


def test_thesis_review_prevalidation_unknown_instrument(session: Session):
    """Verify non-existent instrument fails before calling providers or writing runs."""
    _, _, market_prov, news_prov, portfolio_prov, ai_prov = (
        _setup_thesis_test_environment(session)
    )

    workflow = ThesisReviewWorkflow(
        session=session,
        ai_provider=ai_prov,
        market_provider=market_prov,
        news_provider=news_prov,
        portfolio_provider=portfolio_prov,
    )

    missing_id = uuid4()
    with pytest.raises(InstrumentNotFoundError, match="not found"):
        workflow.run(missing_id)

    # Zero AI requests made
    assert len(ai_prov.recorded_requests) == 0


def test_thesis_review_news_limit_bounds(session: Session):
    """Verify news_limit enforces bounded result count and validates negative values."""
    inst, _, market_prov, _, portfolio_prov, ai_prov = (
        _setup_thesis_test_environment(session)
    )

    multi_news_prov = StaticNewsProvider()
    for i in range(15):
        multi_news_prov.add_news(
            NewsItemRecord(
                title=f"News headline {i}",
                published_at=NOW,
                source="Newswire",
                instrument_id=inst.id,
            )
        )

    workflow = ThesisReviewWorkflow(
        session=session,
        ai_provider=ai_prov,
        market_provider=market_prov,
        news_provider=multi_news_prov,
        portfolio_provider=portfolio_prov,
    )

    # Bound to 5
    workflow.run(inst.id, news_limit=5)
    req = ai_prov.recorded_requests[0]
    assert len(req.supplemental_context["recent_news"]) == 5

    # Negative limit raises ValueError
    with pytest.raises(ValueError, match="news_limit must be non-negative"):
        workflow.run(inst.id, news_limit=-1)
