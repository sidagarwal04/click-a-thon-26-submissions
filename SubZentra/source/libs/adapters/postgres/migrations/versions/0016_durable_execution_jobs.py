"""Add durable Postgres-leased Investigation execution jobs."""

from alembic import op

from zentra_adapter_postgres.schema import execution_jobs, metadata

revision = "0016_durable_execution_jobs"
down_revision = "0015_connector_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_investigations_tenant_identity",
        "investigations",
        ["investigation_id", "tenant_id"],
    )
    metadata.create_all(bind=op.get_bind(), tables=[execution_jobs], checkfirst=True)
    op.execute("ALTER TABLE execution_jobs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE execution_jobs FORCE ROW LEVEL SECURITY")
    op.execute(
        "DROP POLICY IF EXISTS execution_jobs_tenant_isolation ON execution_jobs"
    )
    op.execute(
        """
        CREATE POLICY execution_jobs_tenant_isolation ON execution_jobs
        USING (
          tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        )
        WITH CHECK (
          tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        )
        """
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON execution_jobs TO zentra_runtime"
    )
    # LangGraph owns these wire-compatible checkpoint tables. Alembic creates
    # them so application startup never performs DDL. Their thread identifier
    # is always `<tenant UUID>:<investigation UUID>` and no HTTP repository
    # exposes them.
    op.execute(
        "CREATE TABLE IF NOT EXISTS checkpoint_migrations "
        "(v INTEGER PRIMARY KEY)"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS checkpoints (
          thread_id TEXT NOT NULL,
          tenant_id UUID GENERATED ALWAYS AS
            (split_part(thread_id, ':', 1)::uuid) STORED,
          checkpoint_ns TEXT NOT NULL DEFAULT '',
          checkpoint_id TEXT NOT NULL,
          parent_checkpoint_id TEXT,
          type TEXT,
          checkpoint JSONB NOT NULL,
          metadata JSONB NOT NULL DEFAULT '{}',
          PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS checkpoint_blobs (
          thread_id TEXT NOT NULL,
          tenant_id UUID GENERATED ALWAYS AS
            (split_part(thread_id, ':', 1)::uuid) STORED,
          checkpoint_ns TEXT NOT NULL DEFAULT '',
          channel TEXT NOT NULL,
          version TEXT NOT NULL,
          type TEXT NOT NULL,
          blob BYTEA,
          PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS checkpoint_writes (
          thread_id TEXT NOT NULL,
          tenant_id UUID GENERATED ALWAYS AS
            (split_part(thread_id, ':', 1)::uuid) STORED,
          checkpoint_ns TEXT NOT NULL DEFAULT '',
          checkpoint_id TEXT NOT NULL,
          task_id TEXT NOT NULL,
          idx INTEGER NOT NULL,
          channel TEXT NOT NULL,
          type TEXT,
          blob BYTEA NOT NULL,
          task_path TEXT NOT NULL DEFAULT '',
          PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS checkpoints_thread_id_idx "
        "ON checkpoints(thread_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS checkpoint_blobs_thread_id_idx "
        "ON checkpoint_blobs(thread_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS checkpoint_writes_thread_id_idx "
        "ON checkpoint_writes(thread_id)"
    )
    op.execute(
        "INSERT INTO checkpoint_migrations(v) SELECT generate_series(0, 9) "
        "ON CONFLICT DO NOTHING"
    )
    for table_name in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table_name}_tenant_isolation ON {table_name} "
            "USING (tenant_id = "
            "NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
            "WITH CHECK (tenant_id = "
            "NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
        )
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} "
            "TO zentra_runtime"
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS checkpoint_writes")
    op.execute("DROP TABLE IF EXISTS checkpoint_blobs")
    op.execute("DROP TABLE IF EXISTS checkpoints")
    op.execute("DROP TABLE IF EXISTS checkpoint_migrations")
    op.execute("DROP TABLE IF EXISTS execution_jobs")
    op.drop_constraint(
        "uq_investigations_tenant_identity",
        "investigations",
        type_="unique",
    )
