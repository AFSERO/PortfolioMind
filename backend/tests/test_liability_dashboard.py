"""Liability integration tests for dashboard totals, FX, and snapshots."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portfolio_snapshot import PortfolioSnapshot
from app.utils.currency import ExchangeRateTable


DASHBOARD = "/api/dashboard"
LIABILITIES = "/api/liabilities"

_ASSET = {
    "asset_type": "CUSTOM",
    "name": "Manual asset",
    "current_price": "500000",
    "current_price_currency": "TRY",
    "is_manual_price": True,
    "initial_transaction": {
        "transaction_type": "BUY",
        "quantity": "1",
        "price_per_unit": "500000",
        "transaction_currency": "TRY",
        "transaction_date": "2026-01-01",
        "affects_cash": False,
    },
}


async def _seed_asset(client: AsyncClient) -> None:
    response = await client.post("/api/assets", json=_ASSET)
    assert response.status_code == 201, response.text


async def _seed_liability(
    client: AsyncClient,
    *,
    name: str = "Credit card",
    balance: str = "20000",
    currency: str = "TRY",
    is_active: bool = True,
    liability_type: str = "credit_card",
) -> dict:
    response = await client.post(
        LIABILITIES,
        json={
            "name": name,
            "liability_type": liability_type,
            "currency": currency,
            "current_balance": balance,
            "is_active": is_active,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _register_user(client: AsyncClient, email: str) -> str:
    response = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password12345"},
    )
    assert response.status_code == 201
    return response.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_summary_without_liabilities_preserves_gross_assets(
    authed_client: AsyncClient,
) -> None:
    await _seed_asset(authed_client)
    response = await authed_client.get(f"{DASHBOARD}/summary")
    data = response.json()["data"]

    assert data["total_value"] == 500000
    assert data["total_assets"] == 500000
    assert data["total_liabilities"] == 0
    assert data["net_worth"] == 500000


@pytest.mark.asyncio
async def test_summary_subtracts_multiple_active_liabilities(
    authed_client: AsyncClient,
) -> None:
    await _seed_asset(authed_client)
    await _seed_liability(authed_client, balance="20000")
    await _seed_liability(authed_client, name="Loan", balance="10000")
    await _seed_liability(
        authed_client, name="Inactive", balance="999999", is_active=False
    )

    data = (await authed_client.get(f"{DASHBOARD}/summary")).json()["data"]

    assert data["total_assets"] == 500000
    assert data["total_liabilities"] == 30000
    assert data["net_worth"] == 470000
    assert data["total_value"] == data["total_assets"]


@pytest.mark.asyncio
async def test_negative_net_worth_is_valid(authed_client: AsyncClient) -> None:
    await _seed_liability(authed_client, balance="600000")
    data = (await authed_client.get(f"{DASHBOARD}/summary")).json()["data"]
    assert data["total_assets"] == 0
    assert data["total_liabilities"] == 600000
    assert data["net_worth"] == -600000


@pytest.mark.asyncio
async def test_cash_is_counted_once_in_total_assets(authed_client: AsyncClient) -> None:
    await _seed_asset(authed_client)
    deposit = await authed_client.post(
        "/api/cash/deposit", json={"currency": "TRY", "amount": "10000"}
    )
    assert deposit.status_code == 200
    await _seed_liability(authed_client, balance="20000")

    data = (await authed_client.get(f"{DASHBOARD}/summary")).json()["data"]
    assert data["total_cash"] == 10000
    assert data["total_assets"] == 510000
    assert data["net_worth"] == 490000


@pytest.mark.asyncio
async def test_foreign_liability_is_not_included(
    authed_client: AsyncClient, client: AsyncClient
) -> None:
    await _seed_liability(authed_client, balance="20000")
    other_token = await _register_user(client, "summary-other@example.com")

    response = await client.get(
        f"{DASHBOARD}/summary",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    data = response.json()["data"]
    assert data["total_liabilities"] == 0
    assert data["net_worth"] == 0


@pytest.mark.asyncio
@patch("app.services.dashboard.build_rate_map", new_callable=AsyncMock)
async def test_cross_currency_liability_uses_shared_rate(
    mock_build_rate_map: AsyncMock, authed_client: AsyncClient
) -> None:
    mock_build_rate_map.return_value = {"USD/TRY": Decimal("40")}
    await _seed_asset(authed_client)
    await _seed_liability(authed_client, balance="5000", currency="USD")

    data = (await authed_client.get(f"{DASHBOARD}/summary")).json()["data"]
    assert data["total_assets"] == 500000
    assert data["total_liabilities"] == 200000
    assert data["net_worth"] == 300000


@pytest.mark.asyncio
@pytest.mark.parametrize("rate", [None, Decimal("0"), Decimal("-1")])
@patch("app.services.dashboard.build_rate_map", new_callable=AsyncMock)
async def test_missing_or_invalid_liability_rate_returns_424(
    mock_build_rate_map: AsyncMock,
    rate: Decimal | None,
    authed_client: AsyncClient,
) -> None:
    mock_build_rate_map.return_value = (
        {} if rate is None else {"USD/TRY": rate}
    )
    await _seed_liability(authed_client, balance="5000", currency="USD")

    response = await authed_client.get(f"{DASHBOARD}/summary")

    assert response.status_code == 424
    assert response.json()["code"] == "exchange_rate_unavailable"
    assert response.json()["details"]["missing_rates"] == ["USD/TRY"]
    assert "data" not in response.json()


@pytest.mark.asyncio
@patch("app.services.dashboard.build_rate_map", new_callable=AsyncMock)
async def test_zero_balance_cross_currency_liability_needs_no_rate(
    mock_build_rate_map: AsyncMock, authed_client: AsyncClient
) -> None:
    mock_build_rate_map.return_value = {}
    await _seed_liability(authed_client, balance="0", currency="USD")

    response = await authed_client.get(f"{DASHBOARD}/summary")

    assert response.status_code == 200
    assert response.json()["data"]["total_liabilities"] == 0


@pytest.mark.asyncio
@patch("app.services.dashboard.build_rate_map", new_callable=AsyncMock)
async def test_stale_liability_rate_metadata_is_preserved(
    mock_build_rate_map: AsyncMock, authed_client: AsyncClient
) -> None:
    pair = "USD/TRY"
    fetched_at = datetime.now(timezone.utc) - timedelta(days=2)
    mock_build_rate_map.return_value = ExchangeRateTable(
        rates={pair: Decimal("40")},
        fetched_at={pair: fetched_at},
        stale_pairs={pair},
    )
    await _seed_liability(authed_client, balance="100", currency="USD")

    data = (await authed_client.get(f"{DASHBOARD}/summary")).json()["data"]
    assert data["total_liabilities"] == 4000
    assert data["exchange_rates"]["status"] == "stale"
    assert data["exchange_rates"]["rates"][0]["stale"] is True


@pytest.mark.asyncio
@patch("app.services.dashboard.build_rate_map", new_callable=AsyncMock)
async def test_product_acceptance_scenario_create_update_and_delete(
    mock_build_rate_map: AsyncMock, authed_client: AsyncClient
) -> None:
    mock_build_rate_map.return_value = {"USD/TRY": Decimal("40")}
    await _seed_asset(authed_client)

    initial = (await authed_client.get(f"{DASHBOARD}/summary")).json()["data"]
    assert (initial["total_assets"], initial["total_liabilities"], initial["net_worth"]) == (
        500000,
        0,
        500000,
    )

    card = await _seed_liability(authed_client, balance="20000")
    after_card = (await authed_client.get(f"{DASHBOARD}/summary")).json()["data"]
    assert (after_card["total_liabilities"], after_card["net_worth"]) == (
        20000,
        480000,
    )

    loan = await _seed_liability(
        authed_client,
        name="USD personal loan",
        balance="5000",
        currency="USD",
        liability_type="personal_loan",
    )
    after_loan = (await authed_client.get(f"{DASHBOARD}/summary")).json()["data"]
    assert (after_loan["total_liabilities"], after_loan["net_worth"]) == (
        220000,
        280000,
    )

    update = await authed_client.put(
        f"{LIABILITIES}/{card['id']}", json={"current_balance": "10000"}
    )
    assert update.status_code == 200
    after_update = (await authed_client.get(f"{DASHBOARD}/summary")).json()["data"]
    assert (after_update["total_liabilities"], after_update["net_worth"]) == (
        210000,
        290000,
    )

    delete = await authed_client.delete(f"{LIABILITIES}/{loan['id']}")
    assert delete.status_code == 200
    after_delete = (await authed_client.get(f"{DASHBOARD}/summary")).json()["data"]
    assert (after_delete["total_liabilities"], after_delete["net_worth"]) == (
        10000,
        490000,
    )


@pytest.mark.asyncio
@patch("app.services.dashboard.build_rate_map", new_callable=AsyncMock)
async def test_new_snapshot_stores_assets_liabilities_and_net_worth(
    mock_build_rate_map: AsyncMock, authed_client: AsyncClient
) -> None:
    async def _rates(_currencies, target, _db=None):
        if target == "TRY":
            return {"USD/TRY": Decimal("40")}
        return {
            "TRY/USD": Decimal("0.025"),
        }

    mock_build_rate_map.side_effect = _rates
    await _seed_asset(authed_client)
    await _seed_liability(authed_client, balance="5000", currency="USD")

    response = await authed_client.post(f"{DASHBOARD}/snapshot")
    data = response.json()["data"]

    assert response.status_code == 200
    assert data["total_value_try"] == 500000
    assert data["total_assets_try"] == 500000
    assert data["total_liabilities_try"] == 200000
    assert data["net_worth_try"] == 300000
    assert data["total_assets_usd"] == 12500
    assert data["total_liabilities_usd"] == 5000
    assert data["net_worth_usd"] == 7500


@pytest.mark.asyncio
@patch("app.services.dashboard.build_rate_map", new_callable=AsyncMock)
async def test_missing_liability_rate_does_not_write_snapshot(
    mock_build_rate_map: AsyncMock,
    authed_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    mock_build_rate_map.return_value = {}
    await _seed_liability(authed_client, balance="5000", currency="USD")

    response = await authed_client.post(f"{DASHBOARD}/snapshot")

    assert response.status_code == 424
    count = await db_session.scalar(select(func.count()).select_from(PortfolioSnapshot))
    assert count == 0


@pytest.mark.asyncio
async def test_legacy_snapshot_remains_explicit_and_timeline_safe(
    authed_client: AsyncClient, db_session: AsyncSession
) -> None:
    user_response = await authed_client.get("/api/auth/me")
    user_id = user_response.json()["data"]["id"]
    db_session.add(
        PortfolioSnapshot(
            user_id=UUID(user_id),
            total_value_try=Decimal("100000.00"),
            total_value_usd=Decimal("2500.00"),
            snapshot_date=datetime.now(timezone.utc).date() - timedelta(days=10),
        )
    )
    await db_session.commit()

    response = await authed_client.get(f"{DASHBOARD}/timeline")
    point = response.json()["data"][0]

    assert point["total_value_try"] == 100000
    assert point["total_assets_try"] is None
    assert point["total_liabilities_try"] is None
    assert point["net_worth_try"] is None
    assert point["value_semantics"] == "gross_assets"
