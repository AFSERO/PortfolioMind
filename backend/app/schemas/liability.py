import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.liability import LiabilityType


_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


def _normalize_currency(value: object) -> object:
    if not isinstance(value, str):
        return value
    normalized = value.strip().upper()
    if not _CURRENCY_PATTERN.fullmatch(normalized):
        raise ValueError("currency must be a three-letter alphabetic code")
    return normalized


class LiabilityCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    liability_type: LiabilityType
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    current_balance: Decimal = Field(ge=0, max_digits=18, decimal_places=6)
    original_balance: Optional[Decimal] = Field(
        default=None, ge=0, max_digits=18, decimal_places=6
    )
    interest_rate: Optional[Decimal] = Field(
        default=None, ge=0, max_digits=18, decimal_places=6
    )
    minimum_payment: Optional[Decimal] = Field(
        default=None, ge=0, max_digits=18, decimal_places=6
    )
    due_date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=5000)
    is_active: bool = True

    _currency = field_validator("currency", mode="before")(_normalize_currency)


class LiabilityUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    liability_type: Optional[LiabilityType] = None
    currency: Optional[str] = Field(
        default=None, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$"
    )
    current_balance: Optional[Decimal] = Field(
        default=None, ge=0, max_digits=18, decimal_places=6
    )
    original_balance: Optional[Decimal] = Field(
        default=None, ge=0, max_digits=18, decimal_places=6
    )
    interest_rate: Optional[Decimal] = Field(
        default=None, ge=0, max_digits=18, decimal_places=6
    )
    minimum_payment: Optional[Decimal] = Field(
        default=None, ge=0, max_digits=18, decimal_places=6
    )
    due_date: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=5000)
    is_active: Optional[bool] = None

    _currency = field_validator("currency", mode="before")(_normalize_currency)

    @model_validator(mode="after")
    def _required_fields_cannot_be_null(self) -> "LiabilityUpdateRequest":
        required = {
            "name",
            "liability_type",
            "currency",
            "current_balance",
            "is_active",
        }
        for field in required & self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class LiabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    liability_type: LiabilityType
    currency: str
    current_balance: float
    original_balance: Optional[float]
    interest_rate: Optional[float]
    minimum_payment: Optional[float]
    due_date: Optional[date]
    notes: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

