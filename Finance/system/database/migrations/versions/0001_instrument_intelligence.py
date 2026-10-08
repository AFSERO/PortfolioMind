"""Instrument identity and current intelligence state.

Enum values are frozen here, independently of future application changes.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

thesis = postgresql.ENUM(
    "STRONGER", "UNCHANGED", "WEAKER", "INVALIDATED", name="thesis_status", create_type=False
)
valuation = postgresql.ENUM(
    "ATTRACTIVE", "FAIR", "EXPENSIVE", name="valuation_status", create_type=False
)
technical = postgresql.ENUM(
    "ON_TRACK", "NEUTRAL", "DEVIATED", "REVIEW_REQUIRED", name="technical_status", create_type=False
)
recommendation = postgresql.ENUM(
    "ADD", "HOLD", "REDUCE", "SELL", "REVIEW_REQUIRED", name="recommendation", create_type=False
)


def timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade():
    for enum in (thesis, valuation, technical, recommendation):
        enum.create(op.get_bind())
    op.create_table(
        "instruments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("instrument_type", sa.String(64), nullable=False),
        sa.Column("venue", sa.String(128), nullable=True),
        sa.Column("currency", sa.String(16), nullable=False),
        *timestamps(),
    )
    op.create_table(
        "intelligence_states",
        sa.Column("instrument_id", sa.Uuid(), sa.ForeignKey("instruments.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("thesis_status", thesis, nullable=True),
        sa.Column("valuation_status", valuation, nullable=True),
        sa.Column("technical_status", technical, nullable=True),
        sa.Column("recommendation", recommendation, nullable=True),
        sa.Column("last_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_monitoring_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
    )


def downgrade():
    op.drop_table("intelligence_states")
    op.drop_table("instruments")
    for enum in (recommendation, technical, valuation, thesis):
        enum.drop(op.get_bind())
