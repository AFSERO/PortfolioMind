"""API router for Intelligence Briefing."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.briefing import (
    BriefingGenerateRequest,
    BriefingReviewActionRequest,
    BriefingReviewStatusResponse,
    BriefingRunResponse,
)
from app.services import briefing as briefing_service
from app.services import formal_review

router = APIRouter()


@router.get("/latest", response_model=None)
async def get_latest_briefing(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Retrieve the latest intelligence briefing run for the current user."""
    run = await briefing_service.get_latest_briefing_run(db, current_user.id)
    return {
        "status": "success",
        "data": run.model_dump(mode="json") if run is not None else None,
    }


@router.post("/generate", status_code=status.HTTP_200_OK, response_model=None)
async def generate_briefing(
    payload: BriefingGenerateRequest = BriefingGenerateRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """On-demand generation / refresh of the intelligence briefing."""
    run = await briefing_service.generate_briefing_run(
        db=db,
        user_id=current_user.id,
        scope=payload.scope,
        force_refresh=payload.force_refresh,
    )
    return {
        "status": "success",
        "data": run.model_dump(mode="json"),
    }


@router.get("/stats", response_model=None)
async def get_briefing_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get high-level briefing pulse counts for dashboard display."""
    latest = await briefing_service.get_latest_briefing_run(db, current_user.id)
    if not latest:
        return {
            "status": "success",
            "data": {
                "attention_count": 0,
                "items_shown": 0,
                "items_filtered": 0,
                "last_generated_at": None,
            },
        }

    attention_count = await briefing_service.get_briefing_attention_count(db, current_user.id)
    return {
        "status": "success",
        "data": {
            "attention_count": attention_count,
            "items_shown": latest.items_shown,
            "items_filtered": latest.items_filtered,
            "last_generated_at": latest.generated_at.isoformat(),
        },
    }


@router.post("/items/{briefing_item_id}/review", response_model=None)
async def trigger_briefing_item_review(
    briefing_item_id: UUID,
    payload: BriefingReviewActionRequest = BriefingReviewActionRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Execute or rerun a formal Finance review protocol triggered from a briefing item."""
    result = await formal_review.execute_briefing_formal_review(
        db=db,
        briefing_item_id=briefing_item_id,
        user_id=current_user.id,
        force_rerun=payload.force_rerun,
    )
    return {
        "status": "success",
        "data": result,
    }


@router.get("/items/{briefing_item_id}/review", response_model=None)
async def get_briefing_item_review_status(
    briefing_item_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the current formal review status and review record for a briefing item."""
    result = await formal_review.get_briefing_formal_review_status(
        db=db,
        briefing_item_id=briefing_item_id,
        user_id=current_user.id,
    )
    return {
        "status": "success",
        "data": result,
    }
