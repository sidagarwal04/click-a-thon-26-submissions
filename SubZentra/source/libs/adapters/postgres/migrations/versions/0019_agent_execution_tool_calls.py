"""Record which tools an Agent Execution ran.

Agents made a fixed sequence of model calls before ADR-0024; there was nothing
to record because there was nothing to choose. An Agent that searches the
catalog four times and queries twice is now indistinguishable in Replay from
one that answered in a single shot, and "what did it actually do" is the first
question anyone asks of a run that went wrong.

Names, latencies and outcomes only. Arguments and results carry rows, and this
table is read by Replay — ADR-0006 keeps the ledger metadata-only.
"""

from alembic import op
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

revision = "0019_agent_execution_tool_calls"
down_revision = "0018_cube_analyst_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_executions",
        # Defaulted rather than nullable: every execution before this ran no
        # tools, and an empty list says that exactly. NULL would say "unknown",
        # which is a different and less true claim.
        Column("tool_calls", JSONB, nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("agent_executions", "tool_calls")
