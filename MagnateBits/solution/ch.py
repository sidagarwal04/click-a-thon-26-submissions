"""ClickHouse access. The ONLY module that talks to the database.

Owner: platform. Other modules import `CH` and use it; they never construct a
clickhouse_connect client themselves.

Safety model:
  - run_select()  refuses anything that is not a single read-only statement.
  - execute_ddl() is the only write path, and is used by the Instrumentation Agent.
This split is deliberate: the Analytics Agent is handed a CH instance whose
execute_ddl is never called, so a hallucinated DROP cannot land.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any, Iterable

import clickhouse_connect
from dotenv import load_dotenv

from contracts import ColumnSpec, LoadResult

load_dotenv()

# NB: `system` is deliberately absent. Schema introspection legitimately reads
# system.tables / system.columns, and the leading-keyword check below already makes
# a `SYSTEM ...` command impossible. Including it here blocked every introspection
# query. Word boundaries keep the rest from matching ordinary identifiers that
# merely start with a keyword, e.g. a column named `created_at`.
_FORBIDDEN = re.compile(
    r"\b(insert|alter|drop|truncate|create|attach|detach|rename|optimize|grant|revoke)\b",
    re.IGNORECASE,
)

# `SHOW CREATE <object>` is a read, but the word `create` is (correctly) in _FORBIDDEN.
# So it gets an allowance that is checked BEFORE the keyword scan -- and the allowance is
# deliberately narrow: the whole statement must be `SHOW CREATE [TABLE|VIEW|...] <ident>`
# and nothing else. Nothing can be appended (`$` anchor), no second statement can ride
# along (run_select rejects `;` first), and `CREATE TABLE ...` / `DROP TABLE ...` /
# `SYSTEM DROP CACHE` never match because the statement must START with `SHOW CREATE`.
_SHOW_CREATE = re.compile(
    r"^\s*show\s+create\s+(?:temporary\s+)?(?:table|view|dictionary|database)?\s*"
    r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?\s*$",
    re.IGNORECASE,
)

_QUERY_ID_OK = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")


class ReadOnlyViolation(RuntimeError):
    pass


class CH:
    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str | None = None,
        secure: bool | None = None,
    ) -> None:
        self.database = database or os.getenv("CH_DATABASE", "atlys")
        self._client = clickhouse_connect.get_client(
            host=host or os.getenv("CH_HOST", "localhost"),
            port=int(port or os.getenv("CH_PORT", "8123")),
            username=user or os.getenv("CH_USER", "atlys"),
            password=password or os.getenv("CH_PASSWORD", "atlys"),
            database=self.database,
            secure=(secure if secure is not None else os.getenv("CH_SECURE", "false") == "true"),
        )

    # ---- reads -----------------------------------------------------------

    def run_select(
        self,
        sql: str,
        max_rows: int = 500,
        query_id: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a single read-only statement. Raises on anything mutating.

        `query_id` is passed through to ClickHouse so the statement can be looked up
        afterwards in `system.query_log` (see `query_stats`). That is how the pipeline
        measures rows/bytes actually read instead of estimating them.
        """
        stripped = sql.strip().rstrip(";")
        if ";" in stripped:
            raise ReadOnlyViolation("multiple statements are not allowed in run_select")
        if not re.match(r"^\s*(select|with|explain|describe|show)\b", stripped, re.IGNORECASE):
            raise ReadOnlyViolation(f"not a read statement: {stripped[:80]}")
        if not _SHOW_CREATE.match(stripped):
            if _FORBIDDEN.search(re.sub(r"'[^']*'", "''", stripped)):
                raise ReadOnlyViolation(f"mutating keyword in read query: {stripped[:80]}")
        opts: dict[str, Any] = {"max_result_rows": max_rows}
        if settings:
            opts.update(settings)
        if query_id:
            if not _QUERY_ID_OK.match(query_id):
                raise ReadOnlyViolation(f"unsafe query_id: {query_id[:80]}")
            opts["query_id"] = query_id
        result = self._client.query(stripped, settings=opts)
        return [dict(zip(result.column_names, row)) for row in result.result_rows]

    def timed_select(
        self, sql: str, max_rows: int = 500, query_id: str | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        t0 = time.perf_counter()
        rows = self.run_select(sql, max_rows=max_rows, query_id=query_id)
        return rows, int((time.perf_counter() - t0) * 1000)

    def explain(self, sql: str) -> str:
        rows = self.run_select(f"EXPLAIN {sql.strip().rstrip(';')}", max_rows=200)
        return "\n".join(str(next(iter(r.values()))) for r in rows)

    # ---- schema introspection -------------------------------------------

    def table_exists(self, name: str) -> bool:
        rows = self.run_select(
            f"SELECT count() AS n FROM system.tables "
            f"WHERE database = '{self.database}' AND name = '{name}'"
        )
        return bool(rows and rows[0]["n"])

    def columns(self, table: str) -> list[tuple[str, str]]:
        rows = self.run_select(
            f"SELECT name, type FROM system.columns "
            f"WHERE database = '{self.database}' AND table = '{table}' ORDER BY position",
            max_rows=1000,
        )
        return [(r["name"], r["type"]) for r in rows]

    def list_tables(self) -> list[str]:
        rows = self.run_select(
            f"SELECT name FROM system.tables WHERE database = '{self.database}' ORDER BY name",
            max_rows=1000,
        )
        return [r["name"] for r in rows]

    # ---- measurement -----------------------------------------------------

    def query_stats(self, query_id: str, timeout_s: float = 4.0) -> dict[str, int]:
        """Real cost of one already-executed query, from `system.query_log`.

        Returns {read_rows, read_bytes, query_duration_ms, memory_usage}, or {} if the
        row never showed up. `system.query_log` is written asynchronously, so this
        flushes once (`SYSTEM FLUSH LOGS` goes through execute_ddl -- the write path --
        because run_select's leading-keyword check correctly refuses `SYSTEM ...`) and
        then polls with backoff.
        """
        return self.query_stats_many([query_id], timeout_s=timeout_s).get(query_id, {})

    def query_stats_many(
        self, query_ids: Iterable[str], timeout_s: float = 4.0
    ) -> dict[str, dict[str, int]]:
        """`query_stats` for a batch: one flush and one read for the whole set."""
        wanted = [q for q in dict.fromkeys(query_ids) if q and _QUERY_ID_OK.match(q)]
        if not wanted:
            return {}
        id_list = ", ".join(f"'{q}'" for q in wanted)
        sql = (
            "SELECT query_id, read_rows, read_bytes, query_duration_ms, memory_usage "
            f"FROM system.query_log WHERE type = 'QueryFinish' AND query_id IN ({id_list}) "
            "ORDER BY event_time_microseconds"
        )
        out: dict[str, dict[str, int]] = {}
        deadline = time.time() + timeout_s
        delay = 0.05
        flushed = False
        while True:
            try:
                if not flushed:
                    self.execute_ddl("SYSTEM FLUSH LOGS")
                    flushed = True
                for r in self.run_select(sql, max_rows=4 * len(wanted) + 10):
                    out[str(r["query_id"])] = {
                        "read_rows": int(r["read_rows"]),
                        "read_bytes": int(r["read_bytes"]),
                        "query_duration_ms": int(r["query_duration_ms"]),
                        "memory_usage": int(r["memory_usage"]),
                    }
            except Exception:  # noqa: BLE001 - measurement must never fail the run
                return out
            if len(out) >= len(wanted) or time.time() >= deadline:
                return out
            time.sleep(delay)
            delay = min(delay * 2, 0.5)
            flushed = False

    def create_statement(self, table: str) -> str:
        rows = self.run_select(f"SHOW CREATE TABLE {self.database}.{table}")
        return str(next(iter(rows[0].values()))) if rows else ""

    # ---- writes ----------------------------------------------------------

    def execute_ddl(self, sql: str) -> None:
        self._client.command(sql)

    def insert_rows(self, table: str, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        cols = list(rows[0].keys())
        data = [[r.get(c) for c in cols] for r in rows]
        self._client.insert(table, data, column_names=cols)
        return len(rows)

    def insert_ndjson(
        self,
        table: str,
        path: Path,
        mapping: list[ColumnSpec],
        batch_size: int = 20_000,
    ) -> LoadResult:
        """Map raw NDJSON events onto the proposed columns and bulk-insert.

        `mapping` drives extraction: each ColumnSpec.json_path is a dotted path into
        the source event. Columns with an empty json_path are skipped (derived/MV-only).
        """
        import orjson

        from mapping import coerce_value, extract_path  # local module, owned by agent A

        cols = [c for c in mapping if c.json_path]
        names = [c.name for c in cols]
        buf: list[list[Any]] = []
        read = inserted = rejected = 0
        errors: list[str] = []

        def flush() -> None:
            nonlocal buf, inserted
            if buf:
                self._client.insert(table, buf, column_names=names)
                inserted += len(buf)
                buf = []

        with path.open("rb") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                read += 1
                try:
                    event = orjson.loads(line)
                    buf.append(
                        [coerce_value(extract_path(event, c.json_path), c.type) for c in cols]
                    )
                except Exception as exc:  # noqa: BLE001 - collect and continue
                    rejected += 1
                    if len(errors) < 10:
                        errors.append(f"line {read}: {exc}")
                if len(buf) >= batch_size:
                    flush()
        flush()
        return LoadResult(
            table_name=table,
            rows_read=read,
            rows_inserted=inserted,
            rejected=rejected,
            errors=errors,
        )

    @staticmethod
    def split_statements(sql_text: str) -> list[str]:
        """Split a SQL script into statements.

        Naive `.split(";")` is wrong twice over: a `--` comment may contain a
        semicolon ("Owned by Wave 0; read by ..."), and so may a quoted literal
        (our generated column COMMENTs embed "json_path=x; events: y"). So strip
        comments first, then split only on semicolons outside single quotes.
        """
        no_comments = "\n".join(
            line.split("--", 1)[0] if "--" in line and line.strip().startswith("--") else line
            for line in sql_text.splitlines()
        )
        out: list[str] = []
        buf: list[str] = []
        in_str = False
        i = 0
        while i < len(no_comments):
            ch = no_comments[i]
            if ch == "'" and not (i and no_comments[i - 1] == "\\"):
                in_str = not in_str
            if ch == ";" and not in_str:
                out.append("".join(buf))
                buf = []
            else:
                buf.append(ch)
            i += 1
        out.append("".join(buf))
        return [s.strip() for s in out if s.strip()]

    def execute_script(self, sql_text: str) -> None:
        """Run a multi-statement SQL file (used for context layer bootstrap)."""
        for stmt in self.split_statements(sql_text):
            self._client.command(stmt)
