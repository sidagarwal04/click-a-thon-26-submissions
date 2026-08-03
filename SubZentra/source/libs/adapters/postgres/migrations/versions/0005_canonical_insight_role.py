"""Accept the canonical Insight role and stop accepting the legacy one.

The expand step of ADR 0011's expand-contract rename. `insight_root_cause`
promised causality the evidence cannot establish, so it stops being writable
here. It stays *readable*: the replacement constraint is added NOT VALID, which
enforces every new row without re-checking the ones already stored, so a
database seeded before the rename keeps rendering those investigations in
Replay instead of losing them.
"""

from alembic import op

revision = "0005_canonical_insight_role"
down_revision = "0004_model_tier"
branch_labels = None
depends_on = None

CANONICAL_ROLES = (
    "orchestrator",
    "data_intake",
    "data_quality",
    "data_preparation",
    "semantic_modeling",
    "sql_analyst",
    "evaluator",
    "statistician",
    "insight",
    "demand_planner",
    "forecaster",
    "visualization",
    "executive_report_writer",
    "knowledge",
)

LEGACY_ROLES = ("insight_root_cause",)


def _role_check(roles: tuple[str, ...]) -> str:
    values = ", ".join(f"'{role}'" for role in roles)
    return f"role IN ({values})"


def upgrade() -> None:
    # Unconditional drop-and-replace rather than an inspect() guard: 0001
    # builds the schema from `schema.py` via create_all, so a fresh database
    # already carries the canonical list and an older one carries the legacy
    # list, and `DROP ... IF EXISTS` followed by a re-add reaches the same
    # place from either. The only difference on a fresh database is that the
    # constraint ends up NOT VALID, which changes nothing about what it will
    # accept from here on.
    op.execute(
        "ALTER TABLE agent_registry DROP CONSTRAINT IF EXISTS ck_agent_registry_role"
    )
    op.execute(
        "ALTER TABLE agent_registry ADD CONSTRAINT ck_agent_registry_role "
        f"CHECK ({_role_check(CANONICAL_ROLES)}) NOT VALID"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE agent_registry DROP CONSTRAINT IF EXISTS ck_agent_registry_role"
    )
    op.execute(
        "ALTER TABLE agent_registry ADD CONSTRAINT ck_agent_registry_role "
        f"CHECK ({_role_check(CANONICAL_ROLES + LEGACY_ROLES)}) NOT VALID"
    )
