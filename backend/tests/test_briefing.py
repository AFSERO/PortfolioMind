"""Tests for Intelligence Briefing: on-demand generation, noise filtering,
stats pulse, and latest briefing retrieval.
"""

import uuid
from unittest.mock import MagicMock, patch
import pytest
from httpx import AsyncClient

from app.models.briefing import BriefingMateriality


async def _register_user(client: AsyncClient, email: str = "briefing_user@example.com") -> tuple[str, dict]:
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "display_name": "Briefing Tester",
        },
    )
    token = resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return token, headers


@pytest.mark.asyncio
async def test_latest_briefing_initially_empty(client: AsyncClient):
    _, headers = await _register_user(client, f"br_empty_{uuid.uuid4().hex[:6]}@example.com")

    resp = await client.get("/api/briefing/latest", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"] is None

    stats_resp = await client.get("/api/briefing/stats", headers=headers)
    assert stats_resp.status_code == 200
    assert stats_resp.json()["data"]["attention_count"] == 0
    assert stats_resp.json()["data"]["items_shown"] == 0


@pytest.mark.asyncio
async def test_generate_briefing_with_owned_asset(client: AsyncClient):
    _, headers = await _register_user(client, f"br_gen_{uuid.uuid4().hex[:6]}@example.com")

    # Create an owned asset (e.g. AAPL)
    asset_payload = {
        "asset_type": "STOCK",
        "symbol": "AAPL",
        "name": "Apple Inc",
        "current_price_currency": "USD",
        "initial_transaction": {
            "transaction_type": "BUY",
            "quantity": "5",
            "price_per_unit": "180.00",
            "transaction_currency": "USD",
            "transaction_date": "2024-06-01",
        },
    }
    await client.post("/api/assets", json=asset_payload, headers=headers)

    # Generate briefing
    resp = await client.post("/api/briefing/generate", json={"force_refresh": True}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "COMPLETED"
    assert data["scope"] == "PORTFOLIO_AND_WATCHLIST"
    assert "items_found" in data
    assert "items_shown" in data
    assert "items_filtered" in data

    # Verify latest returns the generated run
    latest_resp = await client.get("/api/briefing/latest", headers=headers)
    assert latest_resp.status_code == 200
    assert latest_resp.json()["data"]["id"] == data["id"]

    # Verify stats
    stats_resp = await client.get("/api/briefing/stats", headers=headers)
    assert stats_resp.status_code == 200
    stats = stats_resp.json()["data"]
    assert stats["items_shown"] == data["items_shown"]
    assert stats["items_filtered"] == data["items_filtered"]


def test_clean_instrument_name():
    from app.services.briefing import _clean_instrument_name

    assert _clean_instrument_name("Alphabet Inc. (Google)", "GOOGL") == "Alphabet"
    assert _clean_instrument_name("Uber Technologies, Inc.", "UBER") == "Uber Technologies"
    assert _clean_instrument_name("Ons Altın / Gold (USD/oz)", "XAU") in ("Gold", "Ons Altin")
    assert _clean_instrument_name("Ethereum (ETH)", "ETH") == "Ethereum"
    assert _clean_instrument_name("", "AAPL") == "AAPL"


def test_classify_development_noise_filtering():
    from app.models.briefing import BriefingCategory, BriefingMateriality
    from app.services.briefing import _classify_development

    # Noise article should be filtered to LOW
    cat, impact, mat, horizon, thesis, rev_req, why = _classify_development(
        "3 Stocks to Buy Right Now: Is It a Good Pick?",
        "Zacks investment research offers their weekly recap and predictions.",
        is_portfolio=True,
    )
    assert mat == BriefingMateriality.LOW
    assert not rev_req

    # High materiality despite noise word if actual SEC/filing event
    cat, impact, mat, horizon, thesis, rev_req, why = _classify_development(
        "Company facing DOJ antitrust probe and restructuring",
        "Regulators issue formal subpoena into acquisition of competitor.",
        is_portfolio=True,
    )
    assert mat == BriefingMateriality.HIGH
    assert rev_req
    assert cat in (BriefingCategory.REGULATORY, BriefingCategory.OPERATIONAL)


def test_classify_development_sec_filings():
    from app.models.briefing import BriefingCategory, BriefingImpact, BriefingMateriality
    from app.services.briefing import _classify_development

    # SEC 8-K
    cat, impact, mat, horizon, thesis, rev_req, why = _classify_development(
        "UBER SEC 8-K: Official Filing",
        "Official SEC 8-K filing submitted on 2026-09-15.",
        is_portfolio=True,
        is_sec=True,
        sec_form="8-K",
        symbol="UBER",
    )
    assert cat == BriefingCategory.REGULATORY
    assert mat == BriefingMateriality.HIGH
    assert rev_req is True
    assert "8-K" in why

    # SEC 10-Q
    cat, impact, mat, horizon, thesis, rev_req, why = _classify_development(
        "GOOGL SEC 10-Q: Official Filing",
        "Quarterly report pursuant to Section 13 or 15(d).",
        is_portfolio=True,
        is_sec=True,
        sec_form="10-Q",
        symbol="GOOGL",
    )
    assert cat == BriefingCategory.EARNINGS
    assert mat == BriefingMateriality.HIGH
    assert rev_req is True

    # SEC Form 4 (insider reporting)
    cat, impact, mat, horizon, thesis, rev_req, why = _classify_development(
        "UBER SEC 4: Official Filing",
        "Statement of changes in beneficial ownership.",
        is_portfolio=False,
        is_sec=True,
        sec_form="4",
        symbol="UBER",
    )
    assert cat == BriefingCategory.OPERATIONAL
    assert mat == BriefingMateriality.MEDIUM
    assert rev_req is False


def test_classify_development_macro_and_operational():
    from app.models.briefing import BriefingCategory, BriefingImpact, BriefingMateriality
    from app.services.briefing import _classify_development

    # High materiality macro event (rate cut)
    cat, impact, mat, horizon, thesis, rev_req, why = _classify_development(
        "Fed signals rate cut as inflation drops to 2.1%",
        "Federal reserve chairman notes cooling CPI and labor market stability.",
        is_portfolio=True,
    )
    assert cat == BriefingCategory.MACRO
    assert mat == BriefingMateriality.HIGH
    assert rev_req is True

    # Standard macro news without extreme keywords
    cat, impact, mat, horizon, thesis, rev_req, why = _classify_development(
        "Treasury yield holds steady following GDP report",
        "Economic indicators remain consistent with previous month baseline.",
        is_portfolio=True,
    )
    assert cat == BriefingCategory.MACRO
    assert mat == BriefingMateriality.MEDIUM

    # Operational partnership
    cat, impact, mat, horizon, thesis, rev_req, why = _classify_development(
        "Uber expands Costco delivery partnership to 7 new markets",
        "Expansion aims to drive higher delivery margins and volume beat.",
        is_portfolio=False,
    )
    assert cat == BriefingCategory.OPERATIONAL
    assert impact == BriefingImpact.POSITIVE
    assert mat == BriefingMateriality.MEDIUM


@pytest.mark.asyncio
async def test_generate_briefing_multi_asset_portfolio(client: AsyncClient):
    _, headers = await _register_user(client, f"br_multi_{uuid.uuid4().hex[:6]}@example.com")

    # Add Crypto asset (ETH)
    await client.post(
        "/api/assets",
        json={
            "asset_type": "CRYPTO",
            "symbol": "ETH",
            "name": "Ethereum (ETH)",
            "current_price_currency": "USD",
            "initial_transaction": {
                "transaction_type": "BUY",
                "quantity": "2",
                "price_per_unit": "3200.00",
                "transaction_currency": "USD",
                "transaction_date": "2024-06-01",
            },
        },
        headers=headers,
    )

    # Add Commodity asset (XAU)
    await client.post(
        "/api/assets",
        json={
            "asset_type": "GOLD",
            "symbol": "XAU",
            "name": "Ons Altın / Gold (USD/oz)",
            "current_price_currency": "USD",
            "initial_transaction": {
                "transaction_type": "BUY",
                "quantity": "10",
                "price_per_unit": "2400.00",
                "transaction_currency": "USD",
                "transaction_date": "2024-06-01",
            },
        },
        headers=headers,
    )

    # Add US Stock asset (GOOGL)
    await client.post(
        "/api/assets",
        json={
            "asset_type": "STOCK",
            "symbol": "GOOGL",
            "name": "Alphabet Inc. (Google)",
            "current_price_currency": "USD",
            "initial_transaction": {
                "transaction_type": "BUY",
                "quantity": "10",
                "price_per_unit": "170.00",
                "transaction_currency": "USD",
                "transaction_date": "2024-06-01",
            },
        },
        headers=headers,
    )

    # Generate briefing
    resp = await client.post("/api/briefing/generate", json={"force_refresh": True}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "COMPLETED"
    assert data["items_shown"] >= 0
    assert data["items_filtered"] >= 0


# ============================================================================
# Selective Codex Reasoning Tests (10 Scenarios)
# ============================================================================

from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from investment_intelligence import (
    BriefingAssessment,
    BriefingAssessmentError,
)
from investment_intelligence.providers import DisclosureItemRecord, NewsItemRecord


@pytest.mark.asyncio
async def test_selective_reasoning_low_filtered_no_codex(client: AsyncClient):
    """1. LOW event -> filtered out as noise, Codex reasoning is NEVER invoked."""
    token, headers = await _register_user(client, f"br_low_{uuid.uuid4().hex[:6]}@example.com")
    await client.post(
        "/api/assets",
        json={
            "asset_type": "STOCK",
            "symbol": "UBER",
            "name": "Uber Technologies Inc",
            "current_price_currency": "USD",
            "initial_transaction": {
                "transaction_type": "BUY",
                "quantity": "10",
                "price_per_unit": "50.00",
                "transaction_currency": "USD",
                "transaction_date": "2024-06-01",
            },
        },
        headers=headers,
    )

    mock_news_item = NewsItemRecord(
        title="3 Stocks to Buy Right Now: Top Picks for 2026",
        published_at=datetime.now(timezone.utc),
        source="MarketWatch",
        url="https://marketwatch.com/noise-article",
        instrument_id=uuid.uuid4(),
        source_quality="RADAR_UNVERIFIED",
    )

    mock_reasoner = MagicMock()

    with patch("app.services.briefing.GoogleNewsRSSProvider") as mock_news_cls, \
         patch("app.services.briefing.SECDisclosureProvider") as mock_sec_cls, \
         patch("app.services.briefing.BriefingReasoner", return_value=mock_reasoner):

        mock_news_inst = MagicMock()
        mock_news_inst.get_recent_news.return_value = [mock_news_item]
        mock_news_cls.return_value = mock_news_inst

        mock_sec_inst = MagicMock()
        mock_sec_inst.get_recent_disclosures.return_value = []
        mock_sec_cls.return_value = mock_sec_inst

        resp = await client.post("/api/briefing/generate", json={"force_refresh": True}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]

        # Codex was NOT called
        assert mock_reasoner.assess_event.call_count == 0
        # Filtered as noise
        assert data["items_filtered"] >= 1
        assert len(data["items"]) == 0


@pytest.mark.asyncio
async def test_selective_reasoning_medium_deterministic_no_codex(client: AsyncClient):
    """2. MEDIUM event -> kept deterministically, Codex reasoning is NOT invoked."""
    token, headers = await _register_user(client, f"br_med_{uuid.uuid4().hex[:6]}@example.com")
    await client.post(
        "/api/assets",
        json={
            "asset_type": "STOCK",
            "symbol": "UBER",
            "name": "Uber Technologies Inc",
            "current_price_currency": "USD",
            "initial_transaction": {
                "transaction_type": "BUY",
                "quantity": "10",
                "price_per_unit": "50.00",
                "transaction_currency": "USD",
                "transaction_date": "2024-06-01",
            },
        },
        headers=headers,
    )

    mock_news_item = NewsItemRecord(
        title="Uber expands delivery partnership to new local markets",
        published_at=datetime.now(timezone.utc),
        source="Reuters",
        url="https://reuters.com/uber-partner",
        instrument_id=uuid.uuid4(),
        source_quality="RADAR_UNVERIFIED",
    )

    mock_reasoner = MagicMock()

    with patch("app.services.briefing.GoogleNewsRSSProvider") as mock_news_cls, \
         patch("app.services.briefing.SECDisclosureProvider") as mock_sec_cls, \
         patch("app.services.briefing.BriefingReasoner", return_value=mock_reasoner):

        mock_news_inst = MagicMock()
        mock_news_inst.get_recent_news.return_value = [mock_news_item]
        mock_news_cls.return_value = mock_news_inst

        mock_sec_inst = MagicMock()
        mock_sec_inst.get_recent_disclosures.return_value = []
        mock_sec_cls.return_value = mock_sec_inst

        resp = await client.post("/api/briefing/generate", json={"force_refresh": True}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]

        # Codex was NOT called
        assert mock_reasoner.assess_event.call_count == 0
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["materiality"] == "MEDIUM"
        assert item["review_required"] is False
        assert item["source_metadata"]["reasoning_source"] == "DETERMINISTIC"


@pytest.mark.asyncio
async def test_selective_reasoning_high_triggers_codex(client: AsyncClient):
    """3. HIGH event -> Codex reasoning IS invoked with bounded context."""
    token, headers = await _register_user(client, f"br_high_{uuid.uuid4().hex[:6]}@example.com")
    await client.post(
        "/api/assets",
        json={
            "asset_type": "STOCK",
            "symbol": "UBER",
            "name": "Uber Technologies Inc",
            "current_price_currency": "USD",
            "initial_transaction": {
                "transaction_type": "BUY",
                "quantity": "10",
                "price_per_unit": "50.00",
                "transaction_currency": "USD",
                "transaction_date": "2024-06-01",
            },
        },
        headers=headers,
    )

    mock_news_item = NewsItemRecord(
        title="DOJ launches antitrust probe and files lawsuit against corporate practices",
        published_at=datetime.now(timezone.utc),
        source="Financial Times",
        url="https://ft.com/antitrust-uber",
        instrument_id=uuid.uuid4(),
        source_quality="RADAR_UNVERIFIED",
    )

    mock_reasoner = MagicMock()
    mock_reasoner.assess_event.return_value = BriefingAssessment(
        event_summary="DOJ antitrust investigation",
        impact="NEGATIVE",
        materiality="HIGH",
        time_horizon="LONG",
        thesis_impact="WEAKER",
        review_required=True,
        why_it_matters="DOJ probe introduces serious regulatory overhang and legal defense costs.",
        recommended_review="Thesis Review",
        confidence="HIGH",
    )

    with patch("app.services.briefing.GoogleNewsRSSProvider") as mock_news_cls, \
         patch("app.services.briefing.SECDisclosureProvider") as mock_sec_cls, \
         patch("app.services.briefing.BriefingReasoner", return_value=mock_reasoner):

        mock_news_inst = MagicMock()
        mock_news_inst.get_recent_news.return_value = [mock_news_item]
        mock_news_cls.return_value = mock_news_inst

        mock_sec_inst = MagicMock()
        mock_sec_inst.get_recent_disclosures.return_value = []
        mock_sec_cls.return_value = mock_sec_inst

        resp = await client.post("/api/briefing/generate", json={"force_refresh": True}, headers=headers)
        assert resp.status_code == 200

        # Codex was called once with context
        assert mock_reasoner.assess_event.call_count == 1
        call_kwargs = mock_reasoner.assess_event.call_args.kwargs
        assert call_kwargs["instrument"]["symbol"] == "UBER"
        assert "event" in call_kwargs


@pytest.mark.asyncio
async def test_selective_reasoning_review_required_triggers_codex(client: AsyncClient):
    """4. review_required event (SEC 8-K) -> Codex reasoning IS invoked."""
    token, headers = await _register_user(client, f"br_rr_{uuid.uuid4().hex[:6]}@example.com")
    await client.post(
        "/api/assets",
        json={
            "asset_type": "STOCK",
            "symbol": "UBER",
            "name": "Uber Technologies Inc",
            "current_price_currency": "USD",
            "initial_transaction": {
                "transaction_type": "BUY",
                "quantity": "10",
                "price_per_unit": "50.00",
                "transaction_currency": "USD",
                "transaction_date": "2024-06-01",
            },
        },
        headers=headers,
    )

    mock_sec_item = DisclosureItemRecord(
        instrument_id=uuid.uuid4(),
        disclosure_type="8-K",
        title="UBER SEC 8-K: Material Definitive Agreement",
        published_at=datetime.now(timezone.utc),
        source="SEC EDGAR",
        url="https://sec.gov/edgar/uber-8k",
        document_id="0001234567-26-000001",
        metadata={"filing_date": "2026-09-16"},
    )

    mock_reasoner = MagicMock()
    mock_reasoner.assess_event.return_value = BriefingAssessment(
        event_summary="Material definitive agreement",
        impact="POSITIVE",
        materiality="HIGH",
        time_horizon="MEDIUM",
        thesis_impact="STRONGER",
        review_required=True,
        why_it_matters="Long-term partnership agreement secures high-margin distribution channel.",
        recommended_review="Thesis Review",
        confidence="HIGH",
    )

    with patch("app.services.briefing.GoogleNewsRSSProvider") as mock_news_cls, \
         patch("app.services.briefing.SECDisclosureProvider") as mock_sec_cls, \
         patch("app.services.briefing.BriefingReasoner", return_value=mock_reasoner):

        mock_news_inst = MagicMock()
        mock_news_inst.get_recent_news.return_value = []
        mock_news_cls.return_value = mock_news_inst

        mock_sec_inst = MagicMock()
        mock_sec_inst.get_recent_disclosures.return_value = [mock_sec_item]
        mock_sec_cls.return_value = mock_sec_inst

        resp = await client.post("/api/briefing/generate", json={"force_refresh": True}, headers=headers)
        assert resp.status_code == 200

        # Codex was called
        assert mock_reasoner.assess_event.call_count == 1


@pytest.mark.asyncio
async def test_valid_codex_result_enriches_briefing_item(client: AsyncClient):
    """5. Valid Codex result enriches BriefingItem with AI provenance, impact, and recommendation."""
    token, headers = await _register_user(client, f"br_enrich_{uuid.uuid4().hex[:6]}@example.com")
    await client.post(
        "/api/assets",
        json={
            "asset_type": "STOCK",
            "symbol": "UBER",
            "name": "Uber Technologies Inc",
            "current_price_currency": "USD",
            "initial_transaction": {
                "transaction_type": "BUY",
                "quantity": "10",
                "price_per_unit": "50.00",
                "transaction_currency": "USD",
                "transaction_date": "2024-06-01",
            },
        },
        headers=headers,
    )

    mock_news_item = NewsItemRecord(
        title="DOJ probe expands into global ride-hailing regulatory compliance",
        published_at=datetime.now(timezone.utc),
        source="Reuters",
        url="https://reuters.com/probe-expanded",
        instrument_id=uuid.uuid4(),
        source_quality="RADAR_UNVERIFIED",
    )

    mock_reasoner = MagicMock()
    mock_reasoner.assess_event.return_value = BriefingAssessment(
        event_summary="Regulatory compliance expansion",
        impact="NEGATIVE",
        materiality="CRITICAL",
        time_horizon="LONG",
        thesis_impact="WEAKER",
        review_required=True,
        why_it_matters="Codex analysis: Regulatory fines and structural limits directly degrade EBITDA margins.",
        recommended_review="Thesis Review",
        confidence="HIGH",
    )

    with patch("app.services.briefing.GoogleNewsRSSProvider") as mock_news_cls, \
         patch("app.services.briefing.SECDisclosureProvider") as mock_sec_cls, \
         patch("app.services.briefing.BriefingReasoner", return_value=mock_reasoner):

        mock_news_inst = MagicMock()
        mock_news_inst.get_recent_news.return_value = [mock_news_item]
        mock_news_cls.return_value = mock_news_inst

        mock_sec_inst = MagicMock()
        mock_sec_inst.get_recent_disclosures.return_value = []
        mock_sec_cls.return_value = mock_sec_inst

        resp = await client.post("/api/briefing/generate", json={"force_refresh": True}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]

        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["impact"] == "NEGATIVE"
        assert item["materiality"] == "CRITICAL"
        assert item["time_horizon"] == "LONG"
        assert item["thesis_impact"] == "WEAKER"
        assert item["review_required"] is True
        assert item["why_it_matters"] == "Codex analysis: Regulatory fines and structural limits directly degrade EBITDA margins."
        assert item["source_metadata"]["reasoning_source"] == "CODEX"
        assert item["source_metadata"]["recommended_review"] == "Thesis Review"
        assert item["source_metadata"]["reasoning_confidence"] == "HIGH"
        assert "reasoning_generated_at" in item["source_metadata"]


@pytest.mark.asyncio
async def test_codex_timeout_fail_open_fallback(client: AsyncClient):
    """6. Codex timeout -> fail-open: deterministic fallback persists with fallback provenance."""
    token, headers = await _register_user(client, f"br_timeout_{uuid.uuid4().hex[:6]}@example.com")
    await client.post(
        "/api/assets",
        json={
            "asset_type": "STOCK",
            "symbol": "UBER",
            "name": "Uber Technologies Inc",
            "current_price_currency": "USD",
            "initial_transaction": {
                "transaction_type": "BUY",
                "quantity": "10",
                "price_per_unit": "50.00",
                "transaction_currency": "USD",
                "transaction_date": "2024-06-01",
            },
        },
        headers=headers,
    )

    mock_news_item = NewsItemRecord(
        title="DOJ probe into ride hailing operations announced",
        published_at=datetime.now(timezone.utc),
        source="Reuters",
        url="https://reuters.com/uber-doj",
        instrument_id=uuid.uuid4(),
        source_quality="RADAR_UNVERIFIED",
    )

    mock_reasoner = MagicMock()
    mock_reasoner.assess_event.side_effect = TimeoutError("Execution timed out after 45 seconds")

    with patch("app.services.briefing.GoogleNewsRSSProvider") as mock_news_cls, \
         patch("app.services.briefing.SECDisclosureProvider") as mock_sec_cls, \
         patch("app.services.briefing.BriefingReasoner", return_value=mock_reasoner):

        mock_news_inst = MagicMock()
        mock_news_inst.get_recent_news.return_value = [mock_news_item]
        mock_news_cls.return_value = mock_news_inst

        mock_sec_inst = MagicMock()
        mock_sec_inst.get_recent_disclosures.return_value = []
        mock_sec_cls.return_value = mock_sec_inst

        resp = await client.post("/api/briefing/generate", json={"force_refresh": True}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]

        assert data["status"] == "COMPLETED"
        assert len(data["items"]) == 1
        item = data["items"][0]
        # Preserves deterministic values
        assert item["materiality"] == "HIGH"
        assert item["review_required"] is True
        assert item["source_metadata"]["reasoning_source"] == "DETERMINISTIC_FALLBACK"
        assert "TimeoutError" in item["source_metadata"]["reasoning_fallback_reason"]


@pytest.mark.asyncio
async def test_codex_malformed_json_fallback(client: AsyncClient):
    """7. Malformed / invalid JSON -> fail-open: fallback persists with error details."""
    token, headers = await _register_user(client, f"br_badjson_{uuid.uuid4().hex[:6]}@example.com")
    await client.post(
        "/api/assets",
        json={
            "asset_type": "STOCK",
            "symbol": "UBER",
            "name": "Uber Technologies Inc",
            "current_price_currency": "USD",
            "initial_transaction": {
                "transaction_type": "BUY",
                "quantity": "10",
                "price_per_unit": "50.00",
                "transaction_currency": "USD",
                "transaction_date": "2024-06-01",
            },
        },
        headers=headers,
    )

    mock_news_item = NewsItemRecord(
        title="DOJ antitrust lawsuit filed against company",
        published_at=datetime.now(timezone.utc),
        source="Reuters",
        url="https://reuters.com/lawsuit",
        instrument_id=uuid.uuid4(),
        source_quality="RADAR_UNVERIFIED",
    )

    mock_reasoner = MagicMock()
    mock_reasoner.assess_event.side_effect = BriefingAssessmentError("Invalid schema: missing field 'impact'")

    with patch("app.services.briefing.GoogleNewsRSSProvider") as mock_news_cls, \
         patch("app.services.briefing.SECDisclosureProvider") as mock_sec_cls, \
         patch("app.services.briefing.BriefingReasoner", return_value=mock_reasoner):

        mock_news_inst = MagicMock()
        mock_news_inst.get_recent_news.return_value = [mock_news_item]
        mock_news_cls.return_value = mock_news_inst

        mock_sec_inst = MagicMock()
        mock_sec_inst.get_recent_disclosures.return_value = []
        mock_sec_cls.return_value = mock_sec_inst

        resp = await client.post("/api/briefing/generate", json={"force_refresh": True}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]

        assert data["status"] == "COMPLETED"
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["source_metadata"]["reasoning_source"] == "DETERMINISTIC_FALLBACK"
        assert "BriefingAssessmentError" in item["source_metadata"]["reasoning_fallback_reason"]


@pytest.mark.asyncio
async def test_briefing_does_not_mutate_intelligence_state(client: AsyncClient, db_session: AsyncSession):
    """8. Immutability: Briefing generation NEVER mutates InstrumentIntelligenceState or TechnicalPlan."""
    from sqlalchemy import select
    from app.models.instrument import Instrument
    from app.models.intelligence import (
        InstrumentIntelligenceState,
        Recommendation,
        TechnicalPlan,
        ThesisStatus,
    )

    token, headers = await _register_user(client, f"br_immut_{uuid.uuid4().hex[:6]}@example.com")
    await client.post(
        "/api/assets",
        json={
            "asset_type": "STOCK",
            "symbol": "UBER",
            "name": "Uber Technologies Inc",
            "current_price_currency": "USD",
            "initial_transaction": {
                "transaction_type": "BUY",
                "quantity": "10",
                "price_per_unit": "50.00",
                "transaction_currency": "USD",
                "transaction_date": "2024-06-01",
            },
        },
        headers=headers,
    )

    # Fetch instrument and set up initial state
    inst_stmt = select(Instrument).where(Instrument.symbol == "UBER")
    inst_res = await db_session.execute(inst_stmt)
    inst = inst_res.scalars().first()
    assert inst is not None

    initial_state = InstrumentIntelligenceState(
        instrument_id=inst.id,
        thesis_status=ThesisStatus.UNCHANGED,
        recommendation=Recommendation.HOLD,
        human_brief="Initial thesis intact.",
    )
    db_session.add(initial_state)
    await db_session.commit()
    await db_session.refresh(initial_state)

    state_id = initial_state.id
    saved_updated_at = initial_state.updated_at

    mock_news_item = NewsItemRecord(
        title="DOJ files antitrust lawsuit seeking structural changes",
        published_at=datetime.now(timezone.utc),
        source="Reuters",
        url="https://reuters.com/lawsuit-immut",
        instrument_id=uuid.uuid4(),
        source_quality="RADAR_UNVERIFIED",
    )

    mock_reasoner = MagicMock()
    mock_reasoner.assess_event.return_value = BriefingAssessment(
        event_summary="DOJ lawsuit",
        impact="NEGATIVE",
        materiality="CRITICAL",
        time_horizon="LONG",
        thesis_impact="WEAKER",
        review_required=True,
        why_it_matters="High risk development.",
        recommended_review="Thesis Review",
        confidence="HIGH",
    )

    with patch("app.services.briefing.GoogleNewsRSSProvider") as mock_news_cls, \
         patch("app.services.briefing.SECDisclosureProvider") as mock_sec_cls, \
         patch("app.services.briefing.BriefingReasoner", return_value=mock_reasoner):

        mock_news_inst = MagicMock()
        mock_news_inst.get_recent_news.return_value = [mock_news_item]
        mock_news_cls.return_value = mock_news_inst

        mock_sec_inst = MagicMock()
        mock_sec_inst.get_recent_disclosures.return_value = []
        mock_sec_cls.return_value = mock_sec_inst

        resp = await client.post("/api/briefing/generate", json={"force_refresh": True}, headers=headers)
        assert resp.status_code == 200

    # Verify InstrumentIntelligenceState was NOT touched
    chk_stmt = select(InstrumentIntelligenceState).where(InstrumentIntelligenceState.id == state_id)
    chk_res = await db_session.execute(chk_stmt)
    current_state = chk_res.scalars().first()
    assert current_state is not None
    assert current_state.thesis_status == ThesisStatus.UNCHANGED
    assert current_state.recommendation == Recommendation.HOLD
    assert current_state.human_brief == "Initial thesis intact."
    assert current_state.updated_at == saved_updated_at

    # Verify no TechnicalPlan was created
    tp_stmt = select(TechnicalPlan).where(TechnicalPlan.instrument_id == inst.id)
    tp_res = await db_session.execute(tp_stmt)
    assert len(tp_res.scalars().all()) == 0


@pytest.mark.asyncio
async def test_briefing_idempotency_reuses_cached_assessment(client: AsyncClient):
    """9. Idempotency: duplicate identical event reuses cached assessment within 48h."""
    token, headers = await _register_user(client, f"br_idemp_{uuid.uuid4().hex[:6]}@example.com")
    await client.post(
        "/api/assets",
        json={
            "asset_type": "STOCK",
            "symbol": "UBER",
            "name": "Uber Technologies Inc",
            "current_price_currency": "USD",
            "initial_transaction": {
                "transaction_type": "BUY",
                "quantity": "10",
                "price_per_unit": "50.00",
                "transaction_currency": "USD",
                "transaction_date": "2024-06-01",
            },
        },
        headers=headers,
    )

    mock_news_item = NewsItemRecord(
        title="DOJ antitrust investigation officially opened for ride share market",
        published_at=datetime.now(timezone.utc),
        source="Reuters",
        url="https://reuters.com/investigation-idemp",
        instrument_id=uuid.uuid4(),
        source_quality="RADAR_UNVERIFIED",
    )

    mock_reasoner = MagicMock()
    mock_reasoner.assess_event.return_value = BriefingAssessment(
        event_summary="DOJ antitrust investigation opened",
        impact="NEGATIVE",
        materiality="CRITICAL",
        time_horizon="LONG",
        thesis_impact="WEAKER",
        review_required=True,
        why_it_matters="Codex assessment: Structural headwinds to pricing power.",
        recommended_review="Thesis Review",
        confidence="HIGH",
    )

    with patch("app.services.briefing.GoogleNewsRSSProvider") as mock_news_cls, \
         patch("app.services.briefing.SECDisclosureProvider") as mock_sec_cls, \
         patch("app.services.briefing.BriefingReasoner", return_value=mock_reasoner):

        mock_news_inst = MagicMock()
        mock_news_inst.get_recent_news.return_value = [mock_news_item]
        mock_news_cls.return_value = mock_news_inst

        mock_sec_inst = MagicMock()
        mock_sec_inst.get_recent_disclosures.return_value = []
        mock_sec_cls.return_value = mock_sec_inst

        # Run 1: initial generation invokes Codex
        resp1 = await client.post("/api/briefing/generate", json={"force_refresh": True}, headers=headers)
        assert resp1.status_code == 200
        assert mock_reasoner.assess_event.call_count == 1
        item1 = resp1.json()["data"]["items"][0]
        assert item1["source_metadata"]["reasoning_source"] == "CODEX"

        # Run 2: same event within 48h must reuse cached assessment without calling Codex
        resp2 = await client.post("/api/briefing/generate", json={"force_refresh": True}, headers=headers)
        assert resp2.status_code == 200
        # Call count must still be 1!
        assert mock_reasoner.assess_event.call_count == 1
        item2 = resp2.json()["data"]["items"][0]
        assert item2["source_metadata"]["reasoning_source"] == "CODEX_CACHED"
        assert item2["why_it_matters"] == item1["why_it_matters"]
        assert item2["source_metadata"]["recommended_review"] == "Thesis Review"


@pytest.mark.asyncio
async def test_dashboard_retrieval_reads_persisted_without_codex(client: AsyncClient):
    """10. Dashboard retrieval (/api/briefing/latest and /stats) reads persisted data without invoking Codex."""
    token, headers = await _register_user(client, f"br_dash_{uuid.uuid4().hex[:6]}@example.com")
    await client.post(
        "/api/assets",
        json={
            "asset_type": "STOCK",
            "symbol": "UBER",
            "name": "Uber Technologies Inc",
            "current_price_currency": "USD",
            "initial_transaction": {
                "transaction_type": "BUY",
                "quantity": "10",
                "price_per_unit": "50.00",
                "transaction_currency": "USD",
                "transaction_date": "2024-06-01",
            },
        },
        headers=headers,
    )

    mock_news_item = NewsItemRecord(
        title="DOJ formal investigation launched into market competition",
        published_at=datetime.now(timezone.utc),
        source="Reuters",
        url="https://reuters.com/investigation-read",
        instrument_id=uuid.uuid4(),
        source_quality="RADAR_UNVERIFIED",
    )

    mock_reasoner = MagicMock()
    mock_reasoner.assess_event.return_value = BriefingAssessment(
        event_summary="DOJ formal investigation",
        impact="NEGATIVE",
        materiality="HIGH",
        time_horizon="MEDIUM",
        thesis_impact="WEAKER",
        review_required=True,
        why_it_matters="Regulatory inquiry into margin pricing.",
        recommended_review="Thesis Review",
        confidence="HIGH",
    )

    # 1. Generate and persist briefing
    with patch("app.services.briefing.GoogleNewsRSSProvider") as mock_news_cls, \
         patch("app.services.briefing.SECDisclosureProvider") as mock_sec_cls, \
         patch("app.services.briefing.BriefingReasoner", return_value=mock_reasoner):

        mock_news_inst = MagicMock()
        mock_news_inst.get_recent_news.return_value = [mock_news_item]
        mock_news_cls.return_value = mock_news_inst

        mock_sec_inst = MagicMock()
        mock_sec_inst.get_recent_disclosures.return_value = []
        mock_sec_cls.return_value = mock_sec_inst

        gen_resp = await client.post("/api/briefing/generate", json={"force_refresh": True}, headers=headers)
        assert gen_resp.status_code == 200

    # 2. Retrieval endpoints: Ensure BriefingReasoner is NOT even instantiated or called on read
    with patch("app.services.briefing.BriefingReasoner", side_effect=AssertionError("BriefingReasoner should never be called on GET!")):
        latest_resp = await client.get("/api/briefing/latest", headers=headers)
        assert latest_resp.status_code == 200
        latest_data = latest_resp.json()["data"]
        assert latest_data is not None
        assert len(latest_data["items"]) == 1
        assert latest_data["items"][0]["source_metadata"]["reasoning_source"] == "CODEX"
        assert latest_data["items"][0]["source_metadata"]["recommended_review"] == "Thesis Review"

        stats_resp = await client.get("/api/briefing/stats", headers=headers)
        assert stats_resp.status_code == 200
        stats_data = stats_resp.json()["data"]
        assert stats_data["attention_count"] == 1
        assert stats_data["items_shown"] == 1



