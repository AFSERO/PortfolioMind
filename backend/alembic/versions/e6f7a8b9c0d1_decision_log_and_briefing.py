"""add decision log and briefing tables

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-09-16 15:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create decision_log_entries table
    op.create_table(
        "decision_log_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=True),
        sa.Column("asset_id", sa.Uuid(), nullable=True),
        sa.Column(
            "event_type",
            sa.Enum(
                "POSITION_OPENED",
                "POSITION_ADDED",
                "POSITION_REDUCED",
                "POSITION_CLOSED",
                "BUY",
                "SELL",
                "THESIS_REVIEWED",
                "THESIS_CHANGED",
                "VALUATION_CHANGED",
                "TECHNICAL_PLAN_CHANGED",
                "RECOMMENDATION_CHANGED",
                "INTELLIGENCE_REVIEW_COMPLETED",
                "MANUAL_DECISION_NOTE",
                name="decisioneventtype",
                native_enum=False,
                length=40,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("user_rationale", sa.Text(), nullable=True),
        sa.Column("confidence", sa.String(length=32), nullable=True),
        sa.Column("expectation", sa.Text(), nullable=True),
        sa.Column("related_review_id", sa.Uuid(), nullable=True),
        sa.Column("related_transaction_id", sa.Uuid(), nullable=True),
        sa.Column(
            "metadata",
            sa.JSON().with_variant(JSONB, "postgresql"),
            nullable=True,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
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
            ["asset_id"], ["assets.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["related_review_id"], ["intelligence_reviews.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["related_transaction_id"], ["transactions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_decision_log_user_id", "decision_log_entries", ["user_id"]
    )
    op.create_index(
        "ix_decision_log_occurred_at", "decision_log_entries", ["occurred_at"]
    )
    op.create_index(
        "ix_decision_log_instrument_id", "decision_log_entries", ["instrument_id"]
    )
    op.create_index(
        "ix_decision_log_asset_id", "decision_log_entries", ["asset_id"]
    )
    op.create_index(
        "ix_decision_log_event_type", "decision_log_entries", ["event_type"]
    )

    # 2. Create briefing_runs table
    op.create_table(
        "briefing_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("items_found", sa.Integer(), nullable=False),
        sa.Column("items_shown", sa.Integer(), nullable=False),
        sa.Column("items_filtered", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_briefing_runs_user_id", "briefing_runs", ["user_id"]
    )
    op.create_index(
        "ix_briefing_runs_generated_at", "briefing_runs", ["generated_at"]
    )

    # 3. Create briefing_items table
    op.create_table(
        "briefing_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("briefing_run_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("headline", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("why_it_matters", sa.Text(), nullable=False),
        sa.Column(
            "impact",
            sa.Enum(
                "POSITIVE",
                "NEGATIVE",
                "NEUTRAL",
                "MIXED",
                name="briefingimpact",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "materiality",
            sa.Enum(
                "LOW",
                "MEDIUM",
                "HIGH",
                "CRITICAL",
                name="briefingmateriality",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "time_horizon",
            sa.Enum(
                "SHORT",
                "MEDIUM",
                "LONG",
                name="briefingtimehorizon",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "thesis_impact",
            sa.Enum(
                "STRONGER",
                "UNCHANGED",
                "WEAKER",
                "INVALIDATED",
                "NOT_EVALUATED",
                name="briefingthesisimpact",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "EARNINGS",
                "REGULATORY",
                "MACRO",
                "OPERATIONAL",
                "COMPETITIVE",
                "GENERAL",
                name="briefingcategory",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "source_metadata",
            sa.JSON().with_variant(JSONB, "postgresql"),
            nullable=True,
        ),
        sa.Column("is_portfolio", sa.Boolean(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["briefing_run_id"], ["briefing_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_briefing_items_briefing_run_id", "briefing_items", ["briefing_run_id"]
    )
    op.create_index(
        "ix_briefing_items_user_id", "briefing_items", ["user_id"]
    )
    op.create_index(
        "ix_briefing_items_instrument_id", "briefing_items", ["instrument_id"]
    )
    op.create_index(
        "ix_briefing_items_materiality", "briefing_items", ["materiality"]
    )


def downgrade() -> None:
    op.drop_index("ix_briefing_items_materiality", table_name="briefing_items")
    op.drop_index("ix_briefing_items_instrument_id", table_name="briefing_items")
    op.drop_index("ix_briefing_items_user_id", table_name="briefing_items")
    op.drop_index("ix_briefing_items_briefing_run_id", table_name="briefing_items")
    op.drop_table("briefing_items")
    op.drop_index("ix_briefing_runs_generated_at", table_name="briefing_runs")
    op.drop_index("ix_briefing_runs_user_id", table_name="briefing_runs")
    op.drop_table("briefing_runs")
    op.drop_index("ix_decision_log_event_type", table_name="decision_log_entries")
    op.drop_index("ix_decision_log_asset_id", table_name="decision_log_entries")
    op.drop_index("ix_decision_log_instrument_id", table_name="decision_log_entries")
    op.drop_index("ix_decision_log_occurred_at", table_name="decision_log_entries")
    op.drop_index("ix_decision_log_user_id", table_name="decision_log_entries")
    op.drop_table("decision_log_entries")
