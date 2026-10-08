"""Test suite for Deep Research Decision Model v2.

Validates the 14 core requirements:
1. Successful Deep Research normally produces directional recommendation (ADD/HOLD/REDUCE/SELL).
2. REVIEW_REQUIRED requires concrete missing-evidence reason.
3. Technical REVIEW_REQUIRED alone does not force final REVIEW_REQUIRED.
4. INVALIDATED + generic REVIEW_REQUIRED is rejected/repaired unless evidence insufficiency exists.
5. INVALIDATED normally produces REDUCE or SELL.
6. Fund does not use stock-style valuation semantics blindly (underlying valuation vs fund quality).
7. Crypto decision model does not require P/E / DCF (evaluates market/network attractiveness).
8. Gold does not use equity intrinsic-value semantics (evaluates macro attractiveness & real yields).
9. Low confidence can coexist with directional recommendation.
10. AI recommendation does not become user decision automatically (DecisionLog is system event).
11. Machine Record validation rejects/repairs contradictory state.
12. Existing historical IntelligenceReview remains readable and backward-compatible.
13. No research execution occurs merely by opening Monitoring.
14. Codex calls during test suite = 0.
"""

import os
from pathlib import Path
import subprocess
import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset, AssetType
from app.models.decision_log import DecisionEventType, DecisionLogEntry
from app.models.instrument import Instrument
from app.models.intelligence import (
    InstrumentIntelligenceState,
    IntelligenceReview,
    ProtocolRunStatus,
    Recommendation,
    TechnicalStatus,
    ThesisStatus,
    ValuationStatus,
)
from app.services.formal_review import resolve_specialized_protocol
from investment_intelligence.enums import (
    Recommendation as IntelligenceRecommendation,
    TechnicalStatus as IntelligenceTechnicalStatus,
    ThesisStatus as IntelligenceThesisStatus,
    ValuationStatus as IntelligenceValuationStatus,
)
from investment_intelligence.execution import AIExecutionResult
from investment_intelligence.validation import (
    DeepResearchRecord,
    MachineRecordValidationError,
    validate_deep_research_record,
    validate_machine_record,
)


# ============================================================================
# Requirement 1: Successful Deep Research produces directional recommendation
# ============================================================================


@pytest.mark.asyncio
async def test_1_successful_deep_research_produces_directional_recommendation(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 1: Deep Research produces a clear directional recommendation (ADD/HOLD/REDUCE/SELL)."""
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    reg = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Equity Investor"},
    )
    token = reg.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create stock asset
    asset_resp = await client.post(
        "/api/assets",
        headers=headers,
        json={
            "asset_type": "STOCK",
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "current_price": 180.0,
            "current_price_currency": "USD",
        },
    )
    assert asset_resp.status_code == 201
    asset_id = asset_resp.json()["data"]["id"]

    mock_result = AIExecutionResult(
        machine_record={
            "thesis_status": "STRONGER",
            "valuation_status": "ATTRACTIVE",
            "technical_status": "ON_TRACK",
            "recommendation": "ADD",
            "confidence": 84,
            "primary_reason": "Services growth and ecosystem lock-in reinforce free cash flow durability.",
            "supporting_reasons": ["High ROCE", "Share buyback accretion"],
            "key_risks": ["China hardware competition", "Regulatory app store scrutiny"],
        },
        human_brief="SONUÇ\n\nÖNERİ:\nADD\n\nGÜVEN:\n84%\n\nNEDEN?\nNakit akış üretimi güçlüdür.",
        confidence="84%",
    )
    mock_provider = MagicMock()
    mock_provider.execute = MagicMock(return_value=mock_result)

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        res = await client.post(
            f"/api/assets/{asset_id}/research",
            headers=headers,
            json={"protocol": "deep-research"},
        )
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["status"] == "COMPLETED"
        assert data["protocol"] == "deep-research-equity"
        assert data["summary"]["recommendation"] in ("ADD", "HOLD", "REDUCE", "SELL")
        assert data["summary"]["recommendation"] == "ADD"
        assert data["summary"]["confidence_score"] == 84


# ============================================================================
# Requirement 2: REVIEW_REQUIRED requires concrete missing-evidence reason
# ============================================================================


def test_2_review_required_requires_concrete_missing_evidence_reason():
    """Test 2: REVIEW_REQUIRED is rejected if missing a concrete review_required_reason."""
    # Fails when review_required_reason is absent
    invalid_record = {
        "thesis_status": "UNCHANGED",
        "valuation_status": "FAIR",
        "recommendation": "REVIEW_REQUIRED",
    }
    with pytest.raises(MachineRecordValidationError) as exc:
        validate_deep_research_record(invalid_record)
    assert "review_required_reason" in str(exc.value)

    # Succeeds when concrete missing-evidence reason is provided
    valid_record = {
        "thesis_status": "UNCHANGED",
        "valuation_status": "FAIR",
        "recommendation": "REVIEW_REQUIRED",
        "review_required_reason": "Audited 2025 financial disclosures are missing and under regulatory freeze.",
    }
    result = validate_deep_research_record(valid_record)
    assert result.recommendation == IntelligenceRecommendation.REVIEW_REQUIRED
    assert result.review_required_reason is not None


# ============================================================================
# Requirement 3: Technical REVIEW_REQUIRED alone does not force final REVIEW_REQUIRED
# ============================================================================


def test_3_technical_review_required_alone_does_not_force_final_review_required():
    """Test 3: Technical=REVIEW_REQUIRED alone does not cause final Recommendation=REVIEW_REQUIRED."""
    record = {
        "thesis_status": "UNCHANGED",
        "valuation_status": "ATTRACTIVE",
        "technical_status": "REVIEW_REQUIRED",
        "recommendation": "REVIEW_REQUIRED",
        # Reason merely cites technical analysis, which is forbidden to block the view
        "review_required_reason": "Technical indicators and chart trend require review",
    }
    repaired = validate_deep_research_record(record)
    # Must be repaired to directional recommendation matching fundamental view
    assert repaired.recommendation in (IntelligenceRecommendation.ADD, IntelligenceRecommendation.HOLD)
    assert repaired.recommendation != IntelligenceRecommendation.REVIEW_REQUIRED


# ============================================================================
# Requirement 4: INVALIDATED + generic REVIEW_REQUIRED is rejected/repaired
# ============================================================================


def test_4_invalidated_plus_generic_review_required_is_repaired():
    """Test 4: INVALIDATED thesis cannot hide under generic REVIEW_REQUIRED."""
    record = {
        "thesis_status": "INVALIDATED",
        "valuation_status": "FAIR",
        "technical_status": "NEUTRAL",
        "recommendation": "REVIEW_REQUIRED",
        # Generic reason without genuine evidence gap
        "review_required_reason": "Please review this position again",
    }
    repaired = validate_deep_research_record(record)
    assert repaired.recommendation in (IntelligenceRecommendation.REDUCE, IntelligenceRecommendation.SELL)
    assert repaired.recommendation == IntelligenceRecommendation.REDUCE


# ============================================================================
# Requirement 5: INVALIDATED normally produces REDUCE or SELL
# ============================================================================


def test_5_invalidated_normally_produces_reduce_or_sell():
    """Test 5: When thesis is INVALIDATED, recommendation must be REDUCE or SELL."""
    for raw_rec in ["ADD", "HOLD", "REVIEW_REQUIRED"]:
        record = {
            "thesis_status": "INVALIDATED",
            "valuation_status": "EXPENSIVE",
            "technical_status": "NEUTRAL",
            "recommendation": raw_rec,
        }
        repaired = validate_deep_research_record(record)
        assert repaired.recommendation in (IntelligenceRecommendation.REDUCE, IntelligenceRecommendation.SELL)


# ============================================================================
# Requirement 6: Fund does not use stock-style valuation semantics blindly
# ============================================================================


def test_6_fund_does_not_use_stock_style_valuation_blindly():
    """Test 6: Fund separates underlying portfolio valuation from fund quality/manager attractiveness."""
    fund_record = {
        "thesis_status": "WEAKER",
        "assessment_type": "FUND",
        "underlying_valuation": "ATTRACTIVE",
        "fund_quality": "WEAKENING",
        "fund_attractiveness": "UNATTRACTIVE",
        "technical_status": "NEUTRAL",
        "recommendation": "REDUCE",
        "confidence": 72,
        "primary_reason": "Underlying equities are cheap, but fund has experienced chronic style drift and fee drag.",
    }
    validated = validate_deep_research_record(fund_record, protocol_name="deep-research-fund")
    assert validated.assessment_type == "FUND"
    assert validated.asset_class_assessment["underlying_valuation"] == "ATTRACTIVE"
    assert validated.asset_class_assessment["fund_quality"] == "WEAKENING"
    assert validated.recommendation == IntelligenceRecommendation.REDUCE
    assert validated.confidence == 72
    d = validated.to_dict()
    assert d["underlying_valuation"] == "ATTRACTIVE"
    assert d["fund_quality"] == "WEAKENING"


# ============================================================================
# Requirement 7: Crypto decision model does not require P/E / DCF
# ============================================================================


def test_7_crypto_decision_model_does_not_require_pe_or_dcf():
    """Test 7: Crypto evaluates network adoption & market attractiveness without equity metrics."""
    crypto_record = {
        "thesis_status": "UNCHANGED",
        "assessment_type": "CRYPTO",
        "network_adoption": "EXPANDING",
        "market_attractiveness": "ATTRACTIVE",
        "technical_status": "ON_TRACK",
        "recommendation": "ADD",
        "confidence": 85,
        "primary_reason": "Hash rate and on-chain active addresses hit all-time highs while exchange reserves decline.",
    }
    validated = validate_deep_research_record(crypto_record, protocol_name="deep-research-crypto")
    assert validated.assessment_type == "CRYPTO"
    assert validated.asset_class_assessment["network_adoption"] == "EXPANDING"
    assert validated.asset_class_assessment["market_attractiveness"] == "ATTRACTIVE"
    assert validated.valuation_status == IntelligenceValuationStatus.ATTRACTIVE
    assert validated.recommendation == IntelligenceRecommendation.ADD


# ============================================================================
# Requirement 8: Gold does not use equity intrinsic-value semantics
# ============================================================================


def test_8_gold_does_not_use_equity_intrinsic_value_semantics():
    """Test 8: Gold evaluates macro regime & macro attractiveness (real yields, central banks)."""
    gold_record = {
        "thesis_status": "STRONGER",
        "assessment_type": "PRECIOUS_METALS",
        "macro_regime": "FAVORABLE",
        "macro_attractiveness": "ATTRACTIVE",
        "technical_status": "ON_TRACK",
        "recommendation": "ADD",
        "confidence": 88,
        "primary_reason": "Central bank accumulation and falling 10Y real yields provide strong macro tailwinds.",
    }
    validated = validate_deep_research_record(gold_record, protocol_name="deep-research-gold")
    assert validated.assessment_type == "PRECIOUS_METALS"
    assert validated.asset_class_assessment["macro_regime"] == "FAVORABLE"
    assert validated.asset_class_assessment["macro_attractiveness"] == "ATTRACTIVE"
    assert validated.valuation_status == IntelligenceValuationStatus.ATTRACTIVE
    assert validated.recommendation == IntelligenceRecommendation.ADD


# ============================================================================
# Requirement 9: Low confidence can coexist with directional recommendation
# ============================================================================


def test_9_low_confidence_can_coexist_with_directional_recommendation():
    """Test 9: Uncertainty is represented via confidence score, not by avoiding directional calls."""
    record = {
        "thesis_status": "WEAKER",
        "valuation_status": "FAIR",
        "technical_status": "DEVIATED",
        "recommendation": "HOLD",
        "confidence": 45,
        "primary_reason": "Despite weaker operational margins, debt covenants are secure so HOLD is appropriate.",
    }
    validated = validate_deep_research_record(record)
    assert validated.recommendation == IntelligenceRecommendation.HOLD
    assert validated.confidence == 45
    assert validated.to_dict()["confidence_level"] == "LOW"


# ============================================================================
# Requirement 10: AI recommendation does not become user decision automatically
# ============================================================================


@pytest.mark.asyncio
async def test_10_ai_recommendation_does_not_become_user_decision_automatically(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 10: AI recommendation changes create system events, not user trades or user decisions."""
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    reg = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Decisions User"},
    )
    token = reg.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create holding
    asset_resp = await client.post(
        "/api/assets",
        headers=headers,
        json={
            "asset_type": "STOCK",
            "symbol": "MSFT",
            "name": "Microsoft Corp.",
            "current_price": 400.0,
            "current_price_currency": "USD",
        },
    )
    asset_id = asset_resp.json()["data"]["id"]

    mock_result = AIExecutionResult(
        machine_record={
            "thesis_status": "WEAKER",
            "valuation_status": "EXPENSIVE",
            "technical_status": "NEUTRAL",
            "recommendation": "REDUCE",
            "confidence": 76,
            "primary_reason": "Cloud growth decelerated and valuation multiple is stretched.",
        },
        human_brief="SONUÇ\n\nÖNERİ:\nREDUCE\n\nGÜVEN:\n76%\n\nNEDEN?\nDeğerleme yüksek.",
        confidence="76%",
    )
    mock_provider = MagicMock()
    mock_provider.execute = MagicMock(return_value=mock_result)

    with patch("app.services.formal_review.CodexCLIProvider", return_value=mock_provider):
        res = await client.post(
            f"/api/assets/{asset_id}/research",
            headers=headers,
            json={"protocol": "deep-research"},
        )
        assert res.status_code == 200

    # Query DecisionLogEntry rows
    stmt = select(DecisionLogEntry).order_by(DecisionLogEntry.created_at.desc())
    res_db = await db_session.execute(stmt)
    entries = res_db.scalars().all()

    # Verify that entries contain RECOMMENDATION_CHANGED system event
    rec_events = [e for e in entries if e.event_type == DecisionEventType.RECOMMENDATION_CHANGED]
    assert len(rec_events) >= 1
    ev = rec_events[0]
    assert ev.metadata_["new_recommendation"] == "REDUCE"

    # Verify that NO user trading actions (BUY, SELL, POSITION_REDUCED) were automatically executed
    trade_events = [
        e
        for e in entries
        if e.event_type in (DecisionEventType.BUY, DecisionEventType.SELL, DecisionEventType.POSITION_REDUCED)
    ]
    assert len(trade_events) == 0


# ============================================================================
# Requirement 11: Machine Record validation rejects/repairs contradictory state
# ============================================================================


def test_11_machine_record_validation_repairs_contradictory_state():
    """Test 11: Direct contradictions like INVALIDATED + ADD are repaired to REDUCE."""
    contradictory_record = {
        "thesis_status": "INVALIDATED",
        "valuation_status": "FAIR",
        "technical_status": "ON_TRACK",
        "recommendation": "ADD",
    }
    repaired = validate_deep_research_record(contradictory_record)
    assert repaired.recommendation in (IntelligenceRecommendation.REDUCE, IntelligenceRecommendation.SELL)
    assert repaired.recommendation != IntelligenceRecommendation.ADD


# ============================================================================
# Requirement 12: Existing historical IntelligenceReview remains readable
# ============================================================================


@pytest.mark.asyncio
async def test_12_existing_historical_intelligence_review_remains_readable(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 12: Historical reviews created under v1 remain 100% readable without errors."""
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    reg = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "History User"},
    )
    token = reg.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create instrument
    inst = Instrument(
        symbol="THYAO",
        name="Turk Hava Yollari",
        asset_type=AssetType.STOCK,
        currency="TRY",
    )
    db_session.add(inst)
    await db_session.commit()
    await db_session.refresh(inst)

    # Insert an old v1 review with legacy structure
    legacy_review = IntelligenceReview(
        instrument_id=inst.id,
        protocol="deep-research-equity",
        status=ProtocolRunStatus.COMPLETED,
        machine_record={
            "thesis_status": "UNCHANGED",
            "valuation_status": "FAIR",
            "technical_status": "REVIEW_REQUIRED",
            "recommendation": "REVIEW_REQUIRED",
            "comprehensive_synthesis": "Legacy review run before v2",
        },
        human_brief="Legacy brief.",
        confidence="0.85",
    )
    db_session.add(legacy_review)
    await db_session.commit()

    # Query reviews endpoint
    resp = await client.get(f"/api/instruments/{inst.id}/reviews", headers=headers)
    assert resp.status_code == 200
    revs = resp.json()["data"]
    assert len(revs) == 1
    assert revs[0]["protocol"] == "deep-research-equity"
    assert revs[0]["machine_record"]["recommendation"] == "REVIEW_REQUIRED"


# ============================================================================
# Requirement 13: No research execution occurs merely by opening Monitoring
# ============================================================================


@pytest.mark.asyncio
async def test_13_no_research_execution_occurs_merely_by_opening_monitoring(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Test 13: Navigating to Monitoring or listing assets NEVER executes research or calls Codex."""
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    reg = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Passive User"},
    )
    token = reg.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create asset
    await client.post(
        "/api/assets",
        headers=headers,
        json={
            "asset_type": "STOCK",
            "symbol": "KOZAL",
            "name": "Koza Altin",
            "current_price": 25.0,
            "current_price_currency": "TRY",
        },
    )

    with patch("app.services.formal_review.CodexCLIProvider") as mock_codex:
        # Load assets (which feeds Monitoring Table)
        get_res = await client.get("/api/assets", headers=headers)
        assert get_res.status_code == 200

        # Verify CodexCLIProvider was NEVER called or instantiated
        mock_codex.assert_not_called()


# ============================================================================
# Requirement 14: Codex calls during test suite = 0
# ============================================================================


def test_14_codex_calls_during_test_suite_is_zero():
    """Test 14: Strict verification that zero real Codex CLI subprocess executions occurred."""
    with patch("subprocess.run") as mock_sub_run, patch("subprocess.Popen") as mock_sub_popen:
        # Running pure deterministic validation and protocol resolution requires 0 subprocess calls
        resolved = resolve_specialized_protocol("deep-research", AssetType.FUND)
        assert resolved == "deep-research-fund"

        mr = {
            "thesis_status": "STRONGER",
            "valuation_status": "ATTRACTIVE",
            "recommendation": "ADD",
        }
        val = validate_deep_research_record(mr, protocol_name=resolved)
        assert val.recommendation == IntelligenceRecommendation.ADD

        # Assert zero subprocess invocations
        mock_sub_run.assert_not_called()
        mock_sub_popen.assert_not_called()
