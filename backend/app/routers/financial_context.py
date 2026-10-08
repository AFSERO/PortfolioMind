import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.financial_context import ResourceAssignmentType
from app.models.user import User
from app.schemas.financial_context import (
    CapitalAssignmentBase,
    CapitalTransferRequest,
    FinancialContextCreate,
    FinancialContextResponse,
    FinancialContextUpdate,
    FinancialGoalCreate,
    FinancialGoalResponse,
    FinancialGoalUpdate,
    FinancialIntelligenceSummary,
    FinancialProfileSynthesis,
    InvestmentMandateCreate,
    InvestmentMandateResponse,
    InvestmentMandateUpdate,
    ResolveAssignmentReviewRequest,
)
from app.services.financial_context import (
    AssignmentService,
    FinancialContextService,
    FinancialIntelligenceService,
    GoalsService,
)

router = APIRouter(prefix="/api", tags=["financial-context-goals"])


# --- Financial Context ---
@router.get("/financial-context", response_model=Dict[str, Any])
async def get_financial_context(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ctx = await FinancialContextService.get_or_create(db, current_user.id)
    return {
        "status": "success",
        "data": FinancialContextResponse.model_validate(ctx).model_dump(),
    }


@router.put("/financial-context", response_model=Dict[str, Any])
async def update_financial_context(
    payload: FinancialContextUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ctx = await FinancialContextService.update(db, current_user.id, payload)
    await db.commit()
    await db.refresh(ctx)
    return {
        "status": "success",
        "data": FinancialContextResponse.model_validate(ctx).model_dump(),
    }


@router.post("/financial-context/confirm", response_model=Dict[str, Any])
async def confirm_financial_context(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ctx = await FinancialContextService.confirm(db, current_user.id)
    await db.commit()
    await db.refresh(ctx)
    return {
        "status": "success",
        "data": FinancialContextResponse.model_validate(ctx).model_dump(),
    }


@router.get("/financial-context/unassigned-resources", response_model=Dict[str, Any])
async def get_unassigned_resources(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    unassigned = await AssignmentService.get_unassigned_resources(db, current_user.id)
    return {
        "status": "success",
        "data": unassigned,
    }


# --- Financial Goals ---
@router.get("/financial-goals", response_model=Dict[str, Any])
async def list_financial_goals(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goals = await GoalsService.list_goals(db, current_user.id)
    return {
        "status": "success",
        "data": goals,
    }


@router.post("/financial-goals", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_financial_goal(
    payload: FinancialGoalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = await GoalsService.create_goal(db, current_user.id, payload)
    await db.commit()
    # Reload with details
    goal_detail = await GoalsService.get_goal(db, current_user.id, goal.id)
    return {
        "status": "success",
        "data": goal_detail,
    }


@router.get("/financial-goals/{goal_id}", response_model=Dict[str, Any])
async def get_financial_goal(
    goal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = await GoalsService.get_goal(db, current_user.id, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {
        "status": "success",
        "data": goal,
    }


@router.put("/financial-goals/{goal_id}", response_model=Dict[str, Any])
async def update_financial_goal(
    goal_id: uuid.UUID,
    payload: FinancialGoalUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await GoalsService.update_goal(db, current_user.id, goal_id, payload)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    goal_detail = await GoalsService.get_goal(db, current_user.id, goal_id)
    return {
        "status": "success",
        "data": goal_detail,
    }


@router.delete("/financial-goals/{goal_id}", response_model=Dict[str, Any])
async def delete_financial_goal(
    goal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = await GoalsService.delete_goal(db, current_user.id, goal_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Goal not found")
    await db.commit()
    return {
        "status": "success",
        "message": "Goal deleted successfully",
    }


# --- Investment Mandates ---
@router.get("/mandates", response_model=Dict[str, Any])
async def list_mandates(
    goal_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mandates = await GoalsService.list_mandates(db, current_user.id, goal_id=goal_id)
    return {
        "status": "success",
        "data": mandates,
    }


@router.post("/mandates", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_mandate(
    payload: InvestmentMandateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        mandate = await GoalsService.create_mandate(db, current_user.id, payload)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    mandate_detail = await GoalsService.get_mandate(db, current_user.id, mandate.id)
    return {
        "status": "success",
        "data": mandate_detail,
    }


@router.get("/mandates/{mandate_id}", response_model=Dict[str, Any])
async def get_mandate(
    mandate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mandate = await GoalsService.get_mandate(db, current_user.id, mandate_id)
    if not mandate:
        raise HTTPException(status_code=404, detail="Mandate not found")
    return {
        "status": "success",
        "data": mandate,
    }


@router.put("/mandates/{mandate_id}", response_model=Dict[str, Any])
async def update_mandate(
    mandate_id: uuid.UUID,
    payload: InvestmentMandateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await GoalsService.update_mandate(db, current_user.id, mandate_id, payload)
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    mandate_detail = await GoalsService.get_mandate(db, current_user.id, mandate_id)
    return {
        "status": "success",
        "data": mandate_detail,
    }


@router.delete("/mandates/{mandate_id}", response_model=Dict[str, Any])
async def delete_mandate(
    mandate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = await GoalsService.delete_mandate(db, current_user.id, mandate_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Mandate not found")
    await db.commit()
    return {
        "status": "success",
        "message": "Mandate deleted successfully",
    }


# --- Capital Assignments & Virtual Transfers ---
@router.post("/mandates/{mandate_id}/assignments", response_model=Dict[str, Any])
async def assign_capital(
    mandate_id: uuid.UUID,
    payload: CapitalAssignmentBase,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        assignment = await AssignmentService.assign_capital(
            session=db,
            user_id=current_user.id,
            mandate_id=mandate_id,
            resource_type=payload.resource_type,
            asset_id=payload.asset_id,
            cash_account_id=payload.cash_account_id,
            assigned_quantity=payload.assigned_quantity,
            assigned_amount=payload.assigned_amount,
            notes=payload.notes,
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Return refreshed mandate
    mandate_detail = await GoalsService.get_mandate(db, current_user.id, mandate_id)
    return {
        "status": "success",
        "data": {
            "assignment_id": str(assignment.id),
            "mandate": mandate_detail,
        },
    }


@router.delete("/mandates/assignments/{assignment_id}", response_model=Dict[str, Any])
async def remove_assignment(
    assignment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = await AssignmentService.delete_assignment(db, current_user.id, assignment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Assignment not found")
    await db.commit()
    return {
        "status": "success",
        "message": "Capital assignment removed successfully",
    }


@router.post("/mandates/transfer-capital", response_model=Dict[str, Any])
async def transfer_capital(
    payload: CapitalTransferRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = await AssignmentService.transfer_capital(
            session=db,
            user_id=current_user.id,
            from_mandate_id=payload.from_mandate_id,
            to_mandate_id=payload.to_mandate_id,
            resource_type=payload.resource_type,
            asset_id=payload.asset_id,
            cash_account_id=payload.cash_account_id,
            quantity=payload.quantity,
            amount=payload.amount,
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "status": "success",
        "data": result,
    }


# --- Financial Intelligence Summary & Profile Synthesis ---
@router.get("/financial-intelligence/summary", response_model=Dict[str, Any])
async def get_financial_intelligence_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    summary = await FinancialIntelligenceService.compute_financial_intelligence(db, current_user.id)
    return {
        "status": "success",
        "data": summary,
    }


@router.get("/financial-intelligence/synthesis", response_model=Dict[str, Any])
async def get_financial_profile_synthesis(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    synthesis = await FinancialIntelligenceService.generate_profile_synthesis(db, current_user.id)
    return {
        "status": "success",
        "data": synthesis,
    }


@router.post("/mandates/resolve-assignment-review", response_model=Dict[str, Any])
async def resolve_assignment_review(
    payload: ResolveAssignmentReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = await AssignmentService.resolve_assignment_review(
            session=db,
            user_id=current_user.id,
            asset_id=payload.asset_id,
            mandate_adjustments=payload.mandate_adjustments,
        )
        await db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "status": "success",
        "data": result,
    }
