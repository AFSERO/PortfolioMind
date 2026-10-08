"""Pydantic schemas for Investment Intelligence state, reviews, and technical plans."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.intelligence import (
    ExecutionStatus,
    FundQuality,
    ProtocolRunStatus,
    Recommendation,
    TechnicalStatus,
    ThesisStatus,
    ValuationStatus,
)


class IntelligenceStateResponse(BaseModel):
    """Public representation of the latest intelligence state of an Instrument."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    instrument_id: uuid.UUID
    thesis_status: Optional[ThesisStatus] = None
    valuation_status: Optional[ValuationStatus] = None
    technical_status: Optional[TechnicalStatus] = None
    recommendation: Optional[Recommendation] = None
    execution_status: Optional[ExecutionStatus] = None
    last_review_at: Optional[datetime] = None
    last_monitoring_at: Optional[datetime] = None
    next_review_at: Optional[datetime] = None
    human_brief: Optional[str] = None
    confidence: Optional[str] = None
    confidence_score: Optional[int] = None
    confidence_level: Optional[str] = None
    recovery_value_confidence: Optional[str] = None
    execution_confidence: Optional[str] = None
    data_quality_score: Optional[int] = None
    primary_reason: Optional[str] = None
    supporting_reasons: Optional[list[str]] = None
    key_risks: Optional[list[str]] = None
    what_would_change_my_view: Optional[str] = None
    evidence_gaps: Optional[list[str]] = None
    review_required_reason: Optional[str] = None
    assessment_type: Optional[str] = None
    asset_class_assessment: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class IntelligenceStateUpsertRequest(BaseModel):
    """Schema for creating or updating current intelligence state."""

    thesis_status: Optional[ThesisStatus] = None
    valuation_status: Optional[ValuationStatus] = None
    technical_status: Optional[TechnicalStatus] = None
    recommendation: Optional[Recommendation] = None
    execution_status: Optional[ExecutionStatus] = None
    last_review_at: Optional[datetime] = None
    last_monitoring_at: Optional[datetime] = None
    next_review_at: Optional[datetime] = None
    human_brief: Optional[str] = None
    confidence: Optional[str] = None
    confidence_score: Optional[int] = None
    confidence_level: Optional[str] = None
    recovery_value_confidence: Optional[str] = None
    execution_confidence: Optional[str] = None
    data_quality_score: Optional[int] = None
    primary_reason: Optional[str] = None
    supporting_reasons: Optional[list[str]] = None
    key_risks: Optional[list[str]] = None
    what_would_change_my_view: Optional[str] = None
    evidence_gaps: Optional[list[str]] = None
    review_required_reason: Optional[str] = None
    assessment_type: Optional[str] = None
    asset_class_assessment: Optional[dict[str, Any]] = None


class IntelligenceReviewResponse(BaseModel):
    """Public representation of a historical intelligence review record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    instrument_id: uuid.UUID
    protocol: str
    run_type: Optional[str] = None
    status: ProtocolRunStatus
    machine_record: Optional[dict[str, Any]] = None
    human_brief: Optional[str] = None
    confidence: Optional[str] = None
    research_path: Optional[str] = None
    source_run_id: Optional[str] = None
    created_at: datetime
    state_updated: bool = False


class IntelligenceReviewCreateRequest(BaseModel):
    """Schema for adding a protocol review run to history."""

    protocol: str = Field(min_length=1, max_length=128)
    run_type: Optional[str] = Field(default=None, max_length=64)
    status: ProtocolRunStatus = ProtocolRunStatus.COMPLETED
    machine_record: Optional[dict[str, Any]] = None
    human_brief: Optional[str] = None
    confidence: Optional[str] = Field(default=None, max_length=32)
    research_path: Optional[str] = None
    source_run_id: Optional[str] = Field(default=None, max_length=128)
    auto_apply_state: bool = Field(
        default=False,
        description="If True, updates current IntelligenceState with fields from this review.",
    )
    is_synthetic: bool = Field(
        default=False,
        description="If True, marks review as synthetic/mock generated.",
    )


class TechnicalPlanResponse(BaseModel):
    """Public representation of a technical plan."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    instrument_id: uuid.UUID
    reference_at: datetime
    reference_price: Optional[float] = None
    trend_expectation: Optional[str] = None
    entry_zones: Optional[List[Any]] = None
    support_zones: Optional[List[Any]] = None
    resistance_zones: Optional[List[Any]] = None
    review_or_invalidation_zones: Optional[List[Any]] = None
    profit_taking_or_reassessment_zones: Optional[List[Any]] = None
    notes: Optional[str] = None
    active: bool
    created_at: datetime
    updated_at: datetime


class TechnicalPlanCreateRequest(BaseModel):
    """Schema for creating or replacing an active technical plan."""

    reference_at: Optional[datetime] = None
    reference_price: Optional[Decimal] = None
    trend_expectation: Optional[str] = None
    entry_zones: Optional[List[Any]] = None
    support_zones: Optional[List[Any]] = None
    resistance_zones: Optional[List[Any]] = None
    review_or_invalidation_zones: Optional[List[Any]] = None
    profit_taking_or_reassessment_zones: Optional[List[Any]] = None
    notes: Optional[str] = None
    active: bool = True
