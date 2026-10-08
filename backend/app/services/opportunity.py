"""Opportunity Automation and Watchlist Service.

Evaluates watchlist candidates and research pipeline instruments to surface
which opportunities deserve research or review now.
Deterministic First, Codex Second.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional, Tuple
import uuid
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.asset import Asset
from app.models.briefing import BriefingCategory, BriefingItem, BriefingMateriality
from app.models.instrument import Instrument
from app.models.intelligence import (
    InstrumentIntelligenceState,
    IntelligenceReview,
    TechnicalPlan,
    ValuationStatus,
)
from app.models.opportunity import (
    OpportunityAssessment,
    OpportunityConfidence,
    OpportunityDriver,
    OpportunityStatus,
    ResearchFreshness,
    ResearchStage,
    SuggestedNextStep,
    ValuationSignal,
    WatchlistItem,
    WatchlistPriority,
)
from app.schemas.opportunity import (
    OpportunityAssessmentResponse,
    OpportunityEvaluationSummary,
    ResearchQueueItemResponse,
    ResearchQueueResponse,
    WatchlistItemCreateRequest,
    WatchlistItemResponse,
    WatchlistItemUpdateRequest,
)
from app.services import price as price_service

logger = logging.getLogger(__name__)


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _extract_target_range(
    watchlist_item: Optional[WatchlistItem],
    technical_plan: Optional[TechnicalPlan],
) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    """Determine the active target entry range from watchlist item or technical plan."""
    if watchlist_item is not None:
        if watchlist_item.target_entry_min is not None or watchlist_item.target_entry_max is not None:
            return watchlist_item.target_entry_min, watchlist_item.target_entry_max

    if technical_plan is not None and technical_plan.entry_zones:
        # Technical plan entry_zones list of dicts: e.g. [{"min": 140, "max": 150}] or [{"low": 140, "high": 150}]
        for zone in technical_plan.entry_zones:
            if isinstance(zone, dict):
                low = zone.get("min") or zone.get("low") or zone.get("target_min")
                high = zone.get("max") or zone.get("high") or zone.get("target_max")
                if low is not None and high is not None:
                    try:
                        return Decimal(str(low)), Decimal(str(high))
                    except Exception:
                        pass
    return None, None


async def evaluate_deterministic_opportunity(
    db: AsyncSession,
    user_id: UUID,
    instrument: Instrument,
    watchlist_item: Optional[WatchlistItem],
    intelligence_state: Optional[InstrumentIntelligenceState],
    technical_plan: Optional[TechnicalPlan],
    latest_review: Optional[IntelligenceReview],
    briefing_items: List[BriefingItem],
    live_price: Optional[dict] = None,
) -> Dict[str, Any]:
    """Perform cheap deterministic opportunity checks on an instrument.

    Returns deterministic assessment context and whether a trigger fired.
    """
    now_utc = datetime.now(timezone.utc)
    research_stage = watchlist_item.research_stage if watchlist_item else ResearchStage.DISCOVERED
    priority = watchlist_item.priority if watchlist_item else WatchlistPriority.MEDIUM

    target_min, target_max = _extract_target_range(watchlist_item, technical_plan)

    # 1. Price analysis
    price_val = None
    price_curr = None
    in_target_range = False
    price_trigger_fired = False

    if live_price and live_price.get("price") is not None:
        try:
            price_val = Decimal(str(live_price["price"]))
            price_curr = live_price.get("currency")
        except Exception:
            price_val = None

    if price_val is not None and target_min is not None and target_max is not None:
        in_target_range = (target_min <= price_val <= target_max)
        if in_target_range:
            price_trigger_fired = True

    # 2. Research Freshness & Event-Driven Analysis
    last_review_at = None
    if intelligence_state and intelligence_state.last_review_at:
        last_review_at = _ensure_utc(intelligence_state.last_review_at)
    elif latest_review and latest_review.created_at:
        last_review_at = _ensure_utc(latest_review.created_at)

    material_event_after_review: Optional[BriefingItem] = None
    earnings_event_after_review: Optional[BriefingItem] = None

    for item in briefing_items:
        item_published = _ensure_utc(getattr(item, "published_at", None) or getattr(item, "created_at", None))
        # Event is considered after review if no review exists or published >= last_review_at
        is_after = (last_review_at is None) or (item_published is not None and item_published >= last_review_at)
        if is_after:
            item_cat = getattr(item, "category", None)
            if item_cat == BriefingCategory.EARNINGS or "earnings" in (item.headline or "").lower():
                earnings_event_after_review = item
                break
            elif getattr(item, "review_required", False) or getattr(item, "materiality", None) in (BriefingMateriality.HIGH, BriefingMateriality.CRITICAL):
                material_event_after_review = item

    freshness = ResearchFreshness.FRESH
    if earnings_event_after_review is not None or material_event_after_review is not None:
        freshness = ResearchFreshness.REVIEW
    elif last_review_at is not None and (now_utc - last_review_at).days > 90:
        freshness = ResearchFreshness.STALE
    elif last_review_at is None:
        freshness = ResearchFreshness.UNKNOWN

    # 3. Valuation signal
    # Authoritative Precedence:
    # 1. Current InstrumentIntelligenceState.valuation_status
    # 2. Latest valid formal Valuation Review result (IntelligenceReview)
    # 3. ValuationSignal.UNKNOWN
    # Note: Target range entry or price action MUST NEVER alter or promote valuation signal.
    valuation_signal = ValuationSignal.UNKNOWN
    val_map = {
        ValuationStatus.ATTRACTIVE: ValuationSignal.ATTRACTIVE,
        ValuationStatus.FAIR: ValuationSignal.FAIR,
        ValuationStatus.EXPENSIVE: ValuationSignal.EXPENSIVE,
    }
    str_val_map = {
        "ATTRACTIVE": ValuationSignal.ATTRACTIVE,
        "FAIR": ValuationSignal.FAIR,
        "EXPENSIVE": ValuationSignal.EXPENSIVE,
    }

    if intelligence_state and intelligence_state.valuation_status:
        valuation_signal = val_map.get(intelligence_state.valuation_status, ValuationSignal.UNKNOWN)
    elif (
        latest_review
        and isinstance(latest_review.machine_record, dict)
        and latest_review.machine_record.get("valuation_status")
    ):
        val_str = str(latest_review.machine_record["valuation_status"]).upper()
        valuation_signal = str_val_map.get(val_str, ValuationSignal.UNKNOWN)

    # 4. Trigger Synthesis & Opportunity Assignment
    trigger_fired = False
    status = OpportunityStatus.NO_CHANGE
    driver = OpportunityDriver.OTHER
    suggested = SuggestedNextStep.NONE
    reason = "Research is fresh and no material price or fundamental triggers detected."
    confidence = OpportunityConfidence.HIGH

    if price_trigger_fired:
        trigger_fired = True
        status = OpportunityStatus.RESEARCH_NOW if research_stage == ResearchStage.WAITING_FOR_PRICE or priority == WatchlistPriority.HIGH else OpportunityStatus.RESEARCH_SOON
        driver = OpportunityDriver.PRICE_MOVE
        suggested = SuggestedNextStep.PRICE_REVIEW if research_stage == ResearchStage.WAITING_FOR_PRICE else SuggestedNextStep.VALUATION_UPDATE
        price_str = f"${price_val:,.2f}" if price_curr == "USD" else f"{price_val:,.2f} {price_curr or ''}"
        min_str = f"${target_min:,.2f}" if price_curr == "USD" else f"{target_min:,.2f}"
        max_str = f"${target_max:,.2f}" if price_curr == "USD" else f"{target_max:,.2f}"
        reason = f"Current price ({price_str.strip()}) entered defined target entry zone ({min_str}–{max_str})."

    elif earnings_event_after_review is not None:
        trigger_fired = True
        status = OpportunityStatus.RESEARCH_NOW if priority == WatchlistPriority.HIGH else OpportunityStatus.RESEARCH_SOON
        driver = OpportunityDriver.CATALYST
        suggested = SuggestedNextStep.THESIS_REVIEW
        reason = f"Earnings release ({earnings_event_after_review.headline}) occurred after the most recent review."

    elif material_event_after_review is not None:
        trigger_fired = True
        status = OpportunityStatus.RESEARCH_SOON
        driver = OpportunityDriver.FUNDAMENTAL
        suggested = SuggestedNextStep.THESIS_REVIEW
        reason = f"Material development ({material_event_after_review.headline}) occurred after the most recent review."

    elif research_stage == ResearchStage.WAITING_FOR_PRICE:
        status = OpportunityStatus.WATCH
        driver = OpportunityDriver.PRICE_MOVE
        suggested = SuggestedNextStep.NONE
        if price_val is not None and target_min is not None and target_max is not None:
            price_str = f"${price_val:,.2f}" if price_curr == "USD" else f"{price_val:,.2f}"
            min_str = f"${target_min:,.2f}" if price_curr == "USD" else f"{target_min:,.2f}"
            max_str = f"${target_max:,.2f}" if price_curr == "USD" else f"{target_max:,.2f}"
            reason = f"Current price ({price_str}) is outside target entry zone ({min_str}–{max_str}). Awaiting entry."
        else:
            reason = "Awaiting price entry into target zone before initiating research review."

    elif freshness == ResearchFreshness.STALE:
        trigger_fired = True
        status = OpportunityStatus.RESEARCH_SOON
        driver = OpportunityDriver.RESEARCH_STALENESS
        suggested = SuggestedNextStep.THESIS_REVIEW if research_stage in (ResearchStage.VALUED, ResearchStage.READY) else SuggestedNextStep.DEEP_RESEARCH
        days_str = f"{(now_utc - last_review_at).days} days" if last_review_at else "extended period"
        reason = f"Research is stale ({days_str} since last formal review) and requires refreshing."

    elif research_stage == ResearchStage.DISCOVERED:
        if priority == WatchlistPriority.HIGH:
            trigger_fired = True
            status = OpportunityStatus.RESEARCH_SOON
            driver = OpportunityDriver.OTHER
            suggested = SuggestedNextStep.SCREENING
            reason = "High-priority candidate in DISCOVERED stage awaiting preliminary screening."
        else:
            status = OpportunityStatus.WATCH
            reason = "Candidate is tracked in DISCOVERED stage."

    elif research_stage == ResearchStage.SCREENED:
        if priority == WatchlistPriority.HIGH:
            trigger_fired = True
            status = OpportunityStatus.RESEARCH_SOON
            driver = OpportunityDriver.OTHER
            suggested = SuggestedNextStep.DEEP_RESEARCH
            reason = "Screening complete; candidate prioritized for deep research."
        else:
            status = OpportunityStatus.WATCH
            reason = "Candidate screened; awaiting deep research initiation."

    return {
        "trigger_fired": trigger_fired,
        "status": status,
        "primary_driver": driver,
        "valuation_signal": valuation_signal,
        "research_freshness": freshness,
        "suggested_next_step": suggested,
        "confidence": confidence,
        "reason": reason,
        "source_references": {
            "current_price": float(price_val) if price_val is not None else None,
            "current_price_currency": price_curr,
            "target_entry_min": float(target_min) if target_min is not None else None,
            "target_entry_max": float(target_max) if target_max is not None else None,
            "in_target_range": in_target_range,
            "last_review_at": last_review_at.isoformat() if last_review_at else None,
            "material_event_id": str(material_event_after_review.id) if material_event_after_review else None,
            "earnings_event_id": str(earnings_event_after_review.id) if earnings_event_after_review else None,
            "price_trigger_fired": price_trigger_fired,
        },
    }


async def evaluate_candidate_opportunity(
    db: AsyncSession,
    user_id: UUID,
    instrument: Instrument,
    watchlist_item: Optional[WatchlistItem] = None,
    force_refresh: bool = False,
    reasoner: Optional[Any] = None,
) -> OpportunityAssessment:
    """Evaluate an instrument opportunity, applying idempotency and selective Codex reasoning."""
    now_utc = datetime.now(timezone.utc)

    # 1. Load existing assessment for idempotency check
    existing_stmt = select(OpportunityAssessment).where(
        OpportunityAssessment.user_id == user_id,
        OpportunityAssessment.instrument_id == instrument.id,
    )
    existing_res = await db.execute(existing_stmt)
    existing: Optional[OpportunityAssessment] = existing_res.scalar_one_or_none()

    # 2. Gather current context
    intel_state: Optional[InstrumentIntelligenceState] = getattr(instrument, "intelligence_state", None)
    if intel_state is None and instrument.id:
        intel_stmt = select(InstrumentIntelligenceState).where(
            InstrumentIntelligenceState.instrument_id == instrument.id
        )
        intel_res = await db.execute(intel_stmt)
        intel_state = intel_res.scalar_one_or_none()

    tech_plan: Optional[TechnicalPlan] = None
    if getattr(instrument, "technical_plans", None):
        active_plans = [p for p in instrument.technical_plans if p.active]
        tech_plan = active_plans[0] if active_plans else instrument.technical_plans[0]

    latest_review: Optional[IntelligenceReview] = None
    if getattr(instrument, "reviews", None):
        latest_review = instrument.reviews[0]
    elif instrument.id:
        review_stmt = (
            select(IntelligenceReview)
            .where(IntelligenceReview.instrument_id == instrument.id)
            .order_by(IntelligenceReview.created_at.desc())
            .limit(1)
        )
        rev_res = await db.execute(review_stmt)
        latest_review = rev_res.scalar_one_or_none()

    # Load recent briefing items for this instrument
    briefing_stmt = (
        select(BriefingItem)
        .where(BriefingItem.instrument_id == instrument.id)
        .order_by(BriefingItem.created_at.desc())
        .limit(10)
    )
    briefing_res = await db.execute(briefing_stmt)
    briefing_items = list(briefing_res.scalars().all())

    # Get live or cached price
    live_price = None
    if instrument.symbol and instrument.asset_type:
        try:
            live_price = await price_service.get_live_price(
                db, instrument.symbol, instrument.asset_type.value
            )
        except Exception as e:
            logger.debug("Live price lookup failed for %s: %s", instrument.symbol, e)

    # 3. Deterministic check
    det = await evaluate_deterministic_opportunity(
        db=db,
        user_id=user_id,
        instrument=instrument,
        watchlist_item=watchlist_item,
        intelligence_state=intel_state,
        technical_plan=tech_plan,
        latest_review=latest_review,
        briefing_items=briefing_items,
        live_price=live_price,
    )

    # 4. Idempotency Check
    if not force_refresh and existing is not None:
        # Check if conditions changed
        prev_refs = existing.source_references or {}
        prev_in_range = prev_refs.get("in_target_range", False)
        curr_in_range = det["source_references"].get("in_target_range", False)

        price_zone_toggled = prev_in_range != curr_in_range
        new_events_since_assessment = any(
            _ensure_utc(i.created_at) > _ensure_utc(existing.assessment_at)
            for i in briefing_items
        )
        freshness_changed = existing.research_freshness != det["research_freshness"]
        valuation_changed = existing.valuation_signal != det["valuation_signal"]

        if not (price_zone_toggled or new_events_since_assessment or freshness_changed or valuation_changed):
            logger.debug(
                "Idempotent opportunity check for instrument %s: unchanged state preserved.",
                instrument.symbol,
            )
            return existing

    # 5. Selective Codex Reasoning
    final_status = det["status"]
    final_reason = det["reason"]
    final_driver = det["primary_driver"]
    final_suggested = det["suggested_next_step"]
    final_confidence = det["confidence"]

    if det["trigger_fired"] and reasoner is not None:
        try:
            candidate_dict = None
            if watchlist_item:
                candidate_dict = {
                    "research_stage": watchlist_item.research_stage.value,
                    "priority": watchlist_item.priority.value,
                    "why_interesting": watchlist_item.why_interesting,
                    "target_entry_min": float(watchlist_item.target_entry_min) if watchlist_item.target_entry_min else None,
                    "target_entry_max": float(watchlist_item.target_entry_max) if watchlist_item.target_entry_max else None,
                    "key_catalyst": watchlist_item.key_catalyst,
                    "key_risk": watchlist_item.key_risk,
                    "next_expected_event": watchlist_item.next_expected_event,
                }

            intel_dict = None
            if intel_state:
                intel_dict = {
                    "thesis_status": intel_state.thesis_status.value if intel_state.thesis_status else None,
                    "valuation_status": intel_state.valuation_status.value if intel_state.valuation_status else None,
                    "recommendation": intel_state.recommendation.value if intel_state.recommendation else None,
                    "last_review_at": intel_state.last_review_at.isoformat() if intel_state.last_review_at else None,
                }

            latest_review_dict = None
            if latest_review:
                latest_review_dict = {
                    "protocol": latest_review.protocol,
                    "confidence": latest_review.confidence.value if hasattr(latest_review.confidence, "value") else str(latest_review.confidence),
                    "human_brief": latest_review.human_brief,
                    "valuation_status": latest_review.machine_record.get("valuation_status") if isinstance(latest_review.machine_record, dict) else None,
                }

            ai_assessment = reasoner.assess_opportunity(
                instrument={
                    "symbol": instrument.symbol,
                    "name": instrument.name,
                    "asset_type": instrument.asset_type.value if instrument.asset_type else None,
                    "exchange": instrument.exchange,
                    "currency": instrument.currency,
                },
                watchlist_candidate=candidate_dict,
                intelligence_state=intel_dict,
                latest_review=latest_review_dict,
                current_price=live_price,
                deterministic_context=det,
                recent_events=[
                    {
                        "headline": b.headline,
                        "summary": b.summary,
                        "category": b.category.value if hasattr(b.category, "value") else str(b.category),
                    }
                    for b in briefing_items[:3]
                ],
            )

            final_status = OpportunityStatus(ai_assessment.opportunity_status)
            final_reason = ai_assessment.reason
            final_driver = OpportunityDriver(ai_assessment.primary_driver)
            final_suggested = SuggestedNextStep(ai_assessment.suggested_next_step)
            final_confidence = OpportunityConfidence(ai_assessment.confidence)
        except Exception as e:
            logger.warning(
                "Codex opportunity reasoning failed for %s; preserving deterministic outcome: %s",
                instrument.symbol,
                e,
            )
            final_confidence = OpportunityConfidence.MEDIUM

    # 6. Upsert OpportunityAssessment
    if existing is not None:
        existing.status = final_status
        existing.reason = final_reason
        existing.primary_driver = final_driver
        existing.valuation_signal = det["valuation_signal"]
        existing.research_freshness = det["research_freshness"]
        existing.suggested_next_step = final_suggested
        existing.confidence = final_confidence
        existing.source_references = det["source_references"]
        existing.assessment_at = now_utc
        record = existing
    else:
        record = OpportunityAssessment(
            user_id=user_id,
            instrument_id=instrument.id,
            status=final_status,
            reason=final_reason,
            primary_driver=final_driver,
            valuation_signal=det["valuation_signal"],
            research_freshness=det["research_freshness"],
            suggested_next_step=final_suggested,
            confidence=final_confidence,
            source_references=det["source_references"],
            assessment_at=now_utc,
        )
        db.add(record)

    await db.flush()
    return record


async def evaluate_user_opportunities(
    db: AsyncSession,
    user_id: UUID,
    instrument_id: Optional[UUID] = None,
    force_refresh: bool = False,
    reasoner: Optional[Any] = None,
) -> OpportunityEvaluationSummary:
    """Evaluate opportunities across all watchlist and candidate instruments for a user."""
    # 1. Determine user's owned instrument IDs
    owned_stmt = select(Asset.instrument_id).where(
        Asset.user_id == user_id,
        Asset.instrument_id.isnot(None),
    )
    owned_res = await db.execute(owned_stmt)
    owned_ids = set(owned_res.scalars().all())

    # 2. Query user watchlist items
    wl_query = (
        select(WatchlistItem)
        .options(
            selectinload(WatchlistItem.instrument).selectinload(Instrument.intelligence_state),
            selectinload(WatchlistItem.instrument).selectinload(Instrument.technical_plans),
            selectinload(WatchlistItem.instrument).selectinload(Instrument.reviews),
        )
        .where(WatchlistItem.user_id == user_id)
    )
    if instrument_id is not None:
        wl_query = wl_query.where(WatchlistItem.instrument_id == instrument_id)

    wl_res = await db.execute(wl_query)
    watchlist_items = list(wl_res.scalars().all())
    wl_inst_map = {item.instrument_id: item for item in watchlist_items}

    # 3. Find candidates: watchlist items + any unowned instruments without a watchlist item
    target_instruments: List[Tuple[Instrument, Optional[WatchlistItem]]] = []
    for item in watchlist_items:
        target_instruments.append((item.instrument, item))

    if instrument_id is None:
        # Also include unowned registered instruments (capped at 20)
        unowned_stmt = (
            select(Instrument)
            .options(
                selectinload(Instrument.intelligence_state),
                selectinload(Instrument.technical_plans),
                selectinload(Instrument.reviews),
            )
            .where(~Instrument.id.in_(owned_ids) if owned_ids else True)
            .order_by(Instrument.created_at.asc())
            .limit(20)
        )
        unowned_res = await db.execute(unowned_stmt)
        for inst in unowned_res.scalars().all():
            if inst.id not in wl_inst_map:
                target_instruments.append((inst, None))
    elif instrument_id not in wl_inst_map:
        inst_stmt = (
            select(Instrument)
            .options(
                selectinload(Instrument.intelligence_state),
                selectinload(Instrument.technical_plans),
                selectinload(Instrument.reviews),
            )
            .where(Instrument.id == instrument_id)
        )
        inst_res = await db.execute(inst_stmt)
        inst = inst_res.scalar_one_or_none()
        if inst:
            target_instruments.append((inst, None))

    evaluated_records: List[OpportunityAssessment] = []
    for inst, wl_item in target_instruments:
        try:
            assessment = await evaluate_candidate_opportunity(
                db=db,
                user_id=user_id,
                instrument=inst,
                watchlist_item=wl_item,
                force_refresh=force_refresh,
                reasoner=reasoner,
            )
            evaluated_records.append(assessment)
        except Exception as e:
            logger.error("Failed to evaluate opportunity for %s: %s", inst.symbol, e, exc_info=True)

    await db.commit()

    research_now_count = sum(1 for a in evaluated_records if a.status == OpportunityStatus.RESEARCH_NOW)
    research_soon_count = sum(1 for a in evaluated_records if a.status == OpportunityStatus.RESEARCH_SOON)
    opportunities_found = research_now_count + research_soon_count

    return OpportunityEvaluationSummary(
        total_candidates=len(target_instruments),
        evaluated=len(evaluated_records),
        opportunities_found=opportunities_found,
        research_now_count=research_now_count,
        research_soon_count=research_soon_count,
        items=[
            OpportunityAssessmentResponse.model_validate(a) for a in evaluated_records
        ],
    )


async def get_watchlist_items(
    db: AsyncSession,
    user_id: UUID,
) -> List[WatchlistItemResponse]:
    """Retrieve user watchlist items enriched with latest price and opportunity assessments."""
    # 1. Fetch user's explicit watchlist items
    stmt = (
        select(WatchlistItem)
        .options(
            selectinload(WatchlistItem.instrument).selectinload(Instrument.intelligence_state),
            selectinload(WatchlistItem.instrument).selectinload(Instrument.technical_plans),
            selectinload(WatchlistItem.instrument).selectinload(Instrument.reviews),
        )
        .where(WatchlistItem.user_id == user_id)
        .order_by(WatchlistItem.created_at.desc())
    )
    res = await db.execute(stmt)
    items = list(res.scalars().all())

    # 2. Fetch existing opportunity assessments
    inst_ids = [item.instrument_id for item in items]
    opp_map: Dict[UUID, OpportunityAssessment] = {}
    if inst_ids:
        opp_stmt = select(OpportunityAssessment).where(
            OpportunityAssessment.user_id == user_id,
            OpportunityAssessment.instrument_id.in_(inst_ids),
        )
        opp_res = await db.execute(opp_stmt)
        for opp in opp_res.scalars().all():
            opp_map[opp.instrument_id] = opp

    # 3. Build response
    responses: List[WatchlistItemResponse] = []
    for item in items:
        opp = opp_map.get(item.instrument_id)

        # Get cached price if available
        live_price = None
        if item.instrument.symbol and item.instrument.asset_type:
            try:
                live_price = await price_service.get_live_price(
                    db, item.instrument.symbol, item.instrument.asset_type.value
                )
            except Exception:
                pass

        resp = WatchlistItemResponse(
            id=item.id,
            instrument_id=item.instrument_id,
            research_stage=item.research_stage,
            priority=item.priority,
            why_interesting=item.why_interesting,
            target_entry_min=item.target_entry_min,
            target_entry_max=item.target_entry_max,
            key_catalyst=item.key_catalyst,
            key_risk=item.key_risk,
            next_expected_event=item.next_expected_event,
            notes=item.notes,
            created_at=item.created_at,
            updated_at=item.updated_at,
            instrument=item.instrument,
            current_price=live_price.get("price") if live_price else None,
            current_price_currency=live_price.get("currency") if live_price else None,
            opportunity=OpportunityAssessmentResponse.model_validate(opp) if opp else None,
        )
        responses.append(resp)

    return responses


get_user_watchlist = get_watchlist_items


async def upsert_watchlist_item(
    db: AsyncSession,
    user_id: UUID,
    body: WatchlistItemCreateRequest,
) -> WatchlistItemResponse:
    """Add or update a watchlist candidate."""
    instrument_id = body.instrument_id

    # If instrument_id not supplied, create or resolve instrument
    if instrument_id is None:
        if not body.name:
            raise ValueError("Instrument name or instrument_id is required")
        from app.services import instrument as instrument_service
        inst = await instrument_service.find_or_create_instrument(
            db,
            name=body.name,
            symbol=body.symbol,
            asset_type=body.asset_type or "STOCK",
            exchange=body.exchange,
            currency=body.currency,
        )
        instrument_id = inst.id

    # Check if watchlist item exists
    stmt = select(WatchlistItem).where(
        WatchlistItem.user_id == user_id,
        WatchlistItem.instrument_id == instrument_id,
    )
    res = await db.execute(stmt)
    item = res.scalar_one_or_none()

    if item is None:
        item = WatchlistItem(
            user_id=user_id,
            instrument_id=instrument_id,
            research_stage=body.research_stage,
            priority=body.priority,
            why_interesting=body.why_interesting,
            target_entry_min=body.target_entry_min,
            target_entry_max=body.target_entry_max,
            key_catalyst=body.key_catalyst,
            key_risk=body.key_risk,
            next_expected_event=body.next_expected_event,
            notes=body.notes,
        )
        db.add(item)
    else:
        if body.research_stage is not None:
            item.research_stage = body.research_stage
        if body.priority is not None:
            item.priority = body.priority
        if body.why_interesting is not None:
            item.why_interesting = body.why_interesting
        if body.target_entry_min is not None:
            item.target_entry_min = body.target_entry_min
        if body.target_entry_max is not None:
            item.target_entry_max = body.target_entry_max
        if body.key_catalyst is not None:
            item.key_catalyst = body.key_catalyst
        if body.key_risk is not None:
            item.key_risk = body.key_risk
        if body.next_expected_event is not None:
            item.next_expected_event = body.next_expected_event
        if body.notes is not None:
            item.notes = body.notes

    await db.commit()
    await db.refresh(item)

    # Evaluate opportunity for this candidate immediately
    try:
        await evaluate_candidate_opportunity(
            db=db,
            user_id=user_id,
            instrument=item.instrument,
            watchlist_item=item,
            force_refresh=True,
        )
        await db.commit()
    except Exception as e:
        logger.warning("Auto-evaluation on watchlist add failed: %s", e)

    results = await get_watchlist_items(db, user_id)
    matching = [r for r in results if r.id == item.id]
    return matching[0] if matching else WatchlistItemResponse.model_validate(item)


async def update_watchlist_item(
    db: AsyncSession,
    user_id: UUID,
    item_id: UUID,
    body: WatchlistItemUpdateRequest,
) -> Optional[WatchlistItemResponse]:
    """Update an existing watchlist candidate."""
    stmt = (
        select(WatchlistItem)
        .options(selectinload(WatchlistItem.instrument))
        .where(
            WatchlistItem.id == item_id,
            WatchlistItem.user_id == user_id,
        )
    )
    res = await db.execute(stmt)
    item = res.scalar_one_or_none()
    if item is None:
        return None

    if body.research_stage is not None:
        item.research_stage = body.research_stage
    if body.priority is not None:
        item.priority = body.priority
    if body.why_interesting is not None:
        item.why_interesting = body.why_interesting
    if body.target_entry_min is not None:
        item.target_entry_min = body.target_entry_min
    if body.target_entry_max is not None:
        item.target_entry_max = body.target_entry_max
    if body.key_catalyst is not None:
        item.key_catalyst = body.key_catalyst
    if body.key_risk is not None:
        item.key_risk = body.key_risk
    if body.next_expected_event is not None:
        item.next_expected_event = body.next_expected_event
    if body.notes is not None:
        item.notes = body.notes

    await db.commit()
    await db.refresh(item)

    # Re-evaluate opportunity if target range or priority changed
    try:
        await evaluate_candidate_opportunity(
            db=db,
            user_id=user_id,
            instrument=item.instrument,
            watchlist_item=item,
            force_refresh=True,
        )
        await db.commit()
    except Exception as e:
        logger.warning("Re-evaluation on watchlist update failed: %s", e)

    results = await get_watchlist_items(db, user_id)
    matching = [r for r in results if r.id == item.id]
    return matching[0] if matching else WatchlistItemResponse.model_validate(item)


async def delete_watchlist_item(
    db: AsyncSession,
    user_id: UUID,
    item_id: UUID,
) -> bool:
    """Remove an item from the user's watchlist."""
    stmt = delete(WatchlistItem).where(
        WatchlistItem.id == item_id,
        WatchlistItem.user_id == user_id,
    )
    res = await db.execute(stmt)
    await db.commit()
    return res.rowcount > 0


async def get_research_queue(
    db: AsyncSession,
    user_id: UUID,
) -> ResearchQueueResponse:
    """Retrieve prioritized research queue categorized by opportunity urgency and pipeline stage."""
    watchlist_items = await get_watchlist_items(db, user_id)

    # Also query user owned assets to compute pipeline stage counts
    owned_stmt = (
        select(Asset)
        .options(selectinload(Asset.instrument))
        .where(Asset.user_id == user_id)
    )
    owned_res = await db.execute(owned_stmt)
    owned_assets = list(owned_res.scalars().all())

    stage_counts: Dict[str, int] = {
        s.value: 0 for s in ResearchStage
    }
    stage_counts[ResearchStage.OWNED.value] = len(owned_assets)

    queue_items: List[ResearchQueueItemResponse] = []

    for w in watchlist_items:
        inst = w.instrument
        if not inst:
            continue

        stage_counts[w.research_stage.value] = stage_counts.get(w.research_stage.value, 0) + 1

        opp = w.opportunity
        opp_status = opp.status if opp else OpportunityStatus.NO_CHANGE
        driver = opp.primary_driver if opp else OpportunityDriver.OTHER
        suggested = opp.suggested_next_step if opp else SuggestedNextStep.NONE
        reason = opp.reason if opp else "Awaiting initial opportunity evaluation."
        conf = opp.confidence if opp else OpportunityConfidence.MEDIUM
        freshness = opp.research_freshness if opp else ResearchFreshness.UNKNOWN
        val_sig = opp.valuation_signal if opp else ValuationSignal.UNKNOWN
        assessment_at = opp.assessment_at if opp else w.created_at

        last_rev = None
        if hasattr(inst, "intelligence_state") and inst.intelligence_state:
            last_rev = getattr(inst.intelligence_state, "last_review_at", None)

        queue_item = ResearchQueueItemResponse(
            instrument_id=inst.id,
            symbol=inst.symbol,
            name=inst.name,
            asset_type=inst.asset_type.value if hasattr(inst.asset_type, "value") else str(inst.asset_type),
            exchange=inst.exchange,
            research_stage=w.research_stage,
            priority=w.priority,
            opportunity_status=opp_status,
            primary_driver=driver,
            suggested_next_step=suggested,
            reason=reason,
            confidence=conf,
            current_price=w.current_price,
            current_price_currency=w.current_price_currency,
            target_entry_min=w.target_entry_min,
            target_entry_max=w.target_entry_max,
            research_freshness=freshness,
            valuation_signal=val_sig,
            last_review_at=last_rev,
            assessment_at=assessment_at,
        )
        queue_items.append(queue_item)

    research_now = [q for q in queue_items if q.opportunity_status == OpportunityStatus.RESEARCH_NOW]
    research_soon = [q for q in queue_items if q.opportunity_status == OpportunityStatus.RESEARCH_SOON]
    waiting = [q for q in queue_items if q.opportunity_status == OpportunityStatus.WATCH or q.research_stage == ResearchStage.WAITING_FOR_PRICE]
    no_action = [q for q in queue_items if q.opportunity_status == OpportunityStatus.NO_CHANGE and q.research_stage != ResearchStage.WAITING_FOR_PRICE]

    return ResearchQueueResponse(
        research_now=research_now,
        research_soon=research_soon,
        waiting=waiting,
        no_action=no_action,
        stage_counts=stage_counts,
        total_candidates=len(queue_items),
    )
