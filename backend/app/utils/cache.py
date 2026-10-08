"""Simple in-memory TTL cache for price lookups.

Each entry expires after TTL_SECONDS (default 300 = 5 min).
Thread-safe via a simple dict — fine for single-process uvicorn.
"""

import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

TTL_SECONDS = 300  # 5 minutes


@dataclass(slots=True)
class CacheEntry:
    price: Decimal
    currency: str
    fetched_at: float  # time.time()
    source_fetched_at: Optional[float] = None


_store: dict[str, CacheEntry] = {}


def get(key: str) -> Optional[CacheEntry]:
    """Return cached entry if it exists and hasn't expired."""
    entry = _store.get(key)
    if entry is None:
        return None
    if time.time() - entry.fetched_at > TTL_SECONDS:
        del _store[key]
        return None
    return entry


def put(
    key: str,
    price: Decimal,
    currency: str,
    *,
    source_fetched_at: Optional[float] = None,
) -> CacheEntry:
    """Store a price in the cache."""
    entry = CacheEntry(
        price=price,
        currency=currency,
        fetched_at=time.time(),
        source_fetched_at=source_fetched_at,
    )
    _store[key] = entry
    return entry


def clear() -> None:
    """Drop all cached entries (useful in tests)."""
    _store.clear()
