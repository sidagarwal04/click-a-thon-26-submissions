"""The production RawTableLookup: resolves a Sequence's Raw Table reference
by reading it from Postgres. Read-only — this never writes anything."""

from __future__ import annotations

from uuid import UUID

from zentra_adapter_postgres import PostgresSequenceUnitOfWorkFactory
from zentra_domain_sequence import RawTableReference


class PostgresRawTableLookup:
    def __init__(self, unit_of_work_factory: PostgresSequenceUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def resolve(
        self, *, tenant_id: UUID, sequence_id: UUID
    ) -> RawTableReference | None:
        async with self._unit_of_work_factory(
            tenant_id, UUID(int=0), UUID(int=0)
        ) as unit_of_work:
            sequence = await unit_of_work.sequences.get_sequence(sequence_id)
        return sequence.raw_table_reference if sequence is not None else None
