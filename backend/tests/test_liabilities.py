"""Authenticated liability CRUD and validation contract tests."""

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.liability import Liability


LIABILITIES_URL = "/api/liabilities"


def _payload(**overrides) -> dict:
    payload = {
        "name": "Primary credit card",
        "liability_type": "credit_card",
        "currency": "TRY",
        "current_balance": "12345.678901",
        "original_balance": "15000.000001",
        "interest_rate": "4.250000",
        "minimum_payment": "500.125000",
        "due_date": "2026-08-20",
        "notes": "Manually maintained balance",
        "is_active": True,
    }
    payload.update(overrides)
    return payload


async def _create(client: AsyncClient, **overrides) -> dict:
    response = await client.post(LIABILITIES_URL, json=_payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _register_second_user(client: AsyncClient) -> str:
    response = await client.post(
        "/api/auth/register",
        json={"email": "liability-other@example.com", "password": "password12345"},
    )
    assert response.status_code == 201
    return response.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_liability_endpoints_require_authentication(client: AsyncClient) -> None:
    response = await client.get(LIABILITIES_URL)
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_and_get_liability(authed_client: AsyncClient) -> None:
    liability = await _create(authed_client)

    assert liability["name"] == "Primary credit card"
    assert liability["liability_type"] == "credit_card"
    assert liability["currency"] == "TRY"
    assert liability["current_balance"] == pytest.approx(12345.678901)
    assert liability["is_active"] is True

    response = await authed_client.get(f"{LIABILITIES_URL}/{liability['id']}")
    assert response.status_code == 200
    assert response.json()["data"]["id"] == liability["id"]


@pytest.mark.asyncio
async def test_list_only_returns_current_users_liabilities(
    authed_client: AsyncClient, client: AsyncClient
) -> None:
    own = await _create(authed_client, name="Own liability")
    other_token = await _register_second_user(client)
    other_response = await client.post(
        LIABILITIES_URL,
        json=_payload(name="Other liability"),
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert other_response.status_code == 201

    response = await authed_client.get(LIABILITIES_URL)
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]] == [own["id"]]


@pytest.mark.asyncio
async def test_update_liability_preserves_unset_fields(
    authed_client: AsyncClient,
) -> None:
    liability = await _create(authed_client)

    response = await authed_client.put(
        f"{LIABILITIES_URL}/{liability['id']}",
        json={"current_balance": "9999.123456", "is_active": False},
    )

    assert response.status_code == 200
    updated = response.json()["data"]
    assert updated["current_balance"] == pytest.approx(9999.123456)
    assert updated["is_active"] is False
    assert updated["name"] == liability["name"]
    assert updated["currency"] == liability["currency"]


@pytest.mark.asyncio
async def test_delete_liability(authed_client: AsyncClient) -> None:
    liability = await _create(authed_client)

    response = await authed_client.delete(f"{LIABILITIES_URL}/{liability['id']}")

    assert response.status_code == 200
    assert response.json()["data"]["message"] == "Liability deleted"
    assert (await authed_client.get(f"{LIABILITIES_URL}/{liability['id']}")).status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["get", "put", "delete"])
async def test_foreign_liability_is_a_safe_404(
    method: str, authed_client: AsyncClient, client: AsyncClient
) -> None:
    liability = await _create(authed_client)
    other_token = await _register_second_user(client)
    headers = {"Authorization": f"Bearer {other_token}"}
    url = f"{LIABILITIES_URL}/{liability['id']}"

    if method == "put":
        response = await client.put(url, json={"name": "Stolen"}, headers=headers)
    else:
        response = await getattr(client, method)(url, headers=headers)

    assert response.status_code == 404
    assert response.json()["message"] == "Liability not found"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("current_balance", "-0.000001"),
        ("original_balance", "-1"),
        ("interest_rate", "-1"),
        ("minimum_payment", "-1"),
    ],
)
async def test_negative_liability_values_are_rejected(
    field: str, value: str, authed_client: AsyncClient
) -> None:
    response = await authed_client.post(
        LIABILITIES_URL, json=_payload(**{field: value})
    )
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("currency", ["US", "US12", "???"])
async def test_invalid_currency_is_rejected(
    currency: str, authed_client: AsyncClient
) -> None:
    response = await authed_client.post(
        LIABILITIES_URL, json=_payload(currency=currency)
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_currency_is_normalized_to_uppercase(
    authed_client: AsyncClient,
) -> None:
    liability = await _create(authed_client, currency="usd")
    assert liability["currency"] == "USD"


@pytest.mark.asyncio
async def test_decimal_precision_is_preserved_in_database(
    authed_client: AsyncClient, db_session: AsyncSession
) -> None:
    await _create(
        authed_client,
        name="Precision liability",
        current_balance="123456789.123456",
    )

    result = await db_session.execute(
        select(Liability).where(Liability.name == "Precision liability")
    )
    liability = result.scalar_one()
    assert liability.current_balance == Decimal("123456789.123456")

