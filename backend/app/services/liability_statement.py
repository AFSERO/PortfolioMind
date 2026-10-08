"""Credit-card statement, line-item, and installment use cases.

Payment and refund values are stored as positive magnitudes and subtracted.
Mixed-currency statement lines are intentionally rejected until historical FX
data exists.  Commit/rollback is owned by the public use-case functions here;
staging helpers never commit so future importers can use the same atomic path.
"""

import calendar
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.liability import Liability, LiabilityType
from app.models.liability_statement import (
    InstallmentPlan,
    InstallmentPlanStatus,
    LiabilityStatement,
    StatementSource,
    StatementStatus,
    StatementTransaction,
    StatementTransactionType,
)
from app.schemas.liability_statement import (
    INSTALLMENT_ROUNDING_TOLERANCE,
    InstallmentPlanCreateRequest,
    InstallmentPlanResponse,
    InstallmentPlanUpdateRequest,
    LiabilityStatementCreateRequest,
    LiabilityStatementResponse,
    LiabilityStatementUpdateRequest,
    StatementTransactionCreateRequest,
    StatementTransactionResponse,
    StatementTransactionUpdateRequest,
)


ZERO = Decimal("0")
RECONCILIATION_TOLERANCE = Decimal("0.01")
CHARGE_TYPES = {
    StatementTransactionType.PURCHASE,
    StatementTransactionType.FEE,
    StatementTransactionType.INTEREST,
    StatementTransactionType.CASH_ADVANCE,
    StatementTransactionType.INSTALLMENT,
    StatementTransactionType.OTHER,
}


class StatementDomainError(ValueError):
    """A safe, user-facing domain validation failure."""


class DuplicateStatementDataError(StatementDomainError):
    """A period, date, or importer hash already exists."""


class StatementReconciliationError(StatementDomainError):
    """A statement cannot be confirmed because its totals do not reconcile."""


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _month_start(value: date) -> date:
    return value.replace(day=1)


async def _commit(db: AsyncSession, duplicate_message: str) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise DuplicateStatementDataError(duplicate_message) from exc
    except Exception:
        await db.rollback()
        raise


async def _credit_card(
    db: AsyncSession, liability_id: UUID, user_id: UUID
) -> Optional[Liability]:
    result = await db.execute(
        select(Liability).where(
            Liability.id == liability_id,
            Liability.user_id == user_id,
            Liability.liability_type == LiabilityType.CREDIT_CARD,
        )
    )
    return result.scalar_one_or_none()


async def _statement(
    db: AsyncSession, statement_id: UUID, user_id: UUID
) -> Optional[LiabilityStatement]:
    result = await db.execute(
        select(LiabilityStatement).where(
            LiabilityStatement.id == statement_id,
            LiabilityStatement.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def _statement_transactions(
    db: AsyncSession, statement_id: UUID
) -> list[StatementTransaction]:
    result = await db.execute(
        select(StatementTransaction)
        .where(StatementTransaction.statement_id == statement_id)
        .order_by(
            StatementTransaction.transaction_date.asc(),
            StatementTransaction.created_at.asc(),
        )
    )
    return list(result.scalars().all())


async def _plan(
    db: AsyncSession, plan_id: UUID, user_id: UUID
) -> Optional[InstallmentPlan]:
    result = await db.execute(
        select(InstallmentPlan).where(
            InstallmentPlan.id == plan_id,
            InstallmentPlan.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


def _summary_calculated_balance(statement: LiabilityStatement) -> Decimal:
    return (
        statement.previous_balance
        + statement.purchases_total
        + statement.fees_total
        + statement.interest_total
        - statement.payments_total
        - statement.refunds_total
    )


def _transaction_calculated_balance(
    statement: LiabilityStatement, transactions: list[StatementTransaction]
) -> Optional[Decimal]:
    if not transactions:
        return None
    total = statement.previous_balance
    for transaction in transactions:
        if transaction.transaction_type in CHARGE_TYPES:
            total += transaction.amount
        elif transaction.transaction_type in {
            StatementTransactionType.PAYMENT,
            StatementTransactionType.REFUND,
        }:
            total -= transaction.amount
    return total


def reconciliation(
    statement: LiabilityStatement, transactions: list[StatementTransaction]
) -> dict:
    summary_balance = _summary_calculated_balance(statement)
    transaction_balance = _transaction_calculated_balance(statement, transactions)
    reported = statement.statement_balance
    summary_difference = reported - summary_balance
    transaction_difference = (
        reported - transaction_balance if transaction_balance is not None else None
    )
    calculated = (
        transaction_balance if transaction_balance is not None else summary_balance
    )
    difference = reported - calculated
    summary_ok = abs(summary_difference) <= RECONCILIATION_TOLERANCE
    transaction_ok = (
        transaction_difference is None
        or abs(transaction_difference) <= RECONCILIATION_TOLERANCE
    )
    return {
        "calculated_balance": calculated,
        "reported_balance": reported,
        "reconciliation_difference": difference,
        "is_reconciled": summary_ok and transaction_ok,
        "reconciliation_tolerance": RECONCILIATION_TOLERANCE,
        "calculation_source": "transactions" if transactions else "summary",
        "summary_calculated_balance": summary_balance,
        "summary_difference": summary_difference,
        "transaction_calculated_balance": transaction_balance,
        "transaction_difference": transaction_difference,
        "transaction_count": len(transactions),
    }


def _transaction_dict(transaction: StatementTransaction) -> dict:
    return StatementTransactionResponse.model_validate(transaction).model_dump(mode="json")


def _statement_dict(
    statement: LiabilityStatement,
    transactions: list[StatementTransaction],
    *,
    include_transactions: bool,
) -> dict:
    data = {
        column.name: getattr(statement, column.name)
        for column in LiabilityStatement.__table__.columns
    }
    data.update(reconciliation(statement, transactions))
    if include_transactions:
        data["transactions"] = [_transaction_dict(item) for item in transactions]
    return LiabilityStatementResponse.model_validate(data).model_dump(mode="json")


def _plan_amounts(plan: InstallmentPlan) -> tuple[int, Decimal]:
    remaining_count = max(plan.installment_count - plan.completed_installment_count, 0)
    completed_amount = min(
        plan.monthly_installment_amount * plan.completed_installment_count,
        plan.original_amount,
    )
    remaining_amount = max(plan.original_amount - completed_amount, ZERO)
    return remaining_count, remaining_amount


def _plan_dict(plan: InstallmentPlan) -> dict:
    remaining_count, remaining_amount = _plan_amounts(plan)
    next_date = (
        _add_months(plan.first_installment_date, plan.completed_installment_count)
        if remaining_count > 0 and plan.status == InstallmentPlanStatus.ACTIVE
        else None
    )
    data = {
        column.name: getattr(plan, column.name)
        for column in InstallmentPlan.__table__.columns
    }
    data.update(
        {
            "remaining_installment_count": remaining_count,
            "remaining_amount": remaining_amount,
            "next_installment_date": next_date,
            "estimated_completion_date": _add_months(
                plan.first_installment_date, plan.installment_count - 1
            ),
        }
    )
    return InstallmentPlanResponse.model_validate(data).model_dump(mode="json")


async def list_statements(
    db: AsyncSession, liability_id: UUID, user_id: UUID
) -> Optional[list[dict]]:
    if await _credit_card(db, liability_id, user_id) is None:
        return None
    result = await db.execute(
        select(LiabilityStatement)
        .where(
            LiabilityStatement.liability_id == liability_id,
            LiabilityStatement.user_id == user_id,
        )
        .order_by(LiabilityStatement.statement_date.desc())
    )
    statements = list(result.scalars().all())
    if not statements:
        return []
    statement_ids = [item.id for item in statements]
    tx_result = await db.execute(
        select(StatementTransaction).where(
            StatementTransaction.statement_id.in_(statement_ids)
        )
    )
    by_statement: dict[UUID, list[StatementTransaction]] = defaultdict(list)
    for transaction in tx_result.scalars().all():
        by_statement[transaction.statement_id].append(transaction)
    return [
        _statement_dict(item, by_statement[item.id], include_transactions=False)
        for item in statements
    ]


async def get_statement_detail(
    db: AsyncSession, statement_id: UUID, user_id: UUID
) -> Optional[dict]:
    statement = await _statement(db, statement_id, user_id)
    if statement is None:
        return None
    transactions = await _statement_transactions(db, statement.id)
    return _statement_dict(statement, transactions, include_transactions=True)


async def _validate_transaction_plan(
    db: AsyncSession,
    data: StatementTransactionCreateRequest,
    statement: LiabilityStatement,
    user_id: UUID,
) -> None:
    if data.currency != statement.currency:
        raise StatementDomainError(
            "transaction currency must match statement currency"
        )
    if data.installment_plan_id is None:
        return
    plan = await _plan(db, data.installment_plan_id, user_id)
    if plan is None or plan.liability_id != statement.liability_id:
        raise StatementDomainError("installment plan not found for this liability")
    if plan.currency != statement.currency:
        raise StatementDomainError("installment plan currency must match statement currency")
    if data.installment_count != plan.installment_count:
        raise StatementDomainError("installment_count must match the installment plan")


def _new_transaction(
    statement: LiabilityStatement,
    user_id: UUID,
    data: StatementTransactionCreateRequest,
) -> StatementTransaction:
    return StatementTransaction(
        user_id=user_id,
        statement_id=statement.id,
        **data.model_dump(),
    )


async def create_statement(
    db: AsyncSession,
    liability_id: UUID,
    user_id: UUID,
    data: LiabilityStatementCreateRequest,
) -> Optional[dict]:
    liability = await _credit_card(db, liability_id, user_id)
    if liability is None:
        return None
    if data.currency != liability.currency:
        raise StatementDomainError("statement currency must match liability currency")
    if data.source != StatementSource.MANUAL:
        raise StatementDomainError("only manual statement entry is enabled")
    if data.status != StatementStatus.DRAFT:
        raise StatementDomainError("new statements must start in draft status")

    statement_data = data.model_dump(exclude={"transactions"})
    statement = LiabilityStatement(
        user_id=user_id,
        liability_id=liability_id,
        **statement_data,
    )
    for transaction in data.transactions:
        await _validate_transaction_plan(db, transaction, statement, user_id)

    db.add(statement)
    try:
        await db.flush()
        transactions = [
            _new_transaction(statement, user_id, transaction)
            for transaction in data.transactions
        ]
        db.add_all(transactions)
        await db.flush()
        await _commit(db, "statement period, date, or import hash already exists")
    except IntegrityError as exc:
        await db.rollback()
        raise DuplicateStatementDataError(
            "statement period, date, or import hash already exists"
        ) from exc
    except Exception:
        if db.in_transaction():
            await db.rollback()
        raise
    await db.refresh(statement)
    transactions = await _statement_transactions(db, statement.id)
    return _statement_dict(statement, transactions, include_transactions=True)


async def update_statement(
    db: AsyncSession,
    statement_id: UUID,
    user_id: UUID,
    data: LiabilityStatementUpdateRequest,
) -> Optional[dict]:
    statement = await _statement(db, statement_id, user_id)
    if statement is None:
        return None
    financial_fields = {
        "statement_period_start",
        "statement_period_end",
        "statement_date",
        "due_date",
        "currency",
        "previous_balance",
        "payments_total",
        "purchases_total",
        "fees_total",
        "interest_total",
        "refunds_total",
        "statement_balance",
        "minimum_payment",
        "remaining_installments_total",
        "source_file_hash",
    }
    if statement.status != StatementStatus.DRAFT and (
        data.model_fields_set & financial_fields
    ):
        raise StatementDomainError("confirmed statement financial fields are immutable")
    if data.status == StatementStatus.CONFIRMED:
        raise StatementDomainError("use the confirm endpoint to confirm a statement")

    liability = await _credit_card(db, statement.liability_id, user_id)
    if liability is None:
        return None
    current = {
        "statement_period_start": statement.statement_period_start,
        "statement_period_end": statement.statement_period_end,
        "statement_date": statement.statement_date,
        "due_date": statement.due_date,
        "currency": statement.currency,
        "previous_balance": statement.previous_balance,
        "payments_total": statement.payments_total,
        "purchases_total": statement.purchases_total,
        "fees_total": statement.fees_total,
        "interest_total": statement.interest_total,
        "refunds_total": statement.refunds_total,
        "statement_balance": statement.statement_balance,
        "minimum_payment": statement.minimum_payment,
        "remaining_installments_total": statement.remaining_installments_total,
        "status": statement.status,
        "notes": statement.notes,
        "source": statement.source,
        "source_file_hash": statement.source_file_hash,
    }
    current.update(data.model_dump(exclude_unset=True))
    validated = LiabilityStatementCreateRequest(**current)
    if validated.currency != liability.currency:
        raise StatementDomainError("statement currency must match liability currency")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(statement, field, value)
    await _commit(db, "statement period, date, or import hash already exists")
    await db.refresh(statement)
    transactions = await _statement_transactions(db, statement.id)
    return _statement_dict(statement, transactions, include_transactions=True)


async def delete_statement(
    db: AsyncSession, statement_id: UUID, user_id: UUID
) -> bool:
    statement = await _statement(db, statement_id, user_id)
    if statement is None:
        return False
    await db.delete(statement)
    await _commit(db, "statement could not be deleted")
    return True


async def confirm_statement(
    db: AsyncSession,
    statement_id: UUID,
    user_id: UUID,
    *,
    apply_to_liability: bool,
) -> Optional[dict]:
    statement = await _statement(db, statement_id, user_id)
    if statement is None:
        return None
    transactions = await _statement_transactions(db, statement.id)
    result = reconciliation(statement, transactions)
    if not result["is_reconciled"]:
        raise StatementReconciliationError(
            "statement cannot be confirmed until reconciliation differences are resolved"
        )
    if statement.status not in {StatementStatus.DRAFT, StatementStatus.CONFIRMED}:
        raise StatementDomainError("only draft or confirmed statements can be confirmed")

    liability = await _credit_card(db, statement.liability_id, user_id)
    if liability is None:
        return None
    now = datetime.now(timezone.utc)
    if statement.confirmed_at is None:
        statement.confirmed_at = now
    statement.status = StatementStatus.CONFIRMED
    if apply_to_liability:
        liability.current_balance = statement.statement_balance
        statement.applied_to_liability_at = statement.applied_to_liability_at or now
        statement.applied_balance = statement.statement_balance
    await _commit(db, "statement could not be confirmed")
    await db.refresh(statement)
    return _statement_dict(statement, transactions, include_transactions=True)


async def list_transactions(
    db: AsyncSession, statement_id: UUID, user_id: UUID
) -> Optional[list[dict]]:
    statement = await _statement(db, statement_id, user_id)
    if statement is None:
        return None
    return [
        _transaction_dict(item)
        for item in await _statement_transactions(db, statement.id)
    ]


async def create_transaction(
    db: AsyncSession,
    statement_id: UUID,
    user_id: UUID,
    data: StatementTransactionCreateRequest,
) -> Optional[dict]:
    statement = await _statement(db, statement_id, user_id)
    if statement is None:
        return None
    if statement.status != StatementStatus.DRAFT:
        raise StatementDomainError("only draft statements can be edited")
    await _validate_transaction_plan(db, data, statement, user_id)
    transaction = _new_transaction(statement, user_id, data)
    db.add(transaction)
    await _commit(db, "transaction import hash already exists for this statement")
    await db.refresh(transaction)
    transactions = await _statement_transactions(db, statement.id)
    return {
        "transaction": _transaction_dict(transaction),
        "reconciliation": {
            key: float(value) if isinstance(value, Decimal) else value
            for key, value in reconciliation(statement, transactions).items()
        },
    }


async def _owned_transaction(
    db: AsyncSession, transaction_id: UUID, user_id: UUID
) -> Optional[tuple[StatementTransaction, LiabilityStatement]]:
    result = await db.execute(
        select(StatementTransaction, LiabilityStatement)
        .join(
            LiabilityStatement,
            StatementTransaction.statement_id == LiabilityStatement.id,
        )
        .where(
            StatementTransaction.id == transaction_id,
            StatementTransaction.user_id == user_id,
            LiabilityStatement.user_id == user_id,
        )
    )
    row = result.one_or_none()
    return (row[0], row[1]) if row is not None else None


async def update_transaction(
    db: AsyncSession,
    transaction_id: UUID,
    user_id: UUID,
    data: StatementTransactionUpdateRequest,
) -> Optional[dict]:
    owned = await _owned_transaction(db, transaction_id, user_id)
    if owned is None:
        return None
    transaction, statement = owned
    if statement.status != StatementStatus.DRAFT:
        raise StatementDomainError("only draft statements can be edited")
    current = {
        "transaction_date": transaction.transaction_date,
        "posting_date": transaction.posting_date,
        "description": transaction.description,
        "merchant_name": transaction.merchant_name,
        "transaction_type": transaction.transaction_type,
        "amount": transaction.amount,
        "currency": transaction.currency,
        "installment_plan_id": transaction.installment_plan_id,
        "installment_number": transaction.installment_number,
        "installment_count": transaction.installment_count,
        "external_reference": transaction.external_reference,
        "source_line_hash": transaction.source_line_hash,
        "notes": transaction.notes,
    }
    current.update(data.model_dump(exclude_unset=True))
    validated = StatementTransactionCreateRequest(**current)
    await _validate_transaction_plan(db, validated, statement, user_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(transaction, field, value)
    await _commit(db, "transaction import hash already exists for this statement")
    await db.refresh(transaction)
    transactions = await _statement_transactions(db, statement.id)
    return {
        "transaction": _transaction_dict(transaction),
        "reconciliation": {
            key: float(value) if isinstance(value, Decimal) else value
            for key, value in reconciliation(statement, transactions).items()
        },
    }


async def delete_transaction(
    db: AsyncSession, transaction_id: UUID, user_id: UUID
) -> Optional[dict]:
    owned = await _owned_transaction(db, transaction_id, user_id)
    if owned is None:
        return None
    transaction, statement = owned
    if statement.status != StatementStatus.DRAFT:
        raise StatementDomainError("only draft statements can be edited")
    await db.delete(transaction)
    await _commit(db, "transaction could not be deleted")
    transactions = await _statement_transactions(db, statement.id)
    return {
        key: float(value) if isinstance(value, Decimal) else value
        for key, value in reconciliation(statement, transactions).items()
    }


async def list_installment_plans(
    db: AsyncSession, liability_id: UUID, user_id: UUID
) -> Optional[list[dict]]:
    if await _credit_card(db, liability_id, user_id) is None:
        return None
    result = await db.execute(
        select(InstallmentPlan)
        .where(
            InstallmentPlan.liability_id == liability_id,
            InstallmentPlan.user_id == user_id,
        )
        .order_by(InstallmentPlan.purchase_date.desc())
    )
    return [_plan_dict(item) for item in result.scalars().all()]


async def get_installment_plan(
    db: AsyncSession, plan_id: UUID, user_id: UUID
) -> Optional[dict]:
    plan = await _plan(db, plan_id, user_id)
    return _plan_dict(plan) if plan is not None else None


async def create_installment_plan(
    db: AsyncSession,
    liability_id: UUID,
    user_id: UUID,
    data: InstallmentPlanCreateRequest,
) -> Optional[dict]:
    liability = await _credit_card(db, liability_id, user_id)
    if liability is None:
        return None
    if data.currency != liability.currency:
        raise StatementDomainError("installment currency must match liability currency")
    statement = None
    if data.initial_statement_id is not None:
        statement = await _statement(db, data.initial_statement_id, user_id)
        if statement is None or statement.liability_id != liability_id:
            raise StatementDomainError("initial statement not found for this liability")
        if statement.status != StatementStatus.DRAFT:
            raise StatementDomainError("only draft statements can receive transactions")
        assert data.initial_transaction is not None
        if data.initial_transaction.currency != data.currency:
            raise StatementDomainError(
                "initial transaction currency must match installment currency"
            )
        if data.initial_transaction.installment_count != data.installment_count:
            raise StatementDomainError(
                "initial transaction installment_count must match the plan"
            )

    plan_data = data.model_dump(
        exclude={"initial_statement_id", "initial_transaction"}
    )
    plan = InstallmentPlan(user_id=user_id, liability_id=liability_id, **plan_data)
    db.add(plan)
    try:
        await db.flush()
        if statement is not None and data.initial_transaction is not None:
            transaction_data = data.initial_transaction.model_copy(
                update={"installment_plan_id": plan.id}
            )
            db.add(_new_transaction(statement, user_id, transaction_data))
            await db.flush()
        await _commit(db, "installment plan reference already exists")
    except IntegrityError as exc:
        await db.rollback()
        raise DuplicateStatementDataError(
            "installment plan reference or transaction import hash already exists"
        ) from exc
    except Exception:
        if db.in_transaction():
            await db.rollback()
        raise
    await db.refresh(plan)
    return _plan_dict(plan)


async def update_installment_plan(
    db: AsyncSession,
    plan_id: UUID,
    user_id: UUID,
    data: InstallmentPlanUpdateRequest,
) -> Optional[dict]:
    plan = await _plan(db, plan_id, user_id)
    if plan is None:
        return None
    liability = await _credit_card(db, plan.liability_id, user_id)
    if liability is None:
        return None
    current = {
        "description": plan.description,
        "merchant_name": plan.merchant_name,
        "purchase_date": plan.purchase_date,
        "currency": plan.currency,
        "original_amount": plan.original_amount,
        "installment_count": plan.installment_count,
        "monthly_installment_amount": plan.monthly_installment_amount,
        "first_installment_date": plan.first_installment_date,
        "completed_installment_count": plan.completed_installment_count,
        "status": plan.status,
        "external_reference": plan.external_reference,
    }
    current.update(data.model_dump(exclude_unset=True))
    validated = InstallmentPlanCreateRequest(**current)
    if validated.currency != liability.currency:
        raise StatementDomainError("installment currency must match liability currency")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    await _commit(db, "installment plan reference already exists")
    await db.refresh(plan)
    return _plan_dict(plan)


async def cancel_installment_plan(
    db: AsyncSession, plan_id: UUID, user_id: UUID
) -> Optional[dict]:
    plan = await _plan(db, plan_id, user_id)
    if plan is None:
        return None
    plan.status = InstallmentPlanStatus.CANCELLED
    await _commit(db, "installment plan could not be cancelled")
    await db.refresh(plan)
    return _plan_dict(plan)


async def delete_installment_plan(
    db: AsyncSession, plan_id: UUID, user_id: UUID
) -> bool:
    plan = await _plan(db, plan_id, user_id)
    if plan is None:
        return False
    await db.delete(plan)
    await _commit(db, "installment plan could not be deleted")
    return True


def _scheduled_amount(plan: InstallmentPlan, installment_index: int) -> Decimal:
    if installment_index == plan.installment_count - 1:
        return max(
            plan.original_amount
            - plan.monthly_installment_amount * (plan.installment_count - 1),
            ZERO,
        )
    return plan.monthly_installment_amount


async def installment_forecast(
    db: AsyncSession,
    liability_id: UUID,
    user_id: UUID,
    *,
    as_of: Optional[date] = None,
) -> Optional[dict]:
    liability = await _credit_card(db, liability_id, user_id)
    if liability is None:
        return None
    if as_of is None:
        as_of = date.today()
    result = await db.execute(
        select(InstallmentPlan).where(
            InstallmentPlan.liability_id == liability_id,
            InstallmentPlan.user_id == user_id,
            InstallmentPlan.status == InstallmentPlanStatus.ACTIVE,
            InstallmentPlan.completed_installment_count
            < InstallmentPlan.installment_count,
        )
    )
    plans = list(result.scalars().all())
    bucket_months = [_add_months(_month_start(as_of), offset) for offset in (1, 2, 3)]
    bucket_totals = {month: ZERO for month in bucket_months}
    remaining_total = ZERO
    next_dates: list[date] = []
    for plan in plans:
        _, remaining_amount = _plan_amounts(plan)
        remaining_total += remaining_amount
        next_date = _add_months(
            plan.first_installment_date, plan.completed_installment_count
        )
        next_dates.append(next_date)
        for index in range(
            plan.completed_installment_count, plan.installment_count
        ):
            installment_date = _add_months(plan.first_installment_date, index)
            month = _month_start(installment_date)
            if month in bucket_totals:
                bucket_totals[month] += _scheduled_amount(plan, index)
    return {
        "currency": liability.currency,
        "as_of": as_of.isoformat(),
        "next_month_total": float(bucket_totals[bucket_months[0]]),
        "next_three_months": [
            {"month": month.isoformat(), "amount": float(bucket_totals[month])}
            for month in bucket_months
        ],
        "remaining_total": float(remaining_total),
        "nearest_installment_date": min(next_dates).isoformat()
        if next_dates
        else None,
        "active_plan_count": len(plans),
    }
