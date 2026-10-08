"""External price fetchers — one async function per asset type.

Each fetcher returns (price: Decimal, currency: str) or raises on failure.
Callers handle fallback to last-known price.
"""

import logging
import json
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Optional

import aiohttp

from app.config import settings

logger = logging.getLogger(__name__)

_AIOHTTP_TIMEOUT = aiohttp.ClientTimeout(total=10)


# ── Forex (ExchangeRate-API) ──────────────────────────────────────────────────


async def fetch_forex(symbol: str) -> tuple[Decimal, str]:
    """Fetch exchange rate for a pair like ``USD/TRY``.

    Returns (rate, quote_currency).  E.g. USD/TRY → (Decimal("32.5"), "TRY").
    """
    parts = symbol.upper().replace("-", "/").split("/")
    if len(parts) != 2:
        raise ValueError(f"Invalid forex pair format: {symbol!r} — expected BASE/QUOTE")
    base, quote = parts

    api_key = settings.EXCHANGE_RATE_API_KEY
    if not api_key or api_key == "your-exchangerate-api-key":
        raise RuntimeError("EXCHANGE_RATE_API_KEY is not configured")

    url = f"https://v6.exchangerate-api.com/v6/{api_key}/pair/{base}/{quote}"
    async with aiohttp.ClientSession(timeout=_AIOHTTP_TIMEOUT) as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            data = await resp.json()

    if data.get("result") != "success":
        raise RuntimeError(f"ExchangeRate-API error: {data}")

    rate = Decimal(str(data["conversion_rate"]))
    return rate, quote


# ── Crypto (CoinGecko) ───────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _coingecko_ids() -> dict[str, str]:
    data_path = Path(__file__).parent.parent / "data" / "crypto_list.json"
    with open(data_path, encoding="utf-8") as f:
        coins = json.load(f)
    return {
        str(coin["symbol"]).upper(): str(coin["coingecko_id"])
        for coin in coins
        if coin.get("symbol") and coin.get("coingecko_id")
    }


async def fetch_crypto(symbol: str) -> tuple[Decimal, str]:
    """Fetch crypto price in USD from CoinGecko.

    *symbol* can be a ticker (``BTC``) or a CoinGecko ID (``bitcoin``).
    """
    ticker = symbol.upper()
    coin_id = _coingecko_ids().get(ticker, symbol.lower())

    url = f"{settings.COINGECKO_BASE_URL}/simple/price"
    params = {"ids": coin_id, "vs_currencies": "usd"}

    async with aiohttp.ClientSession(timeout=_AIOHTTP_TIMEOUT) as session:
        async with session.get(url, params=params) as resp:
            resp.raise_for_status()
            data = await resp.json()

    if coin_id not in data:
        raise ValueError(f"CoinGecko returned no data for {coin_id!r}")

    price = Decimal(str(data[coin_id]["usd"]))
    return price, "USD"


# ── Stocks (yfinance) — BIST + international ────────────────────────────────


async def fetch_stock(symbol: str) -> tuple[Decimal, str]:
    """Fetch stock price via yfinance.

    Supports both BIST and international stocks:
    - If *symbol* already contains a dot (e.g. ``THYAO.IS``, ``BRK.A``),
      it is used exactly as provided.
    - If *symbol* has no dot (e.g. ``AAPL``, ``THYAO``), the ticker is tried
      directly first (covers US/EU markets).  If yfinance returns no price,
      the function retries with an ``.IS`` suffix (Borsa Istanbul fallback).

    Currency is inferred from the final ticker:
      - Ends with ``.IS``  → TRY
      - Otherwise          → USD
    """
    import asyncio
    import yfinance as yf

    ticker = symbol.upper()

    def _price_for(t: str) -> Optional[Decimal]:
        info = yf.Ticker(t).fast_info
        price = getattr(info, "last_price", None)
        if price is None:
            hist = yf.Ticker(t).history(period="1d")
            if hist.empty:
                return None
            price = hist["Close"].iloc[-1]
        return Decimal(str(round(float(price), 6)))

    loop = asyncio.get_running_loop()

    if "." in ticker:
        # Symbol is fully qualified — use as-is
        price = await loop.run_in_executor(None, _price_for, ticker)
        resolved = ticker
    else:
        # Try the bare ticker first (US/international), then .IS fallback
        price = await loop.run_in_executor(None, _price_for, ticker)
        resolved = ticker
        if price is None:
            bist_ticker = f"{ticker}.IS"
            price = await loop.run_in_executor(None, _price_for, bist_ticker)
            resolved = bist_ticker

    if price is None:
        raise ValueError(
            f"yfinance returned no price for {symbol!r} "
            f"(tried {ticker!r}" + (f" and {ticker}.IS" if "." not in ticker else "") + ")"
        )

    currency = "TRY" if resolved.endswith(".IS") else "USD"
    return price, currency


# ── Precious Metals (troy-ounce base + Turkish gold sub-types + silver/platinum/palladium) ──

# 1 troy ounce = 31.1035 grams (exact)
_TROY_OZ_TO_GRAMS = Decimal("31.1035")

_YFINANCE_METAL_TICKERS: dict[str, str] = {
    "XAU": "GC=F",
    "XAG": "SI=F",
    "XPT": "PL=F",
    "XPD": "PA=F",
}

# Mapping from symbol → (base_metal_ticker, gram_multiplier_or_None)
# base_metal_ticker is one of XAU, XAG, XPT, XPD (MetalPriceAPI / ExchangeRate-API symbols)
# gram_multiplier is None for ounce-based symbols (price returned directly)
# For gram-based symbols, price = (oz_price / 31.1035) * multiplier
_SYMBOL_META: dict[str, tuple[str, Optional[Decimal]]] = {
    # Gold
    "XAU":       ("XAU", None),              # gold — troy ounce
    "GR":        ("XAU", Decimal("1")),      # gold — 1 gram (24-karat pure)
    "QTR":       ("XAU", Decimal("1.625")),  # gold — çeyrek altın (quarter coin, 22-karat)
    "HALF":      ("XAU", Decimal("3.25")),   # gold — yarım altın  (half coin,    22-karat)
    "FULL":      ("XAU", Decimal("6.48")),   # gold — tam altın    (full coin,    22-karat)
    # Silver
    "XAG":       ("XAG", None),              # silver — troy ounce
    "SILVER_GR": ("XAG", Decimal("1")),      # silver — 1 gram
    # Platinum
    "XPT":       ("XPT", None),              # platinum — troy ounce
    # Palladium
    "XPD":       ("XPD", None),              # palladium — troy ounce
}


async def fetch_precious_metal(symbol: str) -> tuple[Decimal, str]:
    """Fetch precious metal price in USD.

    *symbol* is one of:
    - Gold:      ``XAU`` (ounce), ``GR`` (gram), ``QTR`` (çeyrek), ``HALF`` (yarım), ``FULL`` (tam)
    - Silver:    ``XAG`` (ounce), ``SILVER_GR`` (gram)
    - Platinum:  ``XPT`` (ounce)
    - Palladium: ``XPD`` (ounce)

    Unrecognised symbols fall back to XAU.
    All prices are returned in USD.
    """
    sub_type = (symbol.upper() if symbol else "XAU")
    if sub_type not in _SYMBOL_META:
        logger.warning("Unknown precious metal symbol %r — defaulting to XAU.", symbol)
        sub_type = "XAU"

    base_metal, gram_multiplier = _SYMBOL_META[sub_type]
    oz_price = await _fetch_metal_oz_usd(base_metal)

    if gram_multiplier is None:
        return oz_price, "USD"

    gram_price = oz_price / _TROY_OZ_TO_GRAMS
    price = (gram_price * gram_multiplier).quantize(Decimal("0.000001"))
    return price, "USD"


async def _fetch_metal_oz_usd(metal: str) -> Decimal:
    """Retrieve the USD price per troy ounce for *metal* (XAU, XAG, XPT, XPD).

    Primary source: yfinance futures tickers, which align with the TradingView
    charts shown in the UI. Fallbacks use the configured metal/forex APIs.
    """
    try:
        return await _fetch_metal_yfinance(metal)
    except Exception:
        logger.warning("yfinance metal price failed for %s, trying fallback", metal, exc_info=True)

    metal_key = getattr(settings, "METAL_PRICE_API_KEY", "")

    if metal_key and metal_key != "your-metal-price-api-key":
        try:
            return await _fetch_metalprice(metal_key, metal)
        except Exception:
            logger.warning(
                "MetalPriceAPI failed for %s, trying fallback", metal, exc_info=True
            )

    # ExchangeRate-API fallback is available for XAU only
    if metal == "XAU":
        api_key = settings.EXCHANGE_RATE_API_KEY
        if api_key and api_key != "your-exchangerate-api-key":
            try:
                return await _fetch_xau_exchangerate(api_key)
            except Exception:
                logger.warning("ExchangeRate-API XAU fallback failed", exc_info=True)

    raise RuntimeError(
        f"No price API configured or all attempts failed for metal {metal!r}"
    )


async def _fetch_metal_yfinance(metal: str) -> Decimal:
    """Fetch metal futures prices via yfinance."""
    import asyncio
    import yfinance as yf

    ticker = _YFINANCE_METAL_TICKERS.get(metal)
    if ticker is None:
        raise ValueError(f"No yfinance ticker configured for metal {metal!r}")

    def _price_for(t: str) -> Optional[Decimal]:
        info = yf.Ticker(t).fast_info
        price = getattr(info, "last_price", None)
        if price is None:
            hist = yf.Ticker(t).history(period="1d")
            if hist.empty:
                return None
            price = hist["Close"].iloc[-1]
        return Decimal(str(round(float(price), 6)))

    loop = asyncio.get_running_loop()
    price = await loop.run_in_executor(None, _price_for, ticker)
    if price is None:
        raise ValueError(f"yfinance returned no price for metal {metal!r} ({ticker})")
    return price


async def _fetch_metalprice(api_key: str, metal: str) -> Decimal:
    """Fetch USD price per troy ounce for *metal* from MetalPriceAPI."""
    url = "https://api.metalpriceapi.com/v1/latest"
    params = {"api_key": api_key, "base": metal, "currencies": "USD"}
    async with aiohttp.ClientSession(timeout=_AIOHTTP_TIMEOUT) as session:
        async with session.get(url, params=params) as resp:
            resp.raise_for_status()
            data = await resp.json()
    if not data.get("success"):
        raise RuntimeError(f"MetalPriceAPI error: {data}")
    rate = data["rates"]["USD"]
    return Decimal(str(rate))


async def _fetch_xau_exchangerate(api_key: str) -> Decimal:
    """Use ExchangeRate-API's XAU/USD pair as a gold price proxy (fallback)."""
    url = f"https://v6.exchangerate-api.com/v6/{api_key}/pair/XAU/USD"
    async with aiohttp.ClientSession(timeout=_AIOHTTP_TIMEOUT) as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            data = await resp.json()
    if data.get("result") != "success":
        raise RuntimeError(f"ExchangeRate-API XAU error: {data}")
    return Decimal(str(data["conversion_rate"]))


# ── Funds (TEFAS) ─────────────────────────────────────────────────────────────


async def fetch_fund(symbol: str) -> tuple[Decimal, str]:
    """Fetch investment fund unit price in TRY from TEFAS."""
    from app.providers import get_fund_provider

    provider = get_fund_provider()
    meta = await provider.get_fund_info(symbol)
    return meta.price, meta.currency


# ── Dispatcher ────────────────────────────────────────────────────────────────


FETCHER_MAP: dict[str, callable] = {
    "FOREX": fetch_forex,
    "CRYPTO": fetch_crypto,
    "STOCK": fetch_stock,
    "PRECIOUS_METALS": fetch_precious_metal,
    "FUND": fetch_fund,
}


async def fetch_price(asset_type: str, symbol: str) -> tuple[Decimal, str]:
    """Dispatch to the correct fetcher based on asset_type.

    Raises ``ValueError`` for manual-only types (REAL_ESTATE, CUSTOM).
    """
    fetcher = FETCHER_MAP.get(asset_type)
    if fetcher is None:
        raise ValueError(
            f"Asset type {asset_type!r} does not support automatic price fetching"
        )
    return await fetcher(symbol)
