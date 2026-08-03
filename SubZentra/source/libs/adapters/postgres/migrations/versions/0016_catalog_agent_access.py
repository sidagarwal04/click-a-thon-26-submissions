"""Add catalog_agent_access: per-table and per-field agent visibility.

Every harvested table and field is visible to agents by default; this table
only ever records a departure from that default. Kept separate from
`catalog_versions.payload`, which is immutable once a Harvest Run completes —
a toggle a Tenant can flip at any time cannot live inside a frozen JSONB blob,
the same reasoning that already put `relations` in its own table in `0015`.
"""

from alembic import op
from sqlalchemy import inspect

from zentra_adapter_postgres.schema import catalog_agent_access

revision = "0016_catalog_agent_access"
down_revision = "0015_connector_catalog"
branch_labels = None
depends_on = None

TABLE_NAME = "catalog_agent_access"


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(inspect(bind).get_table_names())
    if TABLE_NAME not in existing:
        catalog_agent_access.create(bind=bind)

    op.execute(f"ALTER TABLE {TABLE_NAME} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {TABLE_NAME} FORCE ROW LEVEL SECURITY")
    op.execute(f"DROP POLICY IF EXISTS {TABLE_NAME}_tenant_isolation ON {TABLE_NAME}")
    op.execute(
        f"""
        CREATE POLICY {TABLE_NAME}_tenant_isolation ON {TABLE_NAME}
        USING (
          tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        )
        WITH CHECK (
          tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        )
        """
    )
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {TABLE_NAME} TO zentra_runtime"
    )


def downgrade() -> None:
    op.execute(f"REVOKE ALL ON {TABLE_NAME} FROM zentra_runtime")
    op.execute(f"DROP POLICY IF EXISTS {TABLE_NAME}_tenant_isolation ON {TABLE_NAME}")
    op.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
