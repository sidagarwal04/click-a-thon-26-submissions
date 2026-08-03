from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncConnection
from zentra_domain_agent_execution import SequenceTableReference
from zentra_domain_sequence import (
    ConnectorSourceTableReference,
    DatasetTableVersionReference,
    PreparedTable,
    RawTableReference,
    Sequence,
    SequenceOperation,
    SequenceRun,
    SequenceRunFailed,
    SequenceRunOutcome,
    SequenceRunSucceeded,
    SequenceStep,
    build_sequence_operation,
)

from .database import Database, set_tenant_context
from .schema import (
    prepared_tables,
    sequence_final_tables,
    sequence_runs,
    sequence_steps,
    sequences,
)


def _raw_table_to_row(reference: RawTableReference) -> tuple[str, dict[str, Any]]:
    if isinstance(reference, ConnectorSourceTableReference):
        return reference.kind, {
            "catalog_version_id": reference.catalog_version_id,
            "source_table_name": reference.source_table_name,
        }
    return reference.kind, {
        "storage_locator": reference.storage_locator,
        "file_format": reference.file_format,
    }


def _raw_table_from_row(kind: str, payload: dict[str, Any]) -> RawTableReference:
    if kind == "connector_source_table":
        return ConnectorSourceTableReference(**payload)
    return DatasetTableVersionReference(**payload)


def _operation_to_row(operation: SequenceOperation) -> tuple[str, dict[str, Any]]:
    payload = operation.model_dump(mode="json", exclude={"kind"})
    return operation.kind, payload


def _run_outcome_to_row(outcome: SequenceRunOutcome) -> dict[str, Any]:
    if isinstance(outcome, SequenceRunSucceeded):
        return {
            "outcome_kind": "succeeded",
            "produced_table_id": outcome.produced_table_id,
            "failure_reason": None,
            "failure_detail": None,
        }
    return {
        "outcome_kind": "failed",
        "produced_table_id": None,
        "failure_reason": outcome.reason.value,
        "failure_detail": outcome.detail,
    }


def _run_outcome_from_row(row: Any) -> SequenceRunOutcome:
    if row["outcome_kind"] == "succeeded":
        return SequenceRunSucceeded(produced_table_id=row["produced_table_id"])
    return SequenceRunFailed(reason=row["failure_reason"], detail=row["failure_detail"])


def _sequence_from_row(row: Any) -> Sequence:
    value = row._mapping
    return Sequence(
        sequence_id=value["sequence_id"],
        tenant_id=value["tenant_id"],
        dataset_workspace_id=value["dataset_workspace_id"],
        raw_table_reference=_raw_table_from_row(
            value["raw_table_kind"], value["raw_table_payload"]
        ),
        created_at=value["created_at"],
        updated_at=value["updated_at"],
    )


def _step_from_row(row: Any) -> SequenceStep:
    value = row._mapping
    input_reference = None
    if value["input_reference_id"] is not None:
        input_reference = SequenceTableReference(
            tenant_id=value["tenant_id"],
            reference_id=value["input_reference_id"],
            kind="prepared",
        )
    return SequenceStep(
        step_id=value["step_id"],
        sequence_id=value["sequence_id"],
        tenant_id=value["tenant_id"],
        operation=build_sequence_operation(
            value["operation_kind"], value["operation_parameters"]
        ),
        input_reference=input_reference,
        produced_table_id=value["produced_table_id"],
        created_at=value["created_at"],
    )


def _prepared_table_from_row(row: Any) -> PreparedTable:
    value = row._mapping
    parent_reference = None
    if value["parent_prepared_table_id"] is not None:
        parent_reference = SequenceTableReference(
            tenant_id=value["tenant_id"],
            reference_id=value["parent_prepared_table_id"],
            kind="prepared",
        )
    return PreparedTable(
        prepared_table_id=value["prepared_table_id"],
        tenant_id=value["tenant_id"],
        sequence_id=value["sequence_id"],
        step_id=value["step_id"],
        parent_table_reference=parent_reference,
        row_count=value["row_count"],
        columns=tuple(value["columns"]),
        created_at=value["created_at"],
    )


def _run_from_row(row: Any) -> SequenceRun:
    value = row._mapping
    return SequenceRun(
        run_id=value["run_id"],
        sequence_id=value["sequence_id"],
        tenant_id=value["tenant_id"],
        step_id=value["step_id"],
        outcome=_run_outcome_from_row(value),
        attempted_at=value["attempted_at"],
    )


class PostgresSequenceRepository:
    """Persists the Sequence aggregate. Every Prepared Table is written once,
    on a successful Sequence Run, and never updated afterward — there is no
    method here that mutates one once it exists."""

    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add_sequence(self, sequence: Sequence) -> None:
        raw_table_kind, raw_table_payload = _raw_table_to_row(
            sequence.raw_table_reference
        )
        await self._connection.execute(
            insert(sequences).values(
                sequence_id=sequence.sequence_id,
                tenant_id=sequence.tenant_id,
                dataset_workspace_id=sequence.dataset_workspace_id,
                raw_table_kind=raw_table_kind,
                raw_table_payload=raw_table_payload,
                created_at=sequence.created_at,
                updated_at=sequence.updated_at,
            )
        )

    async def get_sequence(
        self, sequence_id: UUID, *, for_update: bool = False
    ) -> Sequence | None:
        statement = select(sequences).where(sequences.c.sequence_id == sequence_id)
        if for_update:
            statement = statement.with_for_update()
        row = (await self._connection.execute(statement)).first()
        if row is None:
            return None
        sequence = _sequence_from_row(row)

        step_rows = (
            await self._connection.execute(
                select(sequence_steps)
                .where(sequence_steps.c.sequence_id == sequence_id)
                .order_by(sequence_steps.c.created_at)
            )
        ).all()
        table_rows = (
            await self._connection.execute(
                select(prepared_tables)
                .where(prepared_tables.c.sequence_id == sequence_id)
                .order_by(prepared_tables.c.created_at)
            )
        ).all()
        run_rows = (
            await self._connection.execute(
                select(sequence_runs)
                .where(sequence_runs.c.sequence_id == sequence_id)
                .order_by(sequence_runs.c.attempted_at)
            )
        ).all()
        final_rows = (
            await self._connection.execute(
                select(sequence_final_tables.c.prepared_table_id).where(
                    sequence_final_tables.c.sequence_id == sequence_id
                )
            )
        ).all()

        sequence.steps = tuple(_step_from_row(row) for row in step_rows)
        sequence.prepared_tables = tuple(
            _prepared_table_from_row(row) for row in table_rows
        )
        sequence.runs = tuple(_run_from_row(row) for row in run_rows)
        sequence.final_table_ids = frozenset(
            row.prepared_table_id for row in final_rows
        )
        return sequence

    async def add_step(self, step: SequenceStep, table: PreparedTable) -> None:
        operation_kind, operation_parameters = _operation_to_row(step.operation)
        await self._connection.execute(
            insert(sequence_steps).values(
                step_id=step.step_id,
                sequence_id=step.sequence_id,
                tenant_id=step.tenant_id,
                operation_kind=operation_kind,
                operation_parameters=operation_parameters,
                input_reference_id=(
                    step.input_reference.reference_id
                    if step.input_reference is not None
                    else None
                ),
                produced_table_id=step.produced_table_id,
                created_at=step.created_at,
            )
        )
        await self._connection.execute(
            insert(prepared_tables).values(
                prepared_table_id=table.prepared_table_id,
                tenant_id=table.tenant_id,
                sequence_id=table.sequence_id,
                step_id=table.step_id,
                parent_prepared_table_id=(
                    table.parent_table_reference.reference_id
                    if table.parent_table_reference is not None
                    else None
                ),
                row_count=table.row_count,
                columns=list(table.columns),
                created_at=table.created_at,
            )
        )

    async def add_run(self, run: SequenceRun) -> None:
        await self._connection.execute(
            insert(sequence_runs).values(
                run_id=run.run_id,
                sequence_id=run.sequence_id,
                tenant_id=run.tenant_id,
                step_id=run.step_id,
                attempted_at=run.attempted_at,
                **_run_outcome_to_row(run.outcome),
            )
        )

    async def mark_final(
        self,
        *,
        sequence_id: UUID,
        prepared_table_id: UUID,
        tenant_id: UUID,
        marked_at: datetime,
    ) -> None:
        await self._connection.execute(
            insert(sequence_final_tables).values(
                sequence_id=sequence_id,
                prepared_table_id=prepared_table_id,
                tenant_id=tenant_id,
                marked_at=marked_at,
            )
        )

    async def unmark_final(self, *, sequence_id: UUID, prepared_table_id: UUID) -> None:
        await self._connection.execute(
            sequence_final_tables.delete().where(
                sequence_final_tables.c.sequence_id == sequence_id,
                sequence_final_tables.c.prepared_table_id == prepared_table_id,
            )
        )


class PostgresSequenceUnitOfWork:
    def __init__(self, connection: AsyncConnection) -> None:
        self.sequences = PostgresSequenceRepository(connection)
        self.should_commit = False

    async def commit(self) -> None:
        self.should_commit = True


class PostgresSequenceUnitOfWorkFactory:
    def __init__(self, database: Database) -> None:
        self._database = database

    @asynccontextmanager
    async def __call__(
        self,
        tenant_id: UUID,
        trace_id: UUID,
        span_id: UUID,
    ) -> AsyncIterator[PostgresSequenceUnitOfWork]:
        del trace_id, span_id
        async with self._database.engine.connect() as connection:
            transaction = await connection.begin()
            await set_tenant_context(connection, tenant_id)
            unit_of_work = PostgresSequenceUnitOfWork(connection)
            try:
                yield unit_of_work
            except Exception:
                await transaction.rollback()
                raise
            else:
                if unit_of_work.should_commit:
                    await transaction.commit()
                else:
                    await transaction.rollback()
