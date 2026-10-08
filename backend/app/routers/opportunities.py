"""API router for Opportunity Evaluation and suggested formal research actions."""

from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.opportunity import OpportunityStatus
from app.models.user import User
from app.schemas.opportunity import (
    OpportunityAssessmentResponse,
    OpportunityEvaluationRequest,
    OpportunityEvaluationSummary,
)
from app.services import formal_review as formal_review_service
from app.services import opportunity as opportunity_service

router = APIRouter()


class LaunchReviewRequest(BaseModel):
    protocol: Optional[str] = None


@router.get("/active")
async def get_active_opportunities(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return watchlist candidates with active opportunity status (RESEARCH_NOW or RESEARCH_SOON)."""
    items = await opportunity_service.get_user_watchlist(db, current_user.id)
    active = [
        w for w in items
        if w.opportunity and w.opportunity.status in (OpportunityStatus.RESEARCH_NOW, OpportunityStatus.RESEARCH_SOON)
    ]
    return {
        "status": "success",
        "data": [w.model_dump(mode="json") for w in active],
    }


@router.post("/evaluate")
async def evaluate_opportunities(
    body: Optional[OpportunityEvaluationRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Evaluate opportunities across eligible watchlist and research candidates for the current user."""
    instrument_id = body.instrument_id if body else None
    force_refresh = body.force_refresh if body else False

    summary = await opportunity_service.evaluate_user_opportunities(
        db=db,
        user_id=current_user.id,
        instrument_id=instrument_id,
        force_refresh=force_refresh,
    )
    return {
        "status": "success",
        "data": summary.model_dump(mode="json"),
    }


@router.post("/{instrument_id}/launch-review")
async def launch_suggested_formal_review(
    instrument_id: uuid.UUID,
    body: Optional[LaunchReviewRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger the formal Finance review protocol suggested by the opportunity assessment."""
    protocol_name = body.protocol if body and body.protocol else "preliminary-screening"
    result = await formal_review_service.execute_instrument_formal_review(
        db=db,
        instrument_id=instrument_id,
        protocol_name=protocol_name,
        user_id=current_user.id,
    )
    return {
        "status": "success",
        "data": result,
    }
