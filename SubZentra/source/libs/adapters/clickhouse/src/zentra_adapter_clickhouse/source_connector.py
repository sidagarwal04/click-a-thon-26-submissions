"""Reading a customer's ClickHouse as a Data Source.

Distinct from ``audit.py`` in this same package, which writes ZentraOS's own
metadata-only ledger. This module reads someone else's warehouse and must never
copy rows out of it: every statistic and every overlap measurement is computed
by aggregate query *at the source*, and only the aggregate comes back.

That constraint is the whole reason ``measure_overlap`` is written the way it
is. Pulling both key columns back and intersecting them in Python would be
simpler, would satisfy the port's type signature, and would quietly turn
discovery into data exfiltration.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import clickhouse_connect
from clickhouse_connect.driver.exceptions import DatabaseError, OperationalError
from zentra_application_connector import (
    SourceCredentials,
    SourceFieldDescriptor,
    SourceTableDescriptor,
)
from zentra_domain_connector import (
    ConnectionCheck,
    ConnectionFailure,
    FieldProfile,
    OverlapMeasurement,
)

from .sql import qualify, quote_identifier

#: Databases that belong to the engine rather than to the customer. Harvesting
#: them would fill a reviewer's catalog with introspection tables they never
#: asked about and cannot join to anything meaningful.
SYSTEM_DATABASES: frozenset[str] = frozenset(
    {"system", "information_schema", "INFORMATION_SCHEMA", "default"}
)

#: Per-query wall-clock ceiling. A pathological table must not be able to hang
#: a harvest, and the source is someone else's production system.
QUERY_TIMEOUT_SECONDS = 30


def _classify_failure(exc: Exception) -> ConnectionFailure:
    """Map a driver error to a reason the admin can act on.

    Matched on the message because the driver raises the same exception class
    for all three. Coarse on purpose: anything finer would start echoing the
    source's own error text, which carries hostnames and usernames.
    """
    text = str(exc).lower()
    if "authentication" in text or "password" in text or "access denied" in text:
        return ConnectionFailure.AUTHENTICATION_FAILED
    if "database" in text and ("not exist" in text or "unknown" in text):
        return ConnectionFailure.DATABASE_NOT_FOUND
    return ConnectionFailure.UNREACHABLE


@dataclass(frozen=True, slots=True)
class _Client:
    """A thin wrapper so query execution has one place to be instrumented."""

    raw: Any

    def query(self, sql: str, parameters: dict[str, Any] | None = None) -> Any:
        return self.raw.query(sql, parameters=parameters or {})


class ClickHouseSourceConnector:
    """A ``SourceConnector`` over ClickHouse.

    Satisfies the application's port by shape rather than by inheritance, so the
    application never imports this module — the layering the import-linter
    contracts enforce.

    Clients are created per call rather than pooled. Harvests are infrequent and
    long, credentials rotate, and a pooled connection to a customer's warehouse
    that outlives the operation is a liability rather than an optimisation.
    """

    def _connect(self, credentials: SourceCredentials) -> _Client:
        return _Client(
            clickhouse_connect.get_client(
                host=credentials.host,
                port=credentials.port,
                username=credentials.username,
                password=credentials.password,
                database=credentials.database,
                secure=credentials.secure,
                connect_timeout=QUERY_TIMEOUT_SECONDS,
                send_receive_timeout=QUERY_TIMEOUT_SECONDS,
            )
        )

    async def test_connection(self, credentials: SourceCredentials) -> ConnectionCheck:
        def probe() -> ConnectionCheck:
            try:
                client = self._connect(credentials)
                client.query("SELECT 1")
                return ConnectionCheck(reachable=True)
            except (DatabaseError, OperationalError, OSError) as exc:
                return ConnectionCheck(
                    reachable=False, failure=_classify_failure(exc)
                )

        return await asyncio.to_thread(probe)

    async def list_tables(
        self,
        credentials: SourceCredentials,
        *,
        databases: Sequence[str] = (),
    ) -> Sequence[SourceTableDescriptor]:
        """Read table metadata from ``system.tables``.

        Row counts and sizes come back as estimates because that is what
        ClickHouse stores; they are never presented to a reviewer as exact.
        """
        sql = """
            SELECT database, name, engine, total_rows, total_bytes
            FROM system.tables
            WHERE database NOT IN %(system_dbs)s
              AND (length(%(dbs)s) = 0 OR database IN %(dbs)s)
        """
        params = {
            "system_dbs": list(SYSTEM_DATABASES),
            "dbs": list(databases),
        }

        def run() -> list[SourceTableDescriptor]:
            result = self._connect(credentials).query(sql, params)
            return [
                SourceTableDescriptor(
                    database=row[0],
                    name=row[1],
                    engine=row[2],
                    estimated_rows=int(row[3]) if row[3] is not None else None,
                    size_bytes=int(row[4]) if row[4] is not None else None,
                )
                for row in result.result_rows
            ]

        return await asyncio.to_thread(run)

    async def describe_fields(
        self,
        credentials: SourceCredentials,
        *,
        database: str,
        table: str,
    ) -> Sequence[SourceFieldDescriptor]:
        sql = """
            SELECT name, type, position
            FROM system.columns
            WHERE database = %(db)s AND table = %(tbl)s
            ORDER BY position
        """

        def run() -> list[SourceFieldDescriptor]:
            result = self._connect(credentials).query(
                sql, {"db": database, "tbl": table}
            )
            return [
                SourceFieldDescriptor(
                    name=row[0],
                    declared_type=row[1],
                    # ClickHouse has no nullability column; it is part of the
                    # type. Reading it from the type string keeps the one source
                    # of truth rather than inventing a second.
                    nullable=row[1].startswith("Nullable("),
                    position=int(row[2]),
                )
                for row in result.result_rows
            ]

        return await asyncio.to_thread(run)

    async def profile_field(
        self,
        credentials: SourceCredentials,
        *,
        database: str,
        table: str,
        field_name: str,
        sample_rows: int,
        include_sample_values: bool,
    ) -> FieldProfile:
        """Compute statistics over a bounded sample.

        Bounded by ``LIMIT`` rather than run over the whole table: this is
        someone's production warehouse, and a full scan of a billion-row table
        to learn a null fraction is not a reasonable thing to do to them. The
        sample size travels with the result so no statistic is ever presented
        without the size of its evidence.
        """
        column = quote_identifier(field_name)
        qualified = qualify(database, table)
        values_expr = (
            f"arraySlice(groupUniqArray(toString({column})), 1, 5)"
            if include_sample_values
            else "[]"
        )
        sql = f"""
            SELECT
                count() AS sampled,
                countIf({column} IS NULL) AS nulls,
                uniqExact({column}) AS distinct_values,
                toString(min({column})) AS min_value,
                toString(max({column})) AS max_value,
                {values_expr} AS samples
            FROM (SELECT {column} FROM {qualified} LIMIT %(limit)s)
        """

        def run() -> FieldProfile:
            result = self._connect(credentials).query(sql, {"limit": sample_rows})
            if not result.result_rows:
                return FieldProfile(sampled_rows=0)
            sampled, nulls, distinct, minimum, maximum, samples = result.result_rows[0]
            sampled = int(sampled)
            return FieldProfile(
                sampled_rows=sampled,
                null_fraction=(int(nulls) / sampled) if sampled else None,
                distinct_count=int(distinct),
                min_value=minimum,
                max_value=maximum,
                sample_values=tuple(samples) if include_sample_values else (),
            )

        return await asyncio.to_thread(run)

    async def measure_overlap(
        self,
        left_credentials: SourceCredentials,
        right_credentials: SourceCredentials,
        *,
        left: tuple[str, str, str],
        right: tuple[str, str, str],
        sample_rows: int,
    ) -> OverlapMeasurement:
        """Measure how many of one field's values appear in another's.

        Two paths, because the two sides may not live in the same place.

        Within one instance, the whole thing is a single aggregate query and no
        row ever leaves the source. Across two instances there is no such query,
        so the *distinct key values* of the smaller side are read and probed
        against the other. That is a real disclosure — bounded by the sample
        limit and confined to key columns — and it is the price of discovering a
        relationship between an uploaded file and a warehouse. It is why the
        cross-source path is separated here rather than hidden behind a helper.
        """
        same_instance = (
            left_credentials.host == right_credentials.host
            and left_credentials.port == right_credentials.port
        )
        if same_instance:
            return await asyncio.to_thread(
                self._overlap_single_instance,
                left_credentials,
                left,
                right,
                sample_rows,
            )
        return await asyncio.to_thread(
            self._overlap_cross_instance,
            left_credentials,
            right_credentials,
            left,
            right,
            sample_rows,
        )

    def _overlap_single_instance(
        self,
        credentials: SourceCredentials,
        left: tuple[str, str, str],
        right: tuple[str, str, str],
        sample_rows: int,
    ) -> OverlapMeasurement:
        left_sql = self._distinct_subquery(left)
        right_sql = self._distinct_subquery(right)
        sql = f"""
            WITH
                l AS ({left_sql}),
                r AS ({right_sql})
            SELECT
                (SELECT uniqExact(v) FROM l) AS left_distinct,
                (SELECT uniqExact(v) FROM r) AS right_distinct,
                (SELECT uniqExact(v) FROM l WHERE v IN (SELECT v FROM r))
                    AS matched,
                (SELECT count() FROM l) AS left_rows,
                (SELECT count() FROM r) AS right_rows
        """
        result = self._connect(credentials).query(sql, {"limit": sample_rows})
        if not result.result_rows:
            return OverlapMeasurement(
                left_distinct=0, right_distinct=0, matched_distinct=0, sampled_rows=0
            )
        left_distinct, right_distinct, matched, left_rows, right_rows = (
            result.result_rows[0]
        )
        return OverlapMeasurement(
            left_distinct=int(left_distinct),
            right_distinct=int(right_distinct),
            matched_distinct=int(matched),
            # The *smaller* side, because the sample-size ceiling exists to
            # bound confidence by the weakest evidence supporting it. A 50-row
            # lookup joined against 20,000 fact rows rests on 50 rows, and
            # reporting the larger number would lift the ceiling to 1.0 on
            # evidence that does not support it.
            sampled_rows=min(int(left_rows), int(right_rows)),
            left_is_unique=int(left_distinct) == int(left_rows) and int(left_rows) > 0,
            right_is_unique=(
                int(right_distinct) == int(right_rows) and int(right_rows) > 0
            ),
        )

    def _overlap_cross_instance(
        self,
        left_credentials: SourceCredentials,
        right_credentials: SourceCredentials,
        left: tuple[str, str, str],
        right: tuple[str, str, str],
        sample_rows: int,
    ) -> OverlapMeasurement:
        left_client = self._connect(left_credentials)
        right_client = self._connect(right_credentials)

        left_stats = self._distinct_stats(left_client, left, sample_rows)
        right_stats = self._distinct_stats(right_client, right, sample_rows)

        # Probe with the smaller side's keys, so the volume that crosses the
        # boundary is the minimum the measurement can be made with.
        if left_stats[0] <= right_stats[0]:
            probe_client, probe_side = right_client, right
            keys = self._distinct_values(left_client, left, sample_rows)
        else:
            probe_client, probe_side = left_client, left
            keys = self._distinct_values(right_client, right, sample_rows)

        matched = self._count_matching(probe_client, probe_side, keys, sample_rows)
        return OverlapMeasurement(
            left_distinct=left_stats[0],
            right_distinct=right_stats[0],
            matched_distinct=matched,
            sampled_rows=min(left_stats[1], right_stats[1]),
            left_is_unique=left_stats[0] == left_stats[1] and left_stats[1] > 0,
            right_is_unique=right_stats[0] == right_stats[1] and right_stats[1] > 0,
        )

    def _distinct_subquery(self, side: tuple[str, str, str]) -> str:
        database, table, column = side
        return (
            f"SELECT {quote_identifier(column)} AS v "
            f"FROM {qualify(database, table)} "
            f"WHERE {quote_identifier(column)} IS NOT NULL "
            f"LIMIT %(limit)s"
        )

    def _distinct_stats(
        self, client: _Client, side: tuple[str, str, str], sample_rows: int
    ) -> tuple[int, int]:
        sql = f"SELECT uniqExact(v), count() FROM ({self._distinct_subquery(side)})"
        result = client.query(sql, {"limit": sample_rows})
        if not result.result_rows:
            return 0, 0
        distinct, rows = result.result_rows[0]
        return int(distinct), int(rows)

    def _distinct_values(
        self, client: _Client, side: tuple[str, str, str], sample_rows: int
    ) -> list[str]:
        sql = (
            f"SELECT DISTINCT toString(v) FROM ({self._distinct_subquery(side)})"
            " LIMIT %(outer_limit)s"
        )
        result = client.query(
            sql, {"limit": sample_rows, "outer_limit": sample_rows}
        )
        return [row[0] for row in result.result_rows]

    def _count_matching(
        self,
        client: _Client,
        side: tuple[str, str, str],
        keys: Sequence[str],
        sample_rows: int,
    ) -> int:
        if not keys:
            return 0
        sql = (
            f"SELECT uniqExact(v) FROM ({self._distinct_subquery(side)})"
            " WHERE toString(v) IN %(keys)s"
        )
        result = client.query(sql, {"limit": sample_rows, "keys": list(keys)})
        return int(result.result_rows[0][0]) if result.result_rows else 0
