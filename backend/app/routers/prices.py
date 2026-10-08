from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.services import price as price_service
from app.services import forex_cache

router = APIRouter()


@router.get("/live/{symbol}")
async def get_live_price(
    symbol: str,
    asset_type: str = Query(
        ..., description="One of STOCK, FOREX, PRECIOUS_METALS, CRYPTO, FUND"
    ),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the current market price for a symbol.

    Requires ``asset_type`` query param so the correct fetcher is used.
    Example: ``GET /api/prices/live/BTC?asset_type=CRYPTO``
    """
    data = await price_service.get_live_price(db, symbol, asset_type)
    return {"status": "success", "data": data}


@router.post("/refresh")
async def refresh_prices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Refresh current prices for all auto-fetchable assets of the authenticated user."""
    results = await price_service.refresh_user_assets(db, current_user.id)
    return {"status": "success", "data": results}


@router.get("/forex-rates")
async def get_forex_rates(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return current exchange rates for standard currency pairs.

    Rates are sourced from (in priority order):
    1. In-memory cache (5-min TTL)
    2. Database cache  (24-h TTL)
    3. Live ExchangeRate-API (result saved to DB + memory cache)

    No authentication required — safe to call from the frontend on page load.
    Returns a flat dict: ``{"USD/TRY": 44.5, "EUR/TRY": 48.2, ...}``
    """
    rates = await forex_cache.get_all_current_rates(db)
    return {"status": "success", "data": rates}


@router.post("/forex-rates/refresh")
async def refresh_forex_rates(
    current_user: User = Depends(get_current_user),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Force-refresh all standard forex rates from ExchangeRate-API and persist to DB.

    Requires authentication.  Useful for scheduled jobs or manual cache invalidation.
    """
    results = await forex_cache.refresh_all_rates(db)
    return {"status": "success", "data": results}
