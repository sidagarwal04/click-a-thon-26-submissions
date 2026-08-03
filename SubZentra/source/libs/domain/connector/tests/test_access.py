"""Tests for CatalogAccessOverride / AccessOverrides."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from zentra_domain_connector import (
    AccessOverrides,
    CatalogAccessOverride,
    CatalogVersion,
    SourceField,
    SourceTable,
    TypeFamily,
)

DATA_SOURCE_ID = UUID("70000000-0000-0000-0000-000000000001")
TENANT_ID = UUID("70000000-0000-0000-0000-000000000002")
DECIDED_BY = UUID("70000000-0000-0000-0000-000000000003")
NOW = datetime(2026, 8, 1, tzinfo=UTC)


def override(
    *,
    table_name: str,
    field_name: str | None,
    agent_visible: bool,
    decided_at: datetime = NOW,
) -> CatalogAccessOverride:
    return CatalogAccessOverride(
        override_id=UUID(int=hash((table_name, field_name, decided_at)) & (2**128 - 1)),
        tenant_id=TENANT_ID,
        data_source_id=DATA_SOURCE_ID,
        table_name=table_name,
        field_name=field_name,
        agent_visible=agent_visible,
        decided_by=DECIDED_BY,
        decided_at=decided_at,
    )


def field(name: str, position: int) -> SourceField:
    return SourceField(
        field_id=UUID(int=position + 1),
        table_id=UUID(int=1),
        name=name,
        declared_type="String",
        family=TypeFamily.STRING,
        normalised_type="string",
        nullable=True,
        position=position,
    )


def table(name: str, fields: tuple[SourceField, ...]) -> SourceTable:
    return SourceTable(table_id=UUID(int=1), name=name, database="db", fields=fields)


def version(tables: tuple[SourceTable, ...]) -> CatalogVersion:
    return CatalogVersion(
        catalog_version_id=UUID(int=1),
        data_source_id=DATA_SOURCE_ID,
        tenant_id=TENANT_ID,
        harvest_run_id=UUID(int=1),
        created_at=NOW,
        tables=tables,
    )


def test_absent_override_means_visible() -> None:
    overrides = AccessOverrides.build(DATA_SOURCE_ID, ())
    assert overrides.is_table_visible("orders")
    assert overrides.is_field_visible("orders", "customer_email")


def test_table_override_hides_the_whole_table() -> None:
    overrides = AccessOverrides.build(
        DATA_SOURCE_ID,
        (override(table_name="orders", field_name=None, agent_visible=False),),
    )
    assert not overrides.is_table_visible("orders")
    assert not overrides.is_field_visible("orders", "customer_email")
    assert overrides.is_table_visible("customers")


def test_field_override_hides_only_that_field() -> None:
    overrides = AccessOverrides.build(
        DATA_SOURCE_ID,
        (
            override(
                table_name="customers", field_name="email", agent_visible=False
            ),
        ),
    )
    assert overrides.is_table_visible("customers")
    assert not overrides.is_field_visible("customers", "email")
    assert overrides.is_field_visible("customers", "name")


def test_table_override_wins_over_a_stale_field_override() -> None:
    """A field re-enabled before its table was hidden must not reopen it.

    Regression for exactly the scenario `is_field_visible` guards against:
    hiding the table must not be one column short of hiding the table.
    """
    overrides = AccessOverrides.build(
        DATA_SOURCE_ID,
        (
            override(table_name="orders", field_name="total", agent_visible=True),
            override(table_name="orders", field_name=None, agent_visible=False),
        ),
    )
    assert not overrides.is_field_visible("orders", "total")


def test_latest_decision_wins_when_overrides_repeat() -> None:
    overrides = AccessOverrides.build(
        DATA_SOURCE_ID,
        (
            override(
                table_name="orders",
                field_name=None,
                agent_visible=False,
                decided_at=datetime(2026, 1, 1, tzinfo=UTC),
            ),
            override(
                table_name="orders",
                field_name=None,
                agent_visible=True,
                decided_at=datetime(2026, 2, 1, tzinfo=UTC),
            ),
        ),
    )
    assert overrides.is_table_visible("orders")


def test_apply_drops_hidden_tables_and_fields_from_the_version() -> None:
    catalog = version(
        (
            table("orders", (field("id", 0), field("total", 1))),
            table("customers", (field("id", 0), field("email", 1))),
        )
    )
    overrides = AccessOverrides.build(
        DATA_SOURCE_ID,
        (
            override(table_name="orders", field_name=None, agent_visible=False),
            override(
                table_name="customers", field_name="email", agent_visible=False
            ),
        ),
    )

    filtered = overrides.apply(catalog)

    assert filtered.table_names() == {"customers"}
    remaining = filtered.tables[0]
    assert [f.name for f in remaining.fields] == ["id"]
    # Identity fields untouched.
    assert filtered.catalog_version_id == catalog.catalog_version_id
    assert filtered.data_source_id == catalog.data_source_id


def test_apply_is_a_no_op_with_no_overrides() -> None:
    catalog = version((table("orders", (field("id", 0),)),))
    overrides = AccessOverrides.build(DATA_SOURCE_ID, ())

    filtered = overrides.apply(catalog)

    assert filtered.table_names() == catalog.table_names()
    assert [f.name for f in filtered.tables[0].fields] == ["id"]
