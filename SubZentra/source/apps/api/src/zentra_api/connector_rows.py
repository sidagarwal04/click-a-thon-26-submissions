"""Building and parsing a raw dimension-browse query for one Source Table.

Deliberately bypasses `CubeSemanticLayer.query()`'s `reject_ungoverned` gate:
every dimension here comes from `CatalogVersion.tables[i].fields[j]`, never
from caller input, so there is nothing ungoverned to reject — this is a
one-purpose escape hatch for browsing raw catalog fields, not a general query
endpoint. See docs/adr/0023-source-table-row-browsing-bypasses-governed-query.md.
"""

from __future__ import annotations

from typing import Any

from zentra_domain_connector import CatalogVersion, SourceTable

#: Fixed in v1 — no page-size selector on the frontend, so there is only one
#: number to keep the two ends of this contract agreeing on.
ROW_PAGE_SIZE = 50


class TableNotInCatalogError(LookupError):
    """`table_name` is not (or no longer) in the latest Catalog Version."""


class CubeNotReadyError(RuntimeError):
    """Cube could not serve this table — not generated yet, or unreachable."""


def find_table(version: CatalogVersion, table_name: str) -> SourceTable:
    for table in version.tables:
        if table.name == table_name:
            return table
    raise TableNotInCatalogError(table_name)


def build_rows_query(table: SourceTable, *, page: int) -> dict[str, Any]:
    fields = sorted(table.fields, key=lambda f: f.position)
    return {
        "dimensions": [f"{table.name}.{f.name}" for f in fields],
        "limit": ROW_PAGE_SIZE,
        "offset": (page - 1) * ROW_PAGE_SIZE,
        "total": True,
    }


def parse_rows_payload(
    payload: dict[str, Any], table: SourceTable
) -> tuple[list[str], list[list[str | None]], int]:
    fields = sorted(table.fields, key=lambda f: f.position)
    columns = [f.name for f in fields]
    keys = [f"{table.name}.{f.name}" for f in fields]
    data = payload.get("data", [])
    rows = [
        [None if row.get(key) is None else str(row.get(key)) for key in keys]
        for row in data
    ]
    # Defensive: matches Cube's documented `total: true` shape (a top-level
    # `total` sibling of `data`), but no fixture of that response exists
    # anywhere in this repo yet — falls back to what was actually returned
    # rather than raising, if a future Cube version moves it.
    total = payload.get("total")
    if not isinstance(total, int):
        total = len(rows)
    return columns, rows, total
