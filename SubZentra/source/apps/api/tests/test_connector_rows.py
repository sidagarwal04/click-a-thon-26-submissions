"""Pure unit tests for the row-browse query builder and payload parser.

No FastAPI/TestClient involved — `connector_rows.py` has no dependency on
either, which is the point of keeping it separate from the route module.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from zentra_domain_connector import CatalogVersion, SourceField, SourceTable

from zentra_api.connector_rows import (
    ROW_PAGE_SIZE,
    TableNotInCatalogError,
    build_rows_query,
    find_table,
    parse_rows_payload,
)


def _field(name: str, *, position: int) -> SourceField:
    return SourceField(
        field_id=uuid4(),
        table_id=uuid4(),
        name=name,
        declared_type="string",
        family="string",
        normalised_type="string",
        nullable=True,
        position=position,
    )


def _table(name: str, fields: tuple[SourceField, ...]) -> SourceTable:
    return SourceTable(table_id=uuid4(), name=name, database="db", fields=fields)


def _version(*tables: SourceTable) -> CatalogVersion:
    return CatalogVersion(
        catalog_version_id=uuid4(),
        data_source_id=uuid4(),
        tenant_id=uuid4(),
        harvest_run_id=uuid4(),
        created_at=datetime.now(UTC),
        tables=tuple(tables),
    )


def test_find_table_returns_the_matching_table() -> None:
    orders = _table("orders", ())
    version = _version(orders, _table("customers", ()))

    assert find_table(version, "orders") is orders


def test_find_table_raises_for_an_unknown_name() -> None:
    version = _version(_table("orders", ()))

    with pytest.raises(TableNotInCatalogError):
        find_table(version, "missing")


def test_build_rows_query_orders_dimensions_by_position_not_declaration() -> None:
    # Declared out of position order on purpose.
    status_field = _field("status", position=1)
    id_field = _field("id", position=0)
    table = _table("orders", (status_field, id_field))

    query = build_rows_query(table, page=1)

    assert query["dimensions"] == ["orders.id", "orders.status"]
    assert "measures" not in query
    assert query["total"] is True


@pytest.mark.parametrize(
    ("page", "expected_offset"),
    [(1, 0), (2, ROW_PAGE_SIZE), (3, ROW_PAGE_SIZE * 2)],
)
def test_build_rows_query_offset_matches_page(page: int, expected_offset: int) -> None:
    table = _table("orders", (_field("id", position=0),))

    query = build_rows_query(table, page=page)

    assert query["limit"] == ROW_PAGE_SIZE
    assert query["offset"] == expected_offset


def test_parse_rows_payload_happy_path() -> None:
    table = _table(
        "orders",
        (_field("id", position=0), _field("status", position=1)),
    )
    payload = {
        "data": [
            {"orders.id": "1", "orders.status": "paid"},
            {"orders.id": "2", "orders.status": "pending"},
        ],
        "total": 284391,
    }

    columns, rows, total = parse_rows_payload(payload, table)

    assert columns == ["id", "status"]
    assert rows == [["1", "paid"], ["2", "pending"]]
    assert total == 284391


def test_parse_rows_payload_falls_back_to_row_count_when_total_missing() -> None:
    table = _table("orders", (_field("id", position=0),))
    payload = {"data": [{"orders.id": "1"}, {"orders.id": "2"}]}

    _, rows, total = parse_rows_payload(payload, table)

    assert total == len(rows) == 2


def test_parse_rows_payload_preserves_none_rather_than_stringifying_it() -> None:
    table = _table("orders", (_field("id", position=0),))
    payload = {"data": [{"orders.id": None}]}

    _, rows, _ = parse_rows_payload(payload, table)

    assert rows == [[None]]


def test_parse_rows_payload_reads_a_field_missing_from_a_row_as_none() -> None:
    """Cube can omit an all-null column key from a given row entirely."""
    table = _table(
        "orders",
        (_field("id", position=0), _field("note", position=1)),
    )
    payload = {"data": [{"orders.id": "1"}]}

    _, rows, _ = parse_rows_payload(payload, table)

    assert rows == [["1", None]]
