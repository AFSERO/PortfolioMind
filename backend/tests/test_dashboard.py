"""Tests for dashboard endpoints: summary, allocation, timeline, snapshot."""

import pytest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import UUID
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portfolio_snapshot import PortfolioSnapshot

DASHBOARD = "/api/dashboard"
ASSETS = "/api/assets"

# ── Fixture payloads ─────────────────────────────────────────────────────────

_STOCK = {
    "asset_type": "STOCK",
    "symbol": "THYAO.IS",
    "name": "THY",
    "current_price": "150",
    "current_price_currency": "TRY",
    "initial_transaction": {
        "transaction_type": "BUY",
        "quantity": "10",
        "price_per_unit": "100",
        "transaction_currency": "TRY",
        "transaction_date": "2024-01-01",
        "affects_cash": False,
    },
}

_CRYPTO = {
    "asset_type": "CRYPTO",
    "symbol": "BTC",
    "name": "Bitcoin",
    "current_price": "95000",
    "current_price_currency": "USD",
    "initial_transaction": {
        "transaction_type": "BUY",
        "quantity": "0.5",
        "price_per_unit": "50000",
        "transaction_currency": "USD",
        "transaction_date": "2024-01-10",
        "affects_cash": False,
    },
}

_REAL_ESTATE = {
    "asset_type": "REAL_ESTATE",
    "name": "Ev - Kadıköy",
    "current_price": "8000000",
    "current_price_currency": "TRY",
    "is_manual_price": True,
    "initial_transaction": {
        "transaction_type": "BUY",
        "quantity": "1",
        "price_per_unit": "5000000",
        "transaction_currency": "TRY",
        "transaction_date": "2022-03-01",
        "affects_cash": False,
    },
}


async def _seed(client: AsyncClient, *payloads) -> None:
    for p in payloads:
        resp = await client.post(ASSETS, json=p)
        assert resp.status_code == 201


# ── Auth guard ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_summary_requires_auth(client: AsyncClient) -> None:
    resp = await client.get(f"{DASHBOARD}/summary")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_allocation_requires_auth(client: AsyncClient) -> None:
    resp = await client.get(f"{DASHBOARD}/allocation")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_timeline_requires_auth(client: AsyncClient) -> None:
    resp = await client.get(f"{DASHBOARD}/timeline")
    assert resp.status_code in (401, 403)


# ── Summary: empty portfolio ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_summary_empty(authed_client: AsyncClient) -> None:
    resp = await authed_client.get(f"{DASHBOARD}/summary")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["asset_count"] == 0
    assert data["total_value"] == 0
    assert data["total_pl"] == 0
    assert data["best_performer"] is None
    assert data["worst_performer"] is None


# ── Summary: with assets ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_summary_single_asset(authed_client: AsyncClient) -> None:
    """Stock: bought 10 @ 100 TRY, current 150 TRY → value 1500, cost 1000, P/L +500."""
    await _seed(authed_client, _STOCK)

    resp = await authed_client.get(f"{DASHBOARD}/summary")
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["asset_count"] == 1
    assert data["total_value"] == 1500.0   # 150 * 10
    assert data["total_cost"] == 1000.0    # 100 * 10
    assert data["total_pl"] == 500.0
    assert data["total_pl_pct"] == 50.0    # 500/1000 * 100

    assert data["best_performer"]["name"] == "THY"
    assert data["best_performer"]["pl_pct"] == 50.0


@pytest.mark.asyncio
@patch("app.services.dashboard.build_rate_map", new_callable=AsyncMock)
async def test_summary_multiple_assets(
    mock_build_rate_map, authed_client: AsyncClient
) -> None:
    """Use a mocked 1:1 rate so assertions are environment-independent.

    Stock (TRY) + Crypto (USD at 1:1) + Real Estate (TRY) — with rate USD/TRY=1
    the numbers match the raw values, making the test deterministic regardless
    of whether a real forex API key is configured.
    """
    mock_build_rate_map.return_value = {"USD/TRY": Decimal("1")}

    await _seed(authed_client, _STOCK, _CRYPTO, _REAL_ESTATE)

    resp = await authed_client.get(f"{DASHBOARD}/summary")
    data = resp.json()["data"]

    assert data["asset_count"] == 3

    # Stock: value 1500, cost 1000, P/L +500, pct +50%
    # Crypto: value 47500, cost 25000, P/L +22500, pct +90%  (USD treated as TRY, rate=1)
    # RE: value 8000000, cost 5000000, P/L +3000000, pct +60%
    assert data["total_value"] == 1500 + 47500 + 8000000
    assert data["total_cost"] == 1000 + 25000 + 5000000
    assert data["total_pl"] == 500 + 22500 + 3000000

    # Best performer by percentage: CRYPTO at +90%
    assert data["best_performer"]["name"] == "Bitcoin"
    assert data["best_performer"]["pl_pct"] == 90.0

    # by_type_summary should have 3 types
    types = {t["asset_type"] for t in data["by_type_summary"]}
    assert types == {"STOCK", "CRYPTO", "REAL_ESTATE"}


@pytest.mark.asyncio
async def test_summary_no_current_price_falls_back(authed_client: AsyncClient) -> None:
    """When current_price is None, value should use purchase_price (P/L = 0)."""
    payload = {
        "asset_type": "FUND",
        "name": "Test Fund",
        "initial_transaction": {
            "transaction_type": "BUY",
            "quantity": "5",
            "price_per_unit": "1000",
            "transaction_currency": "TRY",
            "transaction_date": "2024-06-01",
            "affects_cash": False,
        },
    }
    await _seed(authed_client, payload)

    resp = await authed_client.get(f"{DASHBOARD}/summary")
    data = resp.json()["data"]
    assert data["total_value"] == 5000.0  # fallback: 1000 * 5
    assert data["total_pl"] == 0.0


# ── Allocation ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_allocation_empty(authed_client: AsyncClient) -> None:
    resp = await authed_client.get(f"{DASHBOARD}/allocation")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_value"] == 0
    assert data["by_type"] == []
    assert data["by_asset"] == []


@pytest.mark.asyncio
@patch("app.services.dashboard.build_rate_map", new_callable=AsyncMock)
async def test_allocation_percentages(
    mock_build_rate_map, authed_client: AsyncClient
) -> None:
    """Two assets with known values — check percentages add up to 100.

    Uses a mocked empty rate map (USD treated as TRY 1:1) so assertions are
    deterministic regardless of live forex rates.
    """
    mock_build_rate_map.return_value = {"USD/TRY": Decimal("1")}

    await _seed(authed_client, _STOCK, _CRYPTO)

    resp = await authed_client.get(f"{DASHBOARD}/allocation")
    data = resp.json()["data"]

    # Stock value: 1500, Crypto value: 47500 (USD treated as TRY, rate=1), total: 49000
    assert data["total_value"] == 49000.0

    type_pcts = sum(t["percentage"] for t in data["by_type"])
    assert abs(type_pcts - 100.0) < 0.01

    asset_pcts = sum(a["percentage"] for a in data["by_asset"])
    assert abs(asset_pcts - 100.0) < 0.01

    # Stock: 1500/49000 ≈ 3.06%
    stock_type = next(t for t in data["by_type"] if t["asset_type"] == "STOCK")
    assert 3.0 < stock_type["percentage"] < 3.2

    # Crypto: 47500/49000 ≈ 96.94%
    crypto_type = next(t for t in data["by_type"] if t["asset_type"] == "CRYPTO")
    assert 96.8 < crypto_type["percentage"] < 97.0


@pytest.mark.asyncio
async def test_allocation_by_asset_names(authed_client: AsyncClient) -> None:
    await _seed(authed_client, _STOCK, _REAL_ESTATE)

    resp = await authed_client.get(f"{DASHBOARD}/allocation")
    names = {a["name"] for a in resp.json()["data"]["by_asset"]}
    assert names == {"THY", "Ev - Kadıköy"}


# ── Timeline & Snapshots ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_timeline_empty(authed_client: AsyncClient) -> None:
    resp = await authed_client.get(f"{DASHBOARD}/timeline")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
@pytest.mark.usefixtures("forex_provider")
async def test_snapshot_creates_entry(authed_client: AsyncClient) -> None:
    await _seed(authed_client, _STOCK)

    resp = await authed_client.post(f"{DASHBOARD}/snapshot")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "snapshot_date" in data
    assert data["total_value_try"] == 1500.0  # stock is TRY-denominated


@pytest.mark.asyncio
@pytest.mark.usefixtures("forex_provider")
async def test_snapshot_appears_in_timeline(authed_client: AsyncClient) -> None:
    await _seed(authed_client, _STOCK)
    await authed_client.post(f"{DASHBOARD}/snapshot")

    resp = await authed_client.get(f"{DASHBOARD}/timeline")
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["total_value_try"] == 1500.0


@pytest.mark.asyncio
@pytest.mark.usefixtures("forex_provider")
async def test_snapshot_upsert_same_day(authed_client: AsyncClient) -> None:
    """Creating a snapshot twice on the same day should replace, not duplicate."""
    await _seed(authed_client, _STOCK)

    await authed_client.post(f"{DASHBOARD}/snapshot")
    await authed_client.post(f"{DASHBOARD}/snapshot")

    resp = await authed_client.get(f"{DASHBOARD}/timeline")
    assert len(resp.json()["data"]) == 1


@pytest.mark.asyncio
async def test_snapshot_no_assets(authed_client: AsyncClient) -> None:
    resp = await authed_client.post(f"{DASHBOARD}/snapshot")
    assert resp.status_code == 200
    assert resp.json()["data"]["message"] == "No assets to snapshot"


@pytest.mark.asyncio
@patch("app.services.dashboard.build_rate_map", new_callable=AsyncMock)
async def test_snapshot_mixed_currencies(
    mock_build_rate_map, authed_client: AsyncClient
) -> None:
    """Snapshot converts each asset to both TRY and USD using forex rates.

    We mock ``build_rate_map`` with 1 USD = 38 TRY so the expected values
    are deterministic regardless of the test environment's API access.
    """
    async def _fake_build(from_currencies, to_currency, db=None):
        if to_currency == "TRY":
            return {"USD/TRY": Decimal("38")}
        if to_currency == "USD":
            return {"TRY/USD": Decimal("1") / Decimal("38")}
        return {}

    mock_build_rate_map.side_effect = _fake_build

    await _seed(authed_client, _STOCK, _CRYPTO)

    resp = await authed_client.post(f"{DASHBOARD}/snapshot")
    data = resp.json()["data"]

    # Stock (1500 TRY) stays TRY.  Crypto (47500 USD × 38) = 1,805,000 TRY.
    expected_try = 1500.0 + 47500 * 38
    assert data["total_value_try"] == pytest.approx(expected_try, rel=1e-4)

    # Stock (1500 TRY ÷ 38 ≈ 39.47 USD).  Crypto (47500 USD) stays USD.
    expected_usd = 1500 / 38 + 47500.0
    assert data["total_value_usd"] == pytest.approx(expected_usd, rel=1e-3)


@pytest.mark.asyncio
async def test_timeline_days_param(authed_client: AsyncClient) -> None:
    resp = await authed_client.get(f"{DASHBOARD}/timeline", params={"days": 30})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_snapshot_requires_auth(client: AsyncClient) -> None:
    resp = await client.post(f"{DASHBOARD}/snapshot")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
@patch("app.services.dashboard.build_rate_map", new_callable=AsyncMock)
async def test_summary_missing_rate_returns_stable_error(
    mock_build_rate_map, authed_client: AsyncClient
) -> None:
    mock_build_rate_map.return_value = {}
    await _seed(authed_client, _CRYPTO)

    resp = await authed_client.get(f"{DASHBOARD}/summary")

    assert resp.status_code == 424
    assert resp.json() == {
        "status": "error",
        "message": "Required exchange rate is unavailable",
        "code": "exchange_rate_unavailable",
        "details": {"missing_rates": ["USD/TRY"]},
    }


@pytest.mark.asyncio
@patch("app.services.dashboard.build_rate_map", new_callable=AsyncMock)
async def test_allocation_missing_rate_does_not_return_partial_total(
    mock_build_rate_map, authed_client: AsyncClient
) -> None:
    mock_build_rate_map.return_value = {}
    await _seed(authed_client, _CRYPTO)

    resp = await authed_client.get(f"{DASHBOARD}/allocation")

    assert resp.status_code == 424
    assert "data" not in resp.json()


@pytest.mark.asyncio
@patch("app.services.dashboard.build_rate_map", new_callable=AsyncMock)
async def test_snapshot_missing_rate_is_not_persisted(
    mock_build_rate_map, authed_client: AsyncClient
) -> None:
    mock_build_rate_map.return_value = {}
    await _seed(authed_client, _CRYPTO)

    resp = await authed_client.post(f"{DASHBOARD}/snapshot")

    assert resp.status_code == 424
    timeline = await authed_client.get(f"{DASHBOARD}/timeline")
    assert timeline.json()["data"] == []


@pytest.mark.asyncio
@pytest.mark.usefixtures("forex_provider")
async def test_snapshot_today_and_same_day_upsert(authed_client: AsyncClient) -> None:
    """Verify creating today's snapshot is idempotent without duplicate rows."""
    await _seed(authed_client, _STOCK)
    today_iso = datetime.now(timezone.utc).date().isoformat()

    # Create today's snapshot
    resp1 = await authed_client.post(f"{DASHBOARD}/snapshot")
    assert resp1.status_code == 200
    data1 = resp1.json()["data"]
    assert data1["snapshot_date"] == today_iso
    assert data1["total_value_try"] == 1500.0

    # Call again on the same day (re-opening dashboard / idempotent behavior)
    resp2 = await authed_client.post(f"{DASHBOARD}/snapshot")
    assert resp2.status_code == 200
    data2 = resp2.json()["data"]
    assert data2["snapshot_date"] == today_iso

    # Verify timeline has only 1 snapshot (no duplicates)
    t_resp = await authed_client.get(f"{DASHBOARD}/timeline")
    assert t_resp.status_code == 200
    t_data = t_resp.json()["data"]
    assert len(t_data) == 1
    assert t_data[0]["date"] == today_iso


@pytest.mark.asyncio
async def test_timeline_timeframe_filters_and_order(
    authed_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify 7, 30, 90, 180, 365, 1825 filters return snapshots within cutoff and in ASC order."""
    me_resp = await authed_client.get("/api/auth/me")
    user_id = UUID(me_resp.json()["data"]["id"])
    today = datetime.now(timezone.utc).date()

    # Seed snapshots across various dates:
    # offset 0 (today), 5d ago, 6d ago (boundary of 7d), 7d ago (8th day back, excluded by days=7)
    # 20d ago, 60d ago, 120d ago, 200d ago, 500d ago
    offsets = [0, 5, 6, 7, 20, 60, 120, 200, 500]
    for offset in offsets:
        snap = PortfolioSnapshot(
            user_id=user_id,
            total_value_try=Decimal("10000") + Decimal(offset),
            total_value_usd=Decimal("300") + Decimal(offset),
            total_assets_try=Decimal("10000") + Decimal(offset),
            total_assets_usd=Decimal("300") + Decimal(offset),
            total_liabilities_try=Decimal("0"),
            total_liabilities_usd=Decimal("0"),
            net_worth_try=Decimal("10000") + Decimal(offset),
            net_worth_usd=Decimal("300") + Decimal(offset),
            snapshot_date=today - timedelta(days=offset),
        )
        db_session.add(snap)
    await db_session.commit()

    # 1W (7 days): exactly covers 7 calendar days [today - 6, today].
    # Offset 0, 5, 6 must be included (3 items). Offset 7 (8th calendar day back) must be EXCLUDED!
    resp_7 = await authed_client.get(f"{DASHBOARD}/timeline", params={"days": 7})
    assert resp_7.status_code == 200
    dates_7 = [d["date"] for d in resp_7.json()["data"]]
    assert len(dates_7) == 3
    assert dates_7 == sorted(dates_7)
    assert dates_7 == [
        (today - timedelta(days=6)).isoformat(),
        (today - timedelta(days=5)).isoformat(),
        today.isoformat(),
    ]
    # Ensure offset 7 is NOT included in 7-day filter
    assert (today - timedelta(days=7)).isoformat() not in dates_7

    # 1M (30 days): covers [today - 29, today] -> offsets 0, 5, 6, 7, 20
    resp_30 = await authed_client.get(f"{DASHBOARD}/timeline", params={"days": 30})
    assert resp_30.status_code == 200
    dates_30 = [d["date"] for d in resp_30.json()["data"]]
    assert len(dates_30) == 5
    assert dates_30 == sorted(dates_30)

    # 3M (90 days): covers offsets 0, 5, 6, 7, 20, 60
    resp_90 = await authed_client.get(f"{DASHBOARD}/timeline", params={"days": 90})
    assert resp_90.status_code == 200
    dates_90 = [d["date"] for d in resp_90.json()["data"]]
    assert len(dates_90) == 6
    assert dates_90 == sorted(dates_90)

    # 6M (180 days): covers offsets 0, 5, 6, 7, 20, 60, 120
    resp_180 = await authed_client.get(f"{DASHBOARD}/timeline", params={"days": 180})
    assert resp_180.status_code == 200
    dates_180 = [d["date"] for d in resp_180.json()["data"]]
    assert len(dates_180) == 7
    assert dates_180 == sorted(dates_180)

    # 1Y (365 days): covers offsets 0, 5, 6, 7, 20, 60, 120, 200
    resp_365 = await authed_client.get(f"{DASHBOARD}/timeline", params={"days": 365})
    assert resp_365.status_code == 200
    dates_365 = [d["date"] for d in resp_365.json()["data"]]
    assert len(dates_365) == 8
    assert dates_365 == sorted(dates_365)

    # ALL (1825 days): should return all 9 snapshots without 422 error
    resp_1825 = await authed_client.get(f"{DASHBOARD}/timeline", params={"days": 1825})
    assert resp_1825.status_code == 200
    dates_1825 = [d["date"] for d in resp_1825.json()["data"]]
    assert len(dates_1825) == 9
    assert dates_1825 == sorted(dates_1825)


@pytest.mark.asyncio
async def test_timeline_returns_most_recent_window_not_oldest(
    authed_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify that get_timeline does NOT return oldest records when limit is applied."""
    me_resp = await authed_client.get("/api/auth/me")
    user_id = UUID(me_resp.json()["data"]["id"])
    today = datetime.now(timezone.utc).date()

    # Insert an old snapshot from 100 days ago, and a recent one from 2 days ago
    for offset in [100, 2]:
        snap = PortfolioSnapshot(
            user_id=user_id,
            total_value_try=Decimal("5000"),
            total_value_usd=Decimal("150"),
            total_assets_try=Decimal("5000"),
            total_assets_usd=Decimal("150"),
            net_worth_try=Decimal("5000"),
            net_worth_usd=Decimal("150"),
            snapshot_date=today - timedelta(days=offset),
        )
        db_session.add(snap)
    await db_session.commit()

    # Query for days=7: must return the 2-day-old snapshot and NEVER the 100-day-old one
    resp = await authed_client.get(f"{DASHBOARD}/timeline", params={"days": 7})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["date"] == (today - timedelta(days=2)).isoformat()


@pytest.mark.asyncio
@pytest.mark.usefixtures("forex_provider")
async def test_concurrent_snapshot_creation_no_race_condition(
    authed_client: AsyncClient,
) -> None:
    """Verify concurrent snapshot creation requests (e.g. multi-tab) do not crash with unique violation."""
    import asyncio
    await _seed(authed_client, _STOCK)

    # Fire two concurrent POST /api/dashboard/snapshot requests simultaneously
    responses = await asyncio.gather(
        authed_client.post(f"{DASHBOARD}/snapshot"),
        authed_client.post(f"{DASHBOARD}/snapshot"),
    )

    # Both requests must succeed (status 200) without 500 or UniqueViolation
    assert responses[0].status_code == 200
    assert responses[1].status_code == 200

    # Ensure timeline has exactly 1 entry for today
    t_resp = await authed_client.get(f"{DASHBOARD}/timeline")
    assert t_resp.status_code == 200
    assert len(t_resp.json()["data"]) == 1

