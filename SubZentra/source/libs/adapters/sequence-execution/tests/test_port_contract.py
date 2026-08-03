"""Proves ChdbSequenceExecutionPort satisfies the exact same contract the
fake adapter does (libs/domain/sequence/tests/test_fake_execution_port.py),
via the one shared suite both implementations run."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from zentra_domain_agent_execution import SequenceTableReference
from zentra_domain_sequence import DatasetTableVersionReference
from zentra_domain_sequence.testing import assert_port_satisfies_contract

from zentra_adapter_sequence_execution.chdb_execution import ChdbSequenceExecutionPort
from zentra_adapter_sequence_execution.raw_table import ConnectorClickHouseConnection

TENANT_ID = UUID("20000000-0000-0000-0000-000000000002")
SEQUENCE_ID = UUID("66000000-0000-0000-0000-000000000001")

CONNECTION = ConnectorClickHouseConnection(
    host="localhost", port=9000, user="default", password=""
)


class _SingleFixtureLookup:
    """Every "raw" input resolves to whichever fixture file was written for
    the current assertion — the real adapter has no in-memory raw-table
    registry, so each seed call in the contract suite gets its own file."""

    def __init__(self) -> None:
        self.reference: DatasetTableVersionReference | None = None

    async def resolve(self, *, tenant_id, sequence_id):
        del tenant_id, sequence_id
        return self.reference


def _write_csv(path: Path, rows: list[dict], columns: tuple[str, ...]) -> None:
    lines = [",".join(columns)]
    for row in rows:
        lines.append(
            ",".join("" if row.get(c) is None else str(row[c]) for c in columns)
        )
    path.write_text("\n".join(lines) + "\n")


@pytest.mark.asyncio
async def test_chdb_port_satisfies_the_shared_contract_suite(tmp_path: Path) -> None:
    lookup = _SingleFixtureLookup()
    port = ChdbSequenceExecutionPort(
        connector_clickhouse=CONNECTION,
        storage_root=tmp_path,
        sequence_lookup=lookup,
    )

    fixture_counter = iter(range(1_000_000))

    def seed_raw_table(*, rows: list[dict], columns: tuple[str, ...]):
        fixture_path = tmp_path / f"raw_{next(fixture_counter)}.csv"
        _write_csv(fixture_path, rows, columns)
        lookup.reference = DatasetTableVersionReference(
            storage_locator=str(fixture_path), file_format="csv"
        )
        return SequenceTableReference(
            tenant_id=TENANT_ID, reference_id=uuid4(), kind="raw"
        )

    await assert_port_satisfies_contract(
        apply_operation=port.apply_operation,
        seed_raw_table=seed_raw_table,
        tenant_id=TENANT_ID,
        sequence_id=SEQUENCE_ID,
    )
