import os
from unittest.mock import AsyncMock, patch
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.database import Base, get_db
from app.extensions import limiter
from app.main import app

# Disable rate limiting during tests
limiter.enabled = False

# In-memory SQLite stays the fast default. Critical integration runs can opt in
# to an explicitly isolated PostgreSQL database.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:"
)

_engine_kwargs: dict[str, object] = {"echo": False}
if not TEST_DATABASE_URL.startswith("sqlite"):
    # pytest-asyncio uses a fresh loop per test; never carry asyncpg connections
    # from one loop into the next.
    _engine_kwargs["poolclass"] = NullPool

_engine = create_async_engine(TEST_DATABASE_URL, **_engine_kwargs)
_TestSession = async_sessionmaker(_engine, expire_on_commit=False)

from app import database as app_db
app_db._engine = _engine
app_db._session_factory = _TestSession


if TEST_DATABASE_URL.startswith("sqlite"):

    @event.listens_for(_engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        """Keep fast SQLite tests honest about the production FK contract."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


async def _override_get_db() -> AsyncSession:
    async with _TestSession() as session:
        yield session


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def _clear_price_cache():
    """Reset in-memory price cache before every test to prevent cross-test leakage."""
    from app.utils import cache
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _mock_fetch_price_default():
    """Prevent real network calls in all tests.

    Tests that need specific price values should use
    ``@patch("app.services.price.fetch_price", new_callable=AsyncMock)``
    which overrides this fixture for the duration of that test.
    """
    with patch(
        "app.services.price.fetch_price",
        new_callable=AsyncMock,
        side_effect=RuntimeError("Network calls not allowed in tests"),
    ):
        yield


@pytest.fixture(autouse=True)
async def _setup_db():
    """Create all tables before each test and tear them down after."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client() -> AsyncClient:
    """Async HTTP client wired to the FastAPI app (no real server needed)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
async def db_session() -> AsyncSession:
    async with _TestSession() as session:
        yield session


@pytest.fixture
async def authed_client(client: AsyncClient) -> AsyncClient:
    """Client with a pre-registered user and Authorization header already set."""
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "user@example.com",
            "password": "testpassword123",
            "display_name": "Test User",
        },
    )
    token = resp.json()["data"]["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest.fixture(autouse=True)
def mock_external_discovery_fetch(request):
    """Prevent unmocked discovery network calls to yfinance during tests outside test_discovery."""
    if "test_discovery" in request.node.nodeid:
        yield
        return
    with patch("app.services.discovery.fetch_market_snapshots_batch", new_callable=AsyncMock, return_value={}):
        yield


@pytest.fixture(autouse=True)
def _block_live_forex():
    """Tests never consume real credentials or live exchange rates."""
    with patch("app.utils.price_fetchers.fetch_forex", new_callable=AsyncMock,
               side_effect=RuntimeError("Live forex is disabled in tests")) as provider:
        yield provider


@pytest.fixture
def forex_provider(_block_live_forex):
    """Explicit synthetic provider data; unsupported pairs remain unavailable."""
    rates = {
        "USD/TRY": Decimal("40"), "TRY/USD": Decimal("0.025"),
        "EUR/TRY": Decimal("44"), "TRY/EUR": Decimal("1") / Decimal("44"),
        "EUR/USD": Decimal("1.1"), "USD/EUR": Decimal("1") / Decimal("1.1"),
    }
    async def fetch(pair):
        if pair not in rates:
            raise RuntimeError("Synthetic exchange rate is not configured")
        return rates[pair], pair.split("/")[1]
    _block_live_forex.side_effect = fetch
    return _block_live_forex
