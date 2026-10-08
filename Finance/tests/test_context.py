"""Tests for the compact AI context builder (Part 4A)."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from investment_intelligence.context import (
    ContextBuilder,
    build_asset_context,
    serialize_context,
)
from investment_intelligence.enums import (
    ProtocolRunStatus,
    Recommendation,
    TechnicalStatus,
    ThesisStatus,
    ValuationStatus,
)
from investment_intelligence.repositories import (
    InstrumentNotFoundError,
    InstrumentRepository,
    IntelligenceStateRepository,
    ResearchArtifactRepository,
)
from investment_intelligence.services import ProtocolRunService, TechnicalPlanService

pytestmark = pytest.mark.postgres
NOW = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)


def test_complete_asset_context(session):
    """Verify full asset context with instrument, state, active plan, runs, and artifacts."""
    inst_repo = InstrumentRepository(session)
    state_repo = IntelligenceStateRepository(session)
    plan_svc = TechnicalPlanService(session)
    protocol_svc = ProtocolRunService(session)
    artifact_repo = ResearchArtifactRepository(session)

    with session.begin():
        inst = inst_repo.create(
            symbol="UBER",
            name="Uber Technologies, Inc.",
            instrument_type="equity",
            currency="USD",
            venue="NYSE",
        )
        state_repo.create_initial(inst.id)
        state = state_repo.update(
            inst.id,
            thesis_status=ThesisStatus.STRONGER,
            valuation_status=ValuationStatus.ATTRACTIVE,
            technical_status=TechnicalStatus.ON_TRACK,
            recommendation=Recommendation.ADD,
            last_review_at=NOW,
            next_review_at=datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc),
        )

        # Inactive historical plan (should NOT appear)
        p1 = plan_svc.create_inactive(
            inst.id,
            reference_at=NOW,
            reference_price=Decimal("70.00"),
            trend_expectation="Old trend",
            notes="Old historical plan",
        )

        # Active current plan (SHOULD appear)
        p2 = plan_svc.create_inactive(
            inst.id,
            reference_at=NOW,
            reference_price=Decimal("75.50"),
            trend_expectation="Breakout towards ATH",
            entry_zones=[{"low": 72.0, "high": 75.0}],
            support_zones=[{"level": 70.0}],
            resistance_zones=[{"level": 82.0}],
            review_or_invalidation_zones=[{"level": 67.5}],
            profit_taking_or_reassessment_zones=[{"level": 90.0}],
            notes="Current tactical plan",
        )
        plan_svc.activate_technical_plan(p2.id)

        # Protocol run
        run = protocol_svc.start("thesis_review", instrument_id=inst.id, started_at=NOW)
        protocol_svc.complete(
            run.id,
            machine_record={"summary": "Moat expanding in delivery and autonomous ride-hailing"},
            human_brief="Thesis stronger on improved mobility margins.",
            confidence="HIGH",
        )

        # Research artifact
        art = artifact_repo.create(
            inst.id,
            artifact_type="research_memo",
            path="research/UBER/2026-09-15/memo.md",
            version="v2",
            protocol_run_id=run.id,
            metadata={"word_count": 1200, "source": "10-Q"},
        )

    context = build_asset_context(session, inst.id)

    # 1. Instrument
    assert context["instrument"] == {
        "id": str(inst.id),
        "symbol": "UBER",
        "name": "Uber Technologies, Inc.",
        "instrument_type": "equity",
        "venue": "NYSE",
        "currency": "USD",
    }

    # 2. Intelligence State
    assert context["intelligence_state"] is not None
    assert context["intelligence_state"]["thesis_status"] == "STRONGER"
    assert context["intelligence_state"]["valuation_status"] == "ATTRACTIVE"
    assert context["intelligence_state"]["technical_status"] == "ON_TRACK"
    assert context["intelligence_state"]["recommendation"] == "ADD"
    assert context["intelligence_state"]["last_review_at"] == NOW.isoformat()
    assert context["intelligence_state"]["next_review_at"] == "2026-09-22T12:00:00+00:00"

    # 3. Active Technical Plan (p2 is active, p1 omitted)
    plan_ctx = context["active_technical_plan"]
    assert plan_ctx is not None
    assert plan_ctx["id"] == str(p2.id)
    assert plan_ctx["reference_price"] == 75.50
    assert plan_ctx["trend_expectation"] == "Breakout towards ATH"
    assert plan_ctx["entry_zones"] == [{"low": 72.0, "high": 75.0}]
    assert plan_ctx["notes"] == "Current tactical plan"

    # 4. Recent Runs
    assert len(context["recent_protocol_runs"]) == 1
    run_ctx = context["recent_protocol_runs"][0]
    assert run_ctx["id"] == str(run.id)
    assert run_ctx["protocol_name"] == "thesis_review"
    assert run_ctx["status"] == "COMPLETED"
    assert run_ctx["confidence"] == "HIGH"
    assert run_ctx["machine_record"] == {"summary": "Moat expanding in delivery and autonomous ride-hailing"}
    assert run_ctx["human_brief"] == "Thesis stronger on improved mobility margins."

    # 5. Research Artifacts
    assert len(context["research_artifacts"]) == 1
    art_ctx = context["research_artifacts"][0]
    assert art_ctx["id"] == str(art.id)
    assert art_ctx["artifact_type"] == "research_memo"
    assert art_ctx["path"] == "research/UBER/2026-09-15/memo.md"
    assert art_ctx["version"] == "v2"
    assert art_ctx["protocol_run_id"] == str(run.id)
    assert art_ctx["artifact_metadata"] == {"word_count": 1200, "source": "10-Q"}


def test_new_asset_context_with_missing_optional_data(session):
    """A newly registered instrument has no state, plan, runs, or artifacts."""
    inst_repo = InstrumentRepository(session)
    with session.begin():
        inst = inst_repo.create(
            symbol="NEW",
            name="Newco Technologies",
            instrument_type="equity",
            currency="USD",
        )

    context = build_asset_context(session, inst.id)

    assert context["instrument"]["symbol"] == "NEW"
    assert context["intelligence_state"] is None
    assert context["active_technical_plan"] is None
    assert context["recent_protocol_runs"] == []
    assert context["research_artifacts"] == []


def test_missing_instrument_raises_error(session):
    """Querying a non-existent instrument ID raises InstrumentNotFoundError."""
    with pytest.raises(InstrumentNotFoundError):
        build_asset_context(session, uuid4())


def test_history_and_artifact_limits(session):
    """Strictly enforce bounded recent runs and artifact references."""
    inst_repo = InstrumentRepository(session)
    protocol_svc = ProtocolRunService(session)
    artifact_repo = ResearchArtifactRepository(session)

    with session.begin():
        inst = inst_repo.create(symbol="LIM", name="Limit Test", instrument_type="equity", currency="USD")
        for i in range(7):
            run = protocol_svc.start(f"protocol_{i}", instrument_id=inst.id)
            protocol_svc.complete(run.id, human_brief=f"Brief {i}")
            artifact_repo.create(
                inst.id,
                artifact_type="memo",
                path=f"research/LIM/memo_{i}.md",
                version=f"v{i}",
            )

    # 1. Default limit (5)
    default_ctx = build_asset_context(session, inst.id)
    assert len(default_ctx["recent_protocol_runs"]) == 5
    assert len(default_ctx["research_artifacts"]) == 5

    # 2. Custom limits (runs_limit=2, artifacts_limit=3)
    custom_ctx = build_asset_context(session, inst.id, runs_limit=2, artifacts_limit=3)
    assert len(custom_ctx["recent_protocol_runs"]) == 2
    assert len(custom_ctx["research_artifacts"]) == 3

    # 3. Zero limits
    zero_ctx = build_asset_context(session, inst.id, runs_limit=0, artifacts_limit=0)
    assert zero_ctx["recent_protocol_runs"] == []
    assert zero_ctx["research_artifacts"] == []

    # 4. Negative limits raise ValueError
    with pytest.raises(ValueError, match="non-negative"):
        build_asset_context(session, inst.id, runs_limit=-1)


def test_only_active_technical_plan_included(session):
    """Context must only include the currently active plan; all inactive plans omitted."""
    inst_repo = InstrumentRepository(session)
    plan_svc = TechnicalPlanService(session)

    with session.begin():
        inst = inst_repo.create(symbol="TECH", name="Tech Plan Test", instrument_type="equity", currency="USD")
        p1 = plan_svc.create_inactive(inst.id, reference_at=NOW, notes="Inactive plan 1")
        p2 = plan_svc.create_inactive(inst.id, reference_at=NOW, notes="Inactive plan 2")

        # Both plans are inactive: active_technical_plan must be None
        ctx1 = build_asset_context(session, inst.id)
        assert ctx1["active_technical_plan"] is None

        # Activate plan 2
        plan_svc.activate_technical_plan(p2.id)

        ctx2 = build_asset_context(session, inst.id)
        assert ctx2["active_technical_plan"] is not None
        assert ctx2["active_technical_plan"]["id"] == str(p2.id)
        assert ctx2["active_technical_plan"]["notes"] == "Inactive plan 2"


def test_cross_instrument_isolation(session):
    """Data from other instruments or portfolio-level runs must never leak into asset context."""
    inst_repo = InstrumentRepository(session)
    state_repo = IntelligenceStateRepository(session)
    protocol_svc = ProtocolRunService(session)
    artifact_repo = ResearchArtifactRepository(session)
    plan_svc = TechnicalPlanService(session)

    with session.begin():
        # Asset A
        inst_a = inst_repo.create(symbol="AAA", name="Asset A", instrument_type="equity", currency="USD")
        state_repo.create_initial(inst_a.id)
        state_repo.update(inst_a.id, recommendation=Recommendation.ADD)
        plan_a = plan_svc.create_inactive(inst_a.id, reference_at=NOW, notes="Plan A")
        plan_svc.activate_technical_plan(plan_a.id)
        run_a = protocol_svc.start("run_a", instrument_id=inst_a.id)
        protocol_svc.complete(run_a.id)
        art_a = artifact_repo.create(inst_a.id, artifact_type="memo", path="research/AAA/memo.md")

        # Asset B
        inst_b = inst_repo.create(symbol="BBB", name="Asset B", instrument_type="equity", currency="USD")
        state_repo.create_initial(inst_b.id)
        state_repo.update(inst_b.id, recommendation=Recommendation.SELL)
        plan_b = plan_svc.create_inactive(inst_b.id, reference_at=NOW, notes="Plan B")
        plan_svc.activate_technical_plan(plan_b.id)
        run_b = protocol_svc.start("run_b", instrument_id=inst_b.id)
        protocol_svc.complete(run_b.id)
        art_b = artifact_repo.create(inst_b.id, artifact_type="memo", path="research/BBB/memo.md")

        # Portfolio-level run
        port_run = protocol_svc.start("portfolio_macro", instrument_id=None)
        protocol_svc.complete(port_run.id)

    # Build context for Asset A
    ctx_a = build_asset_context(session, inst_a.id)

    assert ctx_a["instrument"]["symbol"] == "AAA"
    assert ctx_a["intelligence_state"]["recommendation"] == "ADD"
    assert ctx_a["active_technical_plan"]["id"] == str(plan_a.id)
    assert len(ctx_a["recent_protocol_runs"]) == 1
    assert ctx_a["recent_protocol_runs"][0]["id"] == str(run_a.id)
    assert len(ctx_a["research_artifacts"]) == 1
    assert ctx_a["research_artifacts"][0]["id"] == str(art_a.id)

    # Verify no BBB or portfolio run leaked
    run_ids = [r["id"] for r in ctx_a["recent_protocol_runs"]]
    assert str(run_b.id) not in run_ids
    assert str(port_run.id) not in run_ids
    art_ids = [a["id"] for a in ctx_a["research_artifacts"]]
    assert str(art_b.id) not in art_ids


def test_json_serialization_roundtrip(session):
    """Context output must serialize directly with standard json.dumps and serialize_context."""
    inst_repo = InstrumentRepository(session)
    state_repo = IntelligenceStateRepository(session)
    plan_svc = TechnicalPlanService(session)
    protocol_svc = ProtocolRunService(session)

    with session.begin():
        inst = inst_repo.create(symbol="JSON", name="JSON Test", instrument_type="equity", currency="USD")
        state_repo.create_initial(inst.id)
        state_repo.update(
            inst.id,
            thesis_status=ThesisStatus.UNCHANGED,
            valuation_status=ValuationStatus.FAIR,
            technical_status=TechnicalStatus.NEUTRAL,
            recommendation=Recommendation.HOLD,
            last_review_at=NOW,
        )
        plan = plan_svc.create_inactive(
            inst.id,
            reference_at=NOW,
            reference_price=Decimal("123.4567"),
            trend_expectation="Range-bound",
            entry_zones=[{"zone": "A", "price": 120.0}],
        )
        plan_svc.activate_technical_plan(plan.id)
        run = protocol_svc.start("eval", instrument_id=inst.id, started_at=NOW)
        protocol_svc.complete(
            run.id,
            machine_record={"factors": ["growth", "margin"], "score": 8.5},
            human_brief="Stable performance.",
        )

    context = build_asset_context(session, inst.id)

    # 1. Standard library json.dumps works out-of-the-box (no custom encoder needed)
    raw_json = json.dumps(context)
    assert isinstance(raw_json, str)
    parsed = json.loads(raw_json)
    assert parsed["instrument"]["symbol"] == "JSON"
    assert parsed["active_technical_plan"]["reference_price"] == 123.4567
    assert parsed["intelligence_state"]["recommendation"] == "HOLD"
    assert parsed["recent_protocol_runs"][0]["machine_record"]["score"] == 8.5

    # 2. serialize_context helper also works
    helper_json = serialize_context(context, indent=2)
    assert isinstance(helper_json, str)
    assert json.loads(helper_json) == parsed


def test_context_builder_class_interface(session):
    """ContextBuilder class provides the same functionality with injected session."""
    inst_repo = InstrumentRepository(session)
    with session.begin():
        inst = inst_repo.create(symbol="CLS", name="Class Test", instrument_type="equity", currency="USD")

    builder = ContextBuilder(session)
    ctx1 = builder.build_asset_context(inst.id)
    ctx2 = builder.build_asset_context(inst)  # Record object accepted
    ctx3 = builder.build_asset_context(str(inst.id))  # String UUID accepted

    assert ctx1 == ctx2 == ctx3
    assert ctx1["instrument"]["symbol"] == "CLS"
