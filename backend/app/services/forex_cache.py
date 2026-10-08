"""Forex rate caching service — three-layer strategy.

Layer 1 — In-memory (5-min TTL):  handled by ``app.utils.cache``
Layer 2 — Database  (24-h TTL):   ``forex_rates`` table via this module
Layer 3 — Live API:               ``fetch_forex`` in ``price_fetchers``

Typical read flow (``build_rate_map`` in ``currency.py``):
    in-memory hit → return
    DB row < 24 h  → populate memory cache → return
    else           → fetch from API → save to DB → populate memory cache → return

Write endpoints:
    ``GET  /api/prices/forex-rates``         — read current rates (auto-populates DB)
    ``POST /api/prices/forex-rates/refresh`` — force-refresh all standard pairs from API
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.forex_rate import ForexRate
from app.utils import cache

logger = logging.getLogger(__name__)

# Pairs to pre-populate and return via the public endpoint.
# Format: (base, target) — the rate stored is base→target.
STANDARD_PAIRS: list[tuple[str, str]] = [
    ("USD", "TRY"),
    ("EUR", "TRY"),
    ("GBP", "TRY"),
    ("EUR", "USD"),
]

_DB_MAX_AGE_HOURS = 24
_MEMORY_CACHE_PREFIX = "FOREX:"


# ---------------------------------------------------------------------------
# Internal DB helpers
# ---------------------------------------------------------------------------

async def get_db_rate_row(
    db: AsyncSession, base: str, target: str
) -> Optional[ForexRate]:
    """Return the ForexRate row for (base, target), or None if absent."""
    result = await db.execute(
        select(ForexRate)
        .where(ForexRate.base_currency == base, ForexRate.target_currency == target)
    )
    return result.scalar_one_or_none()


async def upsert_rate(
    db: AsyncSession,
    base: str,
    target: str,
    rate: Decimal,
) -> ForexRate:
    """Insert or update a forex rate row and commit immediately."""
    now = datetime.now(timezone.utc)
    if not rate.is_finite() or rate <= 0:
        raise ValueError("Exchange rate must be finite and greater than zero")
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        insert = pg_insert
    elif dialect == "sqlite":
        insert = sqlite_insert
    else:
        raise RuntimeError("Atomic forex upsert requires PostgreSQL or SQLite")
    statement = insert(ForexRate).values(
        base_currency=base, target_currency=target, rate=rate, fetched_at=now
    )
    statement = statement.on_conflict_do_update(
        index_elements=[ForexRate.base_currency, ForexRate.target_currency],
        set_={"rate": statement.excluded.rate, "fetched_at": statement.excluded.fetched_at},
    ).returning(ForexRate)
    row = (await db.execute(
        statement, execution_options={"populate_existing": True}
    )).scalar_one()
    await db.commit()
    await db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Read helpers used by build_rate_map
# ---------------------------------------------------------------------------

async def get_fresh_db_rate(
    db: AsyncSession,
    base: str,
    target: str,
) -> Optional[Decimal]:
    """Return rate from DB if it was fetched within the last 24 hours, else None."""
    row = await get_db_rate_row(db, base, target)
    if row is None:
        return None
    if not is_rate_fresh(row):
        return None
    if not row.rate.is_finite() or row.rate <= 0:
        return None
    return row.rate


def is_rate_fresh(row: ForexRate) -> bool:
    fetched_at = row.fetched_at
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - fetched_at <= timedelta(
        hours=_DB_MAX_AGE_HOURS
    )


# ---------------------------------------------------------------------------
# Bulk operations used by the public API endpoints
# ---------------------------------------------------------------------------

async def refresh_all_rates(db: AsyncSession) -> list[dict]:
    """Fetch every STANDARD_PAIRS rate from ExchangeRate-API and persist to DB.

    Returns a list of per-pair status dicts.
    """
    from app.utils.price_fetchers import fetch_forex

    results = []
    for base, target in STANDARD_PAIRS:
        pair = f"{base}/{target}"
        try:
            rate, _ = await fetch_forex(pair)
            await upsert_rate(db, base, target, rate)
            # Warm the memory cache too
            cache.put(f"{_MEMORY_CACHE_PREFIX}{pair}".upper(), rate, target)
            results.append({"pair": pair, "rate": float(rate), "status": "updated"})
            logger.info("Forex rate refreshed: %s = %.6f", pair, rate)
        except Exception as exc:
            logger.warning("Failed to refresh forex rate %s: %s", pair, exc)
            results.append({"pair": pair, "status": "failed", "error": str(exc)})
    return results


async def get_all_current_rates(db: AsyncSession) -> dict[str, float]:
    """Return all STANDARD_PAIRS rates as a plain dict ``{"USD/TRY": 44.5, ...}``.

    For each pair the lookup order is:
    1. In-memory cache  (5-min TTL)
    2. DB cache         (24-h TTL)
    3. Live API         (also saves to DB + memory cache)
    """
    from app.utils.price_fetchers import fetch_forex

    rates: dict[str, float] = {}

    for base, target in STANDARD_PAIRS:
        pair = f"{base}/{target}"
        cache_key = f"{_MEMORY_CACHE_PREFIX}{pair}".upper()

        # Layer 1 — memory cache
        cached = cache.get(cache_key)
        if cached is not None:
            rates[pair] = float(cached.price)
            continue

        # Layer 2 — DB cache
        db_rate = await get_fresh_db_rate(db, base, target)
        if db_rate is not None:
            cache.put(cache_key, db_rate, target)
            rates[pair] = float(db_rate)
            continue

        # Layer 3 — live API
        try:
            rate, _ = await fetch_forex(pair)
            await upsert_rate(db, base, target, rate)
            cache.put(cache_key, rate, target)
            rates[pair] = float(rate)
        except Exception as exc:
            logger.warning("Cannot retrieve forex rate %s: %s", pair, exc)
            # Omit the pair — frontend falls back gracefully

    return rates
