"""add trigger_type to briefing_runs

Revision ID: g7h8i9j0k1l2
Revises: e6f7a8b9c0d1
Create Date: 2026-09-17 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g7h8i9j0k1l2"
down_revision: Union[str, None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "briefing_runs",
        sa.Column(
            "trigger_type",
            sa.String(length=20),
            server_default="MANUAL",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("briefing_runs", "trigger_type")
