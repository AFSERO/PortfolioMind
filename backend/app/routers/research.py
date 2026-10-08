"""API router for Research Queue and Pipeline tracking."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.services import opportunity as opportunity_service

router = APIRouter()


@router.get("")
async def get_research_queue(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Retrieve the prioritized research queue and pipeline distribution for the current user."""
    queue = await opportunity_service.get_research_queue(db, current_user.id)
    return {
        "status": "success",
        "data": queue.model_dump(mode="json"),
    }
