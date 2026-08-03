"""Connector tables.

Their own module for the same reason as `schema_phase_2`: to keep `schema.py`
under the repository's line limit. Registered on the shared `MetaData`, so
importing `schema` is what brings them into `create_all`.
"""

from __future__ import annotations

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ._metadata import metadata

#: A Data Source, and the sealed credential that reaches it.
#:
#: `sealed_credentials` is `bytea` holding AES-GCM ciphertext, never a
#: password. It is nullable because an uploaded source has no credential to
#: seal — it is backed by a ZentraOS-owned table rather than someone else's
#: warehouse.
data_sources = Table(
    "data_sources",
    metadata,
    Column("data_source_id", UUID(as_uuid=True), primary_key=True),
    Column(
        "tenant_id",
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("name", Text, nullable=False),
    Column("kind", String(16), nullable=False),
    Column("sealed_credentials", LargeBinary, nullable=True),
    Column("description", Text, nullable=True),
    Column("health", String(16), nullable=False),
    Column(
        "store_sample_values",
        Boolean,
        nullable=False,
        server_default=text("false"),
    ),
    Column("last_verified_at", TIMESTAMP(timezone=True), nullable=True),
    Column("last_harvested_at", TIMESTAMP(timezone=True), nullable=True),
    Column(
        "created_at",
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    ),
    Column("landed_table", Text, nullable=True),
    #: Host and database only. What `connection_hint` is derived from, and the
    #: reason a read never has to open the sealed credential to describe the
    #: source.
    Column(
        "source_metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    ),
    CheckConstraint(
        "kind IN ('connected', 'uploaded')",
        name="ck_data_sources_kind",
    ),
    CheckConstraint(
        "health IN ('unverified', 'reachable', 'unreachable')",
        name="ck_data_sources_health",
    ),
    # A tenant's own source names are theirs to keep distinct; two tenants may
    # both call one "Production".
    Index(
        "uq_data_sources_tenant_name",
        "tenant_id",
        "name",
        unique=True,
    ),
    Index("ix_data_sources_tenant", "tenant_id"),
)

#: A Catalog Version, tables and all, as one JSONB document.
#:
#: Not normalised into table and field rows, because a Catalog Version is
#: immutable once its Harvest Run completes and the only read is "fetch one
#: whole version". Normalising would buy query flexibility nothing asks for and
#: cost a multi-table join on the one access path that matters.
catalog_versions = Table(
    "catalog_versions",
    metadata,
    Column("catalog_version_id", UUID(as_uuid=True), primary_key=True),
    Column(
        "tenant_id",
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "data_source_id",
        UUID(as_uuid=True),
        ForeignKey("data_sources.data_source_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("harvest_run_id", UUID(as_uuid=True), nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    #: `{"tables": [...], "unreadable": [...]}` — the frozen picture itself.
    Column("payload", JSONB, nullable=False),
    Index("ix_catalog_versions_tenant", "tenant_id"),
    # `latest_version` orders by this, per source.
    Index("ix_catalog_versions_source_created", "data_source_id", "created_at"),
)

#: A proposed or confirmed join, one row each.
#:
#: Rows rather than a document, unlike the catalog: relations are read, decided
#: and revoked one at a time, and a reviewer's decision is an update to exactly
#: one of them.
relations = Table(
    "relations",
    metadata,
    Column("relation_id", UUID(as_uuid=True), primary_key=True),
    Column(
        "tenant_id",
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "catalog_version_id",
        UUID(as_uuid=True),
        ForeignKey("catalog_versions.catalog_version_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("left_field_id", UUID(as_uuid=True), nullable=False),
    Column("right_field_id", UUID(as_uuid=True), nullable=False),
    #: `FieldIdentity` as `{table_name, field_name, normalised_type}`. What a
    #: confirmation is pinned to, so a re-harvest that did not change the field
    #: carries the decision forward and one that did makes it stale.
    Column("left_identity", JSONB, nullable=False),
    Column("right_identity", JSONB, nullable=False),
    Column("left_data_source_id", UUID(as_uuid=True), nullable=False),
    Column("right_data_source_id", UUID(as_uuid=True), nullable=False),
    Column("state", String(16), nullable=False),
    Column("origin", String(16), nullable=False),
    Column("confidence", Float, nullable=False),
    Column("binding_ceiling", String(16), nullable=False),
    Column("cardinality", String(16), nullable=False),
    Column("evidence", JSONB, nullable=True),
    Column("decided_at", TIMESTAMP(timezone=True), nullable=True),
    Column("decided_by", UUID(as_uuid=True), nullable=True),
    Column("rejection_reason", String(32), nullable=True),
    Column("stale_reason", String(32), nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=True),
    Column(
        "relation_metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    ),
    CheckConstraint(
        "state IN ('proposed', 'confirmed', 'rejected', 'stale')",
        name="ck_relations_state",
    ),
    CheckConstraint(
        "origin IN ('inferred', 'declared')",
        name="ck_relations_origin",
    ),
    Index("ix_relations_tenant", "tenant_id"),
    Index("ix_relations_catalog_version", "catalog_version_id"),
    # `list_for_source` reaches relations from either side of the join.
    Index("ix_relations_left_source", "left_data_source_id"),
    Index("ix_relations_right_source", "right_data_source_id"),
)

#: A Tenant decision that a table, or one field within it, is not for agents.
#:
#: Keyed by `table_name`/`field_name` rather than by `catalog_version_id` or a
#: field id, both of which are reassigned on every re-harvest — the point of
#: this table is that a decision survives re-harvesting the same table.
#: `field_name` null means the override is table-level.
#:
#: Two partial unique indexes rather than one over `(..., field_name)`,
#: because Postgres treats every `NULL` as distinct from every other `NULL`:
#: a plain unique index would let a Tenant "toggle" the same table off twice
#: and get two rows instead of one upsert.
catalog_agent_access = Table(
    "catalog_agent_access",
    metadata,
    Column("override_id", UUID(as_uuid=True), primary_key=True),
    Column(
        "tenant_id",
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "data_source_id",
        UUID(as_uuid=True),
        ForeignKey("data_sources.data_source_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("table_name", Text, nullable=False),
    Column("field_name", Text, nullable=True),
    Column("agent_visible", Boolean, nullable=False),
    Column("decided_by", UUID(as_uuid=True), nullable=False),
    Column("decided_at", TIMESTAMP(timezone=True), nullable=False),
    Index(
        "ux_catalog_agent_access_table",
        "tenant_id",
        "data_source_id",
        "table_name",
        unique=True,
        postgresql_where=text("field_name IS NULL"),
    ),
    Index(
        "ux_catalog_agent_access_field",
        "tenant_id",
        "data_source_id",
        "table_name",
        "field_name",
        unique=True,
        postgresql_where=text("field_name IS NOT NULL"),
    ),
    Index("ix_catalog_agent_access_source", "tenant_id", "data_source_id"),
)

#: One execution of discovery.
harvest_runs = Table(
    "harvest_runs",
    metadata,
    Column("harvest_run_id", UUID(as_uuid=True), primary_key=True),
    Column(
        "tenant_id",
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "data_source_id",
        UUID(as_uuid=True),
        ForeignKey("data_sources.data_source_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("phase", String(24), nullable=False),
    #: Scope and budget travel as documents: both are value objects read whole
    #: with the run, and neither is ever queried across runs.
    Column("scope", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("budget", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    Column("started_at", TIMESTAMP(timezone=True), nullable=True),
    Column("finished_at", TIMESTAMP(timezone=True), nullable=True),
    Column("tables_found", Integer, nullable=False, server_default=text("0")),
    Column("fields_described", Integer, nullable=False, server_default=text("0")),
    Column("fields_profiled", Integer, nullable=False, server_default=text("0")),
    Column("relations_proposed", Integer, nullable=False, server_default=text("0")),
    Column("unreadable_count", Integer, nullable=False, server_default=text("0")),
    Column("catalog_version_id", UUID(as_uuid=True), nullable=True),
    Column("failure_code", Text, nullable=True),
    Column("failure_message", Text, nullable=True),
    Column(
        "cancellation_requested",
        Boolean,
        nullable=False,
        server_default=text("false"),
    ),
    Index("ix_harvest_runs_tenant", "tenant_id"),
    Index("ix_harvest_runs_source", "data_source_id"),
)
