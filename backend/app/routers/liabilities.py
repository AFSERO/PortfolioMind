import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.liability import (
    LiabilityCreateRequest,
    LiabilityResponse,
    LiabilityUpdateRequest,
)
from app.services import liability as liability_service


router = APIRouter()


def _response(liability) -> dict:
    return LiabilityResponse.model_validate(liability).model_dump(mode="json")


@router.get("")
async def list_liabilities(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    liabilities = await liability_service.list_liabilities(db, current_user.id)
    return {"status": "success", "data": [_response(item) for item in liabilities]}


@router.post("", status_code=201)
async def create_liability(
    body: LiabilityCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    liability = await liability_service.create_liability(db, current_user.id, body)
    return {"status": "success", "data": _response(liability)}


@router.get("/{liability_id}")
async def get_liability(
    liability_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    liability = await liability_service.get_liability(
        db, liability_id, current_user.id
    )
    if liability is None:
        raise HTTPException(status_code=404, detail="Liability not found")
    return {"status": "success", "data": _response(liability)}


@router.put("/{liability_id}")
async def update_liability(
    liability_id: uuid.UUID,
    body: LiabilityUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    liability = await liability_service.update_liability(
        db, liability_id, current_user.id, body
    )
    if liability is None:
        raise HTTPException(status_code=404, detail="Liability not found")
    return {"status": "success", "data": _response(liability)}


@router.delete("/{liability_id}")
async def delete_liability(
    liability_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    deleted = await liability_service.delete_liability(
        db, liability_id, current_user.id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Liability not found")
    return {"status": "success", "data": {"message": "Liability deleted"}}

