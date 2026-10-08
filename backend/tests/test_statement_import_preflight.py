"""Security and no-write contract for statement PDF upload preflight."""

import hashlib

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.liability_statement import LiabilityStatement


PDF_BYTES = b"%PDF-1.7\n% NetWorth preflight fixture\n%%EOF\n"


async def _liability(
    client: AsyncClient, *, liability_type: str = "credit_card"
) -> dict:
    response = await client.post(
        "/api/liabilities",
        json={
            "name": "Statement test card",
            "liability_type": liability_type,
            "currency": "TRY",
            "current_balance": "1000",
            "is_active": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _preflight(
    client: AsyncClient,
    liability_id: str,
    *,
    content: bytes = PDF_BYTES,
    filename: str = "statement.pdf",
    content_type: str = "application/pdf",
):
    return await client.post(
        f"/api/liabilities/{liability_id}/statement-imports/preflight",
        files={"file": (filename, content, content_type)},
    )


async def _statement_count(db: AsyncSession) -> int:
    return int(
        (
            await db.execute(select(func.count()).select_from(LiabilityStatement))
        ).scalar_one()
    )


@pytest.mark.asyncio
async def test_valid_pdf_returns_metadata_without_writing_records(
    authed_client: AsyncClient, db_session: AsyncSession
) -> None:
    card = await _liability(authed_client)
    before = await _statement_count(db_session)

    response = await _preflight(authed_client, card["id"])

    assert response.status_code == 200
    data = response.json()["data"]
    assert data == {
        "filename": "statement.pdf",
        "size_bytes": len(PDF_BYTES),
        "sha256": hashlib.sha256(PDF_BYTES).hexdigest(),
        "is_pdf": True,
        "is_duplicate": False,
        "matched_statement_id": None,
        "status": "ready",
        "analysis_available": False,
    }
    assert await _statement_count(db_session) == before


@pytest.mark.asyncio
async def test_client_path_is_reduced_to_safe_filename(
    authed_client: AsyncClient,
) -> None:
    card = await _liability(authed_client)
    response = await _preflight(
        authed_client,
        card["id"],
        filename=r"/demo/statement.pdf",
    )
    assert response.status_code == 200
    assert response.json()["data"]["filename"] == "statement.pdf"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("filename", "content_type"),
    [("statement.txt", "application/pdf"), ("statement.pdf", "text/plain")],
)
async def test_rejects_extension_or_mime_mismatch(
    authed_client: AsyncClient,
    filename: str,
    content_type: str,
) -> None:
    card = await _liability(authed_client)
    response = await _preflight(
        authed_client,
        card["id"],
        filename=filename,
        content_type=content_type,
    )
    assert response.status_code == 415
    assert response.json()["code"] == "invalid_file_type"


@pytest.mark.asyncio
async def test_rejects_fake_pdf_signature(authed_client: AsyncClient) -> None:
    card = await _liability(authed_client)
    response = await _preflight(
        authed_client,
        card["id"],
        content=b"not actually a pdf",
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_pdf"


@pytest.mark.asyncio
async def test_rejects_pdf_over_configured_limit(
    authed_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    card = await _liability(authed_client)
    monkeypatch.setattr(settings, "STATEMENT_PDF_MAX_BYTES", 8)
    response = await _preflight(authed_client, card["id"], content=PDF_BYTES)
    assert response.status_code == 413
    assert response.json()["code"] == "file_too_large"


@pytest.mark.asyncio
async def test_duplicate_hash_returns_existing_statement_link(
    authed_client: AsyncClient,
) -> None:
    card = await _liability(authed_client)
    sha256 = hashlib.sha256(PDF_BYTES).hexdigest()
    create = await authed_client.post(
        f"/api/liabilities/{card['id']}/statements",
        json={
            "statement_period_start": "2026-06-25",
            "statement_period_end": "2026-07-24",
            "statement_date": "2026-07-24",
            "due_date": "2026-08-12",
            "currency": "TRY",
            "previous_balance": "1000",
            "payments_total": "0",
            "purchases_total": "0",
            "fees_total": "0",
            "interest_total": "0",
            "refunds_total": "0",
            "statement_balance": "1000",
            "minimum_payment": "200",
            "remaining_installments_total": "0",
            "source": "manual",
            "source_file_hash": sha256,
        },
    )
    assert create.status_code == 201, create.text

    response = await _preflight(authed_client, card["id"])

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "duplicate_statement_file"
    assert data["is_duplicate"] is True
    assert data["matched_statement_id"] == create.json()["data"]["id"]


@pytest.mark.asyncio
async def test_requires_owned_credit_card(
    authed_client: AsyncClient,
) -> None:
    loan = await _liability(authed_client, liability_type="personal_loan")
    wrong_type = await _preflight(authed_client, loan["id"])
    assert wrong_type.status_code == 400
    assert wrong_type.json()["code"] == "liability_not_credit_card"

    token_response = await authed_client.post(
        "/api/auth/register",
        json={"email": "pdf-owner-check@example.com", "password": "password12345"},
    )
    authed_client.headers["Authorization"] = (
        f"Bearer {token_response.json()['data']['access_token']}"
    )
    not_owned = await _preflight(authed_client, loan["id"])
    assert not_owned.status_code == 404

    authed_client.headers.pop("Authorization")
    unauthorized = await _preflight(authed_client, loan["id"])
    assert unauthorized.status_code == 401
