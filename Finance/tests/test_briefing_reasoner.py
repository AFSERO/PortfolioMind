"""Tests for BriefingReasoner in Finance investment_intelligence package."""

import pytest

from investment_intelligence.briefing_reasoner import (
    BriefingAssessment,
    BriefingAssessmentError,
    BriefingReasoner,
)
from investment_intelligence.execution import (
    AIExecutionError,
    AIExecutionRequest,
    AIExecutionResult,
    StaticAIProvider,
)


@pytest.fixture
def sample_instrument():
    return {
        "symbol": "UBER",
        "name": "Uber Technologies, Inc.",
        "asset_type": "equity",
        "exchange": "NYSE",
        "currency": "USD",
        "is_portfolio": False,
    }


@pytest.fixture
def sample_state():
    return {
        "thesis_status": "STRONGER",
        "valuation_status": "FAIR",
        "recommendation": "ADD",
        "confidence": "HIGH",
        "last_review_at": "2026-09-14T10:00:00Z",
    }


@pytest.fixture
def sample_review():
    return {
        "protocol": "thesis-review",
        "confidence": "HIGH",
        "human_brief": "Autonomous vehicle partnerships expanding mobility TAM.",
        "key_assumptions": ["Take rate stable at 28%", "Delivery margins expand"],
        "growth_drivers": ["Grocery delivery", "Advertising"],
        "key_risks": ["Driver classification regulation"],
    }


@pytest.fixture
def sample_event():
    return {
        "headline": "Costco Expands Nationwide Delivery on Uber Eats",
        "summary": "Uber Eats and Costco expand partnership across 7 additional countries.",
        "source": "Business Wire",
        "url": "https://example.com/news/1",
        "published_at": "2026-09-16T12:00:00Z",
        "sec_form": None,
        "category": "OPERATIONAL",
        "materiality": "HIGH",
    }


def test_briefing_reasoner_success(sample_instrument, sample_state, sample_review, sample_event):
    mock_result = AIExecutionResult(
        machine_record={
            "event_summary": "Costco and Uber Eats expand partnership into 7 international markets.",
            "impact": "POSITIVE",
            "materiality": "HIGH",
            "time_horizon": "MEDIUM",
            "thesis_impact": "STRONGER",
            "review_required": True,
            "why_it_matters": "Directly supports grocery delivery scaling assumption without customer acquisition cost spikes.",
            "recommended_review": "THESIS_REVIEW",
        },
        human_brief="Costco delivery expansion reinforces growth thesis in international grocery.",
        confidence="HIGH",
    )
    ai_provider = StaticAIProvider(default_result=mock_result)
    reasoner = BriefingReasoner(ai_provider=ai_provider)

    assessment = reasoner.assess_event(
        instrument=sample_instrument,
        intelligence_state=sample_state,
        latest_review=sample_review,
        event=sample_event,
    )

    assert isinstance(assessment, BriefingAssessment)
    assert assessment.impact == "POSITIVE"
    assert assessment.materiality == "HIGH"
    assert assessment.thesis_impact == "STRONGER"
    assert assessment.review_required is True
    assert assessment.recommended_review == "THESIS_REVIEW"
    assert assessment.confidence == "HIGH"
    assert "grocery delivery" in assessment.why_it_matters

    # Verify bounded request content
    req: AIExecutionRequest = ai_provider.recorded_requests[0]
    assert req.protocol_name == "briefing-assessment"
    assert req.persistent_context["instrument"]["symbol"] == "UBER"
    assert req.persistent_context["intelligence_state"]["thesis_status"] == "STRONGER"
    assert "event" in req.supplemental_context
    assert req.supplemental_context["event"]["headline"] == sample_event["headline"]


def test_briefing_reasoner_missing_why_it_matters(sample_instrument, sample_event):
    mock_result = AIExecutionResult(
        machine_record={
            "event_summary": "Summary",
            "impact": "POSITIVE",
            "materiality": "HIGH",
            "why_it_matters": "",  # Empty
        },
        human_brief="Brief",
    )
    ai_provider = StaticAIProvider(default_result=mock_result)
    reasoner = BriefingReasoner(ai_provider=ai_provider)

    with pytest.raises(BriefingAssessmentError, match="missing required non-empty 'why_it_matters'"):
        reasoner.assess_event(
            instrument=sample_instrument,
            event=sample_event,
        )


def test_briefing_reasoner_invalid_impact_enum(sample_instrument, sample_event):
    mock_result = AIExecutionResult(
        machine_record={
            "event_summary": "Summary",
            "impact": "SUPER_BULLISH",  # Invalid enum
            "materiality": "HIGH",
            "why_it_matters": "Contextual reason",
        },
        human_brief="Brief",
    )
    ai_provider = StaticAIProvider(default_result=mock_result)
    reasoner = BriefingReasoner(ai_provider=ai_provider)

    with pytest.raises(BriefingAssessmentError, match="Invalid impact 'SUPER_BULLISH'"):
        reasoner.assess_event(
            instrument=sample_instrument,
            event=sample_event,
        )


def test_briefing_reasoner_propagates_ai_execution_error(sample_instrument, sample_event):
    ai_provider = StaticAIProvider(should_fail=True)
    reasoner = BriefingReasoner(ai_provider=ai_provider)

    with pytest.raises(AIExecutionError):
        reasoner.assess_event(
            instrument=sample_instrument,
            event=sample_event,
        )
