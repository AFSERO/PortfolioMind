from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.asset import Asset, AssetType
from app.models.cash import CashAccount
from app.models.financial_context import (
    CapitalAssignment,
    FinancialContext,
    FinancialGoal,
    GoalMode,
    IncomeStability,
    InvestmentMandate,
    MandateType,
    ResourceAssignmentType,
)
from app.models.liability import Liability
from app.models.investor_profile import InvestorProfile, InvestorProfileVersion
from app.services.asset import list_assets_with_stats
from app.services.financial_context.context_service import FinancialContextService
from app.services.financial_context.goals_service import GoalsService
from app.utils.currency import build_rate_map, convert


class FinancialIntelligenceService:
    @staticmethod
    async def compute_financial_intelligence(
        session: AsyncSession,
        user_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Deterministic computation of net worth, liquid net worth, flows, emergency runway,
        speculative cap compliance, and goal progress without LLM arithmetic.
        """
        # 1. Fetch user assets & stats
        assets_with_stats = await list_assets_with_stats(session, user_id)
        
        # 2. Fetch user cash accounts
        ca_stmt = select(CashAccount).where(CashAccount.user_id == user_id)
        cash_accounts = (await session.execute(ca_stmt)).scalars().all()

        # 3. Fetch user liabilities
        l_stmt = select(Liability).where(Liability.user_id == user_id, Liability.is_active == True)
        liabilities = (await session.execute(l_stmt)).scalars().all()

        # 4. Fetch Financial Context
        ctx = await FinancialContextService.get_or_create(session, user_id)

        # 5. Build Currency Rate Map
        currencies = {"TRY"}
        if ctx.planning_currency:
            currencies.add(ctx.planning_currency)
        for a, _ in assets_with_stats:
            currencies.add(a.current_price_currency or "TRY")
        for ca in cash_accounts:
            currencies.add(ca.currency)
        for l in liabilities:
            currencies.add(l.currency)

        rate_map = await build_rate_map(currencies, "TRY", db=session)

        # 6. Total Assets Value & Liquid Assets Value
        total_assets_try = Decimal("0")
        liquid_assets_try = Decimal("0")
        liquid_asset_types = {
            AssetType.STOCK,
            AssetType.FOREX,
            AssetType.PRECIOUS_METALS,
            AssetType.CRYPTO,
            AssetType.FUND,
        }

        for a, stats in assets_with_stats:
            qty = Decimal(str(stats["total_quantity"]))
            p = a.current_price or Decimal("0")
            asset_val_native = qty * p
            asset_val_try = convert(asset_val_native, a.current_price_currency or "TRY", "TRY", rate_map)
            total_assets_try += asset_val_try
            if a.asset_type in liquid_asset_types:
                liquid_assets_try += asset_val_try

        # 7. Total Cash Value
        total_cash_try = Decimal("0")
        for ca in cash_accounts:
            val_try = convert(ca.balance, ca.currency, "TRY", rate_map)
            total_cash_try += val_try

        # 8. Total Liabilities Value & Monthly Debt Payments
        total_liabilities_try = Decimal("0")
        monthly_debt_payments_try = Decimal("0")
        for l in liabilities:
            bal_try = convert(l.current_balance, l.currency, "TRY", rate_map)
            total_liabilities_try += bal_try
            if l.minimum_payment and l.minimum_payment > Decimal("0"):
                pay_try = convert(l.minimum_payment, l.currency, "TRY", rate_map)
                monthly_debt_payments_try += pay_try

        # 9. Net Worth & Liquid Net Worth
        net_worth = total_assets_try + total_cash_try - total_liabilities_try
        liquid_net_worth = liquid_assets_try + total_cash_try - total_liabilities_try

        # 10. Flows, Surplus, and Savings Rate
        monthly_income = ctx.monthly_net_income
        essential_exp = ctx.monthly_essential_expenses
        discretionary_exp = ctx.monthly_discretionary_expenses

        monthly_surplus = None
        savings_rate_pct = None

        if monthly_income is not None and (essential_exp is not None or discretionary_exp is not None):
            outflows = (essential_exp or Decimal("0")) + (discretionary_exp or Decimal("0"))
            monthly_surplus = monthly_income - outflows
            if monthly_income > Decimal("0"):
                savings_rate_pct = ((monthly_surplus / monthly_income) * Decimal("100")).quantize(Decimal("0.01"))

        # 11. Emergency Coverage Months
        # Reserve capital = total cash + liquid capital assigned to RESERVE mandates
        mandates_data = await GoalsService.list_mandates(session, user_id)
        reserve_mandate_val_try = Decimal("0")
        speculative_exposure_val_try = Decimal("0")

        for m in mandates_data:
            if m["mandate_type"] == MandateType.RESERVE:
                reserve_mandate_val_try += m["total_assigned_value"]
            elif m["mandate_type"] == MandateType.SPECULATIVE:
                speculative_exposure_val_try += m["total_assigned_value"]

        # Also add unassigned crypto to speculative exposure if any
        for a, stats in assets_with_stats:
            if a.asset_type == AssetType.CRYPTO:
                # Check if already fully in speculative mandate
                p = a.current_price or Decimal("0")
                tot_val = convert(Decimal(str(stats["total_quantity"])) * p, a.current_price_currency or "TRY", "TRY", rate_map)
                # If not covered in speculative mandates, add difference
                if tot_val > speculative_exposure_val_try:
                    speculative_exposure_val_try = tot_val

        qualifying_reserve_try = total_cash_try + reserve_mandate_val_try
        emergency_coverage_months = None
        if essential_exp is not None and essential_exp > Decimal("0"):
            emergency_coverage_months = (qualifying_reserve_try / essential_exp).quantize(Decimal("0.1"))

        # 12. Debt Ratios
        debt_to_income_pct = None
        if monthly_debt_payments_try > Decimal("0") and monthly_income and monthly_income > Decimal("0"):
            debt_to_income_pct = ((monthly_debt_payments_try / monthly_income) * Decimal("100")).quantize(Decimal("0.01"))

        debt_stock_multiple = None
        if total_liabilities_try > Decimal("0") and monthly_income and monthly_income > Decimal("0"):
            debt_stock_multiple = (total_liabilities_try / (monthly_income * Decimal("12"))).quantize(Decimal("0.01"))

        # 13. Speculative Cap Evaluation
        investable_assets_try = total_assets_try + total_cash_try
        speculative_exposure_pct = None
        if investable_assets_try > Decimal("0"):
            speculative_exposure_pct = ((speculative_exposure_val_try / investable_assets_try) * Decimal("100")).quantize(Decimal("0.01"))

        # Fetch global policy cap if any
        global_policy = await GoalsService._get_global_policy(session, user_id)
        speculative_cap_pct = None
        raw_cap = global_policy.get("speculative_cap_pct")
        if raw_cap is not None:
            speculative_cap_pct = Decimal(str(raw_cap))

        speculative_cap_breached = False
        if speculative_cap_pct is not None and speculative_exposure_pct is not None:
            if speculative_exposure_pct > speculative_cap_pct:
                speculative_cap_breached = True

        # 14. Earmarked vs Unassigned Capital
        total_assigned_capital_try = sum((m["total_assigned_value"] for m in mandates_data), Decimal("0"))
        
        # Calculate unassigned assets & cash
        unassigned_assets_val_try = Decimal("0")
        for a, stats in assets_with_stats:
            total_qty = Decimal(str(stats["total_quantity"]))
            p = a.current_price or Decimal("0")
            # sum assigned for this asset
            assigned_qty = Decimal("0")
            for m in mandates_data:
                for assign in m["assignments"]:
                    if assign.get("asset_id") == a.id:
                        assigned_qty += Decimal(str(assign["assigned_quantity"]))
            unassigned_qty = max(Decimal("0"), total_qty - assigned_qty)
            val_native = unassigned_qty * p
            unassigned_assets_val_try += convert(val_native, a.current_price_currency or "TRY", "TRY", rate_map)

        unassigned_cash_val_try = Decimal("0")
        for ca in cash_accounts:
            total_bal = max(Decimal("0"), ca.balance)
            assigned_amt = Decimal("0")
            for m in mandates_data:
                for assign in m["assignments"]:
                    if assign.get("cash_account_id") == ca.id:
                        assigned_amt += Decimal(str(assign["assigned_amount"]))
            unassigned_amt = max(Decimal("0"), total_bal - assigned_amt)
            unassigned_cash_val_try += convert(unassigned_amt, ca.currency, "TRY", rate_map)

        # 15. Goals Breakdown
        goals_list = await GoalsService.list_goals(session, user_id)
        goals_progress = []
        for g in goals_list:
            shortfall = None
            if g["target_amount"] and g["current_funding"] < g["target_amount"]:
                shortfall = g["target_amount"] - g["current_funding"]

            goals_progress.append({
                "goal_id": g["id"],
                "goal_name": g["name"],
                "goal_type": g["goal_type"],
                "target_amount": g["target_amount"],
                "target_currency": g["target_currency"],
                "target_date": g["target_date"],
                "current_funding": g["current_funding"],
                "funded_ratio": g["funded_ratio"],
                "remaining_amount": g["remaining_amount"],
                "months_remaining": g["months_remaining"],
                "time_remaining_text": g["time_remaining_text"],
                "required_monthly_contribution": g["required_monthly_contribution"],
                "projection_assumptions": g["projection_assumptions"],
                "shortfall": shortfall,
                "status_assessment": g["status_assessment"],
                "mandate_count": len(g["mandates"]),
            })

        warnings = []
        if speculative_cap_breached:
            warnings.append(
                f"Speculative exposure ({speculative_exposure_pct}%) exceeds global policy limit of {speculative_cap_pct}%"
            )
        if emergency_coverage_months is not None and emergency_coverage_months < Decimal("3.0"):
            warnings.append(
                f"Emergency reserve covers only {emergency_coverage_months} months of essential expenses (recommended: >= 3 months)"
            )
        if monthly_surplus is not None and monthly_surplus < Decimal("0"):
            warnings.append("Monthly cash flow is negative (cash deficit)")

        freshness_status = FinancialIntelligenceService.get_freshness_status(
            ctx.last_confirmed_at, ctx.updated_at
        )
        if freshness_status in ("REVIEW_DUE", "STALE"):
            ref_dt = ctx.last_confirmed_at or ctx.updated_at
            now_dt = datetime.now(timezone.utc)
            if ref_dt and ref_dt.tzinfo is None:
                ref_dt = ref_dt.replace(tzinfo=timezone.utc)
            days = (now_dt - ref_dt).days if ref_dt else 0
            warnings.append(
                f"Financial context data is {freshness_status.lower().replace('_', ' ')} (last confirmed {days} days ago). Please review."
            )

        coverage_state = {
            "income": "KNOWN" if monthly_income is not None else "UNKNOWN",
            "expenses": "KNOWN" if (essential_exp is not None or discretionary_exp is not None) else "UNKNOWN",
            "assets": "RECORDED",
            "liabilities": "RECORDED" if liabilities else "NONE_RECORDED",
        }

        return {
            "reporting_currency": "TRY",
            "net_worth": net_worth.quantize(Decimal("0.01")),
            "liquid_net_worth": liquid_net_worth.quantize(Decimal("0.01")),
            "total_assets_value": total_assets_try.quantize(Decimal("0.01")),
            "total_cash_value": total_cash_try.quantize(Decimal("0.01")),
            "total_liabilities_value": total_liabilities_try.quantize(Decimal("0.01")),
            "monthly_net_income": monthly_income,
            "monthly_essential_expenses": essential_exp,
            "monthly_discretionary_expenses": discretionary_exp,
            "monthly_surplus": monthly_surplus,
            "savings_rate_pct": savings_rate_pct,
            "emergency_coverage_months": emergency_coverage_months,
            "debt_to_income_pct": debt_to_income_pct,
            "debt_stock_multiple": debt_stock_multiple,
            "speculative_exposure_value": speculative_exposure_val_try.quantize(Decimal("0.01")),
            "speculative_exposure_pct": speculative_exposure_pct,
            "speculative_cap_pct": speculative_cap_pct,
            "speculative_cap_breached": speculative_cap_breached,
            "total_assigned_capital": total_assigned_capital_try.quantize(Decimal("0.01")),
            "unassigned_assets_value": unassigned_assets_val_try.quantize(Decimal("0.01")),
            "unassigned_cash_value": unassigned_cash_val_try.quantize(Decimal("0.01")),
            "goals": goals_progress,
            "coverage_state": coverage_state,
            "warnings": warnings,
        }

    @staticmethod
    def get_freshness_status(
        last_confirmed_at: Optional[datetime], updated_at: Optional[datetime] = None
    ) -> str:
        ref_dt = last_confirmed_at or updated_at
        if not ref_dt:
            return "UNKNOWN"
        now = datetime.now(timezone.utc)
        if ref_dt.tzinfo is None:
            ref_dt = ref_dt.replace(tzinfo=timezone.utc)
        days = (now - ref_dt).days
        if days <= 90:
            return "CURRENT"
        elif days <= 180:
            return "REVIEW_DUE"
        else:
            return "STALE"

    @classmethod
    async def generate_profile_synthesis(
        cls,
        session: AsyncSession,
        user_id: uuid.UUID,
    ) -> Dict[str, Any]:
        from app.services.financial_context.assignment_service import AssignmentService

        intel = await cls.compute_financial_intelligence(session, user_id)
        ctx = await FinancialContextService.get_or_create(session, user_id)

        # Profile & Policy snapshot
        p_stmt = (
            select(InvestorProfile)
            .where(InvestorProfile.user_id == user_id)
            .options(selectinload(InvestorProfile.versions))
        )
        p_res = await session.execute(p_stmt)
        profile = p_res.scalar_one_or_none()

        active_version = None
        if profile and profile.active_version_id:
            v_stmt = select(InvestorProfileVersion).where(
                InvestorProfileVersion.id == profile.active_version_id
            )
            active_version = (await session.execute(v_stmt)).scalar_one_or_none()

        snapshot = active_version.snapshot if active_version and active_version.snapshot else {}
        policy = snapshot.get("policy", {})

        # Freshness
        freshness = cls.get_freshness_status(ctx.last_confirmed_at, ctx.updated_at)

        # 1. Investor Profile Summary
        profile_summary = {
            "has_profile": profile is not None and active_version is not None,
            "version_number": active_version.version_number if active_version else None,
            "risk_tolerance": snapshot.get("risk_tolerance", "UNKNOWN"),
            "investment_horizon": snapshot.get("investment_horizon", "UNKNOWN"),
            "knowledge_level": snapshot.get("knowledge_level", "UNKNOWN"),
            "global_policy": policy,
        }

        # 2. Cash Flow & Surplus Summary
        income = intel.get("monthly_net_income")
        surplus = intel.get("monthly_surplus")
        savings_rate = intel.get("savings_rate_pct")
        if income is not None and surplus is not None:
            if surplus > Decimal("0"):
                flow_assessment = f"Positive cash flow with surplus of {surplus:,.2f} {intel['reporting_currency']}/mo ({savings_rate}% savings rate)."
            elif surplus == Decimal("0"):
                flow_assessment = "Cash flow is exactly balanced with zero net monthly savings."
            else:
                flow_assessment = f"Cash flow deficit of {abs(surplus):,.2f} {intel['reporting_currency']}/mo."
        else:
            flow_assessment = "Income or expenses are not fully declared; cash flow cannot be determined."

        cash_flow_summary = {
            "monthly_net_income": income,
            "monthly_essential_expenses": intel.get("monthly_essential_expenses"),
            "monthly_discretionary_expenses": intel.get("monthly_discretionary_expenses"),
            "monthly_surplus": surplus,
            "savings_rate_pct": savings_rate,
            "income_stability": ctx.income_stability.value,
            "assessment": flow_assessment,
        }

        # 3. Emergency Reserve Adequacy
        em_months = intel.get("emergency_coverage_months")
        if em_months is not None:
            if em_months >= Decimal("6.0"):
                em_assessment = f"Strong emergency reserve covering {em_months} months of essential expenses."
            elif em_months >= Decimal("3.0"):
                em_assessment = f"Adequate emergency reserve covering {em_months} months."
            else:
                em_assessment = f"Vulnerable: emergency reserve covers only {em_months} months (recommended: >= 3 months)."
        else:
            em_assessment = "Emergency reserve adequacy cannot be assessed without essential monthly expenses."

        reserve_summary = {
            "emergency_coverage_months": em_months,
            "qualifying_reserve_value": intel.get("total_cash_value", Decimal("0")),
            "reserve_self_report": ctx.reserve_self_report,
            "assessment": em_assessment,
        }

        # 4. Goal Architecture Summary
        goals = intel.get("goals", [])
        total_target = sum((Decimal(str(g["target_amount"])) for g in goals if g.get("target_amount")), Decimal("0"))
        total_funded = sum((Decimal(str(g["current_funding"])) for g in goals), Decimal("0"))
        status_counts: Dict[str, int] = {}
        for g in goals:
            st = g["status_assessment"]
            status_counts[st] = status_counts.get(st, 0) + 1

        goal_summary = {
            "total_goals_count": len(goals),
            "total_target_amount": total_target,
            "total_current_funding": total_funded,
            "overall_funding_ratio": (total_funded / total_target).quantize(Decimal("0.0001")) if total_target > Decimal("0") else None,
            "status_distribution": status_counts,
        }

        # 5. Debt Posture Summary
        debt_tot = intel.get("total_liabilities_value", Decimal("0"))
        dti = intel.get("debt_to_income_pct")
        d_mult = intel.get("debt_stock_multiple")
        if debt_tot == Decimal("0"):
            debt_assessment = "No debt liabilities recorded."
        elif dti and dti > Decimal("40.0"):
            debt_assessment = f"High debt burden: debt service is {dti}% of monthly income."
        else:
            debt_assessment = f"Moderate/manageable debt posture with total balance of {debt_tot:,.2f} {intel['reporting_currency']}."

        debt_summary = {
            "total_liabilities": debt_tot,
            "debt_to_income_pct": dti,
            "debt_stock_multiple": d_mult,
            "assessment": debt_assessment,
        }

        # 6. Mandate Alignment Summary
        mandates_data = await GoalsService.list_mandates(session, user_id)
        spec_cap_breached = intel.get("speculative_cap_breached", False)

        unassigned_res = await AssignmentService.get_unassigned_resources(session, user_id)
        has_review_req = any(a.get("reconciliation_status") == "ASSIGNMENT_REVIEW_REQUIRED" for a in unassigned_res.get("assets", []))

        mandate_summary = {
            "total_mandates": len(mandates_data),
            "total_assigned_capital": intel.get("total_assigned_capital", Decimal("0")),
            "unassigned_assets_value": intel.get("unassigned_assets_value", Decimal("0")),
            "unassigned_cash_value": intel.get("unassigned_cash_value", Decimal("0")),
            "speculative_exposure_pct": intel.get("speculative_exposure_pct"),
            "speculative_cap_pct": intel.get("speculative_cap_pct"),
            "speculative_cap_breached": spec_cap_breached,
            "reconciliation_status": "ASSIGNMENT_REVIEW_REQUIRED" if has_review_req else "CONSISTENT",
        }

        # 7. Open Questions and Missing Knowledge Gaps
        gaps = []
        if income is None:
            gaps.append("Monthly net income is unknown.")
        if ctx.monthly_essential_expenses is None:
            gaps.append("Monthly essential expenses are unknown.")
        if ctx.income_stability == IncomeStability.UNKNOWN:
            gaps.append("Income stability is not declared.")
        if not goals:
            gaps.append("No explicit financial goals have been created.")
        if has_review_req:
            gaps.append("Asset sale occurred with unattributed mandate assignment. Review required to assign sold units.")
        if spec_cap_breached:
            gaps.append("Speculative asset allocation exceeds declared global portfolio policy limit.")
        if not profile or not active_version:
            gaps.append("Investor profile assessment has not been completed.")

        # 8. Source Traceability and Confidence Limitations
        ctx_prov = ctx.provenance or {}

        def _trace(field_key: str, value: Any) -> Dict[str, Any]:
            if value is None:
                return {
                    "source": "UNKNOWN",
                    "confidence": 0.0,
                    "limitation": "Value has not been declared or confirmed.",
                }
            entry = ctx_prov.get(field_key, {})
            src = entry.get("source", "EXPLICIT")
            if src == "AI_INTERPRETED":
                return {
                    "source": "AI_INTERPRETED",
                    "confidence": float(entry.get("confidence", 0.85)),
                    "limitation": "Conversationally inferred by Copilot; non-authoritative until user confirmed.",
                }
            return {
                "source": "EXPLICIT",
                "confidence": 1.0,
                "limitation": "Direct user declaration.",
            }

        source_traceability = {
            "monthly_net_income": _trace("monthly_net_income", income),
            "monthly_essential_expenses": _trace("monthly_essential_expenses", ctx.monthly_essential_expenses),
            "monthly_discretionary_expenses": _trace("monthly_discretionary_expenses", ctx.monthly_discretionary_expenses),
            "net_worth": {
                "source": "DERIVED",
                "confidence": 1.0,
                "limitation": "Deterministically computed from holdings, cash accounts, and active liabilities.",
            },
            "liquid_net_worth": {
                "source": "DERIVED",
                "confidence": 1.0,
                "limitation": "Deterministically computed excluding non-liquid assets.",
            },
            "emergency_coverage_months": {
                "source": "DERIVED",
                "confidence": 1.0 if (ctx.monthly_essential_expenses and ctx.monthly_essential_expenses > 0) else 0.0,
                "limitation": "Calculated as qualifying reserves divided by essential monthly expenses." if ctx.monthly_essential_expenses else "Requires essential expenses to compute.",
            },
            "goals_funding": {
                "source": "DERIVED",
                "confidence": 1.0,
                "limitation": "Computed from mandate capital assignments against goal targets.",
            },
            "mandates_assignments": {
                "source": "EXPLICIT",
                "confidence": 1.0,
                "limitation": "Explicit user capital allocations.",
            },
            "investor_profile": {
                "source": "EXPLICIT" if active_version else "UNKNOWN",
                "confidence": 1.0 if active_version else 0.0,
                "limitation": "Active confirmed profile version present." if active_version else "Investor assessment has not been completed.",
            },
        }

        confidence_limitations = [
            "Financial profile synthesis is an analytical snapshot and is non-authoritative.",
            "All market valuations rely on current prices and exchange rates without future return guarantees (0% projected nominal return).",
        ]
        if any(item.get("source") == "AI_INTERPRETED" for item in source_traceability.values()):
            confidence_limitations.append("One or more financial flow values were inferred conversationally and await explicit user confirmation.")
        if any(item.get("source") == "UNKNOWN" for item in source_traceability.values()):
            confidence_limitations.append("Incomplete declarations exist; missing fields are preserved as UNKNOWN without assumed values.")

        return {
            "generated_at": datetime.now(timezone.utc),
            "freshness_status": freshness,
            "is_authoritative": False,
            "disclaimer": (
                "This synthesis is an automated analytical summary for informational and planning assistance only. "
                "It is non-authoritative and does not constitute formal financial advice."
            ),
            "investor_profile_summary": profile_summary,
            "cash_flow_and_surplus_summary": cash_flow_summary,
            "emergency_reserve_adequacy": reserve_summary,
            "goal_architecture_summary": goal_summary,
            "debt_posture_summary": debt_summary,
            "mandate_alignment_summary": mandate_summary,
            "open_questions_and_gaps": gaps,
            "source_traceability": source_traceability,
            "confidence_limitations": confidence_limitations,
        }
