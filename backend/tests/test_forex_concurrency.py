"""PostgreSQL concurrency must keep one valid quote without poisoning sessions."""
import asyncio
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.database import get_session_factory
from app.models.forex_rate import ForexRate
from app.services.forex_cache import upsert_rate


@pytest.mark.asyncio
async def test_concurrent_forex_upserts(db_session):
    async def write(rate):
        async with get_session_factory()() as session:
            row = await upsert_rate(session, "USD", "TRY", rate)
            assert row.rate.is_finite() and row.rate > 0
            await session.execute(select(ForexRate))
    await asyncio.gather(write(Decimal("40")), write(Decimal("41")))
    rows = (await db_session.execute(select(ForexRate).where(
        ForexRate.base_currency == "USD", ForexRate.target_currency == "TRY"
    ))).scalars().all()
    assert len(rows) == 1
    assert rows[0].rate in (Decimal("40"), Decimal("41"))
