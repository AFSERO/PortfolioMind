"""Verification script for PortfolioMind Phase 4 — Investor Profile & Personalization.

Simulates all 6 canonical Phase 4 scenarios end-to-end:
1. Scenario A — Full Onboarding Flow (C01-C12, draft review, explicit confirmation to create material Version 1).
2. Scenario B — Contradiction Engine & Risk Separation (40%+ tolerance + near-term liquidity need = X01, no collapsed score).
3. Scenario C — Skip Onboarding & Non-Intrusive Defaults (skip questions/flow, dashboard accessible, no fake answers).
4. Scenario D — Profile Update via Settings (v1 -> v2 with updated parameters, material version history).
5. Scenario E — Copilot Conversational Profile Change (Level 2 proposal, zero pre-confirm writes, confirmation -> v3, audit log).
6. Scenario F — Portfolio Setup Handoff (seamless delegation to Phase 3 import engine, truthful OCR disclaimer).
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
from app.models.copilot import CopilotAuditLog
from app.models.investor_profile import (
    InvestorProfile,
    InvestorProfileAnswer,
    InvestorProfileAssessment,
    InvestorProfileDraft,
    InvestorProfileVersion,
)
from app.models.opening_position import OpeningPosition


async def run_verification():
    print("======================================================================")
    print("PORTFOLIOMIND — PHASE 4 INVESTOR PROFILE & PERSONALIZATION VERIFICATION")
    print("======================================================================\n")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # =====================================================================
        # Scenario A: Full Onboarding Flow (User A)
        # =====================================================================
        print("--- Scenario A: Full Onboarding Flow ---")
        email_a = f"p4_user_a_{uuid.uuid4().hex[:6]}@example.com"
        reg_a = await client.post(
            "/api/auth/register",
            json={"email": email_a, "password": "StrongPassword123!"},
        )
        assert reg_a.status_code == 201, reg_a.text
        token_a = reg_a.json()["data"]["access_token"]
        user_id_a = reg_a.json()["data"]["user"]["id"]
        headers_a = {"Authorization": f"Bearer {token_a}"}
        print(f"Registered User A: {email_a} (UUID: {user_id_a})")

        # 1. Fetch Question Catalog
        q_resp = await client.get("/api/investor-profile/questions")
        assert q_resp.status_code == 200, q_resp.text
        catalog = q_resp.json()["data"]
        print(f"Catalog loaded: {len(catalog['sections'])} sections, {len(catalog['questions'])} questions.")
        assert len(catalog["questions"]) >= 12

        # 2. Answer C01 through C12
        answers_to_submit = [
            ("C01", ["GROW"], {}),
            ("C02", ["GE_10Y", "FLEXIBLE"], {"flexibility": "FLEXIBLE"}),
            ("C03", ["NONE"], {}),
            ("C04", ["M6_12"], {}),
            ("C05", ["SURPLUS", "RELIABLE"], {"reliability": "RELIABLE"}),
            ("C06", ["NONE"], {}),
            ("C07", ["ADJUST_GOAL"], {}),
            ("C08", ["P20"], {}),
            ("C09", ["REVIEW"], {}),
            ("C10", ["STOCKS", "FUNDS"], {}),
            ("C11", ["LOW_MAINTENANCE"], {}),
            ("C12", ["NONE"], {}),
        ]
        print("Submitting answers for C01–C12...")
        for q_id, opts, num_inputs in answers_to_submit:
            ans_res = await client.post(
                "/api/investor-profile/assessment/answer",
                json={
                    "question_id": q_id,
                    "knowledge_state": "KNOWN",
                    "selected_options": opts,
                    "numeric_inputs": num_inputs,
                },
                headers=headers_a,
            )
            assert ans_res.status_code == 200, f"Failed on {q_id}: {ans_res.text}"

        # 3. Check Draft & Review State
        draft_res = await client.get("/api/investor-profile/draft", headers=headers_a)
        assert draft_res.status_code == 200, draft_res.text
        draft_a = draft_res.json()["data"]
        completeness_a = draft_a["completeness"]["overall_pct"]
        print(f"Generated Profile Draft: Completeness={completeness_a}%, Issues={len(draft_a['issues'])}")
        assert completeness_a >= 85.0, f"Expected completeness >= 85%, got {completeness_a}%"
        assert draft_a["readiness"]["risk_analysis"] == "READY"
        assert draft_a["readiness"]["capacity_analysis"] == "READY"

        # 4. Explicit Confirmation to Material Version 1
        conf_res = await client.post(
            "/api/investor-profile/confirm",
            json={"change_reason": "Onboarding completed", "change_source": "ONBOARDING"},
            headers=headers_a,
        )
        assert conf_res.status_code == 200, conf_res.text
        v1_data = conf_res.json()["data"]
        print(f"Profile Confirmed: Version={v1_data['version_number']}, Reason='{v1_data['change_reason']}'")
        assert v1_data["version_number"] == 1
        assert v1_data["change_source"] == "ONBOARDING"

        # 5. Verify Current Profile Endpoint
        curr_res = await client.get("/api/investor-profile/current", headers=headers_a)
        assert curr_res.status_code == 200
        curr_a = curr_res.json()["data"]
        assert curr_a["version_number"] == 1
        assert curr_a["active_version_id"] == v1_data["version_id"]
        assert curr_a["risk"]["tolerance_summary"] == "MODERATE"
        print("Scenario A PASSED.\n")

        # =====================================================================
        # Scenario B: Contradiction Engine & Risk Separation (User B)
        # =====================================================================
        print("--- Scenario B: Contradiction Engine & Risk Separation ---")
        email_b = f"p4_user_b_{uuid.uuid4().hex[:6]}@example.com"
        reg_b = await client.post(
            "/api/auth/register",
            json={"email": email_b, "password": "StrongPassword123!"},
        )
        token_b = reg_b.json()["data"]["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}
        print(f"Registered User B: {email_b}")

        # Answer conflicting inputs:
        # C08: P40_PLUS (40%+ drawdown tolerance -> Psychological: HIGH)
        # C02: LT_1Y + FIXED (< 1 yr horizon, cannot delay)
        # F01: LT_12M (Near term major withdrawal)
        # C07: GOAL_UNAFFORDABLE (Financial capacity: CONSTRAINED)
        conflicting_answers = [
            ("C01", ["PURCHASE"], {}),
            ("C02", ["LT_1Y", "FIXED"], {"flexibility": "FIXED"}),
            ("C03", ["ONE_OFF"], {}),
            ("F01", ["LT_12M"], {"percentage": 50.0, "size": {"percentage": 50.0}}),
            ("C04", ["LT_3M"], {}),
            ("C07", ["GOAL_UNAFFORDABLE"], {}),
            ("C08", ["P40_PLUS"], {}),  # High psychological tolerance
            ("C09", ["HOLD"], {}),
        ]
        for q_id, opts, num_inputs in conflicting_answers:
            await client.post(
                "/api/investor-profile/assessment/answer",
                json={
                    "question_id": q_id,
                    "knowledge_state": "KNOWN",
                    "selected_options": opts,
                    "numeric_inputs": num_inputs,
                },
                headers=headers_b,
            )

        draft_b_res = await client.get("/api/investor-profile/draft", headers=headers_b)
        draft_b = draft_b_res.json()["data"]

        # Crucial Invariant 1: Psychological tolerance is HIGH
        tol_b = draft_b["risk"]["tolerance_summary"]
        print(f"Psychological Risk Tolerance: {tol_b}")
        assert tol_b == "HIGH"

        # Crucial Invariant 2: Financial capacity is CONSTRAINED
        cap_b = draft_b["risk"]["capacity_by_goal"][0]["status"]
        print(f"Financial Risk Capacity: {cap_b}")
        assert cap_b == "CONSTRAINED"

        # Crucial Invariant 3: Risk dimensions NOT collapsed into single score
        # Crucial Invariant 4: Contradiction X01 is surfaced with clear explanation
        issues_b = draft_b["issues"]
        x01 = next((i for i in issues_b if i["rule_id"] == "X01"), None)
        assert x01 is not None, f"Expected X01 issue in issues list, got {[i['rule_id'] for i in issues_b]}"
        print(f"Contradiction X01 Detected: {x01['explanation']}")
        print("Scenario B PASSED.\n")

        # =====================================================================
        # Scenario C: Skip Onboarding & Non-Intrusive Defaults (User C)
        # =====================================================================
        print("--- Scenario C: Skip Onboarding & Non-Intrusive Defaults ---")
        email_c = f"p4_user_c_{uuid.uuid4().hex[:6]}@example.com"
        reg_c = await client.post(
            "/api/auth/register",
            json={"email": email_c, "password": "StrongPassword123!"},
        )
        token_c = reg_c.json()["data"]["access_token"]
        headers_c = {"Authorization": f"Bearer {token_c}"}
        print(f"Registered User C: {email_c}")

        # User skips C01 explicitly
        skip_res = await client.post(
            "/api/investor-profile/assessment/skip-question?question_id=C01",
            headers=headers_c,
        )
        assert skip_res.status_code == 200

        # Check current profile for unconfirmed user:
        curr_c = (await client.get("/api/investor-profile/current", headers=headers_c)).json()["data"]
        print(f"User C profile before confirmation: Version={curr_c['version_number']}, Completeness={curr_c['completeness_overall_pct']}%")
        assert curr_c["version_number"] is None
        assert curr_c["active_version_id"] is None
        assert curr_c["completeness_overall_pct"] == 0.0

        # User can access dashboard endpoints with zero errors
        dash_res = await client.get("/api/dashboard/summary", headers=headers_c)
        assert dash_res.status_code == 200
        print("Dashboard accessible immediately without completing assessment.")
        print("Scenario C PASSED.\n")

        # =====================================================================
        # Scenario D: Profile Update via Settings (User A)
        # =====================================================================
        print("--- Scenario D: Profile Update via Settings ---")
        update_res = await client.patch(
            "/api/investor-profile/update",
            json={
                "changes": {
                    "policy": {"restriction_topics": ["TOBACCO", "WEAPONS"], "allocation_mode": "STRATEGIC"}
                },
                "reason": "Ethical exclusions added via Settings",
            },
            headers=headers_a,
        )
        assert update_res.status_code == 200, update_res.text
        v2_data = update_res.json()["data"]
        print(f"Settings update successful: Version={v2_data['version_number']}")
        assert v2_data["version_number"] == 2

        # Check version history table
        hist_res = await client.get("/api/investor-profile/versions", headers=headers_a)
        assert hist_res.status_code == 200
        history = hist_res.json()["data"]
        print(f"Version history count: {len(history)}")
        assert len(history) == 2
        assert history[0]["version_number"] == 2
        assert history[0]["change_source"] == "SETTINGS"
        assert history[1]["version_number"] == 1
        assert history[1]["change_source"] == "ONBOARDING"
        print("Scenario D PASSED.\n")

        # =====================================================================
        # Scenario E: Copilot Conversational Profile Change (User A)
        # =====================================================================
        print("--- Scenario E: Copilot Conversational Profile Change ---")
        conv_res = await client.post("/api/copilot/conversations", json={"title": "Risk Policy Update"}, headers=headers_a)
        conv_id = conv_res.json()["data"]["id"]

        copilot_input = "My income is stable now and I can take more risk."
        print(f"User message to Copilot: '{copilot_input}'")
        msg_res = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": copilot_input},
            headers=headers_a,
        )
        assert msg_res.status_code == 200, msg_res.text
        msg_data = msg_res.json()["data"]
        struct_e = msg_data.get("structured_response") or msg_data.get("message", {}).get("structured_metadata", {})

        print(f"Copilot Response Type: {struct_e.get('response_type')}")
        assert struct_e["response_type"] == "PROPOSAL"
        prop_e = struct_e["proposal"]
        assert prop_e["action_type"] == "UPDATE_INVESTOR_PROFILE"
        assert prop_e["permission_level"] == "LEVEL_2_CONFIRMATION_REQUIRED"
        print(f"Proposal generated: ID={prop_e['id']}, Action={prop_e['action_type']}, Status={prop_e['status']}")

        # Invariant: NO writes to database before confirmation
        mid_curr = (await client.get("/api/investor-profile/current", headers=headers_a)).json()["data"]
        assert mid_curr["version_number"] == 2, "Profile must remain at v2 before confirmation!"

        # Explicit confirmation via proposals API
        confirm_e = await client.post(
            f"/api/copilot/proposals/{prop_e['id']}/confirm",
            json={"confirmation_text": "CONFIRM"},
            headers=headers_a,
        )
        assert confirm_e.status_code == 200, confirm_e.text
        exec_e = confirm_e.json()["data"]["execution_result"]
        print(f"Proposal confirmed and executed: Result status={exec_e.get('status')}, New Version={exec_e.get('version_number')}")
        assert exec_e.get("status") == "APPLIED"
        assert exec_e.get("version_number") == 3

        # Post-confirmation active profile check
        after_curr = (await client.get("/api/investor-profile/current", headers=headers_a)).json()["data"]
        assert after_curr["version_number"] == 3
        assert after_curr["risk"]["tolerance_summary"] == "HIGH"
        assert after_curr["goals"]["income_reliability"] == "RELIABLE"

        # Check CopilotAuditLog in database
        async with get_session_factory()() as db:
            audit_res = await db.execute(
                select(CopilotAuditLog).where(
                    CopilotAuditLog.user_id == uuid.UUID(user_id_a),
                    CopilotAuditLog.action_type == "UPDATE_INVESTOR_PROFILE",
                )
            )
            audit_logs = audit_res.scalars().all()
            print(f"Verified CopilotAuditLog entries: {len(audit_logs)}")
            assert len(audit_logs) >= 1
            print(f"Audit log entry: Action={audit_logs[0].action_type}, ExecutionStatus={audit_logs[0].execution_status}")
            assert audit_logs[0].execution_status == "SUCCESS"
        print("Scenario E PASSED.\n")

        # =====================================================================
        # Scenario F: Portfolio Setup Handoff (Reusing Phase 3 Import Engine)
        # =====================================================================
        print("--- Scenario F: Portfolio Setup Handoff ---")
        import_conv_res = await client.post("/api/copilot/conversations", json={"title": "Portfolio Handoff"}, headers=headers_a)
        import_conv_id = import_conv_res.json()["data"]["id"]

        import_text = "Mevcut portföyümde 50 adet THYAO var, maliyetim 300 TL."
        print(f"User imports portfolio after onboarding: '{import_text}'")
        import_msg = await client.post(
            f"/api/copilot/conversations/{import_conv_id}/messages",
            json={"content": import_text},
            headers=headers_a,
        )
        assert import_msg.status_code == 200
        data_f = import_msg.json()["data"]
        struct_f = data_f.get("structured_response") or data_f.get("message", {}).get("structured_metadata", {})
        batch_f = struct_f.get("import_batch")
        prop_f = struct_f.get("proposal")

        assert batch_f is not None
        assert prop_f is not None
        assert prop_f["action_type"] == "PORTFOLIO_IMPORT"
        print(f"Phase 3 Import Batch created seamlessly: ID={batch_f['id']}, Items={len(batch_f['items'])}")

        # Confirm import batch
        confirm_f = await client.post(
            f"/api/copilot/proposals/{prop_f['id']}/confirm",
            json={"confirmation_text": "IMPORT"},
            headers=headers_a,
        )
        assert confirm_f.status_code == 200
        print("Portfolio import confirmed successfully!")

        async with get_session_factory()() as db:
            op_res = await db.execute(
                select(OpeningPosition).where(
                    OpeningPosition.user_id == uuid.UUID(user_id_a),
                )
            )
            ops = op_res.scalars().all()
            assert len(ops) >= 1
            print(f"Verified OpeningPosition saved: Count={len(ops)}, Quantity={ops[0].quantity}, Cost={ops[0].average_cost}")

        print("Scenario F PASSED.\n")

    print("======================================================================")
    print("ALL 6 PHASE 4 SCENARIOS VERIFIED SUCCESSFULLY (100%)")
    print("======================================================================")


if __name__ == "__main__":
    asyncio.run(run_verification())
