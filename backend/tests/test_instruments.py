"""Comprehensive test suite for the Instrument layer.

Validates:
1. Asset creation creates and links an Instrument.
2. Two identical assets can safely reuse the same Instrument.
3. Ambiguous instruments (different asset types or exchanges) are NOT merged.
4. Custom and real estate assets are never erroneously shared.
5. Asset transactions and quantity / cost basis logic still work.
6. Dashboard / P&L behavior is unchanged.
7. Asset deletion does not delete a shared Instrument.
8. Asset detail and list responses correctly expose Instrument identity.
9. Updating an asset's symbol safely relinks to a new Instrument without mutating shared instruments.
10. Migration backfill correctly assigns Instruments to existing Assets.
11. Instrument endpoints (GET /api/instruments, GET /api/instruments/{id}).
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset, AssetType
from app.models.instrument import Instrument
from app.models.user import User


async def _register_user(client: AsyncClient, email: str = "user1@example.com") -> str:
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "display_name": email.split("@")[0],
        },
    )
    return resp.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_asset_creation_creates_and_links_instrument(client: AsyncClient, db_session: AsyncSession):
    token = await _register_user(client, "alice@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "asset_type": "STOCK",
        "symbol": "THYAO.IS",
        "name": "Türk Hava Yolları",
        "current_price_currency": "TRY",
        "initial_transaction": {
            "transaction_type": "BUY",
            "quantity": "50",
            "price_per_unit": "250.00",
            "transaction_currency": "TRY",
            "transaction_date": "2024-05-01",
        },
    }

    with patch("app.services.price.fetch_price", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (Decimal("260.00"), "TRY")
        resp = await client.post("/api/assets", json=payload, headers=headers)

    assert resp.status_code == 201
    data = resp.json()["data"]

    # 1. Response exposes instrument_id and instrument
    assert data["instrument_id"] is not None
    inst = data["instrument"]
    assert inst is not None
    assert inst["id"] == data["instrument_id"]
    assert inst["symbol"] == "THYAO.IS"
    assert inst["exchange"] == "BIST"
    assert inst["currency"] == "TRY"
    assert inst["asset_type"] == "STOCK"

    # Verify directly in DB
    asset_row = (
        await db_session.execute(select(Asset).where(Asset.id == uuid.UUID(data["id"])))
    ).scalar_one()
    assert asset_row.instrument_id == uuid.UUID(inst["id"])

    inst_row = (
        await db_session.execute(
            select(Instrument).where(Instrument.id == uuid.UUID(inst["id"]))
        )
    ).scalar_one()
    assert inst_row.symbol == "THYAO.IS"
    assert inst_row.exchange == "BIST"


@pytest.mark.asyncio
async def test_identical_assets_reuse_same_instrument(client: AsyncClient, db_session: AsyncSession):
    token_1 = await _register_user(client, "bob@example.com")
    token_2 = await _register_user(client, "charlie@example.com")

    payload = {
        "asset_type": "STOCK",
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "current_price_currency": "USD",
        "initial_transaction": {
            "transaction_type": "BUY",
            "quantity": "10",
            "price_per_unit": "180.00",
            "transaction_currency": "USD",
        },
    }

    with patch("app.services.price.fetch_price", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (Decimal("185.00"), "USD")
        resp1 = await client.post("/api/assets", json=payload, headers={"Authorization": f"Bearer {token_1}"})
        resp2 = await client.post("/api/assets", json=payload, headers={"Authorization": f"Bearer {token_2}"})

    assert resp1.status_code == 201
    assert resp2.status_code == 201

    data1 = resp1.json()["data"]
    data2 = resp2.json()["data"]

    # Different user assets
    assert data1["id"] != data2["id"]
    assert data1["user_id"] != data2["user_id"]

    # Same instrument reused!
    assert data1["instrument_id"] == data2["instrument_id"]
    assert data1["instrument"]["id"] == data2["instrument"]["id"]

    # Verify exactly 1 Instrument exists for AAPL in DB
    instruments = (
        await db_session.execute(
            select(Instrument).where(Instrument.symbol == "AAPL")
        )
    ).scalars().all()
    assert len(instruments) == 1


@pytest.mark.asyncio
async def test_ambiguous_or_different_instruments_not_merged(client: AsyncClient, db_session: AsyncSession):
    token = await _register_user(client, "dan@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Stock BAT (NASDAQ)
    stock_payload = {
        "asset_type": "STOCK",
        "symbol": "BAT",
        "name": "British American Tobacco",
        "exchange": "NASDAQ",
        "current_price_currency": "USD",
        "initial_transaction": {
            "transaction_type": "BUY",
            "quantity": "10",
            "price_per_unit": "35.00",
            "transaction_currency": "USD",
        },
    }

    # 2. Crypto BAT (Basic Attention Token)
    crypto_payload = {
        "asset_type": "CRYPTO",
        "symbol": "BAT",
        "name": "Basic Attention Token",
        "current_price_currency": "USD",
        "initial_transaction": {
            "transaction_type": "BUY",
            "quantity": "500",
            "price_per_unit": "0.25",
            "transaction_currency": "USD",
        },
    }

    # 3. Stock BAT on different exchange (LSE)
    stock_lse_payload = {
        "asset_type": "STOCK",
        "symbol": "BAT",
        "name": "BAT LSE",
        "exchange": "LSE",
        "current_price_currency": "GBP",
        "initial_transaction": {
            "transaction_type": "BUY",
            "quantity": "20",
            "price_per_unit": "25.00",
            "transaction_currency": "GBP",
        },
    }

    with patch("app.services.price.fetch_price", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (Decimal("30.00"), "USD")
        r1 = await client.post("/api/assets", json=stock_payload, headers=headers)
        r2 = await client.post("/api/assets", json=crypto_payload, headers=headers)
        r3 = await client.post("/api/assets", json=stock_lse_payload, headers=headers)

    inst_id_1 = r1.json()["data"]["instrument_id"]
    inst_id_2 = r2.json()["data"]["instrument_id"]
    inst_id_3 = r3.json()["data"]["instrument_id"]

    # All three must be distinct instruments
    assert inst_id_1 != inst_id_2
    assert inst_id_1 != inst_id_3
    assert inst_id_2 != inst_id_3


@pytest.mark.asyncio
async def test_custom_and_real_estate_assets_never_shared(client: AsyncClient):
    token_1 = await _register_user(client, "eva@example.com")
    token_2 = await _register_user(client, "frank@example.com")

    payload = {
        "asset_type": "REAL_ESTATE",
        "name": "Kadıköy Daire",
        "current_price": 5000000,
        "current_price_currency": "TRY",
        "is_manual_price": True,
        "initial_transaction": {
            "transaction_type": "BUY",
            "quantity": "1",
            "price_per_unit": "4500000",
            "transaction_currency": "TRY",
        },
    }

    r1 = await client.post("/api/assets", json=payload, headers={"Authorization": f"Bearer {token_1}"})
    r2 = await client.post("/api/assets", json=payload, headers={"Authorization": f"Bearer {token_2}"})

    assert r1.status_code == 201
    assert r2.status_code == 201

    data1 = r1.json()["data"]
    data2 = r2.json()["data"]

    # Custom/Real estate must have dedicated instruments
    assert data1["instrument_id"] != data2["instrument_id"]


@pytest.mark.asyncio
async def test_asset_transactions_and_quantity_still_work(client: AsyncClient):
    token = await _register_user(client, "grace@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Initial BUY: 10 units @ 100 TRY
    create_payload = {
        "asset_type": "STOCK",
        "symbol": "EREGL.IS",
        "name": "Erdemir",
        "current_price": 110,
        "current_price_currency": "TRY",
        "is_manual_price": True,
        "initial_transaction": {
            "transaction_type": "BUY",
            "quantity": "10",
            "price_per_unit": "100.00",
            "transaction_currency": "TRY",
            "transaction_date": "2024-01-01",
        },
    }
    r = await client.post("/api/assets", json=create_payload, headers=headers)
    assert r.status_code == 201
    asset_id = r.json()["data"]["id"]

    # Second BUY: 10 units @ 120 TRY
    tx2_payload = {
        "transaction_type": "BUY",
        "quantity": "10",
        "price_per_unit": "120.00",
        "transaction_currency": "TRY",
        "transaction_date": "2024-02-01",
    }
    r_tx2 = await client.post(f"/api/assets/{asset_id}/transactions", json=tx2_payload, headers=headers)
    assert r_tx2.status_code == 201

    # SELL: 5 units @ 150 TRY
    tx3_payload = {
        "transaction_type": "SELL",
        "quantity": "5",
        "price_per_unit": "150.00",
        "transaction_currency": "TRY",
        "transaction_date": "2024-03-01",
    }
    r_tx3 = await client.post(f"/api/assets/{asset_id}/transactions", json=tx3_payload, headers=headers)
    assert r_tx3.status_code == 201

    # Fetch asset
    r_asset = await client.get(f"/api/assets/{asset_id}", headers=headers)
    assert r_asset.status_code == 200
    asset_data = r_asset.json()["data"]

    # 10 + 10 - 5 = 15 remaining
    assert asset_data["total_quantity"] == 15.0
    # Average cost of BUYs = (10*100 + 10*120)/20 = 110 TRY
    assert asset_data["avg_cost"] == 110.0
    # Realized P&L on 5 units sold: 5 * (150 - 110) = 200 TRY
    assert asset_data["realized_pl"] == 200.0
    # Instrument info present
    assert asset_data["instrument_id"] is not None
    assert asset_data["instrument"]["symbol"] == "EREGL.IS"


@pytest.mark.asyncio
async def test_asset_deletion_preserves_shared_instrument(client: AsyncClient, db_session: AsyncSession):
    token_1 = await _register_user(client, "user_del1@example.com")
    token_2 = await _register_user(client, "user_del2@example.com")

    payload = {
        "asset_type": "STOCK",
        "symbol": "NVDA",
        "name": "NVIDIA Corporation",
        "current_price_currency": "USD",
        "initial_transaction": {
            "transaction_type": "BUY",
            "quantity": "5",
            "price_per_unit": "120.00",
            "transaction_currency": "USD",
        },
    }

    with patch("app.services.price.fetch_price", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (Decimal("125.00"), "USD")
        r1 = await client.post("/api/assets", json=payload, headers={"Authorization": f"Bearer {token_1}"})
        r2 = await client.post("/api/assets", json=payload, headers={"Authorization": f"Bearer {token_2}"})

    asset_id_1 = r1.json()["data"]["id"]
    inst_id = r1.json()["data"]["instrument_id"]
    assert r2.json()["data"]["instrument_id"] == inst_id

    # User 1 deletes their asset
    del_r = await client.delete(f"/api/assets/{asset_id_1}", headers={"Authorization": f"Bearer {token_1}"})
    assert del_r.status_code == 200

    # Verify User 1 asset is deleted
    check_asset = await client.get(f"/api/assets/{asset_id_1}", headers={"Authorization": f"Bearer {token_1}"})
    assert check_asset.status_code == 404

    # Verify shared Instrument still exists in DB
    inst_row = (
        await db_session.execute(select(Instrument).where(Instrument.id == uuid.UUID(inst_id)))
    ).scalar_one_or_none()
    assert inst_row is not None
    assert inst_row.symbol == "NVDA"

    # User 2 asset still points to this instrument
    asset_id_2 = r2.json()["data"]["id"]
    u2_resp = await client.get(f"/api/assets/{asset_id_2}", headers={"Authorization": f"Bearer {token_2}"})
    assert u2_resp.status_code == 200
    assert u2_resp.json()["data"]["instrument_id"] == inst_id


@pytest.mark.asyncio
async def test_asset_update_relinks_instrument_safely(client: AsyncClient):
    token_1 = await _register_user(client, "updater1@example.com")
    token_2 = await _register_user(client, "updater2@example.com")

    payload = {
        "asset_type": "STOCK",
        "symbol": "MSFT",
        "name": "Microsoft Corp",
        "current_price_currency": "USD",
        "initial_transaction": {
            "transaction_type": "BUY",
            "quantity": "2",
            "price_per_unit": "400.00",
            "transaction_currency": "USD",
        },
    }

    with patch("app.services.price.fetch_price", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (Decimal("410.00"), "USD")
        r1 = await client.post("/api/assets", json=payload, headers={"Authorization": f"Bearer {token_1}"})
        r2 = await client.post("/api/assets", json=payload, headers={"Authorization": f"Bearer {token_2}"})

    asset_id_1 = r1.json()["data"]["id"]
    asset_id_2 = r2.json()["data"]["id"]
    original_msft_inst_id = r1.json()["data"]["instrument_id"]
    assert r2.json()["data"]["instrument_id"] == original_msft_inst_id

    # User 1 updates symbol to GOOG
    with patch("app.services.price.fetch_price", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (Decimal("170.00"), "USD")
        update_r = await client.put(
            f"/api/assets/{asset_id_1}",
            json={"symbol": "GOOG", "name": "Alphabet Inc."},
            headers={"Authorization": f"Bearer {token_1}"},
        )
    assert update_r.status_code == 200
    u1_updated = update_r.json()["data"]

    # User 1 asset now relinked to GOOG instrument
    assert u1_updated["instrument_id"] != original_msft_inst_id
    assert u1_updated["instrument"]["symbol"] == "GOOG"

    # User 2 asset still points to original MSFT instrument
    u2_check = await client.get(f"/api/assets/{asset_id_2}", headers={"Authorization": f"Bearer {token_2}"})
    assert u2_check.json()["data"]["instrument_id"] == original_msft_inst_id
    assert u2_check.json()["data"]["instrument"]["symbol"] == "MSFT"


@pytest.mark.asyncio
async def test_migration_backfill_assigns_instruments(db_session: AsyncSession):
    """Simulate legacy assets without instrument_id and run backfill logic."""
    # Create test user
    user = User(email="migtest@example.com", password_hash="pw", base_currency="TRY")
    db_session.add(user)
    await db_session.flush()

    # Create unlinked legacy assets
    asset_bist1 = Asset(
        user_id=user.id,
        asset_type=AssetType.STOCK,
        symbol="SISE.IS",
        name="Şişecam",
        current_price_currency="TRY",
    )
    asset_bist2 = Asset(
        user_id=user.id,
        asset_type=AssetType.STOCK,
        symbol="SISE.IS",
        name="Şişecam Portföy",
        current_price_currency="TRY",
    )
    asset_custom = Asset(
        user_id=user.id,
        asset_type=AssetType.CUSTOM,
        symbol=None,
        name="Antika Tablo",
        current_price_currency="TRY",
    )
    db_session.add_all([asset_bist1, asset_bist2, asset_custom])
    await db_session.commit()

    # Run backfill logic on these assets
    from app.services.instrument import find_or_create_instrument

    for a in [asset_bist1, asset_bist2, asset_custom]:
        inst = await find_or_create_instrument(
            db_session,
            asset_type=a.asset_type,
            name=a.name,
            symbol=a.symbol,
            currency=a.current_price_currency,
        )
        a.instrument_id = inst.id

    await db_session.commit()
    await db_session.refresh(asset_bist1)
    await db_session.refresh(asset_bist2)
    await db_session.refresh(asset_custom)

    # Both SISE.IS assets should share the exact same Instrument
    assert asset_bist1.instrument_id is not None
    assert asset_bist2.instrument_id is not None
    assert asset_bist1.instrument_id == asset_bist2.instrument_id

    # Custom asset should have a unique Instrument
    assert asset_custom.instrument_id is not None
    assert asset_custom.instrument_id != asset_bist1.instrument_id


@pytest.mark.asyncio
async def test_instruments_api_endpoints(client: AsyncClient):
    token = await _register_user(client, "searcher@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Create an asset to ensure an instrument exists
    with patch("app.services.price.fetch_price", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (Decimal("100.00"), "USD")
        await client.post(
            "/api/assets",
            json={
                "asset_type": "STOCK",
                "symbol": "TSLA",
                "name": "Tesla Inc.",
                "current_price_currency": "USD",
            },
            headers=headers,
        )

    # 1. List instruments
    list_r = await client.get("/api/instruments?q=TSLA", headers=headers)
    assert list_r.status_code == 200
    data = list_r.json()["data"]
    assert len(data) >= 1
    inst = data[0]
    assert inst["symbol"] == "TSLA"

    # 2. Get instrument by ID
    get_r = await client.get(f"/api/instruments/{inst['id']}", headers=headers)
    assert get_r.status_code == 200
    assert get_r.json()["data"]["id"] == inst["id"]
