"""Tests for the unified AssetResolver and /api/symbols search and resolve endpoints."""

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.providers.base import FundMetadata
from app.utils import cache


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.asyncio
async def test_search_stock_by_name_and_symbol(client: AsyncClient):
    # Search by ticker
    resp = await client.get("/api/symbols/search?type=stock&q=NVDA")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert any(item["symbol"] == "NVDA" and item["currency"] == "USD" for item in data)

    # Search by name
    resp2 = await client.get("/api/symbols/search?type=stock&q=Nvidia")
    assert resp2.status_code == 200
    data2 = resp2.json()["data"]
    assert any(item["symbol"] == "NVDA" for item in data2)


@pytest.mark.asyncio
async def test_search_bist_stock_by_name_and_symbol(client: AsyncClient):
    # Search by BIST ticker
    resp = await client.get("/api/symbols/search?type=stock&q=THYAO")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert any(item["symbol"] == "THYAO" and item["market"] == "BIST" and item["currency"] == "TRY" for item in data)

    # Search by company name
    resp2 = await client.get("/api/symbols/search?type=stock&q=Hava")
    assert resp2.status_code == 200
    data2 = resp2.json()["data"]
    assert any(item["symbol"] == "THYAO" for item in data2)


@pytest.mark.asyncio
async def test_search_crypto_by_name_and_symbol(client: AsyncClient):
    # Search by ticker
    resp = await client.get("/api/symbols/search?type=crypto&q=BTC")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert any(item["symbol"] == "BTC" and item["name"] == "Bitcoin" for item in data)

    # Search by name
    resp2 = await client.get("/api/symbols/search?type=crypto&q=Bitcoin")
    assert resp2.status_code == 200
    data2 = resp2.json()["data"]
    assert any(item["symbol"] == "BTC" for item in data2)


@pytest.mark.asyncio
async def test_search_precious_metals(client: AsyncClient):
    resp = await client.get("/api/symbols/search?type=precious_metals&q=Gold")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert any(item["symbol"] == "GR" for item in data)
    assert any(item["symbol"] == "XAU" for item in data)


@pytest.mark.asyncio
async def test_resolve_us_stock(client: AsyncClient):
    with patch("app.services.asset_resolver.fetch_stock", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (Decimal("135.50"), "USD")
        resp = await client.get("/api/symbols/resolve?type=stock&symbol=NVDA")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        data = body["data"]
        assert data["symbol"] == "NVDA"
        assert data["name"] == "NVIDIA Corporation"
        assert data["asset_type"] == "STOCK"
        assert data["currency"] == "USD"
        assert data["latest_price"] == 135.50
        assert data["market"] == "NASDAQ"
        assert data["provider"] == "yfinance"


@pytest.mark.asyncio
async def test_resolve_bist_stock_clean_symbol(client: AsyncClient):
    with patch("app.services.asset_resolver.fetch_stock", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (Decimal("292.00"), "TRY")
        resp = await client.get("/api/symbols/resolve?type=stock&symbol=THYAO")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        data = body["data"]
        assert data["symbol"] == "THYAO"  # clean user-facing symbol without .IS
        assert data["name"] == "Türk Hava Yolları"
        assert data["currency"] == "TRY"
        assert data["latest_price"] == 292.00
        assert data["market"] == "BIST"


@pytest.mark.asyncio
async def test_resolve_crypto_canonical_id(client: AsyncClient):
    with patch("app.services.asset_resolver.fetch_crypto", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (Decimal("65000.00"), "USD")
        resp = await client.get("/api/symbols/resolve?type=crypto&symbol=BTC")
        assert resp.status_code == 200
        body = resp.json()
        data = body["data"]
        assert data["symbol"] == "BTC"
        assert data["name"] == "Bitcoin"
        assert data["asset_type"] == "CRYPTO"
        assert data["currency"] == "USD"
        assert data["latest_price"] == 65000.00
        assert data["provider_id"] == "bitcoin"


@pytest.mark.asyncio
async def test_resolve_fund_tefas(client: AsyncClient):
    mock_meta = FundMetadata(
        fund_code="KCV",
        fund_name="KUVEYT TÜRK PORTFÖY ÇOKLU VARLIK KATILIM FONU",
        price=Decimal("5.289166"),
        currency="TRY",
        provider="TEFAS",
    )
    with patch("app.providers.tefas.TefasFundProvider.get_fund_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = mock_meta
        resp = await client.get("/api/symbols/resolve?type=fund&symbol=KCV")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["symbol"] == "KCV"
        assert data["name"] == "KUVEYT TÜRK PORTFÖY ÇOKLU VARLIK KATILIM FONU"
        assert data["asset_type"] == "FUND"
        assert data["currency"] == "TRY"
        assert data["latest_price"] == 5.289166
        assert data["market"] == "TEFAS"


@pytest.mark.asyncio
async def test_resolve_precious_metal(client: AsyncClient):
    with patch("app.services.asset_resolver.fetch_precious_metal", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (Decimal("139.50"), "USD")
        resp = await client.get("/api/symbols/resolve?type=precious_metals&symbol=GR")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["symbol"] == "GR"
        assert "Gram Altın" in data["name"]
        assert data["currency"] == "USD"
        assert data["latest_price"] == 139.50
        assert data["market"] == "Precious Metals"


@pytest.mark.asyncio
async def test_resolve_invalid_symbol_returns_404(client: AsyncClient):
    with patch("app.services.asset_resolver.fetch_stock", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = ValueError("yfinance returned no price")
        resp = await client.get("/api/symbols/resolve?type=stock&symbol=ASSET_DOES_NOT_EXIST_92831")
        assert resp.status_code == 404
        body = resp.json()
        assert body["status"] == "error"
        assert "ASSET_DOES_NOT_EXIST_92831" in body["message"]
