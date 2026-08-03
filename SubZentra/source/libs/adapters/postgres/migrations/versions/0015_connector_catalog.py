"""Add Catalog Versions, Relations and Harvest Runs.

The harvest half of the Connector. `0014` made a registered source survive a
restart; this makes what a harvest learned — and what a reviewer decided about
it — survive one too. A confirmed Relation that vanished on deploy would mean
the Join Graph was a cache, not a record of a governance decision.

Catalog Versions carry a JSONB payload rather than normalised table and field
rows: they are immutable once written and always read whole.
"""

from alembic import op
from sqlalchemy import inspect

from zentra_adapter_postgres.schema import (
    catalog_versions,
    harvest_runs,
    relations,
)

revision = "0015_connector_catalog"
down_revision = "0014_data_sources"
branch_labels = None
depends_on = None

# Order matters: relations reference catalog_versions.
TABLES = (
    ("catalog_versions", catalog_versions),
    ("relations", relations),
    ("harvest_runs", harvest_runs),
)


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(inspect(bind).get_table_names())
    for name, table in TABLES:
        # 0001 builds from `schema.py` via create_all, so a fresh database
        # already has these. Guarding is what makes a rerun safe on both.
        if name not in existing:
            table.create(bind=bind)

        op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS {name}_tenant_isolation ON {name}")
        op.execute(
            f"""
            CREATE POLICY {name}_tenant_isolation ON {name}
            USING (
              tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            )
            WITH CHECK (
              tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            )
            """
        )
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {name} TO zentra_runtime")


def downgrade() -> None:
    for name, _table in reversed(TABLES):
        op.execute(f"REVOKE ALL ON {name} FROM zentra_runtime")
        op.execute(f"DROP POLICY IF EXISTS {name}_tenant_isolation ON {name}")
        op.execute(f"DROP TABLE IF EXISTS {name}")
