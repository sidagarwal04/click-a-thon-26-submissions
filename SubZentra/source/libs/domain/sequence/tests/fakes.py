"""In-memory SequenceExecutionPort for tests — no chDB, no Lambda, no DB.

Satisfies SequenceExecutionPort by shape, exactly as the real chDB adapter
will (ticket #51). Tenant scoping is enforced inside the fake itself, not
trusted from the caller, so a test which forgot to filter still cannot read
across tenants.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from zentra_domain_agent_execution import (
    SequenceExecutionFailureReason,
    SequenceStepExecutionFailure,
    SequenceStepExecutionRequest,
    SequenceStepExecutionResult,
    SequenceTableReference,
)

from zentra_domain_sequence import (
    SequenceOperationValidationError,
    UnknownSequenceOperationError,
    build_sequence_operation,
)
from zentra_domain_sequence.catalog import (
    CastTypeParameters,
    DedupeParameters,
    DropNullsParameters,
    FilterRowsParameters,
    RenameColumnParameters,
)

Row = dict[str, object]


@dataclass
class _TableSnapshot:
    rows: list[Row]
    columns: tuple[str, ...]


class FakeSequenceExecutionPort:
    """An in-memory stand-in for the real chDB-backed SequenceExecutionPort."""

    def __init__(self) -> None:
        self._tables: dict[tuple[UUID, UUID], _TableSnapshot] = {}

    def seed_table(
        self,
        *,
        tenant_id: UUID,
        reference_id: UUID,
        kind: str,
        rows: list[Row],
        columns: tuple[str, ...],
    ) -> None:
        # kind is caller-facing only; the lookup key is (tenant_id, reference_id).
        _ = kind
        self._tables[(tenant_id, reference_id)] = _TableSnapshot(
            rows=[dict(row) for row in rows], columns=columns
        )

    async def apply_operation(
        self, request: SequenceStepExecutionRequest
    ) -> SequenceStepExecutionResult | SequenceStepExecutionFailure:
        snapshot = self._tables.get(
            (request.tenant_id, request.input_table.reference_id)
        )
        if snapshot is None:
            return SequenceStepExecutionFailure(
                request=request,
                reason=SequenceExecutionFailureReason.UNKNOWN_TABLE,
                detail=f"No table {request.input_table.reference_id} for this Tenant",
            )

        try:
            operation = build_sequence_operation(
                request.operation_kind, request.operation_parameters
            )
        except (
            UnknownSequenceOperationError,
            SequenceOperationValidationError,
        ) as error:
            return SequenceStepExecutionFailure(
                request=request,
                reason=SequenceExecutionFailureReason.CATALOG_VIOLATION,
                detail=str(error),
            )

        try:
            rows, columns = self._execute(operation, snapshot)
        except _DataIncompatibleError as error:
            return SequenceStepExecutionFailure(
                request=request,
                reason=SequenceExecutionFailureReason.DATA_INCOMPATIBLE,
                detail=str(error),
            )

        output_id = uuid4()
        self._tables[(request.tenant_id, output_id)] = _TableSnapshot(
            rows=rows, columns=columns
        )
        return SequenceStepExecutionResult(
            request=request,
            output_table=SequenceTableReference(
                tenant_id=request.tenant_id, reference_id=output_id, kind="prepared"
            ),
            row_count=len(rows),
            columns=columns,
        )

    def _execute(
        self, operation: object, snapshot: _TableSnapshot
    ) -> tuple[list[Row], tuple[str, ...]]:
        if isinstance(operation, DropNullsParameters):
            strategy = all if operation.strategy == "all" else any
            rows = [
                row
                for row in snapshot.rows
                if not strategy(row.get(column) is None for column in operation.columns)
            ]
            return rows, snapshot.columns

        if isinstance(operation, DedupeParameters):
            columns = operation.columns or snapshot.columns
            seen: set[tuple[object, ...]] = set()
            rows = []
            for row in snapshot.rows:
                key = tuple(row.get(column) for column in columns)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
            return rows, snapshot.columns

        if isinstance(operation, FilterRowsParameters):
            rows = [
                row
                for row in snapshot.rows
                if _matches_filter(
                    row.get(operation.column), operation.operator, operation.value
                )
            ]
            return rows, snapshot.columns

        if isinstance(operation, RenameColumnParameters):
            if operation.from_name not in snapshot.columns:
                raise _DataIncompatibleError(
                    f"column {operation.from_name!r} does not exist"
                )
            rows = [
                {
                    (operation.to_name if key == operation.from_name else key): value
                    for key, value in row.items()
                }
                for row in snapshot.rows
            ]
            columns = tuple(
                operation.to_name if column == operation.from_name else column
                for column in snapshot.columns
            )
            return rows, columns

        if isinstance(operation, CastTypeParameters):
            if operation.column not in snapshot.columns:
                raise _DataIncompatibleError(
                    f"column {operation.column!r} does not exist"
                )
            caster = _CASTERS.get(operation.target_type)
            if caster is None:
                raise _DataIncompatibleError(
                    f"unsupported target type {operation.target_type!r}"
                )
            rows = []
            for row in snapshot.rows:
                value = row.get(operation.column)
                try:
                    new_value = None if value is None else caster(value)
                except (TypeError, ValueError) as error:
                    raise _DataIncompatibleError(
                        f"cannot cast {value!r} to {operation.target_type!r}"
                    ) from error
                rows.append({**row, operation.column: new_value})
            return rows, snapshot.columns

        raise _DataIncompatibleError(f"unsupported operation {operation!r}")


class _DataIncompatibleError(RuntimeError):
    """The operation is catalog-valid but cannot run against this table's data."""


_CASTERS = {
    "int": int,
    "float": float,
    "str": str,
}


def _matches_filter(value: object, operator: str, target: object) -> bool:
    if operator == "is_null":
        return value is None
    if operator == "is_not_null":
        return value is not None
    if operator == "eq":
        return value == target
    if operator == "ne":
        return value != target
    if operator == "gt":
        return value is not None and value > target
    if operator == "gte":
        return value is not None and value >= target
    if operator == "lt":
        return value is not None and value < target
    if operator == "lte":
        return value is not None and value <= target
    raise _DataIncompatibleError(f"unsupported filter operator {operator!r}")
