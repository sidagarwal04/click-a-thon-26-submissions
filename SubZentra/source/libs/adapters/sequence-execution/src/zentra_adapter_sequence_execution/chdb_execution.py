"""The real SequenceExecutionPort, executing typed operations via chDB.

Persistence split: this adapter is responsible for the Prepared Table's
physical bytes (a Parquet file, addressed deterministically by tenant and
prepared-table id — never a separate location record to keep in sync). It
does not write Sequence/SequenceStep/PreparedTable/SequenceRun *rows* to
Postgres; that remains the caller's job, exactly as it already is for the
fake adapter (ticket #49) — both implementations of the same port return a
result, they don't reach into the aggregate's own repository.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

import chdb
from zentra_domain_agent_execution import (
    SequenceExecutionFailureReason,
    SequenceStepExecutionFailure,
    SequenceStepExecutionRequest,
    SequenceStepExecutionResult,
    SequenceTableReference,
)
from zentra_domain_sequence import (
    CastTypeParameters,
    DedupeParameters,
    DropNullsParameters,
    FilterRowsParameters,
    RawTableReference,
    RenameColumnParameters,
    SequenceOperation,
    SequenceOperationValidationError,
    UnknownSequenceOperationError,
    build_sequence_operation,
)

from .raw_table import ConnectorClickHouseConnection, resolve_raw_table_sql

_CHDB_CAST_TYPES = {
    "int": "Int64",
    "float": "Float64",
    "str": "String",
}


class RawTableLookup(Protocol):
    async def resolve(
        self, *, tenant_id: UUID, sequence_id: UUID
    ) -> RawTableReference | None: ...


def _quote_ident(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


def _sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int | float):
        return repr(value)
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"


_FILTER_OPERATORS = {
    "eq": "=",
    "ne": "!=",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
}


def _select_sql(operation: SequenceOperation, from_sql: str) -> str:
    if isinstance(operation, DropNullsParameters):
        joiner = " AND " if operation.strategy == "any" else " OR "
        condition = joiner.join(
            f"{_quote_ident(column)} IS NOT NULL" for column in operation.columns
        )
        return f"SELECT * FROM {from_sql} WHERE {condition}"

    if isinstance(operation, DedupeParameters):
        if not operation.columns:
            return f"SELECT DISTINCT * FROM {from_sql}"
        columns_sql = ", ".join(_quote_ident(c) for c in operation.columns)
        return f"SELECT * FROM {from_sql} LIMIT 1 BY {columns_sql}"

    if isinstance(operation, FilterRowsParameters):
        column = _quote_ident(operation.column)
        if operation.operator == "is_null":
            condition = f"{column} IS NULL"
        elif operation.operator == "is_not_null":
            condition = f"{column} IS NOT NULL"
        else:
            sql_operator = _FILTER_OPERATORS[operation.operator]
            condition = f"{column} {sql_operator} {_sql_literal(operation.value)}"
        return f"SELECT * FROM {from_sql} WHERE {condition}"

    if isinstance(operation, RenameColumnParameters):
        from_name = _quote_ident(operation.from_name)
        to_name = _quote_ident(operation.to_name)
        return (
            f"SELECT * EXCEPT ({from_name}), {from_name} AS {to_name} FROM {from_sql}"
        )

    if isinstance(operation, CastTypeParameters):
        column = _quote_ident(operation.column)
        cast_type = _CHDB_CAST_TYPES[operation.target_type]
        # accurateCast, not CAST(... AS Nullable(...)): a plain CAST to a
        # Nullable target silently returns NULL on an unparsable value
        # instead of failing, which would hide a data-incompatible operation
        # as a quiet data loss rather than the typed failure it must be.
        return (
            f"SELECT * EXCEPT ({column}), "
            f"accurateCast({column}, '{cast_type}') AS {column} FROM {from_sql}"
        )

    msg = f"Unsupported operation: {operation!r}"
    raise TypeError(msg)


class ChdbSequenceExecutionPort:
    def __init__(
        self,
        *,
        connector_clickhouse: ConnectorClickHouseConnection,
        storage_root: Path,
        sequence_lookup: RawTableLookup | None,
    ) -> None:
        self._connector_clickhouse = connector_clickhouse
        self._storage_root = storage_root
        self._sequence_lookup = sequence_lookup

    def _prepared_table_path(self, *, tenant_id: UUID, prepared_table_id: UUID) -> Path:
        return self._storage_root / str(tenant_id) / f"{prepared_table_id}.parquet"

    async def _resolve_from_sql(
        self, request: SequenceStepExecutionRequest
    ) -> str | None:
        if request.input_table.kind == "raw":
            if self._sequence_lookup is None:
                return None
            raw_table = await self._sequence_lookup.resolve(
                tenant_id=request.tenant_id, sequence_id=request.sequence_id
            )
            if raw_table is None:
                return None
            return resolve_raw_table_sql(
                raw_table, connector_clickhouse=self._connector_clickhouse
            )

        path = self._prepared_table_path(
            tenant_id=request.tenant_id,
            prepared_table_id=request.input_table.reference_id,
        )
        if not path.exists():
            return None
        return f"file('{path}', 'Parquet')"

    async def apply_operation(
        self, request: SequenceStepExecutionRequest
    ) -> SequenceStepExecutionResult | SequenceStepExecutionFailure:
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

        from_sql = await self._resolve_from_sql(request)
        if from_sql is None:
            return SequenceStepExecutionFailure(
                request=request,
                reason=SequenceExecutionFailureReason.UNKNOWN_TABLE,
                detail=f"No table {request.input_table.reference_id} for this Tenant",
            )

        output_id = uuid4()
        output_path = self._prepared_table_path(
            tenant_id=request.tenant_id, prepared_table_id=output_id
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # _select_sql itself can fail — e.g. a catalog-valid but
            # chdb-unsupported cast target_type — and that is exactly as
            # much a data-incompatible operation as a chDB query failing,
            # so it shares this try block rather than raising uncaught.
            select_sql = _select_sql(operation, from_sql)
            chdb.query(
                f"INSERT INTO FUNCTION file('{output_path}', 'Parquet') {select_sql}"
            )
            described = chdb.query(
                f"SELECT count() AS row_count FROM file('{output_path}', 'Parquet')",
                "JSON",
            )
            columns_described = chdb.query(
                f"SELECT * FROM file('{output_path}', 'Parquet') LIMIT 0", "JSON"
            )
        except Exception as error:  # chdb raises plain Exception on SQL errors
            output_path.unlink(missing_ok=True)
            return SequenceStepExecutionFailure(
                request=request,
                reason=SequenceExecutionFailureReason.DATA_INCOMPATIBLE,
                detail=str(error),
            )

        row_count = json.loads(str(described))["data"][0]["row_count"]
        columns = tuple(
            column["name"] for column in json.loads(str(columns_described))["meta"]
        )

        return SequenceStepExecutionResult(
            request=request,
            output_table=SequenceTableReference(
                tenant_id=request.tenant_id, reference_id=output_id, kind="prepared"
            ),
            row_count=row_count,
            columns=columns,
        )
