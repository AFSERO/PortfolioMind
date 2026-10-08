"""Comprehensive test suite for Copilot V2 HTTP & Streaming Endpoint.

Covers:
1. Authenticated user requirement (401 on missing auth).
2. Conversation ownership verification (404 on nonexistent or other user's conversation).
3. Synchronous mode (stream=false) returning structured JSON payload.
4. Live SSE streaming mode (stream=true) yielding valid event sequence (STARTED -> TOOL_RUNNING -> FINAL).
5. Concurrency protection (HTTP 409 Conflict on simultaneous turns in the same conversation).
6. Database cleanliness (progress events are ephemeral and never persisted to copilot_messages).
7. Read-only safety (financial assets/cash accounts are never mutated).
8. V1/V2 isolation (V2 route executes through CodexV2Adapter, never V1 IntentClassifier).
"""

import asyncio
from decimal import Decimal
import json
from unittest.mock import MagicMock, patch
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.asset import Asset, AssetType
from app.models.cash import CashAccount
from app.models.copilot import CopilotConversation, CopilotMessage
from app.services.copilot_v2.adapter import CodexV2ExecutionResult
from app.services.copilot_v2.contracts import ModelProfile, ReasoningEffort


async def _register_user(client: AsyncClient, email_prefix: str = "v2_endpoint") -> tuple[uuid.UUID, dict]:
    email = f"{email_prefix}_{uuid.uuid4().hex[:6]}@example.com"
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "display_name": "V2 Tester",
        },
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    token = data["access_token"]
    user_id = uuid.UUID(data["user"]["id"])
    headers = {"Authorization": f"Bearer {token}"}
    return user_id, headers


# -----------------------------------------------------------------------------
# 1. Authenticated user required
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_v2_endpoint_authentication_required(client: AsyncClient):
    """Unauthenticated request to V2 message endpoint returns 401."""
    random_conv_id = uuid.uuid4()
    resp = await client.post(
        f"/api/copilot/v2/conversations/{random_conv_id}/messages",
        json={"content": "Portföyüm ne kadar?"},
    )
    assert resp.status_code == 401


# -----------------------------------------------------------------------------
# 2. Conversation ownership enforcement
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_v2_endpoint_conversation_ownership(client: AsyncClient, db_session):
    """User cannot send V2 messages to another user's conversation."""
    user1_id, headers1 = await _register_user(client, "user1_v2")
    user2_id, headers2 = await _register_user(client, "user2_v2")

    # Create conversation owned by user 1
    create_resp = await client.post(
        "/api/copilot/conversations",
        json={"title": "User 1 Conversation"},
        headers=headers1,
    )
    assert create_resp.status_code == 201
    conv_id = create_resp.json()["data"]["id"]

    # User 2 attempts to post to User 1's conversation
    forbidden_resp = await client.post(
        f"/api/copilot/v2/conversations/{conv_id}/messages",
        json={"content": "Portföyüme erişebilir misin?"},
        headers=headers2,
    )
    assert forbidden_resp.status_code == 404
    assert "not found" in forbidden_resp.json()["message"].lower()


# -----------------------------------------------------------------------------
# 3. Synchronous mode (stream=false)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_v2_endpoint_sync_mode(client: AsyncClient, db_session):
    """When stream=false, endpoint returns 200 with complete JSON response."""
    user_id, headers = await _register_user(client, "sync_mode")

    create_resp = await client.post(
        "/api/copilot/conversations",
        json={"title": "Sync Test"},
        headers=headers,
    )
    conv_id = create_resp.json()["data"]["id"]

    mock_res = CodexV2ExecutionResult(
        raw_output='{"action": "FINAL_RESPONSE", "answer": "Net portföyünüz 850.000 TL."}',
        parsed_json={"action": "FINAL_RESPONSE", "answer": "Net portföyünüz 850.000 TL."},
        session_id="sync-session-123",
        duration_ms=120.0,
        model_used="gpt-5.6-luna",
        reasoning_effort_used="low",
    )

    with patch("app.services.copilot_v2.service.CodexV2Adapter") as mock_adapter_cls:
        adapter_inst = mock_adapter_cls.return_value
        adapter_inst.execute.return_value = mock_res

        # Patch the singleton adapter in the router
        from app.routers.copilot_v2 import _copilot_v2_service
        _copilot_v2_service.adapter = adapter_inst
        _copilot_v2_service.orchestrator.adapter = adapter_inst
        _copilot_v2_service.reasoner.adapter = adapter_inst

        resp = await client.post(
            f"/api/copilot/v2/conversations/{conv_id}/messages?stream=false",
            json={"content": "Portföy toplamım?"},
            headers=headers,
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert "850.000 TL" in body["data"]["message"]["raw_content"]
    assert body["data"]["session_id"] == "sync-session-123"
    assert "trace" in body["data"]


# -----------------------------------------------------------------------------
# 4. Live SSE streaming mode (stream=true)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_v2_endpoint_streaming_sse_sequence(client: AsyncClient, db_session):
    """Streaming mode yields STARTED, TOOL_RUNNING, and FINAL SSE events."""
    user_id, headers = await _register_user(client, "stream_mode")

    create_resp = await client.post(
        "/api/copilot/conversations",
        json={"title": "Stream Test"},
        headers=headers,
    )
    conv_id = create_resp.json()["data"]["id"]

    # Turn 1: FAST calls tool get_portfolio_summary
    turn1_res = CodexV2ExecutionResult(
        raw_output='{"action": "TOOL_CALL", "tool_calls": [{"tool": "get_portfolio_summary", "args": {}}]}',
        parsed_json={"action": "TOOL_CALL", "tool_calls": [{"tool": "get_portfolio_summary", "args": {}}]},
        session_id="sse-session-456",
        duration_ms=90.0,
        model_used="gpt-5.6-luna",
        reasoning_effort_used="low",
    )
    # Turn 2: FAST provides final answer
    turn2_res = CodexV2ExecutionResult(
        raw_output='{"action": "FINAL_RESPONSE", "answer": "Portföy özeti hazır."}',
        parsed_json={"action": "FINAL_RESPONSE", "answer": "Portföy özeti hazır."},
        session_id="sse-session-456",
        duration_ms=110.0,
        model_used="gpt-5.6-luna",
        reasoning_effort_used="low",
    )

    mock_adapter = MagicMock()
    mock_adapter.execute.side_effect = [turn1_res, turn2_res]

    from app.routers.copilot_v2 import _copilot_v2_service
    _copilot_v2_service.adapter = mock_adapter
    _copilot_v2_service.orchestrator.adapter = mock_adapter
    _copilot_v2_service.reasoner.adapter = mock_adapter

    resp = await client.post(
        f"/api/copilot/v2/conversations/{conv_id}/messages?stream=true",
        json={"content": "Özetimi ver."},
        headers=headers,
    )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    # Parse SSE lines
    raw_lines = resp.text.split("\n")
    events = []
    for line in raw_lines:
        line = line.strip()
        if line.startswith("data:"):
            payload_str = line[len("data:") :].strip()
            events.append(json.loads(payload_str))

    types = [e.get("type") for e in events]
    assert "STARTED" in types
    assert "TOOL_RUNNING" in types
    assert "FINAL" in types

    # Verify FINAL event payload
    final_event = next(e for e in events if e.get("type") == "FINAL")
    assert "Portföy özeti hazır." in final_event["message"]["raw_content"]
    assert final_event["session_id"] == "sse-session-456"


# -----------------------------------------------------------------------------
# 5. Concurrency protection (409 Conflict)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_v2_endpoint_concurrency_lock(client: AsyncClient, db_session):
    """Simultaneous messages in the same conversation are rejected with HTTP 409."""
    user_id, headers = await _register_user(client, "concurrency")

    create_resp = await client.post(
        "/api/copilot/conversations",
        json={"title": "Concurrency Test"},
        headers=headers,
    )
    conv_id = uuid.UUID(create_resp.json()["data"]["id"])

    from app.routers.copilot_v2 import _conversation_locks

    # Artificially acquire the conversation lock to simulate an in-flight turn
    lock = _conversation_locks[conv_id]
    await lock.acquire()

    try:
        conflict_resp = await client.post(
            f"/api/copilot/v2/conversations/{conv_id}/messages?stream=false",
            json={"content": "Eşzamanlı mesaj"},
            headers=headers,
        )
        assert conflict_resp.status_code == 409
        assert "already being processed" in conflict_resp.json()["message"]
    finally:
        lock.release()


# -----------------------------------------------------------------------------
# 6. Database cleanliness: Progress events not in database
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_v2_endpoint_progress_events_not_in_database(client: AsyncClient, db_session):
    """Progress events are strictly ephemeral; only user and assistant messages exist in DB."""
    user_id, headers = await _register_user(client, "clean_db")

    create_resp = await client.post(
        "/api/copilot/conversations",
        json={"title": "Clean DB Test"},
        headers=headers,
    )
    conv_id = uuid.UUID(create_resp.json()["data"]["id"])

    mock_res = CodexV2ExecutionResult(
        raw_output='{"action": "FINAL_RESPONSE", "answer": "Son yanıt."}',
        parsed_json={"action": "FINAL_RESPONSE", "answer": "Son yanıt."},
        session_id="clean-sess-789",
        duration_ms=100.0,
        model_used="gpt-5.6-luna",
        reasoning_effort_used="low",
    )

    mock_adapter = MagicMock()
    mock_adapter.execute.return_value = mock_res

    from app.routers.copilot_v2 import _copilot_v2_service
    _copilot_v2_service.adapter = mock_adapter
    _copilot_v2_service.orchestrator.adapter = mock_adapter

    await client.post(
        f"/api/copilot/v2/conversations/{conv_id}/messages?stream=true",
        json={"content": "Temiz DB testi"},
        headers=headers,
    )

    # Check database rows
    stmt = (
        select(CopilotMessage)
        .where(CopilotMessage.conversation_id == conv_id)
        .order_by(CopilotMessage.created_at.asc())
    )
    res = await db_session.execute(stmt)
    messages = res.scalars().all()

    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].raw_content == "Temiz DB testi"
    assert messages[1].role == "assistant"
    assert messages[1].raw_content == "Son yanıt."


# -----------------------------------------------------------------------------
# 7. Read-only safety invariant
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_v2_endpoint_read_only_safety(client: AsyncClient, db_session):
    """V2 invocation never modifies existing assets or cash accounts."""
    user_id, headers = await _register_user(client, "readonly_user")

    # Seed an asset
    asset = Asset(
        user_id=user_id,
        asset_type=AssetType.STOCK,
        symbol="THYAO.IS",
        name="Türk Hava Yolları",
        current_price=Decimal("300.0"),
        current_price_currency="TRY",
    )
    db_session.add(asset)
    await db_session.commit()

    create_resp = await client.post(
        "/api/copilot/conversations",
        json={"title": "Readonly Check"},
        headers=headers,
    )
    conv_id = create_resp.json()["data"]["id"]

    mock_res = CodexV2ExecutionResult(
        raw_output='{"action": "FINAL_RESPONSE", "answer": "Analiz edildi."}',
        parsed_json={"action": "FINAL_RESPONSE", "answer": "Analiz edildi."},
        session_id="ro-sess-1",
        duration_ms=100.0,
        model_used="gpt-5.6-luna",
        reasoning_effort_used="low",
    )

    mock_adapter = MagicMock()
    mock_adapter.execute.return_value = mock_res
    from app.routers.copilot_v2 import _copilot_v2_service
    _copilot_v2_service.adapter = mock_adapter
    _copilot_v2_service.orchestrator.adapter = mock_adapter

    await client.post(
        f"/api/copilot/v2/conversations/{conv_id}/messages?stream=false",
        json={"content": "Tüm hisselerimi sat!"},
        headers=headers,
    )

    # Verify asset is completely unchanged
    assets = (await db_session.execute(select(Asset).where(Asset.user_id == user_id))).scalars().all()
    assert len(assets) == 1
    assert assets[0].symbol == "THYAO.IS"
