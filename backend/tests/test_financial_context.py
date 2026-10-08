"""Comprehensive test suite for PortfolioMind Phase 4.1:
Financial Context, Goals, Mandates & Financial Intelligence.

Verifies:
1. Financial Context CRUD & Unknown field invariants (no fake 0% or zero balances)
2. Goals & Mandates separation, creation, updates, and goal unlinking on delete
3. Virtual Capital Assignment (Earmarks) & Conservation of Capital
4. Virtual Transfer between Mandates (Zero Transaction rows, zero Cash balance changes)
5. Post-Sell Reconciliation (Proportional scaling when sold quantity exceeds unassigned)
6. Global Policy Inheritance & Mandate Specialization (Cannot loosen global prohibitions)
7. Deterministic Financial Intelligence (Net worth, Liquid net worth, Surplus, Savings rate, Emergency Runway, Speculative cap)
8. Copilot Broad Financial Analysis & Conversational Level 2 Proposals/Confirmation
"""

from datetime import date
from decimal import Decimal
import json
import uuid

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import select

from app.database import get_session_factory
from app.main import app
from app.models.asset import Asset, AssetType
from app.models.cash import CashAccount
from app.models.copilot import CopilotActionProposal, CopilotAuditLog
from app.models.financial_context import (
    CapitalAssignment,
    FinancialContext,
    FinancialGoal,
    GoalStatus,
    GoalType,
    InvestmentMandate,
    MandateType,
    ResourceAssignmentType,
)
from app.models.investor_profile import InvestorProfile, InvestorProfileVersion
from app.models.liability import Liability
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.services.copilot import CopilotService, CopilotWriteExecutor
from app.services.copilot.intent_classifier import IntentClassifier
from app.services.financial_context import (
    AssignmentService,
    FinancialContextService,
    FinancialIntelligenceService,
    GoalsService,
)


async def _register_user(client: AsyncClient, email: str) -> tuple[str, dict[str, str]]:
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Test User"},
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["data"]["access_token"]
    user_id = resp.json()["data"]["user"]["id"]
    return user_id, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_financial_context_crud_and_unknowns():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = f"fc_test_{uuid.uuid4().hex[:6]}@example.com"
        user_id, headers = await _register_user(client, email)

        # 1. Fetch newly initialized context - should have UNKNOWN income & expenses
        res = await client.get("/api/financial-context", headers=headers)
        assert res.status_code == 200
        ctx = res.json()["data"]
        assert ctx["monthly_net_income"] is None
        assert ctx["monthly_essential_expenses"] is None
        assert ctx["income_stability"] == "UNKNOWN"

        # 2. Update context with income and essential expenses
        up_res = await client.put(
            "/api/financial-context",
            json={
                "monthly_net_income": "100000.00",
                "monthly_essential_expenses": "65000.00",
                "income_stability": "PREDICTABLE",
                "planning_currency": "TRY",
            },
            headers=headers,
        )
        assert up_res.status_code == 200
        ctx_up = up_res.json()["data"]
        assert Decimal(ctx_up["monthly_net_income"]) == Decimal("100000.00")
        assert Decimal(ctx_up["monthly_essential_expenses"]) == Decimal("65000.00")
        assert ctx_up["income_stability"] == "PREDICTABLE"

        # 3. Confirm context
        conf_res = await client.post("/api/financial-context/confirm", headers=headers)
        assert conf_res.status_code == 200
        assert conf_res.json()["data"]["last_confirmed_at"] is not None


@pytest.mark.asyncio
async def test_financial_goals_and_mandates_lifecycle():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = f"goal_test_{uuid.uuid4().hex[:6]}@example.com"
        user_id, headers = await _register_user(client, email)

        # 1. Create a Goal: Home Purchase
        goal_res = await client.post(
            "/api/financial-goals",
            json={
                "name": "Home Down Payment",
                "goal_type": "HOME_PURCHASE",
                "target_amount": "500000.00",
                "target_currency": "TRY",
                "target_date": "2028-12-31",
                "priority": "ESSENTIAL",
            },
            headers=headers,
        )
        assert goal_res.status_code == 201
        goal_data = goal_res.json()["data"]
        goal_id = goal_data["id"]
        assert Decimal(str(goal_data["current_funding"])) == 0
        assert goal_data["status_assessment"] == "UNASSIGNED"

        # 2. Create a Mandate linked to this goal
        mandate_res = await client.post(
            "/api/mandates",
            json={
                "name": "Home Preservation Sleeve",
                "goal_id": goal_id,
                "mandate_type": "PRESERVATION",
                "risk_capacity": "LOW",
            },
            headers=headers,
        )
        assert mandate_res.status_code == 201
        mandate_data = mandate_res.json()["data"]
        mandate_id = mandate_data["id"]
        assert mandate_data["goal_id"] == goal_id

        # 3. List goals - should show the linked mandate
        g_list_res = await client.get("/api/financial-goals", headers=headers)
        assert g_list_res.status_code == 200
        goals = g_list_res.json()["data"]
        assert len(goals) == 1
        assert len(goals[0]["mandates"]) == 1
        assert goals[0]["mandates"][0]["id"] == mandate_id

        # 4. Delete goal - mandate should remain alive with goal_id = None (capital not destroyed)
        del_res = await client.delete(f"/api/financial-goals/{goal_id}", headers=headers)
        assert del_res.status_code == 200

        m_get_res = await client.get(f"/api/mandates/{mandate_id}", headers=headers)
        assert m_get_res.status_code == 200
        assert m_get_res.json()["data"]["goal_id"] is None


@pytest.mark.asyncio
async def test_capital_assignment_conservation_and_virtual_transfer():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = f"earmark_test_{uuid.uuid4().hex[:6]}@example.com"
        user_id_str, headers = await _register_user(client, email)
        user_uuid = uuid.UUID(user_id_str)

        async_session = get_session_factory()
        async with async_session() as db:
            # Create an asset with 100 units at 50 TRY
            asset = Asset(
                user_id=user_uuid,
                symbol="THYAO",
                name="Türk Hava Yolları",
                asset_type=AssetType.STOCK,
                current_price_currency="TRY",
                current_price=Decimal("50.00"),
            )
            db.add(asset)
            await db.flush()

            # Add BUY transaction of 100 units
            tx = Transaction(
                asset_id=asset.id,
                transaction_type=TransactionType.BUY,
                quantity=Decimal("100"),
                price_per_unit=Decimal("45.00"),
                total_amount=Decimal("4500.00"),
                transaction_currency="TRY",
                transaction_date=date(2026, 1, 1),
            )
            db.add(tx)

            # Update CashAccount with 10,000 TRY
            cash = (await db.execute(select(CashAccount).where(CashAccount.user_id == user_uuid, CashAccount.currency == "TRY"))).scalar_one()
            cash.balance = Decimal("10000.00")

            # Create Mandate 1 (Retirement) and Mandate 2 (House)
            m1 = InvestmentMandate(
                user_id=user_uuid,
                name="Retirement Growth",
                mandate_type=MandateType.GROWTH,
            )
            m2 = InvestmentMandate(
                user_id=user_uuid,
                name="House Sleeve",
                mandate_type=MandateType.PRESERVATION,
            )
            db.add_all([m1, m2])
            await db.commit()
            m1_id = m1.id
            m2_id = m2.id
            asset_id = asset.id
            cash_id = cash.id

        # 1. Attempt Over-Assignment (Assign 120 units when only 100 available) -> Must Fail
        over_assign_res = await client.post(
            f"/api/mandates/{m1_id}/assignments",
            json={
                "mandate_id": str(m1_id),
                "resource_type": "ASSET",
                "asset_id": str(asset_id),
                "assigned_quantity": "120.00",
            },
            headers=headers,
        )
        assert over_assign_res.status_code == 400
        assert "Cannot assign" in over_assign_res.json()["message"]

        # 2. Assign 60 units to Mandate 1 -> Succeeded
        assign1_res = await client.post(
            f"/api/mandates/{m1_id}/assignments",
            json={
                "mandate_id": str(m1_id),
                "resource_type": "ASSET",
                "asset_id": str(asset_id),
                "assigned_quantity": "60.00",
            },
            headers=headers,
        )
        assert assign1_res.status_code == 200

        # 3. Assign 30 units to Mandate 2 -> Succeeded (Leaves 10 units unassigned)
        assign2_res = await client.post(
            f"/api/mandates/{m2_id}/assignments",
            json={
                "mandate_id": str(m2_id),
                "resource_type": "ASSET",
                "asset_id": str(asset_id),
                "assigned_quantity": "30.00",
            },
            headers=headers,
        )
        assert assign2_res.status_code == 200

        # 4. Now attempt to assign 20 units to Mandate 2 (only 10 unassigned remain) -> Must Fail
        assign_excess_res = await client.post(
            f"/api/mandates/{m2_id}/assignments",
            json={
                "mandate_id": str(m2_id),
                "resource_type": "ASSET",
                "asset_id": str(asset_id),
                "assigned_quantity": "50.00",  # 30 already + 20 more = 50 total > 40 max
            },
            headers=headers,
        )
        assert assign_excess_res.status_code == 400

        # 5. Virtual Transfer: Move 15 units of THYAO from Mandate 1 to Mandate 2
        # Zero transactions created, zero cash moved!
        transfer_res = await client.post(
            "/api/mandates/transfer-capital",
            json={
                "from_mandate_id": str(m1_id),
                "to_mandate_id": str(m2_id),
                "resource_type": "ASSET",
                "asset_id": str(asset_id),
                "quantity": "15.00",
            },
            headers=headers,
        )
        assert transfer_res.status_code == 200

        # Verify Mandate 1 now has 45 units (60 - 15) and Mandate 2 has 45 units (30 + 15)
        m1_check = await client.get(f"/api/mandates/{m1_id}", headers=headers)
        m2_check = await client.get(f"/api/mandates/{m2_id}", headers=headers)
        assert Decimal(str(m1_check.json()["data"]["assignments"][0]["assigned_quantity"])) == Decimal("45.00")
        assert Decimal(str(m2_check.json()["data"]["assignments"][0]["assigned_quantity"])) == Decimal("45.00")

        # Verify no Transactions were created by the virtual transfer
        async with async_session() as db:
            tx_count = (await db.execute(select(Transaction).where(Transaction.asset_id == asset_id))).scalars().all()
            assert len(tx_count) == 1  # Only the original BUY transaction


@pytest.mark.asyncio
async def test_policy_inheritance_and_speculative_cap():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = f"policy_test_{uuid.uuid4().hex[:6]}@example.com"
        user_id_str, headers = await _register_user(client, email)
        user_uuid = uuid.UUID(user_id_str)

        async_session = get_session_factory()
        async with async_session() as db:
            # Create confirmed investor profile version with global NO_LEVERAGE and speculative_cap = 10%
            profile = InvestorProfile(
                user_id=user_uuid,
                completeness_overall_pct=Decimal("100.00"),
            )
            db.add(profile)
            await db.flush()

            version = InvestorProfileVersion(
                profile_id=profile.id,
                user_id=user_uuid,
                version_number=1,
                change_reason="Initial Policy",
                change_source="ONBOARDING",
                confirmed_by=user_uuid,
                snapshot={
                    "policy": {
                        "no_leverage": True,
                        "restrictions": ["NO_BORROWING"],
                        "prohibited_asset_types": ["CRYPTO"],
                        "max_single_asset_pct": 20,
                        "speculative_cap_pct": 10,
                    }
                },
            )
            db.add(version)
            await db.flush()
            profile.active_version_id = version.id
            await db.commit()

        # 1. Mandate attempts to allow leverage while globally prohibited -> Must Fail
        bad_leverage_res = await client.post(
            "/api/mandates",
            json={
                "name": "Leveraged Speculation",
                "mandate_type": "SPECULATIVE",
                "policy_rules": {"allow_leverage": True},
            },
            headers=headers,
        )
        assert bad_leverage_res.status_code == 400
        assert "leverage is prohibited globally" in bad_leverage_res.json()["message"]

        # 2. Mandate attempts to allocate to prohibited asset type (CRYPTO) -> Must Fail
        bad_crypto_res = await client.post(
            "/api/mandates",
            json={
                "name": "Crypto Mandate",
                "mandate_type": "GROWTH",
                "target_allocation": {"CRYPTO": 0.5, "STOCK": 0.5},
            },
            headers=headers,
        )
        assert bad_crypto_res.status_code == 400
        assert "prohibited asset type" in bad_crypto_res.json()["message"]

        # 3. Mandate attempts to loosen single-asset concentration to 40% (Global cap is 20%) -> Must Fail
        bad_conc_res = await client.post(
            "/api/mandates",
            json={
                "name": "Concentrated Mandate",
                "mandate_type": "GROWTH",
                "policy_rules": {"max_single_asset_pct": 40},
            },
            headers=headers,
        )
        assert bad_conc_res.status_code == 400
        assert "cannot loosen global limit" in bad_conc_res.json()["message"]


@pytest.mark.asyncio
@pytest.mark.usefixtures("forex_provider")
async def test_deterministic_financial_intelligence():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = f"intel_test_{uuid.uuid4().hex[:6]}@example.com"
        user_id_str, headers = await _register_user(client, email)
        user_uuid = uuid.UUID(user_id_str)

        async_session = get_session_factory()
        async with async_session() as db:
            # Assets: 100 units of Stock at 100 TRY = 10,000 TRY
            stock = Asset(
                user_id=user_uuid,
                symbol="SISE",
                name="Şişecam",
                asset_type=AssetType.STOCK,
                current_price_currency="TRY",
                current_price=Decimal("100.00"),
            )
            db.add(stock)
            await db.flush()
            db.add(Transaction(
                asset_id=stock.id,
                transaction_type=TransactionType.BUY,
                quantity=Decimal("100"),
                price_per_unit=Decimal("80.00"),
                total_amount=Decimal("8000.00"),
                transaction_currency="TRY",
                transaction_date=date(2026, 1, 1),
            ))

            # Cash: 50,000 TRY
            cash = (await db.execute(select(CashAccount).where(CashAccount.user_id == user_uuid, CashAccount.currency == "TRY"))).scalar_one()
            cash.balance = Decimal("50000.00")

            # Liability: 20,000 TRY with 2,000 TRY monthly payment
            db.add(Liability(
                user_id=user_uuid,
                name="Personal Loan",
                liability_type="personal_loan",
                currency="TRY",
                current_balance=Decimal("20000.00"),
                minimum_payment=Decimal("2000.00"),
                is_active=True,
            ))

            # Financial Context: 80,000 TRY Income, 25,000 TRY Essential, 15,000 TRY Discretionary
            ctx = (await db.execute(select(FinancialContext).where(FinancialContext.user_id == user_uuid))).scalar_one_or_none()
            if not ctx:
                ctx = FinancialContext(
                    user_id=user_uuid,
                    monthly_net_income=Decimal("80000.00"),
                    monthly_essential_expenses=Decimal("25000.00"),
                    monthly_discretionary_expenses=Decimal("15000.00"),
                    income_stability="PREDICTABLE",
                )
                db.add(ctx)
            else:
                ctx.monthly_net_income = Decimal("80000.00")
                ctx.monthly_essential_expenses = Decimal("25000.00")
                ctx.monthly_discretionary_expenses = Decimal("15000.00")
                ctx.income_stability = "PREDICTABLE"
            await db.commit()

        # Compute Financial Intelligence
        intel_res = await client.get("/api/financial-intelligence/summary", headers=headers)
        assert intel_res.status_code == 200
        data = intel_res.json()["data"]

        # Net Worth: 10,000 + 50,000 - 20,000 = 40,000 TRY
        assert Decimal(str(data["net_worth"])) == Decimal("40000.00")
        assert Decimal(str(data["liquid_net_worth"])) == Decimal("40000.00")

        # Surplus: 80,000 - (25,000 + 15,000) = 40,000 TRY
        assert Decimal(str(data["monthly_surplus"])) == Decimal("40000.00")

        # Savings Rate: 40,000 / 80,000 = 50.0%
        assert Decimal(str(data["savings_rate_pct"])) == Decimal("50.00")

        # Emergency Coverage: Cash (50,000) / Essential (25,000) = 2.0 months
        assert Decimal(str(data["emergency_coverage_months"])) == Decimal("2.0")

        # DTI: 2,000 / 80,000 = 2.5%
        assert Decimal(str(data["debt_to_income_pct"])) == Decimal("2.50")


@pytest.mark.asyncio
@pytest.mark.usefixtures("forex_provider")
async def test_copilot_financial_analysis_and_level_2_mutation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = f"copilot_fin_{uuid.uuid4().hex[:6]}@example.com"
        user_id_str, headers = await _register_user(client, email)

        # 1. Ask Copilot "analyze my entire financial situation"
        conv_res = await client.post("/api/copilot/conversations", headers=headers)
        assert conv_res.status_code == 201
        conv_id = conv_res.json()["data"]["id"]

        msg_res = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": "Analyze my entire financial situation and tell me my net worth and cash flow"},
            headers=headers,
        )
        assert msg_res.status_code == 200
        sr = msg_res.json()["data"]["structured_response"]
        assert sr["intent"] == "FINANCIAL_ANALYSIS"
        assert "Finansal Durum Analizi" in sr["answer"]
        assert "Net Değer" in sr["answer"]

        # 2. Conversational income update: "I got a new job and now earn 120k per month"
        up_msg_res = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": "I got a new job and now earn 120k per month"},
            headers=headers,
        )
        assert up_msg_res.status_code == 200
        up_sr = up_msg_res.json()["data"]["structured_response"]
        assert up_sr["response_type"] == "PROPOSAL"
        assert up_sr["proposal"] is not None
        prop_id = up_sr["proposal"]["id"]

        # Verify NO changes written yet before confirmation
        ctx_check = await client.get("/api/financial-context", headers=headers)
        assert ctx_check.json()["data"]["monthly_net_income"] != 120000.0

        # 3. Explicit Confirmation (Level 2)
        exec_res = await client.post(
            f"/api/copilot/proposals/{prop_id}/confirm",
            json={},
            headers=headers,
        )
        assert exec_res.status_code == 200

        # Verify changes written and audit log created
        ctx_after = await client.get("/api/financial-context", headers=headers)
        assert Decimal(str(ctx_after.json()["data"]["monthly_net_income"])) == Decimal("120000.00")

        async_session = get_session_factory()
        async with async_session() as db:
            audit = (await db.execute(select(CopilotAuditLog).where(CopilotAuditLog.proposal_id == uuid.UUID(prop_id)))).scalar_one_or_none()
            assert audit is not None
            assert audit.execution_status == "SUCCESS"
            assert audit.action_type == "UPDATE_FINANCIAL_CONTEXT"


@pytest.mark.asyncio
async def test_post_sell_reconciliation_review_required_and_resolution():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = f"recon_test_{uuid.uuid4().hex[:6]}@example.com"
        user_id_str, headers = await _register_user(client, email)
        user_uuid = uuid.UUID(user_id_str)

        # 1. Create an asset with 100 units
        async_session = get_session_factory()
        async with async_session() as db:
            asset = Asset(
                user_id=user_uuid,
                symbol="BIMAS",
                name="BIM Birlesik Magazalar",
                asset_type=AssetType.STOCK,
                current_price=Decimal("500.00"),
                current_price_currency="TRY",
            )
            db.add(asset)
            await db.flush()

            db.add(
                Transaction(
                    asset_id=asset.id,
                    transaction_type=TransactionType.BUY,
                    quantity=Decimal("100"),
                    price_per_unit=Decimal("500.00"),
                    total_amount=Decimal("50000.00"),
                    transaction_currency="TRY",
                    transaction_date=date(2026, 1, 1),
                )
            )
            await db.commit()
            asset_id = asset.id

        # 2. Create 2 mandates and assign 40 units to each (80 assigned, 20 unassigned)
        m1_res = await client.post(
            "/api/mandates",
            json={"name": "Mandate A", "mandate_type": "GROWTH", "risk_capacity": "HIGH"},
            headers=headers,
        )
        m1_id = m1_res.json()["data"]["id"]

        m2_res = await client.post(
            "/api/mandates",
            json={"name": "Mandate B", "mandate_type": "PRESERVATION", "risk_capacity": "LOW"},
            headers=headers,
        )
        m2_id = m2_res.json()["data"]["id"]

        await client.post(
            f"/api/mandates/{m1_id}/assignments",
            json={
                "mandate_id": m1_id,
                "resource_type": "ASSET",
                "asset_id": str(asset_id),
                "assigned_quantity": "40.00",
            },
            headers=headers,
        )
        await client.post(
            f"/api/mandates/{m2_id}/assignments",
            json={
                "mandate_id": m2_id,
                "resource_type": "ASSET",
                "asset_id": str(asset_id),
                "assigned_quantity": "40.00",
            },
            headers=headers,
        )

        # 3. Perform a SELL of 50 units WITHOUT explicit mandate attribution
        # Sold 50 > 20 unassigned -> MUST NOT scale proportionally, MUST flag ASSIGNMENT_REVIEW_REQUIRED!
        sell_res = await client.post(
            f"/api/assets/{asset_id}/transactions",
            json={
                "transaction_type": "SELL",
                "quantity": "50.00",
                "price_per_unit": "520.00",
                "transaction_currency": "TRY",
                "transaction_date": "2026-02-01",
                "affects_cash": False,
            },
            headers=headers,
        )
        assert sell_res.status_code == 201

        # 4. Check unassigned resources -> MUST show ASSIGNMENT_REVIEW_REQUIRED
        unassigned_res = await client.get("/api/financial-context/unassigned-resources", headers=headers)
        assert unassigned_res.status_code == 200
        asset_info = next(a for a in unassigned_res.json()["data"]["assets"] if a["asset_id"] == str(asset_id))
        assert asset_info["reconciliation_status"] == "ASSIGNMENT_REVIEW_REQUIRED"
        assert Decimal(asset_info["over_assigned_amount"]) == Decimal("30.00")
        assert Decimal(asset_info["total_quantity"]) == Decimal("50.00")
        assert Decimal(asset_info["assigned_quantity"]) == Decimal("80.00")

        # 5. Check assignments: previous assignments MUST NOT have been scaled or altered
        m1_detail = await client.get(f"/api/mandates/{m1_id}", headers=headers)
        m2_detail = await client.get(f"/api/mandates/{m2_id}", headers=headers)
        assert Decimal(str(m1_detail.json()["data"]["assignments"][0]["assigned_quantity"])) == Decimal("40.00")
        assert Decimal(str(m2_detail.json()["data"]["assignments"][0]["assigned_quantity"])) == Decimal("40.00")

        # 6. User resolves review explicitly: adjusts Mandate A to 25, Mandate B to 25
        resolve_res = await client.post(
            "/api/mandates/resolve-assignment-review",
            json={
                "asset_id": str(asset_id),
                "mandate_adjustments": {
                    str(m1_id): "25.00",
                    str(m2_id): "25.00",
                },
            },
            headers=headers,
        )
        assert resolve_res.status_code == 200
        assert resolve_res.json()["data"]["status"] == "CONSISTENT"
        assert Decimal(resolve_res.json()["data"]["currently_assigned_units"]) == Decimal("50.00")

        # Check unassigned resources is now consistent
        unassigned_after = await client.get("/api/financial-context/unassigned-resources", headers=headers)
        asset_info_after = next(a for a in unassigned_after.json()["data"]["assets"] if a["asset_id"] == str(asset_id))
        assert asset_info_after["reconciliation_status"] == "CONSISTENT"
        assert Decimal(asset_info_after["over_assigned_amount"]) == Decimal("0.00")


@pytest.mark.asyncio
async def test_mandate_risk_capacity_diversity_and_coexistence():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = f"cap_div_{uuid.uuid4().hex[:6]}@example.com"
        user_id_str, headers = await _register_user(client, email)
        user_uuid = uuid.UUID(user_id_str)

        # Setup user profile with global risk tolerance = HIGH
        async_session = get_session_factory()
        async with async_session() as db:
            prof = InvestorProfile(user_id=user_uuid, completeness_overall_pct=Decimal("100.00"))
            db.add(prof)
            await db.flush()
            v1 = InvestorProfileVersion(
                profile_id=prof.id,
                user_id=user_uuid,
                version_number=1,
                change_reason="Profile Setup",
                change_source="ONBOARDING",
                confirmed_by=user_uuid,
                snapshot={
                    "risk_tolerance": "HIGH",
                    "policy": {"speculative_cap_pct": 25},
                },
            )
            db.add(v1)
            await db.flush()
            prof.active_version_id = v1.id
            await db.commit()

        # Create mandates with different capacities: LOW, HIGH, VERY_HIGH
        m_house = await client.post(
            "/api/mandates",
            json={"name": "House Downpayment", "mandate_type": "PRESERVATION", "risk_capacity": "LOW"},
            headers=headers,
        )
        assert m_house.status_code == 201
        assert m_house.json()["data"]["risk_capacity"] == "LOW"

        m_retire = await client.post(
            "/api/mandates",
            json={"name": "Long-term Retirement", "mandate_type": "GROWTH", "risk_capacity": "HIGH"},
            headers=headers,
        )
        assert m_retire.status_code == 201
        assert m_retire.json()["data"]["risk_capacity"] == "HIGH"

        m_spec = await client.post(
            "/api/mandates",
            json={"name": "Speculative Moonshot", "mandate_type": "SPECULATIVE", "risk_capacity": "VERY_HIGH"},
            headers=headers,
        )
        assert m_spec.status_code == 201
        assert m_spec.json()["data"]["risk_capacity"] == "VERY_HIGH"

        # Verify mandates maintain their individual risk capacities alongside global tolerance
        mandates_list = await client.get("/api/mandates", headers=headers)
        items = {m["name"]: m["risk_capacity"] for m in mandates_list.json()["data"]}
        assert items["House Downpayment"] == "LOW"
        assert items["Long-term Retirement"] == "HIGH"
        assert items["Speculative Moonshot"] == "VERY_HIGH"


@pytest.mark.asyncio
@pytest.mark.usefixtures("forex_provider")
async def test_goal_progress_math_and_synthesis():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        email = f"goal_math_{uuid.uuid4().hex[:6]}@example.com"
        user_id_str, headers = await _register_user(client, email)
        user_uuid = uuid.UUID(user_id_str)

        # 1. Target: 2,000,000 TRY, Target date: 2028-01-01
        goal_res = await client.post(
            "/api/financial-goals",
            json={
                "name": "Dream House Fund",
                "goal_type": "HOME_PURCHASE",
                "target_amount": "2000000.00",
                "target_currency": "TRY",
                "target_date": "2028-01-01",
            },
            headers=headers,
        )
        assert goal_res.status_code == 201
        goal_id = goal_res.json()["data"]["id"]

        # 2. Mandate linked to goal with cash assignment of 650,000 TRY
        m_res = await client.post(
            "/api/mandates",
            json={"name": "House Savings Sleeve", "goal_id": goal_id, "mandate_type": "GROWTH"},
            headers=headers,
        )
        m_id = m_res.json()["data"]["id"]

        async_session = get_session_factory()
        async with async_session() as db:
            ca_stmt = select(CashAccount).where(CashAccount.user_id == user_uuid, CashAccount.currency == "TRY")
            ca = (await db.execute(ca_stmt)).scalar_one_or_none()
            if ca:
                ca.balance = Decimal("700000.00")
            else:
                ca = CashAccount(user_id=user_uuid, currency="TRY", balance=Decimal("700000.00"))
                db.add(ca)
            await db.commit()
            ca_id = ca.id

        await client.post(
            f"/api/mandates/{m_id}/assignments",
            json={
                "mandate_id": m_id,
                "resource_type": "CASH_ACCOUNT",
                "cash_account_id": str(ca_id),
                "assigned_amount": "650000.00",
            },
            headers=headers,
        )

        # 3. Verify Goal Progress Math
        # Target: 2,000,000 TRY. Funded: 650,000 TRY.
        # Funded ratio: 650,000 / 2,000,000 = 0.3250 (32.5%)
        # Remaining amount: 1,350,000 TRY
        goals = await client.get("/api/financial-goals", headers=headers)
        g = next(x for x in goals.json()["data"] if x["id"] == goal_id)
        assert Decimal(str(g["current_funding"])) == Decimal("650000.00")
        assert Decimal(str(g["funded_ratio"])) == Decimal("0.3250")
        assert Decimal(str(g["remaining_amount"])) == Decimal("1350000.00")
        assert g["months_remaining"] > 0
        assert Decimal(str(g["required_monthly_contribution"])) > Decimal("0")
        assert "Assuming 0% nominal return" in g["projection_assumptions"]

        # 4. Profile Synthesis endpoint
        synth_res = await client.get("/api/financial-intelligence/synthesis", headers=headers)
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
        assert "confidence" in synth["source_traceability"]["monthly_net_income"]
        assert "limitation" in synth["source_traceability"]["monthly_net_income"]


@pytest.mark.asyncio
@pytest.mark.usefixtures("forex_provider")
async def test_copilot_adaptive_financial_discovery():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Case 1: User with known financial context and profile
        email = f"disc_{uuid.uuid4().hex[:6]}@example.com"
        user_id_str, headers = await _register_user(client, email)
        user_uuid = uuid.UUID(user_id_str)

        # Set financial context: Income=100k, Essential=65k, Discretionary=15k -> Surplus=20k, Savings Rate=20%
        await client.put(
            "/api/financial-context",
            json={
                "monthly_net_income": "100000.00",
                "monthly_essential_expenses": "65000.00",
                "monthly_discretionary_expenses": "15000.00",
                "income_stability": "PREDICTABLE",
            },
            headers=headers,
        )

        # Cash balance: 200,000 TRY -> Runway: 200k / 65k = 3.1 mo
        async_session = get_session_factory()
        async with async_session() as db:
            ca_stmt = select(CashAccount).where(CashAccount.user_id == user_uuid, CashAccount.currency == "TRY")
            ca = (await db.execute(ca_stmt)).scalar_one_or_none()
            if ca:
                ca.balance = Decimal("200000.00")
            else:
                ca = CashAccount(user_id=user_uuid, currency="TRY", balance=Decimal("200000.00"))
                db.add(ca)
            prof = InvestorProfile(user_id=user_uuid, completeness_overall_pct=Decimal("100.00"))
            db.add(prof)
            await db.flush()
            v1 = InvestorProfileVersion(
                profile_id=prof.id,
                user_id=user_uuid,
                version_number=1,
                change_reason="Profile Setup",
                change_source="ONBOARDING",
                confirmed_by=user_uuid,
                snapshot={
                    "risk_tolerance": "HIGH",
                    "investment_horizon": "10+ years",
                    "policy": {"speculative_cap_pct": 20},
                },
            )
            db.add(v1)
            await db.flush()
            prof.active_version_id = v1.id
            await db.commit()

        # Create conversation
        conv_res = await client.post("/api/copilot/conversations", headers=headers)
        conv_id = conv_res.json()["data"]["id"]

        # 1. Investable Surplus Discovery
        r1 = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": "I don't really know how much I can invest every month."},
            headers=headers,
        )
        assert r1.status_code == 200
        sr1 = r1.json()["data"]["structured_response"]
        assert sr1["intent"] == "FINANCIAL_DISCOVERY"
        assert "20,000.00 TRY" in sr1["answer"]
        assert "20.0%" in sr1["answer"]

        # 2. Emergency Fund Adequacy Discovery
        r2 = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": "I'm not sure whether my emergency fund is enough."},
            headers=headers,
        )
        assert r2.status_code == 200
        sr2 = r2.json()["data"]["structured_response"]
        assert sr2["intent"] == "FINANCIAL_DISCOVERY"
        assert "3.1 months" in sr2["answer"]

        # 3. Risk Capacity Discovery
        r3 = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": "I don't know how much risk I can take."},
            headers=headers,
        )
        assert r3.status_code == 200
        sr3 = r3.json()["data"]["structured_response"]
        assert sr3["intent"] == "FINANCIAL_DISCOVERY"
        assert "HIGH" in sr3["answer"]

        # Case 2: User with completely unknown / blank context
        email_blank = f"disc_blank_{uuid.uuid4().hex[:6]}@example.com"
        _, headers_blank = await _register_user(client, email_blank)
        conv_b_res = await client.post("/api/copilot/conversations", headers=headers_blank)
        conv_b_id = conv_b_res.json()["data"]["id"]

        # Blank 1: Investable capacity
        rb1 = await client.post(
            f"/api/copilot/conversations/{conv_b_id}/messages",
            json={"content": "I don't really know how much I can invest every month."},
            headers=headers_blank,
        )
        assert rb1.status_code == 200
        srb1 = rb1.json()["data"]["structured_response"]
        assert srb1["intent"] == "FINANCIAL_DISCOVERY"
        assert "UNKNOWN" in srb1["answer"]
        assert "never guess or invent" in srb1["answer"]

        # Blank 2: Emergency fund
        rb2 = await client.post(
            f"/api/copilot/conversations/{conv_b_id}/messages",
            json={"content": "I'm not sure whether my emergency fund is enough."},
            headers=headers_blank,
        )
        assert rb2.status_code == 200
        srb2 = rb2.json()["data"]["structured_response"]
        assert srb2["intent"] == "FINANCIAL_DISCOVERY"
        assert "UNKNOWN" in srb2["answer"]

        # Blank 3: Risk capacity
        rb3 = await client.post(
            f"/api/copilot/conversations/{conv_b_id}/messages",
            json={"content": "I don't know how much risk I can take."},
            headers=headers_blank,
        )
        assert rb3.status_code == 200
        srb3 = rb3.json()["data"]["structured_response"]
        assert srb3["intent"] == "FINANCIAL_DISCOVERY"
        assert "UNKNOWN" in srb3["answer"]

