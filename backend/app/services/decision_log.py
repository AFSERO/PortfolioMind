"""Decision Log service — records, updates, and queries investment decisions and thesis revisions."""

from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.asset import Asset
from app.models.decision_log import DecisionEventType, DecisionLogEntry
from app.models.instrument import Instrument
from app.schemas.decision_log import DecisionLogCreate, DecisionLogResponse, DecisionLogUpdateRationale


def _entry_to_response(entry: DecisionLogEntry) -> DecisionLogResponse:
    """Helper to convert a DecisionLogEntry ORM model to DecisionLogResponse with joined details."""
    symbol = entry.instrument.symbol if entry.instrument else None
    inst_name = entry.instrument.name if entry.instrument else None
    asset_name = entry.asset.name if entry.asset else None

    # Fallback to asset symbol/name if instrument relation is direct or via asset
    if not symbol and entry.asset:
        symbol = entry.asset.symbol

    return DecisionLogResponse(
        id=entry.id,
        user_id=entry.user_id,
        instrument_id=entry.instrument_id,
        asset_id=entry.asset_id,
        event_type=entry.event_type,
        title=entry.title,
        summary=entry.summary,
        user_rationale=entry.user_rationale,
        confidence=entry.confidence,
        expectation=entry.expectation,
        related_review_id=entry.related_review_id,
        related_transaction_id=entry.related_transaction_id,
        metadata_=entry.metadata_,
        occurred_at=entry.occurred_at,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        instrument_symbol=symbol,
        instrument_name=inst_name,
        asset_name=asset_name,
    )


async def create_decision_log_entry(
    db: AsyncSession,
    user_id: UUID,
    payload: DecisionLogCreate,
) -> DecisionLogResponse:
    """Manually record a decision entry."""
    entry = DecisionLogEntry(
        user_id=user_id,
        instrument_id=payload.instrument_id,
        asset_id=payload.asset_id,
        event_type=payload.event_type,
        title=payload.title,
        summary=payload.summary,
        user_rationale=payload.user_rationale,
        confidence=payload.confidence,
        expectation=payload.expectation,
        metadata_=payload.metadata,
        occurred_at=payload.occurred_at or datetime.now(timezone.utc),
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)

    # Re-fetch with eager loaded relationships
    return await get_decision_log_entry(db, user_id, entry.id)  # type: ignore[return-value]


async def log_decision_event(
    db: AsyncSession,
    user_id: UUID,
    event_type: DecisionEventType,
    title: str,
    summary: str,
    instrument_id: Optional[UUID] = None,
    asset_id: Optional[UUID] = None,
    user_rationale: Optional[str] = None,
    confidence: Optional[str] = None,
    expectation: Optional[str] = None,
    related_review_id: Optional[UUID] = None,
    related_transaction_id: Optional[UUID] = None,
    metadata: Optional[dict[str, Any]] = None,
    occurred_at: Optional[datetime] = None,
) -> DecisionLogEntry:
    """Internal helper to automatically log system decision events."""
    entry = DecisionLogEntry(
        user_id=user_id,
        instrument_id=instrument_id,
        asset_id=asset_id,
        event_type=event_type,
        title=title,
        summary=summary,
        user_rationale=user_rationale,
        confidence=confidence,
        expectation=expectation,
        related_review_id=related_review_id,
        related_transaction_id=related_transaction_id,
        metadata_=metadata,
        occurred_at=occurred_at or datetime.now(timezone.utc),
    )
    db.add(entry)
    await db.flush()
    return entry


async def get_decision_log_entries(
    db: AsyncSession,
    user_id: UUID,
    instrument_id: Optional[UUID] = None,
    asset_id: Optional[UUID] = None,
    event_type: Optional[DecisionEventType] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[DecisionLogResponse], int]:
    """Retrieve decision log entries for a user with optional filtering and pagination."""
    query = (
        select(DecisionLogEntry)
        .options(
            selectinload(DecisionLogEntry.instrument),
            selectinload(DecisionLogEntry.asset),
        )
        .where(DecisionLogEntry.user_id == user_id)
    )

    count_query = (
        select(func.count(DecisionLogEntry.id))
        .where(DecisionLogEntry.user_id == user_id)
    )

    if instrument_id is not None:
        query = query.where(DecisionLogEntry.instrument_id == instrument_id)
        count_query = count_query.where(DecisionLogEntry.instrument_id == instrument_id)

    if asset_id is not None:
        query = query.where(DecisionLogEntry.asset_id == asset_id)
        count_query = count_query.where(DecisionLogEntry.asset_id == asset_id)

    if event_type is not None:
        query = query.where(DecisionLogEntry.event_type == event_type)
        count_query = count_query.where(DecisionLogEntry.event_type == event_type)

    query = (
        query.order_by(
            DecisionLogEntry.occurred_at.desc(),
            DecisionLogEntry.created_at.desc(),
        )
        .limit(limit)
        .offset(offset)
    )

    total_res = await db.execute(count_query)
    total = total_res.scalar_one() or 0

    results = await db.execute(query)
    entries = results.scalars().all()

    return [_entry_to_response(e) for e in entries], total


async def get_decision_log_entry(
    db: AsyncSession,
    user_id: UUID,
    entry_id: UUID,
) -> Optional[DecisionLogResponse]:
    """Retrieve a single decision log entry by ID."""
    stmt = (
        select(DecisionLogEntry)
        .options(
            selectinload(DecisionLogEntry.instrument),
            selectinload(DecisionLogEntry.asset),
        )
        .where(
            DecisionLogEntry.id == entry_id,
            DecisionLogEntry.user_id == user_id,
        )
    )
    result = await db.execute(stmt)
    entry = result.scalar_one_or_none()
    if not entry:
        return None
    return _entry_to_response(entry)


async def update_user_rationale(
    db: AsyncSession,
    user_id: UUID,
    entry_id: UUID,
    payload: DecisionLogUpdateRationale,
) -> Optional[DecisionLogResponse]:
    """Update user rationale and optional confidence/expectation on an existing decision."""
    stmt = (
        select(DecisionLogEntry)
        .options(
            selectinload(DecisionLogEntry.instrument),
            selectinload(DecisionLogEntry.asset),
        )
        .where(
            DecisionLogEntry.id == entry_id,
            DecisionLogEntry.user_id == user_id,
        )
    )
    result = await db.execute(stmt)
    entry = result.scalar_one_or_none()
    if not entry:
        return None

    entry.user_rationale = payload.user_rationale
    if payload.confidence is not None:
        entry.confidence = payload.confidence
    if payload.expectation is not None:
        entry.expectation = payload.expectation

    await db.commit()
    await db.refresh(entry)
    return _entry_to_response(entry)
