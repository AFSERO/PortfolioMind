"""create instruments table and link assets

Revision ID: c4d5e6f7a8b9
Revises: b8c9d0e1f2a3
Create Date: 2026-09-16 00:00:00.000000

"""
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create instruments table
    op.create_table(
        "instruments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "asset_type",
            sa.Enum(
                "STOCK",
                "FOREX",
                "PRECIOUS_METALS",
                "CRYPTO",
                "FUND",
                "REAL_ESTATE",
                "CUSTOM",
                name="assettype",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("exchange", sa.String(length=50), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("country", sa.String(length=50), nullable=True),
        sa.Column("isin", sa.String(length=50), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("provider_id", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_instruments_symbol", "instruments", ["symbol"])
    op.create_index("ix_instruments_asset_type", "instruments", ["asset_type"])
    op.create_index("ix_instruments_isin", "instruments", ["isin"])

    # 2. Add instrument_id to assets
    op.add_column("assets", sa.Column("instrument_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_assets_instrument_id_instruments",
        "assets",
        "instruments",
        ["instrument_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_assets_instrument_id", "assets", ["instrument_id"])

    # 3. Backfill: create and link an Instrument for every existing Asset
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, asset_type, symbol, name, current_price_currency FROM assets"
        )
    ).fetchall()

    # Cache of created instruments for standard deduplication:
    # key: (asset_type, symbol.upper(), exchange, currency) -> instrument_id
    shared_instruments: dict[tuple, uuid.UUID] = {}
    now = datetime.now(timezone.utc)

    for row in rows:
        asset_id = row.id
        asset_type = str(row.asset_type)
        symbol = row.symbol
        name = row.name
        currency = row.current_price_currency

        # Custom or Real Estate or assets without symbol are NEVER shared
        if asset_type in ("CUSTOM", "REAL_ESTATE") or not symbol:
            inst_id = uuid.uuid4()
            conn.execute(
                sa.text(
                    """
                    INSERT INTO instruments (id, symbol, name, asset_type, exchange, currency, country, isin, provider, provider_id, created_at, updated_at)
                    VALUES (:id, :symbol, :name, :asset_type, :exchange, :currency, :country, :isin, :provider, :provider_id, :created_at, :updated_at)
                    """
                ),
                {
                    "id": inst_id,
                    "symbol": symbol,
                    "name": name,
                    "asset_type": asset_type,
                    "exchange": None,
                    "currency": currency,
                    "country": None,
                    "isin": None,
                    "provider": None,
                    "provider_id": None,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            conn.execute(
                sa.text("UPDATE assets SET instrument_id = :inst_id WHERE id = :asset_id"),
                {"inst_id": inst_id, "asset_id": asset_id},
            )
            continue

        # Standard market assets: infer exchange and deduplicate safely
        clean_sym = symbol.strip().upper()
        exchange = None
        provider = None
        if asset_type == "STOCK":
            if clean_sym.endswith(".IS"):
                exchange = "BIST"
                currency = currency or "TRY"
            else:
                exchange = "NASDAQ"
                currency = currency or "USD"
            provider = "yfinance"
        elif asset_type == "CRYPTO":
            exchange = "Crypto"
            provider = "CoinGecko"
            currency = currency or "USD"
        elif asset_type == "FUND":
            exchange = "TEFAS"
            provider = "TEFAS"
            currency = currency or "TRY"
        elif asset_type == "PRECIOUS_METALS":
            exchange = "Precious Metals"
            provider = "yfinance"
            currency = currency or "USD"
        elif asset_type == "FOREX":
            exchange = "Forex"
            provider = "ExchangeRate-API"
            if not currency and "/" in clean_sym:
                currency = clean_sym.split("/")[1]

        dedup_key = (asset_type, clean_sym, exchange, currency)
        if dedup_key in shared_instruments:
            inst_id = shared_instruments[dedup_key]
        else:
            inst_id = uuid.uuid4()
            conn.execute(
                sa.text(
                    """
                    INSERT INTO instruments (id, symbol, name, asset_type, exchange, currency, country, isin, provider, provider_id, created_at, updated_at)
                    VALUES (:id, :symbol, :name, :asset_type, :exchange, :currency, :country, :isin, :provider, :provider_id, :created_at, :updated_at)
                    """
                ),
                {
                    "id": inst_id,
                    "symbol": clean_sym,
                    "name": name,
                    "asset_type": asset_type,
                    "exchange": exchange,
                    "currency": currency,
                    "country": None,
                    "isin": None,
                    "provider": provider,
                    "provider_id": None,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            shared_instruments[dedup_key] = inst_id

        conn.execute(
            sa.text("UPDATE assets SET instrument_id = :inst_id WHERE id = :asset_id"),
            {"inst_id": inst_id, "asset_id": asset_id},
        )


def downgrade() -> None:
    op.drop_index("ix_assets_instrument_id", table_name="assets")
    op.drop_constraint(
        "fk_assets_instrument_id_instruments", "assets", type_="foreignkey"
    )
    op.drop_column("assets", "instrument_id")
    op.drop_index("ix_instruments_isin", table_name="instruments")
    op.drop_index("ix_instruments_asset_type", table_name="instruments")
    op.drop_index("ix_instruments_symbol", table_name="instruments")
    op.drop_table("instruments")
