"""Generic protocol history, filesystem references and technical plans."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

run_status = postgresql.ENUM(
    "RUNNING", "COMPLETED", "FAILED", name="protocol_run_status", create_type=False
)


def upgrade():
    run_status.create(op.get_bind())
    op.create_table(
        "protocol_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("instrument_id", sa.Uuid(), sa.ForeignKey("instruments.id", ondelete="RESTRICT")),
        sa.Column("protocol_name", sa.String(128), nullable=False),
        sa.Column("status", run_status, nullable=False, server_default="RUNNING"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("machine_record", postgresql.JSONB(none_as_null=True)),
        sa.Column("human_brief", sa.Text()),
        sa.Column("confidence", sa.String(32)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "(status = 'RUNNING' AND completed_at IS NULL) OR "
            "(status IN ('COMPLETED', 'FAILED') AND completed_at IS NOT NULL)",
            name="ck_protocol_runs_completion",
        ),
        sa.CheckConstraint("completed_at >= started_at", name="ck_protocol_runs_time_order"),
    )
    op.create_index("ix_protocol_runs_instrument_id", "protocol_runs", ["instrument_id"])
    op.create_table(
        "research_artifacts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("instrument_id", sa.Uuid(), sa.ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("artifact_type", sa.String(64), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("version", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("protocol_run_id", sa.Uuid(), sa.ForeignKey("protocol_runs.id", ondelete="RESTRICT")),
        sa.Column("metadata", postgresql.JSONB(none_as_null=True)),
    )
    op.create_index("ix_research_artifacts_instrument_id", "research_artifacts", ["instrument_id"])
    op.create_index("ix_research_artifacts_protocol_run_id", "research_artifacts", ["protocol_run_id"])
    op.create_table(
        "technical_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("instrument_id", sa.Uuid(), sa.ForeignKey("instruments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reference_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reference_price", sa.Numeric(28, 12)),
        sa.Column("trend_expectation", sa.Text()),
        sa.Column("entry_zones", postgresql.JSONB(none_as_null=True)),
        sa.Column("support_zones", postgresql.JSONB(none_as_null=True)),
        sa.Column("resistance_zones", postgresql.JSONB(none_as_null=True)),
        sa.Column("review_or_invalidation_zones", postgresql.JSONB(none_as_null=True)),
        sa.Column("profit_taking_or_reassessment_zones", postgresql.JSONB(none_as_null=True)),
        sa.Column("notes", sa.Text()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_technical_plans_instrument_id", "technical_plans", ["instrument_id"])
    op.create_index("uq_technical_plans_active_instrument", "technical_plans", ["instrument_id"],
                    unique=True, postgresql_where=sa.text("active"))

    # Integrity guards only: no execution, routing or IntelligenceState updates.
    op.execute("""
        CREATE FUNCTION ii_guard_protocol_run() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'ProtocolRun history cannot be deleted' USING ERRCODE = '23514';
            END IF;
            IF OLD.status IN ('COMPLETED', 'FAILED') THEN
                RAISE EXCEPTION 'Terminal ProtocolRun is immutable' USING ERRCODE = '23514';
            END IF;
            IF NEW.id IS DISTINCT FROM OLD.id
               OR NEW.instrument_id IS DISTINCT FROM OLD.instrument_id
               OR NEW.protocol_name IS DISTINCT FROM OLD.protocol_name
               OR NEW.started_at IS DISTINCT FROM OLD.started_at
               OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                RAISE EXCEPTION 'ProtocolRun identity and start time are immutable' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER guard_protocol_run BEFORE UPDATE OR DELETE ON protocol_runs
        FOR EACH ROW EXECUTE FUNCTION ii_guard_protocol_run()
    """)
    op.execute("""
        CREATE FUNCTION ii_preserve_technical_plan() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'TechnicalPlan history cannot be deleted; deactivate it instead'
                USING ERRCODE = '23514';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER preserve_technical_plan BEFORE DELETE ON technical_plans
        FOR EACH ROW EXECUTE FUNCTION ii_preserve_technical_plan()
    """)


def downgrade():
    # Dropping the tables removes their triggers without executing row DELETEs.
    op.drop_table("technical_plans")
    op.drop_table("research_artifacts")
    op.drop_table("protocol_runs")
    op.execute("DROP FUNCTION ii_preserve_technical_plan()")
    op.execute("DROP FUNCTION ii_guard_protocol_run()")
    run_status.drop(op.get_bind())
