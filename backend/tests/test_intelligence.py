"""Comprehensive test suite for the Investment Intelligence persistence layer.

Validates:
1. Unreviewed instrument returns null state gracefully.
2. Upserting current intelligence state (PUT /api/instruments/{id}/intelligence).
3. Successive state updates overwrite existing state while preserving history.
4. Adding review records (POST /api/instruments/{id}/reviews) and listing them (GET).
5. Auto-applying review machine_record into current intelligence state.
6. Review history is preserved across state updates.
7. Deleting a user's Asset does NOT delete Instrument intelligence or reviews.
8. Validation rejects invalid enum values (422).
9. Technical plan creation, retrieval, and deactivation of previous plans.
10. Authentication requirements (401 when unauthorized).
11. 404 response on nonexistent instruments.
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.models.instrument import Instrument
from app.models.intelligence import (
    InstrumentIntelligenceState,
    IntelligenceReview,
    Recommendation,
    TechnicalPlan,
    TechnicalStatus,
    ThesisStatus,
    ValuationStatus,
)


async def _register_user(client: AsyncClient, email: str = "user@example.com") -> tuple[str, dict]:
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "display_name": email.split("@")[0],
        },
    )
    token = resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return token, headers


async def _create_test_instrument(client: AsyncClient, headers: dict) -> dict:
    """Helper to create an asset which automatically provisions an instrument."""
    payload = {
        "asset_type": "STOCK",
        "symbol": f"TEST-{uuid.uuid4().hex[:6].upper()}",
        "name": "Test Company Inc",
        "current_price_currency": "USD",
        "initial_transaction": {
            "transaction_type": "BUY",
            "quantity": "10",
            "price_per_unit": "100.00",
            "transaction_currency": "USD",
            "transaction_date": "2024-06-01",
        },
    }
    with patch("app.services.price.fetch_price", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (Decimal("100.00"), "USD")
        resp = await client.post("/api/assets", json=payload, headers=headers)
        assert resp.status_code == 201
        data = resp.json()["data"]
        return data["instrument"]


@pytest.mark.asyncio
async def test_unreviewed_instrument_returns_null_state(client: AsyncClient):
    _, headers = await _register_user(client, "unreviewed@example.com")
    inst = await _create_test_instrument(client, headers)
    inst_id = inst["id"]

    # 1. Direct intelligence state endpoint returns None
    resp = await client.get(f"/api/instruments/{inst_id}/intelligence", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["data"] is None

    # 2. Instrument detail endpoint includes intelligence_state: null
    resp_inst = await client.get(f"/api/instruments/{inst_id}", headers=headers)
    assert resp_inst.status_code == 200
    inst_data = resp_inst.json()["data"]
    assert inst_data["intelligence_state"] is None

    # 3. Reviews list is empty
    resp_rev = await client.get(f"/api/instruments/{inst_id}/reviews", headers=headers)
    assert resp_rev.status_code == 200
    assert resp_rev.json()["data"] == []


@pytest.mark.asyncio
async def test_upsert_intelligence_state(client: AsyncClient, db_session: AsyncSession):
    _, headers = await _register_user(client, "upsert@example.com")
    inst = await _create_test_instrument(client, headers)
    inst_id = inst["id"]

    # Initial upsert
    create_payload = {
        "thesis_status": "UNCHANGED",
        "valuation_status": "FAIR",
        "technical_status": "ON_TRACK",
        "recommendation": "HOLD",
        "human_brief": "Thesis intact, valuation fair at current levels.",
        "last_review_at": "2024-06-15T10:00:00",
        "next_review_at": "2024-09-15T10:00:00",
    }
    resp = await client.put(
        f"/api/instruments/{inst_id}/intelligence",
        json=create_payload,
        headers=headers,
    )
    assert resp.status_code == 200
    res_data = resp.json()["data"]
    assert res_data["instrument_id"] == inst_id
    assert res_data["thesis_status"] == "UNCHANGED"
    assert res_data["valuation_status"] == "FAIR"
    assert res_data["technical_status"] == "ON_TRACK"
    assert res_data["recommendation"] == "HOLD"
    assert res_data["human_brief"] == "Thesis intact, valuation fair at current levels."

    state_id = res_data["id"]

    # Subsequent update (e.g. upgraded recommendation and stronger thesis)
    update_payload = {
        "thesis_status": "STRONGER",
        "valuation_status": "ATTRACTIVE",
        "technical_status": "ON_TRACK",
        "recommendation": "ADD",
        "human_brief": "Q2 earnings beat expectations. Growth accelerating.",
    }
    resp_update = await client.put(
        f"/api/instruments/{inst_id}/intelligence",
        json=update_payload,
        headers=headers,
    )
    assert resp_update.status_code == 200
    updated_data = resp_update.json()["data"]
    assert updated_data["id"] == state_id  # same record updated in place
    assert updated_data["thesis_status"] == "STRONGER"
    assert updated_data["valuation_status"] == "ATTRACTIVE"
    assert updated_data["recommendation"] == "ADD"
    assert updated_data["human_brief"] == "Q2 earnings beat expectations. Growth accelerating."

    # Verify directly in DB
    db_state = (
        await db_session.execute(
            select(InstrumentIntelligenceState).where(
                InstrumentIntelligenceState.instrument_id == uuid.UUID(inst_id)
            )
        )
    ).scalar_one()
    assert db_state.thesis_status == ThesisStatus.STRONGER
    assert db_state.recommendation == Recommendation.ADD


@pytest.mark.asyncio
async def test_create_and_list_reviews(client: AsyncClient):
    _, headers = await _register_user(client, "reviews@example.com")
    inst = await _create_test_instrument(client, headers)
    inst_id = inst["id"]

    # 1. Add first review
    rev1_payload = {
        "protocol": "quarterly_fundamental_review",
        "run_type": "scheduled",
        "status": "COMPLETED",
        "machine_record": {
            "metrics": {"pe_ratio": 22.5, "revenue_growth_yoy": 0.18},
            "thesis_status": "UNCHANGED",
            "valuation_status": "FAIR",
            "recommendation": "HOLD",
        },
        "human_brief": "Q1 review complete. Fundamentals steady.",
        "confidence": "HIGH",
        "research_path": "/intelligence/runs/run-001",
        "source_run_id": "run-001",
    }
    resp1 = await client.post(
        f"/api/instruments/{inst_id}/reviews",
        json=rev1_payload,
        headers=headers,
    )
    assert resp1.status_code == 201
    rev1_data = resp1.json()["data"]
    assert rev1_data["protocol"] == "quarterly_fundamental_review"
    assert rev1_data["source_run_id"] == "run-001"
    assert rev1_data["confidence"] == "HIGH"
    assert rev1_data["machine_record"]["metrics"]["pe_ratio"] == 22.5

    # 2. Add second review
    rev2_payload = {
        "protocol": "technical_momentum_scan",
        "run_type": "trigger",
        "status": "COMPLETED",
        "machine_record": {"rsi_14": 42.0, "trend": "bullish_continuation"},
        "human_brief": "Consolidating above 50-day EMA.",
        "confidence": "MEDIUM",
        "source_run_id": "run-002",
    }
    resp2 = await client.post(
        f"/api/instruments/{inst_id}/reviews",
        json=rev2_payload,
        headers=headers,
    )
    assert resp2.status_code == 201

    # 3. List reviews (should return both, latest first)
    list_resp = await client.get(f"/api/instruments/{inst_id}/reviews", headers=headers)
    assert list_resp.status_code == 200
    reviews = list_resp.json()["data"]
    assert len(reviews) == 2
    assert reviews[0]["protocol"] == "technical_momentum_scan"
    assert reviews[1]["protocol"] == "quarterly_fundamental_review"


@pytest.mark.asyncio
async def test_auto_apply_review_to_state(client: AsyncClient):
    _, headers = await _register_user(client, "autoapply@example.com")
    inst = await _create_test_instrument(client, headers)
    inst_id = inst["id"]

    # Create review with auto_apply_state=True
    rev_payload = {
        "protocol": "full_investment_thesis_review",
        "run_type": "adhoc",
        "status": "COMPLETED",
        "machine_record": {
            "thesis_status": "STRONGER",
            "valuation_status": "ATTRACTIVE",
            "technical_status": "ON_TRACK",
            "recommendation": "ADD",
        },
        "human_brief": "High conviction upgrade after breakthrough product launch.",
        "confidence": "HIGH",
        "auto_apply_state": True,
    }
    resp = await client.post(
        f"/api/instruments/{inst_id}/reviews",
        json=rev_payload,
        headers=headers,
    )
    assert resp.status_code == 201

    # Verify current state was automatically updated
    state_resp = await client.get(f"/api/instruments/{inst_id}/intelligence", headers=headers)
    assert state_resp.status_code == 200
    state = state_resp.json()["data"]
    assert state is not None
    assert state["thesis_status"] == "STRONGER"
    assert state["valuation_status"] == "ATTRACTIVE"
    assert state["technical_status"] == "ON_TRACK"
    assert state["recommendation"] == "ADD"
    assert state["human_brief"] == "High conviction upgrade after breakthrough product launch."
    assert state["last_review_at"] is not None


@pytest.mark.asyncio
async def test_review_history_preserved_across_state_updates(client: AsyncClient):
    _, headers = await _register_user(client, "history@example.com")
    inst = await _create_test_instrument(client, headers)
    inst_id = inst["id"]

    # 1. Post a review
    await client.post(
        f"/api/instruments/{inst_id}/reviews",
        json={
            "protocol": "audit_review_1",
            "status": "COMPLETED",
            "human_brief": "First review audit note.",
        },
        headers=headers,
    )

    # 2. Modify state multiple times via PUT
    for rec in ["HOLD", "ADD", "REDUCE"]:
        await client.put(
            f"/api/instruments/{inst_id}/intelligence",
            json={"recommendation": rec},
            headers=headers,
        )

    # 3. Verify original review is intact and unmodified
    resp = await client.get(f"/api/instruments/{inst_id}/reviews", headers=headers)
    assert resp.status_code == 200
    reviews = resp.json()["data"]
    assert len(reviews) == 1
    assert reviews[0]["protocol"] == "audit_review_1"
    assert reviews[0]["human_brief"] == "First review audit note."


@pytest.mark.asyncio
async def test_asset_deletion_preserves_instrument_intelligence(
    client: AsyncClient, db_session: AsyncSession
):
    _, headers = await _register_user(client, "assetdelete@example.com")

    # Create asset
    payload = {
        "asset_type": "STOCK",
        "symbol": "SHARED-CORP",
        "name": "Shared Corp",
        "current_price_currency": "USD",
        "initial_transaction": {
            "transaction_type": "BUY",
            "quantity": "5",
            "price_per_unit": "50.00",
            "transaction_currency": "USD",
            "transaction_date": "2024-05-10",
        },
    }
    with patch("app.services.price.fetch_price", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (Decimal("50.00"), "USD")
        asset_resp = await client.post("/api/assets", json=payload, headers=headers)
        assert asset_resp.status_code == 201
        asset_data = asset_resp.json()["data"]
        asset_id = asset_data["id"]
        inst_id = asset_data["instrument_id"]

    # Attach intelligence state and review to the Instrument
    await client.put(
        f"/api/instruments/{inst_id}/intelligence",
        json={"thesis_status": "STRONGER", "recommendation": "ADD"},
        headers=headers,
    )
    await client.post(
        f"/api/instruments/{inst_id}/reviews",
        json={"protocol": "pre_delete_protocol", "status": "COMPLETED"},
        headers=headers,
    )

    # User deletes the Asset
    del_resp = await client.delete(f"/api/assets/{asset_id}", headers=headers)
    assert del_resp.status_code == 200

    # Verify Asset is deleted
    asset_check = (
        await db_session.execute(select(Asset).where(Asset.id == uuid.UUID(asset_id)))
    ).scalar_one_or_none()
    assert asset_check is None

    # Instrument still exists!
    inst_row = (
        await db_session.execute(select(Instrument).where(Instrument.id == uuid.UUID(inst_id)))
    ).scalar_one_or_none()
    assert inst_row is not None

    # Intelligence state still exists and is retrievable!
    state_resp = await client.get(f"/api/instruments/{inst_id}/intelligence", headers=headers)
    assert state_resp.status_code == 200
    assert state_resp.json()["data"]["recommendation"] == "ADD"

    # Reviews still exist!
    reviews_resp = await client.get(f"/api/instruments/{inst_id}/reviews", headers=headers)
    assert reviews_resp.status_code == 200
    assert len(reviews_resp.json()["data"]) == 1
    assert reviews_resp.json()["data"][0]["protocol"] == "pre_delete_protocol"


@pytest.mark.asyncio
async def test_validation_rejects_invalid_enums(client: AsyncClient):
    _, headers = await _register_user(client, "validation@example.com")
    inst = await _create_test_instrument(client, headers)
    inst_id = inst["id"]

    # Invalid recommendation
    resp = await client.put(
        f"/api/instruments/{inst_id}/intelligence",
        json={"recommendation": "MOON_OR_BUST"},
        headers=headers,
    )
    assert resp.status_code == 422

    # Invalid thesis_status
    resp = await client.put(
        f"/api/instruments/{inst_id}/intelligence",
        json={"thesis_status": "SUPER_BULLISH"},
        headers=headers,
    )
    assert resp.status_code == 422

    # Invalid valuation_status
    resp = await client.put(
        f"/api/instruments/{inst_id}/intelligence",
        json={"valuation_status": "DEEP_VALUE_EXTREME"},
        headers=headers,
    )
    assert resp.status_code == 422

    # Invalid technical_status
    resp = await client.put(
        f"/api/instruments/{inst_id}/intelligence",
        json={"technical_status": "OVERHEATED"},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_technical_plan_lifecycle(client: AsyncClient, db_session: AsyncSession):
    _, headers = await _register_user(client, "techplan@example.com")
    inst = await _create_test_instrument(client, headers)
    inst_id = inst["id"]

    # 1. Initially no active technical plan
    resp = await client.get(f"/api/instruments/{inst_id}/technical-plan", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"] is None

    # 2. Create first technical plan
    plan1_payload = {
        "reference_price": 150.50,
        "trend_expectation": "bullish_continuation",
        "entry_zones": [{"min": 145.0, "max": 150.0, "rationale": "50-day EMA confluence"}],
        "support_zones": [{"min": 140.0, "max": 142.0}],
        "resistance_zones": [{"min": 165.0, "max": 170.0}],
        "review_or_invalidation_zones": [{"min": 135.0, "max": 137.0}],
        "profit_taking_or_reassessment_zones": [{"min": 168.0, "max": 175.0}],
        "notes": "Strong breakout on high volume.",
        "active": True,
    }
    resp1 = await client.put(
        f"/api/instruments/{inst_id}/technical-plan",
        json=plan1_payload,
        headers=headers,
    )
    assert resp1.status_code == 200
    p1_data = resp1.json()["data"]
    assert p1_data["trend_expectation"] == "bullish_continuation"
    assert p1_data["active"] is True
    p1_id = p1_data["id"]

    # 3. Retrieve active plan
    resp_get = await client.get(f"/api/instruments/{inst_id}/technical-plan", headers=headers)
    assert resp_get.status_code == 200
    assert resp_get.json()["data"]["id"] == p1_id

    # 4. Upsert a second active plan -> should deactivate the first
    plan2_payload = {
        "reference_price": 165.00,
        "trend_expectation": "consolidation",
        "support_zones": [{"min": 155.0, "max": 158.0}],
        "resistance_zones": [{"min": 172.0, "max": 175.0}],
        "notes": "Target reached, raising stop to break even.",
        "active": True,
    }
    resp2 = await client.put(
        f"/api/instruments/{inst_id}/technical-plan",
        json=plan2_payload,
        headers=headers,
    )
    assert resp2.status_code == 200
    p2_data = resp2.json()["data"]
    assert p2_data["id"] != p1_id
    assert p2_data["trend_expectation"] == "consolidation"
    assert p2_data["active"] is True

    # Check directly in DB that previous plan was deactivated
    old_plan = (
        await db_session.execute(
            select(TechnicalPlan).where(TechnicalPlan.id == uuid.UUID(p1_id))
        )
    ).scalar_one()
    assert old_plan.active is False


@pytest.mark.asyncio
async def test_authentication_and_404_handling(client: AsyncClient):
    random_id = str(uuid.uuid4())

    # 1. Unauthenticated requests are rejected (401)
    resp_unauth = await client.get(f"/api/instruments/{random_id}/intelligence")
    assert resp_unauth.status_code == 401

    resp_unauth_put = await client.put(
        f"/api/instruments/{random_id}/intelligence",
        json={"recommendation": "HOLD"},
    )
    assert resp_unauth_put.status_code == 401

    resp_unauth_rev = await client.post(
        f"/api/instruments/{random_id}/reviews",
        json={"protocol": "test"},
    )
    assert resp_unauth_rev.status_code == 401

    # 2. Authenticated requests on nonexistent instrument return 404
    _, headers = await _register_user(client, "authcheck@example.com")
    resp_404_state = await client.get(f"/api/instruments/{random_id}/intelligence", headers=headers)
    assert resp_404_state.status_code == 404

    resp_404_put = await client.put(
        f"/api/instruments/{random_id}/intelligence",
        json={"recommendation": "HOLD"},
        headers=headers,
    )
    assert resp_404_put.status_code == 404

    resp_404_rev = await client.get(f"/api/instruments/{random_id}/reviews", headers=headers)
    assert resp_404_rev.status_code == 404

    resp_404_plan = await client.get(f"/api/instruments/{random_id}/technical-plan", headers=headers)
    assert resp_404_plan.status_code == 404


@pytest.mark.asyncio
async def test_idempotent_reviews_by_source_run_id(client: AsyncClient):
    _, headers = await _register_user(client, "idempotency@example.com")
    inst = await _create_test_instrument(client, headers)
    inst_id = inst["id"]

    run_payload = {
        "protocol": "thesis_evaluation",
        "status": "COMPLETED",
        "machine_record": {
            "thesis_status": "UNCHANGED",
            "recommendation": "HOLD",
        },
        "human_brief": "Idempotent initial run.",
        "source_run_id": "finance-run-unique-001",
        "auto_apply_state": True,
    }

    # 1. First post
    r1 = await client.post(f"/api/instruments/{inst_id}/reviews", json=run_payload, headers=headers)
    assert r1.status_code == 201
    rev1_id = r1.json()["data"]["id"]

    # 2. Second post with identical source_run_id
    r2 = await client.post(f"/api/instruments/{inst_id}/reviews", json=run_payload, headers=headers)
    assert r2.status_code in (200, 201)
    rev2_id = r2.json()["data"]["id"]
    assert rev1_id == rev2_id

    # 3. Reviews list should only have 1 item
    list_resp = await client.get(f"/api/instruments/{inst_id}/reviews", headers=headers)
    assert list_resp.status_code == 200
    reviews = list_resp.json()["data"]
    assert len(reviews) == 1
    assert reviews[0]["id"] == rev1_id


@pytest.mark.asyncio
async def test_integration_token_authentication(client: AsyncClient, monkeypatch):
    import secrets
    import uuid
    from pydantic import SecretStr
    from app.config import settings

    registered = await client.post("/api/auth/register", json={
        "email": "service_owner@example.com", "password": "synthetic-password-123"
    })
    assert registered.status_code == 201
    token = secrets.token_urlsafe(32)
    monkeypatch.setattr(settings, "INTEGRATION_TOKEN", SecretStr(token))
    monkeypatch.setattr(settings, "INTEGRATION_USER_ID", uuid.UUID(registered.json()["data"]["user"]["id"]))
    resp = await client.get("/api/instruments", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
