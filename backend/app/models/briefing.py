"""Briefing models for PortfolioMind.

Stores persistent periodic or on-demand briefing runs and individual portfolio-
and watchlist-relevant intelligence items.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.instrument import Instrument
    from app.models.user import User


class BriefingImpact(str, enum.Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"
    MIXED = "MIXED"


class BriefingMateriality(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class BriefingTimeHorizon(str, enum.Enum):
    SHORT = "SHORT"
    MEDIUM = "MEDIUM"
    LONG = "LONG"


class BriefingThesisImpact(str, enum.Enum):
    STRONGER = "STRONGER"
    UNCHANGED = "UNCHANGED"
    WEAKER = "WEAKER"
    INVALIDATED = "INVALIDATED"
    NOT_EVALUATED = "NOT_EVALUATED"


class BriefingCategory(str, enum.Enum):
    EARNINGS = "EARNINGS"
    REGULATORY = "REGULATORY"
    MACRO = "MACRO"
    OPERATIONAL = "OPERATIONAL"
    COMPETITIVE = "COMPETITIVE"
    GENERAL = "GENERAL"


class BriefingTriggerType(str, enum.Enum):
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"


class BriefingRun(Base):
    """Execution run representing a snapshot of portfolio & watchlist intelligence."""

    __tablename__ = "briefing_runs"
    __table_args__ = (
        Index("ix_briefing_runs_user_id", "user_id"),
        Index("ix_briefing_runs_generated_at", "generated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    scope: Mapped[str] = mapped_column(
        String(64), default="PORTFOLIO_AND_WATCHLIST", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), default="COMPLETED", nullable=False
    )
    trigger_type: Mapped[BriefingTriggerType] = mapped_column(
        SAEnum(BriefingTriggerType, native_enum=False, length=20),
        default=BriefingTriggerType.MANUAL,
        server_default="MANUAL",
        nullable=False,
    )
    items_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_shown: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_filtered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship("User")
    items: Mapped[List["BriefingItem"]] = relationship(
        "BriefingItem",
        back_populates="briefing_run",
        cascade="all, delete-orphan",
        order_by="BriefingItem.created_at.desc()",
    )


class BriefingItem(Base):
    """Specific event or development relevant to an owned holding or watched instrument."""

    __tablename__ = "briefing_items"
    __table_args__ = (
        Index("ix_briefing_items_briefing_run_id", "briefing_run_id"),
        Index("ix_briefing_items_user_id", "user_id"),
        Index("ix_briefing_items_instrument_id", "instrument_id"),
        Index("ix_briefing_items_materiality", "materiality"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    briefing_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("briefing_runs.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )

    headline: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    why_it_matters: Mapped[str] = mapped_column(Text, nullable=False)

    impact: Mapped[BriefingImpact] = mapped_column(
        SAEnum(BriefingImpact, native_enum=False, length=20),
        default=BriefingImpact.NEUTRAL,
        nullable=False,
    )
    materiality: Mapped[BriefingMateriality] = mapped_column(
        SAEnum(BriefingMateriality, native_enum=False, length=20),
        default=BriefingMateriality.MEDIUM,
        nullable=False,
    )
    time_horizon: Mapped[BriefingTimeHorizon] = mapped_column(
        SAEnum(BriefingTimeHorizon, native_enum=False, length=20),
        default=BriefingTimeHorizon.MEDIUM,
        nullable=False,
    )
    thesis_impact: Mapped[BriefingThesisImpact] = mapped_column(
        SAEnum(BriefingThesisImpact, native_enum=False, length=20),
        default=BriefingThesisImpact.NOT_EVALUATED,
        nullable=False,
    )
    review_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    category: Mapped[BriefingCategory] = mapped_column(
        SAEnum(BriefingCategory, native_enum=False, length=32),
        default=BriefingCategory.GENERAL,
        nullable=False,
    )

    source_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    is_portfolio: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    briefing_run: Mapped["BriefingRun"] = relationship(
        "BriefingRun", back_populates="items"
    )
    instrument: Mapped["Instrument"] = relationship("Instrument")
