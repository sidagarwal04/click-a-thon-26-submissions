"""Create the ZentraOS Phase 0 control-plane schema."""

from alembic import op

from zentra_adapter_postgres.schema import metadata

revision = "0001_phase0"
down_revision = None
branch_labels = None
depends_on = None

TENANT_TABLES = (
    "tenants",
    "tenant_memberships",
    "investigations",
    "agent_executions",
    "human_approvals",
    "semantic_metrics",
)


def upgrade() -> None:
    bind = op.get_bind()
    metadata.create_all(bind=bind)

    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'zentra_runtime') THEN
            CREATE ROLE zentra_runtime NOLOGIN NOSUPERUSER NOBYPASSRLS;
          END IF;
        END
        $$;
        """
    )
    for table in TENANT_TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY')
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation ON "{table}"
            USING (
              tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            )
            WITH CHECK (
              tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            )
            """
        )

    op.execute("GRANT USAGE ON SCHEMA public TO zentra_runtime")
    op.execute(
        "GRANT SELECT ON users, identity_subjects, tenant_identity_bindings, "
        "agent_registry TO zentra_runtime"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON tenants, tenant_memberships, "
        "investigations, agent_executions, human_approvals, semantic_metrics "
        "TO zentra_runtime"
    )


def downgrade() -> None:
    metadata.drop_all(bind=op.get_bind())
