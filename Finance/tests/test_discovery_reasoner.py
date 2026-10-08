"""Tests for DiscoveryReasoner in Finance package."""

import pytest
from investment_intelligence.execution import AIExecutionResult, StaticAIProvider
from investment_intelligence.discovery_reasoner import (
    DiscoveryAssessment,
    DiscoveryAssessmentError,
    DiscoveryReasoner,
)


def test_discovery_reasoner_success():
    mock_record = {
        "discovery_status": "HIGH_PRIORITY_SCREEN",
        "primary_reason": "High quality compounder down 28% from 52-week high after temporary earnings delay.",
        "signal_summary": "PRICE_DISLOCATION (-28%), SUPPORT_PROXIMITY (+6% from 52w low)",
        "key_question": "Are customer churn rates elevated or is revenue growth merely delayed?",
        "key_risk": "Competitive margin pressure in cloud infrastructure segment.",
        "suggested_next_step": "PRELIMINARY_SCREENING",
        "confidence": "HIGH",
    }
    provider = StaticAIProvider(
        default_result=AIExecutionResult(
            machine_record=mock_record,
            human_brief="Warrants preliminary screening due to deep price pullback in market leader.",
            confidence="HIGH",
        )
    )
    reasoner = DiscoveryReasoner(ai_provider=provider)

    assessment = reasoner.assess_candidate(
        instrument={"symbol": "NOW", "name": "ServiceNow Inc.", "asset_type": "STOCK"},
        market_data={"last_price": 720.0, "drawdown_from_52w_high": -0.28},
        signals=[{"type": "PRICE_DISLOCATION", "detail": "Down 28% from 52w high"}],
    )

    assert isinstance(assessment, DiscoveryAssessment)
    assert assessment.discovery_status == "HIGH_PRIORITY_SCREEN"
    assert assessment.suggested_next_step == "PRELIMINARY_SCREENING"
    assert assessment.confidence == "HIGH"
    assert "High quality compounder" in assessment.primary_reason
    assert assessment.key_question == "Are customer churn rates elevated or is revenue growth merely delayed?"
    assert assessment.key_risk == "Competitive margin pressure in cloud infrastructure segment."


def test_discovery_reasoner_invalid_status_raises():
    mock_record = {
        "discovery_status": "BUY_NOW",  # Invalid discovery status / trade action
        "primary_reason": "Attempting to recommend a buy action.",
    }
    provider = StaticAIProvider(
        default_result=AIExecutionResult(
            machine_record=mock_record,
            human_brief="Invalid test.",
        )
    )
    reasoner = DiscoveryReasoner(ai_provider=provider)

    with pytest.raises(DiscoveryAssessmentError, match="Invalid discovery_status"):
        reasoner.assess_candidate(
            instrument={"symbol": "NOW", "name": "ServiceNow Inc."},
        )


def test_discovery_reasoner_missing_reason_raises():
    mock_record = {
        "discovery_status": "SCREEN",
        "primary_reason": "",
    }
    provider = StaticAIProvider(
        default_result=AIExecutionResult(
            machine_record=mock_record,
            human_brief="Empty reason test.",
        )
    )
    reasoner = DiscoveryReasoner(ai_provider=provider)

    with pytest.raises(DiscoveryAssessmentError, match="missing required non-empty 'primary_reason'"):
        reasoner.assess_candidate(
            instrument={"symbol": "NOW", "name": "ServiceNow Inc."},
        )


def test_discovery_reasoner_blocks_buy_sell_recommendations():
    """Verify that DiscoveryAssessment never adopts trade recommendations or position sizing."""
    mock_record = {
        "discovery_status": "SCREEN",
        "primary_reason": "Interesting valuation pullback.",
        "signal_summary": "Dislocation",
        "key_question": "Can margins recover?",
        "key_risk": "Industry slow-down",
        "suggested_next_step": "PRELIMINARY_SCREENING",
        "recommendation": "BUY",  # Rogue recommendation in machine record
        "target_weight": 0.05,
    }
    provider = StaticAIProvider(
        default_result=AIExecutionResult(
            machine_record=mock_record,
            human_brief="Screening candidate.",
        )
    )
    reasoner = DiscoveryReasoner(ai_provider=provider)

    assessment = reasoner.assess_candidate(
        instrument={"symbol": "NOW", "name": "ServiceNow Inc."},
    )

    # Output dataclass has no recommendation or allocation fields
    assert not hasattr(assessment, "recommendation")
    assert not hasattr(assessment, "target_weight")
    assert assessment.discovery_status == "SCREEN"
    assert assessment.suggested_next_step == "PRELIMINARY_SCREENING"
