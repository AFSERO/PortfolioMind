"""Investor Profile Domain Service.

Coordinates:
- Assessment progress & answer persistence
- Profile draft generation & review queues
- Material version creation (v1, v2, ...) and audit
- Copilot integration and preference updates
"""

from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID
import uuid

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.investor_profile import (
    InvestorProfile,
    InvestorProfileAnswer,
    InvestorProfileAssessment,
    InvestorProfileDraft,
    InvestorProfileVersion,
)
from app.models.user import User
from app.schemas.investor_profile import (
    AnswerSubmitRequest,
    KnowledgeState,
    ProfileConfirmRequest,
)
from app.services.investor_profile.rules_engine import InvestorProfileRulesEngine

logger = logging.getLogger(__name__)


class InvestorProfileService:
    """Core domain service for user-scoped Investor Profile lifecycle."""

    @classmethod
    async def get_or_create_profile(
        cls, db: AsyncSession, user_id: UUID
    ) -> InvestorProfile:
        """Retrieves or creates the user's root InvestorProfile container."""
        stmt = (
            select(InvestorProfile)
            .where(InvestorProfile.user_id == user_id)
            .options(selectinload(InvestorProfile.versions))
        )
        res = await db.execute(stmt)
        profile = res.scalar_one_or_none()

        if not profile:
            profile = InvestorProfile(
                user_id=user_id,
                completeness_overall_pct=Decimal("0.00"),
                analysis_readiness={
                    "risk_analysis": "UNAVAILABLE",
                    "capacity_analysis": "UNAVAILABLE",
                    "target_allocation_analysis": "UNAVAILABLE",
                    "portfolio_fit": "UNAVAILABLE",
                    "liquidity_analysis": "UNAVAILABLE",
                    "copilot_support": "LIMITED",
                    "research_relevance": "UNAVAILABLE",
                },
            )
            db.add(profile)
            await db.commit()
            await db.refresh(profile)

        return profile

    @classmethod
    async def get_or_create_assessment(
        cls, db: AsyncSession, user_id: UUID
    ) -> InvestorProfileAssessment:
        """Retrieves the latest draft assessment or starts a new one."""
        stmt = (
            select(InvestorProfileAssessment)
            .where(
                InvestorProfileAssessment.user_id == user_id,
                InvestorProfileAssessment.status == "DRAFT",
            )
            .options(selectinload(InvestorProfileAssessment.answers))
            .order_by(desc(InvestorProfileAssessment.created_at))
        )
        res = await db.execute(stmt)
        assessment = res.scalar_one_or_none()

        if not assessment:
            profile = await cls.get_or_create_profile(db, user_id)
            assessment = InvestorProfileAssessment(
                user_id=user_id,
                base_version_id=profile.active_version_id,
                questionnaire_version="1.0",
                status="DRAFT",
                resume_question_id="C01",
            )
            db.add(assessment)
            await db.commit()
            await db.refresh(assessment)

        return assessment

    @classmethod
    async def save_answer(
        cls, db: AsyncSession, user_id: UUID, req: AnswerSubmitRequest
    ) -> InvestorProfileAnswer:
        """Saves or updates a raw user answer within the active assessment."""
        assessment = await cls.get_or_create_assessment(db, user_id)

        # Look for existing answer for this question and item_id
        stmt = select(InvestorProfileAnswer).where(
            InvestorProfileAnswer.assessment_id == assessment.id,
            InvestorProfileAnswer.user_id == user_id,
            InvestorProfileAnswer.question_id == req.question_id,
            InvestorProfileAnswer.item_id == req.item_id,
        )
        res = await db.execute(stmt)
        ans = res.scalar_one_or_none()

        if ans:
            ans.knowledge_state = (
                req.knowledge_state.value
                if hasattr(req.knowledge_state, "value")
                else str(req.knowledge_state)
            )
            ans.selected_options = req.selected_options
            ans.numeric_inputs = req.numeric_inputs
            ans.raw_text = req.raw_text
            ans.locale = req.locale
            ans.answered_at = datetime.now(timezone.utc)
        else:
            ans = InvestorProfileAnswer(
                assessment_id=assessment.id,
                user_id=user_id,
                question_id=req.question_id,
                item_id=req.item_id,
                knowledge_state=(
                    req.knowledge_state.value
                    if hasattr(req.knowledge_state, "value")
                    else str(req.knowledge_state)
                ),
                selected_options=req.selected_options,
                numeric_inputs=req.numeric_inputs,
                raw_text=req.raw_text,
                locale=req.locale,
                answered_at=datetime.now(timezone.utc),
            )
            db.add(ans)

        # Update resume_question_id
        assessment.resume_question_id = req.question_id
        assessment.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(ans)

        # Automatically update/refresh in-flight draft
        await cls.build_or_update_draft(db, user_id, assessment.id)

        return ans

    @classmethod
    async def skip_question(
        cls,
        db: AsyncSession,
        user_id: UUID,
        question_id: str,
        item_id: Optional[str] = None,
    ) -> InvestorProfileAnswer:
        """Records an explicit SKIPPED answer state."""
        return await cls.save_answer(
            db=db,
            user_id=user_id,
            req=AnswerSubmitRequest(
                question_id=question_id,
                item_id=item_id,
                knowledge_state=KnowledgeState.SKIPPED,
                selected_options=[],
                numeric_inputs={},
            ),
        )

    @classmethod
    async def build_or_update_draft(
        cls,
        db: AsyncSession,
        user_id: UUID,
        assessment_id: Optional[UUID] = None,
    ) -> InvestorProfileDraft:
        """Builds a structured profile draft from assessment answers and persists it."""
        profile = await cls.get_or_create_profile(db, user_id)

        if not assessment_id:
            assessment = await cls.get_or_create_assessment(db, user_id)
            assessment_id = assessment.id
        else:
            res = await db.execute(
                select(InvestorProfileAssessment)
                .where(
                    InvestorProfileAssessment.id == assessment_id,
                    InvestorProfileAssessment.user_id == user_id,
                )
                .options(selectinload(InvestorProfileAssessment.answers))
            )
            assessment = res.scalar_one_or_none()
            if not assessment:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Assessment not found.")

        # Aggregate raw answers
        ans_res = await db.execute(
            select(InvestorProfileAnswer).where(
                InvestorProfileAnswer.assessment_id == assessment_id,
                InvestorProfileAnswer.user_id == user_id,
            )
        )
        answers_list = ans_res.scalars().all()
        answers_map: Dict[str, Any] = {}
        for a in answers_list:
            answers_map[a.question_id] = {
                "selected_options": a.selected_options,
                "numeric_inputs": a.numeric_inputs,
                "raw_text": a.raw_text,
                "knowledge_state": a.knowledge_state,
            }

        # Run rules evaluation
        goals, risk, policy, prefs, issues, completeness, readiness = (
            InvestorProfileRulesEngine.evaluate(answers=answers_map)
        )

        draft_content = {
            "goals": goals.model_dump(mode="json"),
            "risk": risk.model_dump(mode="json"),
            "policy": policy.model_dump(mode="json"),
            "preferences": prefs.model_dump(mode="json"),
            "issues": [i.model_dump(mode="json") for i in issues],
            "completeness": completeness.model_dump(mode="json"),
            "readiness": readiness.model_dump(mode="json"),
        }

        # Find or create draft
        draft_res = await db.execute(
            select(InvestorProfileDraft).where(
                InvestorProfileDraft.user_id == user_id
            )
        )
        draft = draft_res.scalar_one_or_none()

        if draft:
            draft.assessment_id = assessment_id
            draft.base_version_id = profile.active_version_id
            draft.draft_data = draft_content
            draft.updated_at = datetime.now(timezone.utc)
        else:
            draft = InvestorProfileDraft(
                user_id=user_id,
                assessment_id=assessment_id,
                base_version_id=profile.active_version_id,
                draft_data=draft_content,
            )
            db.add(draft)

        await db.commit()
        await db.refresh(draft)
        return draft

    @classmethod
    async def get_draft(
        cls, db: AsyncSession, user_id: UUID
    ) -> Optional[InvestorProfileDraft]:
        """Fetches the user's active draft."""
        res = await db.execute(
            select(InvestorProfileDraft).where(
                InvestorProfileDraft.user_id == user_id
            )
        )
        return res.scalar_one_or_none()

    @classmethod
    async def update_draft(
        cls, db: AsyncSession, user_id: UUID, updated_data: Dict[str, Any]
    ) -> InvestorProfileDraft:
        """Allows direct user edits to draft fields before confirmation."""
        draft = await cls.get_draft(db, user_id)
        if not draft:
            draft = await cls.build_or_update_draft(db, user_id)

        current = dict(draft.draft_data or {})
        for section in ("goals", "risk", "policy", "preferences"):
            if section in updated_data and isinstance(updated_data[section], dict):
                current[section] = {
                    **current.get(section, {}),
                    **updated_data[section],
                }

        # Re-evaluate issues & completeness if key fields changed
        draft.draft_data = current
        draft.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(draft)
        return draft

    @classmethod
    async def confirm_profile(
        cls, db: AsyncSession, user_id: UUID, req: ProfileConfirmRequest
    ) -> InvestorProfileVersion:
        """Confirms the active draft into an immutable material version (v1, v2, ...)."""
        profile = await cls.get_or_create_profile(db, user_id)
        draft = await cls.get_draft(db, user_id)

        if not draft or not draft.draft_data:
            draft = await cls.build_or_update_draft(db, user_id)

        # Determine next version number
        stmt = (
            select(InvestorProfileVersion.version_number)
            .where(
                InvestorProfileVersion.profile_id == profile.id,
                InvestorProfileVersion.user_id == user_id,
            )
            .order_by(desc(InvestorProfileVersion.version_number))
            .limit(1)
        )
        latest_ver_num = (await db.execute(stmt)).scalar_one_or_none() or 0
        next_ver_num = latest_ver_num + 1

        now = datetime.now(timezone.utc)
        snapshot = dict(draft.draft_data)
        snapshot["version_number"] = next_ver_num
        snapshot["confirmed_at"] = now.isoformat()

        version = InvestorProfileVersion(
            profile_id=profile.id,
            user_id=user_id,
            version_number=next_ver_num,
            previous_version_id=profile.active_version_id,
            change_reason=req.change_reason or "Profile confirmed",
            change_source=req.change_source or "ONBOARDING",
            snapshot=snapshot,
            confirmed_by=user_id,
            confirmed_at=now,
        )
        db.add(version)
        await db.flush()

        # Update root InvestorProfile pointers
        profile.active_version_id = version.id
        completeness_pct = snapshot.get("completeness", {}).get("overall_pct", 0.0)
        profile.completeness_overall_pct = Decimal(str(completeness_pct))
        profile.analysis_readiness = snapshot.get("readiness", {})
        profile.updated_at = now

        # Update assessment status if linked
        if draft.assessment_id:
            asmt_res = await db.execute(
                select(InvestorProfileAssessment).where(
                    InvestorProfileAssessment.id == draft.assessment_id
                )
            )
            asmt = asmt_res.scalar_one_or_none()
            if asmt:
                asmt.status = "CONFIRMED"
                asmt.updated_at = now

        await db.commit()
        await db.refresh(version)
        return version

    @classmethod
    async def get_current_profile(
        cls, db: AsyncSession, user_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Returns the active authoritative confirmed profile snapshot and metadata."""
        profile = await cls.get_or_create_profile(db, user_id)
        if not profile.active_version_id:
            # Check if there is an in-flight draft to report completeness
            draft = await cls.get_draft(db, user_id)
            return {
                "id": str(profile.id),
                "user_id": str(user_id),
                "version_number": None,
                "active_version_id": None,
                "completeness_overall_pct": float(
                    draft.draft_data.get("completeness", {}).get("overall_pct", 0.0)
                )
                if draft
                else 0.0,
                "analysis_readiness": draft.draft_data.get("readiness", {})
                if draft
                else profile.analysis_readiness,
                "goals": draft.draft_data.get("goals", {}) if draft else {},
                "risk": draft.draft_data.get("risk", {}) if draft else {},
                "policy": draft.draft_data.get("policy", {}) if draft else {},
                "preferences": draft.draft_data.get("preferences", {})
                if draft
                else {},
                "issues": draft.draft_data.get("issues", []) if draft else [],
                "confirmed_at": None,
                "updated_at": profile.updated_at.isoformat(),
            }

        # Fetch active version
        res = await db.execute(
            select(InvestorProfileVersion).where(
                InvestorProfileVersion.id == profile.active_version_id,
                InvestorProfileVersion.user_id == user_id,
            )
        )
        ver = res.scalar_one_or_none()
        if not ver:
            return None

        snap = ver.snapshot or {}
        goals_data = dict(snap.get("goals", {}))
        if "investment_horizon" not in goals_data and snap.get("investment_horizon"):
            goals_data["investment_horizon"] = snap.get("investment_horizon")
        risk_data = dict(snap.get("risk", {}))
        if "risk_tolerance" not in risk_data and snap.get("risk_tolerance"):
            risk_data["risk_tolerance"] = snap.get("risk_tolerance")

        return {
            "id": str(profile.id),
            "user_id": str(user_id),
            "version_number": ver.version_number,
            "active_version_id": str(ver.id),
            "completeness_overall_pct": float(profile.completeness_overall_pct),
            "analysis_readiness": profile.analysis_readiness,
            "goals": goals_data,
            "risk": risk_data,
            "policy": snap.get("policy", {}),
            "preferences": snap.get("preferences", {}),
            "issues": snap.get("issues", []),
            "confirmed_at": ver.confirmed_at.isoformat(),
            "updated_at": profile.updated_at.isoformat(),
        }

    @classmethod
    async def get_version_history(
        cls, db: AsyncSession, user_id: UUID
    ) -> List[InvestorProfileVersion]:
        """Returns all confirmed material versions for the user."""
        res = await db.execute(
            select(InvestorProfileVersion)
            .where(InvestorProfileVersion.user_id == user_id)
            .order_by(desc(InvestorProfileVersion.version_number))
        )
        return list(res.scalars().all())

    @classmethod
    async def get_version_detail(
        cls, db: AsyncSession, user_id: UUID, version_id: UUID
    ) -> Optional[InvestorProfileVersion]:
        """Fetches a specific historical version ensuring user scoping."""
        res = await db.execute(
            select(InvestorProfileVersion).where(
                InvestorProfileVersion.id == version_id,
                InvestorProfileVersion.user_id == user_id,
            )
        )
        return res.scalar_one_or_none()

    @classmethod
    async def apply_profile_update(
        cls,
        db: AsyncSession,
        user_id: UUID,
        changes: Dict[str, Any],
        reason: str = "Settings update",
        source: str = "SETTINGS",
    ) -> InvestorProfileVersion:
        """Applies a confirmed profile update, creating the next material version."""
        current = await cls.get_current_profile(db, user_id)
        current_data = current or {}

        # Merge changes
        new_goals = {**current_data.get("goals", {}), **changes.get("goals", {})}
        new_risk = {**current_data.get("risk", {}), **changes.get("risk", {})}
        new_policy = {**current_data.get("policy", {}), **changes.get("policy", {})}
        new_prefs = {**current_data.get("preferences", {}), **changes.get("preferences", {})}

        draft_content = {
            "goals": new_goals,
            "risk": new_risk,
            "policy": new_policy,
            "preferences": new_prefs,
            "issues": current_data.get("issues", []),
            "completeness": current_data.get(
                "completeness",
                {"overall_pct": current_data.get("completeness_overall_pct", 75.0)},
            ),
            "readiness": current_data.get("analysis_readiness", {}),
        }

        # Update draft
        draft = await cls.get_draft(db, user_id)
        if not draft:
            draft = InvestorProfileDraft(user_id=user_id, draft_data=draft_content)
            db.add(draft)
        else:
            draft.draft_data = draft_content
        await db.commit()

        # Confirm to create new version
        return await cls.confirm_profile(
            db=db,
            user_id=user_id,
            req=ProfileConfirmRequest(change_reason=reason, change_source=source),
        )
