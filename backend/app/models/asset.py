import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.instrument import Instrument
    from app.models.opening_position import OpeningPosition



class AssetType(str, enum.Enum):
    """Investment asset categories — matches SPEC.md § 3."""

    STOCK = "STOCK"
    FOREX = "FOREX"
    PRECIOUS_METALS = "PRECIOUS_METALS"
    CRYPTO = "CRYPTO"
    FUND = "FUND"
    REAL_ESTATE = "REAL_ESTATE"
    CUSTOM = "CUSTOM"


class Asset(Base):
    """Investment asset — matches SPEC.md § 3 Data Models."""

    __tablename__ = "assets"
    __table_args__ = (
        Index("ix_assets_user_id", "user_id"),
        Index("ix_assets_asset_type", "asset_type"),
        Index("ix_assets_symbol", "symbol"),
        Index("ix_assets_instrument_id", "instrument_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    instrument_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("instruments.id", ondelete="SET NULL"), nullable=True
    )
    asset_type: Mapped[AssetType] = mapped_column(
        SAEnum(AssetType, native_enum=False, length=20), nullable=False
    )
    symbol: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    current_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(18, 6), nullable=True
    )
    current_price_currency: Mapped[Optional[str]] = mapped_column(
        String(3), nullable=True
    )
    is_manual_price: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    instrument: Mapped[Optional["Instrument"]] = relationship(
        "Instrument", back_populates="assets", lazy="selectin"
    )
    opening_position: Mapped[Optional["OpeningPosition"]] = relationship(
        "OpeningPosition",
        back_populates="asset",
        uselist=False,
        lazy="selectin",
        cascade="all, delete-orphan",
    )
