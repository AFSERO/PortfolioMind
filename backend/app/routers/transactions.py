import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.transaction import TransactionResponse, TransactionUpdateRequest
from app.services import transaction as tx_service
from app.services.transaction import NegativeHoldingsError

router = APIRouter()


@router.put("/{tx_id}")
async def update_transaction(
    tx_id: uuid.UUID,
    body: TransactionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    tx = await tx_service.get_transaction(db, tx_id, current_user.id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    try:
        updated = await tx_service.update_transaction(
            db, tx, body, user_id=current_user.id
        )
    except NegativeHoldingsError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    return {
        "status": "success",
        "data": TransactionResponse.model_validate(updated).model_dump(mode="json"),
    }


@router.delete("/{tx_id}")
async def delete_transaction(
    tx_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    tx = await tx_service.get_transaction(db, tx_id, current_user.id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    try:
        await tx_service.delete_transaction(db, tx, user_id=current_user.id)
    except NegativeHoldingsError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    return {"status": "success", "data": {"message": "Transaction deleted"}}
