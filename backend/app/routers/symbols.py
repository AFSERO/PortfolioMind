"""Symbol search and resolution endpoint — serves static JSON symbol lists and live asset resolution."""

import json
from pathlib import Path
from functools import lru_cache
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.services.asset_resolver import get_precious_metals_catalog, resolve_asset

router = APIRouter()

_DATA_DIR = Path(__file__).parent.parent / "data"


@lru_cache(maxsize=8)
def _load(filename: str) -> list[dict]:
    with open(_DATA_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def _search(items: list[dict], q: str, limit: int) -> list[dict]:
    q = q.strip().lower()
    if not q:
        return items[:limit]
    results = []
    # Prioritise prefix matches on symbol, then name or metal
    for item in items:
        sym = item.get("symbol", "").lower()
        name = item.get("name", "").lower()
        metal = item.get("metal", "").lower()
        if sym.startswith(q) or name.startswith(q) or metal.startswith(q):
            results.append(item)
    for item in items:
        if item in results:
            continue
        sym = item.get("symbol", "").lower()
        name = item.get("name", "").lower()
        metal = item.get("metal", "").lower()
        if q in sym or q in name or q in metal:
            results.append(item)
    return results[:limit]


@router.get("/resolve-market/{symbol}")
async def resolve_market(symbol: str):
    """Return the exchange market for a stock symbol.

    Used by the frontend to build the correct TradingView ticker prefix.

    Resolution order:
    1. If *symbol* ends with ``.IS`` → always BIST.
    2. If *symbol* (stripped of ``.IS``) exists in the BIST stock list → BIST.
    3. Otherwise → NASDAQ (default for US / international equities).
    """
    bare = symbol.upper().removesuffix(".IS")
    bist_symbols = {item["symbol"].upper() for item in _load("bist_stocks.json")}
    market = "BIST" if bare in bist_symbols else "NASDAQ"
    return {"status": "success", "data": {"market": market}}


@router.get("/search")
async def search_symbols(
    type: str = Query(..., description="Asset type to search (stock, us_stock, crypto, forex, fund, precious_metals)"),
    q: str = Query("", description="Search query"),
    limit: int = Query(20, ge=1, le=100),
):
    """Search symbols by type and query string.

    For ``type=stock`` both BIST and US stock lists are searched so users can
    find Turkish and global equities in a single query.
    Returns up to *limit* matching entries with normalized metadata.
    """
    t = type.strip().lower()

    if t in ("stock", "stocks"):
        bist = [
            {**item, "asset_type": "STOCK", "market": "BIST", "currency": "TRY"}
            for item in _load("bist_stocks.json")
        ]
        us = [
            {**item, "asset_type": "STOCK", "market": "NASDAQ", "currency": "USD"}
            for item in _load("us_stocks.json")
        ]
        combined = bist + us
        matches = _search(combined, q, limit)
    elif t in ("us_stock", "us_stocks"):
        us = [
            {**item, "asset_type": "STOCK", "market": "NASDAQ", "currency": "USD"}
            for item in _load("us_stocks.json")
        ]
        matches = _search(us, q, limit)
    elif t in ("crypto", "cryptocurrency"):
        crypto = [
            {**item, "asset_type": "CRYPTO", "market": "Crypto", "currency": "USD"}
            for item in _load("crypto_list.json")
        ]
        matches = _search(crypto, q, limit)
    elif t in ("fund", "funds"):
        from app.providers import get_fund_provider

        provider = get_fund_provider()
        raw_matches = await provider.search_funds(q, limit)
        matches = [
            {
                "symbol": item.get("symbol", item.get("fund_code", "")),
                "name": item.get("name", item.get("fund_name", "")),
                "asset_type": "FUND",
                "market": "TEFAS",
                "currency": "TRY",
            }
            for item in raw_matches
        ]
    elif t in ("precious_metals", "precious_metal", "metal", "metals"):
        metals = [
            {**item, "asset_type": "PRECIOUS_METALS", "market": "Precious Metals"}
            for item in get_precious_metals_catalog()
        ]
        matches = _search(metals, q, limit)
    else:  # forex
        fx = [
            {
                **item,
                "asset_type": "FOREX",
                "market": "Forex",
                "currency": item["symbol"].split("/")[-1] if "/" in item["symbol"] else "USD",
            }
            for item in _load("forex_list.json")
        ]
        matches = _search(fx, q, limit)

    return {"status": "success", "data": matches}


@router.get("/resolve")
async def resolve_asset_endpoint(
    type: str = Query(..., description="Asset type: stock, crypto, fund, precious_metals, forex"),
    symbol: str = Query(..., description="Asset symbol or identifier to resolve"),
):
    """Resolve canonical asset metadata and latest market price."""
    try:
        resolved = await resolve_asset(type, symbol)
        return {"status": "success", "data": resolved.model_dump()}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Asset resolution service error: {exc}"
        ) from None


@router.get("/resolve/{symbol}")
async def resolve_asset_by_path(
    symbol: str,
    type: str = Query(..., description="Asset type: stock, crypto, fund, precious_metals, forex"),
):
    """Path-based alias for asset resolution."""
    return await resolve_asset_endpoint(type=type, symbol=symbol)
