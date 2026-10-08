"""Tests for external provider interfaces and test doubles (Part 4B)."""

from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from investment_intelligence.providers import (
    DataUnavailableError,
    MarketDataProvider,
    MarketQuoteRecord,
    NewsItemRecord,
    NewsProvider,
    PortfolioProvider,
    PortfolioSnapshotRecord,
    PositionSnapshotRecord,
    PriceBarRecord,
    ProviderError,
    StaticMarketDataProvider,
    StaticNewsProvider,
    StaticPortfolioProvider,
)
from investment_intelligence.records import InstrumentRecord

UTC = timezone.utc
NOW = datetime(2026, 9, 15, 14, 0, tzinfo=UTC)
PLUS_3 = timezone(timedelta(hours=3))


# ============================================================================
# 1. MarketDataProvider Tests
# ============================================================================


def test_market_quote_record_creation_and_utc_normalization():
    iid = uuid4()
    # Aware datetime with +03:00 timezone must be normalized to UTC
    as_of_plus3 = datetime(2026, 9, 15, 17, 0, tzinfo=PLUS_3)
    quote = MarketQuoteRecord(
        instrument_id=iid,
        price=Decimal("185.50"),
        currency="USD",
        as_of=as_of_plus3,
        source="iex",
    )

    assert quote.instrument_id == iid
    assert quote.price == Decimal("185.50")
    assert quote.currency == "USD"
    assert quote.as_of == datetime(2026, 9, 15, 14, 0, tzinfo=UTC)
    assert quote.as_of.tzinfo == UTC
    assert quote.source == "iex"


def test_market_quote_rejects_naive_datetime():
    naive_dt = datetime(2026, 9, 15, 14, 0)
    with pytest.raises(ValueError, match="Timezone-aware datetime required"):
        MarketQuoteRecord(
            instrument_id=uuid4(),
            price=Decimal("100.00"),
            currency="USD",
            as_of=naive_dt,
        )


def test_price_bar_record_creation_and_validation():
    bar = PriceBarRecord(
        timestamp=NOW,
        open=Decimal("180.00"),
        high=Decimal("186.00"),
        low=Decimal("179.50"),
        close=Decimal("185.50"),
        volume=Decimal("1500000"),
    )

    assert bar.timestamp == NOW
    assert bar.open == Decimal("180.00")
    assert bar.high == Decimal("186.00")
    assert bar.low == Decimal("179.50")
    assert bar.close == Decimal("185.50")
    assert bar.volume == Decimal("1500000")

    # Reject naive datetime
    with pytest.raises(ValueError, match="Timezone-aware datetime required"):
        PriceBarRecord(
            timestamp=datetime(2026, 9, 15, 12, 0),
            open=Decimal("10"),
            high=Decimal("11"),
            low=Decimal("9"),
            close=Decimal("10"),
        )


def test_static_market_data_provider_quote():
    provider = StaticMarketDataProvider()
    assert isinstance(provider, MarketDataProvider)

    iid = uuid4()
    quote = MarketQuoteRecord(
        instrument_id=iid,
        price=Decimal("250.75"),
        currency="USD",
        as_of=NOW,
    )
    provider.set_quote(quote)

    # Lookup by UUID
    retrieved = provider.get_quote(iid)
    assert retrieved == quote

    # Lookup by string UUID
    assert provider.get_quote(str(iid)) == quote

    # Lookup for unknown instrument raises DataUnavailableError
    unknown_id = uuid4()
    with pytest.raises(DataUnavailableError):
        provider.get_quote(unknown_id)


def test_static_market_data_provider_price_history():
    provider = StaticMarketDataProvider()
    iid = uuid4()

    bars = [
        PriceBarRecord(timestamp=NOW - timedelta(days=2), open=Decimal("100"), high=Decimal("105"), low=Decimal("99"), close=Decimal("104")),
        PriceBarRecord(timestamp=NOW - timedelta(days=1), open=Decimal("104"), high=Decimal("108"), low=Decimal("103"), close=Decimal("107")),
        PriceBarRecord(timestamp=NOW, open=Decimal("107"), high=Decimal("110"), low=Decimal("106"), close=Decimal("109")),
    ]
    provider.set_price_history(iid, bars)

    # 1. Fetch all
    history = provider.get_price_history(iid)
    assert len(history) == 3
    assert history[0].timestamp < history[1].timestamp < history[2].timestamp

    # 2. Filter by start
    start_filter = NOW - timedelta(days=1)
    filtered_start = provider.get_price_history(iid, start=start_filter)
    assert len(filtered_start) == 2

    # 3. Filter by limit (most recent N)
    limited = provider.get_price_history(iid, limit=2)
    assert len(limited) == 2
    assert limited[0].timestamp == bars[1].timestamp
    assert limited[1].timestamp == bars[2].timestamp

    # 4. Unknown instrument returns empty list
    assert provider.get_price_history(uuid4()) == []


# ============================================================================
# 2. NewsProvider Tests
# ============================================================================


def test_news_item_record_creation_and_utc_normalization():
    iid = uuid4()
    pub_plus3 = datetime(2026, 9, 15, 13, 0, tzinfo=PLUS_3)
    item = NewsItemRecord(
        title="Quarterly Earnings Beat Expectations",
        published_at=pub_plus3,
        source="Bloomberg",
        url="https://bloomberg.com/news/123",
        summary="Company reported net income increase.",
        instrument_id=iid,
    )

    assert item.title == "Quarterly Earnings Beat Expectations"
    assert item.published_at == datetime(2026, 9, 15, 10, 0, tzinfo=UTC)
    assert item.published_at.tzinfo == UTC
    assert item.source == "Bloomberg"
    assert item.url == "https://bloomberg.com/news/123"
    assert item.instrument_id == iid


def test_news_item_rejects_naive_datetime():
    with pytest.raises(ValueError, match="Timezone-aware datetime required"):
        NewsItemRecord(
            title="Headline",
            published_at=datetime(2026, 9, 15, 10, 0),
            source="Reuters",
        )


def test_static_news_provider_filtering_and_limits():
    provider = StaticNewsProvider()
    assert isinstance(provider, NewsProvider)

    inst_a = uuid4()
    inst_b = uuid4()

    n1 = NewsItemRecord(title="A News 1", published_at=NOW - timedelta(hours=3), source="Reuters", instrument_id=inst_a)
    n2 = NewsItemRecord(title="A News 2 (Recent)", published_at=NOW - timedelta(hours=1), source="WSJ", instrument_id=inst_a)
    n3 = NewsItemRecord(title="B News", published_at=NOW - timedelta(hours=2), source="FT", instrument_id=inst_b)
    n4 = NewsItemRecord(title="Macro News", published_at=NOW - timedelta(hours=4), source="CNBC", instrument_id=None)

    for n in (n1, n2, n3, n4):
        provider.add_news(n)

    # 1. Filter by instrument A (most recent first)
    a_news = provider.get_recent_news(inst_a)
    assert len(a_news) == 2
    assert a_news[0].title == "A News 2 (Recent)"
    assert a_news[1].title == "A News 1"

    # 2. Filter by date range
    since_dt = NOW - timedelta(hours=2)
    recent_a = provider.get_recent_news(inst_a, since=since_dt)
    assert len(recent_a) == 1
    assert recent_a[0].title == "A News 2 (Recent)"

    # 3. Limit
    limited = provider.get_recent_news(limit=2)
    assert len(limited) == 2
    assert limited[0].published_at > limited[1].published_at


# ============================================================================
# 3. PortfolioProvider Tests
# ============================================================================


def test_position_and_portfolio_snapshot_records():
    inst_id = uuid4()
    pos = PositionSnapshotRecord(
        instrument_id=inst_id,
        quantity=Decimal("150.0"),
        average_cost=Decimal("70.25"),
        market_value=Decimal("11250.00"),
        portfolio_weight=Decimal("0.125"),
        unrealized_pnl=Decimal("712.50"),
    )

    assert pos.instrument_id == inst_id
    assert pos.quantity == Decimal("150.0")
    assert pos.average_cost == Decimal("70.25")
    assert pos.market_value == Decimal("11250.00")
    assert pos.portfolio_weight == Decimal("0.125")
    assert pos.unrealized_pnl == Decimal("712.50")

    portfolio = PortfolioSnapshotRecord(
        as_of=NOW,
        positions=[pos],
        total_value=Decimal("90000.00"),
        cash=Decimal("15000.00"),
    )

    assert portfolio.as_of == NOW
    assert len(portfolio.positions) == 1
    assert portfolio.positions[0] == pos
    assert portfolio.total_value == Decimal("90000.00")
    assert portfolio.cash == Decimal("15000.00")


def test_portfolio_snapshot_rejects_naive_as_of():
    with pytest.raises(ValueError, match="Timezone-aware datetime required"):
        PortfolioSnapshotRecord(
            as_of=datetime(2026, 9, 15, 12, 0),
            positions=[],
        )


def test_static_portfolio_provider_operations_and_instrument_separation():
    provider = StaticPortfolioProvider()
    assert isinstance(provider, PortfolioProvider)

    inst_held = uuid4()
    inst_not_held = uuid4()

    pos = PositionSnapshotRecord(
        instrument_id=inst_held,
        quantity=Decimal("50"),
        average_cost=Decimal("100"),
        market_value=Decimal("5500"),
    )
    provider.set_position(pos)
    provider.set_portfolio(as_of=NOW, total_value=Decimal("50000"), cash=Decimal("5000"))

    # 1. Held position returns PositionSnapshotRecord
    retrieved_pos = provider.get_position_context(inst_held)
    assert retrieved_pos is not None
    assert retrieved_pos.instrument_id == inst_held
    assert retrieved_pos.quantity == Decimal("50")

    # 2. Not held instrument returns None (preserves separation between Instrument and Position)
    assert provider.get_position_context(inst_not_held) is None

    # 3. Overall portfolio context
    port_ctx = provider.get_portfolio_context()
    assert port_ctx.as_of == NOW
    assert port_ctx.total_value == Decimal("50000")
    assert port_ctx.cash == Decimal("5000")
    assert len(port_ctx.positions) == 1

    # 4. Remove position
    provider.remove_position(inst_held)
    assert provider.get_position_context(inst_held) is None
    assert len(provider.get_portfolio_context().positions) == 0


# ============================================================================
# 4. Immutability & Serialization Tests
# ============================================================================


def test_provider_records_are_frozen():
    quote = MarketQuoteRecord(
        instrument_id=uuid4(),
        price=Decimal("100"),
        currency="USD",
        as_of=NOW,
    )
    with pytest.raises(Exception):  # FrozenInstanceError
        quote.price = Decimal("200")


def test_provider_records_serialize_cleanly():
    quote = MarketQuoteRecord(
        instrument_id=uuid4(),
        price=Decimal("150.25"),
        currency="USD",
        as_of=NOW,
    )

    data = asdict(quote)
    assert isinstance(data, dict)
    assert data["currency"] == "USD"
    assert data["price"] == Decimal("150.25")
    assert str(data["instrument_id"]) == str(quote.instrument_id)
