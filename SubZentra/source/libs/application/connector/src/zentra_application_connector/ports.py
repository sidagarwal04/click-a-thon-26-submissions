"""The seams the connector application talks through.

Protocols rather than base classes, so an adapter satisfies one by shape and the
application never imports it. This is what keeps the package free of
``clickhouse_connect`` and ``sqlalchemy``, enforced by the import-linter
contracts rather than by review.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from zentra_domain_connector import (
    CatalogAccessOverride,
    CatalogVersion,
    ConnectionCheck,
    DataSource,
    FieldProfile,
    HarvestRun,
    OverlapMeasurement,
    Relation,
    UploadFormat,
)

from .dto import (
    LandedTable,
    SourceCredentials,
    SourceFieldDescriptor,
    SourceTableDescriptor,
)


class SourceConnector(Protocol):
    """Everything the application needs from a data source.

    Five operations, deliberately narrow. A second source type — Postgres,
    BigQuery — is one class implementing this, which is the whole of what the
    "any data source" claim costs.

    ``measure_overlap`` is the one that must be implemented carefully: it exists
    so overlap can be computed *at the source* by aggregate query. An
    implementation that pulled both sides back and compared them locally would
    satisfy the type and violate the design.
    """

    async def test_connection(
        self, credentials: SourceCredentials
    ) -> ConnectionCheck: ...

    async def list_tables(
        self,
        credentials: SourceCredentials,
        *,
        databases: Sequence[str] = (),
    ) -> Sequence[SourceTableDescriptor]: ...

    async def describe_fields(
        self,
        credentials: SourceCredentials,
        *,
        database: str,
        table: str,
    ) -> Sequence[SourceFieldDescriptor]: ...

    async def profile_field(
        self,
        credentials: SourceCredentials,
        *,
        database: str,
        table: str,
        field_name: str,
        sample_rows: int,
        include_sample_values: bool,
    ) -> FieldProfile: ...

    async def measure_overlap(
        self,
        left_credentials: SourceCredentials,
        right_credentials: SourceCredentials,
        *,
        left: tuple[str, str, str],
        right: tuple[str, str, str],
        sample_rows: int,
    ) -> OverlapMeasurement: ...


class FileLandingZone(Protocol):
    """Where an uploaded file becomes a queryable table.

    Separate from ``SourceConnector`` because landing is a write and everything
    else here is a read. The landing zone is ZentraOS-owned storage; the
    connector reads customer-owned storage. Conflating them would blur the one
    boundary that matters most in this design.
    """

    async def land(
        self,
        stream: AsyncIterator[bytes],
        *,
        tenant_id: UUID,
        upload_id: UUID,
        upload_format: UploadFormat,
        columns: Sequence[SourceFieldDescriptor],
    ) -> LandedTable: ...

    async def inspect(
        self,
        stream: AsyncIterator[bytes],
        *,
        upload_format: UploadFormat,
        preview_rows: int,
    ) -> tuple[Sequence[SourceFieldDescriptor], Sequence[tuple[str, ...]], int]: ...

    async def drop(self, *, database: str, table: str) -> None: ...

    def credentials_for(self, landed: LandedTable) -> SourceCredentials: ...


class CredentialCipher(Protocol):
    """Sealing and opening source credentials.

    Named for what it guarantees rather than how. The application seals before
    handing anything to a repository and opens only in the moment a connector
    needs it, so plaintext never rests anywhere a query or a backup could reach.
    """

    def seal(self, credentials: SourceCredentials) -> bytes: ...

    def open(self, sealed: bytes) -> SourceCredentials: ...


class DataSourceRepository(Protocol):
    async def add(self, source: DataSource) -> None: ...

    async def get(
        self, data_source_id: UUID, *, tenant_id: UUID
    ) -> DataSource | None: ...

    async def list(self, *, tenant_id: UUID) -> Sequence[DataSource]: ...

    async def save(self, source: DataSource) -> None: ...

    async def delete(self, data_source_id: UUID, *, tenant_id: UUID) -> None: ...


class CatalogRepository(Protocol):
    async def add_version(self, version: CatalogVersion) -> None: ...

    async def get_version(
        self, catalog_version_id: UUID, *, tenant_id: UUID
    ) -> CatalogVersion | None: ...

    async def latest_version(
        self, data_source_id: UUID, *, tenant_id: UUID
    ) -> CatalogVersion | None: ...

    async def list_versions(
        self, data_source_id: UUID, *, tenant_id: UUID
    ) -> Sequence[CatalogVersion]: ...


class RelationRepository(Protocol):
    async def add_many(self, relations: Sequence[Relation]) -> None: ...

    async def get(self, relation_id: UUID, *, tenant_id: UUID) -> Relation | None: ...

    async def save(self, relation: Relation) -> None: ...

    async def list_for_version(
        self, catalog_version_id: UUID, *, tenant_id: UUID
    ) -> Sequence[Relation]: ...

    async def list_for_source(
        self, data_source_id: UUID, *, tenant_id: UUID
    ) -> Sequence[Relation]: ...


class HarvestRunRepository(Protocol):
    async def add(self, run: HarvestRun) -> None: ...

    async def get(
        self, harvest_run_id: UUID, *, tenant_id: UUID
    ) -> HarvestRun | None: ...

    async def save(self, run: HarvestRun) -> None: ...

    async def list_for_source(
        self, data_source_id: UUID, *, tenant_id: UUID
    ) -> Sequence[HarvestRun]: ...

    async def active_for_source(
        self, data_source_id: UUID, *, tenant_id: UUID
    ) -> HarvestRun | None: ...


class AgentAccessRepository(Protocol):
    """Per-table/per-field agent visibility overrides.

    Every override is a full replacement of the row it targets — there is no
    partial update — so `upsert` is the only write this port offers.
    """

    async def upsert(self, override: CatalogAccessOverride) -> None: ...

    async def list_for_source(
        self, data_source_id: UUID, *, tenant_id: UUID
    ) -> Sequence[CatalogAccessOverride]: ...


class Clock(Protocol):
    def now(self) -> datetime: ...
