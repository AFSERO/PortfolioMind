"""add codex session columns to copilot_conversations

Revision ID: n4o5p6q7r8s9
Revises: 87cbaa8cd11a
Create Date: 2026-09-30 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "n4o5p6q7r8s9"
down_revision: Union[str, None] = "87cbaa8cd11a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "copilot_conversations",
        sa.Column("codex_session_id", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_copilot_conversations_codex_session_id",
        "copilot_conversations",
        ["codex_session_id"],
        unique=False,
    )
    op.add_column(
        "copilot_conversations",
        sa.Column("codex_session_status", sa.String(length=32), nullable=True, server_default="ACTIVE"),
    )
    op.add_column(
        "copilot_conversations",
        sa.Column(
            "session_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("copilot_conversations", "session_metadata")
    op.drop_column("copilot_conversations", "codex_session_status")
    op.drop_index("ix_copilot_conversations_codex_session_id", table_name="copilot_conversations")
    op.drop_column("copilot_conversations", "codex_session_id")
