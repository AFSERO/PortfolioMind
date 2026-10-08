"""REST endpoints for Investor Profile & Assessment.

Implements all contracts required for:
- Reading question definitions and sections
- Assessment lifecycle, answer saving, skipping
- Profile draft review, editing, and confirmation
- Current authoritative profile and version history
"""

from typing import Any, Dict, List
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.investor_profile import (
    AnswerResponse,
    AnswerSubmitRequest,
    AssessmentStateResponse,
    InvestorProfileDraftResponse,
    InvestorProfileResponse,
    InvestorProfileVersionSummary,
    ProfileConfirmRequest,
    QuestionDefinition,
    SectionDefinition,
)
from app.services.investor_profile.profile_service import InvestorProfileService
from app.services.investor_profile.questions import QUESTIONS, SECTIONS

router = APIRouter(prefix="/api/investor-profile", tags=["investor-profile"])


@router.get("/questions", response_model=Dict[str, Any])
async def get_questions():
    """Returns the catalog of assessment sections and question definitions."""
    return {
        "status": "success",
        "data": {
            "sections": [s.model_dump() for s in SECTIONS],
            "questions": [q.model_dump() for q in QUESTIONS],
        },
    }


@router.get("/assessment/current", response_model=Dict[str, Any])
async def get_current_assessment(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns the current draft assessment and all submitted answers."""
    asmt = await InvestorProfileService.get_or_create_assessment(db, current_user.id)
    from sqlalchemy import select
    from app.models.investor_profile import InvestorProfileAnswer
    ans_res = await db.execute(
        select(InvestorProfileAnswer)
        .where(
            InvestorProfileAnswer.assessment_id == asmt.id,
            InvestorProfileAnswer.user_id == current_user.id,
        )
        .order_by(InvestorProfileAnswer.answered_at.asc())
    )
    answers = [AnswerResponse.model_validate(a) for a in ans_res.scalars().all()]
    state = AssessmentStateResponse(

        id=asmt.id,
        user_id=asmt.user_id,
        status=asmt.status,
        questionnaire_version=asmt.questionnaire_version,
        resume_question_id=asmt.resume_question_id,
        answers=answers,
        created_at=asmt.created_at,
        updated_at=asmt.updated_at,
    )
    return {"status": "success", "data": state.model_dump(mode="json")}


@router.post("/assessment/answer", response_model=Dict[str, Any])
async def save_answer(
    req: AnswerSubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Saves or updates an answer to a question in the current assessment."""
    ans = await InvestorProfileService.save_answer(db, current_user.id, req)
    return {"status": "success", "data": AnswerResponse.model_validate(ans).model_dump(mode="json")}


@router.post("/assessment/skip-question", response_model=Dict[str, Any])
async def skip_question(
    question_id: str,
    item_id: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Records an explicit SKIPPED state for a question."""
    ans = await InvestorProfileService.skip_question(db, current_user.id, question_id, item_id)
    return {"status": "success", "data": AnswerResponse.model_validate(ans).model_dump(mode="json")}


@router.get("/draft", response_model=Dict[str, Any])
async def get_profile_draft(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns the active structured profile draft with review issues and readiness."""
    draft = await InvestorProfileService.get_draft(db, current_user.id)
    if not draft or not draft.draft_data:
        draft = await InvestorProfileService.build_or_update_draft(db, current_user.id)

    resp = {
        "id": str(draft.id),
        "user_id": str(draft.user_id),
        "assessment_id": str(draft.assessment_id) if draft.assessment_id else None,
        "base_version_id": str(draft.base_version_id) if draft.base_version_id else None,
        **draft.draft_data,
        "created_at": draft.created_at.isoformat(),
        "updated_at": draft.updated_at.isoformat(),
    }
    return {"status": "success", "data": resp}


@router.put("/draft", response_model=Dict[str, Any])
async def update_profile_draft(
    updated_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Directly edits draft fields during review before confirmation."""
    draft = await InvestorProfileService.update_draft(db, current_user.id, updated_data)
    resp = {
        "id": str(draft.id),
        "user_id": str(draft.user_id),
        "assessment_id": str(draft.assessment_id) if draft.assessment_id else None,
        "base_version_id": str(draft.base_version_id) if draft.base_version_id else None,
        **draft.draft_data,
        "created_at": draft.created_at.isoformat(),
        "updated_at": draft.updated_at.isoformat(),
    }
    return {"status": "success", "data": resp}


@router.post("/confirm", response_model=Dict[str, Any])
async def confirm_profile(
    req: ProfileConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Confirms the active draft into an immutable material version (v1, v2, ...)."""
    version = await InvestorProfileService.confirm_profile(db, current_user.id, req)
    return {
        "status": "success",
        "data": {
            "version_id": str(version.id),
            "version_number": version.version_number,
            "change_reason": version.change_reason,
            "change_source": version.change_source,
            "confirmed_at": version.confirmed_at.isoformat(),
            "snapshot": version.snapshot,
        },
    }


@router.get("/current", response_model=Dict[str, Any])
async def get_current_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetches the user's active confirmed profile, completeness, and readiness."""
    profile_data = await InvestorProfileService.get_current_profile(db, current_user.id)
    return {"status": "success", "data": profile_data}


@router.get("/versions", response_model=Dict[str, Any])
async def get_version_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns the immutable version history of the user's profile."""
    versions = await InvestorProfileService.get_version_history(db, current_user.id)
    summaries = [
        InvestorProfileVersionSummary(
            id=v.id,
            version_number=v.version_number,
            change_reason=v.change_reason,
            change_source=v.change_source,
            confirmed_at=v.confirmed_at,
        ).model_dump(mode="json")
        for v in versions
    ]
    return {"status": "success", "data": summaries}


@router.get("/versions/{version_id}", response_model=Dict[str, Any])
async def get_version_detail(
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns details and full snapshot of a specific historical version."""
    version = await InvestorProfileService.get_version_detail(db, current_user.id, version_id)
    if not version:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile version not found.")

    return {
        "status": "success",
        "data": {
            "id": str(version.id),
            "version_number": version.version_number,
            "previous_version_id": str(version.previous_version_id) if version.previous_version_id else None,
            "change_reason": version.change_reason,
            "change_source": version.change_source,
            "snapshot": version.snapshot,
            "confirmed_at": version.confirmed_at.isoformat(),
        },
    }


@router.patch("/update", response_model=Dict[str, Any])
async def update_profile(
    changes: Dict[str, Any],
    reason: str = "User settings update",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Updates profile fields and increments material version with audit."""
    new_version = await InvestorProfileService.apply_profile_update(
        db=db,
        user_id=current_user.id,
        changes=changes,
        reason=reason,
        source="SETTINGS",
    )
    return {
        "status": "success",
        "data": {
            "version_number": new_version.version_number,
            "confirmed_at": new_version.confirmed_at.isoformat(),
            "snapshot": new_version.snapshot,
        },
    }
