"""Schemas for Decision Log."""

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.decision_log import DecisionEventType


class DecisionLogCreate(BaseModel):
    """Schema for manually creating a decision note or logging a decision."""

    instrument_id: Optional[UUID] = None
    asset_id: Optional[UUID] = None
    event_type: DecisionEventType = DecisionEventType.MANUAL_DECISION_NOTE
    title: str = Field(..., min_length=1, max_length=255)
    summary: str = Field(..., min_length=1)
    user_rationale: Optional[str] = None
    confidence: Optional[str] = None
    expectation: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    occurred_at: Optional[datetime] = None


class DecisionLogUpdateRationale(BaseModel):
    """Schema for editing the user's reasoning/rationale on an existing decision entry."""

    user_rationale: str = Field(..., min_length=1)
    confidence: Optional[str] = None
    expectation: Optional[str] = None


class DecisionLogResponse(BaseModel):
    """Full decision log entry response."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    user_id: UUID
    instrument_id: Optional[UUID] = None
    asset_id: Optional[UUID] = None
    event_type: DecisionEventType
    title: str
    summary: str
    user_rationale: Optional[str] = None
    confidence: Optional[str] = None
    expectation: Optional[str] = None
    related_review_id: Optional[UUID] = None
    related_transaction_id: Optional[UUID] = None
    metadata: Optional[dict[str, Any]] = Field(None, alias="metadata_")
    occurred_at: datetime
    created_at: datetime
    updated_at: datetime

    # Display convenience fields
    instrument_symbol: Optional[str] = None
    instrument_name: Optional[str] = None
    asset_name: Optional[str] = None


class DecisionLogListResponse(BaseModel):
    """Paginated or listed decision log response."""

    items: List[DecisionLogResponse]
    total: int
