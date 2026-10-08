"""Price service — fetch, cache, persist, and refresh asset prices."""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset, AssetType
from app.models.price_history import PriceHistory
from app.utils import cache
from app.utils.price_fetchers import fetch_price

logger = logging.getLogger(__name__)

# Asset types that support automatic price fetching
_AUTO_TYPES = {
    AssetType.STOCK,
    AssetType.FOREX,
    AssetType.PRECIOUS_METALS,
    AssetType.CRYPTO,
    AssetType.FUND,
}


async def get_live_price(
    db: AsyncSession,
    symbol: str,
    asset_type: str,
) -> dict:
    """Return a live price for *symbol*.

    1. Check in-memory cache (5-min TTL).
    2. If miss, fetch from external API.
    3. Cache the result.
    4. On failure, look up the most recent PriceHistory row as fallback.
    """
    cache_key = f"{asset_type}:{symbol}".upper()

    # 1. Cache hit?
    cached = cache.get(cache_key)
    if cached is not None:
        return {
            "symbol": symbol,
            "price": float(cached.price),
            "currency": cached.currency,
            "source": "cache",
            "fetched_at": datetime.fromtimestamp(cached.fetched_at, tz=timezone.utc).isoformat(),
        }

    # 2. Fetch from external API
    try:
        price, currency = await fetch_price(asset_type, symbol)
        cache.put(cache_key, price, currency)
        return {
            "symbol": symbol,
            "price": float(price),
            "currency": currency,
            "source": "live",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.warning("Live price fetch failed for %s (%s): %s", symbol, asset_type, exc)

    # 3. Fallback to last known price in DB
    fallback = await _last_known_price(db, symbol)
    if fallback is not None:
        return {
            "symbol": symbol,
            "price": float(fallback.price),
            "currency": fallback.currency,
            "source": "last_known",
            "fetched_at": fallback.recorded_at.isoformat(),
        }

    return {
        "symbol": symbol,
        "price": None,
        "currency": None,
        "source": "unavailable",
        "fetched_at": None,
    }


async def refresh_user_assets(
    db: AsyncSession,
    user_id: UUID,
    *,
    use_cache: bool = False,
) -> list[dict]:
    """Refresh prices for all auto-fetchable assets of a user.

    Returns a list of per-asset result dicts.
    """
    result = await db.execute(
        select(Asset)
        .where(Asset.user_id == user_id, Asset.asset_type.in_([t.value for t in _AUTO_TYPES]))
        .where(Asset.symbol.isnot(None))
    )
    assets = list(result.scalars().all())

    results = []
    for asset in assets:
        outcome = await _refresh_single(db, asset, use_cache=use_cache)
        results.append(outcome)

    # Commit all updates in one go
    await db.commit()
    return results


async def refresh_single_asset(db: AsyncSession, asset: Asset) -> dict:
    """Fetch and update price for a single asset, then commit.

    Returns a result dict with ``status`` of ``"updated"`` or ``"failed"``.
    Safe to call right after creating or updating an asset.
    """
    result = await _refresh_single(db, asset)
    if result["status"] == "updated":
        await db.commit()
        await db.refresh(asset)
    return result


async def _refresh_single(
    db: AsyncSession,
    asset: Asset,
    *,
    use_cache: bool = True,
) -> dict:
    """Try to fetch a fresh price for a single asset, update it, and log history."""
    cache_key = f"{asset.asset_type.value}:{asset.symbol}".upper()

    try:
        # Check cache first
        cached = cache.get(cache_key) if use_cache else None
        if cached is not None:
            price, currency = cached.price, cached.currency
        else:
            price, currency = await fetch_price(asset.asset_type.value, asset.symbol)
            cache.put(cache_key, price, currency)

        # Update asset row
        asset.current_price = price
        asset.current_price_currency = currency
        asset.is_manual_price = False

        # Record in price_history
        db.add(PriceHistory(
            asset_id=asset.id,
            price=price,
            currency=currency,
        ))

        # If this is a FUND and has no prior history, seed up to 30 days of past prices
        if asset.asset_type == AssetType.FUND and asset.symbol:
            existing_count = await db.execute(
                select(PriceHistory.id).where(PriceHistory.asset_id == asset.id).limit(2)
            )
            if len(existing_count.scalars().all()) <= 1:
                try:
                    from app.providers import get_fund_provider
                    provider = get_fund_provider()
                    history_points = await provider.get_fund_history(asset.symbol, days=30)
                    for pt in history_points:
                        pt_date = datetime.strptime(pt["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                        db.add(PriceHistory(
                            asset_id=asset.id,
                            price=pt["price"],
                            currency=pt["currency"],
                            recorded_at=pt_date,
                        ))
                except Exception as hist_exc:
                    logger.debug("Could not seed history for fund %s: %s", asset.symbol, hist_exc)

        return {
            "asset_id": str(asset.id),
            "symbol": asset.symbol,
            "status": "updated",
            "price": float(price),
            "currency": currency,
        }
    except Exception as exc:
        logger.warning("Price refresh failed for %s: %s", asset.symbol, exc)
        return {
            "asset_id": str(asset.id),
            "symbol": asset.symbol,
            "status": "failed",
            "error": str(exc),
        }


async def get_price_history(
    db: AsyncSession,
    asset_id: UUID,
    limit: int = 90,
) -> list[PriceHistory]:
    """Return the most recent *limit* price history rows for an asset."""
    result = await db.execute(
        select(PriceHistory)
        .where(PriceHistory.asset_id == asset_id)
        .order_by(PriceHistory.recorded_at.desc())
        .limit(limit)
    )
    rows = list(result.scalars().all())
    rows.reverse()  # Return in chronological order
    return rows


async def _last_known_price(
    db: AsyncSession, symbol: str
) -> Optional[PriceHistory]:
    """Look up the most recent PriceHistory row that matches *symbol* via asset."""
    result = await db.execute(
        select(PriceHistory)
        .join(Asset, PriceHistory.asset_id == Asset.id)
        .where(Asset.symbol == symbol)
        .order_by(PriceHistory.recorded_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
