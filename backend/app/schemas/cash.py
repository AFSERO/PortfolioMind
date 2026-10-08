import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.cash import CashMovementType


class CashAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    currency: str
    balance: float
    created_at: datetime
    updated_at: datetime


class CashDepositRequest(BaseModel):
    currency: str = Field(max_length=3, min_length=3)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    notes: Optional[str] = None


class CashWithdrawRequest(BaseModel):
    currency: str = Field(max_length=3, min_length=3)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    notes: Optional[str] = None


class CashTransferRequest(BaseModel):
    from_currency: str = Field(max_length=3, min_length=3)
    to_currency: str = Field(max_length=3, min_length=3)
    from_amount: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    rate: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _currencies_differ(self) -> "CashTransferRequest":
        if self.from_currency.upper() == self.to_currency.upper():
            raise ValueError("from_currency and to_currency must differ.")
        return self


class CashMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cash_account_id: uuid.UUID
    movement_type: CashMovementType
    amount: float
    currency: str
    related_transaction_id: Optional[uuid.UUID]
    notes: Optional[str]
    created_at: datetime
