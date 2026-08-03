from __future__ import annotations

from sqlalchemy import (
    JSON,
    TIMESTAMP,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from zentra_domain_agent_execution import CANONICAL_ROLES

from ._metadata import metadata

# The Phase 2 tables live in their own module to keep this one under the
# repository's line limit. Re-exported here so every existing
# `from ...schema import draft_findings` keeps working — and so importing this
# module is what registers *every* table on the shared `MetaData`. Importing
# `._metadata` alone yields an empty one, and `create_all` would silently do
# nothing.
from .schema_connector import (
    catalog_agent_access,
    catalog_versions,
    data_sources,
    harvest_runs,
    relations,
)
from .schema_investigation_board import analytical_scopes as analytical_scopes
from .schema_investigation_board import board_conflicts as board_conflicts
from .schema_investigation_board import board_facts as board_facts
from .schema_investigation_board import board_gaps as board_gaps
from .schema_investigation_board import board_hypotheses as board_hypotheses
from .schema_investigation_board import investigation_boards as investigation_boards
from .schema_investigation_board import work_items as work_items
from .schema_phase_2 import (
    draft_finding_claim_citations,
    draft_finding_claims,
    draft_findings,
    erasure_operations,
    evidence_citations,
)
from .schema_sequence import prepared_tables as prepared_tables
from .schema_sequence import sequence_final_tables as sequence_final_tables
from .schema_sequence import sequence_runs as sequence_runs
from .schema_sequence import sequence_steps as sequence_steps
from .schema_sequence import sequences as sequences
from .schema_threads import investigation_threads as investigation_threads
from .schema_threads import thread_messages as thread_messages
from .schema_workspace import projects as projects
from .schema_workspace import workspace_groups as workspace_groups


def _role_check() -> str:
    """The canonical write vocabulary, as a CHECK body.

    Sorted so the emitted DDL is stable — an unordered frozenset would make
    every schema diff look like a change.
    """
    values = ", ".join(f"'{role.value}'" for role in sorted(CANONICAL_ROLES))
    return f"role IN ({values})"


tenants = Table(
    "tenants",
    metadata,
    Column(
        "tenant_id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column("name", Text, nullable=False),
    Column("data_residency_zone", Text, nullable=False, server_default="us-east"),
    Column("model_tier", String(16), nullable=False, server_default="free"),
    Column(
        "confidence_threshold", Numeric(4, 3), nullable=False, server_default="0.700"
    ),
    Column("cost_ceiling_usd", Numeric(12, 4), nullable=False, server_default="2.0000"),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    CheckConstraint(
        "confidence_threshold >= 0 AND confidence_threshold <= 1",
        name="ck_tenants_confidence_threshold",
    ),
    CheckConstraint("cost_ceiling_usd >= 0", name="ck_tenants_cost_ceiling"),
    CheckConstraint(
        "model_tier IN ('free', 'premium')",
        name="ck_tenants_model_tier",
    ),
)

users = Table(
    "users",
    metadata,
    Column(
        "user_id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column("email", Text, nullable=False),
    Column("display_name", Text),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

identity_subjects = Table(
    "identity_subjects",
    metadata,
    Column("provider", String(32), primary_key=True),
    Column("external_subject_id", Text, primary_key=True),
    Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    UniqueConstraint("provider", "user_id", name="uq_identity_subject_provider_user"),
)

tenant_identity_bindings = Table(
    "tenant_identity_bindings",
    metadata,
    Column("provider", String(32), primary_key=True),
    Column("external_tenant_id", Text, primary_key=True),
    Column(
        "tenant_id",
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    ),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
)

tenant_memberships = Table(
    "tenant_memberships",
    metadata,
    Column(
        "tenant_id",
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("role", String(16), nullable=False),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    CheckConstraint(
        "role IN ('owner', 'admin', 'member', 'viewer')",
        name="ck_tenant_memberships_role",
    ),
)

investigations = Table(
    "investigations",
    metadata,
    Column(
        "investigation_id",
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
    Column("question", Text, nullable=False),
    Column("status", String(32), nullable=False, server_default="pending"),
    Column("state", JSON, nullable=False, server_default=text("'{}'::jsonb")),
    Column("scenario_key", String(64)),
    Column("thread_id", UUID(as_uuid=True)),
    Column("thread_sequence", Integer),
    Column("initiating_message_id", UUID(as_uuid=True)),
    Column("parent_investigation_id", UUID(as_uuid=True)),
    Column("retry_of_investigation_id", UUID(as_uuid=True)),
    Column("version", Integer, nullable=False, server_default="1"),
    Column("evaluation_attempts", Integer, nullable=False, server_default="0"),
    Column("cost_so_far_usd", Numeric(12, 4), nullable=False, server_default="0"),
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
    Column("finished_at", TIMESTAMP(timezone=True)),
    CheckConstraint(
        "status IN ('pending', 'running', 'evaluating', 'awaiting_approval', "
        "'completed', 'rejected', 'failed', 'cancelled')",
        name="ck_investigations_status",
    ),
    CheckConstraint("cost_so_far_usd >= 0", name="ck_investigations_cost"),
    CheckConstraint("version >= 1", name="ck_investigations_version"),
    CheckConstraint(
        "evaluation_attempts >= 0 AND evaluation_attempts <= 3",
        name="ck_investigations_evaluation_attempts",
    ),
    CheckConstraint(
        "(thread_id IS NULL AND thread_sequence IS NULL AND "
        "initiating_message_id IS NULL) OR "
        "(thread_id IS NOT NULL AND thread_sequence >= 1 AND "
        "initiating_message_id IS NOT NULL)",
        name="ck_investigations_thread_link",
    ),
    ForeignKeyConstraint(
        ("thread_id", "tenant_id"),
        ("investigation_threads.thread_id", "investigation_threads.tenant_id"),
        name="fk_investigations_thread_tenant",
        ondelete="RESTRICT",
    ),
    ForeignKeyConstraint(
        ("initiating_message_id", "thread_id", "tenant_id"),
        (
            "thread_messages.message_id",
            "thread_messages.thread_id",
            "thread_messages.tenant_id",
        ),
        name="fk_investigations_initiating_message",
        ondelete="RESTRICT",
    ),
    ForeignKeyConstraint(
        ("parent_investigation_id", "tenant_id"),
        ("investigations.investigation_id", "investigations.tenant_id"),
        name="fk_investigations_parent_tenant",
        ondelete="RESTRICT",
    ),
    ForeignKeyConstraint(
        ("retry_of_investigation_id", "tenant_id"),
        ("investigations.investigation_id", "investigations.tenant_id"),
        name="fk_investigations_retry_tenant",
        ondelete="RESTRICT",
    ),
    UniqueConstraint(
        "thread_id", "thread_sequence", name="uq_investigations_thread_sequence"
    ),
    UniqueConstraint(
        "investigation_id",
        "tenant_id",
        name="uq_investigations_tenant_identity",
    ),
)
Index(
    "ix_investigations_tenant_created",
    investigations.c.tenant_id,
    investigations.c.created_at,
)

agent_executions = Table(
    "agent_executions",
    metadata,
    Column(
        "execution_id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column(
        "investigation_id",
        UUID(as_uuid=True),
        ForeignKey("investigations.investigation_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "tenant_id",
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("agent_id", Text, nullable=False),
    Column("role", String(64)),
    Column("step", Integer, nullable=False),
    Column("input", JSON, nullable=False),
    Column("output", JSON),
    Column("outcome_kind", String(16)),
    Column("confidence", Numeric(4, 3)),
    Column("outcome", JSON),
    Column("status", String(16), nullable=False),
    Column("latency_ms", Integer),
    Column("cost_usd", Numeric(12, 6)),
    Column("model", Text),
    Column("provider", String(64)),
    Column("input_tokens", Integer, nullable=False, server_default="0"),
    Column("output_tokens", Integer, nullable=False, server_default="0"),
    Column("fallbacks", JSON, nullable=False, server_default="[]"),
    # Which tools the Agent ran, in order: name, latency, ok. Never arguments
    # or results — those carry rows, and this table is read by Replay.
    Column("tool_calls", JSON, nullable=False, server_default="[]"),
    Column(
        "started_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column("completed_at", TIMESTAMP(timezone=True)),
    CheckConstraint("step >= 0", name="ck_agent_executions_step"),
    CheckConstraint(
        "status IN ('success', 'failure', 'partial', 'escalated')",
        name="ck_agent_executions_status",
    ),
    CheckConstraint(
        "outcome_kind IS NULL OR outcome_kind IN ('confidence', 'validation')",
        name="ck_agent_executions_outcome_kind",
    ),
    CheckConstraint(
        "(outcome_kind = 'confidence' AND confidence BETWEEN 0 AND 1) "
        "OR (outcome_kind = 'validation' AND confidence IS NULL) "
        "OR (outcome_kind IS NULL AND confidence IS NULL)",
        name="ck_agent_executions_typed_outcome",
    ),
    CheckConstraint(
        "latency_ms IS NULL OR latency_ms >= 0", name="ck_agent_executions_latency"
    ),
    CheckConstraint(
        "cost_usd IS NULL OR cost_usd >= 0", name="ck_agent_executions_cost"
    ),
    CheckConstraint(
        "input_tokens >= 0 AND output_tokens >= 0",
        name="ck_agent_executions_tokens",
    ),
)
Index(
    "ix_agent_executions_tenant_investigation_step",
    agent_executions.c.tenant_id,
    agent_executions.c.investigation_id,
    agent_executions.c.step,
)

# Phase 2. Additive: the Phase 1 narrative Finding stays where it is, inside
# `investigations.state`, and is neither moved nor rewritten. A structured draft
# is a separate row an Investigation may or may not have, so an Investigation
# that ran before Insight existed reads back exactly as it did.
human_approvals = Table(
    "human_approvals",
    metadata,
    Column(
        "approval_id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column(
        "investigation_id",
        UUID(as_uuid=True),
        ForeignKey("investigations.investigation_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "tenant_id",
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("reason", String(64), nullable=False),
    Column("status", String(16), nullable=False, server_default="pending"),
    Column(
        "requested_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column("decided_at", TIMESTAMP(timezone=True)),
    Column("decided_by", UUID(as_uuid=True), ForeignKey("users.user_id")),
    Column("decision_reason", String(32)),
    # Every publication condition that failed. `reason` is the headline;
    # this is the whole picture a reviewer needs.
    Column("failed_conditions", JSON, nullable=False, server_default="[]"),
    CheckConstraint(
        "reason IN ('low_confidence', 'irreversible_action', "
        "'contradiction_unresolved', 'regulatory_exposure', 'tenant_policy', "
        "'evidence_incomplete')",
        name="ck_human_approvals_reason",
    ),
    CheckConstraint(
        "status IN ('pending', 'granted', 'rejected', 'timed_out')",
        name="ck_human_approvals_status",
    ),
    CheckConstraint(
        "decision_reason IS NULL OR decision_reason IN "
        "('insufficient_evidence', 'incorrect_interpretation', "
        "'policy_mismatch', 'needs_more_analysis')",
        name="ck_human_approvals_decision_reason",
    ),
)
Index(
    "ix_human_approvals_tenant_status",
    human_approvals.c.tenant_id,
    human_approvals.c.status,
)
Index(
    "uq_human_approvals_one_pending",
    human_approvals.c.tenant_id,
    human_approvals.c.investigation_id,
    unique=True,
    postgresql_where=human_approvals.c.status == "pending",
)

audit_outbox = Table(
    "audit_outbox",
    metadata,
    Column("event_id", UUID(as_uuid=True), primary_key=True),
    Column(
        "tenant_id",
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "investigation_id",
        UUID(as_uuid=True),
        ForeignKey("investigations.investigation_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("payload", JSON, nullable=False),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column("dispatched_at", TIMESTAMP(timezone=True)),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("last_error_code", String(64)),
    CheckConstraint("attempts >= 0", name="ck_audit_outbox_attempts"),
)
# The ordering floor reads the latest `created_at` for one Investigation on
# every enqueue. Without this it is a sequential scan over all history, in
# the request path.
Index(
    "ix_audit_outbox_investigation_created",
    audit_outbox.c.investigation_id,
    audit_outbox.c.created_at,
)
Index(
    "ix_audit_outbox_tenant_pending",
    audit_outbox.c.tenant_id,
    audit_outbox.c.dispatched_at,
    audit_outbox.c.created_at,
)

semantic_metrics = Table(
    "semantic_metrics",
    metadata,
    Column(
        "metric_id",
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
    Column("name", Text, nullable=False),
    Column("sql_definition", Text, nullable=False),
    Column("grain", Text, nullable=False),
    Column("description", Text),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    UniqueConstraint("tenant_id", "name", name="uq_semantic_metrics_tenant_name"),
)

agent_registry = Table(
    "agent_registry",
    metadata,
    Column("agent_id", Text, primary_key=True),
    Column("role", String(64), nullable=False),
    Column("version", Text, nullable=False),
    Column("enabled", Boolean, nullable=False, server_default=text("false")),
    Column("eval_status", String(16), nullable=False, server_default="pending"),
    Column("eval_suite_ref", Text, nullable=False),
    Column("display_name", Text),
    Column("description", Text),
    Column("capabilities", JSON, nullable=False, server_default="[]"),
    # Derived from the enum rather than restated, because a hand-kept copy of
    # this list is exactly the kind of drift nothing would catch. Legacy roles
    # are excluded: this is the canonical *write* vocabulary, and `0005`
    # re-adds the constraint NOT VALID so a database already holding a legacy
    # row keeps it readable while refusing to accept another one.
    CheckConstraint(_role_check(), name="ck_agent_registry_role"),
    CheckConstraint(
        "eval_status IN ('pending', 'passing', 'failing')",
        name="ck_agent_registry_eval_status",
    ),
    CheckConstraint(
        "enabled = false OR eval_status = 'passing'",
        name="ck_agent_registry_enabled_requires_passing_eval",
    ),
)

# Imported after `investigations` is registered because the job table carries
# a composite Tenant-safe foreign key to it.
from .schema_chat import (  # noqa: E402
    thread_events as thread_events,
)
from .schema_chat import (  # noqa: E402
    visualization_actions as visualization_actions,
)
from .schema_chat import (  # noqa: E402
    visualization_artifacts as visualization_artifacts,
)
from .schema_chat import (  # noqa: E402
    visualization_briefs as visualization_briefs,
)
from .schema_jobs import execution_jobs as execution_jobs  # noqa: E402

__all__ = [
    "agent_executions",
    "agent_registry",
    "audit_outbox",
    "catalog_agent_access",
    "catalog_versions",
    "data_sources",
    "draft_finding_claim_citations",
    "draft_finding_claims",
    "draft_findings",
    "erasure_operations",
    "evidence_citations",
    "execution_jobs",
    "harvest_runs",
    "human_approvals",
    "identity_subjects",
    "investigations",
    "metadata",
    "prepared_tables",
    "projects",
    "relations",
    "semantic_metrics",
    "sequence_final_tables",
    "sequence_runs",
    "sequence_steps",
    "sequences",
    "tenant_identity_bindings",
    "tenant_memberships",
    "tenants",
    "thread_events",
    "users",
    "visualization_actions",
    "visualization_artifacts",
    "visualization_briefs",
    "workspace_groups",
]
