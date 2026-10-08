"""Part 2 integrity fix: artifact and instrument-level run must agree."""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    # ProtocolRun.instrument_id is already immutable, so only artifact writes
    # can introduce a mismatch. Missing parents remain the foreign key's job.
    op.execute("""
        CREATE FUNCTION ii_check_artifact_run_instrument() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE run_instrument uuid;
        BEGIN
            IF NEW.protocol_run_id IS NOT NULL THEN
                SELECT instrument_id INTO run_instrument
                FROM protocol_runs WHERE id = NEW.protocol_run_id;
                IF run_instrument IS NOT NULL
                   AND run_instrument IS DISTINCT FROM NEW.instrument_id THEN
                    RAISE EXCEPTION 'ResearchArtifact instrument must match its instrument-level ProtocolRun'
                        USING ERRCODE = '23514', CONSTRAINT = 'artifact_run_instrument_match';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER check_artifact_run_instrument BEFORE INSERT OR UPDATE ON research_artifacts
        FOR EACH ROW EXECUTE FUNCTION ii_check_artifact_run_instrument()
    """)
    # CREATE TRIGGER holds a table lock against concurrent writers until commit.
    # Refuse legacy mismatches rather than rewriting historical attribution.
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM research_artifacts a JOIN protocol_runs r ON r.id = a.protocol_run_id
                WHERE r.instrument_id IS NOT NULL AND r.instrument_id <> a.instrument_id
            ) THEN
                RAISE EXCEPTION 'Existing artifact/run instrument mismatch; correct attribution before upgrade'
                    USING ERRCODE = '23514';
            END IF;
        END $$
    """)


def downgrade():
    op.execute("DROP TRIGGER check_artifact_run_instrument ON research_artifacts")
    op.execute("DROP FUNCTION ii_check_artifact_run_instrument()")
