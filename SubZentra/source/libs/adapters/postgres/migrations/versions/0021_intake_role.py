"""Accept the new `intake` canonical role (ADR-0027).

Mirrors `0005_canonical_insight_role.py`'s expand step: role vocabularies are
enforced by a `CHECK` derived from `CANONICAL_ROLES` at the time each table
was created, so a new role needs its own migration widening that `CHECK`
rather than a rewrite of the migration that first installed it.

`_PRIOR_ROLES` names `cube_analyst`, not `sql_analyst`: this migration and
`0018_cube_analyst_role.py` are independent expand steps on parallel branches
that both narrow this same `CHECK`, merged by `0022_merge_heads.py` with no
guaranteed order between them. Whichever runs second must not exclude a role
the other already added, so both list the role under its current name.
"""

from alembic import op

revision = "0021_intake_role"
down_revision = "0020_investigation_board_and_work_items"
branch_labels = None
depends_on = None

_PRIOR_ROLES = (
    "orchestrator",
    "data_intake",
    "data_quality",
    "data_preparation",
    "semantic_modeling",
    "cube_analyst",
    "evaluator",
    "statistician",
    "insight",
    "demand_planner",
    "forecaster",
    "visualization",
    "executive_report_writer",
    "knowledge",
)
_LEGACY_ROLES = ("insight_root_cause",)
_ROLES_WITH_INTAKE = _PRIOR_ROLES + ("intake",)


def _role_check(roles: tuple[str, ...]) -> str:
    values = ", ".join(f"'{role}'" for role in roles)
    return f"role IN ({values})"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE agent_registry DROP CONSTRAINT IF EXISTS ck_agent_registry_role"
    )
    op.execute(
        "ALTER TABLE agent_registry ADD CONSTRAINT ck_agent_registry_role "
        f"CHECK ({_role_check(_ROLES_WITH_INTAKE)}) NOT VALID"
    )
    op.execute("ALTER TABLE work_items DROP CONSTRAINT IF EXISTS ck_work_items_role")
    op.execute(
        "ALTER TABLE work_items ADD CONSTRAINT ck_work_items_role "
        f"CHECK ({_role_check(_ROLES_WITH_INTAKE)}) NOT VALID"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE agent_registry DROP CONSTRAINT IF EXISTS ck_agent_registry_role"
    )
    op.execute(
        "ALTER TABLE agent_registry ADD CONSTRAINT ck_agent_registry_role "
        f"CHECK ({_role_check(_PRIOR_ROLES + _LEGACY_ROLES)}) NOT VALID"
    )
    op.execute("ALTER TABLE work_items DROP CONSTRAINT IF EXISTS ck_work_items_role")
    op.execute(
        "ALTER TABLE work_items ADD CONSTRAINT ck_work_items_role "
        f"CHECK ({_role_check(_PRIOR_ROLES)}) NOT VALID"
    )
