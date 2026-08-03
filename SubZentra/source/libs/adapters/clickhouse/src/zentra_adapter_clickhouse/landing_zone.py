"""Landing uploaded CSV and Parquet files as queryable ClickHouse tables.

This is ZentraOS-owned storage holding raw customer data by design, and it is
deliberately a *different database* from the audit ledger in ``audit.py``. The
ledger's guarantee is that it contains no raw customer values; putting uploads
beside it would make that guarantee a matter of which table you happened to read.

Once landed, an upload is an ordinary Data Source. Everything downstream —
harvest, profiling, relation inference — goes through ``ClickHouseSourceConnector``
exactly as it does for a customer's own warehouse.
"""

from __future__ import annotations

import asyncio
import csv
import io
from collections.abc import AsyncIterator, Sequence
from uuid import UUID

import clickhouse_connect
import pyarrow as pa
import pyarrow.parquet as pq
from zentra_application_connector import (
    LandedTable,
    SourceCredentials,
    SourceFieldDescriptor,
    UploadRejectedError,
)
from zentra_domain_connector import UploadFormat

from .sql import qualify, quote_identifier

#: The database uploads land in. Never the audit ledger's database.
UPLOAD_DATABASE = "zentra_uploads"

#: How many rows are read to guess a column's type. Enough to see past a header
#: and a few blanks; small enough that a preview stays instant.
TYPE_INFERENCE_ROWS = 200


def _sanitise_identifier(name: str) -> str:
    """Reduce a column name from a file to something safely quotable.

    Files carry column names that ClickHouse cannot hold — spaces, punctuation,
    leading digits. Replacing rather than rejecting means a spreadsheet exported
    from a finance team is usable without them having to rename anything.
    """
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in name.strip())
    cleaned = cleaned.strip("_") or "column"
    if cleaned[0].isdigit():
        cleaned = f"c_{cleaned}"
    return cleaned[:64]


def _infer_type(values: Sequence[str]) -> str:
    """Guess a column's type from its observed values.

    Every type is Nullable because a file has no schema promising otherwise, and
    a single blank cell in row 40,000 would otherwise fail the whole load after
    the user already confirmed the preview.

    Deliberately conservative: anything not clearly numeric or a date is a
    String. A wrong String costs a reviewer one correction in the preview; a
    wrongly-guessed Int64 costs them a failed load and a confusing error.
    """
    seen = [v for v in values if v not in ("", None)]
    if not seen:
        return "Nullable(String)"

    def all_match(predicate) -> bool:
        return all(predicate(v) for v in seen)

    if all_match(lambda v: v.lstrip("-").isdigit()):
        return "Nullable(Int64)"
    try:
        if all_match(lambda v: float(v) == float(v)):
            return "Nullable(Float64)"
    except (TypeError, ValueError):
        pass
    if all_match(lambda v: len(v) == 10 and v[4] == "-" and v[7] == "-"):
        return "Nullable(Date)"
    return "Nullable(String)"


def _arrow_to_clickhouse(arrow_type) -> str:
    """Map an Arrow type to the ClickHouse type that will hold it.

    Everything is Nullable for the same reason CSV inference makes it so: a file
    is not a schema contract, and a single null in a column the writer marked
    non-nullable would fail the load after the user already approved the preview.
    """
    if pa.types.is_boolean(arrow_type):
        return "Nullable(Bool)"
    if pa.types.is_integer(arrow_type):
        return "Nullable(Int64)"
    if pa.types.is_floating(arrow_type):
        return "Nullable(Float64)"
    if pa.types.is_decimal(arrow_type):
        return f"Nullable(Decimal({arrow_type.precision}, {arrow_type.scale}))"
    if pa.types.is_timestamp(arrow_type):
        return "Nullable(DateTime64(3))"
    if pa.types.is_date(arrow_type):
        return "Nullable(Date)"
    return "Nullable(String)"


class ClickHouseLandingZone:
    """A ``FileLandingZone`` backed by ZentraOS's own ClickHouse."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        secure: bool = True,
        database: str = UPLOAD_DATABASE,
    ) -> None:
        self._settings = {
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "secure": secure,
        }
        self._database = database

    def _client(self):
        return clickhouse_connect.get_client(
            **self._settings, database=self._database
        )

    def credentials_for(self, landed: LandedTable) -> SourceCredentials:
        """Credentials the source connector can use to read a landed table.

        The landing zone hands these out rather than the service constructing
        them, so that only one place knows where uploads live.
        """
        return SourceCredentials(
            host=str(self._settings["host"]),
            port=int(self._settings["port"]),  # type: ignore[arg-type]
            database=landed.database,
            username=str(self._settings["username"]),
            password=str(self._settings["password"]),
            secure=bool(self._settings["secure"]),
        )

    async def inspect(
        self,
        stream: AsyncIterator[bytes],
        *,
        upload_format: UploadFormat,
        preview_rows: int,
    ) -> tuple[Sequence[SourceFieldDescriptor], Sequence[tuple[str, ...]], int]:
        payload = await _collect(stream)
        if upload_format is UploadFormat.CSV:
            return await asyncio.to_thread(self._inspect_csv, payload, preview_rows)
        return await asyncio.to_thread(self._inspect_parquet, payload, preview_rows)

    def _inspect_csv(
        self, payload: bytes, preview_rows: int
    ) -> tuple[list[SourceFieldDescriptor], list[tuple[str, ...]], int]:
        try:
            text = payload.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise UploadRejectedError(
                "File is not valid UTF-8; re-export it with UTF-8 encoding"
            ) from exc

        reader = csv.reader(io.StringIO(text))
        try:
            header = next(reader)
        except StopIteration as exc:
            raise UploadRejectedError("File is empty") from exc

        width = len(header)
        rows: list[tuple[str, ...]] = []
        sample_columns: list[list[str]] = [[] for _ in header]
        total = 0
        for line_number, row in enumerate(reader, start=2):
            if len(row) != width:
                # Named with the line number, because "inconsistent row width"
                # without a location is not something a user can act on.
                raise UploadRejectedError(
                    f"Row has {len(row)} values but the header declares {width}",
                    row=line_number,
                )
            total += 1
            if len(rows) < preview_rows:
                rows.append(tuple(row))
            if total <= TYPE_INFERENCE_ROWS:
                for index, value in enumerate(row):
                    sample_columns[index].append(value)

        columns = [
            SourceFieldDescriptor(
                name=_sanitise_identifier(name),
                declared_type=_infer_type(sample_columns[index]),
                nullable=True,
                position=index,
            )
            for index, name in enumerate(header)
        ]
        return columns, rows, total

    def _inspect_parquet(
        self, payload: bytes, preview_rows: int
    ) -> tuple[list[SourceFieldDescriptor], list[tuple[str, ...]], int]:
        """Read a Parquet file's schema and first rows.

        Parquet carries its own schema, so unlike CSV nothing here is inferred —
        the declared types are read, not guessed. The same Arrow table is used
        to load the data in ``_insert_parquet``, so there is one Parquet
        implementation rather than two that could disagree about what a file
        contains.
        """
        table = self._read_parquet(payload)
        columns = [
            SourceFieldDescriptor(
                name=_sanitise_identifier(name),
                declared_type=_arrow_to_clickhouse(table.schema.field(index).type),
                nullable=table.schema.field(index).nullable,
                position=index,
            )
            for index, name in enumerate(table.schema.names)
        ]
        head = table.slice(0, preview_rows).to_pylist()
        rows = [
            tuple(
                "" if row[name] is None else str(row[name])
                for name in table.schema.names
            )
            for row in head
        ]
        return columns, rows, table.num_rows

    def _read_parquet(self, payload: bytes):
        try:
            return pq.read_table(pa.BufferReader(payload))
        except Exception as exc:  # noqa: BLE001 - arrow raises a wide family
            raise UploadRejectedError(
                f"File is not readable as Parquet: {exc}"
            ) from exc

    async def land(
        self,
        stream: AsyncIterator[bytes],
        *,
        tenant_id: UUID,
        upload_id: UUID,
        upload_format: UploadFormat,
        columns: Sequence[SourceFieldDescriptor],
    ) -> LandedTable:
        payload = await _collect(stream)
        table = f"upload_{tenant_id.hex[:12]}_{upload_id.hex[:12]}"
        await asyncio.to_thread(
            self._create_and_insert, table, columns, payload, upload_format
        )
        rows = await asyncio.to_thread(self._count_rows, table)
        return LandedTable(database=self._database, table=table, row_count=rows)

    def _create_and_insert(
        self,
        table: str,
        columns: Sequence[SourceFieldDescriptor],
        payload: bytes,
        upload_format: UploadFormat,
    ) -> None:
        column_ddl = ", ".join(
            f"{quote_identifier(c.name)} {c.declared_type}"
            for c in sorted(columns, key=lambda c: c.position)
        )
        client = self._client()
        try:
            client.command(
                f"CREATE DATABASE IF NOT EXISTS {quote_identifier(self._database)}"
            )
            # ORDER BY tuple() because an uploaded file has no key we know of.
            # Inventing one from the first column would impose an ordering the
            # data does not have and would change query behaviour silently.
            client.command(
                f"CREATE TABLE IF NOT EXISTS {qualify(self._database, table)} "
                f"({column_ddl}) ENGINE = MergeTree ORDER BY tuple()"
            )
            target = qualify(self._database, table)
            if upload_format is UploadFormat.CSV:
                client.raw_insert(
                    table=target, insert_block=payload, fmt="CSVWithNames"
                )
            else:
                # The same Arrow table the preview was read from, so what the
                # user approved is exactly what lands.
                client.insert_arrow(target, self._read_parquet(payload))
        finally:
            client.close()

    def _count_rows(self, table: str) -> int:
        client = self._client()
        try:
            result = client.query(
                f"SELECT count() FROM {qualify(self._database, table)}"
            )
            return int(result.result_rows[0][0]) if result.result_rows else 0
        finally:
            client.close()

    async def drop(self, *, database: str, table: str) -> None:
        """Actually remove the table.

        Deletion of an uploaded Data Source has to reach the rows, or deletion
        would mean disappearance from a list while the data stayed.
        """

        def run() -> None:
            client = self._client()
            try:
                client.command(f"DROP TABLE IF EXISTS {qualify(database, table)}")
            finally:
                client.close()

        await asyncio.to_thread(run)


async def _collect(stream: AsyncIterator[bytes]) -> bytes:
    buffer = bytearray()
    async for chunk in stream:
        buffer.extend(chunk)
    return bytes(buffer)
