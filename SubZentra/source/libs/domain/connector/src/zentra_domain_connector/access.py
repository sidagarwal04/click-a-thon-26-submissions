"""Which harvested tables and fields the agent system may see.

Every table and field a Harvest Run finds is visible to agents by default —
that default lives here as an absence, not a row. A ``CatalogAccessOverride``
only ever records a *departure* from that default, one Tenant decision at a
time.

Pinned to ``table_name``/``field_name`` rather than to a Catalog Version or a
field id, for the same reason a ``Relation`` is pinned to a ``FieldIdentity``:
both change on every re-harvest, and the point of turning a column off is that
it stays off the next time the same table is harvested.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .catalog import CatalogVersion, SourceField, SourceTable


@dataclass(frozen=True, slots=True)
class CatalogAccessOverride:
    """One Tenant decision that a table, or one field within it, is not for agents.

    ``field_name`` absent means the override is table-level: every field in
    that table is hidden, not just the ones with their own override.
    """

    override_id: UUID
    tenant_id: UUID
    data_source_id: UUID
    table_name: str
    field_name: str | None
    agent_visible: bool
    decided_by: UUID
    decided_at: datetime

    @property
    def is_table_level(self) -> bool:
        return self.field_name is None


@dataclass(frozen=True, slots=True)
class AccessOverrides:
    """The latest override per (table, field) key, ready to gate a catalog read.

    Construction keeps only the most recent override for each key rather than
    trusting the caller to have already resolved that — the same discipline
    ``JoinGraph.build`` applies by filtering to confirmed Relations, so a
    superseded decision can never leak back in by accident.
    """

    data_source_id: UUID
    by_table: dict[str, CatalogAccessOverride]
    by_field: dict[tuple[str, str], CatalogAccessOverride]

    @classmethod
    def build(
        cls,
        data_source_id: UUID,
        overrides: tuple[CatalogAccessOverride, ...],
    ) -> AccessOverrides:
        by_table: dict[str, CatalogAccessOverride] = {}
        by_field: dict[tuple[str, str], CatalogAccessOverride] = {}
        for override in sorted(overrides, key=lambda o: o.decided_at):
            if override.is_table_level:
                by_table[override.table_name] = override
            else:
                by_field[(override.table_name, override.field_name)] = override  # type: ignore[index]
        return cls(data_source_id=data_source_id, by_table=by_table, by_field=by_field)

    def is_table_visible(self, table_name: str) -> bool:
        override = self.by_table.get(table_name)
        return override is None or override.agent_visible

    def is_field_visible(self, table_name: str, field_name: str) -> bool:
        """A field is visible only if both its table and the field itself are.

        Checked as an AND rather than letting a field-level override alone
        decide, so a table turned off cannot be reopened one column at a time
        by a stale per-field row left over from before the table was hidden.
        """
        if not self.is_table_visible(table_name):
            return False
        override = self.by_field.get((table_name, field_name))
        return override is None or override.agent_visible

    def apply(self, version: CatalogVersion) -> CatalogVersion:
        """A Catalog Version with every hidden table and field dropped.

        The single enforcement point: any code that means to show agents only
        what they are allowed to see calls this instead of reading
        ``version.tables`` directly.
        """
        visible_tables: list[SourceTable] = []
        for table in version.tables:
            if not self.is_table_visible(table.name):
                continue
            visible_fields: tuple[SourceField, ...] = tuple(
                field
                for field in table.fields
                if self.is_field_visible(table.name, field.name)
            )
            visible_tables.append(_replace_fields(table, visible_fields))

        return CatalogVersion(
            catalog_version_id=version.catalog_version_id,
            data_source_id=version.data_source_id,
            tenant_id=version.tenant_id,
            harvest_run_id=version.harvest_run_id,
            created_at=version.created_at,
            tables=tuple(visible_tables),
            unreadable=version.unreadable,
        )


def _replace_fields(table: SourceTable, fields: tuple[SourceField, ...]) -> SourceTable:
    return SourceTable(
        table_id=table.table_id,
        name=table.name,
        database=table.database,
        engine=table.engine,
        estimated_rows=table.estimated_rows,
        size_bytes=table.size_bytes,
        fields=fields,
    )
