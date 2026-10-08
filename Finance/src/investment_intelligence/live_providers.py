"""Zero-key, bounded public evidence adapters. Identity records are detached from DB."""

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from functools import wraps
from urllib.parse import urlencode, urlsplit
from xml.etree import ElementTree

from investment_intelligence.evidence_http import BoundedHTTPClient
from investment_intelligence.providers import (
    MarketDataProvider, NewsProvider, DisclosureProvider, MarketQuoteRecord,
    NewsItemRecord, DisclosureItemRecord, ProviderError, DataUnavailableError,
    ProviderConfigurationError, _as_uuid, _require_utc,
)
from investment_intelligence.records import InstrumentRecord

US_VENUES = {"NYSE", "NASDAQ", "AMEX", "NYSEAMERICAN", "NYSE AMERICAN", "NYSE ARCA",
             "XNYS", "XNAS", "XASE", "ARCX", "BATS", "IEX"}


def parsed(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except ProviderError:
            raise
        except (ValueError, TypeError, KeyError, IndexError, AttributeError,
                OverflowError, InvalidOperation, ElementTree.ParseError, RecursionError):
            raise ProviderError("malformed_response") from None
        except (TimeoutError, OSError):
            raise ProviderError("transport_error") from None
    return wrapped


def window(since, until, limit):
    if type(limit) is not int or not 0 <= limit <= 10:
        raise ValueError("limit must be 0..10")
    end = _require_utc(until, "until") if until is not None else datetime.now(timezone.utc)
    start = _require_utc(since, "since") if since is not None else end - timedelta(days=30)
    if start > end:
        raise ValueError("since must not exceed until")
    return start, end


def text(value, maximum=300):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Missing text")
    return value.strip()[:maximum]


def json_data(raw):
    return json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))


class _Identities:
    def __init__(self, instruments=(), *, transport=None):
        self.instruments = {item.id: item for item in instruments}
        self.transport = transport or BoundedHTTPClient()

    def identity(self, instrument):
        item = instrument if isinstance(instrument, InstrumentRecord) else self.instruments.get(_as_uuid(instrument))
        if item is None:
            raise DataUnavailableError("unknown_instrument")
        if item.instrument_type.lower() != "equity" or (item.venue or "").upper() not in US_VENUES:
            raise DataUnavailableError("unsupported_instrument")
        if not re.fullmatch(r"[A-Z][A-Z0-9]*(?:[.-][A-Z0-9]+)?", item.symbol) or len(item.symbol) > 16:
            raise DataUnavailableError("unsupported_symbol")
        return item


class YahooFinanceMarketDataProvider(_Identities, MarketDataProvider):
    """Unofficial public chart endpoint; latest regular-session quote, possibly delayed."""

    @parsed
    def get_quote(self, instrument):
        item = self.identity(instrument)
        symbol = item.symbol.replace(".", "-")
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
        chart = json_data(self.transport.get(url))["chart"]
        if chart.get("error") or not chart.get("result"):
            raise DataUnavailableError("quote_unavailable")
        meta = chart["result"][0]["meta"]
        if meta["symbol"].upper() != symbol or meta.get("instrumentType") != "EQUITY":
            raise DataUnavailableError("symbol_mismatch")
        currency = text(meta["currency"], 16)
        if currency != item.currency:
            raise DataUnavailableError("currency_mismatch")
        price = Decimal(str(meta["regularMarketPrice"]))
        if not price.is_finite() or price <= 0:
            raise ValueError("Invalid price")
        timestamp = meta["regularMarketTime"]
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or timestamp <= 0:
            raise ValueError("Invalid timestamp")
        as_of = datetime.fromtimestamp(timestamp, timezone.utc)
        if as_of > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("Future quote")
        return MarketQuoteRecord(item.id, price, currency, as_of,
                                 "Yahoo Finance chart; latest regular-session price; delay unknown, not guaranteed real-time")

    def get_price_history(self, instrument, *, start=None, end=None, limit=None):
        self.identity(instrument)
        raise DataUnavailableError("price_history_not_implemented")


class GoogleNewsRSSProvider(_Identities, NewsProvider):
    """Discovery radar only: publisher identity does not verify the linked headline."""

    def identity(self, instrument):
        item = instrument if isinstance(instrument, InstrumentRecord) else self.instruments.get(_as_uuid(instrument))
        if item is None:
            raise DataUnavailableError("unknown_instrument")
        if not isinstance(item.symbol, str) or not item.symbol.strip() or len(item.symbol) > 32:
            raise DataUnavailableError("unsupported_symbol")
        return item

    def get_recent_news(self, instrument=None, *, since=None, until=None, limit=10):
        start, end = window(since, until, limit)
        item = self.identity(instrument)
        if limit == 0:
            return []
        return self._fetch(item, start, end, limit)

    @parsed
    def _fetch(self, item, start, end, limit):
        name = re.sub(r"[^A-Za-z0-9 ]", " ", item.name)[:100].strip()
        # RSS search has day precision. Widen calendar bounds; enforce exact UTC locally.
        query = (f'"{name}" {item.symbol} after:{(start-timedelta(days=1)).date()}'
                 f' before:{(end+timedelta(days=1)).date()}')
        url = "https://news.google.com/rss/search?" + urlencode({"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"})
        raw = self.transport.get(url)
        # Reject DTD/entity declarations and alternate encodings before XML parsing.
        if b"\x00" in raw or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            raise ValueError("Unsafe XML")
        root = ElementTree.fromstring(raw)
        channel = root.find("channel")
        if root.tag != "rss" or channel is None:
            raise ValueError("Not RSS")
        nodes = channel.findall("item")
        if len(nodes) > 1000:
            raise ValueError("Too many items")
        results, seen = [], set()
        for node in nodes:
            title = text(node.findtext("title"))
            date = _require_utc(parsedate_to_datetime(node.findtext("pubDate")), "pubDate")
            link = text(node.findtext("link"), 2000)
            parts = urlsplit(link)
            if parts.scheme not in {"https", "http"} or not parts.hostname or parts.username or parts.password:
                raise ValueError("Invalid news reference")
            publisher = text(node.findtext("source"), 150)
            if start <= date <= end and link not in seen:
                seen.add(link)
                results.append(NewsItemRecord(title, date, publisher, link,
                                              instrument_id=item.id, source_quality="RADAR_UNVERIFIED"))
        return sorted(results, key=lambda r: r.published_at, reverse=True)[:limit]


class SECDisclosureProvider(_Identities, DisclosureProvider):
    """Official ticker map + current submissions metadata, no document body downloads."""

    def __init__(self, instruments=(), *, transport=None, user_agent=None, cache_ttl=86400):
        super().__init__(instruments, transport=transport)
        self.user_agent = user_agent if user_agent is not None else os.environ.get("II_SEC_USER_AGENT", "")
        if (not isinstance(self.user_agent, str) or len(self.user_agent) > 250
                or any(ord(c) < 32 or ord(c) > 126 for c in self.user_agent)
                or len(self.user_agent.split()) < 2
                or not re.search(r"\S+@\S+\.\S+", self.user_agent)
                or "example.com" in self.user_agent.lower()):
            raise ProviderConfigurationError("II_SEC_USER_AGENT requires application identification and a real contact email")
        if not 1 <= cache_ttl <= 86400:
            raise ValueError("cache_ttl must be 1..86400 seconds")
        self.cache_ttl, self._expires, self._mapping = cache_ttl, 0.0, {}

    def _get(self, url):
        return json_data(self.transport.get(url, headers={"User-Agent": self.user_agent, "Accept": "application/json"}))

    @parsed
    def resolve_cik(self, instrument):
        item = self.identity(instrument)
        if time.monotonic() >= self._expires:
            data = self._get("https://www.sec.gov/files/company_tickers.json")
            if not isinstance(data, dict) or not data or len(data) > 50000:
                raise ValueError("Invalid ticker map")
            mapping = {}
            for row in data.values():
                ticker = text(row["ticker"], 32).upper()
                cik = str(row["cik_str"])
                if not re.fullmatch(r"[0-9]{1,10}", cik) or int(cik) == 0:
                    raise ValueError("Invalid CIK")
                if ticker in mapping and mapping[ticker] != cik.zfill(10):
                    raise ValueError("Ambiguous ticker")
                mapping[ticker] = cik.zfill(10)
            self._mapping, self._expires = mapping, time.monotonic() + self.cache_ttl
        cik = self._mapping.get(item.symbol.replace(".", "-"))
        if cik is None:
            raise DataUnavailableError("sec_ticker_not_found")
        return cik

    def get_recent_disclosures(self, instrument, *, since=None, until=None, limit=10):
        start, end = window(since, until, limit)
        item = self.identity(instrument)
        if limit == 0:
            return []
        return self._fetch(item, start, end, limit)

    @parsed
    def _fetch(self, item, start, end, limit):
        cik = self.resolve_cik(item)
        data = self._get(f"https://data.sec.gov/submissions/CIK{cik}.json")
        if str(data["cik"]).zfill(10) != cik:
            raise ValueError("CIK mismatch")
        recent = data["filings"]["recent"]
        keys = ("accessionNumber", "form", "filingDate", "acceptanceDateTime", "primaryDocument")
        if any(not isinstance(recent[k], list) for k in keys):
            raise ValueError("Invalid arrays")
        count = len(recent["form"])
        if count > 20000 or any(len(recent[k]) != count for k in keys):
            raise ValueError("Misaligned arrays")
        results, seen, times = [], set(), []
        for i in range(count):
            # Exact acceptance instant is required; do not invent an intraday filing time.
            date = _require_utc(datetime.fromisoformat(recent["acceptanceDateTime"][i].replace("Z", "+00:00")), "acceptanceDateTime")
            times.append(date)
            if not start <= date <= end:
                continue
            accession = recent["accessionNumber"][i]
            if not re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession):
                raise ValueError("Invalid accession")
            document = recent["primaryDocument"][i]
            # SEC Form 4 primaryDocument commonly includes an xslF345.../ prefix.
            if (not isinstance(document, str) or len(document) > 300
                    or not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*(?:/[A-Za-z0-9_-][A-Za-z0-9_.-]*){0,2}", document)
                    or ".." in document):
                raise ValueError("Invalid document")
            form = text(recent["form"][i], 32)
            filed_date = datetime.strptime(recent["filingDate"][i], "%Y-%m-%d").date().isoformat()
            if accession not in seen:
                seen.add(accession)
                results.append(DisclosureItemRecord(
                    item.id, form, f"{item.symbol} SEC {form}", date, "SEC EDGAR",
                    f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{document}",
                    document_id=accession, metadata={"filing_date": filed_date, "timestamp_basis": "acceptanceDateTime",
                                                     "cik": cik, "content_scope": "metadata_only"},
                ))
        # Do not misrepresent truncated current submissions as complete historical coverage.
        if data["filings"].get("files") and (not times or start < min(times)):
            raise DataUnavailableError("window_exceeds_recent_submissions")
        return sorted(results, key=lambda r: r.published_at, reverse=True)[:limit]
