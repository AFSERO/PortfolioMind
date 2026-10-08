import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    Index,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.asset import AssetType

if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.intelligence import (
        InstrumentIntelligenceState,
        IntelligenceReview,
        TechnicalPlan,
    )


class Instrument(Base):
    """Investment Instrument entity — canonical security/asset identity.

    Separates the security itself (symbol, exchange, currency, etc.) from the
    user's specific holding/position (Asset). Future Investment Intelligence entities
    (thesis, valuation, research, monitoring) will attach here.
    """

    __tablename__ = "instruments"
    __table_args__ = (
        Index("ix_instruments_symbol", "symbol"),
        Index("ix_instruments_asset_type", "asset_type"),
        Index("ix_instruments_isin", "isin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    symbol: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[AssetType] = mapped_column(
        SAEnum(AssetType, native_enum=False, length=20), nullable=False
    )
    exchange: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    isin: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    provider_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    assets: Mapped[List["Asset"]] = relationship(
        "Asset", back_populates="instrument"
    )
    intelligence_state: Mapped[Optional["InstrumentIntelligenceState"]] = relationship(
        "InstrumentIntelligenceState",
        back_populates="instrument",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    reviews: Mapped[List["IntelligenceReview"]] = relationship(
        "IntelligenceReview",
        back_populates="instrument",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="desc(IntelligenceReview.created_at)",
    )
    technical_plans: Mapped[List["TechnicalPlan"]] = relationship(
        "TechnicalPlan",
        back_populates="instrument",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
