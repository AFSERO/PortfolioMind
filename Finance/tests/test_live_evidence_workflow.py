"""PostgreSQL workflow tests use deterministic transports and StaticAIProvider only."""
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select, func

from investment_intelligence.models import ProtocolRun
from investment_intelligence.repositories import InstrumentRepository, IntelligenceStateRepository
from investment_intelligence.providers import (
    StaticMarketDataProvider, StaticNewsProvider, StaticDisclosureProvider, StaticPortfolioProvider,
    MarketQuoteRecord, NewsItemRecord, DisclosureItemRecord, ProviderError,
)
from investment_intelligence.execution import StaticAIProvider
from investment_intelligence.workflows import ThesisReviewWorkflow
from investment_intelligence.live_providers import YahooFinanceMarketDataProvider, GoogleNewsRSSProvider, SECDisclosureProvider

pytestmark = pytest.mark.postgres
BASE = datetime(2026, 9, 14, tzinfo=timezone.utc)


def setup(session):
    with session.begin():
        inst = InstrumentRepository(session).create(symbol="UBER", name="Uber Technologies", instrument_type="equity", venue="NYSE", currency="USD")
        IntelligenceStateRepository(session).create_initial(inst.id)
        state = IntelligenceStateRepository(session).update(inst.id, last_review_at=BASE)
    return inst, state


@pytest.mark.parametrize("news_fail,sec_fail", [(False, False), (True, False), (False, True), (True, True)])
def test_successful_zero_vs_failure_and_state(session, news_fail, sec_fail):
    inst, before = setup(session)
    seen = []
    class News(StaticNewsProvider):
        def get_recent_news(self, iid, *, since=None, until=None, limit=10):
            assert not session.in_transaction()
            seen.append((since, until, limit))
            if news_fail: raise ProviderError("password=secret C:/private stack trace")
            return []
    class SEC(StaticDisclosureProvider):
        def get_recent_disclosures(self, iid, *, since=None, until=None, limit=10):
            assert not session.in_transaction()
            seen.append((since, until, limit))
            if sec_fail: raise ProviderError("password=secret C:/private stack trace")
            return []
    ai = StaticAIProvider()
    workflow = ThesisReviewWorkflow(session, ai, StaticMarketDataProvider(), News(), StaticPortfolioProvider(), disclosure_provider=SEC())
    run = workflow.run(inst.id)
    context = ai.recorded_requests[0].supplemental_context
    assert seen[0] == seen[1] and seen[0][0] == BASE
    assert context["evidence_window"]["evidence_window_start"] == BASE.isoformat()
    assert context["recent_news"] == context["recent_disclosures"] == []
    collection = context["evidence_collection"]
    assert collection["news"]["status"] == ("unavailable" if news_fail else "available")
    assert collection["disclosures"]["status"] == ("unavailable" if sec_fail else "available")
    assert collection["market"]["status"] == "unavailable"
    assert collection["news"]["item_count"] == collection["disclosures"]["item_count"] == 0
    assert "secret" not in json.dumps(context) and "C:/private" not in json.dumps(context)
    with session.begin():
        assert IntelligenceStateRepository(session).get(inst.id) == before
        assert session.scalar(select(func.count()).select_from(ProtocolRun).where(ProtocolRun.instrument_id == inst.id)) == 1
    assert run.run.status.value == "COMPLETED"


def test_live_adapters_to_ai_no_db_transaction(session):
    inst, before = setup(session)
    class Transport:
        def get(self, url, *, headers=None):
            assert not session.in_transaction()
            if "yahoo" in url:
                return json.dumps({"chart": {"result": [{"meta": {"symbol": "UBER", "currency": "USD", "instrumentType": "EQUITY", "regularMarketPrice": 72, "regularMarketTime": int(BASE.timestamp())}}]}}).encode()
            if "google" in url:
                return b"<rss><channel><item><title>Radar</title><link>https://news.google.com/rss/articles/x</link><pubDate>Mon, 14 Sep 2026 12:00:00 GMT</pubDate><source>Reuters</source></item></channel></rss>"
            if "company_tickers" in url:
                return json.dumps({"0": {"ticker": "UBER", "cik_str": 1543151}}).encode()
            return json.dumps({"cik": 1543151, "filings": {"recent": {"form": ["8-K"], "accessionNumber": ["0001543151-26-000041"], "filingDate": ["2026-09-14"], "acceptanceDateTime": ["2026-09-14T12:00:00Z"], "primaryDocument": ["uber.htm"]}, "files": []}}).encode()
    transport = Transport()
    ai = StaticAIProvider()
    workflow = ThesisReviewWorkflow(session, ai,
        YahooFinanceMarketDataProvider([inst], transport=transport),
        GoogleNewsRSSProvider([inst], transport=transport), StaticPortfolioProvider(),
        disclosure_provider=SECDisclosureProvider([inst], transport=transport, user_agent="Test/0.1 test@invalid.test"))
    workflow.run(inst.id)
    supp = ai.recorded_requests[0].supplemental_context
    assert all(v["status"] == "available" for v in supp["evidence_collection"].values())
    assert supp["recent_disclosures"][0]["disclosure_type"] == "8-K"
    assert supp["recent_disclosures"][0]["source_quality"] == "PRIMARY"
    assert supp["recent_news"][0]["source_quality"] == "RADAR_UNVERIFIED"
    assert supp["market"]["current_quote"]["price"] == 72
    with session.begin():
        assert IntelligenceStateRepository(session).get(inst.id) == before


def test_window_isolation_bounds_and_body_omission(session):
    inst, _ = setup(session)
    other = uuid4()
    class Unfiltered(StaticDisclosureProvider):
        def get_recent_disclosures(self, *args, **kwargs):
            return self.items
    good = DisclosureItemRecord(inst.id, "8-K", "Current", BASE, "SEC", "https://www.sec.gov/example", metadata={"body": "FULL SECRET FILING", "content_scope": "metadata_only"}, summary="FULL BODY")
    bad = DisclosureItemRecord(other, "8-K", "OTHER", BASE, "SEC", "https://www.sec.gov/example")
    old = DisclosureItemRecord(inst.id, "8-K", "OLD", BASE-timedelta(seconds=1), "SEC", "https://www.sec.gov/example")
    future = DisclosureItemRecord(inst.id, "8-K", "FUTURE", datetime.now(timezone.utc)+timedelta(days=1), "SEC", "https://www.sec.gov/example")
    ai = StaticAIProvider()
    w = ThesisReviewWorkflow(session, ai, StaticMarketDataProvider(), StaticNewsProvider(), StaticPortfolioProvider(), disclosure_provider=Unfiltered([bad, old, future]+[good]*20))
    w.run(inst.id, disclosure_limit=3)
    supp = ai.recorded_requests[0].supplemental_context
    assert len(supp["recent_disclosures"]) == 3
    assert all(item["title"] == "Current" for item in supp["recent_disclosures"])
    assert "FULL" not in json.dumps(supp)


def test_active_transaction_rejected_and_zero_skipped(session):
    inst, _ = setup(session)
    class Never(StaticDisclosureProvider):
        def get_recent_disclosures(self, *args, **kwargs):
            raise AssertionError("Should not fetch")
    w = ThesisReviewWorkflow(session, StaticAIProvider(), StaticMarketDataProvider(), StaticNewsProvider(), StaticPortfolioProvider(), disclosure_provider=Never())
    with session.begin(), pytest.raises(ValueError, match="active transaction"):
        w.build_supplemental_context(inst.id)
    supp = w.build_supplemental_context(inst.id, news_limit=0, disclosure_limit=0)
    assert supp["evidence_collection"]["news"]["status"] == "skipped"
    assert supp["evidence_collection"]["disclosures"]["status"] == "skipped"
    with pytest.raises(ValueError):
        w.build_supplemental_context(inst.id, disclosure_limit=11)
