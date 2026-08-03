"""ClickHouse access layer (ENGINEERING.md §4.2 `store.py`).

Wraps clickhouse-connect with retries/backoff so transient cloud blips don't
kill a run. All Nullable/DateTime conversion lives here once — agents stay clean.

Also provides an in-memory `DryRunStore` so the whole pipeline (schema inference,
DDL generation, evidence synthesis) works with **no ClickHouse** (deterministic-
first, §5.2.6). Dry-run stores rows in memory and answers the analytical
queries the playbook generates.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from collections import OrderedDict, defaultdict
from typing import Any, Iterable, Sequence

from .sqlsafe import sanitize_identifier as _sanitize_identifier
from .ch_errors import ClickHouseOpError, classify_exception

log = logging.getLogger("atlys.store")


def _table_key(table: str) -> str:
    """'meta.pending_runs' → 'pending_runs' (in-memory key)."""
    return table.split(".")[-1]


class ClickHouseStore:
    """Real ClickHouse connection with bounded retry/backoff."""

    def __init__(self, host: str, user: str, password: str | None = None, secure: bool = False,
                 database: str = "atlys", retries: int = 3, backoff_s: float = 0.5):
        import clickhouse_connect  # deferred import

        self.database = database
        self._retries = retries
        self._backoff = backoff_s
        self.server_version: str | None = None
        # clickhouse-connect clients are not safe for concurrent queries on one
        # session; FastAPI runs sync endpoints in a threadpool, so serialize.
        self._client_lock = threading.RLock()
        # Connect without pinning a database first, then CREATE the target
        # databases — connecting with database='atlys' would fail on a fresh
        # cluster where the database doesn't exist yet (code 81 UNKNOWN_DATABASE),
        # and a restricted user might lack access to a literal 'default' db.
        self._client = clickhouse_connect.get_client(
            host=host, username=user, password=password or "", secure=secure,
            connect_timeout=10, send_receive_timeout=60,
        )
        self._client.command(f"CREATE DATABASE IF NOT EXISTS {_sanitize_identifier(database)}")
        self._client.command("CREATE DATABASE IF NOT EXISTS meta")
        self._client.database = database
        self.server_version = self.detect_version()

    def detect_version(self) -> str:
        """P0.6 — log and return `SELECT version()` once per connection."""
        try:
            with self._client_lock:
                rows = self._client.query("SELECT version() AS v").result_rows
            ver = str(rows[0][0]) if rows else "unknown"
        except Exception as e:  # noqa: BLE001
            ver = f"unknown ({e})"
        log.info("ClickHouse version: %s (database=%s)", ver, self.database)
        self.server_version = ver
        return ver

    # -- generic execution with retry (only retryable error classes) --
    def _retry(self, fn, sql: str | None = None):
        last_err: ClickHouseOpError | None = None
        for attempt in range(self._retries):
            try:
                return fn()
            except ClickHouseOpError as e:
                last_err = e
                if not e.retryable or attempt >= self._retries - 1:
                    raise
                time.sleep(self._backoff * (2**attempt))
            except Exception as e:  # noqa: BLE001 - classify then maybe retry
                last_err = classify_exception(e, sql)
                if not last_err.retryable or attempt >= self._retries - 1:
                    raise last_err from e
                log.warning("retryable CH error (%s) attempt %s: %s",
                            last_err.error_class, attempt + 1, last_err.message)
                time.sleep(self._backoff * (2**attempt))
        assert last_err is not None
        raise last_err

    def query(self, sql: str, params: dict | None = None) -> list[list[Any]]:
        """Run a SELECT, return rows as list-of-lists (ClickHouse native)."""
        def _q():
            with self._client_lock:
                result = self._client.query(sql, parameters=params or {})
                return [list(row) for row in result.result_rows]
        return self._retry(_q, sql)

    def query_rows(self, sql: str, params: dict | None = None) -> list[dict]:
        """Run a SELECT, return rows as dicts keyed by column name."""
        def _q():
            with self._client_lock:
                result = self._client.query(sql, parameters=params or {})
                names = result.column_names
                return [dict(zip(names, row)) for row in result.result_rows]
        return self._retry(_q, sql)

    def command(self, sql: str) -> str | None:
        """Execute DDL or non-SELECT statements (CREATE/ALTER/INSERT ... SELECT)."""
        def _cmd():
            with self._client_lock:
                return self._client.command(sql)
        return self._retry(_cmd, sql)

    def insert(self, table: str, columns: Sequence[str], rows: Iterable[Sequence[Any]]) -> int:
        """Bulk insert rows into `table`. Returns number of inserted rows."""
        rows = list(rows)
        if not rows:
            return 0
        batch = 1000
        for i in range(0, len(rows), batch):
            chunk = rows[i : i + batch]
            # client.insert returns a QuerySummary (not an int) — we count rows ourselves
            def _ins(c=chunk):
                with self._client_lock:
                    return self._client.insert(table, c, column_names=list(columns))
            self._retry(_ins, f"INSERT {table}")
        return len(rows)

    def columns(self, table: str) -> list[dict]:
        """Column metadata from system.columns (name, type, position)."""
        rows = self.query_rows(
            "SELECT name, type, position FROM system.columns "
            "WHERE database = {db:String} AND table = {tbl:String} ORDER BY position",
            {"db": self.database, "tbl": table},
        )
        return rows

    def table_exists(self, table: str) -> bool:
        rows = self.query_rows(
            "SELECT 1 FROM system.tables WHERE database = {db:String} AND name = {tbl:String}",
            {"db": self.database, "tbl": table},
        )
        return bool(rows)

    def row_count(self, table: str) -> int:
        rows = self.query_rows(f"SELECT count() AS c FROM {_sanitize_identifier(table)}")
        return int(rows[0]["c"]) if rows else 0

    def all_tables(self) -> list[str]:
        rows = self.query_rows(
            "SELECT name FROM system.tables WHERE database = {db:String} ORDER BY name",
            {"db": self.database},
        )
        return [r["name"] for r in rows]


def _parse_create_columns(sql: str) -> OrderedDict[str, str]:
    """Best-effort column list from a CREATE TABLE body (dry-run schema tracking)."""
    cols: OrderedDict[str, str] = OrderedDict()
    m = re.search(r"\((.*)\)\s*ENGINE", sql, re.S | re.I)
    if not m:
        return cols
    body = m.group(1)
    for line in body.split("\n"):
        line = line.strip().rstrip(",")
        if not line or line.startswith("--"):
            continue
        # name Type…  (Type may include Nested parens: Nullable(UInt8), LowCardinality(...))
        cm = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s+(.+)$", line)
        if cm:
            cols[cm.group(1)] = cm.group(2).strip()
    return cols


def _bind_params(sql: str, params: dict | None) -> str:
    """Substitute clickhouse-connect `{name:Type}` placeholders for DryRunStore."""
    if not params:
        return sql

    def repl(m: re.Match) -> str:
        name = m.group(1)
        if name not in params:
            return m.group(0)
        val = params[name]
        if val is None:
            return "NULL"
        if isinstance(val, bool):
            return "1" if val else "0"
        if isinstance(val, (int, float)):
            return str(val)
        # quote strings; escape single quotes
        return "'" + str(val).replace("'", "\\'") + "'"

    return re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)(?::[^}]+)?\}", repl, sql)

class DryRunStore:
    """In-memory store that lets the full pipeline run without ClickHouse.

    Stores rows per table, executes the playbook's aggregate SQL against the
    in-memory data (a deliberately small SQL subset — the queries WE generate),
    and no-ops DDL (recording it for inspection). This is what makes
    `--dry-run` regression + unit tests possible with zero infra (§9).
    """

    def __init__(self, database: str = "atlys"):
        self.database = database
        self._tables: dict[str, list[dict]] = defaultdict(list)
        self._schemas: dict[str, OrderedDict[str, str]] = {}
        self.commands: list[str] = []
        self._lock = threading.RLock()
        self.server_version = "dry-run"

    def detect_version(self) -> str:
        log.info("ClickHouse version: dry-run (in-memory)")
        return self.server_version

    # -- plumbing mirrors of ClickHouseStore --
    def query(self, sql: str, params: dict | None = None) -> list[list[Any]]:
        with self._lock:
            sql = self._bind(sql, params)
            sql = re.sub(r"\s+SETTINGS\s+.+$", "", sql, flags=re.I | re.S).rstrip().rstrip(";")
            if re.search(r"SELECT\s+version\s*\(\s*\)", sql, re.I):
                return [[self.server_version]]
            return [list(row) for row in self._execute(sql)]

    def query_rows(self, sql: str, params: dict | None = None) -> list[dict]:
        with self._lock:
            sql = self._bind(sql, params)
            sql = re.sub(r"\s+SETTINGS\s+.+$", "", sql, flags=re.I | re.S).rstrip().rstrip(";")
            if re.search(r"SELECT\s+version\s*\(\s*\)", sql, re.I):
                return [{"v": self.server_version, "version()": self.server_version}]
            names, rows = self._plan(sql)
            return [dict(zip(names, row)) for row in rows]

    @staticmethod
    def _bind(sql: str, params: dict | None) -> str:
        """Substitute clickhouse-connect `{name:Type}` placeholders for dry-run."""
        if not params:
            return sql

        def repl(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in params:
                raise KeyError(f"missing query param: {name}")
            val = params[name]
            if val is None:
                return "NULL"
            if isinstance(val, bool):
                return "1" if val else "0"
            if isinstance(val, (int, float)):
                return str(val)
            # string / other → quoted SQL literal
            text = str(val).replace("\x00", "").replace("'", "''")
            return f"'{text}'"

        return re.sub(r"\{([A-Za-z_][A-Za-z0-9_]*)[^}]*\}", repl, sql)

    def command(self, sql: str) -> str | None:
        with self._lock:
            return self._command_locked(sql)

    def _command_locked(self, sql: str) -> str | None:
        self.commands.append(sql)
        drop = re.match(r"DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?([A-Za-z0-9_.]+)", sql, re.I)
        if drop:
            key = _table_key(drop.group(1))
            self._tables.pop(key, None)
            self._schemas.pop(key, None)
            return None
        trunc = re.match(r"TRUNCATE\s+TABLE\s+(?:IF\s+EXISTS\s+)?([A-Za-z0-9_.]+)", sql, re.I)
        if trunc:
            key = _table_key(trunc.group(1))
            self._tables[key] = []
            return None
        m = re.search(r"CREATE TABLE (?:IF NOT EXISTS )?([A-Za-z0-9_.]+)", sql, re.I)
        if m:
            key = _table_key(m.group(1))
            self._tables.setdefault(key, [])
            parsed = _parse_create_columns(sql)
            # IF NOT EXISTS: keep an existing schema (rebuild DROPs first).
            if parsed and key not in self._schemas:
                self._schemas[key] = parsed
        # ALTER TABLE <t> ADD COLUMN IF NOT EXISTS <col> <type>
        add = re.match(
            r"ALTER\s+TABLE\s+([A-Za-z0-9_.]+)\s+ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?"
            r"([A-Za-z_][A-Za-z0-9_]*)\s+(.+?)(?:;|$)",
            sql, re.I | re.S,
        )
        if add:
            key, col, ctype = _table_key(add.group(1)), add.group(2), add.group(3).strip().rstrip(";")
            schema = self._schemas.setdefault(key, OrderedDict())
            if col not in schema:
                schema[col] = ctype
                for row in self._tables.get(key, []):
                    row.setdefault(col, None)
            return None
        # ALTER TABLE <t> MODIFY COLUMN <col> <type>
        mod = re.match(
            r"ALTER\s+TABLE\s+([A-Za-z0-9_.]+)\s+MODIFY\s+COLUMN\s+"
            r"([A-Za-z_][A-Za-z0-9_]*)\s+(.+?)(?:;|$)",
            sql, re.I | re.S,
        )
        if mod:
            key, col, ctype = _table_key(mod.group(1)), mod.group(2), mod.group(3).strip().rstrip(";")
            schema = self._schemas.setdefault(key, OrderedDict())
            schema[col] = ctype
            return None
        # ALTER TABLE <t> UPDATE col='v', col2='v2' WHERE ... [AND ...]
        alt = re.match(
            r"ALTER TABLE\s+([A-Za-z0-9_.]+)\s+UPDATE\s+(.+?)\s+WHERE\s+(.+?)(?:\s+SETTINGS\s+.+)?$",
            sql.strip(), re.I | re.S,
        )
        if alt:
            table, set_clause, where_clause = alt.groups()
            updates = self._parse_set_clause(set_clause)
            for row in self._tables.get(_table_key(table), []):
                if self._eval_where(where_clause.strip(), row):
                    row.update(updates)
        return None

    @staticmethod
    def _parse_set_clause(set_clause: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for part in re.split(r",\s*", set_clause.strip()):
            m = re.match(r"([a-zA-Z0-9_]+)\s*=\s*'((?:[^']|'')*)'", part.strip())
            if not m:
                raise NotImplementedError(f"dry-run cannot parse SET: {part}")
            out[m.group(1)] = m.group(2).replace("''", "'")
        return out

    def insert(self, table: str, columns: Sequence[str], rows: Iterable[Sequence[Any]]) -> int:
        with self._lock:
            cols = list(columns)
            key = _table_key(table)
            out = []
            for row in rows:
                out.append(dict(zip(cols, row)))
            self._tables[key].extend(out)
            if key not in self._schemas and cols:
                self._schemas[key] = OrderedDict((c, "String") for c in cols)
            return len(out)

    def columns(self, table: str) -> list[dict]:
        with self._lock:
            key = _table_key(table)
            schema = self._schemas.get(key)
            if schema:
                return [{"name": n, "type": t, "position": i} for i, (n, t) in enumerate(schema.items())]
            rows = self._tables.get(key, [])
            if not rows:
                return []
            return [
                {"name": c, "type": "String", "position": i}
                for i, c in enumerate(rows[0].keys())
            ]

    def table_exists(self, table: str) -> bool:
        with self._lock:
            key = _table_key(table)
            return key in self._tables or key in self._schemas

    def row_count(self, table: str) -> int:
        with self._lock:
            return len(self._tables.get(_table_key(table), []))

    def all_tables(self) -> list[str]:
        with self._lock:
            return sorted(set(self._tables) | set(self._schemas))

    # -- tiny aggregate SQL evaluator (subset: the playbook queries we emit) --
    _AGG = {"count", "uniqExact", "uniq", "uniqIf", "quantile", "minIf", "maxIf", "countIf", "min", "max", "sum", "avg"}

    def _plan(self, sql: str) -> tuple[list[str], list[list[Any]]]:
        """Parse a simple `SELECT <exprs> FROM <t> [WHERE ...] [GROUP BY ...] [ORDER BY ...] [LIMIT n]`.

        The FROM is located at parenthesis-depth 0 so scalar subqueries inside
        the SELECT list (e.g. cross-funnel P5) don't confuse the parser, and the
        expression list is taken between SELECT and that top-level FROM.
        """
        select_m = re.match(r"SELECT\s+", sql, re.I)
        if not select_m:
            raise NotImplementedError(f"dry-run cannot execute: {sql[:120]}...")
        exprs_start = select_m.end()

        # locate the top-level FROM at paren-depth 0 (skips subquery FROMs)
        depth = 0
        top_from = None
        for i in range(exprs_start, len(sql)):
            ch = sql[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif depth == 0 and sql[i : i + 4].upper() == "FROM":
                top_from = i
                break
        if top_from is None:
            raise NotImplementedError(f"dry-run cannot find FROM: {sql[:120]}...")

        exprs_raw = sql[exprs_start:top_from].strip().rstrip(";").strip()
        after_from = top_from + 4
        table_m = re.match(r"\s*([A-Za-z0-9_.]+)(?:\s+(?:AS\s+)?[A-Za-z])?", sql[after_from:])
        if not table_m:
            raise NotImplementedError(f"dry-run cannot parse table: {sql[after_from:][:40]}")
        table = _table_key(table_m.group(1))

        where_m = re.search(r"WHERE\s+(.+?)(?:\s+GROUP BY|\s+ORDER BY|\s+LIMIT|$)", sql, re.S | re.I)
        group_m = re.search(r"GROUP BY\s+(.+?)(?:\s+ORDER BY|\s+LIMIT|$)", sql, re.I | re.S)
        order_m = re.search(r"ORDER BY\s+([a-zA-Z0-9_.]+)\s*(ASC|DESC)?", sql, re.I)
        limit_m = re.search(r"LIMIT\s+(\d+)", sql, re.I)

        rows = self._tables.get(table, [])
        if where_m:
            rows = [r for r in rows if self._eval_where(where_m.group(1).strip(), r)]

        group_cols = []
        if group_m:
            group_cols = [c.strip().split(".")[-1] for c in group_m.group(1).split(",") if c.strip()]
        # Split top-level SELECT expressions (commas not inside parens)
        exprs = self._split_exprs(exprs_raw)
        computed: list[list[Any]] = []
        has_agg = any(self._expr_is_aggregate(e) for e in exprs)
        names = [e.rsplit(" AS ", 1)[-1].strip() for e in exprs]

        if group_cols:
            buckets: dict[Any, list[dict]] = defaultdict(list)
            for r in rows:
                key = tuple(r.get(c) for c in group_cols)
                buckets[key].append(r)
            for bucket in buckets.values():
                computed.append([self._eval_expr(e, bucket) for e in exprs])
        elif has_agg:
            # Aggregate over the full filtered set → one output row.
            computed.append([self._eval_expr(e, rows) for e in exprs])
        else:
            # Row-level projection (needed for journal ORDER BY … LIMIT 1 etc.).
            for r in rows:
                computed.append([self._eval_expr(e, [r]) for e in exprs])

        if order_m:
            col = order_m.group(1).split(".")[-1]
            desc = (order_m.group(2) or "ASC").upper() == "DESC"
            # Match bare col or `… AS col` alias
            names = [e.rsplit(" AS ", 1)[-1].strip() for e in exprs]
            idx = None
            if col in exprs:
                idx = exprs.index(col)
            elif col in names:
                idx = names.index(col)
            if idx is not None:
                computed.sort(key=lambda r: (r[idx] is None, r[idx]), reverse=desc)
        if limit_m:
            computed = computed[: int(limit_m.group(1))]

        return names, computed

    @classmethod
    def _expr_is_aggregate(cls, expr: str) -> bool:
        expr = expr.strip()
        if " AS " in expr:
            expr = expr.split(" AS ")[0].strip()
        # quantile(0.5)(col) or fn(...)
        if re.match(r"^[a-zA-Z]+\([^()]*\)\([^()]*\)$", expr):
            return True
        m = re.match(r"^([a-zA-Z]+)\(", expr)
        return bool(m and m.group(1) in cls._AGG)
    def _execute(self, sql: str) -> list[list[Any]]:
        _, rows = self._plan(sql)
        return rows

    @classmethod
    def _is_aggregate_expr(cls, expr: str) -> bool:
        expr = expr.strip()
        if " AS " in expr:
            expr = expr.split(" AS ")[0].strip()
        m = re.match(r"([a-zA-Z]+)\(", expr)
        return bool(m and m.group(1) in cls._AGG)

    @staticmethod
    def _split_exprs(exprs_raw: str) -> list[str]:
        parts, depth, cur = [], 0, ""
        for ch in exprs_raw:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if ch == "," and depth == 0:
                parts.append(cur.strip())
                cur = ""
            else:
                cur += ch
        if cur.strip():
            parts.append(cur.strip())
        return parts

    def _eval_where(self, clause: str, row: dict) -> bool:
        # AND-combination of simple predicates (used by CAS updates)
        parts = [p.strip() for p in re.split(r"\s+AND\s+", clause, flags=re.I)]
        return all(self._eval_where_atom(p, row) for p in parts)

    def _eval_where_atom(self, clause: str, row: dict) -> bool:
        # supports: comparisons, LIKE, IN (literals|subquery), IS NULL
        clause = clause.strip()
        if " IS NOT NULL" in clause:
            return row.get(clause.split(" IS NOT NULL")[0].strip()) is not None
        if " IS NULL" in clause:
            return row.get(clause.split(" IS NULL")[0].strip()) is None
        like = re.match(r"([a-zA-Z0-9_.]+)\s+LIKE\s+'((?:[^']|'')*)'$", clause, re.I)
        if like:
            col = like.group(1).split(".")[-1]
            pattern = like.group(2).replace("''", "'")
            # SQL LIKE with % / _ — translate to a simple regex
            parts: list[str] = []
            for ch in pattern:
                if ch == "%":
                    parts.append(".*")
                elif ch == "_":
                    parts.append(".")
                else:
                    parts.append(re.escape(ch))
            rx = "^" + "".join(parts) + "$"
            return re.match(rx, str(row.get(col, "")), re.I | re.S) is not None
        if " IN (" in clause.upper():
            # normalize split on first IN (
            m_in = re.match(r"([a-zA-Z0-9_.]+)\s+IN\s+\((.+)\)$", clause, re.I | re.S)
            if not m_in:
                raise NotImplementedError(f"dry-run cannot evaluate WHERE: {clause}")
            col, inner = m_in.group(1).strip(), m_in.group(2).strip()
            key = col.split(".")[-1]
            sub_m = re.match(
                r"SELECT\s+(.+?)\s+FROM\s+([A-Za-z0-9_.]+)(?:\s+(?:AS\s+)?[A-Za-z])?\s+WHERE\s+(.+)$",
                inner, re.S | re.I,
            )
            if sub_m:
                sub_expr, sub_tbl, sub_where = (
                    sub_m.group(1).strip(), _table_key(sub_m.group(2)), sub_m.group(3).strip(),
                )
                sub_col = sub_expr.split(".")[-1]
                vals = {
                    r.get(sub_col)
                    for r in self._tables.get(sub_tbl, [])
                    if self._eval_where(sub_where, r)
                }
                return row.get(key) in vals
            if re.match(r"SELECT\s+", inner, re.I):
                sub_rows = [r[0] for r in self._execute(inner)]
                return row.get(key) in sub_rows
            # literal list: 'a', 'b', 1, 2
            vals = []
            for part in re.findall(r"'(?:[^']|'')*'|-?\d+(?:\.\d+)?", inner):
                if part.startswith("'"):
                    vals.append(part[1:-1].replace("''", "'"))
                else:
                    vals.append(float(part) if "." in part else int(part))
            cell = row.get(key)
            return cell in vals or str(cell) in {str(v) for v in vals}
        cmp_m = re.match(
            r"([a-zA-Z0-9_.]+)\s*(=|!=|<>|>=|<=|>|<)\s*(NULL|'((?:[^']|'')*)'|-?\d+(?:\.\d+)?)$",
            clause, re.I,
        )
        if cmp_m:
            col = cmp_m.group(1).split(".")[-1]
            op = cmp_m.group(2)
            if cmp_m.group(3).upper() == "NULL":
                right = None
            elif cmp_m.group(4) is not None:
                right = cmp_m.group(4).replace("''", "'")
            else:
                num = cmp_m.group(3)
                right = float(num) if "." in num else int(num)
            left = row.get(col)
            if op == "=":
                return (left is None and right is None) or str(left) == str(right)
            if op in {"!=", "<>"}:
                return str(left) != str(right)
            try:
                lf, rf = float(left), float(right)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                lf, rf = str(left), str(right)
            if op == ">":
                return lf > rf
            if op == ">=":
                return lf >= rf
            if op == "<":
                return lf < rf
            if op == "<=":
                return lf <= rf
        raise NotImplementedError(f"dry-run cannot evaluate WHERE: {clause}")

    def _eval_expr(self, expr: str, rows: list[dict]) -> Any:
        expr = expr.strip()
        # scalar subquery: (SELECT <expr> FROM <t> WHERE ...)
        sub_m = re.match(r"^\(SELECT\s+(.+?)\s+FROM\s+([A-Za-z0-9_.]+)(?:\s+(?:AS\s+)?[A-Za-z])?\s+WHERE\s+(.+?)\)$", expr, re.S | re.I)
        if sub_m:
            sub_expr, sub_tbl, sub_where = sub_m.group(1).strip(), _table_key(sub_m.group(2)), sub_m.group(3).strip()
            sub_rows = [r for r in self._tables.get(sub_tbl, []) if self._eval_where(sub_where, r)]
            return self._eval_expr(sub_expr, sub_rows)
        # plain column reference (GROUP BY key or bare col in non-aggregate select)
        if re.fullmatch(r"[a-zA-Z0-9_.]+", expr):
            return rows[0].get(expr.split(".")[-1]) if rows else None
        if " AS " in expr:
            expr = expr.split(" AS ")[0].strip()
        # fn(a)(b) form — quantile(0.5)(col)
        m2 = re.match(r"([a-zA-Z]+)\(([^()]*)\)\(([^()]*)\)$", expr)
        if m2 and m2.group(1) == "quantile":
            q = float(m2.group(2))
            col = m2.group(3).strip().split(".")[-1]
            vals = sorted(r.get(col) for r in rows if r.get(col) is not None)
            if not vals:
                return None
            idx = min(len(vals) - 1, int(round(q * (len(vals) - 1))))
            return vals[idx]
        m = re.match(r"([a-zA-Z]+)\(([^()]*)\)$", expr)
        if not m:
            raise NotImplementedError(f"dry-run cannot evaluate expr: {expr}")
        fn, arg = m.group(1), m.group(2)
        if fn == "count":
            return len(rows)
        if fn == "countIf":
            col, cond = arg.split(",", 1)
            return sum(1 for r in rows if self._eval_where(cond.strip(), r))
        if fn in {"uniq", "uniqExact"}:
            return len({r.get(arg.strip().split(".")[-1]) for r in rows if r.get(arg.strip().split(".")[-1]) is not None})
        if fn == "uniqIf":
            col, cond = arg.split(",", 1)
            col = col.strip().split(".")[-1]
            return len({r.get(col) for r in rows if r.get(col) is not None and self._eval_where(cond.strip(), r)})
        if fn == "quantile":
            q, col = arg.split(",", 1) if "," in arg else ("0.5", arg)
            q = float(q.strip())
            col = col.strip().split(".")[-1]
            vals = sorted(r.get(col) for r in rows if r.get(col) is not None)
            if not vals:
                return None
            idx = min(len(vals) - 1, int(round(q * (len(vals) - 1))))
            return vals[idx]
        if fn in {"minIf", "maxIf"}:
            col, cond = arg.split(",", 1)
            col = col.strip().split(".")[-1]
            vals = [r.get(col) for r in rows if self._eval_where(cond.strip(), r) and r.get(col) is not None]
            return min(vals) if vals and fn == "minIf" else (max(vals) if vals else None)
        if fn == "min":
            vals = [r.get(arg.strip().split(".")[-1]) for r in rows if r.get(arg.strip().split(".")[-1]) is not None]
            return min(vals) if vals else None
        if fn == "max":
            vals = [r.get(arg.strip().split(".")[-1]) for r in rows if r.get(arg.strip().split(".")[-1]) is not None]
            return max(vals) if vals else None
        if fn == "sum":
            vals = [r.get(arg.strip().split(".")[-1]) or 0 for r in rows]
            return sum(vals)
        if fn == "avg":
            vals = [r.get(arg.strip().split(".")[-1]) for r in rows if r.get(arg.strip().split(".")[-1]) is not None]
            return sum(vals) / len(vals) if vals else None
        raise NotImplementedError(f"dry-run cannot evaluate fn: {fn}")
