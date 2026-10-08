"""add investor profile tables

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-09-29 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "m3n4o5p6q7r8"
down_revision: Union[str, None] = "l2m3n4o5p6q7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. investor_profiles
    op.create_table(
        "investor_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("active_version_id", sa.Uuid(), nullable=True),
        sa.Column("active_preferences_revision_id", sa.Uuid(), nullable=True),
        sa.Column("completeness_overall_pct", sa.Numeric(precision=5, scale=2), server_default="0.00", nullable=False),
        sa.Column(
            "analysis_readiness",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        "ix_investor_profiles_user_id",
        "investor_profiles",
        ["user_id"],
        unique=True,
    )
    op.create_index(
        "ix_investor_profiles_active_version_id",
        "investor_profiles",
        ["active_version_id"],
        unique=False,
    )

    # 2. investor_profile_assessments
    op.create_table(
        "investor_profile_assessments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("base_version_id", sa.Uuid(), nullable=True),
        sa.Column("questionnaire_version", sa.String(length=32), server_default="1.0", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="DRAFT", nullable=False),
        sa.Column("resume_question_id", sa.String(length=32), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_investor_profile_assessments_user_id",
        "investor_profile_assessments",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_investor_profile_assessments_status",
        "investor_profile_assessments",
        ["status"],
        unique=False,
    )

    # 3. investor_profile_answers
    op.create_table(
        "investor_profile_answers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.String(length=32), nullable=False),
        sa.Column("item_id", sa.String(length=64), nullable=True),
        sa.Column("knowledge_state", sa.String(length=32), server_default="KNOWN", nullable=False),
        sa.Column(
            "selected_options",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
        sa.Column(
            "numeric_inputs",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("locale", sa.String(length=16), server_default="en", nullable=False),
        sa.Column(
            "answered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["assessment_id"], ["investor_profile_assessments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_investor_profile_answers_assessment_id",
        "investor_profile_answers",
        ["assessment_id"],
        unique=False,
    )
    op.create_index(
        "ix_investor_profile_answers_user_id",
        "investor_profile_answers",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_investor_profile_answers_question_id",
        "investor_profile_answers",
        ["question_id"],
        unique=False,
    )

    # 4. investor_profile_versions
    op.create_table(
        "investor_profile_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("previous_version_id", sa.Uuid(), nullable=True),
        sa.Column("change_reason", sa.String(length=255), nullable=False),
        sa.Column("change_source", sa.String(length=64), nullable=False),
        sa.Column(
            "snapshot",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("confirmed_by", sa.Uuid(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["investor_profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_investor_profile_versions_profile_id",
        "investor_profile_versions",
        ["profile_id"],
        unique=False,
    )
    op.create_index(
        "ix_investor_profile_versions_user_id",
        "investor_profile_versions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_investor_profile_versions_version_number",
        "investor_profile_versions",
        ["version_number"],
        unique=False,
    )

    # 5. investor_profile_drafts
    op.create_table(
        "investor_profile_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=True),
        sa.Column("base_version_id", sa.Uuid(), nullable=True),
        sa.Column(
            "draft_data",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assessment_id"], ["investor_profile_assessments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_investor_profile_drafts_user_id",
        "investor_profile_drafts",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_investor_profile_drafts_assessment_id",
        "investor_profile_drafts",
        ["assessment_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_investor_profile_drafts_assessment_id", table_name="investor_profile_drafts")
    op.drop_index("ix_investor_profile_drafts_user_id", table_name="investor_profile_drafts")
    op.drop_table("investor_profile_drafts")

    op.drop_index("ix_investor_profile_versions_version_number", table_name="investor_profile_versions")
    op.drop_index("ix_investor_profile_versions_user_id", table_name="investor_profile_versions")
    op.drop_index("ix_investor_profile_versions_profile_id", table_name="investor_profile_versions")
    op.drop_table("investor_profile_versions")

    op.drop_index("ix_investor_profile_answers_question_id", table_name="investor_profile_answers")
    op.drop_index("ix_investor_profile_answers_user_id", table_name="investor_profile_answers")
    op.drop_index("ix_investor_profile_answers_assessment_id", table_name="investor_profile_answers")
    op.drop_table("investor_profile_answers")

    op.drop_index("ix_investor_profile_assessments_status", table_name="investor_profile_assessments")
    op.drop_index("ix_investor_profile_assessments_user_id", table_name="investor_profile_assessments")
    op.drop_table("investor_profile_assessments")

    op.drop_index("ix_investor_profiles_active_version_id", table_name="investor_profiles")
    op.drop_index("ix_investor_profiles_user_id", table_name="investor_profiles")
    op.drop_table("investor_profiles")
