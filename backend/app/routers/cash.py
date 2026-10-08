from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.cash import (
    CashAccountResponse,
    CashDepositRequest,
    CashMovementResponse,
    CashTransferRequest,
    CashWithdrawRequest,
)
from app.services import cash as cash_service

router = APIRouter()


@router.get("")
async def list_cash_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    accounts = await cash_service.list_accounts(db, current_user.id)
    return {
        "status": "success",
        "data": [
            CashAccountResponse.model_validate(a).model_dump(mode="json")
            for a in accounts
        ],
    }


@router.get("/movements")
async def list_cash_movements(
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    movements = await cash_service.list_movements(db, current_user.id, limit)
    return {
        "status": "success",
        "data": [
            CashMovementResponse.model_validate(m).model_dump(mode="json")
            for m in movements
        ],
    }


@router.post("/deposit")
async def deposit_cash(
    body: CashDepositRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    account = await cash_service.deposit(
        db, current_user.id, body.currency, body.amount, body.notes
    )
    return {
        "status": "success",
        "data": CashAccountResponse.model_validate(account).model_dump(mode="json"),
    }


@router.post("/withdraw")
async def withdraw_cash(
    body: CashWithdrawRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    account = await cash_service.withdraw(
        db, current_user.id, body.currency, body.amount, body.notes
    )
    return {
        "status": "success",
        "data": CashAccountResponse.model_validate(account).model_dump(mode="json"),
    }


@router.post("/transfer")
async def transfer_cash(
    body: CashTransferRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from_acct, to_acct = await cash_service.transfer(
        db,
        current_user.id,
        body.from_currency,
        body.to_currency,
        body.from_amount,
        body.rate,
        body.notes,
    )
    return {
        "status": "success",
        "data": {
            "from_account": CashAccountResponse.model_validate(from_acct).model_dump(
                mode="json"
            ),
            "to_account": CashAccountResponse.model_validate(to_acct).model_dump(
                mode="json"
            ),
        },
    }
