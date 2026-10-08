from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial_context import (
    FinancialContext,
    FinancialScope,
    IncomeStability,
)
from app.schemas.financial_context import (
    FinancialContextCreate,
    FinancialContextUpdate,
)


class FinancialContextService:
    @staticmethod
    async def get_or_create(session: AsyncSession, user_id: uuid.UUID) -> FinancialContext:
        stmt = select(FinancialContext).where(FinancialContext.user_id == user_id)
        result = await session.execute(stmt)
        ctx = result.scalar_one_or_none()
        if ctx is None:
            ctx = FinancialContext(
                user_id=user_id,
                financial_scope=FinancialScope.INDIVIDUAL,
                planning_currency="TRY",
                spending_currencies=["TRY"],
                income_stability=IncomeStability.UNKNOWN,
                income_sources=[],
                non_debt_obligations=[],
                expected_changes=[],
            )
            session.add(ctx)
            await session.flush()
        return ctx

    @staticmethod
    async def update(
        session: AsyncSession,
        user_id: uuid.UUID,
        payload: FinancialContextUpdate | Dict[str, Any],
    ) -> FinancialContext:
        ctx = await FinancialContextService.get_or_create(session, user_id)

        data = payload.model_dump(exclude_unset=True) if isinstance(payload, FinancialContextUpdate) else payload

        # Process income_sources if provided
        if "income_sources" in data and data["income_sources"] is not None:
            raw_sources = data["income_sources"]
            sources_list = []
            derived_income = Decimal("0")
            has_numeric_source = False
            for s in raw_sources:
                s_dict = s if isinstance(s, dict) else s.model_dump()
                sources_list.append(s_dict)
                amt = s_dict.get("amount")
                if amt is not None:
                    derived_income += Decimal(str(amt))
                    has_numeric_source = True
            ctx.income_sources = sources_list
            # If monthly_net_income wasn't explicitly given in this update, update it if sources had numbers
            if "monthly_net_income" not in data and has_numeric_source:
                ctx.monthly_net_income = derived_income

        if "monthly_net_income" in data:
            val = data["monthly_net_income"]
            ctx.monthly_net_income = Decimal(str(val)) if val is not None else None

        if "financial_scope" in data and data["financial_scope"] is not None:
            ctx.financial_scope = FinancialScope(data["financial_scope"])

        if "planning_currency" in data and data["planning_currency"] is not None:
            ctx.planning_currency = str(data["planning_currency"]).upper()

        if "spending_currencies" in data and data["spending_currencies"] is not None:
            ctx.spending_currencies = [str(c).upper() for c in data["spending_currencies"]]

        if "income_stability" in data and data["income_stability"] is not None:
            ctx.income_stability = IncomeStability(data["income_stability"])

        if "monthly_essential_expenses" in data:
            val = data["monthly_essential_expenses"]
            ctx.monthly_essential_expenses = Decimal(str(val)) if val is not None else None

        if "monthly_discretionary_expenses" in data:
            val = data["monthly_discretionary_expenses"]
            ctx.monthly_discretionary_expenses = Decimal(str(val)) if val is not None else None

        if "non_debt_obligations" in data and data["non_debt_obligations"] is not None:
            raw_obs = data["non_debt_obligations"]
            ctx.non_debt_obligations = [o if isinstance(o, dict) else o.model_dump() for o in raw_obs]

        if "dependents_count" in data:
            ctx.dependents_count = data["dependents_count"]

        if "external_support" in data:
            ctx.external_support = data["external_support"]

        if "expected_changes" in data and data["expected_changes"] is not None:
            raw_changes = data["expected_changes"]
            ctx.expected_changes = [c if isinstance(c, dict) else c.model_dump() for c in raw_changes]

        if "coverage_declarations" in data:
            ctx.coverage_declarations = data["coverage_declarations"]

        if "reserve_self_report" in data:
            ctx.reserve_self_report = data["reserve_self_report"]

        if "user_surplus_estimate" in data:
            val = data["user_surplus_estimate"]
            ctx.user_surplus_estimate = Decimal(str(val)) if val is not None else None

        prov = dict(ctx.provenance or {})
        if "provenance" in data and data["provenance"] is not None:
            prov.update(data["provenance"])
        else:
            default_source = data.get("source", "EXPLICIT")
            for field in [
                "monthly_net_income",
                "monthly_essential_expenses",
                "monthly_discretionary_expenses",
                "income_stability",
                "reserve_self_report",
                "user_surplus_estimate",
            ]:
                if field in data and data[field] is not None:
                    prov[field] = {
                        "source": default_source,
                        "confidence": 1.0 if default_source == "EXPLICIT" else 0.8,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
        ctx.provenance = prov

        await session.flush()
        return ctx

    @staticmethod
    async def confirm(session: AsyncSession, user_id: uuid.UUID) -> FinancialContext:
        ctx = await FinancialContextService.get_or_create(session, user_id)
        ctx.last_confirmed_at = datetime.now(timezone.utc)
        await session.flush()
        return ctx
