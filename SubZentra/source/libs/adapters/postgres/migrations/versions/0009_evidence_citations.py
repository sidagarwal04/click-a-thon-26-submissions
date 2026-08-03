"""Evidence Citations, and the ordered link from a claim to what it rests on.

The claim's own `citation_ids` JSON column stays as it was — it predates this
and is not the reachable path. The join table is, because a citation is a row
another Tenant must not be able to reach, and RLS operates on rows.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from zentra_adapter_postgres.schema import (
    draft_finding_claim_citations,
    evidence_citations,
)

revision = "0009_evidence_citations"
down_revision = "0008_claim_measurement"
branch_labels = None
depends_on = None

TABLES = ("evidence_citations", "draft_finding_claim_citations")


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(inspect(bind).get_table_names())

    # 0001 builds from `schema.py` via create_all, so a fresh database already
    # has these. Guarding the create is what makes a rerun safe on both.
    if "evidence_citations" not in existing:
        evidence_citations.create(bind=bind)
    if "draft_finding_claim_citations" not in existing:
        draft_finding_claim_citations.create(bind=bind)

    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING (
              tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            )
            WITH CHECK (
              tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
            )
            """
        )
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO zentra_runtime"
        )


    # `draft_finding_claims.citation_ids` was a JSON copy of a relationship the
    # join table now owns. Two sources of truth that can drift, and only one of
    # them is a row RLS can protect. It was added by 0006 in this same Phase 2
    # work and never read.
    if "citation_ids" in {
        column["name"]
        for column in inspect(bind).get_columns("draft_finding_claims")
    }:
        op.drop_column("draft_finding_claims", "citation_ids")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"REVOKE ALL ON {table} FROM zentra_runtime")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
    op.add_column(
        "draft_finding_claims",
        sa.Column("citation_ids", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.execute("DROP TABLE IF EXISTS draft_finding_claim_citations")
    op.execute("DROP TABLE IF EXISTS evidence_citations")
