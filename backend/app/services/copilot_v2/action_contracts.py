"""Typed action proposal contracts and schemas for Copilot V2 Phase 3.

Enforces:
1. Strict type checking and validation on all model-generated action proposals.
2. Positive quantity (> 0) and non-negative price (>= 0).
3. Clear separation between PROPOSAL creation and DETERMINISTIC backend execution.
4. Product Boundary: All mutations are internal PortfolioMind bookkeeping records, NOT broker orders.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Configurable lazy proposal expiration TTL (default 24 hours)
ACTION_PROPOSAL_TTL = timedelta(hours=24)


class ActionProposalType(str, Enum):
    """Allowed proposal types for Copilot V2 Phase 3."""

    TRANSACTION_RECORD = "TRANSACTION_RECORD"
    WATCHLIST_CHANGE = "WATCHLIST_CHANGE"
    DECISION_NOTE = "DECISION_NOTE"


class ActionProposalStatusV2(str, Enum):
    """Lifecycle statuses for Copilot V2 action proposals."""

    PENDING = "PENDING"
    READY_FOR_CONFIRMATION = "READY_FOR_CONFIRMATION"
    EXECUTED = "EXECUTED"
    APPLIED = "APPLIED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    STALE = "STALE"
    FAILED = "FAILED"


class TransactionProposalParams(BaseModel):
    """Parameters for recording an internal portfolio transaction (bookkeeping)."""

    symbol: str = Field(..., description="Canonical asset symbol (e.g. THF, THYAO.IS, BTC)")
    name: Optional[str] = Field(None, description="Canonical instrument name")
    transaction_type: str = Field(..., description="'BUY' or 'SELL'")
    quantity: Decimal = Field(..., description="Quantity of units (must be > 0)")
    price: Decimal = Field(..., description="Unit price (must be >= 0)")
    currency: str = Field(default="TRY", description="Currency code (e.g. TRY, USD)")
    transaction_date: str = Field(default_factory=lambda: str(date.today()), description="ISO date (YYYY-MM-DD)")
    notes: Optional[str] = Field(None, description="User note or rationale")
    affects_cash: bool = Field(default=True, description="Whether transaction adjusts cash balance")
    asset_id: Optional[str] = Field(None, description="ID of existing Asset if owned")
    instrument_id: Optional[str] = Field(None, description="Canonical Instrument ID")

    @field_validator("transaction_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        upper = v.upper()
        if upper not in ("BUY", "SELL"):
            raise ValueError(f"Invalid transaction_type '{v}'. Must be 'BUY' or 'SELL'.")
        return upper

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0"):
            raise ValueError("Quantity must be greater than 0.")
        return v

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: Decimal) -> Decimal:
        if v < Decimal("0"):
            raise ValueError("Price must be greater than or equal to 0.")
        return v

    model_config = ConfigDict(extra="ignore")


class WatchlistProposalParams(BaseModel):
    """Parameters for modifying a watchlist candidate."""

    symbol: str = Field(..., description="Canonical symbol")
    name: Optional[str] = Field(None, description="Canonical instrument name")
    action: str = Field(..., description="'ADD' or 'REMOVE'")
    priority: str = Field(default="MEDIUM", description="'LOW', 'MEDIUM', or 'HIGH'")
    notes: Optional[str] = Field(None, description="Notes on why instrument is tracked")
    instrument_id: Optional[str] = Field(None, description="Canonical Instrument ID")

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        upper = v.upper()
        if upper not in ("ADD", "REMOVE"):
            raise ValueError(f"Invalid watchlist action '{v}'. Must be 'ADD' or 'REMOVE'.")
        return upper

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        upper = v.upper()
        if upper not in ("LOW", "MEDIUM", "HIGH"):
            return "MEDIUM"
        return upper

    model_config = ConfigDict(extra="ignore")


class DecisionNoteProposalParams(BaseModel):
    """Parameters for logging a formal rationale or note in the decision log."""

    title: str = Field(..., min_length=1, description="Short summary title of the decision note")
    notes: str = Field(..., min_length=1, description="Rationale or detailed thesis note")
    symbol: Optional[str] = Field(None, description="Related asset symbol if applicable")
    instrument_id: Optional[str] = Field(None, description="Related canonical Instrument ID")
    event_type: str = Field(default="NOTE", description="Decision event type (NOTE, THESIS_UPDATE, REVIEW)")
    expectation: Optional[str] = Field(None, description="Expected outcome or target timeframe")
    confidence: Optional[str] = Field(None, description="Confidence level (HIGH, MEDIUM, LOW)")

    model_config = ConfigDict(extra="ignore")
