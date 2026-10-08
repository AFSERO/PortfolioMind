"""add copilot_action_proposals and copilot_audit_logs tables

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-09-25 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "k1l2m3n4o5p6"
down_revision: Union[str, None] = "j0k1l2m3n4o5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. copilot_action_proposals
    op.create_table(
        "copilot_action_proposals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("permission_level", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="DRAFT", nullable=False),
        sa.Column(
            "parameters",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "expected_impact",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "current_state_snapshot",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.Column("human_readable_summary", sa.Text(), nullable=False),
        sa.Column(
            "warnings",
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
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "execution_result",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["copilot_conversations.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_copilot_action_proposals_user_id",
        "copilot_action_proposals",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_copilot_action_proposals_conversation_id",
        "copilot_action_proposals",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_copilot_action_proposals_status",
        "copilot_action_proposals",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_copilot_action_proposals_idempotency_key",
        "copilot_action_proposals",
        ["idempotency_key"],
        unique=False,
    )
    op.create_index(
        "ix_copilot_action_proposals_created_at",
        "copilot_action_proposals",
        ["created_at"],
        unique=False,
    )

    # 2. copilot_audit_logs
    op.create_table(
        "copilot_audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=True),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("user_request", sa.Text(), nullable=True),
        sa.Column("interpreted_intent", sa.String(length=64), nullable=True),
        sa.Column("affected_resource_type", sa.String(length=64), nullable=False),
        sa.Column("affected_resource_id", sa.String(length=128), nullable=True),
        sa.Column(
            "old_state",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "new_state",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.Column("execution_status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["proposal_id"], ["copilot_action_proposals.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_copilot_audit_logs_user_id",
        "copilot_audit_logs",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_copilot_audit_logs_proposal_id",
        "copilot_audit_logs",
        ["proposal_id"],
        unique=False,
    )
    op.create_index(
        "ix_copilot_audit_logs_idempotency_key",
        "copilot_audit_logs",
        ["idempotency_key"],
        unique=False,
    )
    op.create_index(
        "ix_copilot_audit_logs_created_at",
        "copilot_audit_logs",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_copilot_audit_logs_created_at", table_name="copilot_audit_logs")
    op.drop_index("ix_copilot_audit_logs_idempotency_key", table_name="copilot_audit_logs")
    op.drop_index("ix_copilot_audit_logs_proposal_id", table_name="copilot_audit_logs")
    op.drop_index("ix_copilot_audit_logs_user_id", table_name="copilot_audit_logs")
    op.drop_table("copilot_audit_logs")

    op.drop_index("ix_copilot_action_proposals_created_at", table_name="copilot_action_proposals")
    op.drop_index("ix_copilot_action_proposals_idempotency_key", table_name="copilot_action_proposals")
    op.drop_index("ix_copilot_action_proposals_status", table_name="copilot_action_proposals")
    op.drop_index("ix_copilot_action_proposals_conversation_id", table_name="copilot_action_proposals")
    op.drop_index("ix_copilot_action_proposals_user_id", table_name="copilot_action_proposals")
    op.drop_table("copilot_action_proposals")
