import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.liability_statement import (
    InstallmentPlanCreateRequest,
    InstallmentPlanUpdateRequest,
    LiabilityStatementCreateRequest,
    LiabilityStatementUpdateRequest,
    StatementConfirmRequest,
    StatementTransactionCreateRequest,
    StatementTransactionUpdateRequest,
    StatementPdfPreflightResponse,
)
from app.services import liability_statement as statement_service
from app.services import statement_import
from app.services.liability_statement import (
    DuplicateStatementDataError,
    StatementDomainError,
    StatementReconciliationError,
)


router = APIRouter()


def _preflight_error(exc: statement_import.StatementPreflightError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "code": exc.code, "message": str(exc)},
    )


def _raise_domain(exc: StatementDomainError) -> None:
    status_code = 409 if isinstance(
        exc, (DuplicateStatementDataError, StatementReconciliationError)
    ) else 400
    raise HTTPException(status_code=status_code, detail=str(exc)) from None


@router.post(
    "/liabilities/{liability_id}/statement-imports/preflight",
    response_model=None,
)
async def preflight_statement_import(
    liability_id: uuid.UUID,
    file: UploadFile | None = File(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict | JSONResponse:
    if file is None:
        return _preflight_error(
            statement_import.StatementPreflightError(
                "invalid_file_type", "Select a PDF file", 415
            )
        )

    try:
        result: StatementPdfPreflightResponse | None = (
            await statement_import.preflight_statement_pdf(
                db,
                liability_id=liability_id,
                user_id=current_user.id,
                upload=file,
            )
        )
    except statement_import.StatementPreflightError as exc:
        return _preflight_error(exc)
    finally:
        await file.close()

    if result is None:
        raise HTTPException(status_code=404, detail="Liability not found")
    return {"status": "success", "data": result}


@router.get("/liabilities/{liability_id}/statements")
async def list_statements(
    liability_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    statements = await statement_service.list_statements(
        db, liability_id, current_user.id
    )
    if statements is None:
        raise HTTPException(status_code=404, detail="Credit-card liability not found")
    return {"status": "success", "data": statements}


@router.post("/liabilities/{liability_id}/statements", status_code=201)
async def create_statement(
    liability_id: uuid.UUID,
    body: LiabilityStatementCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        statement = await statement_service.create_statement(
            db, liability_id, current_user.id, body
        )
    except StatementDomainError as exc:
        _raise_domain(exc)
    if statement is None:
        raise HTTPException(status_code=404, detail="Credit-card liability not found")
    return {"status": "success", "data": statement}


@router.get("/statements/{statement_id}")
async def get_statement(
    statement_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    statement = await statement_service.get_statement_detail(
        db, statement_id, current_user.id
    )
    if statement is None:
        raise HTTPException(status_code=404, detail="Statement not found")
    return {"status": "success", "data": statement}


@router.put("/statements/{statement_id}")
async def update_statement(
    statement_id: uuid.UUID,
    body: LiabilityStatementUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        statement = await statement_service.update_statement(
            db, statement_id, current_user.id, body
        )
    except StatementDomainError as exc:
        _raise_domain(exc)
    if statement is None:
        raise HTTPException(status_code=404, detail="Statement not found")
    return {"status": "success", "data": statement}


@router.delete("/statements/{statement_id}")
async def delete_statement(
    statement_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        deleted = await statement_service.delete_statement(
            db, statement_id, current_user.id
        )
    except StatementDomainError as exc:
        _raise_domain(exc)
    if not deleted:
        raise HTTPException(status_code=404, detail="Statement not found")
    return {"status": "success", "data": {"message": "Statement deleted"}}


@router.post("/statements/{statement_id}/confirm")
async def confirm_statement(
    statement_id: uuid.UUID,
    body: StatementConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        statement = await statement_service.confirm_statement(
            db,
            statement_id,
            current_user.id,
            apply_to_liability=body.apply_to_liability,
        )
    except StatementDomainError as exc:
        _raise_domain(exc)
    if statement is None:
        raise HTTPException(status_code=404, detail="Statement not found")
    return {"status": "success", "data": statement}


@router.get("/statements/{statement_id}/transactions")
async def list_statement_transactions(
    statement_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    transactions = await statement_service.list_transactions(
        db, statement_id, current_user.id
    )
    if transactions is None:
        raise HTTPException(status_code=404, detail="Statement not found")
    return {"status": "success", "data": transactions}


@router.post("/statements/{statement_id}/transactions", status_code=201)
async def create_statement_transaction(
    statement_id: uuid.UUID,
    body: StatementTransactionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        result = await statement_service.create_transaction(
            db, statement_id, current_user.id, body
        )
    except StatementDomainError as exc:
        _raise_domain(exc)
    if result is None:
        raise HTTPException(status_code=404, detail="Statement not found")
    return {"status": "success", "data": result}


@router.put("/statement-transactions/{transaction_id}")
async def update_statement_transaction(
    transaction_id: uuid.UUID,
    body: StatementTransactionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        result = await statement_service.update_transaction(
            db, transaction_id, current_user.id, body
        )
    except StatementDomainError as exc:
        _raise_domain(exc)
    if result is None:
        raise HTTPException(status_code=404, detail="Statement transaction not found")
    return {"status": "success", "data": result}


@router.delete("/statement-transactions/{transaction_id}")
async def delete_statement_transaction(
    transaction_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        reconciliation = await statement_service.delete_transaction(
            db, transaction_id, current_user.id
        )
    except StatementDomainError as exc:
        _raise_domain(exc)
    if reconciliation is None:
        raise HTTPException(status_code=404, detail="Statement transaction not found")
    return {
        "status": "success",
        "data": {
            "message": "Statement transaction deleted",
            "reconciliation": reconciliation,
        },
    }


@router.get("/liabilities/{liability_id}/installment-plans")
async def list_installment_plans(
    liability_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    plans = await statement_service.list_installment_plans(
        db, liability_id, current_user.id
    )
    if plans is None:
        raise HTTPException(status_code=404, detail="Credit-card liability not found")
    return {"status": "success", "data": plans}


@router.post("/liabilities/{liability_id}/installment-plans", status_code=201)
async def create_installment_plan(
    liability_id: uuid.UUID,
    body: InstallmentPlanCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        plan = await statement_service.create_installment_plan(
            db, liability_id, current_user.id, body
        )
    except StatementDomainError as exc:
        _raise_domain(exc)
    if plan is None:
        raise HTTPException(status_code=404, detail="Credit-card liability not found")
    return {"status": "success", "data": plan}


@router.get("/installment-plans/{plan_id}")
async def get_installment_plan(
    plan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    plan = await statement_service.get_installment_plan(db, plan_id, current_user.id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Installment plan not found")
    return {"status": "success", "data": plan}


@router.put("/installment-plans/{plan_id}")
async def update_installment_plan(
    plan_id: uuid.UUID,
    body: InstallmentPlanUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        plan = await statement_service.update_installment_plan(
            db, plan_id, current_user.id, body
        )
    except StatementDomainError as exc:
        _raise_domain(exc)
    if plan is None:
        raise HTTPException(status_code=404, detail="Installment plan not found")
    return {"status": "success", "data": plan}


@router.post("/installment-plans/{plan_id}/cancel")
async def cancel_installment_plan(
    plan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        plan = await statement_service.cancel_installment_plan(
            db, plan_id, current_user.id
        )
    except StatementDomainError as exc:
        _raise_domain(exc)
    if plan is None:
        raise HTTPException(status_code=404, detail="Installment plan not found")
    return {"status": "success", "data": plan}


@router.delete("/installment-plans/{plan_id}")
async def delete_installment_plan(
    plan_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        deleted = await statement_service.delete_installment_plan(
            db, plan_id, current_user.id
        )
    except StatementDomainError as exc:
        _raise_domain(exc)
    if not deleted:
        raise HTTPException(status_code=404, detail="Installment plan not found")
    return {"status": "success", "data": {"message": "Installment plan deleted"}}


@router.get("/liabilities/{liability_id}/installment-forecast")
async def get_installment_forecast(
    liability_id: uuid.UUID,
    as_of: date | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    forecast = await statement_service.installment_forecast(
        db, liability_id, current_user.id, as_of=as_of
    )
    if forecast is None:
        raise HTTPException(status_code=404, detail="Credit-card liability not found")
    return {"status": "success", "data": forecast}
