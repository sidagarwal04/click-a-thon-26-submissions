"""Add structured Draft Findings and their ordered claims.

Purely additive. The Phase 1 narrative Finding stays inside
`investigations.state` and is neither moved nor rewritten, so every existing
Investigation reads back exactly as it did — it simply has no draft row. That
is what makes the API able to tell a legacy Investigation apart from one whose
claims are genuinely structured, rather than dressing the old shape up as the
new one.
"""

from alembic import op
from sqlalchemy import inspect

from zentra_adapter_postgres.schema import draft_finding_claims, draft_findings

revision = "0006_draft_findings"
down_revision = "0005_canonical_insight_role"
branch_labels = None
depends_on = None

TABLES = ("draft_findings", "draft_finding_claims")


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(inspect(bind).get_table_names())

    # 0001 builds the schema from `schema.py` via create_all, so a fresh
    # database already has these. Guarding the create is what makes a rerun
    # safe on both.
    if "draft_findings" not in existing:
        draft_findings.create(bind=bind)
    if "draft_finding_claims" not in existing:
        draft_finding_claims.create(bind=bind)

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


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"REVOKE ALL ON {table} FROM zentra_runtime")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
    op.execute("DROP TABLE IF EXISTS draft_finding_claims")
    op.execute("DROP TABLE IF EXISTS draft_findings")
