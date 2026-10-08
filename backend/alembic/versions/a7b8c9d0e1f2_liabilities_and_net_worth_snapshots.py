"""add liabilities and explicit net-worth snapshot totals

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-08-06 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a7b8c9d0e1f2"
down_revision: str = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "liabilities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "liability_type",
            sa.Enum(
                "credit_card",
                "personal_loan",
                "mortgage",
                "student_loan",
                "other",
                name="liability_type_enum",
                native_enum=False,
                create_constraint=True,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "current_balance", sa.Numeric(precision=18, scale=6), nullable=False
        ),
        sa.Column(
            "original_balance", sa.Numeric(precision=18, scale=6), nullable=True
        ),
        sa.Column(
            "interest_rate", sa.Numeric(precision=18, scale=6), nullable=True
        ),
        sa.Column(
            "minimum_payment", sa.Numeric(precision=18, scale=6), nullable=True
        ),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
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
        sa.CheckConstraint(
            "current_balance >= 0",
            name="ck_liabilities_current_balance_nonnegative",
        ),
        sa.CheckConstraint(
            "original_balance IS NULL OR original_balance >= 0",
            name="ck_liabilities_original_balance_nonnegative",
        ),
        sa.CheckConstraint(
            "interest_rate IS NULL OR interest_rate >= 0",
            name="ck_liabilities_interest_rate_nonnegative",
        ),
        sa.CheckConstraint(
            "minimum_payment IS NULL OR minimum_payment >= 0",
            name="ck_liabilities_minimum_payment_nonnegative",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_liabilities_user_active", "liabilities", ["user_id", "is_active"]
    )

    op.add_column(
        "portfolio_snapshots",
        sa.Column("total_assets_try", sa.Numeric(18, 2), nullable=True),
    )
    op.add_column(
        "portfolio_snapshots",
        sa.Column("total_assets_usd", sa.Numeric(18, 2), nullable=True),
    )
    op.add_column(
        "portfolio_snapshots",
        sa.Column("total_liabilities_try", sa.Numeric(18, 2), nullable=True),
    )
    op.add_column(
        "portfolio_snapshots",
        sa.Column("total_liabilities_usd", sa.Numeric(18, 2), nullable=True),
    )
    op.add_column(
        "portfolio_snapshots",
        sa.Column("net_worth_try", sa.Numeric(18, 2), nullable=True),
    )
    op.add_column(
        "portfolio_snapshots",
        sa.Column("net_worth_usd", sa.Numeric(18, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("portfolio_snapshots", "net_worth_usd")
    op.drop_column("portfolio_snapshots", "net_worth_try")
    op.drop_column("portfolio_snapshots", "total_liabilities_usd")
    op.drop_column("portfolio_snapshots", "total_liabilities_try")
    op.drop_column("portfolio_snapshots", "total_assets_usd")
    op.drop_column("portfolio_snapshots", "total_assets_try")
    op.drop_index("ix_liabilities_user_active", table_name="liabilities")
    op.drop_table("liabilities")
