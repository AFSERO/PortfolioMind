"""Regression tests for JWT and the explicitly scoped Finance credential."""
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt
from pydantic import SecretStr
from sqlalchemy import select

from app.config import settings
from app.models.user import User


async def configure_bridge(client, monkeypatch):
    for email in ("first@example.com", "bridge@example.com"):
        response = await client.post("/api/auth/register", json={
            "email": email, "password": "synthetic-password-123", "display_name": "Test"
        })
        assert response.status_code == 201
        owner_id = uuid.UUID(response.json()["data"]["user"]["id"])
    token = secrets.token_urlsafe(32)
    monkeypatch.setattr(settings, "INTEGRATION_TOKEN", SecretStr(token))
    monkeypatch.setitem(settings.__dict__, "INTEGRATION_USER_ID", owner_id)
    return owner_id, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/api/auth/me", "/api/assets", "/api/copilot/conversations"])
async def test_bridge_cannot_impersonate_personal_user(client, monkeypatch, path):
    _, headers = await configure_bridge(client, monkeypatch)
    response = await client.get(path, headers=headers)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_bridge_uses_explicit_owner_and_preserves_protocol(client, db_session, monkeypatch):
    owner_id, headers = await configure_bridge(client, monkeypatch)
    from app.middleware.auth import get_bridge_user
    from fastapi.security import HTTPAuthorizationCredentials
    user = await get_bridge_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=headers["Authorization"][7:]), db_session)
    assert user.id == owner_id
    assert (await client.get("/api/instruments", headers=headers)).status_code == 200
    # Canonical instrument creation and on-demand research remain JWT-only.
    assert (await client.post("/api/instruments", json={"name":"Synthetic", "asset_type":"STOCK", "symbol":"SYN", "currency":"USD"}, headers=headers)).status_code == 401


@pytest.mark.asyncio
async def test_bridge_missing_owner_never_falls_back(client, db_session, monkeypatch):
    owner_id, headers = await configure_bridge(client, monkeypatch)
    user = (await db_session.execute(select(User).where(User.id == owner_id))).scalar_one()
    await db_session.delete(user)
    await db_session.commit()
    assert (await client.get("/api/instruments", headers=headers)).status_code == 401


@pytest.mark.asyncio
async def test_outbound_token_alias_is_not_inbound_auth(client, monkeypatch):
    _, headers = await configure_bridge(client, monkeypatch)
    token = headers["Authorization"][7:]
    monkeypatch.setattr(settings, "INTEGRATION_TOKEN", None)
    monkeypatch.setattr(settings, "PORTFOLIOMIND_API_TOKEN", SecretStr(token))
    assert (await client.get("/api/instruments", headers=headers)).status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("subject", ["not-a-uuid", 42, None])
async def test_malformed_jwt_subject_returns_unauthorized(client, subject):
    token = jwt.encode({"sub":subject, "type":"access", "exp":datetime.now(timezone.utc)+timedelta(minutes=5)}, settings.jwt_secret, algorithm="HS256")
    assert (await client.get("/api/auth/me", headers={"Authorization":f"Bearer {token}"})).status_code == 401


@pytest.mark.asyncio
async def test_jwt_without_expiry_is_rejected(client):
    response = await client.post("/api/auth/register", json={"email":"expiry@example.com", "password":"synthetic-password-123"})
    token = jwt.encode({"sub":response.json()["data"]["user"]["id"], "type":"access"}, settings.jwt_secret, algorithm="HS256")
    assert (await client.get("/api/auth/me", headers={"Authorization":f"Bearer {token}"})).status_code == 401


@pytest.mark.asyncio
async def test_unknown_bridge_credential_is_rejected(client, monkeypatch):
    await configure_bridge(client, monkeypatch)
    response = await client.get("/api/instruments", headers={"Authorization":f"Bearer {secrets.token_urlsafe(32)}"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_rotated_jwt_key_revokes_both_token_types(client, monkeypatch):
    registration = await client.post("/api/auth/register", json={"email":"rotation@example.com", "password":"synthetic-password-123"})
    old_access = registration.json()["data"]["access_token"]
    monkeypatch.setattr(settings, "SECRET_KEY", SecretStr(secrets.token_urlsafe(32)))
    assert (await client.get("/api/auth/me", headers={"Authorization":f"Bearer {old_access}"})).status_code == 401
    assert (await client.post("/api/auth/refresh")).status_code == 401
    login = await client.post("/api/auth/login", json={"email":"rotation@example.com", "password":"synthetic-password-123"})
    assert login.status_code == 200
    assert (await client.get("/api/auth/me", headers={"Authorization":f"Bearer {login.json()['data']['access_token']}"})).status_code == 200
