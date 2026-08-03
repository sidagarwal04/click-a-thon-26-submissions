from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from uuid import UUID

import pytest

from zentra_domain_sequence import PreparedTable

NOW = datetime(2026, 8, 1, tzinfo=UTC)
TENANT_ID = UUID("20000000-0000-0000-0000-000000000002")
SEQUENCE_ID = UUID("61000000-0000-0000-0000-000000000001")
STEP_ID = UUID("61000000-0000-0000-0000-000000000002")
PREPARED_TABLE_ID = UUID("61000000-0000-0000-0000-000000000003")


def prepared_table_factory(**overrides: object) -> PreparedTable:
    fields: dict[str, object] = {
        "prepared_table_id": PREPARED_TABLE_ID,
        "tenant_id": TENANT_ID,
        "sequence_id": SEQUENCE_ID,
        "step_id": STEP_ID,
        "parent_table_reference": None,
        "row_count": 10,
        "columns": ("email", "amount"),
        "created_at": NOW,
    }
    fields.update(overrides)
    return PreparedTable(**fields)  # type: ignore[arg-type]


def test_prepared_table_is_an_immutable_value_record() -> None:
    table = prepared_table_factory()
    with pytest.raises(dataclasses.FrozenInstanceError):
        table.row_count = 99  # type: ignore[misc]


def test_prepared_table_produced_from_a_raw_table_has_no_parent_reference() -> None:
    table = prepared_table_factory(parent_table_reference=None)
    assert table.parent_table_reference is None
