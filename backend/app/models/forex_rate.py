import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ForexRate(Base):
    """Cached forex exchange rate — one row per (base, target) pair.

    Updated at most once per day by the ``POST /api/prices/forex-rates/refresh``
    endpoint or lazily when ``build_rate_map`` fetches a fresh rate.
    """

    __tablename__ = "forex_rates"
    __table_args__ = (
        UniqueConstraint("base_currency", "target_currency", name="uq_forex_rate_pair"),
        Index("ix_forex_rates_pair", "base_currency", "target_currency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    target_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
