"""Investment Intelligence service — manage instrument intelligence states, reviews, and plans."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import os
import sys
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession


def _is_authorized_test_environment() -> bool:
    """Determine if execution is occurring within an authorized automated test environment."""
    if "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ:
        return True
    if os.environ.get("ENVIRONMENT") in ("test", "testing"):
        return True
    if os.environ.get("TESTING") in ("1", "true", "True"):
        return True
    return False

from app.models.intelligence import (
    InstrumentIntelligenceState,
    IntelligenceReview,
    TechnicalPlan,
    ThesisStatus,
    ValuationStatus,
    TechnicalStatus,
    Recommendation,
)
from app.schemas.intelligence import (
    IntelligenceReviewCreateRequest,
    IntelligenceStateUpsertRequest,
    TechnicalPlanCreateRequest,
)


# ============================================================================
# Current Intelligence State
# ============================================================================


async def get_intelligence_state(
    db: AsyncSession, instrument_id: UUID
) -> Optional[InstrumentIntelligenceState]:
    """Fetch the latest intelligence state for an instrument."""
    stmt = select(InstrumentIntelligenceState).where(
        InstrumentIntelligenceState.instrument_id == instrument_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def upsert_intelligence_state(
    db: AsyncSession,
    instrument_id: UUID,
    data: IntelligenceStateUpsertRequest,
) -> InstrumentIntelligenceState:
    """Create or update the current intelligence state for an instrument."""
    state = await get_intelligence_state(db, instrument_id)
    update_data = data.model_dump(exclude_unset=True)

    if state is None:
        state = InstrumentIntelligenceState(
            instrument_id=instrument_id,
            **update_data,
        )
        db.add(state)
    else:
        for field, value in update_data.items():
            setattr(state, field, value)

    await db.commit()
    await db.refresh(state)
    return state


# ============================================================================
# Review History
# ============================================================================


async def list_reviews(
    db: AsyncSession, instrument_id: UUID, limit: int = 50
) -> list[IntelligenceReview]:
    """List historical protocol review runs for an instrument, newest first."""
    stmt = (
        select(IntelligenceReview)
        .where(IntelligenceReview.instrument_id == instrument_id)
        .order_by(IntelligenceReview.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# Alias for callers expecting get_reviews
get_reviews = list_reviews


async def create_review(
    db: AsyncSession,
    instrument_id: UUID,
    data: IntelligenceReviewCreateRequest,
    user_id: Optional[UUID] = None,
) -> IntelligenceReview:
    """Record a protocol review run.

    Optionally updates the current IntelligenceState if `auto_apply_state` is True.
    """
    # Idempotency check: if source_run_id is provided, check for existing review
    existing_review = None
    if data.source_run_id:
        stmt = select(IntelligenceReview).where(
            IntelligenceReview.instrument_id == instrument_id,
            IntelligenceReview.source_run_id == data.source_run_id,
        )
        res = await db.execute(stmt)
        existing_review = res.scalar_one_or_none()

    if existing_review is not None:
        # Idempotent re-sync: review already processed; do not re-apply state or duplicate decision logs
        existing_review.state_updated = False
        return existing_review

    if getattr(data, "is_synthetic", False) and not _is_authorized_test_environment():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Synthetic or mock reviews are strictly prohibited from mutating user intelligence state outside test environments.",
        )

    canonical_proto = (data.protocol or "").strip().lower().replace("_", "-")
    if (canonical_proto == "deep-research" or canonical_proto.startswith("deep-research-")) and data.machine_record:
        try:
            from investment_intelligence.validation import validate_deep_research_record
            validated_rec = validate_deep_research_record(
                data.machine_record,
                protocol_name=canonical_proto,
            )
            data.machine_record = validated_rec.to_dict()
            if not data.confidence:
                data.confidence = f"{validated_rec.confidence}%"
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Machine record semantic validation failed: {err}",
            )

    review = IntelligenceReview(
        instrument_id=instrument_id,
        protocol=data.protocol,
        run_type=data.run_type,
        status=data.status,
        machine_record=data.machine_record,
        human_brief=data.human_brief,
        confidence=data.confidence,
        research_path=data.research_path,
        source_run_id=data.source_run_id,
    )
    db.add(review)

    state_actually_changed = False
    if data.auto_apply_state and data.machine_record:
        # Step A: Authoritative before-state snapshot from persistent InstrumentIntelligenceState
        state = await get_intelligence_state(db, instrument_id)
        old_rec = state.recommendation if state else None
        old_thesis = state.thesis_status if state else None
        old_val = state.valuation_status if state else None
        old_tech = state.technical_status if state else None

        mr = data.machine_record

        # Extract compatible status enums if present in machine_record
        thesis_status = None
        if "thesis_status" in mr and mr["thesis_status"]:
            try:
                thesis_status = ThesisStatus(mr["thesis_status"])
            except ValueError:
                pass

        val_status = None
        if "valuation_status" in mr and mr["valuation_status"]:
            try:
                val_status = ValuationStatus(mr["valuation_status"])
            except ValueError:
                pass

        tech_status = None
        if "technical_status" in mr and mr["technical_status"]:
            try:
                tech_status = TechnicalStatus(mr["technical_status"])
            except ValueError:
                pass

        rec = None
        if "recommendation" in mr and mr["recommendation"]:
            try:
                rec = Recommendation(mr["recommendation"])
            except ValueError:
                pass

        now = datetime.now(timezone.utc)
        if state is None:
            # First-time intelligence state establishment
            state_actually_changed = True
            state = InstrumentIntelligenceState(
                instrument_id=instrument_id,
                thesis_status=thesis_status,
                valuation_status=val_status,
                technical_status=tech_status,
                recommendation=rec,
                last_review_at=now,
                human_brief=data.human_brief,
            )
            db.add(state)
        else:
            # Compare each dimension against authoritative before-state snapshot
            rec_changed = (rec is not None and rec != old_rec)
            thesis_changed = (thesis_status is not None and thesis_status != old_thesis)
            val_changed = (val_status is not None and val_status != old_val)
            tech_changed = (tech_status is not None and tech_status != old_tech)

            if rec_changed or thesis_changed or val_changed or tech_changed:
                state_actually_changed = True

            # Mutate state with new values (only for provided dimensions)
            if thesis_status is not None:
                state.thesis_status = thesis_status
            if val_status is not None:
                state.valuation_status = val_status
            if tech_status is not None:
                state.technical_status = tech_status
            if rec is not None:
                state.recommendation = rec
            if data.human_brief is not None:
                state.human_brief = data.human_brief
            state.last_review_at = now

        # Determine if a meaningful transition occurred to auto-log
        from app.models.decision_log import DecisionEventType

        trans: dict[str, Any] | None = None

        if state_actually_changed:
            if rec is not None and rec != old_rec:
                if old_rec is None:
                    summary_text = f"Initial recommendation established as {rec.value} via {data.protocol}"
                else:
                    summary_text = f"Recommendation changed from {old_rec.value} to {rec.value} via {data.protocol}"
                trans = {
                    "event_type": DecisionEventType.RECOMMENDATION_CHANGED,
                    "title": f"Recommendation updated to {rec.value}",
                    "summary": summary_text,
                    "previous_state": old_rec.value if old_rec else None,
                    "new_state": rec.value,
                }
            elif thesis_status is not None and thesis_status != old_thesis:
                if old_thesis is None:
                    summary_text = f"Initial thesis status established as {thesis_status.value} via {data.protocol}"
                else:
                    summary_text = f"Thesis changed from {old_thesis.value} to {thesis_status.value} via {data.protocol}"
                trans = {
                    "event_type": DecisionEventType.THESIS_CHANGED,
                    "title": f"Thesis status updated to {thesis_status.value}",
                    "summary": summary_text,
                    "previous_state": old_thesis.value if old_thesis else None,
                    "new_state": thesis_status.value,
                }
            elif val_status is not None and val_status != old_val:
                if old_val is None:
                    summary_text = f"Initial valuation established as {val_status.value} via {data.protocol}"
                else:
                    summary_text = f"Valuation changed from {old_val.value} to {val_status.value} via {data.protocol}"
                trans = {
                    "event_type": DecisionEventType.VALUATION_CHANGED,
                    "title": f"Valuation updated to {val_status.value}",
                    "summary": summary_text,
                    "previous_state": old_val.value if old_val else None,
                    "new_state": val_status.value,
                }
            elif tech_status is not None and tech_status != old_tech:
                if old_tech is None:
                    summary_text = f"Initial technical status established as {tech_status.value} via {data.protocol}"
                else:
                    summary_text = f"Technical status changed from {old_tech.value} to {tech_status.value} via {data.protocol}"
                trans = {
                    "event_type": DecisionEventType.TECHNICAL_PLAN_CHANGED,
                    "title": f"Technical status updated to {tech_status.value}",
                    "summary": summary_text,
                    "previous_state": old_tech.value if old_tech else None,
                    "new_state": tech_status.value,
                }

        if trans is not None:
            # Find users to notify
            target_user_ids: set[UUID] = set()
            if user_id is not None:
                target_user_ids.add(user_id)
            else:
                from app.models.asset import Asset
                holders_res = await db.execute(
                    select(Asset.user_id).where(Asset.instrument_id == instrument_id)
                )
                for uid in holders_res.scalars().all():
                    target_user_ids.add(uid)

            if target_user_ids:
                from app.services.decision_log import log_decision_event
                for uid in target_user_ids:
                    await log_decision_event(
                        db=db,
                        user_id=uid,
                        event_type=trans["event_type"],
                        title=trans["title"],
                        summary=trans["summary"],
                        instrument_id=instrument_id,
                        confidence=data.confidence,
                        expectation=data.human_brief,
                        related_review_id=review.id,
                        metadata={
                            "protocol": data.protocol,
                            "source_run_id": data.source_run_id,
                            "triggering_briefing_item_id": mr.get("triggering_briefing_item_id") if isinstance(mr, dict) else None,
                            "previous_state": trans["previous_state"],
                            "new_state": trans["new_state"],
                            "old_recommendation": old_rec.value if old_rec else None,
                            "new_recommendation": rec.value if rec else None,
                            "old_thesis": old_thesis.value if old_thesis else None,
                            "new_thesis": thesis_status.value if thesis_status else None,
                            "old_valuation": old_val.value if old_val else None,
                            "new_valuation": val_status.value if val_status else None,
                            "old_technical": old_tech.value if old_tech else None,
                            "new_technical": tech_status.value if tech_status else None,
                            "primary_reason": mr.get("primary_reason"),
                            "confidence_score": mr.get("confidence_score"),
                            "assessment_type": mr.get("assessment_type"),
                            "asset_class_assessment": mr.get("asset_class_assessment"),
                        },
                    )

    review.state_updated = state_actually_changed
    await db.commit()
    await db.refresh(review)
    review.state_updated = state_actually_changed
    return review


# ============================================================================
# Technical Plan
# ============================================================================


async def get_active_technical_plan(
    db: AsyncSession, instrument_id: UUID
) -> Optional[TechnicalPlan]:
    """Retrieve the currently active technical plan for an instrument."""
    stmt = (
        select(TechnicalPlan)
        .where(TechnicalPlan.instrument_id == instrument_id, TechnicalPlan.active.is_(True))
        .order_by(TechnicalPlan.reference_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def upsert_technical_plan(
    db: AsyncSession,
    instrument_id: UUID,
    data: TechnicalPlanCreateRequest,
    user_id: Optional[UUID] = None,
) -> TechnicalPlan:
    """Create a new technical plan. If active=True, deactivates previous plans."""
    if data.active:
        await db.execute(
            update(TechnicalPlan)
            .where(TechnicalPlan.instrument_id == instrument_id, TechnicalPlan.active.is_(True))
            .values(active=False)
        )

    plan = TechnicalPlan(
        instrument_id=instrument_id,
        reference_at=data.reference_at or datetime.now(timezone.utc),
        reference_price=data.reference_price,
        trend_expectation=data.trend_expectation,
        entry_zones=data.entry_zones,
        support_zones=data.support_zones,
        resistance_zones=data.resistance_zones,
        review_or_invalidation_zones=data.review_or_invalidation_zones,
        profit_taking_or_reassessment_zones=data.profit_taking_or_reassessment_zones,
        notes=data.notes,
        active=data.active,
    )
    db.add(plan)
    await db.flush()

    if data.active:
        target_user_ids: set[UUID] = set()
        if user_id is not None:
            target_user_ids.add(user_id)
        else:
            from app.models.asset import Asset
            holders_res = await db.execute(
                select(Asset.user_id).where(Asset.instrument_id == instrument_id)
            )
            for uid in holders_res.scalars().all():
                target_user_ids.add(uid)

        if target_user_ids:
            from app.models.decision_log import DecisionEventType
            from app.services.decision_log import log_decision_event
            for uid in target_user_ids:
                await log_decision_event(
                    db=db,
                    user_id=uid,
                    event_type=DecisionEventType.TECHNICAL_PLAN_CHANGED,
                    title="Technical plan updated",
                    summary=f"Trend expectation: {data.trend_expectation or 'Active plan configured'}. Reference price: {data.reference_price or 'N/A'}",
                    instrument_id=instrument_id,
                    expectation=data.trend_expectation,
                    metadata={
                        "reference_price": str(data.reference_price) if data.reference_price else None,
                        "trend_expectation": data.trend_expectation,
                    },
                )

    await db.commit()
    await db.refresh(plan)
    return plan
