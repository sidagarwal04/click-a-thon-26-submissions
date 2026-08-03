"""Add the coordinated evidence-erasure operation.

Internal: no route reaches it. The shape and its guarantees land before the
user-facing workflow that invokes them, so the first thing a Tenant can do is
not the thing that has never run.
"""

from alembic import op
from sqlalchemy import inspect

from zentra_adapter_postgres.schema import erasure_operations

revision = "0012_erasure_operations"
down_revision = "0011_approval_failed_conditions"
branch_labels = None
depends_on = None

TABLE = "erasure_operations"


def upgrade() -> None:
    bind = op.get_bind()
    # 0001 builds from `schema.py` via create_all, so a fresh database already
    # has it. Guarding the create is what makes a rerun safe on both.
    if TABLE not in set(inspect(bind).get_table_names()):
        erasure_operations.create(bind=bind)

    op.execute(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(f"DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE}")
    op.execute(
        f"""
        CREATE POLICY {TABLE}_tenant_isolation ON {TABLE}
        USING (
          tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        )
        WITH CHECK (
          tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        )
        """
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {TABLE} TO zentra_runtime")


def downgrade() -> None:
    op.execute(f"REVOKE ALL ON {TABLE} FROM zentra_runtime")
    op.execute(f"DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE}")
    op.execute(f"DROP TABLE IF EXISTS {TABLE}")
