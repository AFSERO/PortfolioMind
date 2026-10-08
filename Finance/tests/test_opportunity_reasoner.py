"""Tests for OpportunityReasoner in Finance package."""

import pytest
from investment_intelligence.execution import AIExecutionResult, StaticAIProvider
from investment_intelligence.opportunity_reasoner import (
    OpportunityAssessment,
    OpportunityAssessmentError,
    OpportunityReasoner,
)


def test_opportunity_reasoner_success():
    mock_record = {
        "opportunity_status": "RESEARCH_NOW",
        "reason": "Price entered desired valuation range ($140-$150) while thesis remains strong.",
        "primary_driver": "VALUATION",
        "valuation_signal": "ATTRACTIVE",
        "research_freshness": "FRESH",
        "suggested_next_step": "VALUATION_UPDATE",
        "confidence": "HIGH",
    }
    provider = StaticAIProvider(
        default_result=AIExecutionResult(
            machine_record=mock_record,
            human_brief="Price reached target valuation zone.",
            confidence="HIGH",
        )
    )
    reasoner = OpportunityReasoner(ai_provider=provider)

    assessment = reasoner.assess_opportunity(
        instrument={"symbol": "TSM", "name": "Taiwan Semiconductor"},
        watchlist_candidate={"research_stage": "WAITING_FOR_PRICE", "target_entry_min": 140, "target_entry_max": 150},
        intelligence_state={"valuation_status": "ATTRACTIVE"},
        current_price={"price": 145.0, "currency": "USD"},
    )

    assert isinstance(assessment, OpportunityAssessment)
    assert assessment.opportunity_status == "RESEARCH_NOW"
    assert assessment.primary_driver == "VALUATION"
    assert assessment.valuation_signal == "ATTRACTIVE"
    assert assessment.suggested_next_step == "VALUATION_UPDATE"
    assert assessment.confidence == "HIGH"


def test_opportunity_reasoner_invalid_status_raises():
    mock_record = {
        "opportunity_status": "INVALID_STATUS",
        "reason": "Invalid status test",
    }
    provider = StaticAIProvider(
        default_result=AIExecutionResult(
            machine_record=mock_record,
            human_brief="Invalid status test",
        )
    )
    reasoner = OpportunityReasoner(ai_provider=provider)

    with pytest.raises(OpportunityAssessmentError, match="Invalid opportunity_status"):
        reasoner.assess_opportunity(
            instrument={"symbol": "TSM", "name": "Taiwan Semiconductor"},
        )


def test_opportunity_reasoner_missing_reason_raises():
    mock_record = {
        "opportunity_status": "RESEARCH_SOON",
        "reason": "",
    }
    provider = StaticAIProvider(
        default_result=AIExecutionResult(
            machine_record=mock_record,
            human_brief="Test brief",
        )
    )
    reasoner = OpportunityReasoner(ai_provider=provider)

    with pytest.raises(OpportunityAssessmentError, match="missing required non-empty 'reason'"):
        reasoner.assess_opportunity(
            instrument={"symbol": "TSM", "name": "Taiwan Semiconductor"},
        )


def test_opportunity_reasoner_preserves_authoritative_valuation_and_blocks_codex_promotion():
    """Verify that if AI attempts to return ATTRACTIVE, but authoritative state is FAIR, signal remains FAIR."""
    mock_record = {
        "opportunity_status": "RESEARCH_NOW",
        "reason": "Entered range but margin of safety not yet formally proven.",
        "primary_driver": "PRICE_MOVE",
        "valuation_signal": "ATTRACTIVE",  # AI hallucinates/promotes to ATTRACTIVE
        "research_freshness": "FRESH",
        "suggested_next_step": "PRICE_REVIEW",
        "confidence": "HIGH",
    }
    provider = StaticAIProvider(
        default_result=AIExecutionResult(
            machine_record=mock_record,
            human_brief="Price entry detected.",
            confidence="HIGH",
        )
    )
    reasoner = OpportunityReasoner(ai_provider=provider)

    assessment = reasoner.assess_opportunity(
        instrument={"symbol": "UBER", "name": "Uber Technologies"},
        watchlist_candidate={"research_stage": "WAITING_FOR_PRICE", "target_entry_min": 60, "target_entry_max": 75},
        intelligence_state={"valuation_status": "FAIR"},  # Authoritative source of truth
        current_price={"price": 71.0, "currency": "USD"},
    )

    # Opportunity status and driver are adopted from analysis, but valuation CANNOT be promoted
    assert assessment.opportunity_status == "RESEARCH_NOW"
    assert assessment.primary_driver == "PRICE_MOVE"
    assert assessment.valuation_signal == "FAIR"  # Maintained authoritative FAIR!


def test_opportunity_reasoner_defaults_to_unknown_without_valuation_state():
    """Verify that target range entry without prior formal review results in UNKNOWN valuation signal."""
    mock_record = {
        "opportunity_status": "RESEARCH_NOW",
        "reason": "Price entered target zone for unreviewed candidate.",
        "primary_driver": "PRICE_MOVE",
        "valuation_signal": "ATTRACTIVE",  # AI attempts to claim ATTRACTIVE
        "research_freshness": "UNKNOWN",
        "suggested_next_step": "PRICE_REVIEW",
        "confidence": "MEDIUM",
    }
    provider = StaticAIProvider(
        default_result=AIExecutionResult(
            machine_record=mock_record,
            human_brief="Price entry detected.",
            confidence="MEDIUM",
        )
    )
    reasoner = OpportunityReasoner(ai_provider=provider)

    assessment = reasoner.assess_opportunity(
        instrument={"symbol": "NEW_STOCK", "name": "New Company"},
        watchlist_candidate={"research_stage": "WAITING_FOR_PRICE", "target_entry_min": 20, "target_entry_max": 25},
        current_price={"price": 22.0, "currency": "USD"},
        # No intelligence_state and no latest_review provided
    )

    assert assessment.opportunity_status == "RESEARCH_NOW"
    assert assessment.valuation_signal == "UNKNOWN"  # Strictly UNKNOWN without formal valuation


def test_opportunity_reasoner_respects_deterministic_context_valuation():
    """Verify that valuation signal from deterministic_context is respected and authoritative."""
    mock_record = {
        "opportunity_status": "RESEARCH_SOON",
        "reason": "Price pullback toward support.",
        "primary_driver": "PRICE_MOVE",
        "valuation_signal": "ATTRACTIVE",
        "research_freshness": "FRESH",
        "suggested_next_step": "VALUATION_UPDATE",
        "confidence": "HIGH",
    }
    provider = StaticAIProvider(
        default_result=AIExecutionResult(
            machine_record=mock_record,
            human_brief="Price movement.",
            confidence="HIGH",
        )
    )
    reasoner = OpportunityReasoner(ai_provider=provider)

    assessment = reasoner.assess_opportunity(
        instrument={"symbol": "TECH", "name": "Tech Corp"},
        deterministic_context={"valuation_signal": "EXPENSIVE"},
        current_price={"price": 100.0, "currency": "USD"},
    )

    assert assessment.valuation_signal == "EXPENSIVE"

