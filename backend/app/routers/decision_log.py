"""API router for Decision Log."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.decision_log import DecisionEventType
from app.models.user import User
from app.schemas.decision_log import (
    DecisionLogCreate,
    DecisionLogListResponse,
    DecisionLogResponse,
    DecisionLogUpdateRationale,
)
from app.services import decision_log as decision_service

router = APIRouter()


@router.get("", response_model=None)
async def list_decisions(
    instrument_id: Optional[uuid.UUID] = None,
    asset_id: Optional[uuid.UUID] = None,
    event_type: Optional[DecisionEventType] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List decision log entries with optional filters and pagination."""
    items, total = await decision_service.get_decision_log_entries(
        db=db,
        user_id=current_user.id,
        instrument_id=instrument_id,
        asset_id=asset_id,
        event_type=event_type,
        limit=limit,
        offset=offset,
    )
    return {
        "status": "success",
        "data": {
            "items": [item.model_dump(mode="json") for item in items],
            "total": total,
        },
    }


@router.post("", status_code=status.HTTP_201_CREATED, response_model=None)
async def create_decision(
    payload: DecisionLogCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Manually record a decision or note."""
    entry = await decision_service.create_decision_log_entry(
        db=db,
        user_id=current_user.id,
        payload=payload,
    )
    return {
        "status": "success",
        "data": entry.model_dump(mode="json"),
    }


@router.get("/{decision_id}", response_model=None)
async def get_decision(
    decision_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Retrieve a specific decision log entry."""
    entry = await decision_service.get_decision_log_entry(
        db=db,
        user_id=current_user.id,
        entry_id=decision_id,
    )
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision log entry not found",
        )
    return {
        "status": "success",
        "data": entry.model_dump(mode="json"),
    }


@router.patch("/{decision_id}/rationale", response_model=None)
async def update_rationale(
    decision_id: uuid.UUID,
    payload: DecisionLogUpdateRationale,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Edit user rationale, confidence, or expectation on an existing decision."""
    entry = await decision_service.update_user_rationale(
        db=db,
        user_id=current_user.id,
        entry_id=decision_id,
        payload=payload,
    )
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision log entry not found",
        )
    return {
        "status": "success",
        "data": entry.model_dump(mode="json"),
    }
