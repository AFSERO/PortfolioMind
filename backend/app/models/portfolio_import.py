"""Portfolio import batch and item persistence models.

Represents the common import abstraction across Natural Language, Screenshot, and CSV.
Normalizes, resolves instruments, reconciles with existing holdings, and tracks
reconciliation diffs before user confirmation.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, List, Optional
import uuid

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    JSON,
    Numeric,
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
    from app.models.copilot import CopilotActionProposal, CopilotConversation
    from app.models.instrument import Instrument
    from app.models.opening_position import OpeningPosition
    from app.models.user import User


class PortfolioImportBatch(Base):
    """A batch import session aggregating multiple candidate holdings."""

    __tablename__ = "portfolio_import_batches"
    __table_args__ = (
        Index("ix_portfolio_import_batches_user_id", "user_id"),
        Index("ix_portfolio_import_batches_status", "status"),
        Index("ix_portfolio_import_batches_idempotency_key", "idempotency_key", unique=True),
        Index("ix_portfolio_import_batches_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("copilot_conversations.id", ondelete="SET NULL"), nullable=True
    )
    proposal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("copilot_action_proposals.id", ondelete="SET NULL"), nullable=True
    )

    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # 'NATURAL_LANGUAGE', 'SCREENSHOT', 'CSV'
    source_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT"
    )  # 'DRAFT', 'PARSED', 'READY_FOR_CONFIRMATION', 'CONFIRMED', 'APPLIED', 'CANCELLED', 'FAILED'

    raw_content_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    warnings: Mapped[Optional[List[str]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True, default=list
    )
    errors: Mapped[Optional[List[str]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True, default=list
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    parsed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    applied_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship("User")
    conversation: Mapped[Optional["CopilotConversation"]] = relationship("CopilotConversation")
    proposal: Mapped[Optional["CopilotActionProposal"]] = relationship("CopilotActionProposal")

    items: Mapped[List["PortfolioImportItem"]] = relationship(
        "PortfolioImportItem",
        back_populates="batch",
        cascade="all, delete-orphan",
        order_by="PortfolioImportItem.created_at.asc()",
        lazy="selectin",
    )
    opening_positions: Mapped[List["OpeningPosition"]] = relationship(
        "OpeningPosition", back_populates="import_batch"
    )


class PortfolioImportItem(Base):
    """An individual extracted/parsed holding inside an import batch."""

    __tablename__ = "portfolio_import_items"
    __table_args__ = (
        Index("ix_portfolio_import_items_batch_id", "batch_id"),
        Index("ix_portfolio_import_items_intended_action", "intended_action"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("portfolio_import_batches.id", ondelete="CASCADE"), nullable=False
    )

    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_instrument_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("instruments.id", ondelete="SET NULL"), nullable=True
    )
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False, default="CUSTOM")
    symbol: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    market_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    average_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    total_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    as_of_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    semantic_fields: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    existing_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("assets.id", ondelete="SET NULL"), nullable=True
    )
    existing_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)

    intended_action: Mapped[str] = mapped_column(
        String(32), nullable=False, default="NEEDS_REVIEW"
    )  # 'CREATE_OPENING_POSITION', 'UPDATE_EXISTING_OPENING_POSITION', 'ADD_TO_EXISTING_POSITION', 'SKIP', 'NEEDS_REVIEW', 'AMBIGUOUS'
    action_resolution: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True
    )  # 'REPLACE_OPENING_STATE', 'ADD_TO_EXISTING', 'SKIP'

    warnings: Mapped[Optional[List[str]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True, default=list
    )
    missing_fields: Mapped[Optional[List[str]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True, default=list
    )

    resulting_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("assets.id", ondelete="SET NULL"), nullable=True
    )
    resulting_opening_position_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("opening_positions.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    batch: Mapped["PortfolioImportBatch"] = relationship(
        "PortfolioImportBatch", back_populates="items"
    )
    resolved_instrument: Mapped[Optional["Instrument"]] = relationship("Instrument")
    existing_asset: Mapped[Optional["Asset"]] = relationship(
        "Asset", foreign_keys=[existing_asset_id]
    )
    resulting_asset: Mapped[Optional["Asset"]] = relationship(
        "Asset", foreign_keys=[resulting_asset_id]
    )
    resulting_opening_position: Mapped[Optional["OpeningPosition"]] = relationship(
        "OpeningPosition", foreign_keys=[resulting_opening_position_id]
    )
