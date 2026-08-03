"""Merge the two parallel migration heads before Sequence's tables are added.

0016_catalog_agent_access and 0017_chat_work_feed_visualization landed on
parallel branches and were never merged, leaving two heads. `upgrade head`
is ambiguous against two heads, which was already breaking every existing
migration test that upgrades to "head" rather than a named revision. This is
a pure Alembic merge point: no schema change, just one lineage going forward.
"""

revision = "0018_merge_heads"
down_revision = ("0016_catalog_agent_access", "0017_chat_work_feed_visualization")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
