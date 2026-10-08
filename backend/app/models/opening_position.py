"""Opening position persistence model for legacy/initial holding state.

Preserves imported legacy holdings where historical transaction history is incomplete
or unknown, distinguishing clearly between real historical transactions and imported opening state.
Never fabricates BUY transactions.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional
import uuid

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
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
    from app.models.portfolio_import import PortfolioImportBatch
    from app.models.user import User


class OpeningPosition(Base):
    """Explicit imported opening position for an asset.

    Invariants:
    1. Distinguishes real historical transactions from imported opening state.
    2. Preserves unknown cost basis without fabricating prices or transactions.
    3. One opening position per user asset.
    4. Tracks provenance, source, and incomplete transaction history flags.
    """

    __tablename__ = "opening_positions"
    __table_args__ = (
        Index("ix_opening_positions_user_id", "user_id"),
        Index("ix_opening_positions_asset_id", "asset_id", unique=True),
        Index("ix_opening_positions_import_batch_id", "import_batch_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )

    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)

    cost_basis_known: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    average_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 6), nullable=True
    )
    cost_currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    total_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 6), nullable=True
    )

    has_incomplete_history: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="MANUAL"
    )  # 'NATURAL_LANGUAGE', 'SCREENSHOT', 'CSV', 'MANUAL'
    provenance: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    import_batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("portfolio_import_batches.id", ondelete="SET NULL"),
        nullable=True,
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

    user: Mapped["User"] = relationship("User")
    asset: Mapped["Asset"] = relationship("Asset", back_populates="opening_position")
    import_batch: Mapped[Optional["PortfolioImportBatch"]] = relationship(
        "PortfolioImportBatch", back_populates="opening_positions"
    )
