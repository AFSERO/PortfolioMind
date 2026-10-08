"""API router for Investment Intelligence state, reviews, and technical plans."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_bridge_user
from app.models.user import User
from app.schemas.intelligence import (
    IntelligenceReviewCreateRequest,
    IntelligenceReviewResponse,
    IntelligenceStateResponse,
    IntelligenceStateUpsertRequest,
    TechnicalPlanCreateRequest,
    TechnicalPlanResponse,
)
from app.services import instrument as instrument_service
from app.services import intelligence as intelligence_service

router = APIRouter()


async def _require_instrument(db: AsyncSession, instrument_id: uuid.UUID):
    inst = await instrument_service.get_instrument(db, instrument_id)
    if inst is None:
        raise HTTPException(status_code=404, detail="Instrument not found")
    return inst


# ── Current Intelligence State ───────────────────────────────────────────────


@router.get("/{instrument_id}/intelligence")
async def get_intelligence_state(
    instrument_id: uuid.UUID,
    current_user: User = Depends(get_bridge_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Retrieve the current Investment Intelligence state for an instrument."""
    await _require_instrument(db, instrument_id)
    state = await intelligence_service.get_intelligence_state(db, instrument_id)
    if state is None:
        return {"status": "success", "data": None}

    state_data = IntelligenceStateResponse.model_validate(state).model_dump(mode="json")
    reviews = await intelligence_service.list_reviews(db, instrument_id, limit=1)
    if reviews:
        latest_rev = reviews[0]
        mr = latest_rev.machine_record or {}
        if not state_data.get("confidence"):
            state_data["confidence"] = latest_rev.confidence or (
                f"{mr['confidence_score']}%" if "confidence_score" in mr else (
                    f"{mr['confidence']}%" if "confidence" in mr and isinstance(mr["confidence"], (int, float)) and mr["confidence"] > 1 else str(mr.get("confidence") or "")
                )
            ) or None
        if state_data.get("confidence_score") is None:
            state_data["confidence_score"] = mr.get("confidence_score") or (
                mr.get("confidence") if isinstance(mr.get("confidence"), int) else None
            )
        if not state_data.get("confidence_level"):
            state_data["confidence_level"] = mr.get("confidence_level")
        if not state_data.get("execution_status"):
            state_data["execution_status"] = mr.get("execution_status")
        if not state_data.get("recovery_value_confidence"):
            state_data["recovery_value_confidence"] = mr.get("recovery_value_confidence")
        if not state_data.get("execution_confidence"):
            state_data["execution_confidence"] = mr.get("execution_confidence")
        if state_data.get("data_quality_score") is None:
            state_data["data_quality_score"] = mr.get("data_quality_score")
        if not state_data.get("primary_reason"):
            state_data["primary_reason"] = mr.get("primary_reason")
        if not state_data.get("supporting_reasons"):
            state_data["supporting_reasons"] = mr.get("supporting_reasons")
        if not state_data.get("key_risks"):
            state_data["key_risks"] = mr.get("key_risks")
        if not state_data.get("what_would_change_my_view"):
            state_data["what_would_change_my_view"] = mr.get("what_would_change_my_view")
        if not state_data.get("evidence_gaps"):
            state_data["evidence_gaps"] = mr.get("evidence_gaps")
        if not state_data.get("review_required_reason"):
            state_data["review_required_reason"] = mr.get("review_required_reason")
        if not state_data.get("assessment_type"):
            state_data["assessment_type"] = mr.get("assessment_type")
        if not state_data.get("asset_class_assessment"):
            state_data["asset_class_assessment"] = mr.get("asset_class_assessment")

    return {
        "status": "success",
        "data": state_data,
    }


@router.put("/{instrument_id}/intelligence")
async def upsert_intelligence_state(
    instrument_id: uuid.UUID,
    body: IntelligenceStateUpsertRequest,
    current_user: User = Depends(get_bridge_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Set or update the current Investment Intelligence state for an instrument."""
    await _require_instrument(db, instrument_id)
    state = await intelligence_service.upsert_intelligence_state(
        db, instrument_id, body
    )
    return {
        "status": "success",
        "data": IntelligenceStateResponse.model_validate(state).model_dump(mode="json"),
    }


# ── Intelligence Review History ───────────────────────────────────────────────


@router.get("/{instrument_id}/reviews")
@router.get("/{instrument_id}/intelligence/reviews")
async def list_intelligence_reviews(
    instrument_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_bridge_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List historical protocol review runs for an instrument."""
    await _require_instrument(db, instrument_id)
    reviews = await intelligence_service.list_reviews(db, instrument_id, limit=limit)
    return {
        "status": "success",
        "data": [
            IntelligenceReviewResponse.model_validate(r).model_dump(mode="json")
            for r in reviews
        ],
    }


@router.post("/{instrument_id}/reviews", status_code=201)
@router.post("/{instrument_id}/intelligence/reviews", status_code=201)
async def create_intelligence_review(
    instrument_id: uuid.UUID,
    body: IntelligenceReviewCreateRequest,
    current_user: User = Depends(get_bridge_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Record a protocol review run for an instrument."""
    await _require_instrument(db, instrument_id)
    review = await intelligence_service.create_review(
        db, instrument_id, body, user_id=current_user.id
    )
    review_data = IntelligenceReviewResponse.model_validate(review).model_dump(mode="json")
    review_data["state_updated"] = getattr(review, "state_updated", False)
    return {
        "status": "success",
        "data": review_data,
    }


# ── Technical Plan ────────────────────────────────────────────────────────────


@router.get("/{instrument_id}/technical-plan")
@router.get("/{instrument_id}/intelligence/technical-plan")
async def get_technical_plan(
    instrument_id: uuid.UUID,
    current_user: User = Depends(get_bridge_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Retrieve the active technical plan for an instrument."""
    await _require_instrument(db, instrument_id)
    plan = await intelligence_service.get_active_technical_plan(db, instrument_id)
    return {
        "status": "success",
        "data": (
            TechnicalPlanResponse.model_validate(plan).model_dump(mode="json")
            if plan is not None
            else None
        ),
    }


@router.put("/{instrument_id}/technical-plan")
@router.put("/{instrument_id}/intelligence/technical-plan")
async def upsert_technical_plan(
    instrument_id: uuid.UUID,
    body: TechnicalPlanCreateRequest,
    current_user: User = Depends(get_bridge_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create or update the active technical plan for an instrument."""
    await _require_instrument(db, instrument_id)
    plan = await intelligence_service.upsert_technical_plan(
        db, instrument_id, body, user_id=current_user.id
    )
    return {
        "status": "success",
        "data": TechnicalPlanResponse.model_validate(plan).model_dump(mode="json"),
    }
