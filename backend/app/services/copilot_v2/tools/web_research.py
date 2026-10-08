"""Web research and external evidence tools for Copilot V2.

Provides controlled, read-only tools for searching news and fetching public web pages
with strict SSRF protection, bounded payloads, and in-memory TTL caching.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import html
import ipaddress
import logging
import re
import socket
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit
import urllib.request
from uuid import UUID
from xml.etree import ElementTree

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instrument import Instrument

logger = logging.getLogger(__name__)

# Maximum constants
MAX_SEARCH_RESULTS = 8
DEFAULT_SEARCH_RESULTS = 5
MAX_PAGE_BYTES = 512_000  # 500 KB limit
MAX_PAGE_TEXT_CHARS = 2500
MAX_REDIRECTS = 3
SEARCH_CACHE_TTL_SECONDS = 180  # 3 minutes

# Simple in-memory search cache: key -> (timestamp, results)
_SEARCH_CACHE: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}

# Known cloud metadata / restricted hostnames
DISALLOWED_HOSTS: Set[str] = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "169.254.169.254",
    "metadata.google.internal",
    "backend",
    "db",
    "frontend",
    "postgres",
}


@dataclass
class ExternalEvidenceItem:
    """Structured evidence item representation."""

    title: str
    source_name: str
    source_url: str
    published_at: Optional[str]
    retrieved_at: str
    snippet: str
    evidence_type: str = "NEWS"  # NEWS, ARTICLE, DISCLOSURE
    relevance_hint: Optional[str] = None
    symbol: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "published_at": self.published_at,
            "retrieved_at": self.retrieved_at,
            "snippet": self.snippet,
            "evidence_type": self.evidence_type,
            "relevance_hint": self.relevance_hint,
            "symbol": self.symbol,
        }


def is_ip_allowed(ip_str: str) -> bool:
    """Check if an IP string is public and not reserved or private."""
    try:
        ip = ipaddress.ip_address(ip_str)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False
        # Explicit block for cloud metadata IP 169.254.169.254
        if str(ip) == "169.254.169.254":
            return False
        return True
    except ValueError:
        return False


def is_safe_url(url: str) -> Tuple[bool, Optional[str]]:
    """Validate URL scheme and ensure destination host is public (SSRF defense)."""
    try:
        parts = urlsplit(url)
    except Exception:
        return False, "Invalid URL structure"

    if parts.scheme not in {"http", "https"}:
        return False, f"Unsupported URL scheme '{parts.scheme}'. Only http and https allowed."

    if not parts.hostname:
        return False, "Missing hostname in URL"

    hostname_lower = parts.hostname.lower().strip()
    if hostname_lower in DISALLOWED_HOSTS:
        return False, f"Host '{hostname_lower}' is not permitted (internal/restricted host)."

    # Resolve hostname to all associated IPs and verify none are private/reserved
    try:
        addr_info = socket.getaddrinfo(hostname_lower, None)
    except socket.gaierror as e:
        return False, f"DNS resolution failed for '{hostname_lower}': {e}"
    except Exception as e:
        return False, f"DNS resolution error: {e}"

    if not addr_info:
        return False, f"Could not resolve host '{hostname_lower}'"

    for entry in addr_info:
        sockaddr = entry[4]
        ip_addr = sockaddr[0]
        if not is_ip_allowed(ip_addr):
            return False, f"Host '{hostname_lower}' resolved to private/restricted IP: {ip_addr}"

    return True, None


class SSRFSafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Custom redirect handler that validates target destination on every redirect."""

    def __init__(self, max_redirects: int = MAX_REDIRECTS):
        super().__init__()
        self.max_redirects = max_redirects
        self.redirect_count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.redirect_count += 1
        if self.redirect_count > self.max_redirects:
            raise HTTPError(req.full_url, code, f"Exceeded maximum redirects ({self.max_redirects})", headers, fp)

        # Resolve relative URLs
        target_url = urljoin(req.full_url, newurl)
        safe, reason = is_safe_url(target_url)
        if not safe:
            raise HTTPError(req.full_url, code, f"Redirect target blocked by SSRF guard: {reason}", headers, fp)

        return super().redirect_request(req, fp, code, msg, headers, target_url)


def clean_html_to_text(html_content: str) -> str:
    """Extract readable text from HTML content, stripping scripts and tags."""
    # Remove script and style elements
    cleaned = re.sub(r"<(script|style|svg|noscript)[^>]*>.*?</\1>", " ", html_content, flags=re.DOTALL | re.IGNORECASE)
    # Strip HTML tags
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    # Unescape HTML entities
    cleaned = html.unescape(cleaned)
    # Normalize whitespaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


async def fetch_web_page_handler(url: str, **kwargs: Any) -> Dict[str, Any]:
    """Fetch and extract text content from a web page safely."""
    safe, reason = is_safe_url(url)
    if not safe:
        return {
            "status": "error",
            "url": url,
            "message": f"URL rejected: {reason}",
            "text": None,
        }

    opener = urllib.request.build_opener(SSRFSafeRedirectHandler(max_redirects=MAX_REDIRECTS))
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PortfolioMind-Research/1.0",
            "Accept": "text/html,text/plain,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    )

    try:
        with opener.open(req, timeout=8.0) as resp:
            content_type = resp.headers.get("Content-Type", "")
            # Verify content-type is textual
            if not any(t in content_type.lower() for t in ("text/html", "text/plain", "application/xhtml+xml", "text/")):
                return {
                    "status": "error",
                    "url": url,
                    "message": f"Unsupported Content-Type '{content_type}'. Only HTML or plain text allowed.",
                    "text": None,
                }

            # Bounded read
            raw_bytes = resp.read(MAX_PAGE_BYTES + 1)
            if len(raw_bytes) > MAX_PAGE_BYTES:
                return {
                    "status": "error",
                    "url": url,
                    "message": f"Response exceeded maximum allowed size of {MAX_PAGE_BYTES // 1024} KB.",
                    "text": None,
                }

            charset = "utf-8"
            match = re.search(r"charset=([\w-]+)", content_type, re.IGNORECASE)
            if match:
                charset = match.group(1).lower()

            try:
                decoded_str = raw_bytes.decode(charset, errors="replace")
            except Exception:
                decoded_str = raw_bytes.decode("utf-8", errors="replace")

            extracted_text = clean_html_to_text(decoded_str)
            snippet = extracted_text[:MAX_PAGE_TEXT_CHARS]

            return {
                "status": "success",
                "url": url,
                "title": _extract_html_title(decoded_str),
                "text": snippet,
                "character_count": len(snippet),
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            }

    except HTTPError as e:
        logger.warning("HTTP error fetching %s: status %d", url, e.code)
        return {
            "status": "error",
            "url": url,
            "message": f"HTTP {e.code}: {e.reason}",
            "text": None,
        }
    except URLError as e:
        logger.warning("URL error fetching %s: %s", url, e.reason)
        return {
            "status": "error",
            "url": url,
            "message": f"Connection error: {e.reason}",
            "text": None,
        }
    except Exception as e:
        logger.warning("Unexpected error fetching %s: %s", url, e)
        return {
            "status": "error",
            "url": url,
            "message": f"Failed to fetch page: {type(e).__name__}",
            "text": None,
        }


def _extract_html_title(html_str: str) -> Optional[str]:
    """Extract <title> from HTML if present."""
    match = re.search(r"<title[^>]*>(.*?)</title>", html_str, re.IGNORECASE | re.DOTALL)
    if match:
        return html.unescape(match.group(1)).strip()[:200]
    return None


async def _enrich_query_with_symbol_metadata(
    db: Optional[AsyncSession],
    symbol: str,
    user_id: Optional[UUID] = None,
) -> Optional[str]:
    """Lookup instrument canonical name to enrich search queries using canonical entity resolution."""
    if not db:
        return None
    try:
        from app.services.copilot_v2.entity_resolver import EntityResolver
        entity = await EntityResolver.resolve(db=db, query=symbol, user_id=user_id)
        if entity.canonical_name:
            return entity.canonical_name
    except Exception as e:
        logger.debug("Failed symbol enrichment for %s: %s", symbol, e)
    return None


async def search_news_handler(
    query: str,
    symbols: Optional[List[str]] = None,
    lookback_days: int = 7,
    max_results: int = DEFAULT_SEARCH_RESULTS,
    db: Optional[AsyncSession] = None,
    user_id: Optional[UUID] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Search Google News RSS for recent public news items with deduplication and bounded output."""
    limit = min(max(1, max_results), MAX_SEARCH_RESULTS)
    lookback = min(max(1, lookback_days), 90)

    # Clean and normalize query
    clean_query = query.strip()
    enriched_keywords: List[str] = [clean_query]

    # Symbol enrichment
    if symbols:
        for s in symbols:
            s_clean = s.strip().upper()
            if s_clean not in clean_query.upper():
                enriched_keywords.append(s_clean)
            if db:
                inst_name = await _enrich_query_with_symbol_metadata(db, s_clean, user_id=user_id)
                if inst_name:
                    # e.g. TERA PORTFÖY
                    short_name = re.sub(r"\(.*?\)", "", inst_name).strip()
                    first_words = " ".join(short_name.split()[:3])
                    if first_words.upper() not in clean_query.upper():
                        enriched_keywords.append(f'"{first_words}"')

    final_search_query = " ".join(enriched_keywords)

    # Check cache
    cache_key = f"{final_search_query.lower()}:{lookback}:{limit}"
    now_ts = time.time()
    if cache_key in _SEARCH_CACHE:
        cached_ts, cached_results = _SEARCH_CACHE[cache_key]
        if now_ts - cached_ts < SEARCH_CACHE_TTL_SECONDS:
            logger.debug("Returning cached news search for: %s", final_search_query)
            return {
                "query": final_search_query,
                "cached": True,
                "count": len(cached_results),
                "results": cached_results,
            }

    # Detect language/region: Turkish vs English
    has_turkish_chars = any(c in final_search_query for c in "çğıöşüÇĞİÖŞÜ")
    is_turkish_market = any(kw in final_search_query.upper() for kw in ("THF", "BIST", "TEFAS", "PORTFÖY", "FON", "TL"))

    if has_turkish_chars or is_turkish_market:
        rss_params = {"q": final_search_query, "hl": "tr", "gl": "TR", "ceid": "TR:tr"}
    else:
        rss_params = {"q": final_search_query, "hl": "en-US", "gl": "US", "ceid": "US:en"}

    rss_url = "https://news.google.com/rss/search?" + urlencode(rss_params)

    req = urllib.request.Request(
        rss_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PortfolioMind-Research/1.0",
            "Accept": "application/rss+xml, application/xml, text/xml",
        },
    )

    results: List[Dict[str, Any]] = []
    seen_links: Set[str] = set()
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=lookback)

    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            raw_xml = resp.read()

        # Reject unsafe XML declarations before parsing
        if b"\x00" in raw_xml or b"<!DOCTYPE" in raw_xml.upper() or b"<!ENTITY" in raw_xml.upper():
            return {
                "query": final_search_query,
                "count": 0,
                "results": [],
                "error": "Unsafe XML received from news feed",
            }

        root = ElementTree.fromstring(raw_xml)
        items = root.findall(".//item")

        for item in items:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date_str = item.findtext("pubDate")
            source_name = (item.findtext("source") or "News Provider").strip()

            if not title or not link or link in seen_links:
                continue

            published_dt: Optional[datetime] = None
            if pub_date_str:
                try:
                    published_dt = parsedate_to_datetime(pub_date_str)
                    if published_dt.tzinfo is None:
                        published_dt = published_dt.replace(tzinfo=timezone.utc)
                except Exception:
                    published_dt = None

            # Enforce lookback window
            if published_dt and published_dt < cutoff_date:
                continue

            # Extract source from title suffix if publisher tag is generic
            # e.g. "Headline - SourceName"
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                clean_title = parts[0].strip()
                if not source_name or source_name == "News Provider":
                    source_name = parts[1].strip()
            else:
                clean_title = title

            seen_links.add(link)
            results.append({
                "title": clean_title,
                "source": source_name,
                "published_at": published_dt.isoformat() if published_dt else None,
                "url": link,
                "snippet": clean_title,  # RSS item title acts as concise snippet
                "evidence_type": "NEWS",
            })

            if len(results) >= limit:
                break

    except Exception as e:
        logger.warning("Error fetching Google News RSS for query '%s': %s", final_search_query, e)
        # On error, return bounded graceful response
        return {
            "query": final_search_query,
            "count": 0,
            "results": [],
            "error": f"News search temporary unavailable: {type(e).__name__}",
        }

    # Save to short-lived in-memory cache
    _SEARCH_CACHE[cache_key] = (now_ts, results)

    # Clean old cache entries if cache grows
    if len(_SEARCH_CACHE) > 100:
        expired_keys = [k for k, (ts, _) in _SEARCH_CACHE.items() if now_ts - ts > SEARCH_CACHE_TTL_SECONDS]
        for k in expired_keys:
            _SEARCH_CACHE.pop(k, None)

    return {
        "query": final_search_query,
        "cached": False,
        "count": len(results),
        "results": results,
    }


async def search_web_handler(
    query: str,
    max_results: int = DEFAULT_SEARCH_RESULTS,
    db: Optional[AsyncSession] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Perform generic public web search via safe search provider with broad lookback."""
    # Delegates safely to search_news_handler with 30-day lookback for general queries
    return await search_news_handler(
        query=query,
        symbols=None,
        lookback_days=30,
        max_results=max_results,
        db=db,
        **kwargs,
    )
