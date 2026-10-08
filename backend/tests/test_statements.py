"""Credit-card statement CRUD, reconciliation, transaction, and confirmation tests."""

from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.liability import Liability
from app.models.liability_statement import LiabilityStatement, StatementStatus
from app.models.user import User
from app.services import liability_statement as statement_service


async def _liability(
    client: AsyncClient,
    *,
    liability_type: str = "credit_card",
    currency: str = "TRY",
    name: str = "Garanti Bonus",
) -> dict:
    response = await client.post(
        "/api/liabilities",
        json={
            "name": name,
            "liability_type": liability_type,
            "currency": currency,
            "current_balance": "0",
            "is_active": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _statement_payload(**overrides) -> dict:
    payload = {
        "statement_period_start": "2026-06-25",
        "statement_period_end": "2026-07-24",
        "statement_date": "2026-07-24",
        "due_date": "2026-08-12",
        "currency": "TRY",
        "previous_balance": "5000.000001",
        "payments_total": "4000.000001",
        "purchases_total": "12000.000001",
        "fees_total": "100.000001",
        "interest_total": "200.000001",
        "refunds_total": "1000.000001",
        "statement_balance": "12300.000001",
        "minimum_payment": "2460.000001",
        "remaining_installments_total": "6000.000001",
        "notes": "Manual statement",
        "source": "manual",
    }
    payload.update(overrides)
    return payload


async def _statement_create(
    client: AsyncClient, liability_id: str, **overrides
) -> dict:
    response = await client.post(
        f"/api/liabilities/{liability_id}/statements",
        json=_statement_payload(**overrides),
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _second_user(client: AsyncClient) -> str:
    response = await client.post(
        "/api/auth/register",
        json={"email": "statement-other@example.com", "password": "password12345"},
    )
    assert response.status_code == 201
    return response.json()["data"]["access_token"]


def _transaction_payload(**overrides) -> dict:
    payload = {
        "transaction_date": "2026-07-01",
        "description": "Market purchase",
        "transaction_type": "purchase",
        "amount": "2000.000001",
        "currency": "TRY",
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_statement_crud_and_decimal_precision(
    authed_client: AsyncClient, db_session: AsyncSession
) -> None:
    card = await _liability(authed_client)
    statement = await _statement_create(authed_client, card["id"])
    assert statement["currency"] == "TRY"
    assert statement["status"] == "draft"
    assert statement["calculated_balance"] == pytest.approx(12300.000001)
    assert statement["is_reconciled"] is True

    response = await authed_client.put(
        f"/api/statements/{statement['id']}", json={"notes": "Updated note"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["notes"] == "Updated note"

    db_statement = (
        await db_session.execute(
            select(LiabilityStatement).where(
                LiabilityStatement.id == UUID(statement["id"])
            )
        )
    ).scalar_one()
    assert db_statement.statement_balance == Decimal("12300.000001")

    response = await authed_client.delete(f"/api/statements/{statement['id']}")
    assert response.status_code == 200
    assert (await authed_client.get(f"/api/statements/{statement['id']}")).status_code == 404


@pytest.mark.asyncio
async def test_statement_requires_owned_credit_card_and_matching_currency(
    authed_client: AsyncClient, client: AsyncClient
) -> None:
    loan = await _liability(authed_client, liability_type="personal_loan")
    assert (
        await authed_client.post(
            f"/api/liabilities/{loan['id']}/statements", json=_statement_payload()
        )
    ).status_code == 404

    usd_card = await _liability(authed_client, currency="USD", name="USD card")
    mismatch = await authed_client.post(
        f"/api/liabilities/{usd_card['id']}/statements",
        json=_statement_payload(),
    )
    assert mismatch.status_code == 400

    token = await _second_user(client)
    foreign = await client.post(
        f"/api/liabilities/{usd_card['id']}/statements",
        json=_statement_payload(currency="USD"),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert foreign.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_period_date_and_source_hash_are_conflicts(
    authed_client: AsyncClient,
) -> None:
    card = await _liability(authed_client)
    source_hash = "a" * 64
    await _statement_create(
        authed_client, card["id"], source_file_hash=source_hash
    )

    same_period = await authed_client.post(
        f"/api/liabilities/{card['id']}/statements",
        json=_statement_payload(
            statement_date="2026-07-25", source_file_hash="b" * 64
        ),
    )
    assert same_period.status_code == 409

    same_hash = await authed_client.post(
        f"/api/liabilities/{card['id']}/statements",
        json=_statement_payload(
            statement_period_start="2026-07-25",
            statement_period_end="2026-08-24",
            statement_date="2026-08-24",
            due_date="2026-09-12",
            source_file_hash=source_hash,
        ),
    )
    assert same_hash.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("payments_total", "-0.000001"),
        ("statement_balance", "-1"),
        ("minimum_payment", "13000"),
        ("due_date", "2026-07-01"),
    ],
)
async def test_invalid_statement_values_are_rejected(
    field: str, value: str, authed_client: AsyncClient
) -> None:
    card = await _liability(authed_client)
    response = await authed_client.post(
        f"/api/liabilities/{card['id']}/statements",
        json=_statement_payload(**{field: value}),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reconciliation_tolerance_and_large_difference(
    authed_client: AsyncClient,
) -> None:
    card = await _liability(authed_client)
    within = await _statement_create(
        authed_client, card["id"], statement_balance="12300.010001"
    )
    assert within["is_reconciled"] is True

    second = await _statement_create(
        authed_client,
        card["id"],
        statement_period_start="2026-07-25",
        statement_period_end="2026-08-24",
        statement_date="2026-08-24",
        due_date="2026-09-12",
        statement_balance="12301.000001",
    )
    assert second["is_reconciled"] is False
    response = await authed_client.post(
        f"/api/statements/{second['id']}/confirm",
        json={"apply_to_liability": False},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_transaction_crud_recalculates_reconciliation(
    authed_client: AsyncClient,
) -> None:
    card = await _liability(authed_client)
    statement = await _statement_create(
        authed_client,
        card["id"],
        previous_balance="0",
        purchases_total="2000",
        payments_total="0",
        refunds_total="0",
        fees_total="0",
        interest_total="0",
        statement_balance="2000",
        minimum_payment="200",
    )
    response = await authed_client.post(
        f"/api/statements/{statement['id']}/transactions",
        json=_transaction_payload(amount="1999.50"),
    )
    assert response.status_code == 201
    result = response.json()["data"]
    transaction_id = result["transaction"]["id"]
    assert result["reconciliation"]["is_reconciled"] is False
    assert result["reconciliation"]["reconciliation_difference"] == pytest.approx(0.5)

    response = await authed_client.put(
        f"/api/statement-transactions/{transaction_id}", json={"amount": "2000"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["reconciliation"]["is_reconciled"] is True

    response = await authed_client.delete(
        f"/api/statement-transactions/{transaction_id}"
    )
    assert response.status_code == 200
    assert response.json()["data"]["reconciliation"]["calculation_source"] == "summary"


@pytest.mark.asyncio
async def test_transaction_currency_installment_shape_ownership_and_hash(
    authed_client: AsyncClient, client: AsyncClient
) -> None:
    card = await _liability(authed_client)
    statement = await _statement_create(authed_client, card["id"])
    endpoint = f"/api/statements/{statement['id']}/transactions"

    assert (
        await authed_client.post(endpoint, json=_transaction_payload(currency="USD"))
    ).status_code == 400
    assert (
        await authed_client.post(
            endpoint,
            json=_transaction_payload(
                transaction_type="installment",
                installment_number=2,
                installment_count=1,
            ),
        )
    ).status_code == 422
    assert (
        await authed_client.post(
            endpoint,
            json=_transaction_payload(installment_number=1, installment_count=2),
        )
    ).status_code == 422

    source_hash = "c" * 64
    first = await authed_client.post(
        endpoint, json=_transaction_payload(source_line_hash=source_hash)
    )
    assert first.status_code == 201
    duplicate = await authed_client.post(
        endpoint,
        json=_transaction_payload(
            description="Same imported line", source_line_hash=source_hash
        ),
    )
    assert duplicate.status_code == 409

    token = await _second_user(client)
    foreign = await client.post(
        endpoint,
        json=_transaction_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert foreign.status_code == 404


@pytest.mark.asyncio
async def test_bulk_statement_create_rolls_back_all_rows_on_duplicate_hash(
    authed_client: AsyncClient,
) -> None:
    card = await _liability(authed_client)
    source_hash = "d" * 64
    response = await authed_client.post(
        f"/api/liabilities/{card['id']}/statements",
        json=_statement_payload(
            transactions=[
                _transaction_payload(source_line_hash=source_hash),
                _transaction_payload(
                    description="Duplicate", source_line_hash=source_hash
                ),
            ]
        ),
    )
    assert response.status_code == 409
    listing = await authed_client.get(
        f"/api/liabilities/{card['id']}/statements"
    )
    assert listing.json()["data"] == []


@pytest.mark.asyncio
async def test_bulk_statement_validates_linked_installment_plan_before_writing(
    authed_client: AsyncClient,
) -> None:
    card = await _liability(authed_client)
    plan_response = await authed_client.post(
        f"/api/liabilities/{card['id']}/installment-plans",
        json={
            "description": "Telefon",
            "purchase_date": "2026-05-20",
            "currency": "TRY",
            "original_amount": "9000",
            "installment_count": 6,
            "monthly_installment_amount": "1500",
            "first_installment_date": "2026-06-24",
            "completed_installment_count": 2,
            "status": "active",
        },
    )
    assert plan_response.status_code == 201
    plan = plan_response.json()["data"]

    response = await authed_client.post(
        f"/api/liabilities/{card['id']}/statements",
        json=_statement_payload(
            transactions=[
                _transaction_payload(
                    transaction_type="installment",
                    amount="1500",
                    installment_plan_id=plan["id"],
                    installment_number=2,
                    installment_count=5,
                )
            ]
        ),
    )
    assert response.status_code == 400
    listing = await authed_client.get(
        f"/api/liabilities/{card['id']}/statements"
    )
    assert listing.json()["data"] == []


@pytest.mark.asyncio
async def test_confirm_applies_balance_idempotently_and_delete_does_not_reverse(
    authed_client: AsyncClient, db_session: AsyncSession
) -> None:
    card = await _liability(authed_client)
    statement = await _statement_create(authed_client, card["id"])
    endpoint = f"/api/statements/{statement['id']}/confirm"

    response = await authed_client.post(
        endpoint, json={"apply_to_liability": True}
    )
    assert response.status_code == 200
    confirmed = response.json()["data"]
    assert confirmed["status"] == "confirmed"
    assert confirmed["applied_balance"] == pytest.approx(12300.000001)

    second = await authed_client.post(endpoint, json={"apply_to_liability": True})
    assert second.status_code == 200
    liability = (
        await db_session.execute(
            select(Liability).where(Liability.id == UUID(card["id"]))
        )
    ).scalar_one()
    assert liability.current_balance == Decimal("12300.000001")

    assert (
        await authed_client.delete(f"/api/statements/{statement['id']}")
    ).status_code == 200
    db_session.expire_all()
    liability = (
        await db_session.execute(
            select(Liability).where(Liability.id == UUID(card["id"]))
        )
    ).scalar_one()
    assert liability.current_balance == Decimal("12300.000001")


@pytest.mark.asyncio
async def test_confirm_and_liability_update_roll_back_together_on_commit_failure(
    authed_client: AsyncClient, db_session: AsyncSession
) -> None:
    card = await _liability(authed_client)
    statement = await _statement_create(authed_client, card["id"])
    user_id = (await db_session.execute(select(User.id))).scalar_one()

    failing_commit = AsyncMock(side_effect=RuntimeError("simulated commit failure"))
    with (
        patch.object(db_session, "commit", failing_commit),
        patch.object(
            db_session, "rollback", wraps=db_session.rollback
        ) as rollback_mock,
        pytest.raises(RuntimeError, match="simulated commit failure"),
    ):
        await statement_service.confirm_statement(
            db_session,
            UUID(statement["id"]),
            user_id,
            apply_to_liability=True,
        )

    rollback_mock.assert_awaited_once()
    db_session.expire_all()
    stored_statement = (
        await db_session.execute(
            select(LiabilityStatement).where(
                LiabilityStatement.id == UUID(statement["id"])
            )
        )
    ).scalar_one()
    liability = (
        await db_session.execute(
            select(Liability).where(Liability.id == UUID(card["id"]))
        )
    ).scalar_one()
    assert stored_statement.status == StatementStatus.DRAFT
    assert stored_statement.confirmed_at is None
    assert stored_statement.applied_to_liability_at is None
    assert stored_statement.applied_balance is None
    assert liability.current_balance == Decimal("0")


@pytest.mark.asyncio
async def test_foreign_statement_detail_update_delete_are_safe_404(
    authed_client: AsyncClient, client: AsyncClient
) -> None:
    card = await _liability(authed_client)
    statement = await _statement_create(authed_client, card["id"])
    token = await _second_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    assert (
        await client.get(f"/api/statements/{statement['id']}", headers=headers)
    ).status_code == 404
    assert (
        await client.put(
            f"/api/statements/{statement['id']}",
            json={"notes": "stolen"},
            headers=headers,
        )
    ).status_code == 404
    assert (
        await client.delete(f"/api/statements/{statement['id']}", headers=headers)
    ).status_code == 404
