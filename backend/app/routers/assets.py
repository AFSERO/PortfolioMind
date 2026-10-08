import uuid
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.asset import AssetType
from app.models.user import User
from app.schemas.asset import (
    AssetCreateRequest,
    AssetPriceUpdateRequest,
    AssetResponse,
    AssetUpdateRequest,
)
from app.schemas.transaction import (
    TransactionCreateRequest,
    TransactionResponse,
)
from app.services import asset as asset_service
from app.services import price as price_service
from app.services import transaction as tx_service
from app.services.transaction import NegativeHoldingsError

router = APIRouter()


@router.get("")
async def list_assets(
    asset_type: Optional[AssetType] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    pairs = await asset_service.list_assets_with_stats(db, current_user.id, asset_type)
    return {
        "status": "success",
        "data": [
            AssetResponse.from_asset(a, s).model_dump(mode="json") for a, s in pairs
        ],
    }


@router.post("", status_code=201)
async def create_asset(
    body: AssetCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        asset, stats, warning = await asset_service.create_asset(
            db, current_user.id, body
        )
    except NegativeHoldingsError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    resp: dict = {
        "status": "success",
        "data": AssetResponse.from_asset(asset, stats).model_dump(mode="json"),
    }
    if warning:
        resp["warning"] = warning
    return resp


@router.get("/{asset_id}")
async def get_asset(
    asset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    pair = await asset_service.get_asset_with_stats(db, asset_id, current_user.id)
    if pair is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset, stats = pair
    return {
        "status": "success",
        "data": AssetResponse.from_asset(asset, stats).model_dump(mode="json"),
    }


@router.put("/{asset_id}")
async def update_asset(
    asset_id: uuid.UUID,
    body: AssetUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    asset = await asset_service.get_asset(db, asset_id, current_user.id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    updated, stats, warning = await asset_service.update_asset(db, asset, body)
    resp: dict = {
        "status": "success",
        "data": AssetResponse.from_asset(updated, stats).model_dump(mode="json"),
    }
    if warning:
        resp["warning"] = warning
    return resp


@router.delete("/{asset_id}")
async def delete_asset(
    asset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    asset = await asset_service.get_asset(db, asset_id, current_user.id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    await asset_service.delete_asset(db, asset)
    return {"status": "success", "data": {"message": "Asset deleted"}}


@router.get("/{asset_id}/price-history")
async def get_price_history(
    asset_id: uuid.UUID,
    limit: int = 90,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    asset = await asset_service.get_asset(db, asset_id, current_user.id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    history = await price_service.get_price_history(db, asset_id, limit)
    return {
        "status": "success",
        "data": [
            {
                "id": str(h.id),
                "asset_id": str(h.asset_id),
                "price": float(h.price),
                "currency": h.currency,
                "recorded_at": h.recorded_at.isoformat(),
            }
            for h in history
        ],
    }


@router.post("/{asset_id}/update-price")
async def update_asset_price(
    asset_id: uuid.UUID,
    body: AssetPriceUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    asset = await asset_service.get_asset(db, asset_id, current_user.id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    updated, stats = await asset_service.update_asset_price(db, asset, body)
    return {
        "status": "success",
        "data": AssetResponse.from_asset(updated, stats).model_dump(mode="json"),
    }


# ── Transactions nested under an asset ────────────────────────────────────────


@router.post("/{asset_id}/transactions", status_code=201)
async def create_transaction(
    asset_id: uuid.UUID,
    body: TransactionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    asset = await asset_service.get_asset(db, asset_id, current_user.id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    try:
        tx = await tx_service.create_transaction(
            db, asset_id, body, user_id=current_user.id
        )
    except NegativeHoldingsError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    return {
        "status": "success",
        "data": TransactionResponse.model_validate(tx).model_dump(mode="json"),
    }


@router.get("/{asset_id}/transactions")
async def list_transactions(
    asset_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    asset = await asset_service.get_asset(db, asset_id, current_user.id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    txns = await tx_service.list_transactions(db, asset_id)
    return {
        "status": "success",
        "data": [
            TransactionResponse.model_validate(t).model_dump(mode="json")
            for t in txns
        ],
    }


class AssetResearchRequest(BaseModel):
    protocol: Optional[str] = "deep-research"


@router.post("/{asset_id}/research")
async def execute_asset_research(
    asset_id: uuid.UUID,
    body: Optional[AssetResearchRequest] = Body(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Execute on-demand Deep Research directly for a user's asset holding."""
    from app.services import formal_review as formal_review_service
    from app.services import instrument as instrument_service

    asset = await asset_service.get_asset(db, asset_id, current_user.id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")

    if not asset.instrument_id:
        inst = await instrument_service.find_or_create_instrument(
            db,
            asset_type=asset.asset_type,
            name=asset.name,
            symbol=asset.symbol,
            currency=asset.current_price_currency,
        )
        asset.instrument_id = inst.id
        await db.commit()
        await db.refresh(asset)

    protocol_name = body.protocol if body and body.protocol else "deep-research"
    result = await formal_review_service.execute_instrument_formal_review(
        db=db,
        instrument_id=asset.instrument_id,
        protocol_name=protocol_name,
        user_id=current_user.id,
    )
    return {
        "status": "success",
        "data": result,
    }

