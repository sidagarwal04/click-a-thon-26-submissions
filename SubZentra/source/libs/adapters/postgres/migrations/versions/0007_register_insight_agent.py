"""Register the Insight Agent, disabled and unevaluated.

Seeded exactly as the Phase 1 agents were in 0003, and for the same reason:
`ck_agent_registry_enabled_requires_passing_eval` forbids anything else. An
agent reaches a Tenant only after `nx run evals:promote` has actually run its
suite, so existing here is not the same as being allowed to run.
"""

from alembic import op

revision = "0007_register_insight_agent"
down_revision = "0006_draft_findings"
branch_labels = None
depends_on = None

AGENT_ID = "insight_v1"
ROLE = "insight"
EVAL_SUITE_REF = "evals/insight"


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO agent_registry
          (agent_id, role, version, enabled, eval_status, eval_suite_ref)
        VALUES
          ('{AGENT_ID}', '{ROLE}', '1', false, 'pending', '{EVAL_SUITE_REF}')
        ON CONFLICT (agent_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM agent_registry WHERE agent_id = '{AGENT_ID}'")
