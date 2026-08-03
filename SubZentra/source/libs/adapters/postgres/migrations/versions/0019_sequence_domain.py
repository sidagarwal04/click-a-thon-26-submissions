"""Add the Sequence domain: raw table -> typed transform steps -> final tables."""

from alembic import op

from zentra_adapter_postgres.schema import (
    metadata,
    prepared_tables,
    sequence_final_tables,
    sequence_runs,
    sequence_steps,
    sequences,
)

revision = "0019_sequence_domain"
down_revision = "0018_merge_heads"
branch_labels = None
depends_on = None

_TABLES_IN_DEPENDENCY_ORDER = (
    sequences,
    sequence_steps,
    prepared_tables,
    sequence_runs,
    sequence_final_tables,
)


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
    metadata.create_all(bind=bind, tables=_TABLES_IN_DEPENDENCY_ORDER, checkfirst=True)
    for table in _TABLES_IN_DEPENDENCY_ORDER:
        _install_tenant_policy(table.name)


def downgrade() -> None:
    for table in reversed(_TABLES_IN_DEPENDENCY_ORDER):
        op.execute(f"DROP TABLE IF EXISTS {table.name}")
