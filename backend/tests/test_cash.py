"""Tests for cash accounts, movements, transfers, transaction cash effects,
and dashboard integration."""

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.services import cash as cash_service

ASSETS_URL = "/api/assets"
TXN_URL = "/api/transactions"
CASH_URL = "/api/cash"
DASH_URL = "/api/dashboard"


def _balances_by_currency(accounts: list[dict]) -> dict[str, float]:
    return {a["currency"]: a["balance"] for a in accounts}


async def _cash_balances(client: AsyncClient) -> dict[str, float]:
    resp = await client.get(CASH_URL)
    assert resp.status_code == 200, resp.text
    return _balances_by_currency(resp.json()["data"])


async def _new_asset(client: AsyncClient, symbol: str = "AAPL") -> str:
    resp = await client.post(
        ASSETS_URL,
        json={"asset_type": "STOCK", "symbol": symbol, "name": symbol},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _buy(
    client: AsyncClient,
    asset_id: str,
    quantity: str = "10",
    price: str = "100",
    currency: str = "USD",
    affects_cash: bool = True,
    date: str = "2024-01-15",
) -> dict:
    body = {
        "transaction_type": "BUY",
        "quantity": quantity,
        "price_per_unit": price,
        "transaction_currency": currency,
        "transaction_date": date,
        "affects_cash": affects_cash,
    }
    resp = await client.post(f"{ASSETS_URL}/{asset_id}/transactions", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def _sell(
    client: AsyncClient,
    asset_id: str,
    quantity: str,
    price: str,
    currency: str = "USD",
    date: str = "2024-03-01",
) -> dict:
    body = {
        "transaction_type": "SELL",
        "quantity": quantity,
        "price_per_unit": price,
        "transaction_currency": currency,
        "transaction_date": date,
    }
    resp = await client.post(f"{ASSETS_URL}/{asset_id}/transactions", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


# ── Auto-create on registration ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_registration_auto_creates_cash_accounts(
    authed_client: AsyncClient,
) -> None:
    resp = await authed_client.get(CASH_URL)
    assert resp.status_code == 200
    accounts = resp.json()["data"]
    currencies = {a["currency"] for a in accounts}
    assert currencies == {"TRY", "USD", "EUR"}
    for a in accounts:
        assert a["balance"] == 0.0


# ── Deposit / withdraw ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_deposit_increases_balance(authed_client: AsyncClient) -> None:
    resp = await authed_client.post(
        f"{CASH_URL}/deposit",
        json={"currency": "TRY", "amount": "1000"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["balance"] == 1000.0

    movements = (await authed_client.get(f"{CASH_URL}/movements")).json()["data"]
    assert any(
        m["movement_type"] == "DEPOSIT" and m["amount"] == 1000.0
        for m in movements
    )


@pytest.mark.asyncio
async def test_withdraw_allows_negative(authed_client: AsyncClient) -> None:
    await authed_client.post(
        f"{CASH_URL}/deposit", json={"currency": "TRY", "amount": "100"}
    )
    resp = await authed_client.post(
        f"{CASH_URL}/withdraw", json={"currency": "TRY", "amount": "250"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["balance"] == -150.0


# ── Transfer ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_transfer_between_currencies(authed_client: AsyncClient) -> None:
    resp = await authed_client.post(
        f"{CASH_URL}/transfer",
        json={
            "from_currency": "USD",
            "to_currency": "TRY",
            "from_amount": "100",
            "rate": "32.5",
        },
    )
    assert resp.status_code == 200, resp.text

    balances = await _cash_balances(authed_client)
    assert balances["USD"] == -100.0
    assert balances["TRY"] == 3250.0

    movements = (await authed_client.get(f"{CASH_URL}/movements")).json()["data"]
    types = {m["movement_type"] for m in movements}
    assert "TRANSFER_IN" in types and "TRANSFER_OUT" in types


@pytest.mark.asyncio
async def test_transfer_same_currency_rejected(authed_client: AsyncClient) -> None:
    resp = await authed_client.post(
        f"{CASH_URL}/transfer",
        json={
            "from_currency": "USD",
            "to_currency": "USD",
            "from_amount": "100",
            "rate": "1",
        },
    )
    assert resp.status_code == 422


# ── Transaction cash effects ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_buy_decrements_cash(authed_client: AsyncClient) -> None:
    asset_id = await _new_asset(authed_client)
    tx = await _buy(
        authed_client, asset_id, quantity="5", price="100", currency="USD"
    )
    assert tx["affects_cash"] is True

    balances = await _cash_balances(authed_client)
    assert balances["USD"] == -500.0
    movements = (await authed_client.get(f"{CASH_URL}/movements")).json()["data"]
    buy_movements = [m for m in movements if m["movement_type"] == "BUY"]
    assert len(buy_movements) == 1
    assert buy_movements[0]["related_transaction_id"] == tx["id"]


@pytest.mark.asyncio
async def test_sell_increments_cash(authed_client: AsyncClient) -> None:
    asset_id = await _new_asset(authed_client)
    await _buy(authed_client, asset_id, quantity="10", price="100", currency="USD")
    await _sell(authed_client, asset_id, quantity="3", price="150", currency="USD")

    balances = await _cash_balances(authed_client)
    # -1000 from BUY, +450 from SELL
    assert balances["USD"] == pytest.approx(-550.0)
    movements = (await authed_client.get(f"{CASH_URL}/movements")).json()["data"]
    assert len([m for m in movements if m["movement_type"] == "SELL"]) == 1


@pytest.mark.asyncio
async def test_affects_cash_false_leaves_balance(authed_client: AsyncClient) -> None:
    asset_id = await _new_asset(authed_client)
    tx = await _buy(
        authed_client,
        asset_id,
        quantity="5",
        price="100",
        currency="USD",
        affects_cash=False,
    )
    assert tx["affects_cash"] is False

    balances = await _cash_balances(authed_client)
    assert balances["USD"] == 0.0
    movements = (await authed_client.get(f"{CASH_URL}/movements")).json()["data"]
    assert movements == []


@pytest.mark.asyncio
async def test_duplicate_transaction_requests_are_not_idempotent(
    authed_client: AsyncClient,
) -> None:
    """Document current API behavior: repeated requests create repeated effects."""
    asset_id = await _new_asset(authed_client)
    body = {
        "transaction_type": "BUY",
        "quantity": "1",
        "price_per_unit": "100",
        "transaction_currency": "USD",
        "transaction_date": "2024-01-15",
        "affects_cash": True,
    }

    first = await authed_client.post(
        f"{ASSETS_URL}/{asset_id}/transactions", json=body
    )
    second = await authed_client.post(
        f"{ASSETS_URL}/{asset_id}/transactions", json=body
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["data"]["id"] != second.json()["data"]["id"]

    balances = await _cash_balances(authed_client)
    assert balances["USD"] == -200.0
    movements = (await authed_client.get(f"{CASH_URL}/movements")).json()["data"]
    assert len([m for m in movements if m["movement_type"] == "BUY"]) == 2


@pytest.mark.asyncio
async def test_auto_provision_unknown_currency(authed_client: AsyncClient) -> None:
    asset_id = await _new_asset(authed_client)
    await _buy(authed_client, asset_id, quantity="2", price="50", currency="GBP")

    balances = await _cash_balances(authed_client)
    assert "GBP" in balances
    assert balances["GBP"] == -100.0


@pytest.mark.asyncio
async def test_transaction_update_reverses_old(authed_client: AsyncClient) -> None:
    asset_id = await _new_asset(authed_client)
    tx = await _buy(
        authed_client, asset_id, quantity="5", price="100", currency="USD"
    )
    # Change to 7 @ 100 → total 700, cash should show -700 not -1200
    resp = await authed_client.put(
        f"{TXN_URL}/{tx['id']}", json={"quantity": "7"}
    )
    assert resp.status_code == 200, resp.text

    balances = await _cash_balances(authed_client)
    assert balances["USD"] == pytest.approx(-700.0)


@pytest.mark.asyncio
async def test_transaction_delete_reverses_effect(
    authed_client: AsyncClient,
) -> None:
    asset_id = await _new_asset(authed_client)
    tx = await _buy(
        authed_client, asset_id, quantity="5", price="100", currency="USD"
    )
    balances = await _cash_balances(authed_client)
    assert balances["USD"] == -500.0

    resp = await authed_client.delete(f"{TXN_URL}/{tx['id']}")
    assert resp.status_code == 200

    balances = await _cash_balances(authed_client)
    assert balances["USD"] == 0.0

    asset = (await authed_client.get(f"{ASSETS_URL}/{asset_id}")).json()["data"]
    assert asset["total_quantity"] == 0.0
    movements = (await authed_client.get(f"{CASH_URL}/movements")).json()["data"]
    assert all(m["related_transaction_id"] is None for m in movements)


@pytest.mark.asyncio
async def test_transaction_delete_reverses_sell_effect(
    authed_client: AsyncClient,
) -> None:
    asset_id = await _new_asset(authed_client)
    await _buy(
        authed_client,
        asset_id,
        quantity="10",
        price="100",
        currency="USD",
        affects_cash=False,
    )
    tx = await _sell(
        authed_client, asset_id, quantity="3", price="150", currency="USD"
    )
    assert (await _cash_balances(authed_client))["USD"] == 450.0

    resp = await authed_client.delete(f"{TXN_URL}/{tx['id']}")
    assert resp.status_code == 200, resp.text

    assert (await _cash_balances(authed_client))["USD"] == 0.0
    asset = (await authed_client.get(f"{ASSETS_URL}/{asset_id}")).json()["data"]
    assert asset["total_quantity"] == 10.0


@pytest.mark.asyncio
async def test_asset_initial_transaction_failure_rolls_back_everything(
    authed_client: AsyncClient,
) -> None:
    original_apply = cash_service.apply_transaction_effect

    async def fail_after_cash_effect(db, user_id, tx) -> None:
        await original_apply(db, user_id, tx)
        raise RuntimeError("injected failure after cash effect")

    with patch(
        "app.services.transaction.cash_service.apply_transaction_effect",
        new=fail_after_cash_effect,
    ):
        with pytest.raises(RuntimeError, match="injected failure"):
            await authed_client.post(
                ASSETS_URL,
                json={
                    "asset_type": "STOCK",
                    "symbol": "ROLLBACK",
                    "name": "Rollback asset",
                    "initial_transaction": {
                        "transaction_type": "BUY",
                        "quantity": "5",
                        "price_per_unit": "100",
                        "transaction_currency": "USD",
                        "affects_cash": True,
                    },
                },
            )

    assets = (await authed_client.get(ASSETS_URL)).json()["data"]
    assert all(asset["symbol"] != "ROLLBACK" for asset in assets)
    assert (await _cash_balances(authed_client))["USD"] == 0.0
    movements = (await authed_client.get(f"{CASH_URL}/movements")).json()["data"]
    assert movements == []


@pytest.mark.asyncio
async def test_transaction_update_failure_rolls_back_transaction_and_cash(
    authed_client: AsyncClient,
) -> None:
    asset_id = await _new_asset(authed_client)
    tx = await _buy(
        authed_client, asset_id, quantity="5", price="100", currency="USD"
    )
    original_apply = cash_service.apply_transaction_effect

    async def fail_after_cash_effect(db, user_id, updated_tx) -> None:
        await original_apply(db, user_id, updated_tx)
        raise RuntimeError("injected failure after replacement cash effect")

    with patch(
        "app.services.transaction.cash_service.apply_transaction_effect",
        new=fail_after_cash_effect,
    ):
        with pytest.raises(RuntimeError, match="injected failure"):
            await authed_client.put(
                f"{TXN_URL}/{tx['id']}", json={"quantity": "7"}
            )

    txns = (
        await authed_client.get(f"{ASSETS_URL}/{asset_id}/transactions")
    ).json()["data"]
    assert len(txns) == 1
    assert txns[0]["quantity"] == 5.0
    assert (await _cash_balances(authed_client))["USD"] == -500.0
    movements = (await authed_client.get(f"{CASH_URL}/movements")).json()["data"]
    assert len(movements) == 1


@pytest.mark.asyncio
async def test_transaction_delete_failure_rolls_back_everything(
    authed_client: AsyncClient,
) -> None:
    asset_id = await _new_asset(authed_client)
    tx = await _buy(
        authed_client, asset_id, quantity="5", price="100", currency="USD"
    )
    original_reverse = cash_service.reverse_transaction_effect

    async def fail_after_reverse(db, user_id, snapshot, **kwargs) -> None:
        await original_reverse(db, user_id, snapshot, **kwargs)
        raise RuntimeError("injected failure after cash reversal")

    with patch(
        "app.services.transaction.cash_service.reverse_transaction_effect",
        new=fail_after_reverse,
    ):
        with pytest.raises(RuntimeError, match="injected failure"):
            await authed_client.delete(f"{TXN_URL}/{tx['id']}")

    txns = (
        await authed_client.get(f"{ASSETS_URL}/{asset_id}/transactions")
    ).json()["data"]
    assert len(txns) == 1
    assert txns[0]["id"] == tx["id"]
    assert (await _cash_balances(authed_client))["USD"] == -500.0
    movements = (await authed_client.get(f"{CASH_URL}/movements")).json()["data"]
    assert len(movements) == 1


# ── Dashboard integration ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dashboard_summary_includes_cash(authed_client: AsyncClient) -> None:
    await authed_client.post(
        f"{CASH_URL}/deposit", json={"currency": "TRY", "amount": "1000"}
    )
    resp = await authed_client.get(f"{DASH_URL}/summary")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["total_cash"] == pytest.approx(1000.0)
    assert data["total_value"] >= 1000.0


@pytest.mark.asyncio
async def test_dashboard_allocation_has_cash_bucket(
    authed_client: AsyncClient,
) -> None:
    await authed_client.post(
        f"{CASH_URL}/deposit", json={"currency": "TRY", "amount": "500"}
    )
    resp = await authed_client.get(f"{DASH_URL}/allocation")
    assert resp.status_code == 200
    data = resp.json()["data"]
    types = {b["asset_type"] for b in data["by_type"]}
    assert "CASH" in types
    cash_bucket = next(b for b in data["by_type"] if b["asset_type"] == "CASH")
    assert cash_bucket["value"] == pytest.approx(500.0)
    total_pct = sum(b["percentage"] for b in data["by_type"])
    assert total_pct == pytest.approx(100.0)
