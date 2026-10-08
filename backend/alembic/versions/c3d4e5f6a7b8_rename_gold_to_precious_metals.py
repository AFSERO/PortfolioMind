"""rename GOLD asset_type to PRECIOUS_METALS

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE assets SET asset_type = 'PRECIOUS_METALS' WHERE asset_type = 'GOLD'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE assets SET asset_type = 'GOLD' WHERE asset_type = 'PRECIOUS_METALS'"
    )
