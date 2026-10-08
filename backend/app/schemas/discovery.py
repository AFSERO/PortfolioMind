"""Pydantic schemas for Discovery Engine v1."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DiscoverySignalSchema(BaseModel):
    type: str
    label: str
    detail: str
    data: Optional[Dict[str, Any]] = None


class DiscoveryCandidateResponse(BaseModel):
    id: UUID
    run_id: UUID
    instrument_id: UUID
    symbol: Optional[str] = None
    name: Optional[str] = None
    asset_type: Optional[str] = None
    exchange: Optional[str] = None
    currency: Optional[str] = None
    status: str
    candidate_state: str
    primary_reason: str
    signals: List[Dict[str, Any]] = Field(default_factory=list)
    key_question: Optional[str] = None
    key_risk: Optional[str] = None
    suggested_next_step: str
    confidence: str
    score_band: Optional[str] = None
    current_price: Optional[float] = None
    current_price_currency: Optional[str] = None
    market_data_snapshot: Dict[str, Any] = Field(default_factory=dict)
    source_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class DiscoveryRunResponse(BaseModel):
    id: UUID
    universe: str
    trigger_type: str
    status: str
    instruments_scanned: int
    candidates_filtered: int
    candidates_reasoned: int
    candidates_surfaced: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    candidates: List[DiscoveryCandidateResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class TriggerScanRequest(BaseModel):
    universe: Optional[str] = "US_LARGE_CAP"
    force_refresh: Optional[bool] = False


class ActionResponse(BaseModel):
    status: str
    message: str
    candidate_id: UUID
    extra: Optional[Dict[str, Any]] = None
