"""Index the outbox by Investigation.

Each enqueue reads the latest `created_at` for one Investigation to keep its
timeline strictly increasing. Without this index that is a sequential scan over
every event ever written, on the request path.
"""

from alembic import op
from sqlalchemy import inspect

revision = "0013_outbox_investigation_index"
down_revision = "0012_erasure_operations"
branch_labels = None
depends_on = None

INDEX = "ix_audit_outbox_investigation_created"


def upgrade() -> None:
    existing = {
        index["name"] for index in inspect(op.get_bind()).get_indexes("audit_outbox")
    }
    if INDEX not in existing:
        op.create_index(INDEX, "audit_outbox", ["investigation_id", "created_at"])


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX}")
