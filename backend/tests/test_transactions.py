"""Tests for the transaction model, service, and endpoints."""

import pytest
from httpx import AsyncClient

ASSETS_URL = "/api/assets"
TXN_URL = "/api/transactions"


_BASE_ASSET = {
    "asset_type": "STOCK",
    "symbol": "AAPL",
    "name": "Apple",
    "initial_transaction": {
        "transaction_type": "BUY",
        "quantity": "10",
        "price_per_unit": "100",
        "transaction_currency": "USD",
        "transaction_date": "2024-01-01",
    },
}


async def _new_asset(client: AsyncClient, payload: dict = None) -> str:
    resp = await client.post(ASSETS_URL, json=payload or _BASE_ASSET)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _add_tx(client: AsyncClient, asset_id: str, body: dict) -> dict:
    return await client.post(f"{ASSETS_URL}/{asset_id}/transactions", json=body)


# ── Stats over transactions ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_multiple_buys_weighted_avg(authed_client: AsyncClient) -> None:
    """BUY 10@100 + BUY 5@200 → qty=15, avg=(1000+1000)/15=133.33..."""
    asset_id = await _new_asset(authed_client)
    resp = await _add_tx(
        authed_client,
        asset_id,
        {
            "transaction_type": "BUY",
            "quantity": "5",
            "price_per_unit": "200",
            "transaction_currency": "USD",
            "transaction_date": "2024-02-01",
        },
    )
    assert resp.status_code == 201

    asset = (await authed_client.get(f"{ASSETS_URL}/{asset_id}")).json()["data"]
    assert asset["total_quantity"] == 15.0
    assert abs(asset["avg_cost"] - (2000 / 15)) < 1e-6
    assert abs(asset["total_cost"] - 2000) < 1e-6


@pytest.mark.asyncio
async def test_buy_then_sell_realized_pl(authed_client: AsyncClient) -> None:
    """BUY 10@100, SELL 3@150 → qty=7, avg=100, cost=700, realized=150."""
    asset_id = await _new_asset(authed_client)
    resp = await _add_tx(
        authed_client,
        asset_id,
        {
            "transaction_type": "SELL",
            "quantity": "3",
            "price_per_unit": "150",
            "transaction_currency": "USD",
            "transaction_date": "2024-03-01",
        },
    )
    assert resp.status_code == 201

    asset = (await authed_client.get(f"{ASSETS_URL}/{asset_id}")).json()["data"]
    assert asset["total_quantity"] == 7.0
    assert asset["avg_cost"] == 100.0
    assert asset["total_cost"] == 700.0
    assert asset["realized_pl"] == 150.0


@pytest.mark.asyncio
async def test_sell_more_than_held_rejected(authed_client: AsyncClient) -> None:
    asset_id = await _new_asset(authed_client)
    resp = await _add_tx(
        authed_client,
        asset_id,
        {
            "transaction_type": "SELL",
            "quantity": "11",
            "price_per_unit": "100",
            "transaction_currency": "USD",
            "transaction_date": "2024-03-01",
        },
    )
    assert resp.status_code == 400


# ── Input modes ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dollar_mode_input(authed_client: AsyncClient) -> None:
    asset_id = await _new_asset(authed_client)
    resp = await _add_tx(
        authed_client,
        asset_id,
        {
            "transaction_type": "BUY",
            "total_amount": "1000",
            "price_per_unit": "100",
            "transaction_currency": "USD",
            "transaction_date": "2024-02-01",
        },
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["quantity"] == 10.0
    assert data["total_amount"] == 1000.0


@pytest.mark.asyncio
async def test_quantity_mode_input(authed_client: AsyncClient) -> None:
    asset_id = await _new_asset(authed_client)
    resp = await _add_tx(
        authed_client,
        asset_id,
        {
            "transaction_type": "BUY",
            "quantity": "10",
            "price_per_unit": "100",
            "transaction_currency": "USD",
            "transaction_date": "2024-02-01",
        },
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["quantity"] == 10.0
    assert data["total_amount"] == 1000.0


@pytest.mark.asyncio
async def test_both_or_neither_amount_rejected(authed_client: AsyncClient) -> None:
    asset_id = await _new_asset(authed_client)

    # Neither
    resp = await _add_tx(
        authed_client,
        asset_id,
        {
            "transaction_type": "BUY",
            "price_per_unit": "100",
            "transaction_currency": "USD",
            "transaction_date": "2024-02-01",
        },
    )
    assert resp.status_code == 422

    # Both
    resp = await _add_tx(
        authed_client,
        asset_id,
        {
            "transaction_type": "BUY",
            "quantity": "10",
            "total_amount": "1000",
            "price_per_unit": "100",
            "transaction_currency": "USD",
            "transaction_date": "2024-02-01",
        },
    )
    assert resp.status_code == 422


# ── Mixed currency ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mixed_currency_first_wins(authed_client: AsyncClient) -> None:
    """First BUY currency wins; has_mixed_currencies flag flips to True."""
    asset_id = await _new_asset(
        authed_client,
        {
            "asset_type": "STOCK",
            "symbol": "AAPL",
            "name": "Apple",
            "initial_transaction": {
                "transaction_type": "BUY",
                "quantity": "5",
                "price_per_unit": "100",
                "transaction_currency": "TRY",
                "transaction_date": "2024-01-01",
            },
        },
    )
    resp = await _add_tx(
        authed_client,
        asset_id,
        {
            "transaction_type": "BUY",
            "quantity": "5",
            "price_per_unit": "200",
            "transaction_currency": "USD",
            "transaction_date": "2024-02-01",
        },
    )
    assert resp.status_code == 201

    asset = (await authed_client.get(f"{ASSETS_URL}/{asset_id}")).json()["data"]
    assert asset["avg_cost_currency"] == "TRY"
    assert asset["avg_cost"] == 150.0  # (500 + 1000) / 10
    assert asset["has_mixed_currencies"] is True


# ── List transactions ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_transactions_order(authed_client: AsyncClient) -> None:
    asset_id = await _new_asset(authed_client)
    await _add_tx(
        authed_client,
        asset_id,
        {
            "transaction_type": "BUY",
            "quantity": "1",
            "price_per_unit": "100",
            "transaction_currency": "USD",
            "transaction_date": "2024-05-01",
        },
    )
    resp = await authed_client.get(f"{ASSETS_URL}/{asset_id}/transactions")
    assert resp.status_code == 200
    dates = [t["transaction_date"] for t in resp.json()["data"]]
    assert dates == sorted(dates)


# ── Update / delete ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_transaction_into_negative_rejected(
    authed_client: AsyncClient,
) -> None:
    asset_id = await _new_asset(authed_client)
    sell = await _add_tx(
        authed_client,
        asset_id,
        {
            "transaction_type": "SELL",
            "quantity": "3",
            "price_per_unit": "150",
            "transaction_currency": "USD",
            "transaction_date": "2024-03-01",
        },
    )
    tx_id = sell.json()["data"]["id"]

    # Bump sell to 11 → would exceed the 10 held
    resp = await authed_client.put(f"{TXN_URL}/{tx_id}", json={"quantity": "11"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_delete_transaction_into_negative_rejected(
    authed_client: AsyncClient,
) -> None:
    """BUY 10, BUY 5, SELL 12 — deleting the first BUY would leave -2."""
    asset_id = await _new_asset(authed_client)
    resp = await authed_client.get(f"{ASSETS_URL}/{asset_id}/transactions")
    first_buy_id = resp.json()["data"][0]["id"]

    await _add_tx(
        authed_client,
        asset_id,
        {
            "transaction_type": "BUY",
            "quantity": "5",
            "price_per_unit": "110",
            "transaction_currency": "USD",
            "transaction_date": "2024-02-01",
        },
    )
    await _add_tx(
        authed_client,
        asset_id,
        {
            "transaction_type": "SELL",
            "quantity": "12",
            "price_per_unit": "200",
            "transaction_currency": "USD",
            "transaction_date": "2024-03-01",
        },
    )

    resp = await authed_client.delete(f"{TXN_URL}/{first_buy_id}")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_update_transaction_ownership(
    authed_client: AsyncClient, client: AsyncClient
) -> None:
    asset_id = await _new_asset(authed_client)
    tx_list = await authed_client.get(f"{ASSETS_URL}/{asset_id}/transactions")
    tx_id = tx_list.json()["data"][0]["id"]

    # Register second user
    resp = await client.post(
        "/api/auth/register",
        json={"email": "other@example.com", "password": "otherpassword123"},
    )
    other_token = resp.json()["data"]["access_token"]

    resp = await client.put(
        f"{TXN_URL}/{tx_id}",
        json={"notes": "hijack"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_transaction_success(authed_client: AsyncClient) -> None:
    asset_id = await _new_asset(authed_client)
    tx_list = await authed_client.get(f"{ASSETS_URL}/{asset_id}/transactions")
    tx_id = tx_list.json()["data"][0]["id"]

    resp = await authed_client.delete(f"{TXN_URL}/{tx_id}")
    assert resp.status_code == 200

    asset = (await authed_client.get(f"{ASSETS_URL}/{asset_id}")).json()["data"]
    assert asset["total_quantity"] == 0.0


# ── Regression: datetime vs date sort bug ────────────────────────────────────


@pytest.mark.asyncio
async def test_sell_after_buy_no_datetime_error(authed_client: AsyncClient) -> None:
    """BUY 10 then immediately SELL 3 must not raise TypeError from the sort.

    Before the fix, the unsaved Transaction had created_at=None so the sort
    key mixed datetime.date and datetime.datetime, causing:
      TypeError: can't compare datetime.datetime to datetime.date
    """
    asset_id = await _new_asset(authed_client)  # creates BUY 10 @ 100

    resp = await _add_tx(
        authed_client,
        asset_id,
        {
            "transaction_type": "SELL",
            "quantity": "3",
            "price_per_unit": "150",
            "transaction_currency": "USD",
            "transaction_date": "2024-02-01",
        },
    )
    assert resp.status_code == 201, resp.text

    asset = (await authed_client.get(f"{ASSETS_URL}/{asset_id}")).json()["data"]
    assert asset["total_quantity"] == 7.0
    assert asset["realized_pl"] == pytest.approx(150.0)


# ── Optional transaction_date ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_transaction_date_defaults_to_today(authed_client: AsyncClient) -> None:
    """Omitting transaction_date should succeed and default to today."""
    from datetime import date

    asset_id = await _new_asset(authed_client)

    resp = await _add_tx(
        authed_client,
        asset_id,
        {
            "transaction_type": "BUY",
            "quantity": "5",
            "price_per_unit": "100",
            "transaction_currency": "USD",
            # transaction_date intentionally omitted
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["transaction_date"] == date.today().isoformat()


@pytest.mark.asyncio
async def test_asset_create_without_transaction_date(authed_client: AsyncClient) -> None:
    """Creating an asset with no transaction_date in initial_transaction should succeed."""
    from datetime import date

    resp = await authed_client.post(
        ASSETS_URL,
        json={
            "asset_type": "STOCK",
            "symbol": "MSFT",
            "name": "Microsoft",
            "initial_transaction": {
                "transaction_type": "BUY",
                "quantity": "5",
                "price_per_unit": "300",
                "transaction_currency": "USD",
                # transaction_date omitted
            },
        },
    )
    assert resp.status_code == 201, resp.text
    asset_id = resp.json()["data"]["id"]

    txns = (await authed_client.get(f"{ASSETS_URL}/{asset_id}/transactions")).json()["data"]
    assert len(txns) == 1
    assert txns[0]["transaction_date"] == date.today().isoformat()
