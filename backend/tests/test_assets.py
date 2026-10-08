"""Tests for asset CRUD endpoints (POST/GET/PUT/DELETE /api/assets/*)."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

ASSETS_URL = "/api/assets"

_STOCK = {
    "asset_type": "STOCK",
    "symbol": "THYAO.IS",
    "name": "Türk Hava Yolları",
    "initial_transaction": {
        "transaction_type": "BUY",
        "quantity": "100",
        "price_per_unit": "285.50",
        "transaction_currency": "TRY",
        "transaction_date": "2024-06-15",
    },
}

_CRYPTO = {
    "asset_type": "CRYPTO",
    "symbol": "BTC",
    "name": "Bitcoin",
    "initial_transaction": {
        "transaction_type": "BUY",
        "quantity": "0.5",
        "price_per_unit": "62000.00",
        "transaction_currency": "USD",
        "transaction_date": "2024-01-10",
    },
}

_REAL_ESTATE = {
    "asset_type": "REAL_ESTATE",
    "name": "Ev - Kadıköy",
    "current_price": "8500000",
    "current_price_currency": "TRY",
    "is_manual_price": True,
    "initial_transaction": {
        "transaction_type": "BUY",
        "quantity": "1",
        "price_per_unit": "5500000",
        "transaction_currency": "TRY",
        "transaction_date": "2022-03-01",
    },
}


async def _create(client: AsyncClient, payload: dict = None) -> dict:
    resp = await client.post(ASSETS_URL, json=payload or _STOCK)
    return resp


async def _register_second_user(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/auth/register",
        json={"email": "other@example.com", "password": "otherpassword123"},
    )
    return resp.json()["data"]["access_token"]


# ── Create ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_stock(authed_client: AsyncClient) -> None:
    resp = await _create(authed_client, _STOCK)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "success"
    data = body["data"]
    assert data["asset_type"] == "STOCK"
    assert data["symbol"] == "THYAO.IS"
    assert data["total_quantity"] == 100.0
    assert data["avg_cost"] == 285.5
    assert data["avg_cost_currency"] == "TRY"
    assert data["id"] is not None


@pytest.mark.asyncio
async def test_create_crypto(authed_client: AsyncClient) -> None:
    resp = await _create(authed_client, _CRYPTO)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["asset_type"] == "CRYPTO"
    assert data["symbol"] == "BTC"
    assert data["avg_cost_currency"] == "USD"


@pytest.mark.asyncio
async def test_create_real_estate_manual_price(authed_client: AsyncClient) -> None:
    resp = await _create(authed_client, _REAL_ESTATE)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["asset_type"] == "REAL_ESTATE"
    assert data["is_manual_price"] is True
    assert data["current_price"] == 8500000.0
    assert data["symbol"] is None
    assert data["total_quantity"] == 1.0


@pytest.mark.asyncio
async def test_create_asset_without_initial_transaction(
    authed_client: AsyncClient,
) -> None:
    """An asset can be created with no initial transaction (zero-quantity position)."""
    resp = await _create(
        authed_client,
        {"asset_type": "CUSTOM", "name": "Placeholder"},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["total_quantity"] == 0.0
    assert data["avg_cost"] is None
    assert data["total_cost"] == 0.0


@pytest.mark.asyncio
async def test_create_asset_unauthenticated(client: AsyncClient) -> None:
    resp = await client.post(ASSETS_URL, json=_STOCK)
    assert resp.status_code in (401, 403)


# ── List ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_assets(authed_client: AsyncClient) -> None:
    await _create(authed_client, _STOCK)
    await _create(authed_client, _CRYPTO)

    resp = await authed_client.get(ASSETS_URL)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 2


@pytest.mark.asyncio
async def test_list_assets_filter_by_type(authed_client: AsyncClient) -> None:
    await _create(authed_client, _STOCK)
    await _create(authed_client, _CRYPTO)

    resp = await authed_client.get(ASSETS_URL, params={"asset_type": "CRYPTO"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["asset_type"] == "CRYPTO"


@pytest.mark.asyncio
async def test_list_assets_empty(authed_client: AsyncClient) -> None:
    resp = await authed_client.get(ASSETS_URL)
    assert resp.status_code == 200
    assert resp.json()["data"] == []


# ── Get single ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_asset(authed_client: AsyncClient) -> None:
    create_resp = await _create(authed_client, _STOCK)
    asset_id = create_resp.json()["data"]["id"]

    resp = await authed_client.get(f"{ASSETS_URL}/{asset_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == asset_id
    assert resp.json()["data"]["name"] == _STOCK["name"]


@pytest.mark.asyncio
async def test_get_asset_not_found(authed_client: AsyncClient) -> None:
    fake_id = uuid.uuid4()
    resp = await authed_client.get(f"{ASSETS_URL}/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_asset_wrong_owner(authed_client: AsyncClient, client: AsyncClient) -> None:
    create_resp = await _create(authed_client, _STOCK)
    asset_id = create_resp.json()["data"]["id"]

    other_token = await _register_second_user(client)
    resp = await client.get(
        f"{ASSETS_URL}/{asset_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 404


# ── Update ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_asset(authed_client: AsyncClient) -> None:
    create_resp = await _create(authed_client, _STOCK)
    asset_id = create_resp.json()["data"]["id"]

    resp = await authed_client.put(
        f"{ASSETS_URL}/{asset_id}",
        json={"name": "THY Updated"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "THY Updated"
    assert data["symbol"] == "THYAO.IS"


@pytest.mark.asyncio
async def test_update_asset_not_found(authed_client: AsyncClient) -> None:
    fake_id = uuid.uuid4()
    resp = await authed_client.put(f"{ASSETS_URL}/{fake_id}", json={"name": "nope"})
    assert resp.status_code == 404


# ── Delete ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_asset(authed_client: AsyncClient) -> None:
    create_resp = await _create(authed_client, _STOCK)
    asset_id = create_resp.json()["data"]["id"]

    resp = await authed_client.delete(f"{ASSETS_URL}/{asset_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["message"] == "Asset deleted"

    resp = await authed_client.get(f"{ASSETS_URL}/{asset_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_asset_wrong_owner(
    authed_client: AsyncClient, client: AsyncClient
) -> None:
    create_resp = await _create(authed_client, _STOCK)
    asset_id = create_resp.json()["data"]["id"]

    other_token = await _register_second_user(client)
    resp = await client.delete(
        f"{ASSETS_URL}/{asset_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_asset_cascades_transactions(authed_client: AsyncClient) -> None:
    create_resp = await _create(authed_client, _STOCK)
    asset_id = create_resp.json()["data"]["id"]

    # Asset has 1 initial transaction
    tx_list = await authed_client.get(f"{ASSETS_URL}/{asset_id}/transactions")
    assert len(tx_list.json()["data"]) == 1

    await authed_client.delete(f"{ASSETS_URL}/{asset_id}")

    # 404 on the asset and its transactions
    tx_list = await authed_client.get(f"{ASSETS_URL}/{asset_id}/transactions")
    assert tx_list.status_code == 404


# ── Auto price fetch on create ───────────────────────────────────────────────


@pytest.mark.asyncio
@patch("app.services.price.fetch_price", new_callable=AsyncMock)
async def test_create_stock_auto_fetches_price(
    mock_fetch, authed_client: AsyncClient
) -> None:
    mock_fetch.return_value = (Decimal("310.50"), "TRY")

    resp = await _create(authed_client, _STOCK)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["current_price"] == 310.50
    assert data["current_price_currency"] == "TRY"
    assert data["is_manual_price"] is False
    assert "warning" not in resp.json()


@pytest.mark.asyncio
async def test_create_stock_fetch_failure_returns_warning(
    authed_client: AsyncClient,
) -> None:
    resp = await _create(authed_client, _STOCK)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "success"
    assert "warning" in body
    assert body["data"]["current_price"] is None


@pytest.mark.asyncio
async def test_create_manual_asset_no_fetch(authed_client: AsyncClient) -> None:
    resp = await _create(authed_client, _REAL_ESTATE)
    assert resp.status_code == 201
    body = resp.json()
    assert "warning" not in body
    assert body["data"]["current_price"] == 8500000.0
    assert body["data"]["is_manual_price"] is True


# ── Auto price fetch on update ────────────────────────────────────────────────


@pytest.mark.asyncio
@patch("app.services.price.fetch_price", new_callable=AsyncMock)
async def test_update_symbol_triggers_price_fetch(
    mock_fetch, authed_client: AsyncClient
) -> None:
    mock_fetch.return_value = (Decimal("150.00"), "TRY")

    create_resp = await _create(authed_client, _STOCK)
    asset_id = create_resp.json()["data"]["id"]

    mock_fetch.return_value = (Decimal("999.99"), "TRY")
    resp = await authed_client.put(
        f"{ASSETS_URL}/{asset_id}",
        json={"symbol": "GARAN.IS"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["symbol"] == "GARAN.IS"
    assert data["current_price"] == 999.99
    assert "warning" not in resp.json()


@pytest.mark.asyncio
@patch("app.services.price.fetch_price", new_callable=AsyncMock)
async def test_update_without_symbol_change_skips_fetch(
    mock_fetch, authed_client: AsyncClient
) -> None:
    mock_fetch.return_value = (Decimal("310.50"), "TRY")

    create_resp = await _create(authed_client, _STOCK)
    asset_id = create_resp.json()["data"]["id"]
    initial_call_count = mock_fetch.call_count

    await authed_client.put(
        f"{ASSETS_URL}/{asset_id}",
        json={"name": "Updated Name"},
    )
    assert mock_fetch.call_count == initial_call_count


@pytest.mark.asyncio
async def test_update_symbol_fetch_failure_returns_warning(
    authed_client: AsyncClient,
) -> None:
    create_resp = await _create(authed_client, _STOCK)
    asset_id = create_resp.json()["data"]["id"]

    resp = await authed_client.put(
        f"{ASSETS_URL}/{asset_id}",
        json={"symbol": "GARAN.IS"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["symbol"] == "GARAN.IS"
    assert "warning" in body


@pytest.mark.asyncio
async def test_update_price(authed_client: AsyncClient) -> None:
    create_resp = await _create(authed_client, _REAL_ESTATE)
    asset_id = create_resp.json()["data"]["id"]

    resp = await authed_client.post(
        f"{ASSETS_URL}/{asset_id}/update-price",
        json={"current_price": "9000000", "current_price_currency": "TRY"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["current_price"] == 9000000.0
    assert data["is_manual_price"] is True
