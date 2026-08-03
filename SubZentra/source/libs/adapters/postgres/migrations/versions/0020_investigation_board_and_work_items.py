"""Add the Investigation Board, Work Item queue, and Analytical Scope
(ADR-0026, ADR-0027): the durable working memory an Orchestrator Loop reads
and writes in place of a fixed LangGraph pipeline.
"""

from alembic import op

from zentra_adapter_postgres.schema import (
    analytical_scopes,
    board_conflicts,
    board_facts,
    board_gaps,
    board_hypotheses,
    investigation_boards,
    metadata,
    work_items,
)

revision = "0020_investigation_board_and_work_items"
down_revision = "0019_sequence_domain"
branch_labels = None
depends_on = None

_TABLES_IN_DEPENDENCY_ORDER = (
    investigation_boards,
    board_facts,
    board_hypotheses,
    board_gaps,
    board_conflicts,
    work_items,
    analytical_scopes,
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
