"""Accept the canonical Cube Analyst role and stop accepting the legacy one.

The expand step of ADR-0025's expand-contract rename, and a direct copy of
`0005`'s shape for the same reason: `sql_analyst` named a capability the tree
deliberately does not contain — the Agent writes a governed semantic query and
Cube compiles it, and there is no raw-SQL port anywhere for it to have been
granted.

The registry row is renamed in place because it describes which Agent is
enabled *now*. `agent_executions` is deliberately left alone: those rows record
that an Agent called `sql_analyst_v1` really did run, and rewriting history to
match today's vocabulary would be a lie in an audit trail. The constraint is
re-added NOT VALID so those rows stay readable in Replay.
"""

from alembic import op

revision = "0018_cube_analyst_role"
down_revision = "0017_chat_work_feed_visualization"
branch_labels = None
depends_on = None

CANONICAL_ROLES = (
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

#: Readable, never writable. `insight_root_cause` from ADR-0011, `sql_analyst`
#: from this one.
LEGACY_ROLES = ("insight_root_cause", "sql_analyst")


def _role_check(roles: tuple[str, ...]) -> str:
    values = ", ".join(f"'{role}'" for role in roles)
    return f"role IN ({values})"


def upgrade() -> None:
    # Widen first, so the rename cannot collide with the constraint still in
    # force from 0005 — that one lists `sql_analyst` and not `cube_analyst`.
    op.execute(
        "ALTER TABLE agent_registry DROP CONSTRAINT IF EXISTS ck_agent_registry_role"
    )
    op.execute(
        """
        UPDATE agent_registry
        SET role = 'cube_analyst',
            agent_id = 'cube_analyst_v1',
            eval_suite_ref = 'evals/cube_analyst'
        WHERE role = 'sql_analyst'
        """
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
        """
        UPDATE agent_registry
        SET role = 'sql_analyst',
            agent_id = 'sql_analyst_v1',
            eval_suite_ref = 'evals/sql_analyst'
        WHERE role = 'cube_analyst'
        """
    )
    op.execute(
        "ALTER TABLE agent_registry ADD CONSTRAINT ck_agent_registry_role "
        f"CHECK ({_role_check(CANONICAL_ROLES + LEGACY_ROLES)}) NOT VALID"
    )
