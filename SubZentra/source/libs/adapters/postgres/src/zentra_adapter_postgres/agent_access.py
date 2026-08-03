"""Persistence for CatalogAccessOverride: per-table/per-field agent visibility.

Its own module rather than folded into `connector_catalog.py`, the same split
that file already draws between `PostgresCatalogRepository` (immutable,
whole-version reads) and the relation repository (small, individually
decided rows) — an access override is the latter shape, not the former.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from zentra_domain_connector import CatalogAccessOverride

from .database import Database
from .schema_connector import catalog_agent_access


def _from_row(row: Any) -> CatalogAccessOverride:
    return CatalogAccessOverride(
        override_id=row.override_id,
        tenant_id=row.tenant_id,
        data_source_id=row.data_source_id,
        table_name=row.table_name,
        field_name=row.field_name,
        agent_visible=row.agent_visible,
        decided_by=row.decided_by,
        decided_at=row.decided_at,
    )


class PostgresAgentAccessRepository:
    """`AgentAccessRepository` over Postgres.

    Upserts on one of two partial unique indexes depending on whether the
    override is table-level or field-level, so repeating the same toggle
    updates the one row that decision owns rather than accumulating rows.
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    async def upsert(self, override: CatalogAccessOverride) -> None:
        values = {
            "override_id": override.override_id,
            "tenant_id": override.tenant_id,
            "data_source_id": override.data_source_id,
            "table_name": override.table_name,
            "field_name": override.field_name,
            "agent_visible": override.agent_visible,
            "decided_by": override.decided_by,
            "decided_at": override.decided_at,
        }
        if override.is_table_level:
            index_elements = ["tenant_id", "data_source_id", "table_name"]
            index_where = text("field_name IS NULL")
        else:
            index_elements = ["tenant_id", "data_source_id", "table_name", "field_name"]
            index_where = text("field_name IS NOT NULL")

        async with self._database.tenant_connection(override.tenant_id) as connection:
            await connection.execute(
                insert(catalog_agent_access)
                .values(**values)
                .on_conflict_do_update(
                    index_elements=index_elements,
                    index_where=index_where,
                    set_={
                        "agent_visible": override.agent_visible,
                        "decided_by": override.decided_by,
                        "decided_at": override.decided_at,
                    },
                )
            )

    async def list_for_source(
        self, data_source_id: UUID, *, tenant_id: UUID
    ) -> Sequence[CatalogAccessOverride]:
        async with self._database.tenant_connection(tenant_id) as connection:
            rows = (
                await connection.execute(
                    select(catalog_agent_access).where(
                        catalog_agent_access.c.data_source_id == data_source_id,
                        catalog_agent_access.c.tenant_id == tenant_id,
                    )
                )
            ).all()
        return [_from_row(row) for row in rows]


__all__ = ["PostgresAgentAccessRepository"]
