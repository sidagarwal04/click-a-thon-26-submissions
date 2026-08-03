"""Investigation Board and Work Item: the Investigation Engine's durable
working memory and work queue (ADR-0026), plus the Analytical Scope an
Intake Agent resolves a question against (ADR-0027).

`role`'s CHECK is generated from the current `CANONICAL_ROLES`, the same
pattern `agent_registry.role` uses (`schema.py`) — correct for this table's
initial shape. A future role addition needs its own migration widening this
CHECK explicitly (mirroring `0005_canonical_insight_role.py`), not a rewrite
of this one.

One Analytical Scope per Tenant is the Phase 1 shape: a Tenant either
narrows its catalog or does not. Per-thread or per-cube-family scopes are a
Phase 5+ concern and would need a different key, not a change to this one.
"""

from sqlalchemy import (
    JSON,
    TIMESTAMP,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from zentra_domain_agent_execution import CANONICAL_ROLES

from ._metadata import metadata


def _role_check() -> str:
    values = ", ".join(f"'{role.value}'" for role in sorted(CANONICAL_ROLES))
    return f"role IN ({values})"


investigation_boards = Table(
    "investigation_boards",
    metadata,
    Column(
        "board_id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column(
        "tenant_id",
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("investigation_id", UUID(as_uuid=True), nullable=False),
    Column("narrative", Text),
    Column("confidence_score", Numeric(5, 4)),
    Column("confidence_threshold", Numeric(5, 4)),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    ForeignKeyConstraint(
        ("investigation_id", "tenant_id"),
        ("investigations.investigation_id", "investigations.tenant_id"),
        name="fk_investigation_boards_investigation_tenant",
        ondelete="CASCADE",
    ),
    UniqueConstraint(
        "investigation_id", "tenant_id", name="uq_investigation_boards_one_per_run"
    ),
    UniqueConstraint(
        "board_id", "tenant_id", name="uq_investigation_boards_tenant_identity"
    ),
)


board_facts = Table(
    "board_facts",
    metadata,
    Column(
        "fact_id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column("board_id", UUID(as_uuid=True), nullable=False),
    Column(
        "tenant_id",
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("metric", Text, nullable=False),
    Column("value", Text, nullable=False),
    Column("period", Text),
    Column("producing_work_item_id", UUID(as_uuid=True), nullable=False),
    Column(
        "evidence_refs", JSON, nullable=False, server_default=text("'[]'::jsonb")
    ),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    ForeignKeyConstraint(
        ("board_id", "tenant_id"),
        ("investigation_boards.board_id", "investigation_boards.tenant_id"),
        name="fk_board_facts_board_tenant",
        ondelete="CASCADE",
    ),
)


board_hypotheses = Table(
    "board_hypotheses",
    metadata,
    Column(
        "hypothesis_id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column("board_id", UUID(as_uuid=True), nullable=False),
    Column(
        "tenant_id",
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("statement", Text, nullable=False),
    Column("status", Text, nullable=False, server_default="open"),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    ForeignKeyConstraint(
        ("board_id", "tenant_id"),
        ("investigation_boards.board_id", "investigation_boards.tenant_id"),
        name="fk_board_hypotheses_board_tenant",
        ondelete="CASCADE",
    ),
    CheckConstraint(
        "status IN ('open', 'supported', 'rejected')",
        name="ck_board_hypotheses_status",
    ),
)


board_gaps = Table(
    "board_gaps",
    metadata,
    Column(
        "gap_id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column("board_id", UUID(as_uuid=True), nullable=False),
    Column(
        "tenant_id",
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("description", Text, nullable=False),
    Column("priority", Text, nullable=False),
    Column("resolved", Boolean, nullable=False, server_default=text("false")),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    ForeignKeyConstraint(
        ("board_id", "tenant_id"),
        ("investigation_boards.board_id", "investigation_boards.tenant_id"),
        name="fk_board_gaps_board_tenant",
        ondelete="CASCADE",
    ),
    CheckConstraint(
        "priority IN ('low', 'medium', 'high')", name="ck_board_gaps_priority"
    ),
)


board_conflicts = Table(
    "board_conflicts",
    metadata,
    Column(
        "conflict_id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column("board_id", UUID(as_uuid=True), nullable=False),
    Column(
        "tenant_id",
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("description", Text, nullable=False),
    Column("status", Text, nullable=False, server_default="open"),
    Column("resolution", Text),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    ForeignKeyConstraint(
        ("board_id", "tenant_id"),
        ("investigation_boards.board_id", "investigation_boards.tenant_id"),
        name="fk_board_conflicts_board_tenant",
        ondelete="CASCADE",
    ),
    CheckConstraint(
        "status IN ('open', 'resolved', 'documented')",
        name="ck_board_conflicts_status",
    ),
)


work_items = Table(
    "work_items",
    metadata,
    Column(
        "work_item_id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column(
        "tenant_id",
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("investigation_id", UUID(as_uuid=True), nullable=False),
    Column("role", Text, nullable=False),
    Column("objective", Text, nullable=False),
    Column("status", Text, nullable=False, server_default="pending"),
    Column("parent_work_item_id", UUID(as_uuid=True)),
    Column("depends_on", JSON, nullable=False, server_default=text("'[]'::jsonb")),
    Column(
        "artifact_refs", JSON, nullable=False, server_default=text("'[]'::jsonb")
    ),
    Column("rejection_reason", Text),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    ForeignKeyConstraint(
        ("investigation_id", "tenant_id"),
        ("investigations.investigation_id", "investigations.tenant_id"),
        name="fk_work_items_investigation_tenant",
        ondelete="CASCADE",
    ),
    ForeignKeyConstraint(
        ("parent_work_item_id", "tenant_id"),
        ("work_items.work_item_id", "work_items.tenant_id"),
        name="fk_work_items_parent_tenant",
    ),
    UniqueConstraint("work_item_id", "tenant_id", name="uq_work_items_tenant_identity"),
    CheckConstraint(_role_check(), name="ck_work_items_role"),
    CheckConstraint(
        "status IN ('pending', 'running', 'waiting', 'blocked', 'completed', "
        "'rejected')",
        name="ck_work_items_status",
    ),
)


analytical_scopes = Table(
    "analytical_scopes",
    metadata,
    Column(
        "tenant_id",
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("cubes", JSON, nullable=False, server_default=text("'[]'::jsonb")),
    Column(
        "member_overrides", JSON, nullable=False, server_default=text("'[]'::jsonb")
    ),
    Column(
        "updated_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)
