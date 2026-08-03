"""Merge the two parallel migration heads before this branch's own head.

`0019_agent_execution_tool_calls` (agent tool-call telemetry) and
`0021_intake_role` (this branch's Investigation Engine: Board, Work Items,
Analytical Scope, the Intake role) both descend from `0018_merge_heads` but
never converged, leaving two heads. `upgrade head` is ambiguous against two
heads. This is a pure Alembic merge point: no schema change, just one
lineage going forward — same pattern as `0018_merge_heads.py`.
"""

revision = "0022_merge_heads"
down_revision = ("0019_agent_execution_tool_calls", "0021_intake_role")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
