from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.services import dashboard as dashboard_service

router = APIRouter()


@router.get("/summary")
async def get_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Total portfolio value, P/L, and allocation data."""
    data = await dashboard_service.get_summary(
        db, current_user.id, current_user.base_currency
    )
    return {"status": "success", "data": data}


@router.get("/timeline")
async def get_timeline(
    days: int = Query(default=90, ge=1, le=1825),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Portfolio value over time (for line chart)."""
    data = await dashboard_service.get_timeline(db, current_user.id, days)
    return {"status": "success", "data": data}


@router.get("/allocation")
async def get_allocation(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Allocation breakdown by asset type and individual asset."""
    data = await dashboard_service.get_allocation(
        db, current_user.id, current_user.base_currency
    )
    return {"status": "success", "data": data}


@router.post("/snapshot")
async def create_snapshot(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create or replace today's portfolio snapshot."""
    result = await dashboard_service.create_daily_snapshot(db, current_user.id)
    if result is None:
        return {"status": "success", "data": {"message": "No assets to snapshot"}}
    snapshot, exchange_rates = result
    return {
        "status": "success",
        "data": {
            "snapshot_date": snapshot.snapshot_date.isoformat(),
            "total_value_try": float(snapshot.total_value_try),
            "total_value_usd": float(snapshot.total_value_usd),
            "total_assets_try": float(snapshot.total_assets_try),
            "total_assets_usd": float(snapshot.total_assets_usd),
            "total_liabilities_try": float(snapshot.total_liabilities_try),
            "total_liabilities_usd": float(snapshot.total_liabilities_usd),
            "net_worth_try": float(snapshot.net_worth_try),
            "net_worth_usd": float(snapshot.net_worth_usd),
            "exchange_rates": exchange_rates,
        },
    }
