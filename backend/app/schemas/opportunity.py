"""Pydantic schemas for Watchlist and Opportunity Assessment."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.asset import AssetType
from app.models.opportunity import (
    OpportunityConfidence,
    OpportunityDriver,
    OpportunityStatus,
    ResearchFreshness,
    ResearchStage,
    SuggestedNextStep,
    ValuationSignal,
    WatchlistPriority,
)
from app.schemas.instrument import InstrumentResponse


class OpportunityAssessmentResponse(BaseModel):
    """Structured opportunity assessment result for an instrument."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    instrument_id: uuid.UUID
    status: OpportunityStatus
    reason: str
    primary_driver: OpportunityDriver
    valuation_signal: ValuationSignal
    research_freshness: ResearchFreshness
    suggested_next_step: SuggestedNextStep
    confidence: OpportunityConfidence
    source_references: Optional[Dict[str, Any]] = None
    assessment_at: datetime
    created_at: datetime


class WatchlistItemResponse(BaseModel):
    """Enriched watchlist item response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    instrument_id: uuid.UUID
    research_stage: ResearchStage
    priority: WatchlistPriority
    why_interesting: Optional[str] = None
    target_entry_min: Optional[Decimal] = None
    target_entry_max: Optional[Decimal] = None
    key_catalyst: Optional[str] = None
    key_risk: Optional[str] = None
    next_expected_event: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    instrument: Optional[InstrumentResponse] = None
    current_price: Optional[float] = None
    current_price_currency: Optional[str] = None
    opportunity: Optional[OpportunityAssessmentResponse] = None


class WatchlistItemCreateRequest(BaseModel):
    """Request to track an instrument on the watchlist / research pipeline."""

    instrument_id: Optional[uuid.UUID] = None
    name: Optional[str] = Field(default=None, max_length=255)
    symbol: Optional[str] = Field(default=None, max_length=50)
    asset_type: Optional[AssetType] = None
    exchange: Optional[str] = Field(default=None, max_length=50)
    currency: Optional[str] = Field(default=None, max_length=3)

    research_stage: ResearchStage = ResearchStage.DISCOVERED
    priority: WatchlistPriority = WatchlistPriority.MEDIUM
    why_interesting: Optional[str] = None
    target_entry_min: Optional[Decimal] = None
    target_entry_max: Optional[Decimal] = None
    key_catalyst: Optional[str] = None
    key_risk: Optional[str] = None
    next_expected_event: Optional[str] = None
    notes: Optional[str] = None


class WatchlistItemUpdateRequest(BaseModel):
    """Request to update a watchlist candidate."""

    research_stage: Optional[ResearchStage] = None
    priority: Optional[WatchlistPriority] = None
    why_interesting: Optional[str] = None
    target_entry_min: Optional[Decimal] = None
    target_entry_max: Optional[Decimal] = None
    key_catalyst: Optional[str] = None
    key_risk: Optional[str] = None
    next_expected_event: Optional[str] = None
    notes: Optional[str] = None


class OpportunityEvaluationRequest(BaseModel):
    """Request payload to trigger opportunity evaluation."""

    instrument_id: Optional[uuid.UUID] = None
    force_refresh: bool = False


class OpportunityEvaluationSummary(BaseModel):
    """Summary of an opportunity evaluation cycle."""

    total_candidates: int
    evaluated: int
    opportunities_found: int
    research_now_count: int
    research_soon_count: int
    items: List[OpportunityAssessmentResponse]


class ResearchQueueItemResponse(BaseModel):
    """Item formatted for the research queue."""

    instrument_id: uuid.UUID
    symbol: Optional[str] = None
    name: str
    asset_type: str
    exchange: Optional[str] = None
    research_stage: ResearchStage
    priority: WatchlistPriority
    opportunity_status: OpportunityStatus
    primary_driver: OpportunityDriver
    suggested_next_step: SuggestedNextStep
    reason: str
    confidence: OpportunityConfidence
    current_price: Optional[float] = None
    current_price_currency: Optional[str] = None
    target_entry_min: Optional[Decimal] = None
    target_entry_max: Optional[Decimal] = None
    research_freshness: ResearchFreshness
    valuation_signal: ValuationSignal
    last_review_at: Optional[datetime] = None
    assessment_at: datetime


class ResearchQueueResponse(BaseModel):
    """Prioritized Research Queue response."""

    research_now: List[ResearchQueueItemResponse]
    research_soon: List[ResearchQueueItemResponse]
    waiting: List[ResearchQueueItemResponse]
    no_action: List[ResearchQueueItemResponse]
    stage_counts: Dict[str, int]
    total_candidates: int
