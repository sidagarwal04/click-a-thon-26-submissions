"""Add Data Sources, so a registered Connector source survives a restart.

The Connector's HTTP surface, domain and application service all shipped
already; nothing under them ever stored a row. This is the table that makes
`POST /v1/connector/sources` mean something.

`sealed_credentials` is `bytea` holding AES-GCM ciphertext. RLS is what makes a
credential belong to exactly one Tenant even if a query forgets to say so.
"""

from alembic import op
from sqlalchemy import inspect

from zentra_adapter_postgres.schema import data_sources

revision = "0014_data_sources"
# Re-pointed at the workspace/threads chain rather than at 0013 directly. Both
# branched from 0013 and Alembic will not resolve two heads; this one moved
# because it had not been pushed. The number is left alone — renaming a
# revision would break any database already stamped with it.
down_revision = "0015_draft_investigation_threads"
branch_labels = None
depends_on = None

TABLE = "data_sources"


def upgrade() -> None:
    bind = op.get_bind()
    # 0001 builds from `schema.py` via create_all, so a fresh database already
    # has it. Guarding the create is what makes a rerun safe on both.
    if TABLE not in set(inspect(bind).get_table_names()):
        data_sources.create(bind=bind)

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
