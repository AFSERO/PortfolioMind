"""Compact, append-only thesis history."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "thesis_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("instrument_id", sa.Uuid(), sa.ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("core_investment_rationale", sa.Text(), nullable=False),
        sa.Column("key_assumptions", postgresql.JSONB(), nullable=False),
        sa.Column("growth_drivers", postgresql.JSONB(), nullable=False),
        sa.Column("moat_or_competitive_assumptions", postgresql.JSONB(), nullable=False),
        sa.Column("key_risks", postgresql.JSONB(), nullable=False),
        sa.Column("invalidation_conditions", postgresql.JSONB(), nullable=False),
        sa.Column("key_kpis", postgresql.JSONB(), nullable=False),
        sa.Column("catalysts", postgresql.JSONB(), nullable=False),
        sa.Column("open_questions", postgresql.JSONB(), nullable=False),
        sa.Column("source_artifact_references", postgresql.JSONB(), nullable=False),
        sa.Column("confidence", sa.String(32)),
        sa.Column("source_protocol_run_id", sa.Uuid(), sa.ForeignKey("protocol_runs.id", ondelete="RESTRICT")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_thesis_snapshots_baseline", "thesis_snapshots", ["instrument_id", "as_of", "created_at", "id"])
    op.execute("""
        CREATE FUNCTION ii_guard_thesis_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE run_instrument uuid;
        BEGIN
            IF TG_OP <> 'INSERT' THEN
                RAISE EXCEPTION 'ThesisSnapshot history is immutable' USING ERRCODE = '23514';
            END IF;
            IF NEW.source_protocol_run_id IS NOT NULL THEN
                SELECT instrument_id INTO run_instrument FROM protocol_runs WHERE id = NEW.source_protocol_run_id;
                IF run_instrument IS NOT NULL AND run_instrument IS DISTINCT FROM NEW.instrument_id THEN
                    RAISE EXCEPTION 'Snapshot source run must match instrument' USING ERRCODE = '23514';
                END IF;
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute("CREATE TRIGGER guard_thesis_snapshot BEFORE INSERT OR UPDATE OR DELETE ON thesis_snapshots FOR EACH ROW EXECUTE FUNCTION ii_guard_thesis_snapshot()")


def downgrade():
    op.drop_table("thesis_snapshots")
    op.execute("DROP FUNCTION ii_guard_thesis_snapshot()")
