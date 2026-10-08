"""Fail-closed currency conversion contract tests."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.forex_rate import ForexRate
from app.utils.currency import (
    ExchangeRateNotFoundError,
    build_rate_map,
    convert,
    exchange_rate_metadata,
)


def test_same_currency_conversion_is_one_to_one() -> None:
    assert convert(Decimal("125.50"), "TRY", "TRY", {}) == Decimal("125.50")


def test_cross_currency_conversion_uses_positive_rate() -> None:
    assert convert(
        Decimal("100"), "USD", "TRY", {"USD/TRY": Decimal("42.5")}
    ) == Decimal("4250.0")


@pytest.mark.parametrize("rate", [None, Decimal("0"), Decimal("-1")])
def test_missing_or_non_positive_cross_rate_is_rejected(rate: Decimal | None) -> None:
    rates = {} if rate is None else {"USD/TRY": rate}

    with pytest.raises(ExchangeRateNotFoundError) as exc_info:
        convert(Decimal("100"), "USD", "TRY", rates)

    assert exc_info.value.missing_pairs == ("USD/TRY",)


@pytest.mark.asyncio
@patch("app.utils.price_fetchers.fetch_forex", new_callable=AsyncMock)
async def test_stale_db_rate_is_distinct_from_missing_rate(
    mock_fetch: AsyncMock, db_session: AsyncSession
) -> None:
    mock_fetch.side_effect = RuntimeError("provider unavailable")
    fetched_at = datetime.now(timezone.utc) - timedelta(days=2)
    db_session.add(
        ForexRate(
            base_currency="USD",
            target_currency="TRY",
            rate=Decimal("40"),
            fetched_at=fetched_at,
        )
    )
    await db_session.commit()

    rate_map = await build_rate_map({"USD"}, "TRY", db_session)

    assert convert(Decimal("100"), "USD", "TRY", rate_map) == Decimal("4000")
    metadata = exchange_rate_metadata(rate_map)
    assert metadata["status"] == "stale"
    assert metadata["rates"][0]["pair"] == "USD/TRY"
    assert metadata["rates"][0]["stale"] is True
