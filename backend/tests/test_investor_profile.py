"""Comprehensive test suite for PortfolioMind Phase 4 — Investor Profile & Personalization.

Tests:
1. Question catalog & sections retrieval
2. Assessment progression, answer saving, skipping
3. Separate risk tolerance vs capacity model
4. Contradiction & consistency engine (X01, X04)
5. Meaningful completeness & capability readiness
6. Profile draft review & material versioning (v1, v2)
7. Multi-user isolation & security
8. Copilot context integration (USER_PROFILE & INVESTMENT_POLICY)
9. Copilot profile change proposal, Level 2 confirmation, executor, and audit
"""

from decimal import Decimal
import json
import uuid

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import select

from app.main import app
from app.models.copilot import CopilotActionProposal, CopilotAuditLog
from app.models.investor_profile import (
    InvestorProfile,
    InvestorProfileAnswer,
    InvestorProfileAssessment,
    InvestorProfileDraft,
    InvestorProfileVersion,
)
from app.models.user import User
from app.schemas.copilot import IntentType
from app.schemas.investor_profile import (
    AnswerSubmitRequest,
    CapacityStatus,
    KnowledgeState,
    LiquiditySummary,
    ProfileConfirmRequest,
    ReadinessStatus,
    ToleranceSummary,
)

from app.services.copilot import CopilotContextEngine, CopilotService, CopilotWriteExecutor
from app.services.copilot.intent_classifier import IntentClassifier
from app.services.investor_profile.profile_service import InvestorProfileService
from app.services.investor_profile.questions import QUESTIONS, SECTIONS
from app.services.investor_profile.rules_engine import InvestorProfileRulesEngine


async def _register_user(client: AsyncClient, email: str) -> tuple[str, dict[str, str]]:
    """Helper to register a user and return user_id and Authorization headers."""
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "Password123!", "display_name": "Test Investor"},
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["data"]["access_token"]
    user_id = resp.json()["data"]["user"]["id"]
    return user_id, {"Authorization": f"Bearer {token}"}


# -----------------------------------------------------------------------------
# 1. Question Catalog
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_question_catalog():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/investor-profile/questions")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["sections"]) >= 5
        assert len(data["questions"]) >= 12
        q_ids = [q["id"] for q in data["questions"]]
        assert "C01" in q_ids
        assert "C08" in q_ids
        assert "C12" in q_ids
        assert "F01" in q_ids


# -----------------------------------------------------------------------------
# 2. Assessment Progression & Answer Saving
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_assessment_progression_and_skipping(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user_id_str, headers = await _register_user(client, f"prof_{uuid.uuid4().hex[:6]}@example.com")
        user_id = uuid.UUID(user_id_str)

        # Start / get current assessment
        curr_resp = await client.get("/api/investor-profile/assessment/current", headers=headers)
        assert curr_resp.status_code == 200
        asmt_data = curr_resp.json()["data"]
        assert asmt_data["status"] == "DRAFT"
        assert asmt_data["answers"] == []

        # Save structured answer for C01
        ans1_resp = await client.post(
            "/api/investor-profile/assessment/answer",
            json={
                "question_id": "C01",
                "knowledge_state": "KNOWN",
                "selected_options": ["GROW"],
                "numeric_inputs": {},
                "raw_text": None,
            },
            headers=headers,
        )
        assert ans1_resp.status_code == 200
        assert ans1_resp.json()["data"]["question_id"] == "C01"
        assert ans1_resp.json()["data"]["selected_options"] == ["GROW"]

        # Save composite answer for C02
        ans2_resp = await client.post(
            "/api/investor-profile/assessment/answer",
            json={
                "question_id": "C02",
                "knowledge_state": "KNOWN",
                "selected_options": ["GE_10Y", "FLEXIBLE"],
                "numeric_inputs": {"flexibility": "FLEXIBLE"},
            },
            headers=headers,
        )
        assert ans2_resp.status_code == 200

        # Skip question C03
        skip_resp = await client.post(
            "/api/investor-profile/assessment/skip-question?question_id=C03",
            headers=headers,
        )
        assert skip_resp.status_code == 200
        assert skip_resp.json()["data"]["knowledge_state"] == "SKIPPED"

        # Check in-flight draft is updated automatically
        draft_resp = await client.get("/api/investor-profile/draft", headers=headers)
        assert draft_resp.status_code == 200
        draft_data = draft_resp.json()["data"]
        assert draft_data["goals"]["items"][0]["kind"] == "GROW"
        assert draft_data["goals"]["items"][0]["horizon"] == "GE_10Y"
        assert draft_data["completeness"]["overall_pct"] > 0.0


# -----------------------------------------------------------------------------
# 3. Separation of Risk Tolerance and Risk Capacity (Scenario B: Contradiction)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_risk_tolerance_vs_capacity_and_contradiction():
    """Verify that a high stated drawdown tolerance does NOT mask a constrained
    financial risk capacity, and that contradiction X01 is surfaced.
    """
    answers_map = {
        "C01": {"selected_options": ["PURCHASE"]},  # Home purchase
        "C02": {
            "selected_options": ["LT_1Y", "FIXED"],  # Needed in < 1 year, cannot delay
            "numeric_inputs": {"flexibility": "FIXED"},
        },
        "C03": {"selected_options": ["ONE_OFF"]},
        "F01": {
            "selected_options": ["LT_12M"],
            "numeric_inputs": {"percentage": 50.0, "size": {"percentage": 50.0}},
        },
        "C04": {"selected_options": ["M3_6"]},
        "C05": {"selected_options": ["SURPLUS", "RELIABLE"]},
        "C06": {"selected_options": ["MANAGEABLE"]},
        "C07": {"selected_options": ["GOAL_UNAFFORDABLE"]},  # Permanent 20% loss makes goal unaffordable
        "C08": {"selected_options": ["P40_PLUS"]},  # High psychological tolerance: 40%+
        "C09": {"selected_options": ["HOLD"]},
        "C10": {"selected_options": ["STOCKS"]},
        "C11": {"selected_options": ["PERIODIC"]},
        "C12": {"selected_options": ["BORROWING"]},
    }

    goals, risk, policy, prefs, issues, completeness, readiness = (
        InvestorProfileRulesEngine.evaluate(answers=answers_map)
    )

    # 1. Stated tolerance is HIGH
    assert risk.tolerance_summary == ToleranceSummary.HIGH
    assert risk.drawdown_comfort == "P40_PLUS"

    # 2. Risk capacity is CONSTRAINED
    assert len(risk.capacity_by_goal) == 1
    assert risk.capacity_by_goal[0].status == CapacityStatus.CONSTRAINED

    # 3. Contradiction X01 is detected and surfaced
    issue_rule_ids = [i.rule_id for i in issues]
    assert "X01" in issue_rule_ids
    x01_issue = next(i for i in issues if i.rule_id == "X01")
    assert "finansal risk kapasitenizi sınırlandırmaktadır" in x01_issue.explanation

    # 4. Liquidity needs are KNOWN
    assert risk.liquidity_summary == LiquiditySummary.KNOWN_NEEDS

    # 5. Core coverage is comprehensive
    assert completeness.overall_pct >= 90.0


# -----------------------------------------------------------------------------
# 4. Contradiction X04: Tolerance vs Stress Reaction Conflict
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tolerance_stress_conflict_x04():
    """Verify that claiming 40% tolerance but selecting 'EXIT' under stress triggers X04
    and yields MIXED tolerance.
    """
    answers_map = {
        "C08": {"selected_options": ["P40_PLUS"]},
        "C09": {"selected_options": ["EXIT"]},  # Panic sell
    }
    goals, risk, policy, prefs, issues, completeness, readiness = (
        InvestorProfileRulesEngine.evaluate(answers=answers_map)
    )

    assert risk.tolerance_summary == ToleranceSummary.MIXED
    assert any(i.rule_id == "X04" for i in issues)


# -----------------------------------------------------------------------------
# 5. Profile Draft Review, Confirmation, and Versioning
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_profile_confirmation_and_versioning(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user_id_str, headers = await _register_user(client, f"ver_{uuid.uuid4().hex[:6]}@example.com")
        user_id = uuid.UUID(user_id_str)

        # Before confirmation: current profile shows version_number = None, active_version_id = None
        curr_before = (await client.get("/api/investor-profile/current", headers=headers)).json()["data"]
        assert curr_before["version_number"] is None
        assert curr_before["active_version_id"] is None

        # Fill core answers
        core_answers = [
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
        for q_id, opts, num_in in core_answers:
            await client.post(
                "/api/investor-profile/assessment/answer",
                json={
                    "question_id": q_id,
                    "knowledge_state": "KNOWN",
                    "selected_options": opts,
                    "numeric_inputs": num_in,
                },
                headers=headers,
            )

        # Check draft
        draft_resp = await client.get("/api/investor-profile/draft", headers=headers)
        assert draft_resp.status_code == 200
        draft_data = draft_resp.json()["data"]
        assert draft_data["completeness"]["overall_pct"] >= 95.0

        # Confirm draft -> produces v1
        conf_resp = await client.post(
            "/api/investor-profile/confirm",
            json={"change_reason": "Onboarding completed", "change_source": "ONBOARDING"},
            headers=headers,
        )
        assert conf_resp.status_code == 200
        v1_data = conf_resp.json()["data"]
        assert v1_data["version_number"] == 1
        assert v1_data["change_reason"] == "Onboarding completed"
        assert v1_data["change_source"] == "ONBOARDING"

        # Check active profile
        active_resp = await client.get("/api/investor-profile/current", headers=headers)
        active_data = active_resp.json()["data"]
        assert active_data["version_number"] == 1
        assert active_data["active_version_id"] == v1_data["version_id"]
        assert active_data["risk"]["tolerance_summary"] == "MODERATE"
        assert active_data["completeness_overall_pct"] >= 95.0

        # Perform a settings update -> produces v2
        update_resp = await client.patch(
            "/api/investor-profile/update",
            json={
                "changes": {
                    "risk": {"drawdown_comfort": "P30", "tolerance_summary": "HIGH"}
                },
                "reason": "Risk tolerance increased via Settings",
            },
            headers=headers,
        )
        assert update_resp.status_code == 200
        v2_data = update_resp.json()["data"]
        assert v2_data["version_number"] == 2

        # Check version history
        hist_resp = await client.get("/api/investor-profile/versions", headers=headers)
        assert hist_resp.status_code == 200
        history = hist_resp.json()["data"]
        assert len(history) == 2
        assert history[0]["version_number"] == 2
        assert history[1]["version_number"] == 1

        # Check detail of historical v1
        v1_detail = (await client.get(f"/api/investor-profile/versions/{v1_data['version_id']}", headers=headers)).json()["data"]
        assert v1_detail["version_number"] == 1
        assert v1_detail["snapshot"]["risk"]["drawdown_comfort"] == "P20"


# -----------------------------------------------------------------------------
# 6. Multi-User Isolation
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_multi_user_isolation(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        u1_str, h1 = await _register_user(client, f"u1_{uuid.uuid4().hex[:6]}@example.com")
        u2_str, h2 = await _register_user(client, f"u2_{uuid.uuid4().hex[:6]}@example.com")

        # User 1 saves answers and confirms v1
        await client.post(
            "/api/investor-profile/assessment/answer",
            json={"question_id": "C01", "selected_options": ["GROW"]},
            headers=h1,
        )
        conf1 = (await client.post("/api/investor-profile/confirm", json={}, headers=h1)).json()["data"]
        v1_id = conf1["version_id"]

        # User 2 cannot access User 1's version
        u2_access = await client.get(f"/api/investor-profile/versions/{v1_id}", headers=h2)
        assert u2_access.status_code == 404

        # User 2 current profile is completely separate
        u2_profile = (await client.get("/api/investor-profile/current", headers=h2)).json()["data"]
        assert u2_profile["version_number"] is None
        assert u2_profile["user_id"] == u2_str


# -----------------------------------------------------------------------------
# 7. Copilot Context Integration
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_copilot_context_integration(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user_id_str, headers = await _register_user(client, f"cop_{uuid.uuid4().hex[:6]}@example.com")
        user_id = uuid.UUID(user_id_str)

        # Set up a confirmed profile with goals and risk
        await client.post(
            "/api/investor-profile/assessment/answer",
            json={"question_id": "C01", "selected_options": ["RETIREMENT"]},
            headers=headers,
        )
        await client.post(
            "/api/investor-profile/assessment/answer",
            json={"question_id": "C08", "selected_options": ["P20"]},
            headers=headers,
        )
        await client.post("/api/investor-profile/confirm", json={}, headers=headers)

        # Test context engine with USER_PROFILE and INVESTMENT_POLICY intent
        intent = IntentClassifier.classify("What are my biggest portfolio risks?")
        bundle = await CopilotContextEngine.build_context(
            db=db_session,
            user_id=user_id,
            intent=intent,
            entities={},
        )

        user_profile_item = next(
            (it for it in bundle.items if it.source_type == "USER_PROFILE"),
            None,
        )
        assert user_profile_item is not None
        assert user_profile_item.content["has_investor_profile"] is True
        assert user_profile_item.content["version_number"] == 1
        assert user_profile_item.content["goals"]["items"][0]["kind"] == "RETIREMENT"
        assert user_profile_item.content["risk"]["drawdown_comfort"] == "P20"


# -----------------------------------------------------------------------------
# 8. Copilot Profile Change Proposal & Execution (Scenario E)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_copilot_profile_change_proposal_and_confirm(db_session):
    """Scenario E: User says 'My income is stable now and I can take more risk.'
    Copilot must:
    1. Propose structured profile update (Level 2).
    2. Zero immediate database mutations before confirmation.
    3. Require confirmation.
    4. Execute atomic update into a new material InvestorProfileVersion.
    5. Log durable CopilotAuditLog.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user_id_str, headers = await _register_user(client, f"scen_e_{uuid.uuid4().hex[:6]}@example.com")
        user_id = uuid.UUID(user_id_str)

        # Initial profile v1
        await client.post(
            "/api/investor-profile/assessment/answer",
            json={"question_id": "C01", "selected_options": ["GROW"]},
            headers=headers,
        )
        await client.post(
            "/api/investor-profile/assessment/answer",
            json={"question_id": "C08", "selected_options": ["P10"]},  # Initial moderate-low
            headers=headers,
        )
        await client.post("/api/investor-profile/confirm", json={"change_reason": "v1 initial"}, headers=headers)

        # Create Copilot conversation
        conv_resp = await client.post("/api/copilot/conversations", json={"title": "Profile Update"}, headers=headers)
        conv_id = conv_resp.json()["data"]["id"]

        # User sends message: "My income is stable now and I can take more risk."
        msg_resp = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": "My income is stable now and I can take more risk."},
            headers=headers,
        )
        assert msg_resp.status_code == 200
        msg_data = msg_resp.json()["data"]

        # Check proposal was created with Level 2 permission
        structured_resp = msg_data.get("structured_response") or msg_data.get("message", {}).get("structured_metadata", {})
        assert structured_resp["response_type"] == "PROPOSAL"
        proposal_dict = structured_resp["proposal"]
        assert proposal_dict is not None
        assert proposal_dict["action_type"] == "UPDATE_INVESTOR_PROFILE"
        assert proposal_dict["permission_level"] == "LEVEL_2_CONFIRMATION_REQUIRED"
        assert proposal_dict["status"] in ("READY_FOR_CONFIRMATION", "CONFIRMED")

        proposal_id = uuid.UUID(proposal_dict["id"])

        # Invariant: ZERO profile version mutations before confirmation!
        curr_mid = (await client.get("/api/investor-profile/current", headers=headers)).json()["data"]
        assert curr_mid["version_number"] == 1, "Profile must remain at v1 before confirmation"

        # Confirm the proposal
        exec_res = await CopilotWriteExecutor.execute_proposal(
            db=db_session,
            user_id=user_id,
            proposal_id=proposal_id,
        )
        assert exec_res["status"] == "APPLIED"
        assert exec_res["version_number"] == 2

        # Post-confirmation DB check
        curr_after = (await client.get("/api/investor-profile/current", headers=headers)).json()["data"]
        assert curr_after["version_number"] == 2
        assert curr_after["risk"]["drawdown_comfort"] == "P30"
        assert curr_after["risk"]["tolerance_summary"] == "HIGH"
        assert curr_after["goals"]["income_reliability"] == "RELIABLE"

        # Check CopilotAuditLog entry
        audit_res = await db_session.execute(
            select(CopilotAuditLog).where(
                CopilotAuditLog.user_id == user_id,
                CopilotAuditLog.proposal_id == proposal_id,
            )
        )
        audit_entry = audit_res.scalar_one_or_none()
        assert audit_entry is not None
        assert audit_entry.action_type == "UPDATE_INVESTOR_PROFILE"
        assert audit_entry.execution_status == "SUCCESS"
        assert audit_entry.affected_resource_type == "INVESTOR_PROFILE"
