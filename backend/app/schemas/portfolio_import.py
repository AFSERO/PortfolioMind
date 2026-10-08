"""Pydantic schemas for Portfolio Import and Opening Positions."""

from datetime import date, datetime
from decimal import Decimal
import enum
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ImportSourceType(str, enum.Enum):
    NATURAL_LANGUAGE = "NATURAL_LANGUAGE"
    SCREENSHOT = "SCREENSHOT"
    CSV = "CSV"
    MANUAL = "MANUAL"


class ImportBatchStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PARSED = "PARSED"
    READY_FOR_CONFIRMATION = "READY_FOR_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    APPLIED = "APPLIED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class ImportItemAction(str, enum.Enum):
    CREATE_OPENING_POSITION = "CREATE_OPENING_POSITION"
    UPDATE_EXISTING_OPENING_POSITION = "UPDATE_EXISTING_OPENING_POSITION"
    ADD_TO_EXISTING_POSITION = "ADD_TO_EXISTING_POSITION"
    SKIP = "SKIP"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    AMBIGUOUS = "AMBIGUOUS"


class ActionResolutionType(str, enum.Enum):
    REPLACE_OPENING_STATE = "REPLACE_OPENING_STATE"
    ADD_TO_EXISTING = "ADD_TO_EXISTING"
    SKIP = "SKIP"


class CandidateInstrumentSchema(BaseModel):
    id: UUID
    symbol: Optional[str] = None
    name: str
    asset_type: str
    exchange: Optional[str] = None
    currency: Optional[str] = None


class PortfolioImportItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    batch_id: UUID
    raw_input: str
    resolved_instrument_id: Optional[UUID] = None
    asset_type: str
    symbol: Optional[str] = None
    name: str
    quantity: Optional[float] = None
    market_value: Optional[float] = None
    average_cost: Optional[float] = None
    total_cost: Optional[float] = None
    currency: Optional[str] = None
    as_of_date: Optional[date] = None
    semantic_fields: Optional[dict[str, Any]] = None
    confidence: Optional[float] = None
    existing_asset_id: Optional[UUID] = None
    existing_quantity: Optional[float] = None
    intended_action: ImportItemAction
    action_resolution: Optional[ActionResolutionType] = None
    warnings: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    candidate_instruments: Optional[List[CandidateInstrumentSchema]] = None
    resulting_asset_id: Optional[UUID] = None
    resulting_opening_position_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class PortfolioImportBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    conversation_id: Optional[UUID] = None
    proposal_id: Optional[UUID] = None
    source_type: ImportSourceType
    source_reference: Optional[str] = None
    status: ImportBatchStatus
    raw_content_preview: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    idempotency_key: str
    created_at: datetime
    parsed_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None
    items: List[PortfolioImportItemResponse] = Field(default_factory=list)
    ready_count: int = 0
    needs_review_count: int = 0
    ambiguous_count: int = 0


class ImportItemResolutionRequest(BaseModel):
    quantity: Optional[Decimal] = Field(default=None, gt=0, max_digits=18, decimal_places=6)
    average_cost: Optional[Decimal] = Field(default=None, ge=0, max_digits=18, decimal_places=6)
    total_cost: Optional[Decimal] = Field(default=None, ge=0, max_digits=18, decimal_places=6)
    currency: Optional[str] = Field(default=None, pattern=r"^[A-Z]{3}$")
    action_resolution: Optional[ActionResolutionType] = None
    selected_instrument_id: Optional[UUID] = None


class PortfolioImportConfirmRequest(BaseModel):
    idempotency_key: Optional[str] = None


class OpeningPositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    asset_id: UUID
    quantity: float
    as_of_date: date
    cost_basis_known: bool
    average_cost: Optional[float] = None
    cost_currency: Optional[str] = None
    total_cost: Optional[float] = None
    has_incomplete_history: bool
    source: str
    provenance: Optional[dict[str, Any]] = None
    notes: Optional[str] = None
    import_batch_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
