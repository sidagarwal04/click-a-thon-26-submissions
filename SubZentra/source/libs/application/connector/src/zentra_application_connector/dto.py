"""What the connector application accepts and returns.

Read models here are deliberately not the domain entities. A ``DataSource``
carries sealed credential bytes; a ``SourceSummary`` cannot, because it is what
crosses the API boundary. Keeping them as separate types means the redaction is
structural rather than something every caller must remember.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from zentra_domain_connector import (
    BindingCeiling,
    Cardinality,
    ConnectionFailure,
    HarvestPhase,
    RejectionReason,
    RelationOrigin,
    RelationState,
    SourceHealth,
    SourceKind,
    UploadFormat,
)


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


#: Roles permitted to change what the connector knows or trusts.
#:
#: Confirming a Relation licenses agents to join on it, which is a governance
#: act rather than a browsing one — so it sits with source registration on the
#: admin side of the line rather than with catalog reads.
WRITE_ROLES: frozenset[Role] = frozenset({Role.OWNER, Role.ADMIN})

#: Roles permitted to start a harvest. Members may, because a harvest changes
#: nothing a human has decided — it only refreshes what the system observed.
HARVEST_ROLES: frozenset[Role] = frozenset({Role.OWNER, Role.ADMIN, Role.MEMBER})


@dataclass(frozen=True, slots=True)
class AuthenticatedActor:
    user_id: UUID
    tenant_id: UUID
    role: Role


class PermissionDeniedError(PermissionError):
    pass


class DataSourceNotFoundError(LookupError):
    pass


class RelationNotFoundError(LookupError):
    pass


class HarvestRunNotFoundError(LookupError):
    pass


class CatalogVersionNotFoundError(LookupError):
    pass


class ConflictError(RuntimeError):
    pass


class ConnectionFailedError(RuntimeError):
    """A source could not be reached, with a reason the caller can act on.

    Carries the typed failure and nothing from the source's own error text,
    which routinely contains hostnames and usernames and is destined for an API
    response.
    """

    def __init__(self, failure: ConnectionFailure) -> None:
        super().__init__(failure.value)
        self.failure = failure


class UploadRejectedError(ValueError):
    """A file could not be parsed, with the location of the problem."""

    def __init__(
        self,
        message: str,
        *,
        row: int | None = None,
        column: str | None = None,
    ):
        super().__init__(message)
        self.row = row
        self.column = column


@dataclass(frozen=True, slots=True)
class SourceCredentials:
    """Connection details for a source. Never leaves the application layer."""

    host: str
    port: int
    database: str
    username: str
    password: str
    secure: bool = True


@dataclass(frozen=True, slots=True)
class SourceSummary:
    """The safe read model of a Data Source.

    There is no credential field, so there is no representation of a source
    that could accidentally be serialised into a response or a log line.
    """

    data_source_id: UUID
    name: str
    kind: SourceKind
    health: SourceHealth
    description: str | None = None
    store_sample_values: bool = False
    last_verified_at: datetime | None = None
    last_harvested_at: datetime | None = None
    created_at: datetime | None = None
    #: A non-reversible hint so an admin can tell two sources apart without the
    #: secret being present: host and database only, never user or password.
    connection_hint: str | None = None


@dataclass(frozen=True, slots=True)
class SourceTableDescriptor:
    """What a connector reports about a table before its fields are read."""

    name: str
    database: str
    engine: str | None = None
    estimated_rows: int | None = None
    size_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class SourceFieldDescriptor:
    """What a connector reports about a column."""

    name: str
    declared_type: str
    nullable: bool
    position: int


@dataclass(frozen=True, slots=True)
class LandedTable:
    """Where an uploaded file ended up."""

    database: str
    table: str
    row_count: int

    @property
    def qualified_name(self) -> str:
        return f"{self.database}.{self.table}"


@dataclass(frozen=True, slots=True)
class UploadPreview:
    """What a file looks like before anyone commits to it.

    Types are inferred but presented as a proposal: a mis-parsed date column
    that is only discovered after commit has already poisoned every profile and
    every relation downstream of it.
    """

    upload_id: UUID
    filename: str
    upload_format: UploadFormat
    columns: tuple[SourceFieldDescriptor, ...]
    rows: tuple[tuple[str, ...], ...]
    total_bytes: int
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class HarvestStatus:
    """Progress of a Harvest Run, in counts rather than a percentage.

    A percentage of an unknown total is a fiction. "412 fields described" is
    something a reader can act on.
    """

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
    unreadable: tuple[tuple[str, str], ...] = ()
    #: Fields inference never examined, grouped by why. Without these an empty
    #: proposal list reads as "no relationships exist" when it may mean "almost
    #: nothing here was eligible to be looked at".
    fields_unexamined: int = 0
    unexamined_reasons: dict[str, int] = field(default_factory=dict)
    #: What inference does not look for. Stated, not left to be inferred.
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RelationView:
    """A Relation as a reviewer sees it, with the reasoning attached."""

    relation_id: UUID
    state: RelationState
    origin: RelationOrigin
    confidence: float
    binding_ceiling: BindingCeiling
    cardinality: Cardinality
    left: str
    right: str
    left_field_id: UUID
    right_field_id: UUID
    is_cross_source: bool
    evidence: dict[str, float | int] = field(default_factory=dict)
    rejection_reason: RejectionReason | None = None
    stale_reason: str | None = None
    decided_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class AgentAccessView:
    """A table/field agent-visibility decision as an API caller sees it."""

    override_id: UUID
    data_source_id: UUID
    table_name: str
    field_name: str | None
    agent_visible: bool
    decided_by: UUID
    decided_at: datetime


@dataclass(frozen=True, slots=True)
class JoinGraphView:
    """The confirmed Relations of a Catalog Version, plus what is unreachable."""

    catalog_version_id: UUID
    relations: tuple[RelationView, ...]
    isolated_fields: tuple[str, ...] = ()
    #: Carried on the graph itself so a caller reading an empty one is told what
    #: was not looked for, at the moment the emptiness would otherwise mislead.
    limitations: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not self.relations


@dataclass(frozen=True, slots=True)
class DeletionPreview:
    """What removing a Data Source would take with it.

    Informs rather than gates: deletion stays unconditional, because a Tenant
    who wants their data gone should not be argued with. But "this also destroys
    fourteen confirmed Relations, three of which join your uploaded file to your
    warehouse" is something they should learn before, not after.
    """

    data_source_id: UUID
    name: str
    catalog_versions: int
    confirmed_relations: int
    #: Confirmed Relations reaching into a *different* source. Called out
    #: separately because deleting this source silently degrades another one,
    #: which is the consequence least likely to be anticipated.
    cross_source_relations: int
    #: True for an uploaded source, whose landed table is dropped outright.
    drops_stored_data: bool


@dataclass(frozen=True, slots=True)
class ReharvestReport:
    """What a re-harvest did to work a human had already done."""

    catalog_version_id: UUID
    carried_forward: int
    staled: int
    added_fields: int
    removed_fields: int
    type_changed_fields: int
