"""Intelligence Briefing service — scans portfolio & watchlist for developments,
evaluates materiality, filters noise, and produces structured Briefing runs.
"""

import asyncio
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID
import zoneinfo

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.asset import Asset
from app.models.briefing import (
    BriefingCategory,
    BriefingImpact,
    BriefingItem,
    BriefingMateriality,
    BriefingRun,
    BriefingThesisImpact,
    BriefingTimeHorizon,
    BriefingTriggerType,
)
from app.models.decision_log import DecisionEventType, DecisionLogEntry
from app.models.instrument import Instrument
from app.models.intelligence import (
    InstrumentIntelligenceState,
    IntelligenceReview,
    Recommendation,
    ThesisStatus,
)
from app.models.transaction import Transaction, TransactionType
from app.schemas.briefing import BriefingItemResponse, BriefingRunResponse

# Ensure Finance/src is accessible for live providers
finance_src = Path(__file__).resolve().parent.parent.parent.parent / "Finance" / "src"
if finance_src.exists() and str(finance_src) not in sys.path:
    sys.path.insert(0, str(finance_src))

try:
    from investment_intelligence.briefing_reasoner import BriefingAssessment, BriefingReasoner
    from investment_intelligence.live_providers import GoogleNewsRSSProvider, SECDisclosureProvider
    from investment_intelligence.records import InstrumentRecord
except ImportError:
    BriefingReasoner = None  # type: ignore[assignment,misc]
    BriefingAssessment = None  # type: ignore[assignment,misc]
    GoogleNewsRSSProvider = None  # type: ignore[assignment,misc]
    SECDisclosureProvider = None  # type: ignore[assignment,misc]
    InstrumentRecord = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

# Module-level in-flight concurrency lock to prevent overlapping runs per user
_briefing_generation_lock = asyncio.Lock()
_active_generating_users: Set[UUID] = set()


def _clean_instrument_name(name: str, symbol: str = "") -> str:
    """Sanitize instrument display names to improve search query precision.
    Removes parenthetical suffixes like (Google), corporate designations like Inc./Corp.,
    and multilingual slash phrases like 'Ons Altın / Gold (USD/oz)'.
    """
    if not name:
        return symbol or ""
    # Strip parenthetical annotations: (Google), (USD/oz), (ETH), etc.
    cleaned = re.sub(r"\s*\([^)]*\)", "", name)
    # Handle bilingual or slash names like "Ons Altın / Gold"
    if "/" in cleaned:
        parts = [p.strip() for p in cleaned.split("/") if p.strip()]
        # Prefer recognizable asset keyword if present, else first part
        asset_part = next((p for p in parts if any(k in p.lower() for k in ("gold", "silver", "altin"))), parts[0])
        cleaned = asset_part
    # Strip common corporate designations
    cleaned = re.sub(
        r"\b(Inc\.?|Corp\.?|Corporation|Ltd\.?|Limited|LLC|PLC|A\.?O\.?|A\.Ş\.?|S\.A\.?)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Strip punctuation and keep clean words
    cleaned = re.sub(r"[^A-Za-z0-9 ]", " ", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned if cleaned else (symbol or name)


def _classify_development(
    title: str,
    summary: str,
    is_portfolio: bool,
    is_sec: bool = False,
    sec_form: Optional[str] = None,
    symbol: Optional[str] = None,
) -> Tuple[
    BriefingCategory, BriefingImpact, BriefingMateriality, BriefingTimeHorizon, BriefingThesisImpact, bool, str
]:
    """Classify a news/filing item into category, impact, materiality, and thesis impact."""
    text = f"{title} {summary}".lower()

    # Category classification
    if is_sec:
        form_upper = (sec_form or "").upper()
        if any(f in form_upper for f in ("10-K", "10-Q")):
            category = BriefingCategory.EARNINGS
        elif any(f in form_upper for f in ("4", "3", "5")):
            category = BriefingCategory.OPERATIONAL
        else:
            category = BriefingCategory.REGULATORY
    else:
        title_l = title.lower()
        summary_l = summary.lower()

        cat_keywords = {
            BriefingCategory.REGULATORY: (
                "sec", "doj", "ftc", "regulat", "lawsuit", "probe", "fine", "compliance",
                "antitrust", "8-k", "subpoena", "court", "investigat", "sanction",
            ),
            BriefingCategory.EARNINGS: (
                "earning", "quarterly", "revenue", "eps", "guidance", "dividend",
                "10-q", "10-k", "profit", "sales beat", "sales miss", "operating income",
            ),
            BriefingCategory.MACRO: (
                "fed", "interest rate", "inflation", "cpi", "macro", "tariff", "gdp",
                "recession", "rate cut", "rate hike", "central bank", "treasury", "yield",
            ),
            BriefingCategory.OPERATIONAL: (
                "acqui", "merger", "ceo", "partnership", "partner", "layoff", "expansion",
                "expands", "restructur", "contract", "deal", "launch", "product", "hire",
                "offering", "debt", "bond", "buyback", "share repurchase", "crypto", "token",
                "etf", "mining", "reserve",
            ),
            BriefingCategory.COMPETITIVE: (
                "compet", "rival", "market share", "beats rival", "displaces",
            ),
        }

        cat_scores: Dict[BriefingCategory, int] = {}
        for cat, keywords in cat_keywords.items():
            score = 0
            for kw in keywords:
                if kw in title_l:
                    score += 2
                if kw in summary_l:
                    score += 1
            if score > 0:
                cat_scores[cat] = score

        if cat_scores:
            category = max(cat_scores, key=lambda c: cat_scores[c])
        else:
            category = BriefingCategory.GENERAL

    # Impact classification
    if is_sec:
        form_upper = (sec_form or "").upper()
        if "8-K" in form_upper:
            impact = BriefingImpact.MIXED
        else:
            impact = BriefingImpact.NEUTRAL
    else:
        pos_keywords = (
            "beat", "surge", "record high", "upgrade", "partner", "approval", "expands",
            "profit rises", "bullish", "jump", "rally", "gain", "climbs", "all-time high",
            "ath", "inflows", "secures", "outperform", "dividend increase"
        )
        neg_keywords = (
            "miss", "probe", "lawsuit", "investigat", "downgrade", "fall", "drop",
            "warning", "penalty", "bearish", "plunge", "slump", "cuts", "decline",
            "sinks", "loss", "layoffs", "underperform", "fraud", "breach"
        )
        mixed_keywords = ("volatile", "mixed", "dispute", "uncertain", "conflicting")

        pos_score = sum(1 for k in pos_keywords if k in text)
        neg_score = sum(1 for k in neg_keywords if k in text)
        mixed_score = sum(1 for k in mixed_keywords if k in text)

        if mixed_score > 0 and pos_score > 0 and neg_score > 0:
            impact = BriefingImpact.MIXED
        elif pos_score > neg_score:
            impact = BriefingImpact.POSITIVE
        elif neg_score > pos_score:
            impact = BriefingImpact.NEGATIVE
        else:
            impact = BriefingImpact.NEUTRAL

    # Noise & Materiality classification (news-monitoring protocol: LOW is filtered noise)
    noise_patterns = (
        "stocks to buy",
        "why is it down today",
        "why is it up today",
        "should you buy",
        "motley fool",
        "zacks",
        "is it a good pick",
        "best stocks",
        "options alert",
        "weekly recap",
        "top stocks for 20",
        "here's why",
        "prediction",
        "stock price prediction",
    )
    is_noise = any(np in text for np in noise_patterns)

    high_materiality_patterns = (
        "10-k", "10-q", "8-k", "sec probe", "doj", "antitrust", "ceo resigns", "ceo steps down",
        "earnings beat", "earnings miss", "revenue cuts", "restructuring", "acquisition of", "merger with",
        "bankruptcy", "default", "rate hike", "rate cut", "tender offer", "delisting", "all-time high"
    )
    is_high_material = any(hmp in text for hmp in high_materiality_patterns)

    if is_sec:
        form_upper = (sec_form or "").upper()
        if any(f in form_upper for f in ("8-K", "10-K", "10-Q")):
            materiality = BriefingMateriality.HIGH
        else:
            materiality = BriefingMateriality.MEDIUM
    elif is_noise and not is_high_material:
        materiality = BriefingMateriality.LOW
    elif is_high_material:
        materiality = BriefingMateriality.HIGH
    elif category in (BriefingCategory.EARNINGS, BriefingCategory.REGULATORY, BriefingCategory.OPERATIONAL):
        materiality = BriefingMateriality.MEDIUM
    elif category in (BriefingCategory.MACRO, BriefingCategory.COMPETITIVE):
        materiality = BriefingMateriality.MEDIUM
    elif impact in (BriefingImpact.POSITIVE, BriefingImpact.NEGATIVE, BriefingImpact.MIXED):
        materiality = BriefingMateriality.MEDIUM
    else:
        materiality = BriefingMateriality.LOW

    # Time horizon
    if category in (BriefingCategory.EARNINGS, BriefingCategory.OPERATIONAL):
        horizon = BriefingTimeHorizon.MEDIUM
    elif category == BriefingCategory.REGULATORY:
        horizon = BriefingTimeHorizon.LONG
    elif category == BriefingCategory.MACRO:
        horizon = BriefingTimeHorizon.SHORT
    elif category == BriefingCategory.COMPETITIVE:
        horizon = BriefingTimeHorizon.MEDIUM
    else:
        horizon = BriefingTimeHorizon.MEDIUM

    # Review requirement
    review_required = materiality in (BriefingMateriality.HIGH, BriefingMateriality.CRITICAL)

    # Thesis impact
    if review_required:
        if impact == BriefingImpact.POSITIVE:
            thesis_impact = BriefingThesisImpact.STRONGER
        elif impact == BriefingImpact.NEGATIVE:
            thesis_impact = BriefingThesisImpact.WEAKER
        else:
            thesis_impact = BriefingThesisImpact.UNCHANGED
    else:
        thesis_impact = BriefingThesisImpact.NOT_EVALUATED

    # Contextual why_it_matters explanation
    target_name = symbol or "Asset"
    if is_sec:
        why = f"Official SEC {sec_form or 'filing'} for {target_name}. Primary regulatory evidence requiring review for material disclosures, governance, or capital structure updates."
    elif is_portfolio:
        why = f"Direct portfolio holding. {category.value.capitalize()} development with {impact.value.lower()} bias that may affect position risk/return parameters."
    else:
        why = f"Watchlist instrument. Monitored for potential thesis alignment or entry conditions under {category.value.capitalize()} events."

    return category, impact, materiality, horizon, thesis_impact, review_required, why



def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def compute_item_attention_state(
    review_required: bool,
    source_metadata: Optional[dict[str, Any]],
    user_decision_recorded: bool = False,
    current_state_cleared: bool = False,
) -> str:
    """Compute the attention state for a Briefing item.

    Returns:
    - 'NONE': If review_required is False.
    - 'OPEN': If review_required is True, but no review has completed (or review failed).
    - 'REVIEWED_BUT_STILL_REQUIRES_ATTENTION': Review completed, but outcome requires ongoing review attention
      (recommendation is REVIEW_REQUIRED, thesis_status is WEAKER or INVALIDATED,
       or technical_status is REVIEW_REQUIRED or DEVIATED).
    - 'DECISION_REQUIRED': Review completed with an actionable recommendation (ADD, BUY, REDUCE, SELL)
      and intact thesis that requires an explicit user investment decision.
    - 'RESOLVED': Review completed successfully and outcome confirms position/watch is stable (HOLD with intact thesis),
      or an actionable recommendation has been acted upon / decided by the user (or cleared by subsequent authoritative review).
    """
    if not review_required:
        return "NONE"

    if not source_metadata:
        return "OPEN"

    review_status = source_metadata.get("review_status")
    if review_status != "COMPLETED":
        return "OPEN"

    summary = source_metadata.get("review_summary")
    if not isinstance(summary, dict):
        return "OPEN"

    rec = str(summary.get("recommendation") or "").upper().strip()
    thesis = str(summary.get("thesis_status") or "").upper().strip()
    tech = str(summary.get("technical_status") or "").upper().strip()

    if not (rec or thesis or tech):
        return "OPEN"

    # If cleared by a subsequent authoritative review (e.g. state now HOLD) or marked resolved
    if current_state_cleared or source_metadata.get("decision_resolved"):
        return "RESOLVED"

    # Review attention check
    if (
        rec in ("REVIEW_REQUIRED",)
        or thesis in ("WEAKER", "INVALIDATED")
        or tech in ("REVIEW_REQUIRED", "DEVIATED")
    ):
        return "REVIEWED_BUT_STILL_REQUIRES_ATTENTION"

    # Decision attention check: actionable recommendations require user decision
    if rec in ("ADD", "BUY", "REDUCE", "SELL"):
        if user_decision_recorded:
            return "RESOLVED"
        return "DECISION_REQUIRED"

    return "RESOLVED"


async def resolve_item_attention_states(
    db: AsyncSession,
    user_id: UUID,
    items: List[BriefingItem],
) -> Dict[UUID, str]:
    """Dynamically resolve the attention state for a list of briefing items.

    Evaluates:
    1. Static metadata on the item (review_status, review_summary).
    2. Any subsequent InstrumentIntelligenceState updates (e.g. state updated to HOLD after item review).
    3. Any user decisions in DecisionLogEntry (MANUAL_DECISION_NOTE, BUY/SELL actions, position changes)
       occurring after the item's review. System events (e.g. RECOMMENDATION_CHANGED,
       INTELLIGENCE_REVIEW_COMPLETED) alone do NOT resolve decision attention.
    4. Any user transactions (BUY matching ADD/BUY, SELL matching REDUCE/SELL) occurring after the review.
    """
    if not items:
        return {}

    res_map: Dict[UUID, str] = {}
    pending_items: List[BriefingItem] = []

    for item in items:
        if not item.review_required:
            res_map[item.id] = "NONE"
            continue
        if not item.source_metadata or item.source_metadata.get("review_status") != "COMPLETED":
            res_map[item.id] = "OPEN"
            continue
        summary = item.source_metadata.get("review_summary")
        if not isinstance(summary, dict):
            res_map[item.id] = "OPEN"
            continue
        rec = str(summary.get("recommendation") or "").upper().strip()
        thesis = str(summary.get("thesis_status") or "").upper().strip()
        tech = str(summary.get("technical_status") or "").upper().strip()
        if not (rec or thesis or tech):
            res_map[item.id] = "OPEN"
            continue
        if item.source_metadata.get("decision_resolved"):
            res_map[item.id] = "RESOLVED"
            continue
        pending_items.append(item)

    if not pending_items:
        return res_map

    inst_ids = {i.instrument_id for i in pending_items if i.instrument_id is not None}

    # Query 1: Latest InstrumentIntelligenceState for all pending instruments
    state_by_inst: Dict[UUID, InstrumentIntelligenceState] = {}
    if inst_ids:
        st_stmt = select(InstrumentIntelligenceState).where(
            InstrumentIntelligenceState.instrument_id.in_(inst_ids)
        )
        st_res = await db.execute(st_stmt)
        for s in st_res.scalars().all():
            state_by_inst[s.instrument_id] = s

    # Query 2: User DecisionLogEntry records for pending instruments
    # Only explicit user actions: MANUAL_DECISION_NOTE, POSITION_OPENED, POSITION_ADDED,
    # POSITION_REDUCED, POSITION_CLOSED, BUY, SELL.
    decisions_by_inst: Dict[UUID, List[DecisionLogEntry]] = {}
    if inst_ids:
        dl_stmt = (
            select(DecisionLogEntry)
            .where(
                DecisionLogEntry.user_id == user_id,
                DecisionLogEntry.instrument_id.in_(inst_ids),
                DecisionLogEntry.event_type.in_([
                    DecisionEventType.MANUAL_DECISION_NOTE,
                    DecisionEventType.POSITION_OPENED,
                    DecisionEventType.POSITION_ADDED,
                    DecisionEventType.POSITION_REDUCED,
                    DecisionEventType.POSITION_CLOSED,
                    DecisionEventType.BUY,
                    DecisionEventType.SELL,
                ]),
            )
            .order_by(DecisionLogEntry.occurred_at.desc())
        )
        dl_res = await db.execute(dl_stmt)
        for d in dl_res.scalars().all():
            if d.instrument_id:
                decisions_by_inst.setdefault(d.instrument_id, []).append(d)

    # Query 3: Transactions on user's assets for pending instruments
    txs_by_inst: Dict[UUID, List[Transaction]] = {}
    if inst_ids:
        tx_stmt = (
            select(Transaction, Asset.instrument_id)
            .join(Asset, Transaction.asset_id == Asset.id)
            .where(
                Asset.user_id == user_id,
                Asset.instrument_id.in_(inst_ids),
            )
            .order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
        )
        tx_res = await db.execute(tx_stmt)
        for tx, inst_id in tx_res.all():
            if inst_id:
                txs_by_inst.setdefault(inst_id, []).append(tx)

    # Evaluate each pending item
    for item in pending_items:
        meta = item.source_metadata or {}
        summary = meta.get("review_summary") or {}
        rec = str(summary.get("recommendation") or "").upper().strip()

        # Determine review timestamp
        raw_trig = meta.get("triggered_at")
        review_time: Optional[datetime] = None
        if isinstance(raw_trig, str):
            try:
                review_time = datetime.fromisoformat(raw_trig)
            except Exception:
                review_time = item.created_at
        elif isinstance(raw_trig, datetime):
            review_time = raw_trig
        else:
            review_time = item.created_at

        review_time_utc = _ensure_utc(review_time) or datetime.now(timezone.utc)

        # Check 1: Has a subsequent authoritative review updated the instrument state to HOLD?
        current_state_cleared = False
        if item.instrument_id and item.instrument_id in state_by_inst:
            curr_state = state_by_inst[item.instrument_id]
            curr_last_review = _ensure_utc(curr_state.last_review_at)
            if curr_last_review and curr_last_review > review_time_utc:
                st_rec = curr_state.recommendation.value if hasattr(curr_state.recommendation, "value") else str(curr_state.recommendation or "")
                st_thesis = curr_state.thesis_status.value if hasattr(curr_state.thesis_status, "value") else str(curr_state.thesis_status or "")
                if st_rec.upper() == "HOLD" and st_thesis.upper() not in ("WEAKER", "INVALIDATED"):
                    current_state_cleared = True

        # Check 2: Was an explicit user decision recorded after the review?
        user_decision_recorded = False
        if item.instrument_id:
            inst_decisions = decisions_by_inst.get(item.instrument_id, [])
            for d in inst_decisions:
                d_time = _ensure_utc(d.occurred_at or d.created_at)
                if d_time and d_time >= review_time_utc:
                    if d.event_type == DecisionEventType.MANUAL_DECISION_NOTE:
                        user_decision_recorded = True
                        break
                    if rec in ("ADD", "BUY") and d.event_type in (
                        DecisionEventType.POSITION_OPENED,
                        DecisionEventType.POSITION_ADDED,
                        DecisionEventType.BUY,
                    ):
                        user_decision_recorded = True
                        break
                    if rec in ("REDUCE", "SELL") and d.event_type in (
                        DecisionEventType.POSITION_REDUCED,
                        DecisionEventType.POSITION_CLOSED,
                        DecisionEventType.SELL,
                    ):
                        user_decision_recorded = True
                        break

            if not user_decision_recorded:
                inst_txs = txs_by_inst.get(item.instrument_id, [])
                for tx in inst_txs:
                    tx_time = _ensure_utc(tx.created_at)
                    if tx_time is None and tx.transaction_date:
                        tx_time = datetime.combine(tx.transaction_date, datetime.min.time(), tzinfo=timezone.utc)
                    if tx_time and tx_time >= review_time_utc:
                        if rec in ("ADD", "BUY") and tx.transaction_type == TransactionType.BUY:
                            user_decision_recorded = True
                            break
                        if rec in ("REDUCE", "SELL") and tx.transaction_type == TransactionType.SELL:
                            user_decision_recorded = True
                            break

        res_map[item.id] = compute_item_attention_state(
            review_required=item.review_required,
            source_metadata=item.source_metadata,
            user_decision_recorded=user_decision_recorded,
            current_state_cleared=current_state_cleared,
        )

    return res_map


def _item_to_response(item: BriefingItem, attention_state: Optional[str] = None) -> BriefingItemResponse:
    symbol = item.instrument.symbol if item.instrument else None
    inst_name = item.instrument.name if item.instrument else None
    att_state = attention_state or compute_item_attention_state(item.review_required, item.source_metadata)
    return BriefingItemResponse(
        id=item.id,
        briefing_run_id=item.briefing_run_id,
        user_id=item.user_id,
        instrument_id=item.instrument_id,
        headline=item.headline,
        summary=item.summary,
        why_it_matters=item.why_it_matters,
        impact=item.impact,
        materiality=item.materiality,
        time_horizon=item.time_horizon,
        thesis_impact=item.thesis_impact,
        review_required=item.review_required,
        category=item.category,
        source_metadata=item.source_metadata,
        is_portfolio=item.is_portfolio,
        published_at=item.published_at,
        created_at=item.created_at,
        instrument_symbol=symbol,
        instrument_name=inst_name,
        attention_state=att_state,
    )


def _run_to_response(run: BriefingRun, attention_map: Optional[Dict[UUID, str]] = None) -> BriefingRunResponse:
    att_map = attention_map or {}
    items = [_item_to_response(i, attention_state=att_map.get(i.id)) for i in run.items]
    return BriefingRunResponse(
        id=run.id,
        user_id=run.user_id,
        generated_at=run.generated_at,
        scope=run.scope,
        status=run.status,
        trigger_type=run.trigger_type,
        items_found=run.items_found,
        items_shown=run.items_shown,
        items_filtered=run.items_filtered,
        created_at=run.created_at,
        items=items,
    )


async def get_latest_briefing_run(
    db: AsyncSession,
    user_id: UUID,
) -> Optional[BriefingRunResponse]:
    """Retrieve the most recent briefing run for a user with its associated items."""
    stmt = (
        select(BriefingRun)
        .options(
            selectinload(BriefingRun.items).selectinload(BriefingItem.instrument)
        )
        .where(BriefingRun.user_id == user_id)
        .order_by(BriefingRun.generated_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    run = result.scalar_one_or_none()
    if not run:
        return None
    attention_map = await resolve_item_attention_states(db, user_id, run.items)
    return _run_to_response(run, attention_map=attention_map)


async def get_briefing_attention_count(
    db: AsyncSession,
    user_id: UUID,
) -> int:
    """Return count of unresolved items needing attention from the latest briefing."""
    latest = await get_latest_briefing_run(db, user_id)
    if not latest or not latest.items:
        return 0
    return sum(
        1
        for item in latest.items
        if item.attention_state in ("OPEN", "REVIEWED_BUT_STILL_REQUIRES_ATTENTION", "DECISION_REQUIRED")
    )


async def generate_briefing_run(
    db: AsyncSession,
    user_id: UUID,
    scope: str = "PORTFOLIO_AND_WATCHLIST",
    force_refresh: bool = False,
    trigger_type: BriefingTriggerType = BriefingTriggerType.MANUAL,
    evidence_since: Optional[datetime] = None,
    reasoner: Optional[Any] = None,
) -> BriefingRunResponse:
    """Scan owned assets and watchlist instruments, filter noise, and record a new BriefingRun."""
    now = datetime.now(timezone.utc)

    # 0. Cross-process at-most-once check for SCHEDULED runs
    if trigger_type == BriefingTriggerType.SCHEDULED:
        try:
            tz = zoneinfo.ZoneInfo(settings.BRIEFING_SCHEDULE_TIMEZONE)
        except Exception:
            tz = timezone.utc
        now_local = datetime.now(tz)
        today_start_utc = datetime(
            now_local.year, now_local.month, now_local.day, 0, 0, 0, tzinfo=tz
        ).astimezone(timezone.utc)

        existing_sched_stmt = (
            select(BriefingRun)
            .options(
                selectinload(BriefingRun.items).selectinload(BriefingItem.instrument)
            )
            .where(
                BriefingRun.user_id == user_id,
                BriefingRun.trigger_type == BriefingTriggerType.SCHEDULED,
                BriefingRun.generated_at >= today_start_utc,
            )
            .order_by(BriefingRun.generated_at.desc())
            .limit(1)
        )
        existing_sched_res = await db.execute(existing_sched_stmt)
        existing_sched_run = existing_sched_res.scalar_one_or_none()
        if existing_sched_run is not None:
            logger.info(
                "Scheduled briefing already executed today (%s) for user %s (run_id=%s); skipping duplicate execution.",
                now_local.date().isoformat(),
                user_id,
                existing_sched_run.id,
            )
            return _run_to_response(existing_sched_run)

    # 1. Check for recent run if not force_refresh (cache for 10 minutes for MANUAL runs)
    if not force_refresh and trigger_type == BriefingTriggerType.MANUAL:
        latest = await get_latest_briefing_run(db, user_id)
        if latest and (now - latest.generated_at) < timedelta(minutes=10):
            return latest

    # Concurrency guard: prevent overlapping runs for the same user
    async with _briefing_generation_lock:
        if user_id in _active_generating_users:
            logger.warning(
                "Briefing generation already in progress for user %s; returning latest run",
                user_id,
            )
            latest = await get_latest_briefing_run(db, user_id)
            if latest:
                return latest
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Briefing generation already in progress for this account",
            )
        _active_generating_users.add(user_id)

    try:
        # 1b. Determine incremental evidence collection window
        if evidence_since is None:
            latest_run_record = await get_latest_briefing_run(db, user_id)
            if latest_run_record is not None:
                # 2-hour safety overlap to catch late-indexed news / filings
                evidence_since = latest_run_record.generated_at - timedelta(hours=2)
            else:
                # Bootstrap window: past 48 hours
                evidence_since = now - timedelta(hours=48)

        # 2. Identify owned holdings vs watched instruments
        # Owned assets
        asset_stmt = (
            select(Asset)
            .options(selectinload(Asset.instrument))
            .where(Asset.user_id == user_id)
        )
        asset_res = await db.execute(asset_stmt)
        assets = asset_res.scalars().all()

        portfolio_instrument_map: Dict[UUID, Instrument] = {}
        unlinked_symbols: Set[str] = set()
        for a in assets:
            if a.instrument is not None:
                portfolio_instrument_map[a.instrument.id] = a.instrument
            elif a.symbol:
                unlinked_symbols.add(a.symbol.strip().upper())

        # Fallback: resolve unlinked asset symbols to instruments if available
        if unlinked_symbols:
            unlinked_stmt = select(Instrument).where(
                func.upper(Instrument.symbol).in_(unlinked_symbols)
            )
            unlinked_res = await db.execute(unlinked_stmt)
            for inst in unlinked_res.scalars().all():
                portfolio_instrument_map[inst.id] = inst

        # Watchlist instruments (all registered instruments not owned by user, capped at 15)
        inst_stmt = (
            select(Instrument)
            .order_by(desc(Instrument.created_at))
            .limit(30)
        )
        inst_res = await db.execute(inst_stmt)
        all_instruments = inst_res.scalars().all()

        watchlist_instrument_map: Dict[UUID, Instrument] = {}
        for inst in all_instruments:
            if inst.id not in portfolio_instrument_map and len(watchlist_instrument_map) < 15:
                watchlist_instrument_map[inst.id] = inst

        # 2b. Fetch recent briefing items for idempotency caching of Codex reasoning (last 48 hours)
        recent_ai_stmt = (
            select(BriefingItem)
            .where(
                BriefingItem.user_id == user_id,
                BriefingItem.created_at >= now - timedelta(hours=48),
            )
        )
        recent_ai_res = await db.execute(recent_ai_stmt)
        cached_enriched: Dict[Tuple[UUID, str], BriefingItem] = {}
        for bi in recent_ai_res.scalars().all():
            norm_h = re.sub(r"[^a-zA-Z0-9]", "", bi.headline.lower())
            if norm_h:
                cached_enriched[(bi.instrument_id, norm_h)] = bi

        # 3. Scan instruments using Finance live providers
        items_to_create: List[Dict[str, Any]] = []
        items_filtered = 0
        seen_headlines: Set[str] = set()

        scan_targets: List[Tuple[Instrument, bool]] = []
        for inst in portfolio_instrument_map.values():
            scan_targets.append((inst, True))
        for inst in watchlist_instrument_map.values():
            scan_targets.append((inst, False))

        for inst, is_portfolio in scan_targets:
            symbol = (inst.symbol or "").strip()
            if not symbol:
                continue

            cleaned_name = _clean_instrument_name(inst.name, symbol)
            inst_type = (
                inst.asset_type.value.lower()
                if hasattr(inst.asset_type, "value")
                else str(inst.asset_type or "equity").lower()
            )
            if inst_type == "stock":
                inst_type = "equity"

            inst_rec = InstrumentRecord(
                id=inst.id,
                symbol=symbol,
                name=cleaned_name,
                instrument_type=inst_type,
                venue=inst.exchange or "NASDAQ",
                currency=inst.currency or "USD",
                created_at=inst.created_at,
                updated_at=inst.updated_at,
            )

            raw_items: List[Dict[str, Any]] = []

            # A. Fetch news from GoogleNewsRSSProvider
            try:
                news_provider = GoogleNewsRSSProvider([inst_rec])
                # Fetch recent items within evidence window
                news_records = news_provider.get_recent_news(
                    inst_rec,
                    since=evidence_since,
                    until=now,
                    limit=5,
                )
                for nr in news_records:
                    raw_items.append({
                        "headline": nr.title,
                        "summary": nr.summary or nr.title,
                        "source": nr.source,
                        "url": nr.url,
                        "published_at": nr.published_at,
                        "source_quality": nr.source_quality,
                        "is_sec": False,
                    })
            except Exception as e:
                logger.debug("GoogleNewsRSSProvider fetch failed for %s: %s", symbol, e)

            # B. Fetch SEC filings for US equities
            venue_upper = (inst.exchange or "").upper()
            if venue_upper in {"NASDAQ", "NYSE", "BATS", "ARCA", "AMEX"}:
                try:
                    sec_user_agent = os.environ.get(
                        "II_SEC_USER_AGENT",
                        "PortfolioMind contact@portfoliomind.local",
                    )
                    sec_provider = SECDisclosureProvider([inst_rec], user_agent=sec_user_agent)
                    sec_records = sec_provider.get_recent_disclosures(
                        inst_rec,
                        since=evidence_since,
                        until=now,
                        limit=3,
                    )
                    for sr in sec_records:
                        raw_items.append({
                            "headline": f"{symbol} SEC {sr.disclosure_type}: Official Filing",
                            "summary": f"Official SEC {sr.disclosure_type} filing submitted on {sr.published_at.strftime('%Y-%m-%d')}. Document: {sr.title}",
                            "source": "SEC EDGAR",
                            "url": sr.url,
                            "published_at": sr.published_at,
                            "source_quality": sr.source_quality,
                            "is_sec": True,
                            "sec_form": sr.disclosure_type,
                        })
                except Exception as e:
                    logger.debug("SECDisclosureProvider fetch failed for %s: %s", symbol, e)

        # C. Check recent intelligence reviews
        reviews = []
        try:
            rev_stmt = (
                select(IntelligenceReview)
                .where(IntelligenceReview.instrument_id == inst.id)
                .order_by(IntelligenceReview.created_at.desc())
                .limit(2)
            )
            rev_res = await db.execute(rev_stmt)
            reviews = list(rev_res.scalars().all())
            for r in reviews:
                if r.human_brief:
                    raw_items.append({
                        "headline": f"{symbol} Protocol Review ({r.protocol})",
                        "summary": r.human_brief,
                        "source": "PortfolioMind Intelligence",
                        "url": None,
                        "published_at": r.created_at,
                        "source_quality": "PRIMARY",
                        "is_sec": False,
                        "is_review_brief": True,
                    })
        except Exception as e:
            logger.debug("Intelligence reviews query failed for %s: %s", symbol, e)

        # D. Classify and filter items
        for raw in raw_items:
            norm_headline = re.sub(r"[^a-zA-Z0-9]", "", raw["headline"].lower())
            if not norm_headline or norm_headline in seen_headlines:
                continue
            seen_headlines.add(norm_headline)

            cat, impact, materiality, horizon, thesis_impact, rev_req, why = _classify_development(
                raw["headline"],
                raw["summary"],
                is_portfolio,
                is_sec=raw.get("is_sec", False),
                sec_form=raw.get("sec_form"),
                symbol=symbol,
            )

            # Filter low-materiality noise
            if materiality == BriefingMateriality.LOW:
                items_filtered += 1
                continue

            # Base metadata
            source_meta: Dict[str, Any] = {
                "source": raw.get("source"),
                "url": raw.get("url"),
                "source_quality": raw.get("source_quality"),
                "is_sec": raw.get("is_sec", False),
                "sec_form": raw.get("sec_form"),
                "reasoning_source": "DETERMINISTIC",
            }

            cached_item = cached_enriched.get((inst.id, norm_headline))
            if cached_item and cached_item.source_metadata:
                # Carry over formal review metadata across overlapping runs
                for rev_key in ("review_status", "triggered_review_id", "triggered_protocol", "review_summary", "review_error", "triggered_at", "decision_resolved"):
                    if rev_key in cached_item.source_metadata:
                        source_meta[rev_key] = cached_item.source_metadata[rev_key]

            # Selective Codex reasoning for HIGH, CRITICAL, or review_required
            if (materiality in (BriefingMateriality.HIGH, BriefingMateriality.CRITICAL) or rev_req is True) and not raw.get("is_review_brief"):
                if cached_item and cached_item.source_metadata and cached_item.source_metadata.get("reasoning_source") in ("CODEX", "CODEX_CACHED"):
                    # Idempotency: reuse previously enriched assessment
                    impact = cached_item.impact
                    materiality = cached_item.materiality
                    horizon = cached_item.time_horizon
                    thesis_impact = cached_item.thesis_impact
                    rev_req = cached_item.review_required
                    why = cached_item.why_it_matters
                    source_meta["reasoning_source"] = "CODEX_CACHED"
                    source_meta["reasoning_confidence"] = cached_item.source_metadata.get("reasoning_confidence")
                    source_meta["recommended_review"] = cached_item.source_metadata.get("recommended_review")
                    source_meta["reasoning_generated_at"] = cached_item.source_metadata.get("reasoning_generated_at")
                else:
                    try:
                        active_reasoner = reasoner or (BriefingReasoner() if BriefingReasoner else None)
                        if active_reasoner is not None:
                            inst_ctx = {
                                "symbol": symbol,
                                "name": inst.name,
                                "asset_type": inst_type,
                                "exchange": inst.exchange,
                                "currency": inst.currency,
                                "is_portfolio": is_portfolio,
                            }

                            state_ctx = None
                            if getattr(inst, "intelligence_state", None):
                                st = inst.intelligence_state
                                state_ctx = {
                                    "thesis_status": st.thesis_status.value if hasattr(st.thesis_status, "value") else str(st.thesis_status),
                                    "valuation_status": st.valuation_status.value if hasattr(st.valuation_status, "value") else str(st.valuation_status),
                                    "recommendation": st.recommendation.value if hasattr(st.recommendation, "value") else str(st.recommendation),
                                    "confidence": getattr(st, "confidence", None),
                                    "last_review_at": st.last_review_at.isoformat() if st.last_review_at else None,
                                }

                            review_ctx = None
                            if reviews:
                                lr = reviews[0]
                                review_ctx = {
                                    "protocol": lr.protocol,
                                    "confidence": lr.confidence,
                                    "human_brief": lr.human_brief,
                                    "key_assumptions": lr.machine_record.get("key_assumptions") if lr.machine_record else None,
                                    "growth_drivers": lr.machine_record.get("growth_drivers") if lr.machine_record else None,
                                    "key_risks": lr.machine_record.get("key_risks") if lr.machine_record else None,
                                }

                            event_ctx = {
                                "headline": raw["headline"],
                                "summary": raw["summary"],
                                "source": raw.get("source"),
                                "url": raw.get("url"),
                                "published_at": raw["published_at"].isoformat() if raw.get("published_at") else None,
                                "sec_form": raw.get("sec_form"),
                                "category": cat.value if hasattr(cat, "value") else str(cat),
                                "materiality": materiality.value if hasattr(materiality, "value") else str(materiality),
                            }

                            assessment = active_reasoner.assess_event(
                                instrument=inst_ctx,
                                intelligence_state=state_ctx,
                                latest_review=review_ctx,
                                event=event_ctx,
                            )

                            if assessment.impact in BriefingImpact.__members__:
                                impact = BriefingImpact(assessment.impact)
                            if assessment.materiality in BriefingMateriality.__members__:
                                materiality = BriefingMateriality(assessment.materiality)
                            if assessment.time_horizon in BriefingTimeHorizon.__members__:
                                horizon = BriefingTimeHorizon(assessment.time_horizon)
                            if assessment.thesis_impact in BriefingThesisImpact.__members__:
                                thesis_impact = BriefingThesisImpact(assessment.thesis_impact)

                            rev_req = assessment.review_required
                            why = assessment.why_it_matters

                            source_meta["reasoning_source"] = "CODEX"
                            source_meta["reasoning_confidence"] = assessment.confidence
                            source_meta["recommended_review"] = assessment.recommended_review
                            source_meta["reasoning_generated_at"] = now.isoformat()

                    except Exception as e:
                        logger.warning(
                            "Codex reasoning failed for %s (%s); retaining deterministic classification: %s",
                            symbol,
                            raw["headline"][:40],
                            e,
                        )
                        source_meta["reasoning_source"] = "DETERMINISTIC_FALLBACK"
                        source_meta["reasoning_fallback_reason"] = f"{type(e).__name__}: {e}"

            items_to_create.append({
                "instrument_id": inst.id,
                "headline": raw["headline"][:255],
                "summary": raw["summary"],
                "why_it_matters": why,
                "impact": impact,
                "materiality": materiality,
                "time_horizon": horizon,
                "thesis_impact": thesis_impact,
                "review_required": rev_req,
                "category": cat,
                "source_metadata": source_meta,
                "is_portfolio": is_portfolio,
                "published_at": raw.get("published_at"),
            })

        # 4. Save BriefingRun
        briefing_run = BriefingRun(
            user_id=user_id,
            generated_at=now,
            scope=scope,
            status="COMPLETED",
            trigger_type=trigger_type,
            items_found=len(items_to_create) + items_filtered,
            items_shown=len(items_to_create),
            items_filtered=items_filtered,
        )
        db.add(briefing_run)
        await db.flush()

        for item_data in items_to_create:
            item = BriefingItem(
                briefing_run_id=briefing_run.id,
                user_id=user_id,
                **item_data,
            )
            db.add(item)

        await db.commit()
        await db.refresh(briefing_run)

        # Re-fetch with joined relations
        return await get_latest_briefing_run(db, user_id)  # type: ignore[return-value]
    finally:
        async with _briefing_generation_lock:
            _active_generating_users.discard(user_id)
