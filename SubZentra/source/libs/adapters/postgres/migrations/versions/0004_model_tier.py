"""Add the per-tenant model tier that selects a provider chain."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0004_model_tier"
down_revision = "0003_phase1_agents"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {
        column["name"]
        for column in inspect(op.get_bind()).get_columns(table_name=table)
    }


def _constraints(table: str) -> set[str]:
    return {
        constraint["name"]
        for constraint in inspect(op.get_bind()).get_check_constraints(
            table_name=table
        )
    }


def upgrade() -> None:
    # 0001 builds the schema from `schema.py` via create_all, so on a fresh
    # database this column already exists and only an upgrade from an older
    # one needs to add it.
    if "model_tier" not in _columns("tenants"):
        op.add_column(
            "tenants",
            sa.Column(
                "model_tier",
                sa.String(16),
                nullable=False,
                # Defaults to free: a tenant reaches Anthropic-first routing,
                # and the no-training guarantee with it, only deliberately.
                server_default="free",
            ),
        )
    if "ck_tenants_model_tier" not in _constraints("tenants"):
        op.create_check_constraint(
            "ck_tenants_model_tier",
            "tenants",
            "model_tier IN ('free', 'premium')",
        )


def downgrade() -> None:
    op.execute("ALTER TABLE tenants DROP CONSTRAINT IF EXISTS ck_tenants_model_tier")
    if "model_tier" in _columns("tenants"):
        op.drop_column("tenants", "model_tier")
