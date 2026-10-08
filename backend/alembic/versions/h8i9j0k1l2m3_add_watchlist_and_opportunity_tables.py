"""add watchlist_items and opportunity_assessments tables

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-09-17 17:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "h8i9j0k1l2m3"
down_revision: Union[str, None] = "g7h8i9j0k1l2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. watchlist_items
    op.create_table(
        "watchlist_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("research_stage", sa.String(length=32), server_default="DISCOVERED", nullable=False),
        sa.Column("priority", sa.String(length=16), server_default="MEDIUM", nullable=False),
        sa.Column("why_interesting", sa.Text(), nullable=True),
        sa.Column("target_entry_min", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("target_entry_max", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("key_catalyst", sa.String(length=255), nullable=True),
        sa.Column("key_risk", sa.String(length=255), nullable=True),
        sa.Column("next_expected_event", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "instrument_id", name="uq_watchlist_items_user_instrument"),
    )
    op.create_index("ix_watchlist_items_user_id", "watchlist_items", ["user_id"], unique=False)
    op.create_index("ix_watchlist_items_instrument_id", "watchlist_items", ["instrument_id"], unique=False)
    op.create_index("ix_watchlist_items_research_stage", "watchlist_items", ["research_stage"], unique=False)

    # 2. opportunity_assessments
    op.create_table(
        "opportunity_assessments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="NO_CHANGE", nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("primary_driver", sa.String(length=32), server_default="OTHER", nullable=False),
        sa.Column("valuation_signal", sa.String(length=32), server_default="UNKNOWN", nullable=False),
        sa.Column("research_freshness", sa.String(length=32), server_default="UNKNOWN", nullable=False),
        sa.Column("suggested_next_step", sa.String(length=32), server_default="NONE", nullable=False),
        sa.Column("confidence", sa.String(length=16), server_default="MEDIUM", nullable=False),
        sa.Column(
            "source_references",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.Column("assessment_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "instrument_id", name="uq_opportunity_assessments_user_instrument"),
    )
    op.create_index("ix_opportunity_assessments_user_id", "opportunity_assessments", ["user_id"], unique=False)
    op.create_index("ix_opportunity_assessments_instrument_id", "opportunity_assessments", ["instrument_id"], unique=False)
    op.create_index("ix_opportunity_assessments_status", "opportunity_assessments", ["status"], unique=False)


def downgrade() -> None:
    op.drop_table("opportunity_assessments")
    op.drop_table("watchlist_items")
