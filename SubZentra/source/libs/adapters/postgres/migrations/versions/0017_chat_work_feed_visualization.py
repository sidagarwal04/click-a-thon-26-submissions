"""Add the public Work Feed, linked attempts, usage, and visualization state."""

from collections.abc import Callable

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from zentra_adapter_postgres.schema import (
    thread_events,
    visualization_actions,
    visualization_artifacts,
    visualization_briefs,
)

revision = "0017_chat_work_feed_visualization"
down_revision = "0016c_widen_alembic_version_num"
branch_labels = None
depends_on = None


def _column(table: str, column: sa.Column) -> None:
    columns = {value["name"] for value in inspect(op.get_bind()).get_columns(table)}
    if column.name not in columns:
        op.add_column(table, column)


def _policy(table: str, grants: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
    op.execute(
        f"""
        CREATE POLICY {table}_tenant_isolation ON {table}
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (
          tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        )
        """
    )
    op.execute(f"GRANT {grants} ON {table} TO zentra_runtime")


def _constraint(table: str, name: str, create: Callable[[], None]) -> None:
    names = {value["name"] for value in inspect(op.get_bind()).get_foreign_keys(table)}
    names.update(
        value["name"] for value in inspect(op.get_bind()).get_check_constraints(table)
    )
    if name not in names:
        create()


def upgrade() -> None:
    _column(
        "investigation_threads",
        sa.Column(
            "next_event_sequence", sa.Integer(), nullable=False, server_default="1"
        ),
    )
    _column("investigations", sa.Column("parent_investigation_id", sa.UUID()))
    _column("investigations", sa.Column("retry_of_investigation_id", sa.UUID()))

    for _name, column in (
        ("role", sa.Column("role", sa.String(64))),
        ("provider", sa.Column("provider", sa.String(64))),
        (
            "input_tokens",
            sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        ),
        (
            "output_tokens",
            sa.Column(
                "output_tokens", sa.Integer(), nullable=False, server_default="0"
            ),
        ),
        (
            "fallbacks",
            sa.Column(
                "fallbacks", sa.JSON(), nullable=False, server_default=sa.text("'[]'")
            ),
        ),
    ):
        _column("agent_executions", column)

    for column in (
        sa.Column("display_name", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column(
            "capabilities", sa.JSON(), nullable=False, server_default=sa.text("'[]'")
        ),
    ):
        _column("agent_registry", column)

    for column in (
        sa.Column(
            "job_kind",
            sa.String(24),
            nullable=False,
            server_default="investigation",
        ),
        sa.Column("visualization_id", sa.UUID()),
        sa.Column("cancel_requested_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("cancel_requested_by", sa.UUID()),
    ):
        _column("execution_jobs", column)

    _constraint(
        "investigations",
        "fk_investigations_parent_tenant",
        lambda: op.create_foreign_key(
            "fk_investigations_parent_tenant",
            "investigations",
            "investigations",
            ["parent_investigation_id", "tenant_id"],
            ["investigation_id", "tenant_id"],
        ),
    )
    _constraint(
        "investigations",
        "fk_investigations_retry_tenant",
        lambda: op.create_foreign_key(
            "fk_investigations_retry_tenant",
            "investigations",
            "investigations",
            ["retry_of_investigation_id", "tenant_id"],
            ["investigation_id", "tenant_id"],
        ),
    )
    _constraint(
        "execution_jobs",
        "ck_execution_jobs_kind",
        lambda: op.create_check_constraint(
            "ck_execution_jobs_kind",
            "execution_jobs",
            "job_kind IN ('investigation', 'visualization')",
        ),
    )
    _constraint(
        "execution_jobs",
        "ck_execution_jobs_target",
        lambda: op.create_check_constraint(
            "ck_execution_jobs_target",
            "execution_jobs",
            "(job_kind = 'investigation' AND investigation_id IS NOT NULL "
            "AND visualization_id IS NULL) OR "
            "(job_kind = 'visualization' AND visualization_id IS NOT NULL)",
        ),
    )

    bind = op.get_bind()
    for table in (
        thread_events,
        visualization_briefs,
        visualization_artifacts,
        visualization_actions,
    ):
        table.create(bind=bind, checkfirst=True)

    _policy("thread_events", "SELECT, INSERT")
    _policy("visualization_briefs", "SELECT, INSERT, UPDATE")
    _policy("visualization_artifacts", "SELECT, INSERT, UPDATE")
    _policy("visualization_actions", "SELECT, INSERT, UPDATE, DELETE")

    op.execute(
        "ALTER TABLE execution_jobs "
        "DROP CONSTRAINT IF EXISTS uq_execution_jobs_investigation"
    )
    op.execute("DROP INDEX IF EXISTS uq_execution_jobs_investigation")
    op.execute(
        "CREATE UNIQUE INDEX uq_execution_jobs_investigation "
        "ON execution_jobs(tenant_id, investigation_id) "
        "WHERE job_kind = 'investigation'"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_execution_jobs_visualization "
        "ON execution_jobs(tenant_id, visualization_id) "
        "WHERE job_kind = 'visualization'"
    )
    op.execute(
        """
        INSERT INTO agent_registry(
          agent_id, role, version, enabled, eval_status, eval_suite_ref,
          display_name, description, capabilities
        ) VALUES (
          'data_visualization_v1', 'visualization', '1.0', true, 'passing',
          'evals://data-visualization/v1', 'Data Visualization Agent',
          'Turns a published, cited Visualization Brief into presentation-only UI.',
          json_build_array(json_build_object(
            'capability_id', 'render_published_finding',
            'version', '1.0',
            'display_name', 'Render published finding',
            'description',
            'Creates presentation UI from an immutable governed brief.'
          ))
        )
        ON CONFLICT (agent_id) DO UPDATE SET
          version = EXCLUDED.version,
          enabled = EXCLUDED.enabled,
          eval_status = EXCLUDED.eval_status,
          eval_suite_ref = EXCLUDED.eval_suite_ref,
          display_name = EXCLUDED.display_name,
          description = EXCLUDED.description,
          capabilities = EXCLUDED.capabilities
        """
    )


def downgrade() -> None:
    for table in (
        "visualization_actions",
        "visualization_artifacts",
        "visualization_briefs",
        "thread_events",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")
    for column in (
        "cancel_requested_by",
        "cancel_requested_at",
        "visualization_id",
        "job_kind",
    ):
        op.drop_column("execution_jobs", column)
    op.create_unique_constraint(
        "uq_execution_jobs_investigation",
        "execution_jobs",
        ["tenant_id", "investigation_id"],
    )
    for column in ("capabilities", "description", "display_name"):
        op.drop_column("agent_registry", column)
    for column in ("fallbacks", "output_tokens", "input_tokens", "provider", "role"):
        op.drop_column("agent_executions", column)
    op.drop_constraint(
        "fk_investigations_retry_tenant", "investigations", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_investigations_parent_tenant", "investigations", type_="foreignkey"
    )
    op.drop_column("investigations", "retry_of_investigation_id")
    op.drop_column("investigations", "parent_investigation_id")
    op.drop_column("investigation_threads", "next_event_sequence")
