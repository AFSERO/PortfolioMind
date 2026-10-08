"""Tests for the authentication endpoints (POST /api/auth/*)."""

from datetime import datetime, timedelta, timezone
import asyncio
import os
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_session import RefreshSession
from app.main import app
from app.services import auth as auth_service

# ── Helpers ──────────────────────────────────────────────────────────────────

REGISTER_URL = "/api/auth/register"
LOGIN_URL = "/api/auth/login"
REFRESH_URL = "/api/auth/refresh"
ME_URL = "/api/auth/me"

_USER = {
    "email": "test@example.com",
    "password": "securepassword123",
    "display_name": "Test User",
}


async def _register(client: AsyncClient, **overrides) -> dict:
    payload = {**_USER, **overrides}
    resp = await client.post(REGISTER_URL, json=payload)
    return resp


# ── Registration ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient) -> None:
    resp = await _register(client)

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "success"
    assert "access_token" in body["data"]
    assert body["data"]["user"]["email"] == _USER["email"]
    assert body["data"]["user"]["display_name"] == _USER["display_name"]
    assert body["data"]["user"]["base_currency"] == "TRY"
    # Refresh token should be set as a cookie
    assert "refresh_token" in resp.cookies


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient) -> None:
    await _register(client)
    resp = await _register(client)

    assert resp.status_code == 409
    assert resp.json()["status"] == "error"


# ── Login ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient) -> None:
    await _register(client)

    resp = await client.post(
        LOGIN_URL, json={"email": _USER["email"], "password": _USER["password"]}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert "access_token" in body["data"]
    assert body["data"]["user"]["email"] == _USER["email"]
    assert "refresh_token" in resp.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient) -> None:
    await _register(client)

    resp = await client.post(
        LOGIN_URL, json={"email": _USER["email"], "password": "wrongpassword"}
    )

    assert resp.status_code == 401
    assert resp.json()["status"] == "error"


# ── Refresh ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient) -> None:
    reg_resp = await _register(client)
    refresh_cookie = reg_resp.cookies["refresh_token"]

    client.cookies.set("refresh_token", refresh_cookie)
    resp = await client.post(REFRESH_URL)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert "access_token" in body["data"]
    assert resp.cookies["refresh_token"] != refresh_cookie


@pytest.mark.asyncio
async def test_rotated_refresh_token_cannot_be_reused(client: AsyncClient) -> None:
    reg_resp = await _register(client)
    old_token = reg_resp.cookies["refresh_token"]

    rotated = await client.post(REFRESH_URL)
    assert rotated.status_code == 200

    client.cookies.set("refresh_token", old_token, path="/api/auth")
    replay = await client.post(REFRESH_URL)

    assert replay.status_code == 401
    assert replay.json()["message"] == "Invalid or expired refresh token"

    new_token = rotated.cookies["refresh_token"]
    client.cookies.set("refresh_token", new_token, path="/api/auth")
    family_token = await client.post(REFRESH_URL)
    assert family_token.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_presented_refresh_token(client: AsyncClient) -> None:
    reg_resp = await _register(client)
    token = reg_resp.cookies["refresh_token"]

    logout = await client.post("/api/auth/logout")
    assert logout.status_code == 200

    client.cookies.set("refresh_token", token, path="/api/auth")
    refresh = await client.post(REFRESH_URL)
    assert refresh.status_code == 401


@pytest.mark.asyncio
async def test_access_token_is_rejected_by_refresh_endpoint(client: AsyncClient) -> None:
    reg_resp = await _register(client)
    access_token = reg_resp.json()["data"]["access_token"]

    client.cookies.set("refresh_token", access_token, path="/api/auth")
    resp = await client.post(REFRESH_URL)

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_is_rejected_by_protected_endpoint(
    client: AsyncClient,
) -> None:
    reg_resp = await _register(client)
    refresh_token = reg_resp.cookies["refresh_token"]

    resp = await client.get(
        ME_URL, headers={"Authorization": f"Bearer {refresh_token}"}
    )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_is_hashed_at_rest(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    reg_resp = await _register(client)
    token = reg_resp.cookies["refresh_token"]

    result = await db_session.execute(select(RefreshSession))
    session = result.scalar_one()

    assert session.token_hash != token
    assert token not in session.token_hash
    assert len(session.token_hash) == 64


@pytest.mark.asyncio
async def test_db_expired_refresh_session_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    reg_resp = await _register(client)
    token = reg_resp.cookies["refresh_token"]
    payload = auth_service.decode_token(token)
    assert payload is not None

    session = await db_session.get(RefreshSession, UUID(payload["jti"]))
    assert session is not None
    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()

    resp = await client.post(REFRESH_URL)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_rotation_failure_rolls_back_old_session_state(
    client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    reg_resp = await _register(client)
    token = reg_resp.cookies["refresh_token"]
    payload = auth_service.decode_token(token)
    assert payload is not None

    async def fail_new_session(*args, **kwargs):
        raise RuntimeError("injected refresh-session failure")

    monkeypatch.setattr(auth_service, "_stage_refresh_session", fail_new_session)
    with pytest.raises(RuntimeError, match="injected refresh-session failure"):
        await client.post(REFRESH_URL)

    db_session.expire_all()
    session = await db_session.get(RefreshSession, UUID(payload["jti"]))
    assert session is not None
    assert session.revoked_at is None


@pytest.mark.asyncio
async def test_logout_one_device_does_not_revoke_another_session(
    client: AsyncClient,
) -> None:
    first = await _register(client)
    first_token = first.cookies["refresh_token"]

    second = await client.post(
        LOGIN_URL, json={"email": _USER["email"], "password": _USER["password"]}
    )
    second_token = second.cookies["refresh_token"]
    assert second_token != first_token

    client.cookies.set("refresh_token", first_token, path="/api/auth")
    await client.post("/api/auth/logout")

    client.cookies.set("refresh_token", second_token, path="/api/auth")
    refresh = await client.post(REFRESH_URL)
    assert refresh.status_code == 200


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL", "").startswith("postgresql"),
    reason="SELECT FOR UPDATE concurrency semantics require PostgreSQL",
)
async def test_concurrent_refresh_allows_one_rotation_and_revokes_family_replay(
    client: AsyncClient,
) -> None:
    registered = await _register(client)
    old_token = registered.cookies["refresh_token"]
    transport = ASGITransport(app=app)

    async with (
        AsyncClient(transport=transport, base_url="http://test") as first,
        AsyncClient(transport=transport, base_url="http://test") as second,
    ):
        first.cookies.set("refresh_token", old_token, path="/api/auth")
        second.cookies.set("refresh_token", old_token, path="/api/auth")
        responses = await asyncio.gather(
            first.post(REFRESH_URL), second.post(REFRESH_URL)
        )

    assert sorted(response.status_code for response in responses) == [200, 401]
    rotated = next(response for response in responses if response.status_code == 200)
    rotated_token = rotated.cookies["refresh_token"]

    client.cookies.set("refresh_token", rotated_token, path="/api/auth")
    assert (await client.post(REFRESH_URL)).status_code == 401


# ── Protected route (GET /me) ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_me_with_valid_token(client: AsyncClient) -> None:
    reg = await _register(client)
    token = reg.json()["data"]["access_token"]

    resp = await client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["data"]["email"] == _USER["email"]


@pytest.mark.asyncio
async def test_me_without_token(client: AsyncClient) -> None:
    resp = await client.get(ME_URL)

    assert resp.status_code in (401, 403)
    assert resp.json()["status"] == "error"
