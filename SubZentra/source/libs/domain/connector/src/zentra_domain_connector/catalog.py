"""Data Sources, Catalog Versions, and the fields they contain.

A Catalog Version is immutable once a Harvest Run completes. Re-harvesting adds
a version rather than editing one, so a published Finding can keep pointing at
the picture of the schema it was actually computed against — which is what lets
Investigation Replay stay honest as schemas move on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from .types import SourceHealth, SourceKind, TypeFamily


@dataclass(frozen=True, slots=True)
class FieldIdentity:
    """What makes a field *the same field* across Catalog Versions.

    Deliberately not the database row id, which changes every harvest, and
    deliberately not the name alone, which would let a type change pass
    unnoticed. Name, type and parent table together: change any of them and the
    field the reviewer confirmed a Relation against no longer exists.

    This single decision is what allows both desirable re-harvest behaviours at
    once — routine re-harvests carry confirmations forward without re-review,
    while a genuine schema change withdraws them.
    """

    table_name: str
    field_name: str
    normalised_type: str

    def __str__(self) -> str:
        return f"{self.table_name}.{self.field_name}:{self.normalised_type}"


@dataclass(frozen=True, slots=True)
class FieldProfile:
    """Observed statistics for a Source Field.

    Distinct from declared schema, which is free to read. These cost queries
    against the customer's warehouse, so they are modelled — and budgeted —
    separately.

    ``sampled_rows`` is carried on every profile so that no statistic can be
    presented without the size of the evidence behind it. ``sample_values`` is
    empty unless the Data Source explicitly opted in; the default is off
    because retained raw values would place customer data in ZentraOS storage.
    """

    sampled_rows: int
    null_fraction: float | None = None
    distinct_count: int | None = None
    min_value: str | None = None
    max_value: str | None = None
    sample_values: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.sampled_rows < 0:
            raise ValueError("sampled_rows cannot be negative")
        if self.null_fraction is not None and not 0.0 <= self.null_fraction <= 1.0:
            raise ValueError("null_fraction must be a fraction between 0 and 1")
        if self.distinct_count is not None and self.distinct_count < 0:
            raise ValueError("distinct_count cannot be negative")

    @property
    def is_unique(self) -> bool:
        """Whether every sampled row held a different value.

        Used to state a Relation's direction. Honest about its own limits: this
        is uniqueness *within the sample*, never a constraint, because
        ClickHouse has no uniqueness constraint to appeal to.
        """
        from .constants import UNIQUENESS_TOLERANCE

        if self.distinct_count is None or self.sampled_rows == 0:
            return False
        return self.distinct_count >= self.sampled_rows * UNIQUENESS_TOLERANCE


@dataclass(frozen=True, slots=True)
class SourceField:
    """One harvested column."""

    field_id: UUID
    table_id: UUID
    name: str
    declared_type: str
    family: TypeFamily
    normalised_type: str
    nullable: bool
    position: int
    profile: FieldProfile | None = None

    def identity(self, table_name: str) -> FieldIdentity:
        return FieldIdentity(
            table_name=table_name,
            field_name=self.name,
            normalised_type=self.normalised_type,
        )


@dataclass(frozen=True, slots=True)
class SourceTable:
    """One harvested table and its fields."""

    table_id: UUID
    name: str
    database: str
    engine: str | None = None
    estimated_rows: int | None = None
    size_bytes: int | None = None
    fields: tuple[SourceField, ...] = ()

    @property
    def qualified_name(self) -> str:
        return f"{self.database}.{self.name}"


@dataclass(frozen=True, slots=True)
class UnreadableTable:
    """A table a harvest could see but not read.

    Kept alongside the successful results rather than aborting the run: one
    permission-denied table should not discard everything else that was learned.
    """

    qualified_name: str
    reason: str


@dataclass(frozen=True, slots=True)
class CatalogVersion:
    """What a Harvest Run learned, frozen at the moment it completed."""

    catalog_version_id: UUID
    data_source_id: UUID
    tenant_id: UUID
    harvest_run_id: UUID
    created_at: datetime
    tables: tuple[SourceTable, ...] = ()
    unreadable: tuple[UnreadableTable, ...] = ()

    def field_index(self) -> dict[FieldIdentity, SourceField]:
        """Every field in this version, keyed by what makes it stable."""
        index: dict[FieldIdentity, SourceField] = {}
        for table in self.tables:
            for source_field in table.fields:
                index[source_field.identity(table.name)] = source_field
        return index

    def table_names(self) -> frozenset[str]:
        return frozenset(table.name for table in self.tables)

    def find_field(self, field_id: UUID) -> tuple[SourceTable, SourceField] | None:
        for table in self.tables:
            for source_field in table.fields:
                if source_field.field_id == field_id:
                    return table, source_field
        return None

    def search(self, term: str) -> tuple[tuple[SourceTable, SourceField | None], ...]:
        """Find tables and fields whose name contains ``term``.

        Case-insensitive substring rather than anything cleverer: the job is
        finding ``customer_id`` across dozens of tables, and a fuzzy match that
        surfaced near-misses would make that harder rather than easier.
        """
        needle = term.strip().lower()
        if not needle:
            return ()
        hits: list[tuple[SourceTable, SourceField | None]] = []
        for table in self.tables:
            if needle in table.name.lower():
                hits.append((table, None))
            for source_field in table.fields:
                if needle in source_field.name.lower():
                    hits.append((table, source_field))
        return tuple(hits)


@dataclass(frozen=True, slots=True)
class FieldChange:
    identity: FieldIdentity
    change: str


@dataclass(frozen=True, slots=True)
class CatalogDiff:
    """What changed between two Catalog Versions."""

    added: tuple[FieldIdentity, ...] = ()
    removed: tuple[FieldIdentity, ...] = ()
    type_changed: tuple[FieldChange, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.type_changed)


def diff_catalogs(previous: CatalogVersion, current: CatalogVersion) -> CatalogDiff:
    """Compare two Catalog Versions field by field.

    A field whose type changed shows up as a type change rather than as a
    removal plus an addition, because that is what a reader wants to know and
    because a confirmed Relation on it needs to be stale rather than orphaned.
    """
    before = previous.field_index()
    after = current.field_index()

    by_name_before = {(i.table_name, i.field_name): i for i in before}
    by_name_after = {(i.table_name, i.field_name): i for i in after}

    added = tuple(
        identity
        for key, identity in by_name_after.items()
        if key not in by_name_before
    )
    removed = tuple(
        identity
        for key, identity in by_name_before.items()
        if key not in by_name_after
    )
    type_changed = tuple(
        FieldChange(
            identity=by_name_before[key],
            change=(
                f"{by_name_before[key].normalised_type} -> "
                f"{by_name_after[key].normalised_type}"
            ),
        )
        for key in by_name_before
        if key in by_name_after
        and by_name_before[key].normalised_type != by_name_after[key].normalised_type
    )
    return CatalogDiff(added=added, removed=removed, type_changed=type_changed)


@dataclass(slots=True)
class DataSource:
    """A tenant-owned origin of queryable data ZentraOS may read.

    Credentials live behind ``sealed_credentials`` and are never held in the
    clear on this object, so there is no representation of a Data Source that
    could accidentally be serialised into a response or a log line.
    """

    data_source_id: UUID
    tenant_id: UUID
    name: str
    kind: SourceKind
    sealed_credentials: bytes | None = None
    description: str | None = None
    health: SourceHealth = SourceHealth.UNVERIFIED
    store_sample_values: bool = False
    last_verified_at: datetime | None = None
    last_harvested_at: datetime | None = None
    created_at: datetime | None = None
    #: Only meaningful for uploaded sources: where the landed table lives.
    landed_table: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def mark_reachable(self, *, at: datetime) -> None:
        self.health = SourceHealth.REACHABLE
        self.last_verified_at = at

    def mark_unreachable(self, *, at: datetime) -> None:
        self.health = SourceHealth.UNREACHABLE
        self.last_verified_at = at

    def mark_harvested(self, *, at: datetime) -> None:
        self.last_harvested_at = at
