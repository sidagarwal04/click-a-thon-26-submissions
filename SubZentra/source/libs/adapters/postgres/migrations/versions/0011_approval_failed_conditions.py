"""Persist every publication condition a Human Approval was opened for.

`reason` is the headline. The complete list used to be derivable only from the
Investigation's in-memory events, which `_investigation_from_row` rehydrates
empty — so it was correct exactly once, in the request that wrote it, and empty
on every read afterwards. It belongs on the approval, which a read actually
loads.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0011_approval_failed_conditions"
down_revision = "0010_evidence_incomplete_reason"
branch_labels = None
depends_on = None


def _columns() -> set[str]:
    return {
        column["name"]
        for column in inspect(op.get_bind()).get_columns("human_approvals")
    }


def upgrade() -> None:
    # 0001 builds from `schema.py` via create_all, so a fresh database already
    # has it and only an upgrade needs the add.
    if "failed_conditions" not in _columns():
        op.add_column(
            "human_approvals",
            sa.Column(
                "failed_conditions",
                sa.JSON(),
                nullable=False,
                server_default="[]",
            ),
        )


def downgrade() -> None:
    if "failed_conditions" in _columns():
        op.drop_column("human_approvals", "failed_conditions")
