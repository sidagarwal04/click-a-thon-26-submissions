"""Add Draft Investigation Threads and immutable messages."""

import sqlalchemy as sa
from alembic import op

from zentra_adapter_postgres.schema import (
    investigation_threads,
    metadata,
    thread_messages,
)

revision = "0015_draft_investigation_threads"
down_revision = "0014_workspace_groups_projects"
branch_labels = None
depends_on = None


def _install_policy(table_name: str, *, grants: str) -> None:
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
    op.execute(f"GRANT {grants} ON {table_name} TO zentra_runtime")


def upgrade() -> None:
    bind = op.get_bind()
    metadata.create_all(
        bind=bind,
        tables=[investigation_threads, thread_messages],
        checkfirst=True,
    )
    _install_policy("investigation_threads", grants="SELECT, INSERT, UPDATE, DELETE")
    _install_policy("thread_messages", grants="SELECT, INSERT")

    op.add_column("investigations", sa.Column("thread_id", sa.UUID(), nullable=True))
    op.add_column(
        "investigations", sa.Column("thread_sequence", sa.Integer(), nullable=True)
    )
    op.add_column(
        "investigations",
        sa.Column("initiating_message_id", sa.UUID(), nullable=True),
    )
    op.create_check_constraint(
        "ck_investigations_thread_link",
        "investigations",
        "(thread_id IS NULL AND thread_sequence IS NULL AND "
        "initiating_message_id IS NULL) OR "
        "(thread_id IS NOT NULL AND thread_sequence >= 1 AND "
        "initiating_message_id IS NOT NULL)",
    )
    op.create_unique_constraint(
        "uq_investigations_thread_sequence",
        "investigations",
        ["thread_id", "thread_sequence"],
    )
    op.create_foreign_key(
        "fk_investigations_thread_tenant",
        "investigations",
        "investigation_threads",
        ["thread_id", "tenant_id"],
        ["thread_id", "tenant_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_investigations_initiating_message",
        "investigations",
        "thread_messages",
        ["initiating_message_id", "thread_id", "tenant_id"],
        ["message_id", "thread_id", "tenant_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_investigations_initiating_message", "investigations", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_investigations_thread_tenant", "investigations", type_="foreignkey"
    )
    op.drop_constraint(
        "uq_investigations_thread_sequence", "investigations", type_="unique"
    )
    op.drop_constraint("ck_investigations_thread_link", "investigations", type_="check")
    op.drop_column("investigations", "initiating_message_id")
    op.drop_column("investigations", "thread_sequence")
    op.drop_column("investigations", "thread_id")
    # fk_investigation_threads_initiating_message is use_alter=True/deferrable
    # in schema_threads.py precisely because it's the closing edge of a
    # circular FK between these two tables. That DDL choreography only
    # applies to SQLAlchemy-driven create_all/drop_all; these raw DROP TABLE
    # statements bypass it, so the circular edge must be broken explicitly
    # before either table can be dropped.
    op.execute(
        "ALTER TABLE investigation_threads "
        "DROP CONSTRAINT IF EXISTS fk_investigation_threads_initiating_message"
    )
    op.execute("DROP TABLE IF EXISTS thread_messages")
    op.execute("DROP TABLE IF EXISTS investigation_threads")
