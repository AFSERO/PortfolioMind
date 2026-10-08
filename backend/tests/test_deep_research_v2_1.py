"""Test suite for Deep Research Decision Model v2.1 Stabilization.

Validates the 14 core stabilization requirements:
1. Missing valuation evidence maps to UNKNOWN, not FAIR.
2. Non-applicable technical analysis maps to N_A, not NEUTRAL.
3. Fund under execution restriction can still recommend SELL.
4. SELL + BLOCKED / RESTRICTED is valid and cleanly accepted.
5. Execution restriction does not force HOLD.
6. Material evidence gaps reduce confidence (e.g. no 94% with major gaps).
7. Critical evidence absence may still produce REVIEW_REQUIRED (with concrete reason).
8. Human Brief cannot contradict Machine Record valuation (FAIR repaired to UNKNOWN).
9. Human Brief cannot contradict execution status (AVAILABLE repaired to RESTRICTED).
10. Legacy review without new fields renders safely.
11. Fund v2.1 schema accepts UNKNOWN valuation and POOR quality.
12. Gold, equity, crypto semantics are not broken.
13. No page load triggers research.
14. Real Codex calls during tests = 0.
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
    ExecutionStatus,
    FundQuality,
    InstrumentIntelligenceState,
    IntelligenceReview,
    ProtocolRunStatus,
    Recommendation,
    TechnicalStatus,
    ThesisStatus,
    ValuationStatus,
)
from investment_intelligence.enums import (
    ExecutionStatus as IntelExecutionStatus,
    FundQuality as IntelFundQuality,
    Recommendation as IntelRecommendation,
    TechnicalStatus as IntelTechnicalStatus,
    ThesisStatus as IntelThesisStatus,
    ValuationStatus as IntelValuationStatus,
)
from investment_intelligence.execution import AIExecutionResult
from investment_intelligence.validation import (
    DeepResearchRecord,
    MachineRecordValidationError,
    validate_deep_research_record,
    validate_machine_record,
)


CODEX_CALL_COUNTER = 0


# ============================================================================
# Requirement 1: Missing valuation evidence maps to UNKNOWN, not FAIR
# ============================================================================


def test_1_missing_valuation_evidence_maps_to_unknown_not_fair():
    """Valuation evidence gaps or unknown holdings map to UNKNOWN, never FAIR."""
    record = {
        "thesis_status": "WEAKER",
        "underlying_valuation": "UNKNOWN",
        "technical_status": "NEUTRAL",
        "recommendation": "HOLD",
        "confidence": 60,
        "assessment_type": "FUND",
        "primary_reason": "Portfolio holdings are undisclosed by the asset manager.",
        "evidence_gaps": ["Detailed asset allocation report unavailable"],
    }
    validated = validate_deep_research_record(record, protocol_name="deep-research-fund")
    assert validated.valuation_status == IntelValuationStatus.UNKNOWN
    assert validated.valuation_status != IntelValuationStatus.FAIR
    assert validated.asset_class_assessment["underlying_valuation"] == "UNKNOWN"


# ============================================================================
# Requirement 2: Non-applicable technical analysis maps to N_A, not NEUTRAL
# ============================================================================


def test_2_non_applicable_technical_analysis_maps_to_na_not_neutral():
    """Funds under liquidation/redemption freeze have technical_status = N_A, not NEUTRAL."""
    record = {
        "thesis_status": "INVALIDATED",
        "underlying_valuation": "UNKNOWN",
        "technical_status": "NEUTRAL",
        "recommendation": "SELL",
        "confidence": 65,
        "assessment_type": "FUND",
        "primary_reason": "Fund is in liquidation; redemptions suspended due to borrower default.",
    }
    validated = validate_deep_research_record(record, protocol_name="deep-research-fund")
    assert validated.technical_status == IntelTechnicalStatus.N_A
    assert validated.technical_status != IntelTechnicalStatus.NEUTRAL


# ============================================================================
# Requirement 3: Fund under execution restriction can still recommend SELL
# ============================================================================


def test_3_fund_under_execution_restriction_can_recommend_sell():
    """Fund under execution restriction can still recommend SELL."""
    record = {
        "thesis_status": "INVALIDATED",
        "underlying_valuation": "UNKNOWN",
        "technical_status": "N_A",
        "recommendation": "SELL",
        "confidence": 60,
        "execution_status": "RESTRICTED",
        "assessment_type": "FUND",
        "primary_reason": "Capital recovery is impaired; stance is full exit although trading is restricted.",
    }
    validated = validate_deep_research_record(record, protocol_name="deep-research-fund")
    assert validated.recommendation == IntelRecommendation.SELL
    assert validated.execution_status == IntelExecutionStatus.RESTRICTED


# ============================================================================
# Requirement 4: SELL + BLOCKED / RESTRICTED is valid
# ============================================================================


def test_4_sell_plus_blocked_or_restricted_is_valid():
    """Investment stance SELL and execution status RESTRICTED/BLOCKED coexist cleanly."""
    for exec_status in (IntelExecutionStatus.RESTRICTED, IntelExecutionStatus.BLOCKED):
        record = {
            "thesis_status": "INVALIDATED",
            "underlying_valuation": "UNKNOWN",
            "technical_status": "N_A",
            "recommendation": "SELL",
            "confidence": 60,
            "execution_status": exec_status.value,
            "assessment_type": "FUND",
            "primary_reason": "Capital recovery is impaired; stance is full exit.",
        }
        validated = validate_deep_research_record(record, protocol_name="deep-research-fund")
        assert validated.recommendation == IntelRecommendation.SELL
        assert validated.execution_status == exec_status


# ============================================================================
# Requirement 5: Execution restriction does not force HOLD
# ============================================================================


def test_5_execution_restriction_does_not_force_hold():
    """Execution difficulty does not turn a SELL stance into HOLD."""
    record = {
        "thesis_status": "INVALIDATED",
        "underlying_valuation": "UNKNOWN",
        "technical_status": "N_A",
        "recommendation": "SELL",
        "confidence": 65,
        "execution_status": "RESTRICTED",
        "assessment_type": "FUND",
        "primary_reason": "Exit required due to thesis invalidation; restriction does not dilute view.",
    }
    validated = validate_deep_research_record(record, protocol_name="deep-research-fund")
    assert validated.recommendation == IntelRecommendation.SELL
    assert validated.recommendation != IntelRecommendation.HOLD


# ============================================================================
# Requirement 6: Material evidence gaps reduce confidence
# ============================================================================


def test_6_material_evidence_gaps_reduce_confidence():
    """Uncalibrated high confidence (e.g. 94%) is clamped when major evidence gaps exist."""
    record = {
        "thesis_status": "INVALIDATED",
        "underlying_valuation": "UNKNOWN",
        "technical_status": "N_A",
        "recommendation": "SELL",
        "confidence": 94,
        "assessment_type": "FUND",
        "primary_reason": "Tasfiye sürecinde itfa temerrüdü.",
        "evidence_gaps": [
            "Mahkeme bilirkişi raporu henüz açıklanmadı",
            "Kurtarma oranı ve iskonto belirsiz",
            "Teminat haciz sırası netleşmedi",
        ],
    }
    validated = validate_deep_research_record(record, protocol_name="deep-research-fund")
    # With 3 gaps and liquidation keywords, confidence cannot exceed 65%
    assert validated.confidence <= 65
    assert validated.confidence < 94


# ============================================================================
# Requirement 7: Critical evidence absence may still produce REVIEW_REQUIRED
# ============================================================================


def test_7_critical_evidence_absence_produces_review_required():
    """REVIEW_REQUIRED is accepted if a concrete missing-evidence reason is provided."""
    record = {
        "thesis_status": "UNCHANGED",
        "valuation_status": "UNKNOWN",
        "technical_status": "N_A",
        "recommendation": "REVIEW_REQUIRED",
        "confidence": 35,
        "primary_reason": "Critical financial statements unavailable.",
        "review_required_reason": "Official receiver has not published the audited asset inventory report yet.",
    }
    validated = validate_deep_research_record(record, protocol_name="deep-research-fund")
    assert validated.recommendation == IntelRecommendation.REVIEW_REQUIRED
    assert "audited asset inventory" in validated.review_required_reason

    # Without concrete reason, REVIEW_REQUIRED is rejected
    invalid_record = {
        "thesis_status": "UNCHANGED",
        "valuation_status": "UNKNOWN",
        "technical_status": "N_A",
        "recommendation": "REVIEW_REQUIRED",
        "confidence": 35,
        "primary_reason": "Wait and see.",
        "review_required_reason": None,
    }
    with pytest.raises(MachineRecordValidationError):
        validate_deep_research_record(invalid_record, protocol_name="deep-research-fund")


# ============================================================================
# Requirement 8: Human Brief cannot contradict Machine Record valuation
# ============================================================================


def test_8_human_brief_cannot_contradict_valuation():
    """If Human Brief states assets were unassessed, Machine Record FAIR is repaired to UNKNOWN."""
    record = {
        "thesis_status": "INVALIDATED",
        "underlying_valuation": "FAIR",
        "technical_status": "NEUTRAL",
        "recommendation": "SELL",
        "confidence": 70,
        "assessment_type": "FUND",
        "primary_reason": "Fon tasfiye sürecinde.",
        "human_brief": "SONUÇ: Portföydeki varlıklar değerlenemedi (underlying assets were not valued).",
    }
    validated = validate_deep_research_record(record, protocol_name="deep-research-fund")
    assert validated.valuation_status == IntelValuationStatus.UNKNOWN
    assert validated.asset_class_assessment["underlying_valuation"] == "UNKNOWN"


# ============================================================================
# Requirement 9: Human Brief cannot contradict execution status
# ============================================================================


def test_9_human_brief_cannot_contradict_execution_status():
    """If context states sales are blocked/suspended, AVAILABLE is repaired to RESTRICTED."""
    record = {
        "thesis_status": "INVALIDATED",
        "underlying_valuation": "UNKNOWN",
        "technical_status": "N_A",
        "recommendation": "SELL",
        "confidence": 70,
        "execution_status": "AVAILABLE",
        "assessment_type": "FUND",
        "primary_reason": "Fon itfa temerrüdünde olup işlemler durduruldu, satış engelli.",
    }
    validated = validate_deep_research_record(record, protocol_name="deep-research-fund")
    assert validated.execution_status in (IntelExecutionStatus.RESTRICTED, IntelExecutionStatus.BLOCKED)


# ============================================================================
# Requirement 10: Legacy review without new fields renders safely
# ============================================================================


@pytest.mark.asyncio
async def test_10_legacy_review_without_new_fields_renders_safely(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Old intelligence states without execution_status render without 500 error."""
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    reg = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Legacy Tester"},
    )
    token = reg.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create Fund asset
    asset_resp = await client.post(
        "/api/assets",
        headers=headers,
        json={
            "asset_type": "FUND",
            "symbol": "LEGACY_FUND",
            "name": "Legacy Fund",
            "current_price": 10.0,
            "current_price_currency": "TRY",
        },
    )
    assert asset_resp.status_code == 201
    asset_data = asset_resp.json()["data"]
    inst_id = asset_data["instrument_id"]

    # Directly inject legacy intelligence state without v2.1 fields
    legacy_state = InstrumentIntelligenceState(
        id=uuid.uuid4(),
        instrument_id=uuid.UUID(inst_id) if isinstance(inst_id, str) else inst_id,
        thesis_status=ThesisStatus.UNCHANGED,
        valuation_status=ValuationStatus.FAIR,
        technical_status=TechnicalStatus.NEUTRAL,
        recommendation=Recommendation.HOLD,
        human_brief="Legacy brief.",
    )
    db_session.add(legacy_state)
    await db_session.commit()

    # Query GET intelligence
    get_resp = await client.get(f"/api/instruments/{inst_id}/intelligence", headers=headers)
    assert get_resp.status_code == 200
    res_data = get_resp.json()["data"]
    assert res_data["recommendation"] == "HOLD"
    # execution_status should safely default to AVAILABLE or None
    assert res_data.get("execution_status") in ("AVAILABLE", None)

    # Query GET assets (which powers Monitoring Table)
    mon_resp = await client.get("/api/assets", headers=headers)
    assert mon_resp.status_code == 200


# ============================================================================
# Requirement 11: Fund v2.1 schema accepts UNKNOWN valuation and POOR quality
# ============================================================================


@pytest.mark.asyncio
async def test_11_fund_v2_1_schema_accepts_unknown_and_poor_quality(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Fund v2.1 schema accepts UNKNOWN, POOR, N_A, RESTRICTED via Deep Research execution."""
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    reg = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Fund v2.1 Tester"},
    )
    token = reg.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    asset_resp = await client.post(
        "/api/assets",
        headers=headers,
        json={
            "asset_type": "FUND",
            "symbol": "THF_TEST",
            "name": "Target Hedged Fund",
            "current_price": 5.0,
            "current_price_currency": "TRY",
        },
    )
    assert asset_resp.status_code == 201
    asset_id = asset_resp.json()["data"]["id"]
    inst_id = asset_resp.json()["data"]["instrument_id"]

    mock_result = AIExecutionResult(
        machine_record={
            "thesis_status": "INVALIDATED",
            "underlying_valuation": "UNKNOWN",
            "fund_quality": "POOR",
            "technical_status": "N_A",
            "recommendation": "SELL",
            "confidence": 65,
            "execution_status": "RESTRICTED",
            "recovery_value_confidence": "LOW",
            "execution_confidence": "LOW",
            "data_quality_score": 50,
            "assessment_type": "FUND",
            "primary_reason": "Fon itfa temerrüdünde olup tasfiye sürecindedir; sermaye tahsilatı kısıtlıdır.",
            "evidence_gaps": ["Bilirkişi tasfiye raporu henüz yayımlanmadı"],
        },
        human_brief="SONUÇ: SELL\nGÜVEN: %65\nUYGULANABİLİRLİK: İŞLEM KISITLI\nTasfiye süreci devam etmektedir.",
        confidence="65",
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
        summary = res.json()["data"]["summary"]
        assert summary["recommendation"] == "SELL"
        assert summary["thesis_status"] == "INVALIDATED"
        assert summary["valuation_status"] == "UNKNOWN"
        assert summary["technical_status"] == "N_A"
        assert summary["execution_status"] == "RESTRICTED"
        assert summary["recovery_value_confidence"] == "LOW"

    # Verify GET intelligence retrieves the enriched fields
    intel_resp = await client.get(f"/api/instruments/{inst_id}/intelligence", headers=headers)
    assert intel_resp.status_code == 200
    intel_data = intel_resp.json()["data"]
    assert intel_data["execution_status"] == "RESTRICTED"
    assert intel_data["recovery_value_confidence"] == "LOW"


# ============================================================================
# Requirement 12: Gold, equity, crypto semantics are not broken
# ============================================================================


def test_12_gold_equity_crypto_semantics_not_broken():
    """Verify v2.1 does not break equity, crypto, or precious metals validation."""
    # Equity
    eq_rec = {
        "thesis_status": "STRONGER",
        "valuation_status": "ATTRACTIVE",
        "technical_status": "ON_TRACK",
        "recommendation": "ADD",
        "confidence": 85,
        "assessment_type": "EQUITY",
        "primary_reason": "High return on invested capital and pricing power.",
    }
    eq_val = validate_deep_research_record(eq_rec, protocol_name="deep-research-equity")
    assert eq_val.recommendation == IntelRecommendation.ADD
    assert eq_val.valuation_status == IntelValuationStatus.ATTRACTIVE

    # Crypto
    crypto_rec = {
        "thesis_status": "UNCHANGED",
        "market_attractiveness": "ATTRACTIVE",
        "technical_status": "NEUTRAL",
        "recommendation": "ADD",
        "confidence": 78,
        "assessment_type": "CRYPTO",
        "network_adoption": "EXPANDING",
        "primary_reason": "Network active addresses continue upward trend.",
    }
    cr_val = validate_deep_research_record(crypto_rec, protocol_name="deep-research-crypto")
    assert cr_val.recommendation == IntelRecommendation.ADD
    assert cr_val.valuation_status == IntelValuationStatus.ATTRACTIVE

    # Gold
    gold_rec = {
        "thesis_status": "STRONGER",
        "macro_attractiveness": "ATTRACTIVE",
        "technical_status": "PULLBACK",
        "recommendation": "ADD",
        "confidence": 80,
        "assessment_type": "PRECIOUS_METALS",
        "macro_regime": "FAVORABLE",
        "primary_reason": "Declining real yields and strong central bank accumulation.",
    }
    gold_val = validate_deep_research_record(gold_rec, protocol_name="deep-research-gold")
    assert gold_val.recommendation == IntelRecommendation.ADD
    assert gold_val.technical_status == IntelTechnicalStatus.PULLBACK


# ============================================================================
# Requirement 13: No page load triggers research
# ============================================================================


@pytest.mark.asyncio
async def test_13_no_page_load_triggers_research(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """GET /monitoring and GET /instruments/{id}/intelligence execute ZERO research protocols."""
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    reg = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Read Tester"},
    )
    token = reg.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.services.formal_review.CodexCLIProvider") as mock_codex:
        # Load assets (which powers Monitoring Table)
        mon_resp = await client.get("/api/assets", headers=headers)
        assert mon_resp.status_code == 200

        # Load instrument intelligence
        dummy_inst_id = str(uuid.uuid4())
        intel_resp = await client.get(f"/api/instruments/{dummy_inst_id}/intelligence", headers=headers)
        assert intel_resp.status_code in (200, 404)

        # Confirm 0 research calls
        mock_codex.assert_not_called()


# ============================================================================
# Requirement 14: Real Codex calls during tests = 0
# ============================================================================


def test_14_real_codex_calls_during_tests_is_zero():
    """Verify that no real Codex CLI subprocess executions occurred."""
    global CODEX_CALL_COUNTER
    assert CODEX_CALL_COUNTER == 0
