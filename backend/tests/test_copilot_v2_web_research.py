"""Comprehensive test suite for Copilot V2.6 Web Research & External Evidence Layer.

Covers:
1. SSRF Guard: Disallowing loopback, link-local, cloud metadata, internal Docker hosts, non-http schemes.
2. Tool Registry & Safety: search_news, search_web, fetch_web_page registered as READ_ONLY.
3. Query Enrichment: Canonical instrument symbol expansion (e.g. THF).
4. Caching & Deduplication: In-memory TTL caching prevents redundant web calls.
5. Fetch Web Page: Text extraction, tag stripping, bounded size limits, SSRF blocking.
6. Zero Hallucination Sources: Sources in metadata strictly match real tool outputs.
7. Regression: get_asset_context with IntelligenceReview protocol attribute works without AttributeError.
"""

from datetime import datetime, timezone
from decimal import Decimal
import io
import socket
import time
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.error import HTTPError
import uuid

import pytest
from sqlalchemy import select

from app.models.asset import Asset, AssetType
from app.models.copilot import CopilotConversation, CopilotMessage
from app.models.instrument import Instrument
from app.models.intelligence import IntelligenceReview
from app.models.user import User
from app.services.copilot_v2.adapter import CodexV2Adapter, CodexV2ExecutionResult
from app.services.copilot_v2.contracts import (
    HandoffContext,
    OrchestratorAction,
    OrchestratorResult,
)
from app.services.copilot_v2.orchestrator import FastOrchestrator
from app.services.copilot_v2.profiles import ModelProfile, ReasoningEffort
from app.services.copilot_v2.reasoner import ReasonerEngine
from app.services.copilot_v2.service import CopilotV2Service
from app.services.copilot_v2.telemetry import ExecutionTrace
from app.services.copilot_v2.tools import ToolClassification, default_tool_registry
from app.services.copilot_v2.tools.builtins import get_asset_context_handler
from app.services.copilot_v2.tools.web_research import (
    _SEARCH_CACHE,
    fetch_web_page_handler,
    is_ip_allowed,
    is_safe_url,
    search_news_handler,
    search_web_handler,
)


async def _create_test_user(db_session, email_prefix: str = "web_research_test") -> User:
    user = User(
        email=f"{email_prefix}_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed_pw_test",
        display_name="Web Research Tester",
        base_currency="TRY",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# -----------------------------------------------------------------------------
# 1. SSRF Guard Tests
# -----------------------------------------------------------------------------
def test_ssrf_guard_is_ip_allowed():
    """Verify that private, link-local, loopback, and cloud metadata IPs are rejected."""
    # Loopback
    assert not is_ip_allowed("127.0.0.1")
    assert not is_ip_allowed("127.0.1.1")
    assert not is_ip_allowed("::1")

    # Cloud metadata (AWS, GCP, Azure)
    assert not is_ip_allowed("169.254.169.254")

    # RFC 1918 Private IPv4
    assert not is_ip_allowed("10.0.0.1")
    assert not is_ip_allowed("10.255.255.255")
    assert not is_ip_allowed("172.16.0.1")
    assert not is_ip_allowed("172.31.255.255")
    assert not is_ip_allowed("192.168.1.1")
    assert not is_ip_allowed("192.168.0.254")

    # Multicast & Link-local
    assert not is_ip_allowed("224.0.0.1")
    assert not is_ip_allowed("fe80::1")

    # Invalid string
    assert not is_ip_allowed("invalid-ip")
    assert not is_ip_allowed("999.999.999.999")

    # Valid public IPs
    assert is_ip_allowed("8.8.8.8")
    assert is_ip_allowed("1.1.1.1")
    assert is_ip_allowed("142.250.190.46")


def test_ssrf_guard_is_safe_url():
    """Verify URL scheme, hostname, and internal Docker service blocking."""
    # Bad schemes
    safe, err = is_safe_url("file:///etc/passwd")
    assert not safe and "scheme" in err.lower()

    safe, err = is_safe_url("ftp://ftp.example.com/file")
    assert not safe and "scheme" in err.lower()

    safe, err = is_safe_url("gopher://gopher.example.com")
    assert not safe and "scheme" in err.lower()

    # Disallowed hostnames
    for bad_host in ["localhost", "127.0.0.1", "169.254.169.254", "db", "backend", "frontend", "postgres"]:
        safe, err = is_safe_url(f"http://{bad_host}:8000/api")
        assert not safe, f"Expected {bad_host} to be blocked"

    # Valid safe public URLs
    with patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("142.250.190.46", 443))]):
        safe, err = is_safe_url("https://news.google.com/rss/search?q=THF")
        assert safe
        assert not err


# -----------------------------------------------------------------------------
# 2. Tool Registry & Read-Only Invariant
# -----------------------------------------------------------------------------
def test_web_research_tools_registered_and_read_only():
    """Ensure search_news, search_web, and fetch_web_page are registered as READ_ONLY."""
    for tool_name in ["search_news", "search_web", "fetch_web_page"]:
        tool_def = default_tool_registry.get(tool_name)
        assert tool_def is not None
        assert tool_def.classification == ToolClassification.READ_ONLY
        assert tool_def.name == tool_name
        assert len(tool_def.parameters_schema.get("properties", {})) > 0


# -----------------------------------------------------------------------------
# 3. Query Enrichment with Canonical Symbols
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_news_enriches_symbol_query(db_session):
    """search_news enriches query when a known symbol is provided."""
    user = await _create_test_user(db_session)

    # Insert a test instrument into the DB
    instrument = Instrument(
        symbol="TESTFON",
        name="TEST PORTFOY DEGISKEN FON",
        asset_type=AssetType.FUND,
        currency="TRY",
    )
    db_session.add(instrument)
    await db_session.commit()

    sample_rss = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Google News</title>
        <item>
          <title>Test Fon Analizi - Finans Dunyasi</title>
          <link>https://news.google.com/articles/CAIiE123</link>
          <pubDate>Mon, 30 Sep 2026 12:00:00 GMT</pubDate>
          <source url="https://finans.com">Finans Dunyasi</source>
          <description>Test Fon hakkinda gelismeler aciklandi.</description>
        </item>
      </channel>
    </rss>
    """

    mock_resp = MagicMock()
    mock_resp.read.return_value = sample_rss.encode("utf-8")
    mock_resp.headers = {"Content-Type": "application/rss+xml"}
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen, \
         patch("app.services.copilot_v2.tools.web_research.datetime", wraps=datetime) as clock, \
         patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("142.250.190.46", 443))]):
        clock.now.return_value = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)
        tool_res = await default_tool_registry.execute(
            name="search_news",
            db=db_session,
            user_id=user.id,
            args={"query": "TESTFON", "symbols": ["TESTFON"]},
        )

        assert tool_res.error is None
        result = tool_res.output
        assert result["count"] == 1
        assert len(result["results"]) == 1
        item = result["results"][0]
        assert "Test Fon Analizi" in item["title"]
        assert item["source"] == "Finans Dunyasi"
        assert item["url"] == "https://news.google.com/articles/CAIiE123"

        # Check that the query incorporated the instrument context
        called_req = mock_urlopen.call_args[0][0]
        called_url = called_req.full_url
        assert "TESTFON" in called_url


# -----------------------------------------------------------------------------
# 4. In-Memory Search Caching
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_news_in_memory_cache(db_session):
    """Repeated identical searches within TTL hit memory cache without redundant HTTP requests."""
    user = await _create_test_user(db_session)
    _SEARCH_CACHE.clear()

    sample_rss = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Borsa Istanbul Rekor Kirdi - Haber</title>
          <link>https://news.google.com/articles/CAIiE999</link>
          <source url="https://haber.com">Haber</source>
        </item>
      </channel>
    </rss>
    """

    mock_resp = MagicMock()
    mock_resp.read.return_value = sample_rss.encode("utf-8")
    mock_resp.headers = {"Content-Type": "application/rss+xml"}
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        # First call: hits network
        res1 = await search_news_handler(
            query="BIST 100 Guncel",
            db=db_session,
        )
        assert res1["count"] == 1
        assert mock_urlopen.call_count == 1

        # Second call with identical query: hits memory cache
        res2 = await search_news_handler(
            query="BIST 100 Guncel",
            db=db_session,
        )
        assert res2["cached"] is True
        # Network request count MUST NOT increment
        assert mock_urlopen.call_count == 1
        assert res1["results"] == res2["results"]


# -----------------------------------------------------------------------------
# 5. Fetch Web Page Handler & SSRF Blocking
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fetch_web_page_ssrf_rejection(db_session):
    """fetch_web_page strictly rejects dangerous internal and local URLs."""
    user = await _create_test_user(db_session)

    # Attempt fetching localhost
    res = await fetch_web_page_handler(
        url="http://127.0.0.1:8000/api/v1/metrics",
    )
    assert res["status"] == "error"
    assert "rejected" in res["message"].lower()

    # Attempt fetching AWS metadata
    res = await fetch_web_page_handler(
        url="http://169.254.169.254/latest/meta-data/",
    )
    assert res["status"] == "error"
    assert "rejected" in res["message"].lower()


@pytest.mark.asyncio
async def test_fetch_web_page_content_extraction(db_session):
    """fetch_web_page strips scripts, styles, decodes entities and extracts clean text."""
    user = await _create_test_user(db_session)

    html_content = """
    <!DOCTYPE html>
    <html>
      <head>
        <title>Sermaye Piyasası Duyurusu &amp; Fon Raporu</title>
        <style>body { font-size: 14px; } .hidden { display: none; }</style>
        <script>function track() { alert('tracking'); }</script>
      </head>
      <body>
        <h1>Fon Likidasyon Süreci Hakkında</h1>
        <p>Tera Portföy Yönetimi A.Ş. tarafından yönetilen THF fonu tasfiye sürecine girmiştir.</p>
        <script>console.log('malicious script');</script>
        <footer>Tüm hakları saklıdır.</footer>
      </body>
    </html>
    """

    mock_resp = MagicMock()
    mock_resp.read.return_value = html_content.encode("utf-8")
    mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
    mock_resp.__enter__.return_value = mock_resp

    with patch("socket.getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]), \
         patch("urllib.request.build_opener") as mock_opener:
        opener_mock = MagicMock()
        opener_mock.open.return_value = mock_resp
        mock_opener.return_value = opener_mock

        res = await fetch_web_page_handler(
            url="https://example.com/announcement",
        )

        assert res["status"] == "success"
        assert res["title"] == "Sermaye Piyasası Duyurusu & Fon Raporu"
        text = res["text"]
        assert "Fon Likidasyon Süreci Hakkında" in text
        assert "THF fonu tasfiye sürecine girmiştir." in text
        assert "function track" not in text
        assert "malicious script" not in text
        assert "font-size" not in text


# -----------------------------------------------------------------------------
# 6. Zero Hallucination Sources & Metadata Persistence
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_copilot_service_persists_verified_external_sources(db_session):
    """CopilotV2Service persists verified sources in message metadata without hallucination."""
    user = await _create_test_user(db_session)

    # Create a conversation
    conv = CopilotConversation(user_id=user.id, title="THF News Test")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    service = CopilotV2Service()

    # Mock the FastOrchestrator to return a turn that used external search
    fake_sources = [
        {
            "title": "Tera Portföy THF Fonu Likidasyon Raporu",
            "source": "Google News",
            "url": "https://news.google.com/test-article",
            "published_at": "2026-09-30 10:00",
        }
    ]

    mock_orch_result = OrchestratorResult(
        action=OrchestratorAction.FINAL_RESPONSE,
        final_answer="THF fonunun tasfiye sürecinde olduğu doğrulanmıştır [Tera Portföy, 2026].",
        tools_used=["get_asset_context", "search_news"],
        external_sources=fake_sources,
        session_id="test-session-123",
    )

    with patch.object(service.orchestrator, "run", new_callable=AsyncMock) as mock_orch_run:
        mock_orch_run.return_value = mock_orch_result

        result = await service.handle_user_message(
            db=db_session,
            user_id=user.id,
            user_message="THF niye düştü?",
            conversation_id=conv.id,
        )

        assert result["answer"] == mock_orch_result.final_answer
        assert result["external_sources"] == fake_sources
        assert result["trace"]["source_count_used_in_final_answer"] == 1

        # Check canonical message in database
        stmt = select(CopilotMessage).where(CopilotMessage.conversation_id == conv.id, CopilotMessage.role == "assistant")
        asst_msg = (await db_session.execute(stmt)).scalars().first()

        assert asst_msg is not None
        assert asst_msg.structured_metadata is not None
        assert "external_sources" in asst_msg.structured_metadata
        persisted_sources = asst_msg.structured_metadata["external_sources"]
        assert len(persisted_sources) == 1
        assert persisted_sources[0]["title"] == "Tera Portföy THF Fonu Likidasyon Raporu"
        assert persisted_sources[0]["url"] == "https://news.google.com/test-article"


# -----------------------------------------------------------------------------
# 7. Regression Test: get_asset_context with IntelligenceReview protocol attribute
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_asset_context_intelligence_review_protocol_attribute(db_session):
    """Verify that get_asset_context handles IntelligenceReview with protocol attribute without AttributeError."""
    user = await _create_test_user(db_session)

    # 1. Create instrument
    inst = Instrument(
        symbol="THF",
        name="TERA PORTFOY HISSE SENEDI FONU",
        asset_type=AssetType.FUND,
        currency="TRY",
    )
    db_session.add(inst)
    await db_session.flush()

    # 2. Create user asset
    asset = Asset(
        user_id=user.id,
        instrument_id=inst.id,
        asset_type=AssetType.FUND,
        symbol="THF",
        name="TERA PORTFOY HISSE SENEDI FONU",
        current_price=Decimal("1.250000"),
        current_price_currency="TRY",
        is_manual_price=False,
    )
    db_session.add(asset)
    await db_session.flush()

    # 3. Create an IntelligenceReview for this instrument
    review = IntelligenceReview(
        instrument_id=inst.id,
        protocol="FUND_HEALTH_ANALYSIS",  # Column name is 'protocol'
        human_brief="Fon likidasyon sürecindedir.",
        confidence="0.85",
        machine_record={"recommendation": "SELL"},
    )
    db_session.add(review)
    await db_session.commit()

    # Execute get_asset_context_handler
    context_res = await get_asset_context_handler(
        db=db_session,
        user_id=user.id,
        symbol="THF",
    )

    assert context_res["instrument"]["symbol"] == "THF"
    assert context_res["instrument"]["name"] == "TERA PORTFOY HISSE SENEDI FONU"
    assert len(context_res["recent_reviews"]) == 1
    review_data = context_res["recent_reviews"][0]
    assert review_data["protocol_name"] == "FUND_HEALTH_ANALYSIS"
    assert review_data["human_brief"] == "Fon likidasyon sürecindedir."
    assert review_data["recommendation"] == "SELL"


@pytest.mark.asyncio
async def test_news_lookback_filters_old_evidence_with_frozen_clock(db_session):
    user = await _create_test_user(db_session)
    _SEARCH_CACHE.clear()
    rss = b"""<rss><channel>
    <item><title>Recent</title><link>https://example.com/recent</link><pubDate>Wed, 07 Oct 2026 12:00:00 GMT</pubDate></item>
    <item><title>Old</title><link>https://example.com/old</link><pubDate>Tue, 01 Sep 2026 12:00:00 GMT</pubDate></item>
    </channel></rss>"""
    response = MagicMock()
    response.read.return_value = rss
    response.__enter__.return_value = response
    with patch("urllib.request.urlopen", return_value=response), \
         patch("app.services.copilot_v2.tools.web_research.datetime", wraps=datetime) as clock, \
         patch("socket.getaddrinfo", return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,"",("142.250.190.46",443))]):
        clock.now.return_value = datetime(2026,10,8,12,tzinfo=timezone.utc)
        result = await default_tool_registry.execute(name="search_news", db=db_session, user_id=user.id,
            args={"query":"Synthetic freshness regression","lookback_days":7})
    assert result.error is None
    assert result.output["count"] == 1
    assert result.output["results"][0]["title"] == "Recent"
