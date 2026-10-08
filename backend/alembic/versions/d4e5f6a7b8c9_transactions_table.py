"""create transactions table and migrate purchase fields

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-17 12:00:00.000000

"""
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d4e5f6a7b8c9"
down_revision: str = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column(
            "transaction_type",
            sa.Enum("BUY", "SELL", name="transactiontype", native_enum=False, length=10),
            nullable=False,
        ),
        sa.Column("quantity", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("price_per_unit", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("transaction_currency", sa.String(length=3), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transactions_asset_id", "transactions", ["asset_id"])
    op.create_index(
        "ix_transactions_transaction_date", "transactions", ["transaction_date"]
    )

    # Backfill: one initial BUY per existing asset.
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, purchase_price, quantity, purchase_currency, purchase_date "
            "FROM assets"
        )
    ).fetchall()
    now = datetime.now(timezone.utc)
    for asset_id, purchase_price, quantity, purchase_currency, purchase_date in rows:
        conn.execute(
            sa.text(
                "INSERT INTO transactions (id, asset_id, transaction_type, quantity, "
                "price_per_unit, total_amount, transaction_currency, transaction_date, "
                "created_at, updated_at) VALUES (:id, :asset_id, 'BUY', :qty, :price, "
                ":total, :cur, :date, :now, :now)"
            ),
            {
                "id": uuid.uuid4(),
                "asset_id": asset_id,
                "qty": quantity,
                "price": purchase_price,
                "total": quantity * purchase_price,
                "cur": purchase_currency,
                "date": purchase_date,
                "now": now,
            },
        )

    op.drop_column("assets", "purchase_price")
    op.drop_column("assets", "quantity")
    op.drop_column("assets", "purchase_currency")
    op.drop_column("assets", "purchase_date")


def downgrade() -> None:
    op.add_column(
        "assets",
        sa.Column("purchase_price", sa.Numeric(precision=18, scale=6), nullable=True),
    )
    op.add_column(
        "assets",
        sa.Column("quantity", sa.Numeric(precision=18, scale=6), nullable=True),
    )
    op.add_column(
        "assets", sa.Column("purchase_currency", sa.String(length=3), nullable=True)
    )
    op.add_column("assets", sa.Column("purchase_date", sa.Date(), nullable=True))

    conn = op.get_bind()
    assets = conn.execute(sa.text("SELECT id FROM assets")).fetchall()
    for (asset_id,) in assets:
        row = conn.execute(
            sa.text(
                "SELECT quantity, price_per_unit, transaction_currency, transaction_date "
                "FROM transactions WHERE asset_id = :aid AND transaction_type = 'BUY' "
                "ORDER BY transaction_date ASC, created_at ASC LIMIT 1"
            ),
            {"aid": asset_id},
        ).fetchone()
        if row is None:
            # No BUY — fall back to zero/placeholder values so NOT NULL passes
            conn.execute(
                sa.text(
                    "UPDATE assets SET purchase_price=0, quantity=0, "
                    "purchase_currency='TRY', purchase_date=CURRENT_DATE "
                    "WHERE id=:aid"
                ),
                {"aid": asset_id},
            )
        else:
            qty, price, cur, date_ = row
            conn.execute(
                sa.text(
                    "UPDATE assets SET purchase_price=:price, quantity=:qty, "
                    "purchase_currency=:cur, purchase_date=:date WHERE id=:aid"
                ),
                {"aid": asset_id, "qty": qty, "price": price, "cur": cur, "date": date_},
            )

    op.alter_column("assets", "purchase_price", nullable=False)
    op.alter_column("assets", "quantity", nullable=False)
    op.alter_column("assets", "purchase_currency", nullable=False)
    op.alter_column("assets", "purchase_date", nullable=False)

    op.drop_index("ix_transactions_transaction_date", table_name="transactions")
    op.drop_index("ix_transactions_asset_id", table_name="transactions")
    op.drop_table("transactions")
