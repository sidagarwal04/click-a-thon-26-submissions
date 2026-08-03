"""Persistence for Connector Data Sources.

Unlike the Investigation repositories, these open their own connections rather
than being handed one. `ConnectorService` is built once at startup and holds its
repositories for the process lifetime — it has no unit of work to enlist in — so
a connection captured at construction would be a single connection shared by
every request. Each method takes a tenant-scoped connection for its own work and
gives it back.

Every method is tenant-scoped through `Database.tenant_connection`, which sets
`app.tenant_id` for RLS. The explicit `tenant_id` predicates are belt and braces:
a missing policy should mean a query returns nothing, not a cross-tenant read.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, insert, select, update
from zentra_domain_connector import DataSource, SourceHealth, SourceKind

from .database import Database
from .schema_connector import data_sources


def _to_entity(row: object) -> DataSource:
    """Rebuild a `DataSource`, credential still sealed.

    The ciphertext is carried across as bytes and never opened here — this layer
    has no key and no reason to hold a password in memory.
    """
    return DataSource(
        data_source_id=row.data_source_id,  # type: ignore[attr-defined]
        tenant_id=row.tenant_id,  # type: ignore[attr-defined]
        name=row.name,  # type: ignore[attr-defined]
        kind=SourceKind(row.kind),  # type: ignore[attr-defined]
        sealed_credentials=(
            bytes(row.sealed_credentials)  # type: ignore[attr-defined]
            if row.sealed_credentials is not None  # type: ignore[attr-defined]
            else None
        ),
        description=row.description,  # type: ignore[attr-defined]
        health=SourceHealth(row.health),  # type: ignore[attr-defined]
        store_sample_values=row.store_sample_values,  # type: ignore[attr-defined]
        last_verified_at=row.last_verified_at,  # type: ignore[attr-defined]
        last_harvested_at=row.last_harvested_at,  # type: ignore[attr-defined]
        created_at=row.created_at,  # type: ignore[attr-defined]
        landed_table=row.landed_table,  # type: ignore[attr-defined]
        metadata=dict(row.source_metadata or {}),  # type: ignore[attr-defined]
    )


def _mutable_values(source: DataSource) -> dict[str, object]:
    """The columns a save may change.

    Identity and `created_at` are absent by construction: a save that could move
    a row to another tenant is a save that could be made to leak one.
    """
    return {
        "name": source.name,
        "sealed_credentials": source.sealed_credentials,
        "description": source.description,
        "health": source.health.value,
        "store_sample_values": source.store_sample_values,
        "last_verified_at": source.last_verified_at,
        "last_harvested_at": source.last_harvested_at,
        "landed_table": source.landed_table,
        "source_metadata": dict(source.metadata),
    }


class PostgresDataSourceRepository:
    """`DataSourceRepository` over Postgres."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def add(self, source: DataSource) -> None:
        async with self._database.tenant_connection(source.tenant_id) as connection:
            await connection.execute(
                insert(data_sources).values(
                    data_source_id=source.data_source_id,
                    tenant_id=source.tenant_id,
                    kind=source.kind.value,
                    created_at=source.created_at,
                    **_mutable_values(source),
                )
            )

    async def get(self, data_source_id: UUID, *, tenant_id: UUID) -> DataSource | None:
        async with self._database.tenant_connection(tenant_id) as connection:
            row = (
                await connection.execute(
                    select(data_sources).where(
                        data_sources.c.data_source_id == data_source_id,
                        data_sources.c.tenant_id == tenant_id,
                    )
                )
            ).one_or_none()
        return None if row is None else _to_entity(row)

    async def list(self, *, tenant_id: UUID) -> Sequence[DataSource]:
        async with self._database.tenant_connection(tenant_id) as connection:
            rows = (
                await connection.execute(
                    select(data_sources)
                    .where(data_sources.c.tenant_id == tenant_id)
                    .order_by(data_sources.c.created_at.desc())
                )
            ).all()
        return [_to_entity(row) for row in rows]

    async def save(self, source: DataSource) -> None:
        async with self._database.tenant_connection(source.tenant_id) as connection:
            await connection.execute(
                update(data_sources)
                .where(
                    data_sources.c.data_source_id == source.data_source_id,
                    data_sources.c.tenant_id == source.tenant_id,
                )
                .values(**_mutable_values(source))
            )

    async def delete(self, data_source_id: UUID, *, tenant_id: UUID) -> None:
        async with self._database.tenant_connection(tenant_id) as connection:
            await connection.execute(
                delete(data_sources).where(
                    data_sources.c.data_source_id == data_source_id,
                    data_sources.c.tenant_id == tenant_id,
                )
            )


__all__ = ["PostgresDataSourceRepository"]
