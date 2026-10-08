import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.transaction import TransactionType


class TransactionCreateRequest(BaseModel):
    transaction_type: TransactionType
    quantity: Optional[Decimal] = Field(default=None, gt=0, max_digits=18, decimal_places=6)
    price_per_unit: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    total_amount: Optional[Decimal] = Field(
        default=None, gt=0, max_digits=18, decimal_places=6
    )
    transaction_currency: str = Field(max_length=3)
    transaction_date: date = Field(default_factory=date.today)
    notes: Optional[str] = None
    affects_cash: bool = True

    @model_validator(mode="after")
    def _exactly_one_of_qty_or_total(self) -> "TransactionCreateRequest":
        has_qty = self.quantity is not None
        has_total = self.total_amount is not None
        if has_qty == has_total:
            raise ValueError(
                "Provide exactly one of 'quantity' or 'total_amount' (not both, not neither)."
            )
        return self


class TransactionUpdateRequest(BaseModel):
    """All fields optional. If quantity or total_amount change, the other is recomputed."""

    transaction_type: Optional[TransactionType] = None
    quantity: Optional[Decimal] = Field(default=None, gt=0, max_digits=18, decimal_places=6)
    price_per_unit: Optional[Decimal] = Field(
        default=None, gt=0, max_digits=18, decimal_places=6
    )
    total_amount: Optional[Decimal] = Field(
        default=None, gt=0, max_digits=18, decimal_places=6
    )
    transaction_currency: Optional[str] = Field(default=None, max_length=3)
    transaction_date: Optional[date] = None
    notes: Optional[str] = None
    affects_cash: Optional[bool] = None

    @model_validator(mode="after")
    def _not_both_qty_and_total(self) -> "TransactionUpdateRequest":
        if self.quantity is not None and self.total_amount is not None:
            raise ValueError("Provide at most one of 'quantity' or 'total_amount'.")
        return self


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asset_id: uuid.UUID
    transaction_type: TransactionType
    quantity: float
    price_per_unit: float
    total_amount: float
    transaction_currency: str
    transaction_date: date
    notes: Optional[str]
    affects_cash: bool
    created_at: datetime
    updated_at: datetime
