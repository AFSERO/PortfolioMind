"""Tests for Turkish investment funds (TEFAS provider, endpoints, and asset integration)."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient

from app.models.asset import Asset, AssetType
from app.models.price_history import PriceHistory
from app.providers import get_fund_provider
from app.providers.base import FundMetadata
from app.providers.tefas import TefasFundProvider


# ── Provider Unit Tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tefas_provider_parses_success():
    provider = TefasFundProvider()

    mock_rows = [
        {
            "fonKodu": "KCV",
            "fonUnvan": "KUVEYT TÜRK PORTFÖY ÇOKLU VARLIK KATILIM FONU",
            "tarih": "2026-09-14",
            "fiyat": 5.28,
        },
        {
            "fonKodu": "KCV",
            "fonUnvan": "KUVEYT TÜRK PORTFÖY ÇOKLU VARLIK KATILIM FONU",
            "tarih": "2026-09-15",
            "fiyat": 5.29265,
        },
    ]

    with patch.object(provider, "_query_tefas_code", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = mock_rows
        meta = await provider.get_fund_info("KCV")

        assert meta.fund_code == "KCV"
        assert meta.fund_name == "KUVEYT TÜRK PORTFÖY ÇOKLU VARLIK KATILIM FONU"
        assert meta.price == Decimal("5.29265")
        assert meta.currency == "TRY"
        assert meta.price_date == date(2026, 9, 15)
        assert meta.provider == "TEFAS"


@pytest.mark.asyncio
async def test_tefas_provider_invalid_fund_raises_value_error():
    provider = TefasFundProvider()

    with patch.object(provider, "_query_tefas_code", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = []
        with pytest.raises(ValueError, match="Fund 'INVALID' not found on TEFAS"):
            await provider.get_fund_info("INVALID")


@pytest.mark.asyncio
async def test_tefas_provider_search():
    provider = TefasFundProvider()

    mock_catalog = [
        {"symbol": "KCV", "name": "KUVEYT TÜRK PORTFÖY ÇOKLU VARLIK KATILIM FONU", "price": 5.29},
        {"symbol": "THF", "name": "TERA PORTFÖY HİSSE SENEDİ FONU", "price": 2.83},
        {"symbol": "MAC", "name": "MARMARA CAPITAL HİSSE FONU", "price": 0.74},
    ]

    with patch.object(provider, "_get_fund_catalog", new_callable=AsyncMock) as mock_cat:
        mock_cat.return_value = mock_catalog
        res = await provider.search_funds("KCV")
        assert len(res) == 1
        assert res[0]["symbol"] == "KCV"

        res_tera = await provider.search_funds("TERA")
        assert len(res_tera) == 1
        assert res_tera[0]["symbol"] == "THF"


@pytest.mark.asyncio
async def test_tefas_provider_history():
    provider = TefasFundProvider()

    mock_rows = [
        {"fonKodu": "THF", "tarih": "2026-09-15", "fiyat": 2.85},
        {"fonKodu": "THF", "tarih": "2026-09-14", "fiyat": 2.80},
    ]

    with patch.object(provider, "_query_tefas_code", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = mock_rows
        history = await provider.get_fund_history("THF", days=5)
        assert len(history) == 2
        # History is returned chronologically ascending
        assert history[0]["date"] == "2026-09-14"
        assert history[0]["price"] == Decimal("2.80")
        assert history[1]["date"] == "2026-09-15"
        assert history[1]["price"] == Decimal("2.85")


# ── API Endpoint Tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_fund_info_endpoint(client: AsyncClient):
    mock_meta = FundMetadata(
        fund_code="KCV",
        fund_name="KUVEYT TÜRK PORTFÖY ÇOKLU VARLIK KATILIM FONU",
        price=Decimal("5.29265"),
        currency="TRY",
        price_date=date(2026, 9, 15),
        provider="TEFAS",
    )

    with patch("app.providers.tefas.TefasFundProvider.get_fund_info", new_callable=AsyncMock) as mock_info:
        mock_info.return_value = mock_meta
        resp = await client.get("/api/funds/info/KCV")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        data = body["data"]
        assert data["fund_code"] == "KCV"
        assert data["fund_name"] == "KUVEYT TÜRK PORTFÖY ÇOKLU VARLIK KATILIM FONU"
        assert data["price"] == 5.29265
        assert data["currency"] == "TRY"
        assert data["price_date"] == "2026-09-15"


@pytest.mark.asyncio
async def test_get_fund_info_endpoint_not_found(client: AsyncClient):
    with patch("app.providers.tefas.TefasFundProvider.get_fund_info", new_callable=AsyncMock) as mock_info:
        mock_info.side_effect = ValueError("Fund 'INVALID' not found on TEFAS")
        resp = await client.get("/api/funds/info/INVALID")
        assert resp.status_code == 404
        body = resp.json()
        assert body["status"] == "error"
        assert "not found" in body["message"].lower()


@pytest.mark.asyncio
async def test_search_funds_via_symbols_endpoint(client: AsyncClient):
    mock_results = [
        {"symbol": "THF", "name": "TERA PORTFÖY HİSSE SENEDİ FONU", "price": 2.83}
    ]

    with patch("app.providers.tefas.TefasFundProvider.search_funds", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_results
        resp = await client.get("/api/symbols/search?type=fund&q=THF")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert len(body["data"]) == 1
        assert body["data"][0]["symbol"] == "THF"


@pytest.mark.asyncio
async def test_live_price_fund_endpoint(client: AsyncClient):
    with patch("app.services.price.fetch_price", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = (Decimal("2.8332"), "TRY")
        resp = await client.get("/api/prices/live/THF?asset_type=FUND")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "success"
        assert body["data"]["symbol"] == "THF"
        assert body["data"]["price"] == 2.8332
        assert body["data"]["currency"] == "TRY"


# ── Asset Integration Tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_fund_asset_with_auto_price_and_history(
    authed_client: AsyncClient,
):
    mock_history = [
        {"date": "2026-09-12", "price": Decimal("5.25"), "currency": "TRY"},
        {"date": "2026-09-15", "price": Decimal("5.29265"), "currency": "TRY"},
    ]

    with patch("app.services.price.fetch_price", new_callable=AsyncMock) as mock_fetch, \
         patch("app.providers.tefas.TefasFundProvider.get_fund_history", new_callable=AsyncMock) as mock_hist:
        mock_fetch.return_value = (Decimal("5.29265"), "TRY")
        mock_hist.return_value = mock_history

        payload = {
            "asset_type": "FUND",
            "symbol": "KCV",
            "name": "KUVEYT TÜRK PORTFÖY ÇOKLU VARLIK KATILIM FONU",
            "initial_transaction": {
                "transaction_type": "BUY",
                "quantity": 1000,
                "price_per_unit": 5.20,
                "transaction_currency": "TRY",
                "affects_cash": False,
            },
        }

        resp = await authed_client.post("/api/assets", json=payload)
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["asset_type"] == "FUND"
        assert data["symbol"] == "KCV"
        assert data["total_quantity"] == 1000.0
        assert data["current_price"] == 5.29265
        assert data["current_price_currency"] == "TRY"
        assert data["is_manual_price"] is False

        asset_id = data["id"]

        # Verify price history endpoint returns seeded points + current point
        hist_resp = await authed_client.get(f"/api/assets/{asset_id}/price-history")
        assert hist_resp.status_code == 200
        hist_data = hist_resp.json()["data"]
        assert len(hist_data) >= 2

        # Verify dashboard summary includes the fund
        dash_resp = await authed_client.get("/api/dashboard/summary")
        assert dash_resp.status_code == 200
        summary = dash_resp.json()["data"]
        assert summary["total_value"] > 0
        # Check fund type bucket
        fund_bucket = next(
            (b for b in summary["by_type_summary"] if b["asset_type"] == "FUND"),
            None,
        )
        assert fund_bucket is not None
        assert fund_bucket["count"] == 1
        assert fund_bucket["total_value"] == 5292.65


@pytest.mark.asyncio
async def test_tefas_http_contract_kcv_and_thf():
    """Exercise the real provider's HTTP payload and parsing without live data."""
    import json
    import httpx
    from datetime import datetime
    def response(request):
        assert request.method == "POST"
        assert request.url.host == "www.tefas.gov.tr"
        payload = json.loads(request.content)
        assert payload["fonTipi"] == "YAT"
        assert payload["basTarih"] == "20260905"
        assert payload["bitTarih"] == "20260915"
        code = payload["fonKodu"]
        name = "KUVEYT Test Fund" if code == "KCV" else "TERA Test Fund"
        return httpx.Response(200, json={"resultList":[
            {"fonKodu":code,"fonUnvan":name,"tarih":"2026-09-14","fiyat":"5.25"},
            {"fonKodu":code,"fonUnvan":name,"tarih":"2026-09-15","fiyat":0},
        ]})
    provider = TefasFundProvider(transport=httpx.MockTransport(response))
    with patch("app.providers.tefas.datetime", wraps=datetime) as clock:
        clock.now.return_value = datetime(2026, 9, 15)
        for code in ("KCV", "THF"):
            meta = await provider.get_fund_info(code)
            assert meta.fund_code == code
            assert meta.price == Decimal("5.25")
            assert meta.price_date == date(2026, 9, 14)
            assert meta.currency == "TRY"


@pytest.mark.asyncio
@pytest.mark.parametrize("price", [0, -1, None, "invalid", "NaN", "Infinity"])
async def test_tefas_invalid_quotes_are_never_usable_or_cached(price):
    provider = TefasFundProvider()
    with patch.object(provider, "_query_tefas_code", new_callable=AsyncMock) as query:
        query.return_value = [{"fonKodu":"SYN", "tarih":"2026-09-15", "fiyat":price}]
        with pytest.raises(ValueError, match="valid positive price"):
            await provider.get_fund_info("SYN")
    assert "SYN" not in provider._info_cache


@pytest.mark.asyncio
async def test_invalid_fund_quote_is_upstream_failure_not_missing_fund(client):
    provider = TefasFundProvider()
    with patch.object(provider, "_query_tefas_code", new_callable=AsyncMock) as query, \
         patch("app.routers.funds.get_fund_provider", return_value=provider):
        query.return_value = [{"fonKodu":"SYN","tarih":"2026-09-15","fiyat":0}]
        response = await client.get("/api/funds/info/SYN")
    assert response.status_code == 502
    assert response.json()["status"] == "error"
    assert "data" not in response.json()
