"""add opening_positions and portfolio_import tables

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-09-25 02:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "l2m3n4o5p6q7"
down_revision: Union[str, None] = "k1l2m3n4o5p6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. portfolio_import_batches
    op.create_table(
        "portfolio_import_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("proposal_id", sa.Uuid(), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_reference", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="DRAFT", nullable=False),
        sa.Column("raw_content_preview", sa.Text(), nullable=True),
        sa.Column(
            "warnings",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default=sa.text("'[]'"),
            nullable=True,
        ),
        sa.Column(
            "errors",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default=sa.text("'[]'"),
            nullable=True,
        ),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["copilot_conversations.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["copilot_action_proposals.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_portfolio_import_batches_user_id",
        "portfolio_import_batches",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_portfolio_import_batches_status",
        "portfolio_import_batches",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_portfolio_import_batches_idempotency_key",
        "portfolio_import_batches",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index(
        "ix_portfolio_import_batches_created_at",
        "portfolio_import_batches",
        ["created_at"],
        unique=False,
    )

    # 2. opening_positions
    op.create_table(
        "opening_positions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("cost_basis_known", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("average_cost", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("cost_currency", sa.String(length=3), nullable=True),
        sa.Column("total_cost", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("has_incomplete_history", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("source", sa.String(length=32), server_default="MANUAL", nullable=False),
        sa.Column(
            "provenance",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("import_batch_id", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["import_batch_id"],
            ["portfolio_import_batches.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_opening_positions_user_id",
        "opening_positions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_opening_positions_asset_id",
        "opening_positions",
        ["asset_id"],
        unique=True,
    )
    op.create_index(
        "ix_opening_positions_import_batch_id",
        "opening_positions",
        ["import_batch_id"],
        unique=False,
    )

    # 3. portfolio_import_items
    op.create_table(
        "portfolio_import_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("raw_input", sa.Text(), nullable=False),
        sa.Column("resolved_instrument_id", sa.Uuid(), nullable=True),
        sa.Column("asset_type", sa.String(length=32), server_default="CUSTOM", nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("market_value", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("average_cost", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("total_cost", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("as_of_date", sa.Date(), nullable=True),
        sa.Column(
            "semantic_fields",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("existing_asset_id", sa.Uuid(), nullable=True),
        sa.Column("existing_quantity", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("intended_action", sa.String(length=32), server_default="NEEDS_REVIEW", nullable=False),
        sa.Column("action_resolution", sa.String(length=32), nullable=True),
        sa.Column(
            "warnings",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default=sa.text("'[]'"),
            nullable=True,
        ),
        sa.Column(
            "missing_fields",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default=sa.text("'[]'"),
            nullable=True,
        ),
        sa.Column("resulting_asset_id", sa.Uuid(), nullable=True),
        sa.Column("resulting_opening_position_id", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["portfolio_import_batches.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["existing_asset_id"],
            ["assets.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_instrument_id"],
            ["instruments.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["resulting_asset_id"],
            ["assets.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["resulting_opening_position_id"],
            ["opening_positions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_portfolio_import_items_batch_id",
        "portfolio_import_items",
        ["batch_id"],
        unique=False,
    )
    op.create_index(
        "ix_portfolio_import_items_intended_action",
        "portfolio_import_items",
        ["intended_action"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_portfolio_import_items_intended_action", table_name="portfolio_import_items")
    op.drop_index("ix_portfolio_import_items_batch_id", table_name="portfolio_import_items")
    op.drop_table("portfolio_import_items")

    op.drop_index("ix_opening_positions_import_batch_id", table_name="opening_positions")
    op.drop_index("ix_opening_positions_asset_id", table_name="opening_positions")
    op.drop_index("ix_opening_positions_user_id", table_name="opening_positions")
    op.drop_table("opening_positions")

    op.drop_index("ix_portfolio_import_batches_created_at", table_name="portfolio_import_batches")
    op.drop_index("ix_portfolio_import_batches_idempotency_key", table_name="portfolio_import_batches")
    op.drop_index("ix_portfolio_import_batches_status", table_name="portfolio_import_batches")
    op.drop_index("ix_portfolio_import_batches_user_id", table_name="portfolio_import_batches")
    op.drop_table("portfolio_import_batches")
