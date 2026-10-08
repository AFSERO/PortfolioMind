"""Deterministic public-provider tests; no public network requests."""
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest

from investment_intelligence.records import InstrumentRecord
from investment_intelligence.providers import DataUnavailableError, ProviderError, ProviderConfigurationError
from investment_intelligence.live_providers import YahooFinanceMarketDataProvider, GoogleNewsRSSProvider, SECDisclosureProvider
from investment_intelligence.evidence_http import BoundedHTTPClient, allowed_url

NOW = datetime(2026, 9, 15, 12, tzinfo=timezone.utc)
START = NOW-timedelta(days=1)
UA = "TestSuite/0.1 test@invalid.test"


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    import socket
    def denied(*args, **kwargs):
        raise AssertionError("Public internet forbidden in tests")
    monkeypatch.setattr(socket, "create_connection", denied)


@pytest.fixture
def inst():
    return InstrumentRecord(uuid4(), "UBER", "Uber Technologies", "equity", "NYSE", "USD", START, START)


class Transport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
    def get(self, url, *, headers=None):
        self.calls.append((url, headers))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return json.dumps(response).encode() if isinstance(response, dict) else response


def quote():
    return {"chart": {"error": None, "result": [{"meta": {
        "symbol": "UBER", "instrumentType": "EQUITY", "currency": "USD",
        "regularMarketPrice": 72.5, "regularMarketTime": int(START.timestamp())}}]}}


def test_market_quote(inst):
    t = Transport(quote())
    p = YahooFinanceMarketDataProvider([inst], transport=t)
    r = p.get_quote(inst.id)
    assert r.price == Decimal("72.5") and r.currency == "USD" and r.as_of == START
    assert r.instrument_id == inst.id and "not guaranteed real-time" in r.source
    assert t.calls[0][0].startswith("https://query1.finance.yahoo.com/v8/finance/chart/UBER?")
    with pytest.raises(DataUnavailableError, match="history_not_implemented"):
        p.get_price_history(inst)


@pytest.mark.parametrize("response", [b"not json", {}, {"chart": {"result": []}}, TimeoutError("secret"), ProviderError("secret")])
def test_market_failures(inst, response):
    with pytest.raises(ProviderError):
        YahooFinanceMarketDataProvider([inst], transport=Transport(response)).get_quote(inst.id)


@pytest.mark.parametrize("key,value", [("currency", "EUR"), ("symbol", "OTHER"), ("regularMarketPrice", "NaN"), ("regularMarketPrice", -1), ("regularMarketTime", None)])
def test_market_invalid_fields(inst, key, value):
    data = quote(); data["chart"]["result"][0]["meta"][key] = value
    with pytest.raises(ProviderError):
        YahooFinanceMarketDataProvider(transport=Transport(data)).get_quote(inst)


def rss_item(date, n=1):
    return f"<item><title>News {n}</title><link>https://news.google.com/rss/articles/{n}</link><pubDate>{date}</pubDate><source>Reuters</source><description>Untrusted HTML</description></item>"


def rss(*items):
    return ("<rss><channel>"+"".join(items)+"</channel></rss>").encode()


def test_rss_window_limit_timezone_query_quality(inst):
    data = rss(rss_item("Mon, 14 Sep 2026 11:00:00 GMT", 1),
               rss_item("Tue, 15 Sep 2026 13:00:00 +0300", 2),
               rss_item("Tue, 15 Sep 2026 11:00:00 GMT", 3),
               rss_item("Tue, 15 Sep 2026 13:00:00 GMT", 4))
    t = Transport(data)
    r = GoogleNewsRSSProvider([inst], transport=t).get_recent_news(inst.id, since=START, until=NOW, limit=1)
    assert len(r) == 1 and r[0].title == "News 3" and r[0].source == "Reuters"
    assert r[0].source_quality == "RADAR_UNVERIFIED" and r[0].summary is None
    query = parse_qs(urlsplit(t.calls[0][0]).query)["q"][0]
    assert "UBER" in query and "Uber Technologies" in query and "after:2026-09-13" in query
    r = GoogleNewsRSSProvider(transport=Transport(data)).get_recent_news(inst, since=START, until=NOW)
    assert r[1].published_at == datetime(2026, 9, 15, 10, tzinfo=timezone.utc)
    assert r[1].instrument_id == inst.id


@pytest.mark.parametrize("data", [b"bad xml", b"<html/>", b"<rss/>", rss("<item/>"), b'<!DOCTYPE rss [<!ENTITY a "b">]><rss><channel/></rss>'])
def test_rss_malformed(inst, data):
    with pytest.raises(ProviderError, match="malformed_response"):
        GoogleNewsRSSProvider(transport=Transport(data)).get_recent_news(inst, since=START, until=NOW)


def test_rss_empty_and_zero(inst):
    t = Transport(rss())
    p = GoogleNewsRSSProvider(transport=t)
    assert p.get_recent_news(inst, since=START, until=NOW) == []
    assert p.get_recent_news(inst, limit=0) == [] and len(t.calls) == 1


def mapping():
    return {"0": {"cik_str": 1543151, "ticker": "UBER", "title": "Uber"}}


def submissions():
    return {"cik": "1543151", "filings": {"files": [], "recent": {
        "form": ["8-K", "4", "10-Q"],
        "filingDate": ["2026-09-15", "2026-09-14", "2026-09-13"],
        "acceptanceDateTime": ["2026-09-15T10:00:00Z", "2026-09-14T12:00:00Z", "2026-09-13T10:00:00Z"],
        "accessionNumber": ["0001543151-26-000040", "0001543151-26-000039", "0001543151-26-000038"],
        "primaryDocument": ["uber-8k.htm", "form4.xml", "uber-10q.htm"]}}}


def test_sec_metadata_window_cache_and_urls(inst):
    t = Transport(mapping(), submissions(), submissions())
    p = SECDisclosureProvider([inst], user_agent=UA, transport=t)
    assert p.resolve_cik(inst.id) == "0001543151"
    results = p.get_recent_disclosures(inst.id, since=START, until=NOW)
    assert len(results) == 2 and results[0].disclosure_type == "8-K"
    assert results[0].published_at == datetime(2026, 9, 15, 10, tzinfo=timezone.utc)
    assert results[1].published_at == START
    assert results[0].url == "https://www.sec.gov/Archives/edgar/data/1543151/000154315126000040/uber-8k.htm"
    assert results[0].source_quality == "PRIMARY" and results[0].summary is None
    assert results[0].metadata["timestamp_basis"] == "acceptanceDateTime"
    assert len(p.get_recent_disclosures(inst, since=START, until=NOW, limit=1)) == 1
    assert len(t.calls) == 3
    assert all(call[1]["User-Agent"] == UA for call in t.calls)
    assert all("Archives" not in call[0] for call in t.calls)


def test_sec_cache_expiry(inst, monkeypatch):
    import investment_intelligence.live_providers as live
    clock = [100.0]
    monkeypatch.setattr(live.time, "monotonic", lambda: clock[0])
    t = Transport(mapping(), mapping())
    p = SECDisclosureProvider(transport=t, user_agent=UA, cache_ttl=10)
    p.resolve_cik(inst); p.resolve_cik(inst)
    clock[0] += 11
    p.resolve_cik(inst)
    assert len(t.calls) == 2


def test_sec_official_document_subdirectory(inst):
    data = submissions()
    data["filings"]["recent"]["primaryDocument"][1] = "xslF345X05/ownership.xml"
    provider = SECDisclosureProvider(transport=Transport(mapping(), data), user_agent=UA)
    results = provider.get_recent_disclosures(inst, since=START, until=NOW)
    assert results[1].url.endswith("/xslF345X05/ownership.xml")


def test_sec_submission_timeout_is_not_empty_result(inst):
    provider = SECDisclosureProvider(transport=Transport(mapping(), TimeoutError("secret")), user_agent=UA)
    with pytest.raises(ProviderError, match="transport_error"):
        provider.get_recent_disclosures(inst, since=START, until=NOW)


def test_rss_timeout_is_not_empty_result(inst):
    with pytest.raises(ProviderError, match="transport_error"):
        GoogleNewsRSSProvider(transport=Transport(TimeoutError("secret"))).get_recent_news(inst)


@pytest.mark.parametrize("ua", ["", "bot", "bot contact@example.com", "bad\r\nContact: test@invalid.test"])
def test_sec_missing_or_invalid_user_agent(ua, monkeypatch):
    monkeypatch.delenv("II_SEC_USER_AGENT", raising=False)
    with pytest.raises(ProviderConfigurationError):
        SECDisclosureProvider(user_agent=ua)
    with pytest.raises(ProviderConfigurationError):
        SECDisclosureProvider()


def test_sec_env_and_unsupported(inst, monkeypatch):
    monkeypatch.setenv("II_SEC_USER_AGENT", UA)
    p = SECDisclosureProvider(transport=Transport(mapping()))
    with pytest.raises(DataUnavailableError, match="sec_ticker_not_found"):
        p.resolve_cik(replace(inst, symbol="OTHER"))
    for item in (replace(inst, venue="BIST"), replace(inst, instrument_type="crypto"), replace(inst, symbol="../../localhost")):
        with pytest.raises(DataUnavailableError):
            p.resolve_cik(item)


@pytest.mark.parametrize("response", [TimeoutError("secret"), ProviderError("http_error"), b"bad", {}])
def test_sec_failed_mapping(inst, response):
    with pytest.raises(ProviderError):
        SECDisclosureProvider(transport=Transport(response), user_agent=UA).get_recent_disclosures(inst)


@pytest.mark.parametrize("field,value", [("acceptanceDateTime", ["2026-09-15T10:00:00"]*3),
                                        ("form", ["8-K"]), ("primaryDocument", ["../../secret"]*3)])
def test_sec_invalid_metadata(inst, field, value):
    data = submissions(); data["filings"]["recent"][field] = value
    with pytest.raises(ProviderError):
        SECDisclosureProvider(transport=Transport(mapping(), data), user_agent=UA).get_recent_disclosures(inst, since=START, until=NOW)


def test_sec_empty_and_insufficient_history(inst):
    data = submissions()
    p = SECDisclosureProvider(transport=Transport(mapping(), data), user_agent=UA)
    assert p.get_recent_disclosures(inst, since=NOW, until=NOW+timedelta(hours=1)) == []
    data["filings"]["files"] = [{"name": "old.json"}]
    with pytest.raises(DataUnavailableError, match="window_exceeds"):
        SECDisclosureProvider(transport=Transport(mapping(), data), user_agent=UA).get_recent_disclosures(inst, since=START-timedelta(days=90), until=NOW)


@pytest.mark.parametrize("url", ["http://news.google.com/rss/search", "https://localhost/rss/search", "https://news.google.com.evil/rss/search", "https://news.google.com:443/rss/search", "https://x@news.google.com/rss/search", "https://www.sec.gov/Archives/evil", "https://data.sec.gov/submissions/../../x"])
def test_http_rejects_arbitrary_urls(url):
    assert not allowed_url(url)
    with pytest.raises(ProviderError):
        BoundedHTTPClient().get(url)


def test_http_bounds_redirect_and_timeout(monkeypatch):
    import investment_intelligence.evidence_http as http
    settings = {"status": 200, "body": b"{}", "headers": {}, "timeout": False}
    calls = []
    class Socket:
        def settimeout(self, value):
            calls.append(("timeout", value))
    class Response:
        def __init__(self):
            self.status = settings["status"]; self.body = settings["body"]
        def getheader(self, name, default=None):
            return settings["headers"].get(name, default)
        def read1(self, amount):
            if settings["timeout"]:
                raise TimeoutError("secret-local-path")
            result, self.body = self.body[:amount], self.body[amount:]
            return result
    class Connection:
        def __init__(self, host, timeout, context):
            self.sock = Socket(); calls.append((host, timeout))
        def connect(self): pass
        def request(self, method, path, headers): calls.append((method, path, headers))
        def getresponse(self): return Response()
        def close(self): calls.append("closed")
    monkeypatch.setattr(http.http.client, "HTTPSConnection", Connection)
    p = BoundedHTTPClient(max_bytes=10)
    url = "https://news.google.com/rss/search?q=UBER"
    assert p.get(url) == b"{}" and any(c[0] == "GET" for c in calls if isinstance(c, tuple))
    for changes, error in [({"status": 302}, "http_error"), ({"status": 429}, "http_error"),
                           ({"status": 200, "body": b"x"*11}, "response_too_large"),
                           ({"body": b"{}", "headers": {"Content-Encoding": "gzip"}}, "unsupported_encoding"),
                           ({"headers": {}, "timeout": True}, "timeout")]:
        settings.update(changes)
        with pytest.raises(ProviderError, match=error):
            p.get(url)
        assert calls[-1] == "closed"


def test_sec_throttle_shared(monkeypatch):
    import investment_intelligence.evidence_http as http
    clock = [10.0]; waits = []
    monkeypatch.setattr(http, "_SEC_LAST_REQUEST", 0.0)
    monkeypatch.setattr(http.time, "monotonic", lambda: clock[0])
    def sleep(delay): waits.append(delay); clock[0] += delay
    monkeypatch.setattr(http.time, "sleep", sleep)
    http.throttle_sec(); http.throttle_sec(); http.throttle_sec()
    assert waits == [0.5, 0.5]
