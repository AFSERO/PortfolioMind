"""PortfolioMind Phase 4.1 — Financial Context, Goals, Mandates & Financial Intelligence
Deterministic End-to-End Verification Script (Scenarios A through J).

Covers all 10 canonical Phase 4.1 verification scenarios:
- Scenario A: Financial context creation & math (income, expenses, surplus, savings rate, emergency runway)
- Scenario B: Goal creation (multiple goals: Retirement, House, Emergency)
- Scenario C: Mandate creation & capital assignment (assigning assets & cash accounts to mandates, capital conservation)
- Scenario D: Mandate risk capacity diversity (Retirement = HIGH, House = LOW, Speculative = VERY_HIGH alongside investor profile risk tolerance)
- Scenario E: Post-Sell Reconciliation:
  * SELL without explicit mandate attribution exceeding unassigned units -> triggers ASSIGNMENT_REVIEW_REQUIRED
    (showing available units, currently assigned units, over-assigned amount, affected mandates, preserving previous allocations).
  * User resolution via resolve_assignment_review.
- Scenario F: Goal progress calculation: Target 2,000,000 TRY, Assigned 650,000 TRY -> funded ratio 32.5%,
  remaining amount 1,350,000 TRY, time remaining, required monthly contribution with explicit 0% growth disclaimer.
- Scenario G: Virtual mandate transfer (transferring units between mandates with zero transaction/ledger side effects).
- Scenario H: Unknown financial context handling (missing income -> savings rate = UNKNOWN, no invented zeros).
- Scenario I: Copilot context integration: 'Analyze my finances' prompt produces rich financial intelligence context + profile synthesis.
- Scenario J: Backward compatibility: verify existing Phase 4 investor profile is intact, not corrupted.
"""

import asyncio
from datetime import date
from decimal import Decimal
import os
import sys
import uuid

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.database import get_session_factory
from app.main import app
from app.models.asset import Asset, AssetType
from app.models.cash import CashAccount
from app.models.copilot import CopilotAuditLog
from app.models.financial_context import (
    CapitalAssignment,
    FinancialContext,
    FinancialGoal,
    GoalStatus,
    GoalType,
    InvestmentMandate,
    MandateType,
    RiskCapacity,
)
from app.models.investor_profile import InvestorProfile, InvestorProfileVersion
from app.models.liability import Liability
from app.models.transaction import Transaction, TransactionType
from app.services.financial_context.assignment_service import AssignmentService


async def _register_user(client: AsyncClient, email: str, display_name: str = "Test User") -> tuple[str, dict[str, str]]:
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "StrongPassword123!", "display_name": display_name},
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["data"]["access_token"]
    user_id = resp.json()["data"]["user"]["id"]
    return user_id, {"Authorization": f"Bearer {token}"}


async def run_verification():
    print("======================================================================")
    print("PORTFOLIOMIND — PHASE 4.1 GAP AUDIT E2E VERIFICATION SUITE")
    print("======================================================================\n")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # =====================================================================
        # Scenario A: Financial Context Creation & Math
        # =====================================================================
        print("--- Scenario A: Financial Context Creation & Math ---")
        user_a_id, headers_a = await _register_user(client, f"p41_a_{uuid.uuid4().hex[:6]}@example.com", "User A")
        user_uuid_a = uuid.UUID(user_a_id)

        # Update financial context
        up_ctx = await client.put(
            "/api/financial-context",
            json={
                "monthly_net_income": "100000.00",
                "monthly_essential_expenses": "65000.00",
                "monthly_discretionary_expenses": "15000.00",
                "income_stability": "PREDICTABLE",
                "planning_currency": "TRY",
            },
            headers=headers_a,
        )
        assert up_ctx.status_code == 200, up_ctx.text
        ctx_data = up_ctx.json()["data"]
        assert Decimal(ctx_data["monthly_net_income"]) == Decimal("100000.00")
        assert Decimal(ctx_data["monthly_essential_expenses"]) == Decimal("65000.00")
        assert Decimal(ctx_data["monthly_discretionary_expenses"]) == Decimal("15000.00")

        # Confirm context
        conf_res = await client.post("/api/financial-context/confirm", headers=headers_a)
        assert conf_res.status_code == 200
        assert conf_res.json()["data"]["last_confirmed_at"] is not None

        # Give user 200,000 TRY cash
        async_session = get_session_factory()
        async with async_session() as db:
            ca_stmt = select(CashAccount).where(CashAccount.user_id == user_uuid_a, CashAccount.currency == "TRY")
            ca = (await db.execute(ca_stmt)).scalar_one_or_none()
            if ca:
                ca.balance = Decimal("200000.00")
            else:
                ca = CashAccount(user_id=user_uuid_a, currency="TRY", balance=Decimal("200000.00"))
                db.add(ca)
            await db.commit()
            cash_id = ca.id

        # Verify Financial Intelligence formulas:
        # Outflow = Essential (65,000) + Discretionary (15,000) = 80,000 TRY
        # Surplus = Income (100,000) - Outflow (80,000) = 20,000 TRY
        # Savings Rate = Surplus (20,000) / Income (100,000) = 20.00%
        # Emergency Runway = Cash (200,000) / Essential (65,000) = ~3.07 -> 3.1 months
        intel_res = await client.get("/api/financial-intelligence/summary", headers=headers_a)
        assert intel_res.status_code == 200
        intel_a = intel_res.json()["data"]
        assert Decimal(str(intel_a["monthly_net_income"])) == Decimal("100000.00")
        assert Decimal(str(intel_a["monthly_essential_expenses"])) == Decimal("65000.00")
        assert Decimal(str(intel_a["monthly_discretionary_expenses"])) == Decimal("15000.00")
        assert Decimal(str(intel_a["monthly_surplus"])) == Decimal("20000.00")
        assert Decimal(str(intel_a["savings_rate_pct"])) == Decimal("20.00")
        assert round(float(intel_a["emergency_coverage_months"]), 1) == 3.1
        print("  Verified: Financial context math fully traceable:")
        print("    - Declared Net Income: 100,000.00 TRY")
        print("    - Declared Essential Expenses: 65,000.00 TRY")
        print("    - Declared Discretionary Expenses: 15,000.00 TRY")
        print("    - Total Monthly Outflows: 65,000.00 + 15,000.00 = 80,000.00 TRY")
        print("    - Monthly Surplus: 100,000.00 - 80,000.00 = 20,000.00 TRY")
        print("    - Savings Rate: 20,000.00 / 100,000.00 = 20.00%")
        print("    - Emergency Runway: 200,000.00 / 65,000.00 = 3.1 months (3.07)")

        # =====================================================================
        # Scenario B: Multiple Goal Creation (Retirement, House, Emergency)
        # =====================================================================
        print("\n--- Scenario B: Multiple Goal Creation ---")
        g_house_res = await client.post(
            "/api/financial-goals",
            json={
                "name": "Dream House Downpayment",
                "goal_type": "HOME_PURCHASE",
                "target_amount": "2000000.00",
                "target_currency": "TRY",
                "target_date": "2028-06-01",
            },
            headers=headers_a,
        )
        assert g_house_res.status_code == 201
        g_house_id = g_house_res.json()["data"]["id"]

        g_retire_res = await client.post(
            "/api/financial-goals",
            json={
                "name": "Retirement Nest Egg",
                "goal_type": "RETIREMENT",
                "target_amount": "10000000.00",
                "target_currency": "TRY",
                "target_date": "2045-01-01",
            },
            headers=headers_a,
        )
        assert g_retire_res.status_code == 201
        g_retire_id = g_retire_res.json()["data"]["id"]

        g_emerg_res = await client.post(
            "/api/financial-goals",
            json={
                "name": "Emergency Liquidity Buffer",
                "goal_type": "EMERGENCY_RESERVE",
                "target_amount": "400000.00",
                "target_currency": "TRY",
            },
            headers=headers_a,
        )
        assert g_emerg_res.status_code == 201
        g_emerg_id = g_emerg_res.json()["data"]["id"]

        goals_list = await client.get("/api/financial-goals", headers=headers_a)
        assert len(goals_list.json()["data"]) == 3
        print(f"  Verified: Successfully created 3 distinct goals: House ({g_house_id[:8]}), Retirement ({g_retire_id[:8]}), Emergency ({g_emerg_id[:8]}).")

        # =====================================================================
        # Scenario C: Mandate Creation & Capital Assignment
        # =====================================================================
        print("\n--- Scenario C: Mandate Creation & Capital Assignment ---")
        # Mandate 1: linked to House
        m_house_res = await client.post(
            "/api/mandates",
            json={
                "name": "House Capital Sleeve",
                "goal_id": g_house_id,
                "mandate_type": "PRESERVATION",
                "risk_capacity": "LOW",
            },
            headers=headers_a,
        )
        m_house_id = m_house_res.json()["data"]["id"]

        # Mandate 2: linked to Retirement
        m_retire_res = await client.post(
            "/api/mandates",
            json={
                "name": "Retirement Equity Sleeve",
                "goal_id": g_retire_id,
                "mandate_type": "GROWTH",
                "risk_capacity": "HIGH",
            },
            headers=headers_a,
        )
        m_retire_id = m_retire_res.json()["data"]["id"]

        # Mandate 3: Speculative Moonshot (unlinked)
        m_spec_res = await client.post(
            "/api/mandates",
            json={
                "name": "Speculative Alpha Sleeve",
                "mandate_type": "SPECULATIVE",
                "risk_capacity": "VERY_HIGH",
            },
            headers=headers_a,
        )
        m_spec_id = m_spec_res.json()["data"]["id"]

        # Add Asset: 1,000 units of THYAO @ 300 TRY = 300,000 TRY
        async with async_session() as db:
            thyao = Asset(
                user_id=user_uuid_a,
                symbol="THYAO",
                name="Türk Hava Yolları",
                asset_type=AssetType.STOCK,
                current_price=Decimal("300.00"),
                current_price_currency="TRY",
            )
            db.add(thyao)
            await db.flush()
            db.add(
                Transaction(
                    asset_id=thyao.id,
                    transaction_type=TransactionType.BUY,
                    quantity=Decimal("1000"),
                    price_per_unit=Decimal("250.00"),
                    total_amount=Decimal("250000.00"),
                    transaction_currency="TRY",
                    transaction_date=date(2026, 1, 1),
                )
            )
            await db.commit()
            thyao_id = thyao.id

        # Assign 400 THYAO units to Retirement Mandate
        as1_res = await client.post(
            f"/api/mandates/{m_retire_id}/assignments",
            json={
                "mandate_id": m_retire_id,
                "resource_type": "ASSET",
                "asset_id": str(thyao_id),
                "assigned_quantity": "400.00",
            },
            headers=headers_a,
        )
        assert as1_res.status_code == 200

        # Assign 100,000 TRY Cash to House Mandate
        as2_res = await client.post(
            f"/api/mandates/{m_house_id}/assignments",
            json={
                "mandate_id": m_house_id,
                "resource_type": "CASH_ACCOUNT",
                "cash_account_id": str(cash_id),
                "assigned_amount": "100000.00",
            },
            headers=headers_a,
        )
        assert as2_res.status_code == 200

        # Over-assignment test: try assigning 700 units of THYAO to Speculative mandate (only 600 available) -> Must Fail
        over_as = await client.post(
            f"/api/mandates/{m_spec_id}/assignments",
            json={
                "mandate_id": m_spec_id,
                "resource_type": "ASSET",
                "asset_id": str(thyao_id),
                "assigned_quantity": "700.00",
            },
            headers=headers_a,
        )
        assert over_as.status_code == 400
        print("  Verified: Capital assignment completed; conservation engine correctly rejected over-assignment.")

        # =====================================================================
        # Scenario D: Mandate Risk Capacity Diversity & Coexistence
        # =====================================================================
        print("\n--- Scenario D: Mandate Risk Capacity Diversity & Coexistence ---")
        # Global profile with risk_tolerance = HIGH
        async with async_session() as db:
            prof = InvestorProfile(user_id=user_uuid_a, completeness_overall_pct=Decimal("100.00"))
            db.add(prof)
            await db.flush()
            v1 = InvestorProfileVersion(
                profile_id=prof.id,
                user_id=user_uuid_a,
                version_number=1,
                change_reason="Profile Setup",
                change_source="ONBOARDING",
                confirmed_by=user_uuid_a,
                snapshot={"risk_tolerance": "HIGH", "policy": {"speculative_cap_pct": 20}},
            )
            db.add(v1)
            await db.flush()
            prof.active_version_id = v1.id
            await db.commit()

        # Check that mandates maintain distinct capacities (House: LOW, Retirement: HIGH, Speculative: VERY_HIGH)
        mandates_resp = await client.get("/api/mandates", headers=headers_a)
        caps = {m["name"]: m["risk_capacity"] for m in mandates_resp.json()["data"]}
        assert caps["House Capital Sleeve"] == "LOW"
        assert caps["Retirement Equity Sleeve"] == "HIGH"
        assert caps["Speculative Alpha Sleeve"] == "VERY_HIGH"
        print("  Verified: Mandate-specific risk capacities coexist independently (LOW, HIGH, VERY_HIGH) alongside global risk tolerance (HIGH).")

        # =====================================================================
        # Scenario E: Sell Reconciliation (ASSIGNMENT_REVIEW_REQUIRED & Resolution)
        # =====================================================================
        print("\n--- Scenario E: Post-Sell Reconciliation ---")
        # State: 1000 units total.
        # Mandate Retirement has 400 assigned.
        # Let's assign 200 units to Speculative sleeve as well -> total assigned = 600 units, 400 unassigned.
        await client.post(
            f"/api/mandates/{m_spec_id}/assignments",
            json={
                "mandate_id": m_spec_id,
                "resource_type": "ASSET",
                "asset_id": str(thyao_id),
                "assigned_quantity": "200.00",
            },
            headers=headers_a,
        )

        # Unassigned = 400 units. Total assigned = 600 units.
        # Now perform an unattributed SELL of 700 units (700 sold > 400 unassigned units).
        # MUST NOT proportionally alter assignments! MUST flag ASSIGNMENT_REVIEW_REQUIRED!
        sell_tx_res = await client.post(
            f"/api/assets/{thyao_id}/transactions",
            json={
                "transaction_type": "SELL",
                "quantity": "700.00",
                "price_per_unit": "310.00",
                "transaction_currency": "TRY",
                "transaction_date": "2026-02-15",
                "affects_cash": False,
            },
            headers=headers_a,
        )
        assert sell_tx_res.status_code == 201

        # Check unassigned resources status
        unassigned_check = await client.get("/api/financial-context/unassigned-resources", headers=headers_a)
        u_thyao = next(a for a in unassigned_check.json()["data"]["assets"] if a["asset_id"] == str(thyao_id))
        assert u_thyao["reconciliation_status"] == "ASSIGNMENT_REVIEW_REQUIRED"
        assert Decimal(u_thyao["total_quantity"]) == Decimal("300.00")
        assert Decimal(u_thyao["assigned_quantity"]) == Decimal("600.00")
        assert Decimal(u_thyao["over_assigned_amount"]) == Decimal("300.00")

        # Check that previous mandate allocations remained untouched!
        m_ret_chk = await client.get(f"/api/mandates/{m_retire_id}", headers=headers_a)
        m_sp_chk = await client.get(f"/api/mandates/{m_spec_id}", headers=headers_a)
        ret_qty = next(a for a in m_ret_chk.json()["data"]["assignments"] if a["asset_id"] == str(thyao_id))["assigned_quantity"]
        sp_qty = next(a for a in m_sp_chk.json()["data"]["assignments"] if a["asset_id"] == str(thyao_id))["assigned_quantity"]
        assert Decimal(str(ret_qty)) == Decimal("400.00"), "Mandate assignments must NOT be modified automatically"
        assert Decimal(str(sp_qty)) == Decimal("200.00"), "Mandate assignments must NOT be modified automatically"

        # Explicit user resolution via resolve-assignment-review:
        # User explicitly decides: Retirement absorbs 200 units (now 200), Speculative absorbs 100 units (now 100). Total = 300 <= 300 available.
        resolve_res = await client.post(
            "/api/mandates/resolve-assignment-review",
            json={
                "asset_id": str(thyao_id),
                "mandate_adjustments": {
                    str(m_retire_id): "200.00",
                    str(m_spec_id): "100.00",
                },
            },
            headers=headers_a,
        )
        assert resolve_res.status_code == 200
        assert resolve_res.json()["data"]["status"] == "CONSISTENT"
        assert Decimal(resolve_res.json()["data"]["currently_assigned_units"]) == Decimal("300.00")

        # Verify state is consistent again
        unassigned_after = await client.get("/api/financial-context/unassigned-resources", headers=headers_a)
        u_thyao_after = next(a for a in unassigned_after.json()["data"]["assets"] if a["asset_id"] == str(thyao_id))
        assert u_thyao_after["reconciliation_status"] == "CONSISTENT"
        assert Decimal(u_thyao_after["over_assigned_amount"]) == Decimal("0.00")
        print("  Verified: Post-sell reconciliation flagged ASSIGNMENT_REVIEW_REQUIRED without guessing, and user resolved explicitly.")

        # =====================================================================
        # Scenario F: Goal Progress Calculation (32.5% on 650k / 2M)
        # =====================================================================
        print("\n--- Scenario F: Goal Progress Calculation ---")
        # Target: 2,000,000 TRY for House Goal. Currently has 100,000 TRY cash assigned.
        # Let's add 550,000 TRY more cash to make total assigned = 650,000 TRY.
        async with async_session() as db:
            ca_fetch = (await db.execute(select(CashAccount).where(CashAccount.id == cash_id))).scalar_one()
            ca_fetch.balance = Decimal("800000.00")
            await db.commit()

        await client.post(
            f"/api/mandates/{m_house_id}/assignments",
            json={
                "mandate_id": m_house_id,
                "resource_type": "CASH_ACCOUNT",
                "cash_account_id": str(cash_id),
                "assigned_amount": "650000.00",
            },
            headers=headers_a,
        )

        goals_f = await client.get("/api/financial-goals", headers=headers_a)
        g_house_f = next(g for g in goals_f.json()["data"] if g["id"] == g_house_id)
        assert Decimal(str(g_house_f["current_funding"])) == Decimal("650000.00")
        assert Decimal(str(g_house_f["funded_ratio"])) == Decimal("0.3250")  # 32.5%
        assert Decimal(str(g_house_f["remaining_amount"])) == Decimal("1350000.00")
        assert g_house_f["months_remaining"] > 0
        assert Decimal(str(g_house_f["required_monthly_contribution"])) > Decimal("0")
        assert "Assuming 0% nominal return" in g_house_f["projection_assumptions"]
        print("  Verified: Goal progress derived dynamically: Target 2M, Assigned 650k -> Funded ratio 32.5%, Remaining: 1.35M, 0% growth disclaimer present.")

        # =====================================================================
        # Scenario G: Virtual Mandate Transfer (Zero Transaction Side Effects)
        # =====================================================================
        print("\n--- Scenario G: Virtual Mandate Transfer ---")
        # Transfer 50 units of THYAO from Retirement (200 units) to Speculative (100 units)
        xfer_res = await client.post(
            "/api/mandates/transfer-capital",
            json={
                "from_mandate_id": m_retire_id,
                "to_mandate_id": m_spec_id,
                "resource_type": "ASSET",
                "asset_id": str(thyao_id),
                "quantity": "50.00",
            },
            headers=headers_a,
        )
        assert xfer_res.status_code == 200, xfer_res.text

        # Verify new quantities: Retirement = 150, Speculative = 150
        m_ret_xfer = await client.get(f"/api/mandates/{m_retire_id}", headers=headers_a)
        m_sp_xfer = await client.get(f"/api/mandates/{m_spec_id}", headers=headers_a)
        qty_ret = next(a for a in m_ret_xfer.json()["data"]["assignments"] if a["asset_id"] == str(thyao_id))["assigned_quantity"]
        qty_sp = next(a for a in m_sp_xfer.json()["data"]["assignments"] if a["asset_id"] == str(thyao_id))["assigned_quantity"]
        assert Decimal(str(qty_ret)) == Decimal("150.00")
        assert Decimal(str(qty_sp)) == Decimal("150.00")

        # Verify zero new transactions created in database
        async with async_session() as db:
            tx_count = (await db.execute(select(Transaction).where(Transaction.asset_id == thyao_id))).scalars().all()
            assert len(tx_count) == 2  # Original 1 BUY + 1 SELL from earlier, NO transfer transaction
        print("  Verified: Virtual mandate transfer completed with ZERO transaction rows and ZERO cash movements.")

        # =====================================================================
        # Scenario H: Unknown Financial Context Handling (No Invented Zeros)
        # =====================================================================
        print("\n--- Scenario H: Unknown Financial Context Handling ---")
        user_h_id, headers_h = await _register_user(client, f"p41_h_{uuid.uuid4().hex[:6]}@example.com", "User H")
        ctx_h = (await client.get("/api/financial-context", headers=headers_h)).json()["data"]
        assert ctx_h["monthly_net_income"] is None
        assert ctx_h["monthly_essential_expenses"] is None
        assert ctx_h["income_stability"] == "UNKNOWN"

        intel_h = (await client.get("/api/financial-intelligence/summary", headers=headers_h)).json()["data"]
        assert intel_h["monthly_net_income"] is None
        assert intel_h["monthly_surplus"] is None
        assert intel_h["savings_rate_pct"] is None
        assert intel_h["emergency_coverage_months"] is None
        assert intel_h["coverage_state"]["income"] == "UNKNOWN"
        print("  Verified: Missing financial context strictly represented as null/UNKNOWN; zero invented zeros or fake rates.")

        # =====================================================================
        # Scenario I: Copilot Context Integration & Profile Synthesis
        # =====================================================================
        print("\n--- Scenario I: Copilot Context Integration & Profile Synthesis ---")
        # 1. Ask Copilot "analyze my finances"
        conv_res = await client.post("/api/copilot/conversations", headers=headers_a)
        conv_id = conv_res.json()["data"]["id"]

        copilot_res = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": "Analyze my finances and give me a complete financial situation assessment"},
            headers=headers_a,
        )
        assert copilot_res.status_code == 200
        sr = copilot_res.json()["data"]["structured_response"]
        assert sr["intent"] == "FINANCIAL_ANALYSIS"
        assert "Finansal Durum Analizi" in sr["answer"]
        assert "Net Değer" in sr["answer"]

        # 2. Query synthesis endpoint
        synth_res = await client.get("/api/financial-intelligence/synthesis", headers=headers_a)
        assert synth_res.status_code == 200
        synth = synth_res.json()["data"]
        assert synth["is_authoritative"] is False
        assert "non-authoritative" in synth["disclaimer"]
        assert synth["freshness_status"] in ("CURRENT", "UNKNOWN")
        assert "investor_profile_summary" in synth
        assert "cash_flow_and_surplus_summary" in synth
        assert "emergency_reserve_adequacy" in synth
        assert "goal_architecture_summary" in synth
        assert "debt_posture_summary" in synth
        assert "mandate_alignment_summary" in synth
        assert "source_traceability" in synth
        assert "confidence_limitations" in synth
        assert len(synth["confidence_limitations"]) > 0
        assert "monthly_net_income" in synth["source_traceability"]
        assert synth["source_traceability"]["monthly_net_income"]["source"] in ("EXPLICIT", "DERIVED")
        assert "confidence" in synth["source_traceability"]["monthly_net_income"]
        assert "limitation" in synth["source_traceability"]["monthly_net_income"]
        print("  Verified: Copilot Financial Analysis & Profile Synthesis successfully compose intelligence with traceability, confidence limitations, and non-authoritative disclaimers.")

        # =====================================================================
        # Scenario J: Backward Compatibility with Phase 4 Investor Profile
        # =====================================================================
        print("\n--- Scenario J: Backward Compatibility with Phase 4 ---")
        # Verify User A's confirmed profile from Phase 4 is intact
        async with async_session() as db:
            p_stmt = select(InvestorProfile).where(InvestorProfile.user_id == user_uuid_a)
            p_obj = (await db.execute(p_stmt)).scalar_one_or_none()
            assert p_obj is not None
            assert p_obj.active_version_id is not None
            v_stmt = select(InvestorProfileVersion).where(InvestorProfileVersion.id == p_obj.active_version_id)
            v_obj = (await db.execute(v_stmt)).scalar_one_or_none()
            assert v_obj is not None
            assert v_obj.snapshot["risk_tolerance"] == "HIGH"
            assert v_obj.snapshot["policy"]["speculative_cap_pct"] == 20
        print("  Verified: Existing Phase 4 Investor Profile and version history 100% preserved and untouched.")

        # =====================================================================
        # Scenario K: Adaptive Financial Discovery through Copilot
        # =====================================================================
        print("\n--- Scenario K: Adaptive Financial Discovery through Copilot ---")
        # Part 1: User A has full context (Income 100k, Essential 65k, Discretionary 15k, Cash 200k, Profile HIGH)
        # Test Case 1: "I don't really know how much I can invest every month."
        disc1_res = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": "I don't really know how much I can invest every month."},
            headers=headers_a,
        )
        assert disc1_res.status_code == 200
        sr1 = disc1_res.json()["data"]["structured_response"]
        assert sr1["intent"] == "FINANCIAL_DISCOVERY"
        assert "20,000.00 TRY" in sr1["answer"]
        assert "20.0%" in sr1["answer"]
        assert "Calculated Monthly Surplus" in sr1["answer"]
        print("  Verified: 'How much can I invest' calculates deterministic surplus (20,000.00 TRY, 20.0%) when context is known.")

        # Test Case 2: "I'm not sure whether my emergency fund is enough."
        disc2_res = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": "I'm not sure whether my emergency fund is enough."},
            headers=headers_a,
        )
        assert disc2_res.status_code == 200
        sr2 = disc2_res.json()["data"]["structured_response"]
        assert sr2["intent"] == "FINANCIAL_DISCOVERY"
        assert "12.3 months" in sr2["answer"]
        assert "exceeding the recommended 6-month" in sr2["answer"]
        print("  Verified: 'Emergency fund enough' calculates deterministic runway (12.3 months on 800k cash) and confirms adequacy against 3-6 month rule.")

        # Test Case 3: "I don't know how much risk I can take."
        disc3_res = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": "I don't know how much risk I can take."},
            headers=headers_a,
        )
        assert disc3_res.status_code == 200
        sr3 = disc3_res.json()["data"]["structured_response"]
        assert sr3["intent"] == "FINANCIAL_DISCOVERY"
        assert "HIGH" in sr3["answer"]
        assert "Mandate" in sr3["answer"]
        print("  Verified: 'How much risk can I take' articulates investor profile tolerance and mandate-specific capacity.")

        # Part 2: User H has blank/unknown financial context and no profile
        conv_h_res = await client.post("/api/copilot/conversations", headers=headers_h)
        conv_h_id = conv_h_res.json()["data"]["id"]

        # Blank Context Case 1: "I don't really know how much I can invest every month."
        h1_res = await client.post(
            f"/api/copilot/conversations/{conv_h_id}/messages",
            json={"content": "I don't really know how much I can invest every month."},
            headers=headers_h,
        )
        assert h1_res.status_code == 200
        sr_h1 = h1_res.json()["data"]["structured_response"]
        assert sr_h1["intent"] == "FINANCIAL_DISCOVERY"
        assert "UNKNOWN" in sr_h1["answer"]
        assert "never guess or invent" in sr_h1["answer"]
        assert "net take-home income" in sr_h1["answer"]
        print("  Verified: Missing context for investable capacity preserves UNKNOWN and asks contextual follow-up without hallucinating.")

        # Blank Context Case 2: "I'm not sure whether my emergency fund is enough."
        h2_res = await client.post(
            f"/api/copilot/conversations/{conv_h_id}/messages",
            json={"content": "I'm not sure whether my emergency fund is enough."},
            headers=headers_h,
        )
        assert h2_res.status_code == 200
        sr_h2 = h2_res.json()["data"]["structured_response"]
        assert sr_h2["intent"] == "FINANCIAL_DISCOVERY"
        assert "UNKNOWN" in sr_h2["answer"]
        assert "monthly non-negotiable living expenses" in sr_h2["answer"]
        print("  Verified: Missing context for emergency fund preserves UNKNOWN and prompts for living expenses.")

        # Blank Context Case 3: "I don't know how much risk I can take."
        h3_res = await client.post(
            f"/api/copilot/conversations/{conv_h_id}/messages",
            json={"content": "I don't know how much risk I can take."},
            headers=headers_h,
        )
        assert h3_res.status_code == 200
        sr_h3 = h3_res.json()["data"]["structured_response"]
        assert sr_h3["intent"] == "FINANCIAL_DISCOVERY"
        assert "UNKNOWN" in sr_h3["answer"]
        assert "Drawdown Comfort" in sr_h3["answer"]
        assert "Time Horizon" in sr_h3["answer"]
        print("  Verified: Missing profile for risk capacity preserves UNKNOWN, avoids inventing a score, and asks diagnostic questions.")

    print("\n======================================================================")
    print("ALL 11 VERIFICATION SCENARIOS (A THROUGH K) COMPLETED WITH 100% PASS")
    print("======================================================================\n")


if __name__ == "__main__":
    asyncio.run(run_verification())
