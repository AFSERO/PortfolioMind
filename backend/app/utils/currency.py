"""Fail-closed currency conversion and exchange-rate freshness helpers."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Mapping, Optional

from app.utils import cache

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_CACHE_PREFIX = "FOREX:"


class ExchangeRateNotFoundError(ValueError):
    """Raised when a cross-currency calculation lacks a valid rate."""

    def __init__(self, missing_pairs: set[str] | list[str] | tuple[str, ...]):
        self.missing_pairs = tuple(sorted(set(missing_pairs)))
        super().__init__("Required exchange rate is unavailable")


@dataclass(slots=True)
class ExchangeRateTable:
    """Rates plus source timestamps and explicit stale/missing state."""

    rates: dict[str, Decimal] = field(default_factory=dict)
    fetched_at: dict[str, datetime] = field(default_factory=dict)
    stale_pairs: set[str] = field(default_factory=set)
    missing_pairs: set[str] = field(default_factory=set)

    def get(self, key: str) -> Optional[Decimal]:
        return self.rates.get(key)


RateMap = Mapping[str, Decimal] | ExchangeRateTable


def _is_valid_rate(rate: Optional[Decimal]) -> bool:
    return rate is not None and rate.is_finite() and rate > 0


def _source_time(timestamp: float) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


async def build_rate_map(
    from_currencies: set[str],
    to_currency: str,
    db: Optional["AsyncSession"] = None,
) -> ExchangeRateTable:
    """Resolve required rates from memory, DB, live API, then stale DB fallback.

    Missing and invalid rates are recorded instead of silently becoming 1:1.
    A stale DB rate remains usable but is marked so API consumers can distinguish
    it from a fresh rate and from a completely unavailable rate.
    """
    from app.utils.price_fetchers import fetch_forex

    table = ExchangeRateTable()
    to_currency = to_currency.upper()

    for raw_from_cur in from_currencies:
        from_cur = raw_from_cur.upper() if raw_from_cur else raw_from_cur
        if not from_cur or from_cur == to_currency:
            continue

        pair = f"{from_cur}/{to_currency}"
        cache_key = f"{_CACHE_PREFIX}{pair}".upper()

        cached = cache.get(cache_key)
        if cached is not None and _is_valid_rate(cached.price):
            table.rates[pair] = cached.price
            timestamp = cached.source_fetched_at or cached.fetched_at
            source_at = _source_time(timestamp)
            table.fetched_at[pair] = source_at
            if datetime.now(timezone.utc) - source_at > timedelta(hours=24):
                table.stale_pairs.add(pair)
            continue

        db_row = None
        if db is not None:
            from app.services.forex_cache import get_db_rate_row, is_rate_fresh

            db_row = await get_db_rate_row(db, from_cur, to_currency)
            if (
                db_row is not None
                and is_rate_fresh(db_row)
                and _is_valid_rate(db_row.rate)
            ):
                source_at = db_row.fetched_at
                if source_at.tzinfo is None:
                    source_at = source_at.replace(tzinfo=timezone.utc)
                cache.put(
                    cache_key,
                    db_row.rate,
                    to_currency,
                    source_fetched_at=source_at.timestamp(),
                )
                table.rates[pair] = db_row.rate
                table.fetched_at[pair] = source_at
                continue

        try:
            rate, _ = await fetch_forex(pair)
            if not _is_valid_rate(rate):
                raise ValueError("Provider returned a non-positive exchange rate")

            fetched_at = datetime.now(timezone.utc)
            cache.put(
                cache_key,
                rate,
                to_currency,
                source_fetched_at=fetched_at.timestamp(),
            )
            if db is not None:
                from app.services.forex_cache import upsert_rate

                await upsert_rate(db, from_cur, to_currency, rate)
            table.rates[pair] = rate
            table.fetched_at[pair] = fetched_at
        except Exception as exc:
            if db_row is not None and _is_valid_rate(db_row.rate):
                source_at = db_row.fetched_at
                if source_at.tzinfo is None:
                    source_at = source_at.replace(tzinfo=timezone.utc)
                table.rates[pair] = db_row.rate
                table.fetched_at[pair] = source_at
                table.stale_pairs.add(pair)
                logger.warning("Using stale exchange rate for %s", pair)
            else:
                table.missing_pairs.add(pair)
                logger.warning(
                    "Cannot retrieve a valid exchange rate for %s: %s", pair, exc
                )

    return table


def require_rates(
    from_currencies: set[str], to_currency: str, rate_map: RateMap
) -> None:
    """Raise once with every missing/invalid cross-currency pair."""
    missing = set(getattr(rate_map, "missing_pairs", set()))
    to_currency = to_currency.upper()
    for raw_from_cur in from_currencies:
        from_cur = raw_from_cur.upper() if raw_from_cur else raw_from_cur
        if not from_cur or from_cur == to_currency:
            continue
        pair = f"{from_cur}/{to_currency}"
        if not _is_valid_rate(rate_map.get(pair)):
            missing.add(pair)
    if missing:
        raise ExchangeRateNotFoundError(missing)


def exchange_rate_metadata(rate_map: RateMap) -> dict:
    """Return freshness metadata without exposing rate values."""
    if not isinstance(rate_map, ExchangeRateTable):
        return {"status": "complete", "rates": []}
    return {
        "status": "stale" if rate_map.stale_pairs else "complete",
        "rates": [
            {
                "pair": pair,
                "fetched_at": rate_map.fetched_at[pair].isoformat()
                if pair in rate_map.fetched_at
                else None,
                "stale": pair in rate_map.stale_pairs,
            }
            for pair in sorted(rate_map.rates)
        ],
    }


def convert(
    amount: Decimal,
    from_cur: str,
    to_cur: str,
    rate_map: RateMap,
) -> Decimal:
    """Convert an amount, failing closed when a cross rate is invalid or absent."""
    from_cur = from_cur.upper()
    to_cur = to_cur.upper()
    if from_cur == to_cur:
        return amount

    pair = f"{from_cur}/{to_cur}"
    rate = rate_map.get(pair)
    if not _is_valid_rate(rate):
        raise ExchangeRateNotFoundError({pair})
    return amount * rate
