"""Phase 2 tables: structured Draft Findings and their Evidence Citations.

Split from `schema.py` to keep both files under the repository's 600-line
limit. Registered against the same `MetaData`, and foreign keys reference the
Phase 0/1 tables by name, so neither module imports the other.
"""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    TIMESTAMP,
    CheckConstraint,
    Column,
    ForeignKey,
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

from ._metadata import metadata

draft_findings = Table(
    "draft_findings",
    metadata,
    Column(
        "draft_finding_id",
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
    Column("version", Integer, nullable=False, server_default="1"),
    # The Insight Agent Execution that produced it. Nullable through the
    # migration window only — Insight does not run yet.
    Column(
        "produced_by_execution_id",
        UUID(as_uuid=True),
        ForeignKey("agent_executions.execution_id", ondelete="SET NULL"),
    ),
    Column("headline", Text, nullable=False),
    Column("summary", Text, nullable=False),
    Column("contradictions", JSON, nullable=False, server_default="[]"),
    Column("root_cause", String(32), nullable=False),
    Column("confidence", Numeric(4, 3)),
    Column("confidence_method", Text),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    # ADR 0011 admits no Root Cause Claim until a causal-evidence standard is
    # accepted, so the database refuses any other value rather than trusting
    # every future writer to remember.
    CheckConstraint(
        "root_cause IN ('unresolved')",
        name="ck_draft_findings_root_cause",
    ),
    CheckConstraint(
        "confidence IS NULL OR confidence BETWEEN 0 AND 1",
        name="ck_draft_findings_confidence",
    ),
    # A score with no calibration method is an unexplained number, which is
    # exactly what bounded confidence exists to stop.
    CheckConstraint(
        "(confidence IS NULL) = (confidence_method IS NULL)",
        name="ck_draft_findings_confidence_is_explained",
    ),
    CheckConstraint("version >= 1", name="ck_draft_findings_version"),
    UniqueConstraint(
        "investigation_id",
        "version",
        name="uq_draft_findings_investigation_version",
    ),
)
Index(
    "ix_draft_findings_tenant_investigation",
    draft_findings.c.tenant_id,
    draft_findings.c.investigation_id,
    draft_findings.c.version,
)

draft_finding_claims = Table(
    "draft_finding_claims",
    metadata,
    Column(
        "claim_id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column(
        "draft_finding_id",
        UUID(as_uuid=True),
        ForeignKey("draft_findings.draft_finding_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "tenant_id",
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("kind", String(16), nullable=False),
    Column("claim_text", Text, nullable=False),
    # The measurement an observed claim rests on, carried rather than
    # re-derived. Null for an interpretation, which has none of its own.
    #
    # `claim_value` rather than `value` for the same reason as `claim_text`:
    # both are SQL-adjacent words that read ambiguously in a query against a
    # table full of other values.
    Column("metric", Text),
    Column("claim_value", Text),
    Column("period", Text),
    Column("position", Integer, nullable=False),
    CheckConstraint(
        "kind IN ('observed', 'interpretation')",
        name="ck_draft_finding_claims_kind",
    ),
    CheckConstraint("position >= 0", name="ck_draft_finding_claims_position"),
    # An observed claim with no measurement is an interpretation wearing the
    # wrong label. The domain refuses it; so does the database.
    CheckConstraint(
        "kind <> 'observed' OR (metric IS NOT NULL AND claim_value IS NOT NULL)",
        name="ck_draft_finding_claims_observed_is_measured",
    ),
    # Order is the contract, not an accident of insertion.
    UniqueConstraint(
        "draft_finding_id",
        "position",
        name="uq_draft_finding_claims_position",
    ),
)
Index(
    "ix_draft_finding_claims_draft_position",
    draft_finding_claims.c.draft_finding_id,
    draft_finding_claims.c.position,
)

evidence_citations = Table(
    "evidence_citations",
    metadata,
    Column(
        "citation_id",
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
    Column("metric", Text, nullable=False),
    Column("filters", JSON, nullable=False, server_default="[]"),
    Column("period", Text),
    Column("grain", Text),
    Column(
        "producing_execution_id",
        UUID(as_uuid=True),
        ForeignKey("agent_executions.execution_id", ondelete="SET NULL"),
    ),
    Column("aggregate_value", Text, nullable=False),
    Column("evaluator_outcome", JSON),
    Column("state", String(16), nullable=False, server_default="active"),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    # `unavailable` is a fault and `tombstoned` a Tenant's deliberate erasure.
    # Collapsing them would either alarm a reader about a deletion they asked
    # for or quietly reassure them about data loss.
    CheckConstraint(
        "state IN ('active', 'unavailable', 'tombstoned')",
        name="ck_evidence_citations_state",
    ),
    # One measurement per metric-and-period, so two claims about the same
    # figure share it rather than holding copies that can drift.
    UniqueConstraint(
        "investigation_id",
        "metric",
        "period",
        name="uq_evidence_citations_measurement",
    ),
)
Index(
    "ix_evidence_citations_tenant_investigation",
    evidence_citations.c.tenant_id,
    evidence_citations.c.investigation_id,
)

# Many-to-many on purpose: a claim can rest on several measurements, and one
# measurement can support several claims. `position` is the claim's ordering of
# its own evidence, which is part of what the claim says.
draft_finding_claim_citations = Table(
    "draft_finding_claim_citations",
    metadata,
    Column(
        "claim_id",
        UUID(as_uuid=True),
        ForeignKey("draft_finding_claims.claim_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "citation_id",
        UUID(as_uuid=True),
        ForeignKey("evidence_citations.citation_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tenant_id",
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("position", Integer, nullable=False),
    CheckConstraint(
        "position >= 0", name="ck_draft_finding_claim_citations_position"
    ),
    UniqueConstraint(
        "claim_id",
        "position",
        name="uq_draft_finding_claim_citations_position",
    ),
)


# One row per erasure request. Idempotent by construction: the unique
# constraint means asking twice reaches the same row rather than starting a
# second erasure that could race the first.
erasure_operations = Table(
    "erasure_operations",
    metadata,
    Column(
        "erasure_id",
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
    Column("category", String(32), nullable=False),
    Column("progress", String(16), nullable=False, server_default="requested"),
    Column(
        "requested_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column("completed_at", TIMESTAMP(timezone=True)),
    Column("attempts", Integer, nullable=False, server_default="0"),
    # A category, never a message. A failed erasure must not become the place
    # the erased value is quoted back.
    Column("failure_code", Text),
    CheckConstraint(
        "category IN ('tenant_request')",
        name="ck_erasure_operations_category",
    ),
    CheckConstraint(
        "progress IN ('requested', 'erasing', 'completed', 'failed')",
        name="ck_erasure_operations_progress",
    ),
    # The database refuses the one answer this must never give: a completion
    # time on something that did not complete, or a completion without one.
    CheckConstraint(
        "(progress = 'completed') = (completed_at IS NOT NULL)",
        name="ck_erasure_operations_completion_is_recorded",
    ),
    CheckConstraint(
        "progress <> 'failed' OR failure_code IS NOT NULL",
        name="ck_erasure_operations_failure_is_explained",
    ),
    CheckConstraint("attempts >= 0", name="ck_erasure_operations_attempts"),
    UniqueConstraint(
        "investigation_id",
        "category",
        name="uq_erasure_operations_request",
    ),
)
