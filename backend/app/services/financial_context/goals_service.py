from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.asset import Asset
from app.models.cash import CashAccount
from app.models.financial_context import (
    CapitalAssignment,
    FinancialGoal,
    GoalMode,
    GoalPriority,
    GoalStatus,
    GoalType,
    InvestmentMandate,
    MandateStatus,
    MandateType,
    ResourceAssignmentType,
    RiskCapacity,
)
from app.models.investor_profile import InvestorProfile, InvestorProfileVersion
from app.schemas.financial_context import (
    FinancialGoalCreate,
    FinancialGoalUpdate,
    InvestmentMandateCreate,
    InvestmentMandateUpdate,
)
from app.utils.currency import build_rate_map, convert


class GoalsService:
    @staticmethod
    async def _get_global_policy(session: AsyncSession, user_id: uuid.UUID) -> Dict[str, Any]:
        """Fetch active confirmed Investor Profile policy snapshot if present."""
        stmt = (
            select(InvestorProfile)
            .where(InvestorProfile.user_id == user_id)
            .options(selectinload(InvestorProfile.versions))
        )
        res = await session.execute(stmt)
        profile = res.scalar_one_or_none()
        if not profile or not profile.active_version_id:
            return {}

        v_stmt = select(InvestorProfileVersion).where(
            InvestorProfileVersion.id == profile.active_version_id
        )
        version = (await session.execute(v_stmt)).scalar_one_or_none()
        if not version or not version.snapshot:
            return {}

        return version.snapshot.get("policy", {})

    @classmethod
    async def validate_mandate_policy_inheritance(
        cls,
        session: AsyncSession,
        user_id: uuid.UUID,
        policy_rules: Optional[Dict[str, Any]],
        target_allocation: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Enforces that a mandate cannot loosen global hard policy restrictions."""
        if not policy_rules and not target_allocation:
            return

        global_policy = await cls._get_global_policy(session, user_id)
        if not global_policy:
            return

        # 1. Leverage prohibition
        global_restrictions = global_policy.get("restrictions", []) or []
        global_no_leverage = (
            global_policy.get("no_leverage", False)
            or "NO_BORROWING" in global_restrictions
            or "NO_LEVERAGE" in global_restrictions
        )

        if global_no_leverage and policy_rules:
            if policy_rules.get("allow_leverage") is True or policy_rules.get("leverage_allowed") is True:
                raise ValueError(
                    "Mandate cannot loosen global policy prohibition: leverage is prohibited globally"
                )

        # 2. Prohibited asset types
        prohibited = set(global_policy.get("prohibited_asset_types", []) or [])
        if prohibited:
            if target_allocation:
                for asset_type, weight in target_allocation.items():
                    if weight and float(weight) > 0 and asset_type.upper() in prohibited:
                        raise ValueError(
                            f"Mandate cannot allocate to prohibited asset type: {asset_type}"
                        )
            if policy_rules and "allowed_asset_types" in policy_rules:
                allowed = set(policy_rules["allowed_asset_types"])
                overlap = allowed.intersection(prohibited)
                if overlap:
                    raise ValueError(
                        f"Mandate cannot permit globally prohibited asset types: {list(overlap)}"
                    )

        # 3. Single-asset concentration cap
        global_max_single = global_policy.get("max_single_asset_pct")
        if global_max_single is not None and policy_rules:
            local_max_single = policy_rules.get("max_single_asset_pct")
            if local_max_single is not None and float(local_max_single) > float(global_max_single):
                raise ValueError(
                    f"Mandate single-asset limit ({local_max_single}%) cannot loosen global limit of {global_max_single}%"
                )

    # --- Financial Goals ---
    @staticmethod
    async def create_goal(
        session: AsyncSession,
        user_id: uuid.UUID,
        payload: FinancialGoalCreate | Dict[str, Any],
    ) -> FinancialGoal:
        data = payload.model_dump() if isinstance(payload, FinancialGoalCreate) else payload
        goal = FinancialGoal(
            user_id=user_id,
            name=data["name"],
            goal_type=GoalType(data["goal_type"]),
            mode=GoalMode(data.get("mode", GoalMode.TARGET_AMOUNT)),
            target_amount=Decimal(str(data["target_amount"])) if data.get("target_amount") is not None else None,
            target_currency=data.get("target_currency", "TRY").upper(),
            target_date=data.get("target_date"),
            horizon_band=data.get("horizon_band"),
            priority=GoalPriority(data.get("priority", GoalPriority.IMPORTANT)),
            date_flexibility=data.get("date_flexibility", "UNKNOWN"),
            amount_flexibility=data.get("amount_flexibility", "UNKNOWN"),
            status=GoalStatus(data.get("status", GoalStatus.ACTIVE)),
            notes=data.get("notes"),
        )
        session.add(goal)
        await session.flush()
        return goal

    @staticmethod
    async def list_goals(
        session: AsyncSession,
        user_id: uuid.UUID,
        status: Optional[GoalStatus] = None,
    ) -> List[Dict[str, Any]]:
        stmt = (
            select(FinancialGoal)
            .where(FinancialGoal.user_id == user_id)
            .options(
                selectinload(FinancialGoal.mandates).selectinload(InvestmentMandate.assignments).selectinload(CapitalAssignment.asset),
                selectinload(FinancialGoal.mandates).selectinload(InvestmentMandate.assignments).selectinload(CapitalAssignment.cash_account),
            )
            .order_by(FinancialGoal.created_at.asc())
        )
        if status is not None:
            stmt = stmt.where(FinancialGoal.status == status)

        goals = (await session.execute(stmt)).scalars().all()

        # Build rate map for currency conversions
        currencies: set[str] = set()
        for g in goals:
            currencies.add(g.target_currency)
            for m in g.mandates:
                for a in m.assignments:
                    if a.resource_type == ResourceAssignmentType.ASSET and a.asset:
                        currencies.add(a.asset.current_price_currency or "TRY")
                    elif a.resource_type == ResourceAssignmentType.CASH_ACCOUNT and a.cash_account:
                        currencies.add(a.cash_account.currency)

        rate_map = await build_rate_map(currencies, "TRY", db=session)

        results = []
        for g in goals:
            current_funding_try = Decimal("0")
            mandate_summaries = []
            for m in g.mandates:
                m_funding_try = Decimal("0")
                for a in m.assignments:
                    if a.resource_type == ResourceAssignmentType.ASSET and a.asset:
                        p = a.asset.current_price or Decimal("0")
                        val = a.assigned_quantity * p
                        val_try = convert(val, a.asset.current_price_currency or "TRY", "TRY", rate_map)
                        m_funding_try += val_try
                    elif a.resource_type == ResourceAssignmentType.CASH_ACCOUNT and a.cash_account:
                        val = a.assigned_amount
                        val_try = convert(val, a.cash_account.currency, "TRY", rate_map)
                        m_funding_try += val_try
                current_funding_try += m_funding_try
                mandate_summaries.append({
                    "id": m.id,
                    "name": m.name,
                    "mandate_type": m.mandate_type,
                    "status": m.status,
                    "risk_capacity": m.risk_capacity,
                    "assigned_market_value": m_funding_try,
                })

            # Convert funding from TRY to target_currency
            current_funding_goal_curr = convert(current_funding_try, "TRY", g.target_currency, rate_map)
            
            funded_ratio = None
            if g.target_amount and g.target_amount > Decimal("0"):
                funded_ratio = (current_funding_goal_curr / g.target_amount).quantize(Decimal("0.0001"))

            # Derive status assessment
            if not g.target_amount or g.mode == GoalMode.OPEN_ENDED:
                status_assessment = "NOT_TARGETED"
            elif g.target_amount and current_funding_goal_curr >= g.target_amount:
                status_assessment = "FUNDED_NOW"
            elif current_funding_goal_curr == Decimal("0"):
                status_assessment = "UNASSIGNED"
            elif funded_ratio and funded_ratio >= Decimal("0.8"):
                status_assessment = "ON_TRACK"
            else:
                status_assessment = "SHORTFALL"

            remaining_amount = None
            if g.target_amount is not None:
                remaining_amount = max(Decimal("0"), g.target_amount - current_funding_goal_curr)

            months_remaining = None
            time_remaining_text = None
            required_monthly_contribution = None
            projection_assumptions = (
                "Assuming 0% nominal return. No investment returns are assumed or projected."
            )

            if g.target_date:
                today = datetime.now(timezone.utc).date()
                if g.target_date > today:
                    months_remaining = (g.target_date.year - today.year) * 12 + (g.target_date.month - today.month)
                    if g.target_date.day > today.day and months_remaining == 0:
                        months_remaining = 1
                    months_remaining = max(1, months_remaining)

                    years = months_remaining // 12
                    rem_m = months_remaining % 12
                    if years > 0 and rem_m > 0:
                        time_remaining_text = f"{years} yr {rem_m} mo ({months_remaining} months)"
                    elif years > 0:
                        time_remaining_text = f"{years} yr ({months_remaining} months)"
                    else:
                        time_remaining_text = f"{months_remaining} months"

                    if remaining_amount is not None:
                        if remaining_amount > Decimal("0"):
                            required_monthly_contribution = (
                                remaining_amount / Decimal(str(months_remaining))
                            ).quantize(Decimal("0.01"))
                        else:
                            required_monthly_contribution = Decimal("0.00")
                else:
                    months_remaining = 0
                    time_remaining_text = "Target date reached or passed"
                    required_monthly_contribution = Decimal("0.00")

            results.append({
                "id": g.id,
                "user_id": g.user_id,
                "name": g.name,
                "goal_type": g.goal_type,
                "mode": g.mode,
                "target_amount": g.target_amount,
                "target_currency": g.target_currency,
                "target_date": g.target_date,
                "horizon_band": g.horizon_band,
                "priority": g.priority,
                "date_flexibility": g.date_flexibility,
                "amount_flexibility": g.amount_flexibility,
                "status": g.status,
                "notes": g.notes,
                "created_at": g.created_at,
                "updated_at": g.updated_at,
                "mandates": mandate_summaries,
                "current_funding": current_funding_goal_curr,
                "funded_ratio": funded_ratio,
                "remaining_amount": remaining_amount,
                "months_remaining": months_remaining,
                "time_remaining_text": time_remaining_text,
                "required_monthly_contribution": required_monthly_contribution,
                "projection_assumptions": projection_assumptions,
                "status_assessment": status_assessment,
            })
        return results

    @staticmethod
    async def get_goal(session: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        goals = await GoalsService.list_goals(session, user_id)
        return next((g for g in goals if g["id"] == goal_id), None)

    @staticmethod
    async def update_goal(
        session: AsyncSession,
        user_id: uuid.UUID,
        goal_id: uuid.UUID,
        payload: FinancialGoalUpdate | Dict[str, Any],
    ) -> FinancialGoal:
        stmt = select(FinancialGoal).where(
            FinancialGoal.id == goal_id,
            FinancialGoal.user_id == user_id,
        )
        goal = (await session.execute(stmt)).scalar_one_or_none()
        if not goal:
            raise ValueError("Financial goal not found or access denied")

        data = payload.model_dump(exclude_unset=True) if isinstance(payload, FinancialGoalUpdate) else payload

        if "name" in data and data["name"] is not None:
            goal.name = data["name"]
        if "goal_type" in data and data["goal_type"] is not None:
            goal.goal_type = GoalType(data["goal_type"])
        if "mode" in data and data["mode"] is not None:
            goal.mode = GoalMode(data["mode"])
        if "target_amount" in data:
            val = data["target_amount"]
            goal.target_amount = Decimal(str(val)) if val is not None else None
        if "target_currency" in data and data["target_currency"] is not None:
            goal.target_currency = str(data["target_currency"]).upper()
        if "target_date" in data:
            goal.target_date = data["target_date"]
        if "horizon_band" in data:
            goal.horizon_band = data["horizon_band"]
        if "priority" in data and data["priority"] is not None:
            goal.priority = GoalPriority(data["priority"])
        if "date_flexibility" in data and data["date_flexibility"] is not None:
            goal.date_flexibility = data["date_flexibility"]
        if "amount_flexibility" in data and data["amount_flexibility"] is not None:
            goal.amount_flexibility = data["amount_flexibility"]
        if "status" in data and data["status"] is not None:
            goal.status = GoalStatus(data["status"])
        if "notes" in data:
            goal.notes = data["notes"]

        await session.flush()
        return goal

    @staticmethod
    async def delete_goal(session: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID) -> bool:
        stmt = select(FinancialGoal).where(
            FinancialGoal.id == goal_id,
            FinancialGoal.user_id == user_id,
        )
        goal = (await session.execute(stmt)).scalar_one_or_none()
        if not goal:
            return False

        # Unlink linked mandates rather than deleting capital
        m_stmt = select(InvestmentMandate).where(InvestmentMandate.goal_id == goal_id)
        mandates = (await session.execute(m_stmt)).scalars().all()
        for m in mandates:
            m.goal_id = None

        await session.delete(goal)
        await session.flush()
        return True

    # --- Investment Mandates ---
    @classmethod
    async def create_mandate(
        cls,
        session: AsyncSession,
        user_id: uuid.UUID,
        payload: InvestmentMandateCreate | Dict[str, Any],
    ) -> InvestmentMandate:
        data = payload.model_dump() if isinstance(payload, InvestmentMandateCreate) else payload

        goal_id = data.get("goal_id")
        if goal_id:
            g_stmt = select(FinancialGoal).where(
                FinancialGoal.id == goal_id,
                FinancialGoal.user_id == user_id,
            )
            g = (await session.execute(g_stmt)).scalar_one_or_none()
            if not g:
                raise ValueError("Linked financial goal not found or access denied")

        # Validate policy inheritance
        await cls.validate_mandate_policy_inheritance(
            session,
            user_id,
            data.get("policy_rules"),
            data.get("target_allocation"),
        )

        mandate = InvestmentMandate(
            user_id=user_id,
            goal_id=goal_id,
            name=data["name"],
            mandate_type=MandateType(data.get("mandate_type", MandateType.GROWTH)),
            purpose=data.get("purpose"),
            horizon_override=data.get("horizon_override"),
            risk_capacity=RiskCapacity(data["risk_capacity"]) if data.get("risk_capacity") else None,
            target_allocation=data.get("target_allocation"),
            concentration_limits=data.get("concentration_limits"),
            policy_rules=data.get("policy_rules"),
            status=MandateStatus(data.get("status", MandateStatus.ACTIVE)),
        )
        session.add(mandate)
        await session.flush()
        return mandate

    @staticmethod
    async def list_mandates(
        session: AsyncSession,
        user_id: uuid.UUID,
        goal_id: Optional[uuid.UUID] = None,
    ) -> List[Dict[str, Any]]:
        stmt = (
            select(InvestmentMandate)
            .where(InvestmentMandate.user_id == user_id)
            .options(
                selectinload(InvestmentMandate.assignments).selectinload(CapitalAssignment.asset),
                selectinload(InvestmentMandate.assignments).selectinload(CapitalAssignment.cash_account),
                selectinload(InvestmentMandate.goal),
            )
            .order_by(InvestmentMandate.created_at.asc())
        )
        if goal_id is not None:
            stmt = stmt.where(InvestmentMandate.goal_id == goal_id)

        mandates = (await session.execute(stmt)).scalars().all()

        currencies: set[str] = set()
        for m in mandates:
            for a in m.assignments:
                if a.resource_type == ResourceAssignmentType.ASSET and a.asset:
                    currencies.add(a.asset.current_price_currency or "TRY")
                elif a.resource_type == ResourceAssignmentType.CASH_ACCOUNT and a.cash_account:
                    currencies.add(a.cash_account.currency)

        rate_map = await build_rate_map(currencies, "TRY", db=session)

        results = []
        for m in mandates:
            total_value_try = Decimal("0")
            assignment_responses = []
            for a in m.assignments:
                current_market_val = Decimal("0")
                symbol = None
                name = None
                if a.resource_type == ResourceAssignmentType.ASSET and a.asset:
                    symbol = a.asset.symbol
                    name = a.asset.name
                    p = a.asset.current_price or Decimal("0")
                    val = a.assigned_quantity * p
                    current_market_val = convert(val, a.asset.current_price_currency or "TRY", "TRY", rate_map)
                elif a.resource_type == ResourceAssignmentType.CASH_ACCOUNT and a.cash_account:
                    symbol = a.cash_account.currency
                    name = f"Cash ({a.cash_account.currency})"
                    val = a.assigned_amount
                    current_market_val = convert(val, a.cash_account.currency, "TRY", rate_map)

                total_value_try += current_market_val
                assignment_responses.append({
                    "id": a.id,
                    "user_id": a.user_id,
                    "mandate_id": a.mandate_id,
                    "resource_type": a.resource_type,
                    "asset_id": a.asset_id,
                    "cash_account_id": a.cash_account_id,
                    "assigned_quantity": a.assigned_quantity,
                    "assigned_amount": a.assigned_amount,
                    "notes": a.notes,
                    "current_market_value": current_market_val,
                    "resource_symbol": symbol,
                    "resource_name": name,
                    "created_at": a.created_at,
                    "updated_at": a.updated_at,
                })

            results.append({
                "id": m.id,
                "user_id": m.user_id,
                "goal_id": m.goal_id,
                "name": m.name,
                "mandate_type": m.mandate_type,
                "purpose": m.purpose,
                "horizon_override": m.horizon_override,
                "risk_capacity": m.risk_capacity,
                "target_allocation": m.target_allocation,
                "concentration_limits": m.concentration_limits,
                "policy_rules": m.policy_rules,
                "status": m.status,
                "created_at": m.created_at,
                "updated_at": m.updated_at,
                "assignments": assignment_responses,
                "total_assigned_value": total_value_try,
            })
        return results

    @staticmethod
    async def get_mandate(session: AsyncSession, user_id: uuid.UUID, mandate_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        mandates = await GoalsService.list_mandates(session, user_id)
        return next((m for m in mandates if m["id"] == mandate_id), None)

    @classmethod
    async def update_mandate(
        cls,
        session: AsyncSession,
        user_id: uuid.UUID,
        mandate_id: uuid.UUID,
        payload: InvestmentMandateUpdate | Dict[str, Any],
    ) -> InvestmentMandate:
        stmt = select(InvestmentMandate).where(
            InvestmentMandate.id == mandate_id,
            InvestmentMandate.user_id == user_id,
        )
        mandate = (await session.execute(stmt)).scalar_one_or_none()
        if not mandate:
            raise ValueError("Investment mandate not found or access denied")

        data = payload.model_dump(exclude_unset=True) if isinstance(payload, InvestmentMandateUpdate) else payload

        if "goal_id" in data:
            gid = data["goal_id"]
            if gid is not None:
                g_stmt = select(FinancialGoal).where(
                    FinancialGoal.id == gid,
                    FinancialGoal.user_id == user_id,
                )
                if not (await session.execute(g_stmt)).scalar_one_or_none():
                    raise ValueError("Linked financial goal not found or access denied")
            mandate.goal_id = gid

        new_policy = data.get("policy_rules", mandate.policy_rules)
        new_alloc = data.get("target_allocation", mandate.target_allocation)
        await cls.validate_mandate_policy_inheritance(session, user_id, new_policy, new_alloc)

        if "name" in data and data["name"] is not None:
            mandate.name = data["name"]
        if "mandate_type" in data and data["mandate_type"] is not None:
            mandate.mandate_type = MandateType(data["mandate_type"])
        if "purpose" in data:
            mandate.purpose = data["purpose"]
        if "horizon_override" in data:
            mandate.horizon_override = data["horizon_override"]
        if "risk_capacity" in data:
            rc = data["risk_capacity"]
            mandate.risk_capacity = RiskCapacity(rc) if rc else None
        if "target_allocation" in data:
            mandate.target_allocation = data["target_allocation"]
        if "concentration_limits" in data:
            mandate.concentration_limits = data["concentration_limits"]
        if "policy_rules" in data:
            mandate.policy_rules = data["policy_rules"]
        if "status" in data and data["status"] is not None:
            mandate.status = MandateStatus(data["status"])

        await session.flush()
        return mandate

    @staticmethod
    async def delete_mandate(session: AsyncSession, user_id: uuid.UUID, mandate_id: uuid.UUID) -> bool:
        stmt = delete(InvestmentMandate).where(
            InvestmentMandate.id == mandate_id,
            InvestmentMandate.user_id == user_id,
        )
        res = await session.execute(stmt)
        await session.flush()
        return res.rowcount > 0
