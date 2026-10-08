"""TEFAS (Türkiye Elektronik Fon Alım Satım Platformu) Fund Provider.

Fetches real-time and historical Turkish mutual fund data directly from
the official TEFAS API (https://www.tefas.gov.tr/api/funds/fonGnlBlgSiraliGetir).
"""

import asyncio
import logging
import time
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional

import httpx

from app.providers.base import BaseFundProvider, FundMetadata

logger = logging.getLogger(__name__)

_TEFAS_URL = "https://www.tefas.gov.tr/api/funds/fonGnlBlgSiraliGetir"
_HTTP_TIMEOUT = 12.0

_HEADERS = {
    "Accept": "*/*",
    "Content-Type": "application/json",
    "Origin": "https://www.tefas.gov.tr",
    "Referer": "https://www.tefas.gov.tr/tr/fon-verileri",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
    ),
}

# Supported TEFAS fund types:
# YAT: Mutual Funds (Yatırım Fonları - most common, e.g. KCV, THF, MAC, AFT)
# BYF: Exchange Traded Funds (Borsa Yatırım Fonları)
# EMK: Pension Funds (Emeklilik Fonları)
_FUND_KINDS = ("YAT", "BYF", "EMK", "GYF", "GSYF")


def _build_payload(
    kind: str,
    fund_code: Optional[str],
    start_dt: datetime,
    end_dt: datetime,
    search_text: Optional[str] = None,
    limit: int = 100000,
) -> dict:
    return {
        "fonTipi": kind,
        "fonKodu": fund_code,
        "aramaMetni": search_text,
        "fonTurKod": None,
        "fonGrubu": None,
        "sfonTurKod": None,
        "fonTurAciklama": None,
        "kurucuKod": None,
        "basTarih": start_dt.strftime("%Y%m%d"),
        "bitTarih": end_dt.strftime("%Y%m%d"),
        "basSira": 1,
        "bitSira": limit,
        "dil": "TR",
        "sFonTurKod": "",
        "fonKod": "",
        "fonGrup": "",
        "fonUnvanTip": "",
    }


class InvalidFundQuoteError(ValueError):
    """A known fund has no usable provider quote; do not treat it as absent."""


def _positive_price(value) -> Optional[Decimal]:
    """Provider data is usable only when finite and strictly positive."""
    try:
        price = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return price if price.is_finite() and price > 0 else None


class TefasFundProvider(BaseFundProvider):
    """Encapsulates all communication with the official TEFAS API."""

    def __init__(self, cache_ttl_seconds: int = 300, *, transport: Optional[httpx.AsyncBaseTransport] = None) -> None:
        self._cache_ttl = cache_ttl_seconds
        self._transport = transport
        # fund_code -> (FundMetadata, cached_at_timestamp)
        self._info_cache: dict[str, tuple[FundMetadata, float]] = {}
        # cached directory of all funds: (list of dicts, cached_at_timestamp)
        self._catalog_cache: Optional[tuple[list[dict], float]] = None
        self._catalog_lock = asyncio.Lock()

    async def get_fund_info(self, fund_code: str) -> FundMetadata:
        """Fetch latest price and metadata for *fund_code*.

        Looks back up to 10 days to handle non-trading days, weekends, and holidays.
        Caches results in-memory for 5 minutes.
        """
        code = fund_code.strip().upper()
        if not code:
            raise ValueError("Fund code cannot be empty")

        # 1. Check in-memory cache
        now = time.monotonic()
        if code in self._info_cache:
            meta, ts = self._info_cache[code]
            if now - ts < self._cache_ttl:
                return meta

        # 2. Query TEFAS with a 10-day lookback window
        today = datetime.now()
        start_dt = today - timedelta(days=10)
        rows = await self._query_tefas_code(code, start_dt, today)

        if not rows:
            raise ValueError(f"Fund '{code}' not found on TEFAS")

        # An unusable latest quote may coexist with valid earlier trading data.
        # Keep its actual source date; never manufacture a zero/1:1 price.
        valid_rows = [r for r in rows if _positive_price(r.get("fiyat")) is not None]
        if not valid_rows:
            raise InvalidFundQuoteError(f"TEFAS returned no valid positive price for fund '{code}'")
        latest_row = max(valid_rows, key=lambda r: r.get("tarih") or "")
        price = _positive_price(latest_row.get("fiyat"))
        fund_name = str(latest_row.get("fonUnvan") or code).strip()

        pdate: Optional[date] = None
        raw_date = latest_row.get("tarih")
        if raw_date:
            try:
                pdate = datetime.strptime(raw_date[:10], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pdate = None

        meta = FundMetadata(
            fund_code=code,
            fund_name=fund_name,
            price=price,
            currency="TRY",
            price_date=pdate,
            provider="TEFAS",
        )

        self._info_cache[code] = (meta, now)
        return meta

    async def _query_tefas_code(
        self, code: str, start_dt: datetime, end_dt: datetime
    ) -> list[dict]:
        """Query TEFAS for a fund code.

        Defaults to YAT (covers almost all mutual funds). To avoid triggering
        TEFAS rate limits (approx 6 req/min), we do not loop through unused kinds.
        """
        async with httpx.AsyncClient(headers=_HEADERS, verify=False, timeout=_HTTP_TIMEOUT, transport=self._transport) as client:
            payload = _build_payload("YAT", code, start_dt, end_dt)
            try:
                resp = await client.post(_TEFAS_URL, json=payload)
                if resp.status_code == 429:
                    logger.warning("TEFAS rate limit (429) hit for %s", code)
                    raise RuntimeError("TEFAS rate limit reached. Please try again shortly.")
                resp.raise_for_status()
                data = resp.json()
                rows = data.get("resultList") or []
                if rows:
                    return rows
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    raise RuntimeError("TEFAS rate limit reached. Please try again shortly.") from exc
                logger.warning("TEFAS HTTP error for %s: %s", code, exc)
                raise RuntimeError(f"TEFAS API error: {exc}") from exc
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                logger.warning("TEFAS connection error for %s: %s", code, exc)
                raise RuntimeError(f"TEFAS connection failed: {exc}") from exc
            except Exception as exc:
                logger.warning("Unexpected error during TEFAS fetch for %s: %s", code, exc)
        return []

    async def search_funds(self, query: str, limit: int = 20) -> list[dict]:
        """Search funds by code or title.

        Prioritizes prefix matches on fund code, then title matches.
        Uses cached fund catalog when available for instant responses.
        """
        q = query.strip().upper()
        catalog = await self._get_fund_catalog()

        if not q:
            return catalog[:limit]

        # 1. Exact symbol match first
        exact = [f for f in catalog if f["symbol"] == q]
        # 2. Symbol prefix match
        prefix = [f for f in catalog if f["symbol"].startswith(q) and f["symbol"] != q]
        # 3. Name contains query
        q_lower = query.strip().lower()
        name_match = [
            f for f in catalog
            if q_lower in f.get("name", "").lower() and f not in exact and f not in prefix
        ]

        results = exact + prefix + name_match
        if results:
            return results[:limit]

        # Fallback: if not in catalog (e.g. catalog outdated or fund in another kind),
        # query TEFAS directly with query as code or aramaMetni
        if len(q) in (3, 4, 5):
            try:
                info = await self.get_fund_info(q)
                return [{
                    "symbol": info.fund_code,
                    "name": info.fund_name,
                    "price": float(info.price),
                }]
            except Exception:
                pass

        return []

    async def get_fund_history(
        self, fund_code: str, days: int = 30
    ) -> list[dict]:
        """Fetch historical price points up to *days* days for *fund_code*.

        Returns a chronologically ascending list of:
        ``{"date": "YYYY-MM-DD", "price": Decimal, "currency": "TRY"}``
        """
        code = fund_code.strip().upper()
        days_bounded = min(max(days, 1), 30)  # TEFAS single request window ~30 days
        today = datetime.now()
        start_dt = today - timedelta(days=days_bounded)

        rows = await self._query_tefas_code(code, start_dt, today)
        if not rows:
            return []

        # Sort ascending by date
        sorted_rows = sorted(rows, key=lambda r: r.get("tarih", ""))
        history = []
        for r in sorted_rows:
            raw_p = _positive_price(r.get("fiyat"))
            raw_d = r.get("tarih")
            if raw_p is not None and raw_d:
                history.append({
                    "date": raw_d[:10],
                    "price": raw_p,
                    "currency": "TRY",
                })
        return history

    async def _get_fund_catalog(self) -> list[dict]:
        """Retrieve and cache the full directory of TEFAS mutual funds (1 hour TTL)."""
        now = time.monotonic()
        if self._catalog_cache is not None:
            catalog, ts = self._catalog_cache
            if now - ts < 3600:  # 1 hour
                return catalog

        async with self._catalog_lock:
            # Double check under lock
            if self._catalog_cache is not None:
                catalog, ts = self._catalog_cache
                if now - ts < 3600:
                    return catalog

            catalog = await self._fetch_all_funds()
            if catalog:
                self._catalog_cache = (catalog, now)
            return catalog or (self._catalog_cache[0] if self._catalog_cache else [])

    async def _fetch_all_funds(self) -> list[dict]:
        """Fetch list of all active funds from TEFAS."""
        today = datetime.now()
        async with httpx.AsyncClient(headers=_HEADERS, verify=False, timeout=_HTTP_TIMEOUT, transport=self._transport) as client:
            # Try today, and if weekend/holiday, try up to 4 days back
            for back in range(0, 5):
                target_dt = today - timedelta(days=back)
                payload = _build_payload("YAT", None, target_dt, target_dt)
                try:
                    resp = await client.post(_TEFAS_URL, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    rows = data.get("resultList") or []
                    if rows:
                        catalog = []
                        for r in rows:
                            sym = r.get("fonKodu")
                            name = r.get("fonUnvan")
                            price = r.get("fiyat")
                            if sym:
                                catalog.append({
                                    "symbol": sym.strip().upper(),
                                    "name": str(name or sym).strip(),
                                    "price": float(price) if price is not None else None,
                                })
                        return catalog
                except Exception as exc:
                    logger.debug("Failed catalog fetch for date %s: %s", target_dt.date(), exc)
        return []


# ── Global singleton accessor ──────────────────────────────────────────────────

_provider_instance: Optional[TefasFundProvider] = None


def get_fund_provider() -> BaseFundProvider:
    """Return the application-wide fund provider instance."""
    global _provider_instance
    if _provider_instance is None:
        _provider_instance = TefasFundProvider()
    return _provider_instance
