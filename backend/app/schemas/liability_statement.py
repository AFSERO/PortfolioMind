import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.liability_statement import (
    InstallmentPlanStatus,
    StatementSource,
    StatementStatus,
    StatementTransactionType,
)


_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
MONEY = {"ge": 0, "max_digits": 18, "decimal_places": 6}
POSITIVE_MONEY = {"gt": 0, "max_digits": 18, "decimal_places": 6}
INSTALLMENT_ROUNDING_TOLERANCE = Decimal("0.01")


class StatementPdfPreflightResponse(BaseModel):
    filename: str
    size_bytes: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    is_pdf: Literal[True] = True
    is_duplicate: bool
    matched_statement_id: Optional[uuid.UUID] = None
    status: Literal["ready", "duplicate_statement_file"]
    analysis_available: Literal[False] = False


def _normalize_currency(value: object) -> object:
    if not isinstance(value, str):
        return value
    normalized = value.strip().upper()
    if not _CURRENCY_PATTERN.fullmatch(normalized):
        raise ValueError("currency must be a three-letter alphabetic code")
    return normalized


def _normalize_hash(value: object) -> object:
    if value is None or not isinstance(value, str):
        return value
    normalized = value.strip().lower()
    if not _HASH_PATTERN.fullmatch(normalized):
        raise ValueError("hash must be a 64-character SHA-256 hex digest")
    return normalized


class StatementTransactionCreateRequest(BaseModel):
    transaction_date: date
    posting_date: Optional[date] = None
    description: str = Field(min_length=1, max_length=1000)
    merchant_name: Optional[str] = Field(default=None, max_length=255)
    transaction_type: StatementTransactionType
    amount: Decimal = Field(**POSITIVE_MONEY)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    installment_plan_id: Optional[uuid.UUID] = None
    installment_number: Optional[int] = Field(default=None, ge=1)
    installment_count: Optional[int] = Field(default=None, ge=2)
    external_reference: Optional[str] = Field(default=None, max_length=255)
    source_line_hash: Optional[str] = Field(default=None, max_length=64)
    notes: Optional[str] = Field(default=None, max_length=5000)

    _currency = field_validator("currency", mode="before")(_normalize_currency)
    _source_hash = field_validator("source_line_hash", mode="before")(
        _normalize_hash
    )

    @model_validator(mode="after")
    def _validate_installment_fields(self) -> "StatementTransactionCreateRequest":
        values = (
            self.installment_plan_id,
            self.installment_number,
            self.installment_count,
        )
        if self.transaction_type == StatementTransactionType.INSTALLMENT:
            if self.installment_number is None or self.installment_count is None:
                raise ValueError(
                    "installment transactions require installment_number and installment_count"
                )
            if self.installment_count < self.installment_number:
                raise ValueError("installment_count must be >= installment_number")
        elif any(value is not None for value in values):
            raise ValueError(
                "non-installment transactions cannot contain installment fields"
            )
        return self


class StatementTransactionUpdateRequest(BaseModel):
    transaction_date: Optional[date] = None
    posting_date: Optional[date] = None
    description: Optional[str] = Field(default=None, min_length=1, max_length=1000)
    merchant_name: Optional[str] = Field(default=None, max_length=255)
    transaction_type: Optional[StatementTransactionType] = None
    amount: Optional[Decimal] = Field(default=None, **POSITIVE_MONEY)
    currency: Optional[str] = Field(
        default=None, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$"
    )
    installment_plan_id: Optional[uuid.UUID] = None
    installment_number: Optional[int] = Field(default=None, ge=1)
    installment_count: Optional[int] = Field(default=None, ge=2)
    external_reference: Optional[str] = Field(default=None, max_length=255)
    source_line_hash: Optional[str] = Field(default=None, max_length=64)
    notes: Optional[str] = Field(default=None, max_length=5000)

    _currency = field_validator("currency", mode="before")(_normalize_currency)
    _source_hash = field_validator("source_line_hash", mode="before")(
        _normalize_hash
    )

    @model_validator(mode="after")
    def _required_fields_cannot_be_null(self) -> "StatementTransactionUpdateRequest":
        required = {
            "transaction_date",
            "description",
            "transaction_type",
            "amount",
            "currency",
        }
        for field in required & self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class LiabilityStatementCreateRequest(BaseModel):
    statement_period_start: date
    statement_period_end: date
    statement_date: date
    due_date: date
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    previous_balance: Decimal = Field(**MONEY)
    payments_total: Decimal = Field(**MONEY)
    purchases_total: Decimal = Field(**MONEY)
    fees_total: Decimal = Field(**MONEY)
    interest_total: Decimal = Field(**MONEY)
    refunds_total: Decimal = Field(**MONEY)
    statement_balance: Decimal = Field(**MONEY)
    minimum_payment: Decimal = Field(**MONEY)
    remaining_installments_total: Decimal = Field(default=Decimal("0"), **MONEY)
    status: StatementStatus = StatementStatus.DRAFT
    notes: Optional[str] = Field(default=None, max_length=5000)
    source: StatementSource = StatementSource.MANUAL
    source_file_hash: Optional[str] = Field(default=None, max_length=64)
    transactions: list[StatementTransactionCreateRequest] = Field(default_factory=list)

    _currency = field_validator("currency", mode="before")(_normalize_currency)
    _source_hash = field_validator("source_file_hash", mode="before")(
        _normalize_hash
    )

    @model_validator(mode="after")
    def _validate_dates_and_minimum(self) -> "LiabilityStatementCreateRequest":
        if self.statement_period_start > self.statement_period_end:
            raise ValueError("statement_period_start must be <= statement_period_end")
        if self.due_date < self.statement_date:
            raise ValueError("due_date must be >= statement_date")
        if self.minimum_payment > self.statement_balance:
            raise ValueError("minimum_payment cannot exceed statement_balance")
        return self


class LiabilityStatementUpdateRequest(BaseModel):
    statement_period_start: Optional[date] = None
    statement_period_end: Optional[date] = None
    statement_date: Optional[date] = None
    due_date: Optional[date] = None
    currency: Optional[str] = Field(
        default=None, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$"
    )
    previous_balance: Optional[Decimal] = Field(default=None, **MONEY)
    payments_total: Optional[Decimal] = Field(default=None, **MONEY)
    purchases_total: Optional[Decimal] = Field(default=None, **MONEY)
    fees_total: Optional[Decimal] = Field(default=None, **MONEY)
    interest_total: Optional[Decimal] = Field(default=None, **MONEY)
    refunds_total: Optional[Decimal] = Field(default=None, **MONEY)
    statement_balance: Optional[Decimal] = Field(default=None, **MONEY)
    minimum_payment: Optional[Decimal] = Field(default=None, **MONEY)
    remaining_installments_total: Optional[Decimal] = Field(default=None, **MONEY)
    status: Optional[StatementStatus] = None
    notes: Optional[str] = Field(default=None, max_length=5000)
    source_file_hash: Optional[str] = Field(default=None, max_length=64)

    _currency = field_validator("currency", mode="before")(_normalize_currency)
    _source_hash = field_validator("source_file_hash", mode="before")(
        _normalize_hash
    )

    @model_validator(mode="after")
    def _required_fields_cannot_be_null(self) -> "LiabilityStatementUpdateRequest":
        nullable = {"notes", "source_file_hash"}
        for field in self.model_fields_set - nullable:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class StatementConfirmRequest(BaseModel):
    apply_to_liability: bool = False


class InstallmentPlanCreateRequest(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    merchant_name: Optional[str] = Field(default=None, max_length=255)
    purchase_date: date
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    original_amount: Decimal = Field(**POSITIVE_MONEY)
    installment_count: int = Field(ge=2, le=600)
    monthly_installment_amount: Decimal = Field(**POSITIVE_MONEY)
    first_installment_date: date
    completed_installment_count: int = Field(default=0, ge=0)
    status: InstallmentPlanStatus = InstallmentPlanStatus.ACTIVE
    external_reference: Optional[str] = Field(default=None, max_length=255)
    initial_statement_id: Optional[uuid.UUID] = None
    initial_transaction: Optional[StatementTransactionCreateRequest] = None

    _currency = field_validator("currency", mode="before")(_normalize_currency)

    @model_validator(mode="after")
    def _validate_plan(self) -> "InstallmentPlanCreateRequest":
        if self.completed_installment_count > self.installment_count:
            raise ValueError(
                "completed_installment_count cannot exceed installment_count"
            )
        scheduled = self.monthly_installment_amount * self.installment_count
        tolerance = INSTALLMENT_ROUNDING_TOLERANCE * self.installment_count
        if abs(scheduled - self.original_amount) > tolerance:
            raise ValueError(
                "installment schedule differs from original_amount beyond rounding tolerance"
            )
        has_statement = self.initial_statement_id is not None
        has_transaction = self.initial_transaction is not None
        if has_statement != has_transaction:
            raise ValueError(
                "initial_statement_id and initial_transaction must be provided together"
            )
        if (
            self.initial_transaction is not None
            and self.initial_transaction.transaction_type
            != StatementTransactionType.INSTALLMENT
        ):
            raise ValueError("initial_transaction must be an installment transaction")
        return self


class InstallmentPlanUpdateRequest(BaseModel):
    description: Optional[str] = Field(default=None, min_length=1, max_length=500)
    merchant_name: Optional[str] = Field(default=None, max_length=255)
    purchase_date: Optional[date] = None
    currency: Optional[str] = Field(
        default=None, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$"
    )
    original_amount: Optional[Decimal] = Field(default=None, **POSITIVE_MONEY)
    installment_count: Optional[int] = Field(default=None, ge=2, le=600)
    monthly_installment_amount: Optional[Decimal] = Field(
        default=None, **POSITIVE_MONEY
    )
    first_installment_date: Optional[date] = None
    completed_installment_count: Optional[int] = Field(default=None, ge=0)
    status: Optional[InstallmentPlanStatus] = None
    external_reference: Optional[str] = Field(default=None, max_length=255)

    _currency = field_validator("currency", mode="before")(_normalize_currency)

    @model_validator(mode="after")
    def _required_fields_cannot_be_null(self) -> "InstallmentPlanUpdateRequest":
        nullable = {"merchant_name", "external_reference"}
        for field in self.model_fields_set - nullable:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class StatementTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    statement_id: uuid.UUID
    transaction_date: date
    posting_date: Optional[date]
    description: str
    merchant_name: Optional[str]
    transaction_type: StatementTransactionType
    amount: float
    currency: str
    installment_plan_id: Optional[uuid.UUID]
    installment_number: Optional[int]
    installment_count: Optional[int]
    external_reference: Optional[str]
    source_line_hash: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class InstallmentPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    liability_id: uuid.UUID
    description: str
    merchant_name: Optional[str]
    purchase_date: date
    currency: str
    original_amount: float
    installment_count: int
    monthly_installment_amount: float
    first_installment_date: date
    completed_installment_count: int
    status: InstallmentPlanStatus
    external_reference: Optional[str]
    created_at: datetime
    updated_at: datetime
    remaining_installment_count: int
    remaining_amount: float
    next_installment_date: Optional[date]
    estimated_completion_date: date


class LiabilityStatementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    liability_id: uuid.UUID
    statement_period_start: date
    statement_period_end: date
    statement_date: date
    due_date: date
    currency: str
    previous_balance: float
    payments_total: float
    purchases_total: float
    fees_total: float
    interest_total: float
    refunds_total: float
    statement_balance: float
    minimum_payment: float
    remaining_installments_total: float
    status: StatementStatus
    notes: Optional[str]
    source: StatementSource
    source_file_hash: Optional[str]
    confirmed_at: Optional[datetime]
    applied_to_liability_at: Optional[datetime]
    applied_balance: Optional[float]
    created_at: datetime
    updated_at: datetime
    calculated_balance: float
    reported_balance: float
    reconciliation_difference: float
    is_reconciled: bool
    reconciliation_tolerance: float
    calculation_source: str
    summary_calculated_balance: float
    summary_difference: float
    transaction_calculated_balance: Optional[float]
    transaction_difference: Optional[float]
    transaction_count: int
    transactions: Optional[list[StatementTransactionResponse]] = None
