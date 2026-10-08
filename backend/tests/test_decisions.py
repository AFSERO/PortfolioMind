"""Tests for Decision Log: manual entries, filtering, rationale updates,
and auto-logging triggers on transactions and intelligence state transitions.
"""

import uuid
from decimal import Decimal
import pytest
from httpx import AsyncClient

from app.models.decision_log import DecisionEventType


async def _register_user(client: AsyncClient, email: str = "decisions_user@example.com") -> tuple[str, dict]:
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "display_name": "Decisions Tester",
        },
    )
    token = resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return token, headers


@pytest.mark.asyncio
async def test_manual_decision_log_crud(client: AsyncClient):
    _, headers = await _register_user(client, f"crud_{uuid.uuid4().hex[:6]}@example.com")

    # 1. Create a manual decision entry
    payload = {
        "event_type": "MANUAL_DECISION_NOTE",
        "title": "Trimming exposure due to macro uncertainty",
        "summary": "Plan to scale down portfolio risk over next 2 weeks.",
        "user_rationale": "CPI numbers were hotter than expected.",
        "confidence": "HIGH",
        "expectation": "Anticipate market pullback.",
    }
    resp = await client.post("/api/decisions", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()["data"]
    decision_id = data["id"]
    assert data["title"] == payload["title"]
    assert data["event_type"] == "MANUAL_DECISION_NOTE"
    assert data["user_rationale"] == payload["user_rationale"]

    # 2. Get single decision entry
    resp = await client.get(f"/api/decisions/{decision_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == decision_id

    # 3. Update rationale
    patch_payload = {
        "user_rationale": "Updated rationale: Revised core CPI was in fact moderate.",
        "confidence": "MEDIUM",
        "expectation": "Wait for next FOMC meeting before taking action.",
    }
    resp = await client.patch(
        f"/api/decisions/{decision_id}/rationale",
        json=patch_payload,
        headers=headers,
    )
    assert resp.status_code == 200
    updated = resp.json()["data"]
    assert updated["user_rationale"] == patch_payload["user_rationale"]
    assert updated["confidence"] == "MEDIUM"

    # 4. List decisions
    resp = await client.get("/api/decisions", headers=headers)
    assert resp.status_code == 200
    list_data = resp.json()["data"]
    assert list_data["total"] >= 1
    assert any(d["id"] == decision_id for d in list_data["items"])


@pytest.mark.asyncio
async def test_transactions_auto_log_decision_events(client: AsyncClient):
    _, headers = await _register_user(client, f"tx_log_{uuid.uuid4().hex[:6]}@example.com")

    # 1. Create an asset (this executes an initial BUY transaction)
    symbol = f"DEC-{uuid.uuid4().hex[:4].upper()}"
    asset_payload = {
        "asset_type": "STOCK",
        "symbol": symbol,
        "name": "Decision Test Co",
        "current_price_currency": "USD",
        "initial_transaction": {
            "transaction_type": "BUY",
            "quantity": "10",
            "price_per_unit": "100.00",
            "transaction_currency": "USD",
            "transaction_date": "2024-06-01",
            "notes": "Initial position buy thesis",
        },
    }
    resp = await client.post("/api/assets", json=asset_payload, headers=headers)
    assert resp.status_code == 201
    asset_id = resp.json()["data"]["id"]

    # 2. Verify auto-logged POSITION_OPENED decision
    resp = await client.get(f"/api/decisions?asset_id={asset_id}", headers=headers)
    assert resp.status_code == 200
    decisions = resp.json()["data"]["items"]
    assert len(decisions) == 1
    assert decisions[0]["event_type"] == "POSITION_OPENED"
    assert "Opened position" in decisions[0]["title"]
    assert decisions[0]["user_rationale"] == "Initial position buy thesis"

    # 3. Add to position (BUY)
    buy_payload = {
        "transaction_type": "BUY",
        "quantity": "5",
        "price_per_unit": "110.00",
        "transaction_currency": "USD",
        "transaction_date": "2024-06-10",
        "notes": "Adding on breakout",
    }
    resp = await client.post(f"/api/assets/{asset_id}/transactions", json=buy_payload, headers=headers)
    assert resp.status_code == 201

    resp = await client.get(f"/api/decisions?asset_id={asset_id}", headers=headers)
    decisions = resp.json()["data"]["items"]
    assert len(decisions) == 2
    assert decisions[0]["event_type"] == "POSITION_ADDED"
    assert "Added to position" in decisions[0]["title"]

    # 4. Partial sell (POSITION_REDUCED)
    sell_payload = {
        "transaction_type": "SELL",
        "quantity": "4",
        "price_per_unit": "125.00",
        "transaction_currency": "USD",
        "transaction_date": "2024-06-15",
        "notes": "Taking partial profits",
    }
    resp = await client.post(f"/api/assets/{asset_id}/transactions", json=sell_payload, headers=headers)
    assert resp.status_code == 201

    resp = await client.get(f"/api/decisions?asset_id={asset_id}", headers=headers)
    decisions = resp.json()["data"]["items"]
    assert len(decisions) == 3
    assert decisions[0]["event_type"] == "POSITION_REDUCED"
    assert "Reduced position" in decisions[0]["title"]

    # 5. Sell remaining 11 units (POSITION_CLOSED)
    close_payload = {
        "transaction_type": "SELL",
        "quantity": "11",
        "price_per_unit": "130.00",
        "transaction_currency": "USD",
        "transaction_date": "2024-06-20",
        "notes": "Thesis fully realized",
    }
    resp = await client.post(f"/api/assets/{asset_id}/transactions", json=close_payload, headers=headers)
    assert resp.status_code == 201

    resp = await client.get(f"/api/decisions?asset_id={asset_id}", headers=headers)
    decisions = resp.json()["data"]["items"]
    assert len(decisions) == 4
    assert decisions[0]["event_type"] == "POSITION_CLOSED"
    assert "Closed position" in decisions[0]["title"]


@pytest.mark.asyncio
async def test_intelligence_transition_auto_logs_and_suppresses_noise(client: AsyncClient):
    _, headers = await _register_user(client, f"intel_log_{uuid.uuid4().hex[:6]}@example.com")

    # Create asset and retrieve its instrument_id
    symbol = f"INT-{uuid.uuid4().hex[:4].upper()}"
    asset_payload = {
        "asset_type": "STOCK",
        "symbol": symbol,
        "name": "Intel Decision Corp",
        "current_price_currency": "USD",
        "initial_transaction": {
            "transaction_type": "BUY",
            "quantity": "10",
            "price_per_unit": "50.00",
            "transaction_currency": "USD",
            "transaction_date": "2024-06-01",
        },
    }
    resp = await client.post("/api/assets", json=asset_payload, headers=headers)
    asset_id = resp.json()["data"]["id"]
    instrument_id = resp.json()["data"]["instrument_id"]

    # 1. Post a review that establishes recommendation ADD and thesis STRONGER
    review_1 = {
        "protocol": "deep-research",
        "status": "COMPLETED",
        "confidence": "HIGH",
        "human_brief": "Strong competitive moat and margin expansion.",
        "machine_record": {
            "recommendation": "ADD",
            "thesis_status": "STRONGER",
            "valuation_status": "ATTRACTIVE",
        },
        "auto_apply_state": True,
    }
    resp = await client.post(f"/api/instruments/{instrument_id}/reviews", json=review_1, headers=headers)
    assert resp.status_code == 201

    # Check decision log for auto-logged recommendation transition
    resp = await client.get(f"/api/decisions?instrument_id={instrument_id}", headers=headers)
    decisions = resp.json()["data"]["items"]
    # We should have the initial BUY plus the recommendation changed decision
    event_types = [d["event_type"] for d in decisions]
    assert "RECOMMENDATION_CHANGED" in event_types

    count_before = len(decisions)

    # 2. NOISE SUPPRESSION TEST:
    # Post another review with identical recommendation (ADD) and identical thesis (STRONGER).
    # This must NOT create another noisy decision log entry!
    review_duplicate = {
        "protocol": "news-monitoring",
        "status": "COMPLETED",
        "confidence": "HIGH",
        "human_brief": "Routine check, no state changes.",
        "machine_record": {
            "recommendation": "ADD",
            "thesis_status": "STRONGER",
            "valuation_status": "ATTRACTIVE",
        },
        "auto_apply_state": True,
    }
    resp = await client.post(f"/api/instruments/{instrument_id}/reviews", json=review_duplicate, headers=headers)
    assert resp.status_code == 201

    resp = await client.get(f"/api/decisions?instrument_id={instrument_id}", headers=headers)
    count_after = len(resp.json()["data"]["items"])
    # Verified: NO extra decision was added!
    assert count_after == count_before

    # 3. Post a review that transitions recommendation to HOLD
    review_hold = {
        "protocol": "earnings-review",
        "status": "COMPLETED",
        "confidence": "MEDIUM",
        "human_brief": "Valuation reached fair value, changing to HOLD.",
        "machine_record": {
            "recommendation": "HOLD",
            "thesis_status": "UNCHANGED",
            "valuation_status": "FAIR",
        },
        "auto_apply_state": True,
    }
    resp = await client.post(f"/api/instruments/{instrument_id}/reviews", json=review_hold, headers=headers)
    assert resp.status_code == 201

    resp = await client.get(f"/api/decisions?instrument_id={instrument_id}", headers=headers)
    latest_decisions = resp.json()["data"]["items"]
    assert len(latest_decisions) == count_before + 1
    assert latest_decisions[0]["event_type"] == "RECOMMENDATION_CHANGED"
    assert "HOLD" in latest_decisions[0]["title"]
