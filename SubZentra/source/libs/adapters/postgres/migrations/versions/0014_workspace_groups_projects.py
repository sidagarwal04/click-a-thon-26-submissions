"""Add tenant-scoped organizational Groups and Projects."""

from alembic import op
from sqlalchemy import inspect

from zentra_adapter_postgres.schema import projects, workspace_groups

revision = "0014_workspace_groups_projects"
down_revision = "0013_outbox_investigation_index"
branch_labels = None
depends_on = None


def _install_tenant_policy(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(f"DROP POLICY IF EXISTS {table_name}_tenant_isolation ON {table_name}")
    op.execute(
        f"""
        CREATE POLICY {table_name}_tenant_isolation ON {table_name}
        USING (
          tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        )
        WITH CHECK (
          tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        )
        """
    )
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO zentra_runtime"
    )


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(inspect(bind).get_table_names())
    if "workspace_groups" not in existing:
        workspace_groups.create(bind=bind)
    if "projects" not in existing:
        projects.create(bind=bind)
    _install_tenant_policy("workspace_groups")
    _install_tenant_policy("projects")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS projects")
    op.execute("DROP TABLE IF EXISTS workspace_groups")
