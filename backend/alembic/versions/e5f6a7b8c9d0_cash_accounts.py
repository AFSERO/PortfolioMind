"""cash accounts + movements; affects_cash column on transactions

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-18 12:00:00.000000

"""
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e5f6a7b8c9d0"
down_revision: str = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_CURRENCIES = ("TRY", "USD", "EUR")


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "affects_cash",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    op.create_table(
        "cash_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "balance",
            sa.Numeric(precision=18, scale=6),
            nullable=False,
            server_default="0",
        ),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "currency", name="uq_cash_accounts_user_currency"
        ),
    )
    op.create_index(
        "ix_cash_accounts_user_id", "cash_accounts", ["user_id"]
    )

    op.create_table(
        "cash_movements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cash_account_id", sa.Uuid(), nullable=False),
        sa.Column(
            "movement_type",
            sa.Enum(
                "DEPOSIT",
                "WITHDRAW",
                "TRANSFER_IN",
                "TRANSFER_OUT",
                "BUY",
                "SELL",
                "ADJUSTMENT",
                name="cashmovementtype",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("related_transaction_id", sa.Uuid(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["cash_account_id"], ["cash_accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["related_transaction_id"], ["transactions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cash_movements_cash_account_id",
        "cash_movements",
        ["cash_account_id"],
    )
    op.create_index(
        "ix_cash_movements_related_transaction_id",
        "cash_movements",
        ["related_transaction_id"],
    )

    # Backfill existing users with zero-balance TRY/USD/EUR accounts
    conn = op.get_bind()
    users = conn.execute(sa.text("SELECT id FROM users")).fetchall()
    now = datetime.now(timezone.utc)
    for (user_id,) in users:
        for currency in DEFAULT_CURRENCIES:
            conn.execute(
                sa.text(
                    "INSERT INTO cash_accounts "
                    "(id, user_id, currency, balance, created_at, updated_at) "
                    "VALUES (:id, :uid, :cur, 0, :now, :now)"
                ),
                {
                    "id": uuid.uuid4(),
                    "uid": user_id,
                    "cur": currency,
                    "now": now,
                },
            )


def downgrade() -> None:
    op.drop_index(
        "ix_cash_movements_related_transaction_id", table_name="cash_movements"
    )
    op.drop_index(
        "ix_cash_movements_cash_account_id", table_name="cash_movements"
    )
    op.drop_table("cash_movements")
    op.drop_index("ix_cash_accounts_user_id", table_name="cash_accounts")
    op.drop_table("cash_accounts")
    op.drop_column("transactions", "affects_cash")
