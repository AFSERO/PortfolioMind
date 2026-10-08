"""Schemas for Intelligence Briefing."""

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.briefing import (
    BriefingCategory,
    BriefingImpact,
    BriefingMateriality,
    BriefingThesisImpact,
    BriefingTimeHorizon,
    BriefingTriggerType,
)


class BriefingItemResponse(BaseModel):
    """Briefing item representing an individual intelligence event."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    briefing_run_id: UUID
    user_id: UUID
    instrument_id: UUID
    headline: str
    summary: str
    why_it_matters: str
    impact: BriefingImpact
    materiality: BriefingMateriality
    time_horizon: BriefingTimeHorizon
    thesis_impact: BriefingThesisImpact
    review_required: bool
    category: BriefingCategory
    source_metadata: Optional[dict[str, Any]] = None
    is_portfolio: bool
    published_at: Optional[datetime] = None
    created_at: datetime

    # Display convenience fields
    instrument_symbol: Optional[str] = None
    instrument_name: Optional[str] = None
    # Attention state: 'NONE', 'OPEN', 'REVIEWED_BUT_STILL_REQUIRES_ATTENTION', 'DECISION_REQUIRED', 'RESOLVED'
    attention_state: str = "NONE"


class BriefingRunResponse(BaseModel):
    """Briefing run execution response with included items."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    generated_at: datetime
    scope: str
    status: str
    trigger_type: BriefingTriggerType = BriefingTriggerType.MANUAL
    items_found: int
    items_shown: int
    items_filtered: int
    created_at: datetime
    items: List[BriefingItemResponse] = []


class BriefingGenerateRequest(BaseModel):
    """Request payload to trigger briefing generation."""

    scope: str = "PORTFOLIO_AND_WATCHLIST"
    force_refresh: bool = False


class BriefingReviewActionRequest(BaseModel):
    """Request payload to trigger a formal review for a briefing item."""

    force_rerun: bool = False


class BriefingReviewStatusResponse(BaseModel):
    """Status and result summary of a formal review triggered by a briefing item."""

    model_config = ConfigDict(from_attributes=True)

    status: str
    review_id: Optional[UUID] = None
    protocol: Optional[str] = None
    summary: Optional[dict[str, Any]] = None
    reused: bool = False
    error: Optional[str] = None
