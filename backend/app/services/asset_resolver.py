"""Asset Resolver service — resolves canonical metadata and live market price.

Normalizes responses across US/BIST stocks, crypto, precious metals, TEFAS funds,
and forex pairs into a single consistent ResolvedAsset model.
"""

import asyncio
import json
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.asset import AssetType
from app.providers import get_fund_provider
from app.utils import cache
from app.utils.price_fetchers import (
    fetch_crypto,
    fetch_forex,
    fetch_precious_metal,
    fetch_stock,
)

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent / "data"


class ResolvedAsset(BaseModel):
    """Normalized resolution result for an asset."""

    model_config = ConfigDict(from_attributes=True)

    symbol: str
    name: str
    asset_type: str
    currency: str
    latest_price: float
    price_date: Optional[str] = None
    market: Optional[str] = None
    provider: Optional[str] = None
    provider_id: Optional[str] = None


@lru_cache(maxsize=8)
def _load_data(filename: str) -> list[dict]:
    path = _DATA_DIR / filename
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


_METALS_DATA: list[dict] = [
    {
        "symbol": "GR",
        "name": "Gram Altın / Gold (24 Karat)",
        "metal": "GOLD",
        "currency": "USD",
        "market": "Precious Metals",
    },
    {
        "symbol": "QTR",
        "name": "Çeyrek Altın / Gold Quarter",
        "metal": "GOLD",
        "currency": "USD",
        "market": "Precious Metals",
    },
    {
        "symbol": "HALF",
        "name": "Yarım Altın / Gold Half",
        "metal": "GOLD",
        "currency": "USD",
        "market": "Precious Metals",
    },
    {
        "symbol": "FULL",
        "name": "Tam Altın / Gold Full",
        "metal": "GOLD",
        "currency": "USD",
        "market": "Precious Metals",
    },
    {
        "symbol": "XAU",
        "name": "Ons Altın / Gold (Troy Ounce)",
        "metal": "GOLD",
        "currency": "USD",
        "market": "Precious Metals",
    },
    {
        "symbol": "SILVER_GR",
        "name": "Gram Gümüş / Silver (Gram)",
        "metal": "SILVER",
        "currency": "USD",
        "market": "Precious Metals",
    },
    {
        "symbol": "XAG",
        "name": "Ons Gümüş / Silver (Troy Ounce)",
        "metal": "SILVER",
        "currency": "USD",
        "market": "Precious Metals",
    },
    {
        "symbol": "XPT",
        "name": "Ons Platin / Platinum (Troy Ounce)",
        "metal": "PLATINUM",
        "currency": "USD",
        "market": "Precious Metals",
    },
    {
        "symbol": "XPD",
        "name": "Ons Paladyum / Palladium (Troy Ounce)",
        "metal": "PALLADIUM",
        "currency": "USD",
        "market": "Precious Metals",
    },
]


class StockResolver:
    """Resolves US and BIST equities."""

    @staticmethod
    async def resolve(symbol: str) -> ResolvedAsset:
        clean_symbol = symbol.strip().upper()
        bare_symbol = clean_symbol.removesuffix(".IS")

        # 1. Check BIST stocks list
        bist_items = _load_data("bist_stocks.json")
        bist_match = next(
            (item for item in bist_items if item["symbol"].upper() == bare_symbol),
            None,
        )

        # 2. Check US stocks list
        us_items = _load_data("us_stocks.json")
        us_match = next(
            (item for item in us_items if item["symbol"].upper() == clean_symbol),
            None,
        )

        # 3. Determine user-facing symbol, market and name
        if bist_match or clean_symbol.endswith(".IS"):
            user_facing_symbol = bare_symbol
            market = "BIST"
            name = bist_match["name"] if bist_match else bare_symbol
            expected_currency = "TRY"
        elif us_match:
            user_facing_symbol = clean_symbol
            market = "NASDAQ"
            name = us_match["name"]
            expected_currency = "USD"
        else:
            user_facing_symbol = bare_symbol
            market = "US/Global"
            name = bare_symbol
            expected_currency = "USD"

        # 4. Check price cache
        cache_key = f"STOCK:{clean_symbol}"
        cached = cache.get(cache_key)
        if cached is not None:
            price = cached.price
            currency = cached.currency
        else:
            try:
                price, currency = await fetch_stock(clean_symbol)
                cache.put(cache_key, price, currency)
            except Exception as exc:
                raise ValueError(
                    f"Could not resolve stock '{symbol}': price unavailable ({exc})"
                ) from exc

        # 5. If name was not in catalog, try yfinance name lookup
        if name == bare_symbol:
            try:
                import yfinance as yf

                loop = asyncio.get_running_loop()

                def _get_name():
                    t = yf.Ticker(clean_symbol if market != "BIST" else f"{bare_symbol}.IS")
                    info = t.info or {}
                    return info.get("shortName") or info.get("longName")

                fetched_name = await loop.run_in_executor(None, _get_name)
                if fetched_name:
                    name = fetched_name
            except Exception:
                pass

        today_str = date.today().isoformat()

        return ResolvedAsset(
            symbol=user_facing_symbol,
            name=name,
            asset_type=AssetType.STOCK.value,
            currency=currency or expected_currency,
            latest_price=float(price),
            price_date=today_str,
            market=market,
            provider="yfinance",
        )


class CryptoResolver:
    """Resolves cryptocurrencies with CoinGecko canonical mappings."""

    @staticmethod
    async def resolve(symbol: str) -> ResolvedAsset:
        query = symbol.strip().upper()
        crypto_items = _load_data("crypto_list.json")

        # Match by symbol (e.g. BTC) or coingecko_id (e.g. bitcoin)
        match = next(
            (
                item
                for item in crypto_items
                if item["symbol"].upper() == query
                or item.get("coingecko_id", "").lower() == symbol.strip().lower()
            ),
            None,
        )

        canonical_symbol = match["symbol"] if match else query
        name = match["name"] if match else query
        coingecko_id = match.get("coingecko_id") if match else query.lower()

        cache_key = f"CRYPTO:{canonical_symbol}"
        cached = cache.get(cache_key)
        if cached is not None:
            price = cached.price
            currency = cached.currency
        else:
            try:
                price, currency = await fetch_crypto(canonical_symbol)
                cache.put(cache_key, price, currency)
            except Exception as exc:
                raise ValueError(
                    f"Could not resolve crypto '{symbol}': price unavailable ({exc})"
                ) from exc

        today_str = date.today().isoformat()

        return ResolvedAsset(
            symbol=canonical_symbol,
            name=name,
            asset_type=AssetType.CRYPTO.value,
            currency=currency or "USD",
            latest_price=float(price),
            price_date=today_str,
            market="Crypto",
            provider="CoinGecko",
            provider_id=coingecko_id,
        )


class FundResolver:
    """Resolves Turkish investment funds using TEFAS provider."""

    @staticmethod
    async def resolve(symbol: str) -> ResolvedAsset:
        code = symbol.strip().upper()
        provider = get_fund_provider()
        try:
            meta = await provider.get_fund_info(code)
        except Exception as exc:
            raise ValueError(f"Could not resolve fund '{code}': {exc}") from exc

        return ResolvedAsset(
            symbol=meta.fund_code,
            name=meta.fund_name,
            asset_type=AssetType.FUND.value,
            currency=meta.currency,
            latest_price=float(meta.price),
            price_date=meta.price_date.isoformat() if meta.price_date else None,
            market="TEFAS",
            provider=meta.provider,
        )


class PreciousMetalsResolver:
    """Resolves precious metals (Gold, Silver, Platinum, Palladium)."""

    @staticmethod
    async def resolve(symbol: str) -> ResolvedAsset:
        query = symbol.strip().upper()

        match = next(
            (item for item in _METALS_DATA if item["symbol"].upper() == query),
            None,
        )
        if not match:
            # Fallback search by name substring (e.g. 'Gold', 'Silver')
            match = next(
                (
                    item
                    for item in _METALS_DATA
                    if query.lower() in item["name"].lower()
                    or query == item.get("metal", "")
                ),
                None,
            )

        canonical_symbol = match["symbol"] if match else query
        name = match["name"] if match else query

        cache_key = f"PRECIOUS_METALS:{canonical_symbol}"
        cached = cache.get(cache_key)
        if cached is not None:
            price = cached.price
            currency = cached.currency
        else:
            try:
                price, currency = await fetch_precious_metal(canonical_symbol)
                cache.put(cache_key, price, currency)
            except Exception as exc:
                raise ValueError(
                    f"Could not resolve precious metal '{symbol}': {exc}"
                ) from exc

        today_str = date.today().isoformat()

        return ResolvedAsset(
            symbol=canonical_symbol,
            name=name,
            asset_type=AssetType.PRECIOUS_METALS.value,
            currency=currency or "USD",
            latest_price=float(price),
            price_date=today_str,
            market="Precious Metals",
            provider="yfinance",
        )


class ForexResolver:
    """Resolves currency exchange pairs."""

    @staticmethod
    async def resolve(symbol: str) -> ResolvedAsset:
        clean = symbol.strip().upper().replace("-", "/")
        parts = clean.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid forex pair format: {symbol} (expected BASE/QUOTE)")

        base, quote = parts
        cache_key = f"FOREX:{clean}"
        cached = cache.get(cache_key)
        if cached is not None:
            price = cached.price
            currency = cached.currency
        else:
            try:
                price, currency = await fetch_forex(clean)
                cache.put(cache_key, price, currency)
            except Exception as exc:
                raise ValueError(f"Could not resolve forex '{symbol}': {exc}") from exc

        today_str = date.today().isoformat()

        return ResolvedAsset(
            symbol=clean,
            name=f"{clean} Exchange Rate",
            asset_type=AssetType.FOREX.value,
            currency=currency or quote,
            latest_price=float(price),
            price_date=today_str,
            market="Forex",
            provider="ExchangeRate-API",
        )


_RESOLVERS = {
    AssetType.STOCK.value: StockResolver.resolve,
    "STOCK": StockResolver.resolve,
    AssetType.CRYPTO.value: CryptoResolver.resolve,
    "CRYPTO": CryptoResolver.resolve,
    AssetType.FUND.value: FundResolver.resolve,
    "FUND": FundResolver.resolve,
    AssetType.PRECIOUS_METALS.value: PreciousMetalsResolver.resolve,
    "PRECIOUS_METALS": PreciousMetalsResolver.resolve,
    "METAL": PreciousMetalsResolver.resolve,
    AssetType.FOREX.value: ForexResolver.resolve,
    "FOREX": ForexResolver.resolve,
}


async def resolve_asset(asset_type: str, symbol: str) -> ResolvedAsset:
    """Dispatch asset resolution by asset_type."""
    key = asset_type.strip().upper()
    resolver = _RESOLVERS.get(key)
    if not resolver:
        raise ValueError(f"Asset type '{asset_type}' does not support automatic resolution.")
    return await resolver(symbol)


def get_precious_metals_catalog() -> list[dict]:
    """Return the precious metals catalog for search."""
    return [dict(item) for item in _METALS_DATA]
