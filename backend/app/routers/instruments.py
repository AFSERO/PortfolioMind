import uuid
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_bridge_user, get_current_user
from app.models.asset import AssetType
from app.models.user import User
from app.schemas.instrument import InstrumentCreateRequest, InstrumentResponse
from app.services import instrument as instrument_service

router = APIRouter()


@router.post("", status_code=201)
async def create_instrument(
    body: InstrumentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create or find a canonical investment instrument."""
    inst = await instrument_service.find_or_create_instrument(
        db,
        asset_type=body.asset_type,
        name=body.name,
        symbol=body.symbol,
        exchange=body.exchange,
        currency=body.currency,
        country=body.country,
        isin=body.isin,
        provider=body.provider,
        provider_id=body.provider_id,
    )
    await db.commit()
    await db.refresh(inst)
    return {
        "status": "success",
        "data": InstrumentResponse.model_validate(inst).model_dump(mode="json"),
    }


@router.get("")
async def list_instruments(
    q: Optional[str] = Query(None, description="Search term for symbol, name, or ISIN"),
    asset_type: Optional[AssetType] = Query(None, description="Filter by asset type"),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_bridge_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List or search investment instruments."""
    instruments = await instrument_service.list_instruments(
        db, q=q, asset_type=asset_type, limit=limit
    )
    return {
        "status": "success",
        "data": [
            InstrumentResponse.model_validate(inst).model_dump(mode="json")
            for inst in instruments
        ],
    }


@router.get("/{instrument_id}")
async def get_instrument(
    instrument_id: uuid.UUID,
    current_user: User = Depends(get_bridge_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Retrieve details for a specific investment instrument."""
    inst = await instrument_service.get_instrument(db, instrument_id)
    if inst is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return {
        "status": "success",
        "data": InstrumentResponse.model_validate(inst).model_dump(mode="json"),
    }


class ExecuteResearchRequest(BaseModel):
    protocol: Optional[str] = "deep-research"


@router.post("/{instrument_id}/research")
async def execute_instrument_research(
    instrument_id: uuid.UUID,
    body: Optional[ExecuteResearchRequest] = Body(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger on-demand Deep Research / formal protocol review for an instrument."""
    from app.services import formal_review as formal_review_service

    protocol_name = body.protocol if body and body.protocol else "deep-research"
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

