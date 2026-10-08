"""External provider contracts and in-memory test doubles (Part 4B)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from investment_intelligence.records import InstrumentRecord


# ============================================================================
# 1. Datetime and Identity Helpers
# ============================================================================


def _require_utc(dt: datetime, field_name: str) -> datetime:
    """Validate timezone-awareness and normalize to UTC."""
    if not isinstance(dt, datetime) or dt.utcoffset() is None:
        raise ValueError(f"Timezone-aware datetime required for '{field_name}'; naive datetime is not accepted")
    return dt.astimezone(timezone.utc)


def _as_uuid(identity: Any) -> UUID:
    """Extract UUID from UUID, InstrumentRecord, or string."""
    if hasattr(identity, "id"):
        return identity.id
    if hasattr(identity, "instrument_id"):
        return identity.instrument_id
    if isinstance(identity, str):
        return UUID(identity)
    if isinstance(identity, UUID):
        return identity
    raise TypeError(f"Cannot resolve UUID from {identity!r}")


# ============================================================================
# 2. Minimal Provider Errors
# ============================================================================


class ProviderError(Exception):
    """Base exception for external provider operations."""


class DataUnavailableError(ProviderError):
    """Requested provider data is not available or entity was not found."""


class ProviderConfigurationError(ProviderError):
    """Required provider configuration is missing or invalid."""


# ============================================================================
# 3. Provider Data Records (Frozen Dataclasses)
# ============================================================================


@dataclass(frozen=True)
class MarketQuoteRecord:
    """Current market quote snapshot for an instrument."""

    instrument_id: UUID
    price: Decimal
    currency: str
    as_of: datetime
    source: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "instrument_id", _as_uuid(self.instrument_id))
        object.__setattr__(self, "price", Decimal(str(self.price)))
        object.__setattr__(self, "as_of", _require_utc(self.as_of, "as_of"))


@dataclass(frozen=True)
class PriceBarRecord:
    """Single historical price bar (OHLCV) without technical indicators."""

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | int | None = None

    def __post_init__(self):
        object.__setattr__(self, "timestamp", _require_utc(self.timestamp, "timestamp"))
        object.__setattr__(self, "open", Decimal(str(self.open)))
        object.__setattr__(self, "high", Decimal(str(self.high)))
        object.__setattr__(self, "low", Decimal(str(self.low)))
        object.__setattr__(self, "close", Decimal(str(self.close)))
        if self.volume is not None:
            object.__setattr__(self, "volume", Decimal(str(self.volume)))


@dataclass(frozen=True)
class NewsItemRecord:
    """Headline/article reference. Does not determine materiality or recommendations."""

    title: str
    published_at: datetime
    source: str
    url: str | None = None
    summary: str | None = None
    instrument_id: UUID | None = None
    source_quality: str = "RADAR_UNVERIFIED"

    def __post_init__(self):
        object.__setattr__(self, "published_at", _require_utc(self.published_at, "published_at"))
        if self.instrument_id is not None:
            object.__setattr__(self, "instrument_id", _as_uuid(self.instrument_id))


@dataclass(frozen=True)
class PositionSnapshotRecord:
    """Current position snapshot for an instrument. Separated from Instrument identity."""

    instrument_id: UUID
    quantity: Decimal
    average_cost: Decimal | None = None
    market_value: Decimal | None = None
    portfolio_weight: Decimal | None = None
    unrealized_pnl: Decimal | None = None

    def __post_init__(self):
        object.__setattr__(self, "instrument_id", _as_uuid(self.instrument_id))
        object.__setattr__(self, "quantity", Decimal(str(self.quantity)))
        for field in ("average_cost", "market_value", "portfolio_weight", "unrealized_pnl"):
            val = getattr(self, field)
            if val is not None:
                object.__setattr__(self, field, Decimal(str(val)))


@dataclass(frozen=True)
class PortfolioSnapshotRecord:
    """High-level portfolio snapshot independent of NetWorth database models."""

    as_of: datetime
    positions: list[PositionSnapshotRecord]
    total_value: Decimal | None = None
    cash: Decimal | None = None

    def __post_init__(self):
        object.__setattr__(self, "as_of", _require_utc(self.as_of, "as_of"))
        object.__setattr__(self, "positions", list(self.positions))
        if self.total_value is not None:
            object.__setattr__(self, "total_value", Decimal(str(self.total_value)))
        if self.cash is not None:
            object.__setattr__(self, "cash", Decimal(str(self.cash)))


# ============================================================================
# 4. Provider Abstract Interfaces (Contracts)
# ============================================================================


class MarketDataProvider(ABC):
    """Abstract contract for real-time quotes and historical price bars."""

    @abstractmethod
    def get_quote(self, instrument: UUID | InstrumentRecord | str) -> MarketQuoteRecord:
        """Fetch current market quote for the given instrument."""

    @abstractmethod
    def get_price_history(
        self,
        instrument: UUID | InstrumentRecord | str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
    ) -> list[PriceBarRecord]:
        """Fetch historical OHLCV price bars for the given instrument."""


class NewsProvider(ABC):
    """Abstract contract for market/company news references."""

    @abstractmethod
    def get_recent_news(
        self,
        instrument: UUID | InstrumentRecord | str | None = None,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 10,
    ) -> list[NewsItemRecord]:
        """Fetch recent news articles optionally filtered by instrument or date."""


@dataclass(frozen=True)
class DisclosureItemRecord:
    instrument_id: UUID
    disclosure_type: str
    title: str
    published_at: datetime
    source: str
    url: str
    document_id: str | None = None
    summary: str | None = None
    metadata: dict[str, Any] | None = None
    source_quality: str = "PRIMARY"

    def __post_init__(self):
        object.__setattr__(self, "instrument_id", _as_uuid(self.instrument_id))
        object.__setattr__(self, "published_at", _require_utc(self.published_at, "published_at"))


class DisclosureProvider(ABC):
    @abstractmethod
    def get_recent_disclosures(self, instrument: UUID | InstrumentRecord | str, *,
                               since: datetime | None = None, until: datetime | None = None,
                               limit: int = 10) -> list[DisclosureItemRecord]:
        """Return bounded disclosure metadata, never full filing bodies."""


class StaticDisclosureProvider(DisclosureProvider):
    def __init__(self, items=()):
        self.items = list(items)

    def get_recent_disclosures(self, instrument, *, since=None, until=None, limit=10):
        if limit < 0:
            raise ValueError("limit must be non-negative")
        iid = _as_uuid(instrument)
        start = _require_utc(since, "since") if since is not None else None
        end = _require_utc(until, "until") if until is not None else None
        return sorted((item for item in self.items if item.instrument_id == iid
                       and (start is None or item.published_at >= start)
                       and (end is None or item.published_at <= end)),
                      key=lambda item: item.published_at, reverse=True)[:limit]


class PortfolioProvider(ABC):
    """Abstract contract for portfolio holding snapshots."""

    @abstractmethod
    def get_portfolio_context(self) -> PortfolioSnapshotRecord:
        """Fetch current overall portfolio snapshot including all positions."""

    @abstractmethod
    def get_position_context(
        self, instrument: UUID | InstrumentRecord | str
    ) -> PositionSnapshotRecord | None:
        """Fetch current position snapshot for an instrument, or None if not held."""


# ============================================================================
# 5. Deterministic In-Memory Test Doubles
# ============================================================================


class StaticMarketDataProvider(MarketDataProvider):
    """Deterministic in-memory market data provider for tests and local mocks."""

    def __init__(self):
        self._quotes: dict[UUID, MarketQuoteRecord] = {}
        self._bars: dict[UUID, list[PriceBarRecord]] = {}

    def set_quote(self, quote: MarketQuoteRecord) -> None:
        self._quotes[quote.instrument_id] = quote

    def set_price_history(self, instrument: UUID | InstrumentRecord | str, bars: list[PriceBarRecord]) -> None:
        iid = _as_uuid(instrument)
        # Store sorted chronologically
        self._bars[iid] = sorted(bars, key=lambda b: b.timestamp)

    def get_quote(self, instrument: UUID | InstrumentRecord | str) -> MarketQuoteRecord:
        iid = _as_uuid(instrument)
        quote = self._quotes.get(iid)
        if quote is None:
            raise DataUnavailableError(f"No market quote available for instrument {iid}")
        return quote

    def get_price_history(
        self,
        instrument: UUID | InstrumentRecord | str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int | None = None,
    ) -> list[PriceBarRecord]:
        iid = _as_uuid(instrument)
        bars = self._bars.get(iid, [])
        if start is not None:
            start_utc = _require_utc(start, "start")
            bars = [b for b in bars if b.timestamp >= start_utc]
        if end is not None:
            end_utc = _require_utc(end, "end")
            bars = [b for b in bars if b.timestamp <= end_utc]
        if limit is not None and limit > 0:
            bars = bars[-limit:]
        return list(bars)


class StaticNewsProvider(NewsProvider):
    """Deterministic in-memory news provider for tests and local mocks."""

    def __init__(self):
        self._news: list[NewsItemRecord] = []

    def add_news(self, item: NewsItemRecord) -> None:
        self._news.append(item)

    def get_recent_news(
        self,
        instrument: UUID | InstrumentRecord | str | None = None,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 10,
    ) -> list[NewsItemRecord]:
        items = list(self._news)
        if instrument is not None:
            iid = _as_uuid(instrument)
            items = [item for item in items if item.instrument_id == iid]
        if since is not None:
            since_utc = _require_utc(since, "since")
            items = [item for item in items if item.published_at >= since_utc]
        if until is not None:
            until_utc = _require_utc(until, "until")
            items = [item for item in items if item.published_at <= until_utc]
        # Most recent first
        items.sort(key=lambda x: x.published_at, reverse=True)
        return items[:limit] if limit > 0 else []


class StaticPortfolioProvider(PortfolioProvider):
    """Deterministic in-memory portfolio provider for tests and local mocks."""

    def __init__(self):
        self._positions: dict[UUID, PositionSnapshotRecord] = {}
        self._total_value: Decimal | None = None
        self._cash: Decimal | None = None
        self._as_of: datetime = datetime.now(timezone.utc)

    def set_portfolio(
        self,
        *,
        as_of: datetime | None = None,
        total_value: Decimal | None = None,
        cash: Decimal | None = None,
    ) -> None:
        if as_of is not None:
            self._as_of = _require_utc(as_of, "as_of")
        if total_value is not None:
            self._total_value = Decimal(str(total_value))
        if cash is not None:
            self._cash = Decimal(str(cash))

    def set_position(self, position: PositionSnapshotRecord) -> None:
        self._positions[position.instrument_id] = position

    def remove_position(self, instrument: UUID | InstrumentRecord | str) -> None:
        self._positions.pop(_as_uuid(instrument), None)

    def get_portfolio_context(self) -> PortfolioSnapshotRecord:
        return PortfolioSnapshotRecord(
            as_of=self._as_of,
            positions=list(self._positions.values()),
            total_value=self._total_value,
            cash=self._cash,
        )

    def get_position_context(
        self, instrument: UUID | InstrumentRecord | str
    ) -> PositionSnapshotRecord | None:
        return self._positions.get(_as_uuid(instrument))
