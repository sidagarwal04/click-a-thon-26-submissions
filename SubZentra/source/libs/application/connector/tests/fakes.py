"""In-memory implementations of every connector port.

The service is the agreed test seam, so these exist to let behaviour be driven
through it without a database or a warehouse. They satisfy the Protocols by
shape, exactly as the real adapters do — which is also a standing check that the
ports are implementable without importing anything the application forbids.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from zentra_domain_connector import (
    CatalogAccessOverride,
    CatalogVersion,
    ConnectionCheck,
    ConnectionFailure,
    DataSource,
    FieldProfile,
    HarvestRun,
    OverlapMeasurement,
    Relation,
    UploadFormat,
)

from zentra_application_connector import (
    LandedTable,
    SourceCredentials,
    SourceFieldDescriptor,
    SourceTableDescriptor,
)


class FakeClock:
    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        self._now += timedelta(seconds=1)
        return self._now


@dataclass
class FakeCipher:
    """Reversible sealing that is obviously not encryption.

    A test that asserted on a real ciphertext would be testing the cipher. What
    matters here is that the service seals before storing and opens only to
    hand credentials to a connector — so a marker prefix is enough to prove the
    stored form is not the plaintext.
    """

    sealed: list[SourceCredentials] = field(default_factory=list)

    def seal(self, credentials: SourceCredentials) -> bytes:
        self.sealed.append(credentials)
        return f"sealed::{len(self.sealed) - 1}".encode()

    def open(self, sealed: bytes) -> SourceCredentials:
        index = int(sealed.decode().split("::")[1])
        return self.sealed[index]


@dataclass
class FakeConnector:
    """A warehouse whose contents and failures the test decides."""

    tables: dict[str, list[SourceFieldDescriptor]] = field(default_factory=dict)
    table_meta: dict[str, SourceTableDescriptor] = field(default_factory=dict)
    profiles: dict[str, FieldProfile] = field(default_factory=dict)
    overlaps: dict[tuple[str, str], OverlapMeasurement] = field(default_factory=dict)
    reachable: bool = True
    failure: ConnectionFailure = ConnectionFailure.AUTHENTICATION_FAILED
    unreadable_tables: set[str] = field(default_factory=set)
    describe_calls: int = 0
    profile_calls: int = 0
    overlap_calls: int = 0
    sample_values_requested: list[bool] = field(default_factory=list)

    async def test_connection(self, credentials: SourceCredentials) -> ConnectionCheck:
        if self.reachable:
            return ConnectionCheck(reachable=True)
        return ConnectionCheck(reachable=False, failure=self.failure)

    async def list_tables(
        self, credentials: SourceCredentials, *, databases: Sequence[str] = ()
    ) -> Sequence[SourceTableDescriptor]:
        """Only the tables in the database this connection points at.

        Scoping by the credentials' database matters for the cross-source
        tests: two Data Sources share this fake, and without the filter each
        would see the other's tables through its own connection, which no real
        connection does.
        """
        out = []
        for name in self.tables:
            meta = self.table_meta.get(
                name, SourceTableDescriptor(name=name, database=credentials.database)
            )
            if meta.database != credentials.database:
                continue
            if databases and meta.database not in databases:
                continue
            out.append(meta)
        return out

    async def describe_fields(
        self, credentials: SourceCredentials, *, database: str, table: str
    ) -> Sequence[SourceFieldDescriptor]:
        self.describe_calls += 1
        if table in self.unreadable_tables:
            raise RuntimeError(f"permission denied on {table}")
        return self.tables[table]

    async def profile_field(
        self,
        credentials: SourceCredentials,
        *,
        database: str,
        table: str,
        field_name: str,
        sample_rows: int,
        include_sample_values: bool,
    ) -> FieldProfile:
        self.profile_calls += 1
        self.sample_values_requested.append(include_sample_values)
        profile = self.profiles.get(
            f"{table}.{field_name}", FieldProfile(sampled_rows=sample_rows)
        )
        if not include_sample_values and profile.sample_values:
            profile = FieldProfile(
                sampled_rows=profile.sampled_rows,
                null_fraction=profile.null_fraction,
                distinct_count=profile.distinct_count,
                min_value=profile.min_value,
                max_value=profile.max_value,
            )
        return profile

    async def measure_overlap(
        self,
        left_credentials: SourceCredentials,
        right_credentials: SourceCredentials,
        *,
        left: tuple[str, str, str],
        right: tuple[str, str, str],
        sample_rows: int,
    ) -> OverlapMeasurement:
        self.overlap_calls += 1
        key = (f"{left[1]}.{left[2]}", f"{right[1]}.{right[2]}")
        if key in self.overlaps:
            return self.overlaps[key]
        reverse = (key[1], key[0])
        if reverse in self.overlaps:
            return self.overlaps[reverse]
        return OverlapMeasurement(
            left_distinct=1000,
            right_distinct=1000,
            matched_distinct=0,
            sampled_rows=sample_rows,
        )


@dataclass
class FakeLandingZone:
    columns: list[SourceFieldDescriptor] = field(default_factory=list)
    rows: list[tuple[str, ...]] = field(default_factory=list)
    total_rows: int = 0
    landed: list[LandedTable] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    parse_error: Exception | None = None

    async def inspect(
        self,
        stream: AsyncIterator[bytes],
        *,
        upload_format: UploadFormat,
        preview_rows: int,
    ) -> tuple[Sequence[SourceFieldDescriptor], Sequence[tuple[str, ...]], int]:
        async for _ in stream:
            pass
        if self.parse_error is not None:
            raise self.parse_error
        return self.columns, self.rows[:preview_rows], self.total_rows

    async def land(
        self,
        stream: AsyncIterator[bytes],
        *,
        tenant_id: UUID,
        upload_id: UUID,
        upload_format: UploadFormat,
        columns: Sequence[SourceFieldDescriptor],
    ) -> LandedTable:
        async for _ in stream:
            pass
        table = LandedTable(
            database="zentra_uploads",
            table=f"t_{tenant_id.hex[:8]}_{upload_id.hex[:8]}",
            row_count=self.total_rows,
        )
        self.landed.append(table)
        return table

    async def drop(self, *, database: str, table: str) -> None:
        self.dropped.append(f"{database}.{table}")

    def credentials_for(self, landed: LandedTable) -> SourceCredentials:
        return SourceCredentials(
            host="landing",
            port=8123,
            database=landed.database,
            username="uploads",
            password="uploads",
        )


class FakeSourceRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, DataSource] = {}

    async def add(self, source: DataSource) -> None:
        self.items[source.data_source_id] = source

    async def get(self, data_source_id: UUID, *, tenant_id: UUID) -> DataSource | None:
        source = self.items.get(data_source_id)
        # Tenant scoping is applied here rather than trusted from the caller,
        # so that a test which forgot to filter still cannot read across tenants.
        if source is None or source.tenant_id != tenant_id:
            return None
        return source

    async def list(self, *, tenant_id: UUID) -> Sequence[DataSource]:
        return [s for s in self.items.values() if s.tenant_id == tenant_id]

    async def save(self, source: DataSource) -> None:
        self.items[source.data_source_id] = source

    async def delete(self, data_source_id: UUID, *, tenant_id: UUID) -> None:
        source = self.items.get(data_source_id)
        if source is not None and source.tenant_id == tenant_id:
            del self.items[data_source_id]


class FakeCatalogRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, CatalogVersion] = {}

    async def add_version(self, version: CatalogVersion) -> None:
        self.items[version.catalog_version_id] = version

    async def get_version(
        self, catalog_version_id: UUID, *, tenant_id: UUID
    ) -> CatalogVersion | None:
        version = self.items.get(catalog_version_id)
        if version is None or version.tenant_id != tenant_id:
            return None
        return version

    async def latest_version(
        self, data_source_id: UUID, *, tenant_id: UUID
    ) -> CatalogVersion | None:
        matches = [
            v
            for v in self.items.values()
            if v.data_source_id == data_source_id and v.tenant_id == tenant_id
        ]
        if not matches:
            return None
        return max(matches, key=lambda v: v.created_at)

    async def list_versions(
        self, data_source_id: UUID, *, tenant_id: UUID
    ) -> Sequence[CatalogVersion]:
        return sorted(
            (
                v
                for v in self.items.values()
                if v.data_source_id == data_source_id and v.tenant_id == tenant_id
            ),
            key=lambda v: v.created_at,
        )


class FakeRelationRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, Relation] = {}

    async def add_many(self, relations: Sequence[Relation]) -> None:
        for relation in relations:
            self.items[relation.relation_id] = relation

    async def get(self, relation_id: UUID, *, tenant_id: UUID) -> Relation | None:
        relation = self.items.get(relation_id)
        if relation is None or relation.tenant_id != tenant_id:
            return None
        return relation

    async def save(self, relation: Relation) -> None:
        self.items[relation.relation_id] = relation

    async def list_for_version(
        self, catalog_version_id: UUID, *, tenant_id: UUID
    ) -> Sequence[Relation]:
        return [
            r
            for r in self.items.values()
            if r.catalog_version_id == catalog_version_id and r.tenant_id == tenant_id
        ]

    async def list_for_source(
        self, data_source_id: UUID, *, tenant_id: UUID
    ) -> Sequence[Relation]:
        return [
            r
            for r in self.items.values()
            if r.tenant_id == tenant_id
            and data_source_id in (r.left_data_source_id, r.right_data_source_id)
        ]


class FakeAgentAccessRepository:
    """Upserts by (data_source_id, table_name, field_name), like the real one."""

    def __init__(self) -> None:
        self.items: dict[tuple[UUID, str, str | None], CatalogAccessOverride] = {}

    async def upsert(self, override: CatalogAccessOverride) -> None:
        key = (override.data_source_id, override.table_name, override.field_name)
        self.items[key] = override

    async def list_for_source(
        self, data_source_id: UUID, *, tenant_id: UUID
    ) -> Sequence[CatalogAccessOverride]:
        return [
            o
            for o in self.items.values()
            if o.data_source_id == data_source_id and o.tenant_id == tenant_id
        ]


class FakeHarvestRunRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, HarvestRun] = {}

    async def add(self, run: HarvestRun) -> None:
        self.items[run.harvest_run_id] = run

    async def get(self, harvest_run_id: UUID, *, tenant_id: UUID) -> HarvestRun | None:
        run = self.items.get(harvest_run_id)
        if run is None or run.tenant_id != tenant_id:
            return None
        return run

    async def save(self, run: HarvestRun) -> None:
        self.items[run.harvest_run_id] = run

    async def list_for_source(
        self, data_source_id: UUID, *, tenant_id: UUID
    ) -> Sequence[HarvestRun]:
        return [
            r
            for r in self.items.values()
            if r.data_source_id == data_source_id and r.tenant_id == tenant_id
        ]

    async def active_for_source(
        self, data_source_id: UUID, *, tenant_id: UUID
    ) -> HarvestRun | None:
        for run in self.items.values():
            if (
                run.data_source_id == data_source_id
                and run.tenant_id == tenant_id
                and not run.is_terminal
            ):
                return run
        return None
