"""add discovery_runs and discovery_candidates tables

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-09-17 20:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "i9j0k1l2m3n4"
down_revision: Union[str, None] = "h8i9j0k1l2m3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. discovery_runs
    op.create_table(
        "discovery_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("universe", sa.String(length=64), server_default="US_LARGE_CAP", nullable=False),
        sa.Column("trigger_type", sa.String(length=32), server_default="MANUAL", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="RUNNING", nullable=False),
        sa.Column("instruments_scanned", sa.Integer(), server_default="0", nullable=False),
        sa.Column("candidates_filtered", sa.Integer(), server_default="0", nullable=False),
        sa.Column("candidates_reasoned", sa.Integer(), server_default="0", nullable=False),
        sa.Column("candidates_surfaced", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("diagnostics", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_discovery_runs_user_id", "discovery_runs", ["user_id"], unique=False)
    op.create_index("ix_discovery_runs_status", "discovery_runs", ["status"], unique=False)
    op.create_index("ix_discovery_runs_created_at", "discovery_runs", ["created_at"], unique=False)

    # 2. discovery_candidates
    op.create_table(
        "discovery_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="WATCH", nullable=False),
        sa.Column("candidate_state", sa.String(length=32), server_default="SURFACED", nullable=False),
        sa.Column("primary_reason", sa.Text(), nullable=False),
        sa.Column("signals", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("key_question", sa.Text(), nullable=True),
        sa.Column("key_risk", sa.Text(), nullable=True),
        sa.Column("suggested_next_step", sa.String(length=32), server_default="NONE", nullable=False),
        sa.Column("confidence", sa.String(length=16), server_default="MEDIUM", nullable=False),
        sa.Column("score_band", sa.String(length=16), nullable=True),
        sa.Column("current_price", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("current_price_currency", sa.String(length=8), nullable=True),
        sa.Column("market_data_snapshot", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("source_metadata", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("watchlisted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["discovery_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_discovery_candidates_user_id", "discovery_candidates", ["user_id"], unique=False)
    op.create_index("ix_discovery_candidates_run_id", "discovery_candidates", ["run_id"], unique=False)
    op.create_index("ix_discovery_candidates_instrument_id", "discovery_candidates", ["instrument_id"], unique=False)
    op.create_index("ix_discovery_candidates_status", "discovery_candidates", ["status"], unique=False)
    op.create_index("ix_discovery_candidates_state", "discovery_candidates", ["candidate_state"], unique=False)

    # 3. Add discovery_candidate_id to watchlist_items
    op.add_column("watchlist_items", sa.Column("discovery_candidate_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_watchlist_items_discovery_candidate_id",
        "watchlist_items",
        "discovery_candidates",
        ["discovery_candidate_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_watchlist_items_discovery_candidate_id", "watchlist_items", type_="foreignkey")
    op.drop_column("watchlist_items", "discovery_candidate_id")
    op.drop_index("ix_discovery_candidates_state", table_name="discovery_candidates")
    op.drop_index("ix_discovery_candidates_status", table_name="discovery_candidates")
    op.drop_index("ix_discovery_candidates_instrument_id", table_name="discovery_candidates")
    op.drop_index("ix_discovery_candidates_run_id", table_name="discovery_candidates")
    op.drop_index("ix_discovery_candidates_user_id", table_name="discovery_candidates")
    op.drop_table("discovery_candidates")
    op.drop_index("ix_discovery_runs_created_at", table_name="discovery_runs")
    op.drop_index("ix_discovery_runs_status", table_name="discovery_runs")
    op.drop_index("ix_discovery_runs_user_id", table_name="discovery_runs")
    op.drop_table("discovery_runs")
