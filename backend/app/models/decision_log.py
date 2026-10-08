"""Decision Log model for PortfolioMind.

Records the reasoning, context, and history behind investment decisions,
such as position adjustments, thesis reviews, valuation changes, and manual notes.
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
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
    from app.models.asset import Asset
    from app.models.instrument import Instrument
    from app.models.intelligence import IntelligenceReview
    from app.models.transaction import Transaction
    from app.models.user import User


class DecisionEventType(str, enum.Enum):
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_ADDED = "POSITION_ADDED"
    POSITION_REDUCED = "POSITION_REDUCED"
    POSITION_CLOSED = "POSITION_CLOSED"
    BUY = "BUY"
    SELL = "SELL"
    THESIS_REVIEWED = "THESIS_REVIEWED"
    THESIS_CHANGED = "THESIS_CHANGED"
    VALUATION_CHANGED = "VALUATION_CHANGED"
    TECHNICAL_PLAN_CHANGED = "TECHNICAL_PLAN_CHANGED"
    RECOMMENDATION_CHANGED = "RECOMMENDATION_CHANGED"
    INTELLIGENCE_REVIEW_COMPLETED = "INTELLIGENCE_REVIEW_COMPLETED"
    MANUAL_DECISION_NOTE = "MANUAL_DECISION_NOTE"


class DecisionLogEntry(Base):
    """Immutable audit trail entry capturing investment decisions and thesis revisions."""

    __tablename__ = "decision_log_entries"
    __table_args__ = (
        Index("ix_decision_log_user_id", "user_id"),
        Index("ix_decision_log_occurred_at", "occurred_at"),
        Index("ix_decision_log_instrument_id", "instrument_id"),
        Index("ix_decision_log_asset_id", "asset_id"),
        Index("ix_decision_log_event_type", "event_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    instrument_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("instruments.id", ondelete="SET NULL"), nullable=True
    )
    asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("assets.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[DecisionEventType] = mapped_column(
        SAEnum(DecisionEventType, native_enum=False, length=40), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    user_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    expectation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    related_review_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("intelligence_reviews.id", ondelete="SET NULL"), nullable=True
    )
    related_transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True
    )
    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata", JSON().with_variant(JSONB, "postgresql"), nullable=True
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["User"] = relationship("User")
    instrument: Mapped[Optional["Instrument"]] = relationship("Instrument")
    asset: Mapped[Optional["Asset"]] = relationship("Asset")
    review: Mapped[Optional["IntelligenceReview"]] = relationship("IntelligenceReview")
    transaction: Mapped[Optional["Transaction"]] = relationship("Transaction")
