"""add investment intelligence tables

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-09-16 00:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create instrument_intelligence_states table
    op.create_table(
        "instrument_intelligence_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column(
            "thesis_status",
            sa.Enum(
                "STRONGER",
                "UNCHANGED",
                "WEAKER",
                "INVALIDATED",
                name="thesisstatus",
                native_enum=False,
                length=20,
            ),
            nullable=True,
        ),
        sa.Column(
            "valuation_status",
            sa.Enum(
                "ATTRACTIVE",
                "FAIR",
                "EXPENSIVE",
                name="valuationstatus",
                native_enum=False,
                length=20,
            ),
            nullable=True,
        ),
        sa.Column(
            "technical_status",
            sa.Enum(
                "ON_TRACK",
                "NEUTRAL",
                "DEVIATED",
                "REVIEW_REQUIRED",
                name="technicalstatus",
                native_enum=False,
                length=20,
            ),
            nullable=True,
        ),
        sa.Column(
            "recommendation",
            sa.Enum(
                "ADD",
                "HOLD",
                "REDUCE",
                "SELL",
                "REVIEW_REQUIRED",
                name="recommendation",
                native_enum=False,
                length=20,
            ),
            nullable=True,
        ),
        sa.Column("last_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_monitoring_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("human_brief", sa.Text(), nullable=True),
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
            ["instrument_id"], ["instruments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("instrument_id"),
    )
    op.create_index(
        "ix_intelligence_states_instrument_id",
        "instrument_intelligence_states",
        ["instrument_id"],
        unique=True,
    )

    # 2. Create intelligence_reviews table
    op.create_table(
        "intelligence_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("protocol", sa.String(length=128), nullable=False),
        sa.Column("run_type", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "RUNNING",
                "COMPLETED",
                "FAILED",
                name="protocolrunstatus",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column(
            "machine_record",
            sa.JSON().with_variant(JSONB, "postgresql"),
            nullable=True,
        ),
        sa.Column("human_brief", sa.Text(), nullable=True),
        sa.Column("confidence", sa.String(length=32), nullable=True),
        sa.Column("research_path", sa.Text(), nullable=True),
        sa.Column("source_run_id", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_intelligence_reviews_instrument_id",
        "intelligence_reviews",
        ["instrument_id"],
    )
    op.create_index(
        "ix_intelligence_reviews_created_at",
        "intelligence_reviews",
        ["created_at"],
    )

    # 3. Create technical_plans table
    op.create_table(
        "technical_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column(
            "reference_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("reference_price", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("trend_expectation", sa.Text(), nullable=True),
        sa.Column(
            "entry_zones",
            sa.JSON().with_variant(JSONB, "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "support_zones",
            sa.JSON().with_variant(JSONB, "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "resistance_zones",
            sa.JSON().with_variant(JSONB, "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "review_or_invalidation_zones",
            sa.JSON().with_variant(JSONB, "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "profit_taking_or_reassessment_zones",
            sa.JSON().with_variant(JSONB, "postgresql"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
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
            ["instrument_id"], ["instruments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_technical_plans_instrument_id",
        "technical_plans",
        ["instrument_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_technical_plans_instrument_id", table_name="technical_plans")
    op.drop_table("technical_plans")
    op.drop_index("ix_intelligence_reviews_created_at", table_name="intelligence_reviews")
    op.drop_index("ix_intelligence_reviews_instrument_id", table_name="intelligence_reviews")
    op.drop_table("intelligence_reviews")
    op.drop_index("ix_intelligence_states_instrument_id", table_name="instrument_intelligence_states")
    op.drop_table("instrument_intelligence_states")
