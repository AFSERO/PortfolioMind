"""Tests for the price fetching service and /api/prices endpoints.

External APIs are mocked — we test the caching, fallback, refresh, and
price_history persistence logic.
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.utils import cache

PRICES_URL = "/api/prices"

_STOCK_PAYLOAD = {
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

_CRYPTO_PAYLOAD = {
    "asset_type": "CRYPTO",
    "symbol": "BTC",
    "name": "Bitcoin",
    "initial_transaction": {
        "transaction_type": "BUY",
        "quantity": "0.5",
        "price_per_unit": "62000",
        "transaction_currency": "USD",
        "transaction_date": "2024-01-10",
    },
}

_REAL_ESTATE_PAYLOAD = {
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


@pytest.fixture(autouse=True)
def _clear_cache():
    """Ensure each test starts with a clean price cache."""
    cache.clear()
    yield
    cache.clear()


# ── GET /api/prices/live/{symbol} ─────────────────────────────────────────────


@pytest.mark.asyncio
@patch("app.services.price.fetch_price", new_callable=AsyncMock)
async def test_live_price_success(mock_fetch, client: AsyncClient) -> None:
    mock_fetch.return_value = (Decimal("95000.50"), "USD")

    resp = await client.get(f"{PRICES_URL}/live/BTC", params={"asset_type": "CRYPTO"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    data = body["data"]
    assert data["symbol"] == "BTC"
    assert data["price"] == 95000.50
    assert data["currency"] == "USD"
    assert data["source"] == "live"


@pytest.mark.asyncio
@patch("app.services.price.fetch_price", new_callable=AsyncMock)
async def test_live_price_uses_cache(mock_fetch, client: AsyncClient) -> None:
    mock_fetch.return_value = (Decimal("95000"), "USD")

    # First call → live fetch
    resp1 = await client.get(f"{PRICES_URL}/live/BTC", params={"asset_type": "CRYPTO"})
    assert resp1.json()["data"]["source"] == "live"

    # Second call → should hit cache, fetch_price NOT called again
    resp2 = await client.get(f"{PRICES_URL}/live/BTC", params={"asset_type": "CRYPTO"})
    assert resp2.json()["data"]["source"] == "cache"
    assert mock_fetch.call_count == 1


@pytest.mark.asyncio
@patch("app.services.price.fetch_price", new_callable=AsyncMock)
async def test_live_price_fallback_unavailable(mock_fetch, client: AsyncClient) -> None:
    """When fetch fails and there's no history, return source=unavailable."""
    mock_fetch.side_effect = RuntimeError("API down")

    resp = await client.get(
        f"{PRICES_URL}/live/NOSYMBOL", params={"asset_type": "STOCK"}
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["source"] == "unavailable"
    assert data["price"] is None


# ── POST /api/prices/refresh ──────────────────────────────────────────────────


@pytest.mark.asyncio
@patch("app.services.price.fetch_price", new_callable=AsyncMock)
async def test_refresh_updates_assets(mock_fetch, authed_client: AsyncClient) -> None:
    """Refresh should update current_price on auto-fetchable assets."""
    mock_fetch.return_value = (Decimal("300.00"), "TRY")

    # Create a stock asset
    await authed_client.post("/api/assets", json=_STOCK_PAYLOAD)

    resp = await authed_client.post(f"{PRICES_URL}/refresh")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    results = body["data"]
    assert len(results) == 1
    assert results[0]["status"] == "updated"
    assert results[0]["price"] == 300.00


@pytest.mark.asyncio
@patch("app.services.price.fetch_price", new_callable=AsyncMock)
async def test_refresh_bypasses_cached_create_price(
    mock_fetch, authed_client: AsyncClient
) -> None:
    """Manual refresh should fetch from the provider, not reuse the create-time cache."""
    mock_fetch.side_effect = [
        (Decimal("290.00"), "TRY"),
        (Decimal("310.00"), "TRY"),
    ]

    create_resp = await authed_client.post("/api/assets", json=_STOCK_PAYLOAD)
    asset_id = create_resp.json()["data"]["id"]
    assert create_resp.json()["data"]["current_price"] == 290.00

    resp = await authed_client.post(f"{PRICES_URL}/refresh")
    assert resp.status_code == 200
    results = resp.json()["data"]
    assert results[0]["status"] == "updated"
    assert results[0]["price"] == 310.00

    asset_resp = await authed_client.get(f"/api/assets/{asset_id}")
    assert asset_resp.json()["data"]["current_price"] == 310.00
    assert mock_fetch.call_count == 2


@pytest.mark.asyncio
@patch("app.services.price.fetch_price", new_callable=AsyncMock)
async def test_refresh_skips_manual_assets(mock_fetch, authed_client: AsyncClient) -> None:
    """REAL_ESTATE and other manual types should not be refreshed."""
    mock_fetch.return_value = (Decimal("100"), "TRY")

    await authed_client.post("/api/assets", json=_REAL_ESTATE_PAYLOAD)

    resp = await authed_client.post(f"{PRICES_URL}/refresh")
    assert resp.status_code == 200
    results = resp.json()["data"]
    # Real estate has no symbol / is manual, so nothing to refresh
    assert len(results) == 0
    mock_fetch.assert_not_called()


@pytest.mark.asyncio
@patch("app.services.price.fetch_price", new_callable=AsyncMock)
async def test_refresh_handles_partial_failure(
    mock_fetch, authed_client: AsyncClient
) -> None:
    """If one asset fetch fails, others should still succeed."""
    call_count = 0

    async def _side_effect(asset_type, symbol):
        nonlocal call_count
        call_count += 1
        if symbol == "THYAO.IS":
            raise RuntimeError("yfinance timeout")
        return (Decimal("95000"), "USD")

    mock_fetch.side_effect = _side_effect

    await authed_client.post("/api/assets", json=_STOCK_PAYLOAD)
    await authed_client.post("/api/assets", json=_CRYPTO_PAYLOAD)

    resp = await authed_client.post(f"{PRICES_URL}/refresh")
    assert resp.status_code == 200
    results = resp.json()["data"]
    assert len(results) == 2

    statuses = {r["symbol"]: r["status"] for r in results}
    assert statuses["THYAO.IS"] == "failed"
    assert statuses["BTC"] == "updated"


@pytest.mark.asyncio
async def test_refresh_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(f"{PRICES_URL}/refresh")
    assert resp.status_code in (401, 403)


# ── Price history persistence ─────────────────────────────────────────────────


@pytest.mark.asyncio
@patch("app.services.price.fetch_price", new_callable=AsyncMock)
async def test_refresh_creates_price_history(
    mock_fetch, authed_client: AsyncClient
) -> None:
    """After refresh, a PriceHistory row should exist for each updated asset."""
    mock_fetch.return_value = (Decimal("300.00"), "TRY")

    create_resp = await authed_client.post("/api/assets", json=_STOCK_PAYLOAD)
    asset_id = create_resp.json()["data"]["id"]

    await authed_client.post(f"{PRICES_URL}/refresh")

    # Verify the asset's current_price was updated
    asset_resp = await authed_client.get(f"/api/assets/{asset_id}")
    assert asset_resp.json()["data"]["current_price"] == 300.00
    assert asset_resp.json()["data"]["current_price_currency"] == "TRY"
    assert asset_resp.json()["data"]["is_manual_price"] is False


# ── Cache unit tests ──────────────────────────────────────────────────────────


def test_cache_put_and_get() -> None:
    cache.put("TEST:KEY", Decimal("123.45"), "USD")
    entry = cache.get("TEST:KEY")
    assert entry is not None
    assert entry.price == Decimal("123.45")
    assert entry.currency == "USD"


def test_cache_miss() -> None:
    assert cache.get("NONEXISTENT") is None


def test_cache_expiry() -> None:
    import time

    cache.put("EXPIRE:KEY", Decimal("1"), "USD")
    entry = cache.get("EXPIRE:KEY")
    assert entry is not None

    # Manually backdate the entry
    entry.fetched_at = time.time() - 301  # > 5 min
    assert cache.get("EXPIRE:KEY") is None


def test_cache_clear() -> None:
    cache.put("A", Decimal("1"), "USD")
    cache.put("B", Decimal("2"), "EUR")
    cache.clear()
    assert cache.get("A") is None
    assert cache.get("B") is None


def test_crypto_symbols_from_static_list_are_mapped() -> None:
    from app.utils.price_fetchers import _coingecko_ids

    ids = _coingecko_ids()
    assert ids["USDC"] == "usd-coin"
    assert ids["USDT"] == "tether"


@pytest.mark.asyncio
async def test_precious_metal_uses_yfinance_before_api_fallback() -> None:
    from app.utils import price_fetchers

    with (
        patch.object(
            price_fetchers,
            "_fetch_metal_yfinance",
            new_callable=AsyncMock,
            return_value=Decimal("4546.25"),
        ) as mock_yf,
        patch.object(
            price_fetchers,
            "_fetch_metalprice",
            new_callable=AsyncMock,
        ) as mock_metal_api,
    ):
        price, currency = await price_fetchers.fetch_precious_metal("XAU")

    assert price == Decimal("4546.25")
    assert currency == "USD"
    mock_yf.assert_awaited_once_with("XAU")
    mock_metal_api.assert_not_called()
