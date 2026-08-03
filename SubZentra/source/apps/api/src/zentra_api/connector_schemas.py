"""Wire shapes for the Connector API.

Every model forbids extra fields, following ``schemas.py``. That matters more
here than anywhere else in this API: it is what makes "no credential ever
appears in a response" a property of the type rather than of each construction
site. There is deliberately no response model anywhere in this module with a
password field, so there is no way to build one.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from zentra_application_connector import (
    AgentAccessView,
    HarvestStatus,
    JoinGraphView,
    RelationView,
    SourceSummary,
    UploadPreview,
)
from zentra_domain_connector import (
    AccessOverrides,
    BindingCeiling,
    Cardinality,
    CatalogVersion,
    HarvestPhase,
    RejectionReason,
    RelationOrigin,
    RelationState,
    SourceHealth,
    SourceKind,
    UploadFormat,
)


class SourceCredentialsRequest(BaseModel):
    """Credentials on the way in. Write-only: nothing returns this shape."""

    model_config = ConfigDict(extra="forbid")

    host: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)
    database: str = Field(min_length=1)
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    secure: bool = True


class RegisterSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    credentials: SourceCredentialsRequest
    description: str | None = Field(default=None, max_length=1000)
    #: Off by default. Enabling it stores raw field values in ZentraOS, which is
    #: a materially different data posture, so it must be asked for explicitly.
    store_sample_values: bool = False


class UpdateCredentialsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credentials: SourceCredentialsRequest


class SourceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_source_id: UUID
    name: str
    kind: SourceKind
    health: SourceHealth
    description: str | None = None
    store_sample_values: bool = False
    connection_hint: str | None = None
    last_verified_at: datetime | None = None
    last_harvested_at: datetime | None = None
    created_at: datetime | None = None

    @classmethod
    def from_summary(cls, summary: SourceSummary) -> SourceResponse:
        return cls(
            data_source_id=summary.data_source_id,
            name=summary.name,
            kind=summary.kind,
            health=summary.health,
            description=summary.description,
            store_sample_values=summary.store_sample_values,
            connection_hint=summary.connection_hint,
            last_verified_at=summary.last_verified_at,
            last_harvested_at=summary.last_harvested_at,
            created_at=summary.created_at,
        )


class DeletionPreviewResponse(BaseModel):
    """What deleting a source would destroy. Informs; does not gate."""

    model_config = ConfigDict(extra="forbid")

    data_source_id: UUID
    name: str
    catalog_versions: int
    confirmed_relations: int
    #: Called out separately: deleting this source silently degrades another
    #: one, which is the consequence least likely to be anticipated.
    cross_source_relations: int
    drops_stored_data: bool


class StartHarvestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    databases: list[str] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)
    max_queries: int | None = Field(default=None, ge=1, le=100_000)
    sample_rows: int | None = Field(default=None, ge=1, le=10_000_000)


class UnreadableTableResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    qualified_name: str
    reason: str


class HarvestResponse(BaseModel):
    """Progress as counts. A percentage of an unknown total would be a fiction."""

    model_config = ConfigDict(extra="forbid")

    harvest_run_id: UUID
    data_source_id: UUID
    phase: HarvestPhase
    tables_found: int
    fields_described: int
    fields_profiled: int
    relations_proposed: int
    unreadable_count: int
    queries_used: int
    queries_budget: int
    seconds_used: float
    started_at: datetime | None = None
    finished_at: datetime | None = None
    catalog_version_id: UUID | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    unreadable: list[UnreadableTableResponse] = Field(default_factory=list)
    #: Fields inference never examined, grouped by why. An empty proposal list
    #: without these reads as "no relationships exist" when it may mean almost
    #: nothing was eligible to be examined.
    fields_unexamined: int = 0
    unexamined_reasons: dict[str, int] = Field(default_factory=dict)
    #: What inference does not look for. Stated, not left to be inferred.
    limitations: list[str] = Field(default_factory=list)

    @classmethod
    def from_status(cls, status: HarvestStatus) -> HarvestResponse:
        return cls(
            harvest_run_id=status.harvest_run_id,
            data_source_id=status.data_source_id,
            phase=status.phase,
            tables_found=status.tables_found,
            fields_described=status.fields_described,
            fields_profiled=status.fields_profiled,
            relations_proposed=status.relations_proposed,
            unreadable_count=status.unreadable_count,
            queries_used=status.queries_used,
            queries_budget=status.queries_budget,
            seconds_used=status.seconds_used,
            started_at=status.started_at,
            finished_at=status.finished_at,
            catalog_version_id=status.catalog_version_id,
            failure_code=status.failure_code,
            failure_message=status.failure_message,
            unreadable=[
                UnreadableTableResponse(qualified_name=name, reason=reason)
                for name, reason in status.unreadable
            ],
            fields_unexamined=status.fields_unexamined,
            unexamined_reasons=dict(status.unexamined_reasons),
            limitations=list(status.limitations),
        )


class FieldProfileResponse(BaseModel):
    """Statistics, always accompanied by the size of the sample behind them."""

    model_config = ConfigDict(extra="forbid")

    sampled_rows: int
    null_fraction: float | None = None
    distinct_count: int | None = None
    min_value: str | None = None
    max_value: str | None = None
    sample_values: list[str] = Field(default_factory=list)


class FieldResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_id: UUID
    name: str
    declared_type: str
    family: str
    nullable: bool
    position: int
    profile: FieldProfileResponse | None = None
    #: Whether the agent system may see this field. Defaults to visible; a
    #: Tenant departs from that default one field at a time.
    agent_visible: bool = True


class TableResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table_id: UUID
    name: str
    database: str
    engine: str | None = None
    #: Named an estimate because that is what ClickHouse stores. Presenting it
    #: as exact would invite a reader to reconcile it with a count that differs.
    estimated_rows: int | None = None
    size_bytes: int | None = None
    fields: list[FieldResponse] = Field(default_factory=list)
    agent_visible: bool = True


class CatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_version_id: UUID
    data_source_id: UUID
    harvest_run_id: UUID
    created_at: datetime
    tables: list[TableResponse] = Field(default_factory=list)
    unreadable: list[UnreadableTableResponse] = Field(default_factory=list)

    @classmethod
    def from_version(
        cls,
        version: CatalogVersion,
        *,
        overrides: AccessOverrides | None = None,
    ) -> CatalogResponse:
        """Build the response, folding in agent-access overrides at the seam.

        ``overrides`` stays optional so every existing caller keeps compiling;
        omitting it means every table and field reports the default (visible).
        """
        access = overrides or AccessOverrides.build(version.data_source_id, ())
        return cls(
            catalog_version_id=version.catalog_version_id,
            data_source_id=version.data_source_id,
            harvest_run_id=version.harvest_run_id,
            created_at=version.created_at,
            tables=[
                TableResponse(
                    table_id=table.table_id,
                    name=table.name,
                    database=table.database,
                    engine=table.engine,
                    estimated_rows=table.estimated_rows,
                    size_bytes=table.size_bytes,
                    agent_visible=access.is_table_visible(table.name),
                    fields=[
                        FieldResponse(
                            field_id=f.field_id,
                            name=f.name,
                            declared_type=f.declared_type,
                            family=f.family.value,
                            nullable=f.nullable,
                            position=f.position,
                            agent_visible=access.is_field_visible(table.name, f.name),
                            profile=(
                                FieldProfileResponse(
                                    sampled_rows=f.profile.sampled_rows,
                                    null_fraction=f.profile.null_fraction,
                                    distinct_count=f.profile.distinct_count,
                                    min_value=f.profile.min_value,
                                    max_value=f.profile.max_value,
                                    sample_values=list(f.profile.sample_values),
                                )
                                if f.profile
                                else None
                            ),
                        )
                        for f in table.fields
                    ],
                )
                for table in version.tables
            ],
            unreadable=[
                UnreadableTableResponse(
                    qualified_name=u.qualified_name, reason=u.reason
                )
                for u in version.unreadable
            ],
        )


class RelationResponse(BaseModel):
    """A Relation with the evidence a reviewer needs to disagree with it."""

    model_config = ConfigDict(extra="forbid")

    relation_id: UUID
    state: RelationState
    origin: RelationOrigin
    confidence: float
    #: Which bound held the confidence down, so a middling proposal can be
    #: understood rather than merely distrusted.
    binding_ceiling: BindingCeiling
    cardinality: Cardinality
    left: str
    right: str
    left_field_id: UUID
    right_field_id: UUID
    is_cross_source: bool
    evidence: dict[str, float] = Field(default_factory=dict)
    rejection_reason: RejectionReason | None = None
    stale_reason: str | None = None
    decided_at: datetime | None = None

    @classmethod
    def from_view(cls, view: RelationView) -> RelationResponse:
        return cls(
            relation_id=view.relation_id,
            state=view.state,
            origin=view.origin,
            confidence=view.confidence,
            binding_ceiling=view.binding_ceiling,
            cardinality=view.cardinality,
            left=view.left,
            right=view.right,
            left_field_id=view.left_field_id,
            right_field_id=view.right_field_id,
            is_cross_source=view.is_cross_source,
            evidence={k: float(v) for k, v in view.evidence.items()},
            rejection_reason=view.rejection_reason,
            stale_reason=view.stale_reason,
            decided_at=view.decided_at,
        )


class RelationDecisionRequest(BaseModel):
    """Confirm or reject. A rejection must say why; a confirmation need not.

    Asymmetric on purpose, and the same asymmetry the Investigation API already
    uses for Human Approvals: the recorded reason is what suppresses
    re-proposal, so a rejection without one would silently lose that behaviour.
    """

    model_config = ConfigDict(extra="forbid")

    decision: str = Field(pattern="^(confirm|reject)$")
    reason: RejectionReason | None = None


class SetAgentAccessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_visible: bool


class AgentAccessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    override_id: UUID
    data_source_id: UUID
    table_name: str
    field_name: str | None
    agent_visible: bool
    decided_by: UUID
    decided_at: datetime

    @classmethod
    def from_view(cls, view: AgentAccessView) -> AgentAccessResponse:
        return cls(
            override_id=view.override_id,
            data_source_id=view.data_source_id,
            table_name=view.table_name,
            field_name=view.field_name,
            agent_visible=view.agent_visible,
            decided_by=view.decided_by,
            decided_at=view.decided_at,
        )


class DeclareRelationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left_field_id: UUID
    right_field_id: UUID


class JoinGraphResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_version_id: UUID
    relations: list[RelationResponse] = Field(default_factory=list)
    #: Fields nothing connects to. The difference between "your data connects"
    #: and "half of it is unreachable and nobody said so".
    isolated_fields: list[str] = Field(default_factory=list)
    #: Populated only when the graph is empty, which is the one moment the
    #: absence of joins could be read as "your data has none".
    limitations: list[str] = Field(default_factory=list)

    @classmethod
    def from_view(cls, view: JoinGraphView) -> JoinGraphResponse:
        return cls(
            catalog_version_id=view.catalog_version_id,
            relations=[RelationResponse.from_view(r) for r in view.relations],
            isolated_fields=list(view.isolated_fields),
            limitations=list(view.limitations),
        )


class UploadColumnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    declared_type: str = Field(min_length=1)
    nullable: bool = True
    position: int = Field(ge=0)


class UploadPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_id: UUID
    filename: str
    upload_format: UploadFormat
    columns: list[UploadColumnRequest] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    total_bytes: int
    truncated: bool = False

    @classmethod
    def from_preview(cls, preview: UploadPreview) -> UploadPreviewResponse:
        return cls(
            upload_id=preview.upload_id,
            filename=preview.filename,
            upload_format=preview.upload_format,
            columns=[
                UploadColumnRequest(
                    name=c.name,
                    declared_type=c.declared_type,
                    nullable=c.nullable,
                    position=c.position,
                )
                for c in preview.columns
            ],
            rows=[list(row) for row in preview.rows],
            total_bytes=preview.total_bytes,
            truncated=preview.truncated,
        )


class CommitUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    #: The reviewer's corrections. Absent means the inferred types stand.
    columns: list[UploadColumnRequest] | None = None


class CatalogDiffResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_version_id: UUID
    carried_forward: int
    staled: int
    added_fields: int
    removed_fields: int
    type_changed_fields: int


class TableRowsResponse(BaseModel):
    """A page of raw rows from one Source Table, read straight through Cube.

    Columns and rows are pre-shaped server-side, in the catalog's own field
    order, so the frontend never has to reconcile Cube's `"table.field"`-keyed
    row objects against a separately-fetched column list.
    """

    model_config = ConfigDict(extra="forbid")

    data_source_id: UUID
    table_name: str
    columns: list[str]
    rows: list[list[str | None]]
    total: int
    page: int
    page_size: int
