"""Installment calculations, ownership, atomic linking, and future forecast tests."""

import pytest
from httpx import AsyncClient

from tests.test_statements import (
    _liability,
    _second_user,
    _statement_create,
    _transaction_payload,
)


def _plan_payload(**overrides) -> dict:
    payload = {
        "description": "Telefon",
        "merchant_name": "Phone Store",
        "purchase_date": "2026-05-20",
        "currency": "TRY",
        "original_amount": "9000",
        "installment_count": 6,
        "monthly_installment_amount": "1500",
        "first_installment_date": "2026-06-24",
        "completed_installment_count": 2,
        "status": "active",
    }
    payload.update(overrides)
    return payload


async def _plan(client: AsyncClient, liability_id: str, **overrides) -> dict:
    response = await client.post(
        f"/api/liabilities/{liability_id}/installment-plans",
        json=_plan_payload(**overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


@pytest.mark.asyncio
async def test_installment_plan_computed_fields_and_update(
    authed_client: AsyncClient,
) -> None:
    card = await _liability(authed_client)
    plan = await _plan(authed_client, card["id"])
    assert plan["remaining_installment_count"] == 4
    assert plan["remaining_amount"] == 6000
    assert plan["next_installment_date"] == "2026-08-24"
    assert plan["estimated_completion_date"] == "2026-11-24"

    response = await authed_client.put(
        f"/api/installment-plans/{plan['id']}",
        json={"completed_installment_count": 3},
    )
    assert response.status_code == 200
    assert response.json()["data"]["remaining_amount"] == 4500


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"installment_count": 1},
        {"completed_installment_count": 7},
        {"original_amount": "-1"},
        {"monthly_installment_amount": "100"},
    ],
)
async def test_invalid_installment_plan_is_rejected(
    overrides: dict, authed_client: AsyncClient
) -> None:
    card = await _liability(authed_client)
    response = await authed_client.post(
        f"/api/liabilities/{card['id']}/installment-plans",
        json=_plan_payload(**overrides),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_rounding_tolerance_allows_small_last_installment_difference(
    authed_client: AsyncClient,
) -> None:
    card = await _liability(authed_client)
    plan = await _plan(
        authed_client,
        card["id"],
        original_amount="100.00",
        installment_count=3,
        monthly_installment_amount="33.33",
        completed_installment_count=0,
    )
    assert plan["remaining_amount"] == 100


@pytest.mark.asyncio
async def test_forecast_excludes_completed_and_cancelled_plans(
    authed_client: AsyncClient,
) -> None:
    card = await _liability(authed_client)
    active = await _plan(authed_client, card["id"])
    await _plan(
        authed_client,
        card["id"],
        description="Completed",
        external_reference="completed",
        completed_installment_count=6,
        status="completed",
    )
    cancelled = await _plan(
        authed_client,
        card["id"],
        description="Cancelled",
        external_reference="cancelled",
    )
    assert (
        await authed_client.post(
            f"/api/installment-plans/{cancelled['id']}/cancel"
        )
    ).status_code == 200

    response = await authed_client.get(
        f"/api/liabilities/{card['id']}/installment-forecast?as_of=2026-07-01"
    )
    forecast = response.json()["data"]
    assert forecast["active_plan_count"] == 1
    assert forecast["remaining_total"] == 6000
    assert forecast["next_month_total"] == 1500
    assert [item["amount"] for item in forecast["next_three_months"]] == [
        1500,
        1500,
        1500,
    ]
    assert forecast["nearest_installment_date"] == active["next_installment_date"]


@pytest.mark.asyncio
async def test_plan_and_initial_statement_transaction_are_atomic_and_linked(
    authed_client: AsyncClient,
) -> None:
    card = await _liability(authed_client)
    statement = await _statement_create(
        authed_client,
        card["id"],
        previous_balance="0",
        purchases_total="1500",
        payments_total="0",
        refunds_total="0",
        fees_total="0",
        interest_total="0",
        statement_balance="1500",
        minimum_payment="150",
    )
    transaction = _transaction_payload(
        description="Telefon 2/6",
        transaction_type="installment",
        amount="1500",
        installment_number=2,
        installment_count=6,
    )
    plan = await _plan(
        authed_client,
        card["id"],
        initial_statement_id=statement["id"],
        initial_transaction=transaction,
    )
    detail = (
        await authed_client.get(f"/api/statements/{statement['id']}")
    ).json()["data"]
    assert detail["transactions"][0]["installment_plan_id"] == plan["id"]
    assert detail["is_reconciled"] is True


@pytest.mark.asyncio
async def test_plan_is_rolled_back_when_initial_transaction_conflicts(
    authed_client: AsyncClient,
) -> None:
    card = await _liability(authed_client)
    statement = await _statement_create(authed_client, card["id"])
    source_hash = "e" * 64
    transaction = _transaction_payload(source_line_hash=source_hash)
    assert (
        await authed_client.post(
            f"/api/statements/{statement['id']}/transactions",
            json=transaction,
        )
    ).status_code == 201

    response = await authed_client.post(
        f"/api/liabilities/{card['id']}/installment-plans",
        json=_plan_payload(
            initial_statement_id=statement["id"],
            initial_transaction=_transaction_payload(
                description="Conflicting line",
                transaction_type="installment",
                amount="1500",
                installment_number=2,
                installment_count=6,
                source_line_hash=source_hash,
            ),
        ),
    )
    assert response.status_code == 409
    plans = await authed_client.get(
        f"/api/liabilities/{card['id']}/installment-plans"
    )
    assert plans.json()["data"] == []
    detail = (
        await authed_client.get(f"/api/statements/{statement['id']}")
    ).json()["data"]
    assert len(detail["transactions"]) == 1


@pytest.mark.asyncio
async def test_foreign_installment_plan_is_safe_404(
    authed_client: AsyncClient, client: AsyncClient
) -> None:
    card = await _liability(authed_client)
    plan = await _plan(authed_client, card["id"])
    token = await _second_user(client)
    headers = {"Authorization": f"Bearer {token}"}
    assert (
        await client.get(f"/api/installment-plans/{plan['id']}", headers=headers)
    ).status_code == 404
    assert (
        await client.put(
            f"/api/installment-plans/{plan['id']}",
            json={"completed_installment_count": 4},
            headers=headers,
        )
    ).status_code == 404
