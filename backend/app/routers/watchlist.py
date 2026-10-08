"""API router for Watchlist candidates and research pipeline tracking."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.opportunity import (
    WatchlistItemCreateRequest,
    WatchlistItemResponse,
    WatchlistItemUpdateRequest,
)
from app.services import opportunity as opportunity_service

router = APIRouter()


@router.get("")
async def list_watchlist(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List all watchlist candidates tracked by the current user."""
    items = await opportunity_service.get_watchlist_items(db, current_user.id)
    return {
        "status": "success",
        "data": [item.model_dump(mode="json") for item in items],
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(
    body: WatchlistItemCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Add a new candidate or track an existing instrument on the user's watchlist."""
    try:
        item = await opportunity_service.upsert_watchlist_item(
            db, current_user.id, body
        )
        return {
            "status": "success",
            "data": item.model_dump(mode="json"),
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put("/{item_id}")
async def update_watchlist(
    item_id: uuid.UUID,
    body: WatchlistItemUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update metadata, target entry range, or stage of a watchlist candidate."""
    item = await opportunity_service.update_watchlist_item(
        db, current_user.id, item_id, body
    )
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist item not found",
        )
    return {
        "status": "success",
        "data": item.model_dump(mode="json"),
    }


@router.delete("/{item_id}")
async def remove_from_watchlist(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Remove an instrument from the user's watchlist."""
    success = await opportunity_service.delete_watchlist_item(
        db, current_user.id, item_id
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist item not found",
        )
    return {
        "status": "success",
        "data": {"deleted": True, "id": str(item_id)},
    }
