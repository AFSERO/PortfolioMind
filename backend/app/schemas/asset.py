import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.asset import AssetType
from app.schemas.instrument import InstrumentResponse
from app.schemas.transaction import TransactionCreateRequest


class AssetCreateRequest(BaseModel):
    asset_type: AssetType
    symbol: Optional[str] = None
    name: str = Field(min_length=1, max_length=255)
    current_price: Optional[Decimal] = Field(
        default=None, ge=0, max_digits=18, decimal_places=6
    )
    current_price_currency: Optional[str] = Field(default=None, max_length=3)
    is_manual_price: bool = False
    notes: Optional[str] = None
    instrument_id: Optional[uuid.UUID] = None
    exchange: Optional[str] = None
    initial_transaction: Optional[TransactionCreateRequest] = None


class AssetUpdateRequest(BaseModel):
    """All fields optional — only provided fields are updated."""

    asset_type: Optional[AssetType] = None
    symbol: Optional[str] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    current_price: Optional[Decimal] = Field(
        default=None, ge=0, max_digits=18, decimal_places=6
    )
    current_price_currency: Optional[str] = Field(default=None, max_length=3)
    is_manual_price: Optional[bool] = None
    notes: Optional[str] = None
    instrument_id: Optional[uuid.UUID] = None
    exchange: Optional[str] = None


class AssetPriceUpdateRequest(BaseModel):
    """For POST /assets/{id}/update-price (manual price override)."""

    current_price: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    current_price_currency: str = Field(max_length=3)


class AssetResponse(BaseModel):
    """Public representation returned by all asset endpoints.

    Built from an (Asset, stats_dict) pair via :meth:`from_asset`.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    instrument_id: Optional[uuid.UUID] = None
    instrument: Optional[InstrumentResponse] = None
    asset_type: AssetType
    symbol: Optional[str]
    name: str
    current_price: Optional[float]
    current_price_currency: Optional[str]
    is_manual_price: bool
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    # Computed from transactions
    total_quantity: float
    avg_cost: Optional[float]
    avg_cost_currency: Optional[str]
    total_cost: Optional[float]
    realized_pl: Optional[float]
    cost_basis_known: bool = True
    has_incomplete_history: bool = False
    has_mixed_currencies: bool

    @classmethod
    def from_asset(cls, asset, stats: dict) -> "AssetResponse":
        def _f(v):
            return float(v) if v is not None else None

        inst = getattr(asset, "instrument", None)
        instrument_resp = (
            InstrumentResponse.model_validate(inst) if inst is not None else None
        )

        return cls(
            id=asset.id,
            user_id=asset.user_id,
            instrument_id=asset.instrument_id,
            instrument=instrument_resp,
            asset_type=asset.asset_type,
            symbol=asset.symbol,
            name=asset.name,
            current_price=_f(asset.current_price),
            current_price_currency=asset.current_price_currency,
            is_manual_price=asset.is_manual_price,
            notes=asset.notes,
            created_at=asset.created_at,
            updated_at=asset.updated_at,
            total_quantity=float(stats["total_quantity"]),
            avg_cost=_f(stats["avg_cost"]),
            avg_cost_currency=stats["avg_cost_currency"],
            total_cost=_f(stats["total_cost"]),
            realized_pl=_f(stats["realized_pl"]),
            has_mixed_currencies=stats["has_mixed_currencies"],
            cost_basis_known=stats.get("cost_basis_known", True),
            has_incomplete_history=stats.get("has_incomplete_history", False),
        )

