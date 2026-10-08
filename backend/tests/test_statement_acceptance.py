"""The product-level Garanti Bonus statement acceptance scenario."""

import pytest
from httpx import AsyncClient

from tests.test_installment_plans import _plan
from tests.test_statements import (
    _liability,
    _statement_create,
    _transaction_payload,
)


@pytest.mark.asyncio
async def test_garanti_bonus_statement_acceptance_scenario(
    authed_client: AsyncClient,
) -> None:
    card = await _liability(authed_client)
    statement = await _statement_create(
        authed_client,
        card["id"],
        previous_balance="5000",
        purchases_total="12000",
        payments_total="4000",
        refunds_total="1000",
        fees_total="100",
        interest_total="200",
        statement_balance="12300",
        minimum_payment="2460",
        remaining_installments_total="6000",
    )
    plan = await _plan(authed_client, card["id"])
    endpoint = f"/api/statements/{statement['id']}/transactions"
    rows = [
        _transaction_payload(description="Market", amount="2000"),
        _transaction_payload(description="Online", amount="3000"),
        _transaction_payload(
            description="Telefon 2/6",
            transaction_type="installment",
            amount="1500",
            installment_plan_id=plan["id"],
            installment_number=2,
            installment_count=6,
        ),
        _transaction_payload(description="Other purchases", amount="5500"),
        _transaction_payload(
            description="Payment", transaction_type="payment", amount="4000"
        ),
        _transaction_payload(
            description="Refund", transaction_type="refund", amount="1000"
        ),
        _transaction_payload(
            description="Interest", transaction_type="interest", amount="200"
        ),
        _transaction_payload(
            description="Fee", transaction_type="fee", amount="100"
        ),
    ]
    for row in rows:
        response = await authed_client.post(endpoint, json=row)
        assert response.status_code == 201, response.text

    detail = (
        await authed_client.get(f"/api/statements/{statement['id']}")
    ).json()["data"]
    assert detail["calculated_balance"] == 12300
    assert detail["reconciliation_difference"] == 0
    assert detail["is_reconciled"] is True
    assert plan["remaining_installment_count"] == 4
    assert plan["remaining_amount"] == 6000

    first_confirm = await authed_client.post(
        f"/api/statements/{statement['id']}/confirm",
        json={"apply_to_liability": True},
    )
    assert first_confirm.status_code == 200
    assert first_confirm.json()["data"]["status"] == "confirmed"
    assert (
        await authed_client.post(
            f"/api/statements/{statement['id']}/confirm",
            json={"apply_to_liability": True},
        )
    ).status_code == 200

    dashboard = (
        await authed_client.get("/api/dashboard/summary")
    ).json()["data"]
    assert dashboard["total_liabilities"] == 12300
    assert dashboard["net_worth"] == -12300

    await authed_client.delete(f"/api/statements/{statement['id']}")
    liability = (
        await authed_client.get(f"/api/liabilities/{card['id']}")
    ).json()["data"]
    assert liability["current_balance"] == 12300
