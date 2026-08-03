"""Safe, generic ClickHouse read helpers for the chat agent.

Structured JSON args → server-built SELECT. No free-form SQL from the LLM.
Read-only SETTINGS, hard caps, identifier sanitization, single-table only.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from .ch_errors import TIMEOUT_QUERY, ClickHouseOpError
from .sqlsafe import sanitize_identifier, sql_string_literal

log = logging.getLogger("atlys.db_read")

# -- knobs -----------------------------------------------------------------
AGENT_QUERY_TIMEOUT_S = 15
AGGREGATE_MAX_LIMIT = 100
AGGREGATE_DEFAULT_LIMIT = 20
AGGREGATE_MAX_METRICS = 8
AGGREGATE_MAX_GROUP_BY = 4
AGGREGATE_MAX_FILTERS = 8
SAMPLE_MAX_LIMIT = 20
SAMPLE_DEFAULT_LIMIT = 5
SAMPLE_DEFAULT_COLUMNS = 12
TABLE_STATS_MAX_TABLES = 20
DB_SCHEMA_MAX_TABLES = 20
MAX_RESULT_BYTES = 2_097_152
MAX_IN_VALUES = 50
MAX_LIKE_LEN = 64
META_DATABASE = "meta"

METRIC_FNS = frozenset({"count", "uniq", "sum", "avg", "min", "max", "p50", "p90"})
FILTER_OPS = frozenset({"eq", "neq", "in", "gt", "gte", "lt", "lte", "like"})
# LLMs often emit SQL operators; normalize to FILTER_OPS before validation.
FILTER_OP_ALIASES = {
    "=": "eq",
    "==": "eq",
    "!=": "neq",
    "<>": "neq",
    ">": "gt",
    ">=": "gte",
    "<": "lt",
    "<=": "lte",
    "equals": "eq",
    "equal": "eq",
    "not_equals": "neq",
    "ne": "neq",
    "ge": "gte",
    "le": "lte",
}
_NUMERIC_TYPE = re.compile(r"(U?Int\d*|Float\d*|Decimal|Bool)", re.I)
_SETTINGS_TAIL = re.compile(r"\s+SETTINGS\s+.+$", re.I | re.S)


class DbReadError(Exception):
    """Structured validation / scope error for agent DB tools."""

    def __init__(self, message: str, code: str = "BAD_ARGUMENT"):
        super().__init__(message)
        self.message = message
        self.code = code

    def to_dict(self) -> dict[str, Any]:
        return {"error": self.message, "code": self.code, "retriable": False}


def _is_dry_run(store) -> bool:
    return getattr(store, "server_version", None) == "dry-run"


def _analytics_db(store) -> str:
    return sanitize_identifier(getattr(store, "database", None) or "atlys")


def _allowed_dbs(store, *, include_meta: bool) -> set[str]:
    dbs = {_analytics_db(store)}
    if include_meta:
        dbs.add(META_DATABASE)
    return dbs


def _parse_table_ref(table: str, store, *, include_meta: bool) -> tuple[str, str]:
    """Return (database, bare_table). Rejects system.* and disallowed DBs."""
    if not table or not isinstance(table, str):
        raise DbReadError("table is required", "BAD_ARGUMENT")
    raw = table.strip()
    try:
        sanitize_identifier(raw)
    except ValueError as e:
        raise DbReadError(str(e), "BAD_ARGUMENT") from e

    if "." in raw:
        db, name = raw.split(".", 1)
    else:
        db, name = _analytics_db(store), raw

    db = sanitize_identifier(db)
    name = sanitize_identifier(name)
    if db == "system":
        raise DbReadError("system tables are not queryable via agent tools", "DB_NOT_ALLOWED")
    if db not in _allowed_dbs(store, include_meta=include_meta):
        raise DbReadError(
            f"database {db!r} not allowed (pass include_meta=true for meta.*)",
            "DB_NOT_ALLOWED",
        )
    return db, name


def _qualified(db: str, table: str) -> str:
    return f"{sanitize_identifier(db)}.{sanitize_identifier(table)}"


def _column_map(store, db: str, table: str) -> dict[str, str]:
    """name → type for a table in db."""
    if db == _analytics_db(store) or _is_dry_run(store):
        cols = store.columns(table)
        if cols:
            return {c["name"]: str(c["type"]) for c in cols}
        if store.table_exists(table):
            return {}
        raise DbReadError(f"table not found: {db}.{table}", "NOT_FOUND")

    # Live meta (or other) DB — system.columns
    rows = store.query_rows(
        "SELECT name, type FROM system.columns "
        "WHERE database = {db:String} AND table = {tbl:String} ORDER BY position",
        {"db": db, "tbl": table},
    )
    if not rows:
        # confirm absence
        exists = store.query_rows(
            "SELECT 1 AS ok FROM system.tables "
            "WHERE database = {db:String} AND name = {tbl:String} LIMIT 1",
            {"db": db, "tbl": table},
        )
        if not exists:
            raise DbReadError(f"table not found: {db}.{table}", "NOT_FOUND")
        return {}
    return {r["name"]: str(r["type"]) for r in rows}


def _require_column(col_map: dict[str, str], column: str, *, what: str = "column") -> str:
    try:
        name = sanitize_identifier(column)
    except ValueError as e:
        raise DbReadError(str(e), "BAD_ARGUMENT") from e
    if name not in col_map:
        raise DbReadError(f"unknown {what}: {name!r}", "BAD_ARGUMENT")
    return name


def _is_numeric_type(ctype: str) -> bool:
    return bool(_NUMERIC_TYPE.search(ctype or ""))


def _strip_settings(sql: str) -> str:
    return _SETTINGS_TAIL.sub("", sql).rstrip().rstrip(";")


def _readonly_settings(*, limit: int, timeout_s: int = AGENT_QUERY_TIMEOUT_S) -> str:
    return (
        f" SETTINGS readonly = 1, max_execution_time = {int(timeout_s)}, "
        f"max_result_rows = {int(limit)}, max_result_bytes = {MAX_RESULT_BYTES}"
    )


def _run_select(store, sql: str) -> tuple[list[dict], int]:
    """Execute a SELECT; dry-run strips SETTINGS. Returns (rows, elapsed_ms)."""
    exec_sql = _strip_settings(sql) if _is_dry_run(store) else sql
    t0 = time.monotonic()
    try:
        rows = store.query_rows(exec_sql)
    except ClickHouseOpError as e:
        if e.error_class == TIMEOUT_QUERY:
            raise DbReadError(e.message or "query timed out", "TIMEOUT") from e
        raise
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if re.search(r"timeout|timed?\s*out|TIMEOUT", msg, re.I):
            raise DbReadError(msg, "TIMEOUT") from e
        raise
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    return rows, elapsed_ms


# -- public API ------------------------------------------------------------

def _coerce_table_names(table: Any, *, max_tables: int, required: bool) -> list[str] | None:
    """Normalize table / tables arg → list of names (or None if omitted)."""
    if table is None or table == "":
        if required:
            raise DbReadError("table is required", "BAD_ARGUMENT")
        return None
    if isinstance(table, list):
        names = [str(t).strip() for t in table if str(t).strip()]
    elif isinstance(table, str):
        text = table.strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError as e:
                raise DbReadError("table JSON array is invalid", "BAD_ARGUMENT") from e
            if not isinstance(parsed, list):
                raise DbReadError("table must be a string or list of strings", "BAD_ARGUMENT")
            names = [str(t).strip() for t in parsed if str(t).strip()]
        elif "," in text:
            names = [p.strip() for p in text.split(",") if p.strip()]
        else:
            names = [text]
    else:
        raise DbReadError("table must be a string or list of strings", "BAD_ARGUMENT")
    if not names:
        if required:
            raise DbReadError("table is required", "BAD_ARGUMENT")
        return None
    if len(names) > max_tables:
        raise DbReadError(f"at most {max_tables} tables per call", "BAD_ARGUMENT")
    return names


def _describe_one_table(
    store,
    raw: str,
    *,
    include_engine: bool,
    include_meta: bool,
) -> dict[str, Any]:
    db, name = _parse_table_ref(raw, store, include_meta=include_meta)
    col_map = _column_map(store, db, name)
    columns = [
        {"name": n, "type": t, "position": i}
        for i, (n, t) in enumerate(col_map.items())
    ]
    out: dict[str, Any] = {
        "database": db,
        "table": name,
        "columns": columns,
        "column_count": len(columns),
    }
    if include_engine and not _is_dry_run(store):
        meta = store.query_rows(
            "SELECT engine, sorting_key, partition_key FROM system.tables "
            "WHERE database = {db:String} AND name = {tbl:String} LIMIT 1",
            {"db": db, "tbl": name},
        )
        if meta:
            out["engine"] = meta[0].get("engine")
            out["sorting_key"] = meta[0].get("sorting_key") or ""
            out["partition_key"] = meta[0].get("partition_key") or ""
    elif include_engine:
        out["engine"] = "Memory"
    return out


def db_schema(
    store,
    *,
    table: str | list[str] | None = None,
    include_engine: bool = False,
    include_meta: bool = False,
) -> dict[str, Any]:
    """List tables, or describe one/many tables (columns) in a single call."""
    analytics = _analytics_db(store)
    names = _coerce_table_names(table, max_tables=DB_SCHEMA_MAX_TABLES, required=False)

    if names is not None:
        described = [
            _describe_one_table(
                store, n, include_engine=include_engine, include_meta=include_meta,
            )
            for n in names
        ]
        # Single-table: keep flat shape for backward compatibility.
        if len(described) == 1:
            return described[0]
        return {
            "database": analytics,
            "tables": described,
            "count": len(described),
        }

    tables: list[dict[str, Any]] = []
    for name in store.all_tables():
        entry: dict[str, Any] = {"name": name, "database": analytics}
        if include_engine and not _is_dry_run(store):
            meta = store.query_rows(
                "SELECT engine FROM system.tables "
                "WHERE database = {db:String} AND name = {tbl:String} LIMIT 1",
                {"db": analytics, "tbl": name},
            )
            if meta:
                entry["engine"] = meta[0].get("engine")
        tables.append(entry)

    if include_meta and not _is_dry_run(store):
        meta_rows = store.query_rows(
            "SELECT name, engine FROM system.tables "
            "WHERE database = {db:String} ORDER BY name",
            {"db": META_DATABASE},
        )
        for r in meta_rows:
            entry = {"name": r["name"], "database": META_DATABASE}
            if include_engine:
                entry["engine"] = r.get("engine")
            tables.append(entry)

    return {
        "database": analytics,
        "tables": tables,
        "count": len(tables),
        "include_meta": include_meta,
    }


def table_stats(
    store,
    table: str | list[str],
    *,
    approximate: bool = True,
    include_meta: bool = False,
) -> dict[str, Any]:
    """Row count / size summary for one or more tables."""
    names = _coerce_table_names(table, max_tables=TABLE_STATS_MAX_TABLES, required=True)
    assert names is not None

    stats: list[dict[str, Any]] = []
    for raw in names:
        db, name = _parse_table_ref(raw, store, include_meta=include_meta)
        col_map = _column_map(store, db, name)
        entry: dict[str, Any] = {
            "database": db,
            "table": name,
            "column_count": len(col_map),
            "approximate": approximate,
        }

        if approximate and not _is_dry_run(store):
            meta = store.query_rows(
                "SELECT engine, total_rows, total_bytes FROM system.tables "
                "WHERE database = {db:String} AND name = {tbl:String} LIMIT 1",
                {"db": db, "tbl": name},
            )
            if meta:
                entry["engine"] = meta[0].get("engine")
                entry["row_count"] = int(meta[0].get("total_rows") or 0)
                entry["bytes_on_disk"] = int(meta[0].get("total_bytes") or 0)
            else:
                entry["row_count"] = 0
                entry["bytes_on_disk"] = None
        else:
            # Exact count (or dry-run): analytics helpers when possible
            if db == _analytics_db(store) or _is_dry_run(store):
                entry["row_count"] = int(store.row_count(name))
            else:
                sql = (
                    f"SELECT count() AS c FROM {_qualified(db, name)}"
                    + _readonly_settings(limit=1)
                )
                rows, _ = _run_select(store, sql)
                entry["row_count"] = int(rows[0]["c"]) if rows else 0
            entry["bytes_on_disk"] = None
            if not _is_dry_run(store):
                meta = store.query_rows(
                    "SELECT engine FROM system.tables "
                    "WHERE database = {db:String} AND name = {tbl:String} LIMIT 1",
                    {"db": db, "tbl": name},
                )
                if meta:
                    entry["engine"] = meta[0].get("engine")
        stats.append(entry)

    return {"tables": stats, "count": len(stats)}


def _metric_sql(fn: str, column: str | None, alias: str, col_map: dict[str, str]) -> str:
    fn = (fn or "").lower().strip()
    if fn not in METRIC_FNS:
        raise DbReadError(f"unsupported metric fn: {fn!r}", "BAD_ARGUMENT")
    alias = sanitize_identifier(alias)

    if fn == "count":
        if column:
            col = _require_column(col_map, column)
            return f"count({col}) AS {alias}"
        return f"count() AS {alias}"

    if not column:
        raise DbReadError(f"metric {fn!r} requires column", "BAD_ARGUMENT")
    col = _require_column(col_map, column)
    ctype = col_map[col]

    if fn == "uniq":
        return f"uniqExact({col}) AS {alias}"
    if fn in {"sum", "avg", "min", "max", "p50", "p90"} and not _is_numeric_type(ctype):
        # min/max also useful on DateTime/String — allow min/max on any type
        if fn not in {"min", "max"}:
            raise DbReadError(
                f"metric {fn!r} requires a numeric column; {col!r} is {ctype}",
                "BAD_ARGUMENT",
            )
    if fn == "sum":
        return f"sum({col}) AS {alias}"
    if fn == "avg":
        return f"avg({col}) AS {alias}"
    if fn == "min":
        return f"min({col}) AS {alias}"
    if fn == "max":
        return f"max({col}) AS {alias}"
    if fn == "p50":
        return f"quantile(0.5)({col}) AS {alias}"
    if fn == "p90":
        return f"quantile(0.9)({col}) AS {alias}"
    raise DbReadError(f"unsupported metric fn: {fn!r}", "BAD_ARGUMENT")


def _default_metric_alias(fn: str, column: str | None, used: set[str]) -> str:
    base = fn if not column else f"{fn}_{column}"
    try:
        base = sanitize_identifier(base)
    except ValueError:
        base = fn
    alias = base
    n = 2
    while alias in used:
        alias = f"{base}_{n}"
        n += 1
    used.add(alias)
    return alias


def _literal_sql(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    text = str(value)
    if "\x00" in text:
        text = text.replace("\x00", "")
    return sql_string_literal(text)


def _normalize_filter_op(op: Any) -> str:
    """Map SQL-ish / verbose ops onto canonical FILTER_OPS names."""
    raw = str(op or "").strip()
    if not raw:
        raise DbReadError(
            "filter op is required (eq|neq|in|gt|gte|lt|lte|like; aliases: = != > >= < <=)",
            "BAD_ARGUMENT",
        )
    # Keep symbolic ops case-sensitive as written; word ops lowercased.
    key = raw if raw in FILTER_OP_ALIASES else raw.lower()
    if key in FILTER_OP_ALIASES:
        return FILTER_OP_ALIASES[key]
    if key in FILTER_OPS:
        return key
    raise DbReadError(
        f"unsupported filter op: {raw!r}; use eq|neq|in|gt|gte|lt|lte|like "
        f"(aliases: = != > >= < <=)",
        "BAD_ARGUMENT",
    )


def _filter_sql(filt: dict, col_map: dict[str, str]) -> str:
    if not isinstance(filt, dict):
        raise DbReadError("each filter must be an object", "BAD_ARGUMENT")
    column = filt.get("column")
    op = _normalize_filter_op(filt.get("op"))
    value = filt.get("value")
    col = _require_column(col_map, column, what="filter column")

    if op == "in":
        if not isinstance(value, (list, tuple)) or not value:
            raise DbReadError("op=in requires a non-empty array value", "BAD_ARGUMENT")
        if len(value) > MAX_IN_VALUES:
            raise DbReadError(f"op=in allows at most {MAX_IN_VALUES} values", "BAD_ARGUMENT")
        parts = ", ".join(_literal_sql(v) for v in value)
        return f"{col} IN ({parts})"

    if op == "like":
        text = str(value)
        if len(text) > MAX_LIKE_LEN:
            raise DbReadError(f"like pattern max length is {MAX_LIKE_LEN}", "BAD_ARGUMENT")
        return f"{col} LIKE {sql_string_literal(text)}"

    lit = _literal_sql(value)
    mapping = {
        "eq": "=",
        "neq": "!=",
        "gt": ">",
        "gte": ">=",
        "lt": "<",
        "lte": "<=",
    }
    return f"{col} {mapping[op]} {lit}"


def build_aggregate_sql(
    store,
    *,
    table: str,
    metrics: list[dict],
    group_by: list[str] | None = None,
    filters: list[dict] | None = None,
    order_by: list[dict] | None = None,
    limit: int | None = None,
    include_meta: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Validate + build aggregate SELECT. Returns (sql, meta)."""
    db, name = _parse_table_ref(table, store, include_meta=include_meta)
    col_map = _column_map(store, db, name)
    if not metrics or not isinstance(metrics, list):
        raise DbReadError("metrics must be a non-empty array", "BAD_ARGUMENT")
    if len(metrics) > AGGREGATE_MAX_METRICS:
        raise DbReadError(f"at most {AGGREGATE_MAX_METRICS} metrics", "BAD_ARGUMENT")

    group_by = group_by or []
    filters = filters or []
    order_by = order_by or []
    if not isinstance(group_by, list) or len(group_by) > AGGREGATE_MAX_GROUP_BY:
        raise DbReadError(f"group_by allows at most {AGGREGATE_MAX_GROUP_BY} columns", "BAD_ARGUMENT")
    if not isinstance(filters, list) or len(filters) > AGGREGATE_MAX_FILTERS:
        raise DbReadError(f"filters allows at most {AGGREGATE_MAX_FILTERS} predicates", "BAD_ARGUMENT")
    if not isinstance(order_by, list) or len(order_by) > 2:
        raise DbReadError("order_by allows at most 2 keys", "BAD_ARGUMENT")

    lim = AGGREGATE_DEFAULT_LIMIT if limit is None else int(limit)
    if lim < 1:
        raise DbReadError("limit must be >= 1", "BAD_ARGUMENT")
    if lim > AGGREGATE_MAX_LIMIT:
        lim = AGGREGATE_MAX_LIMIT

    used_aliases: set[str] = set()
    select_parts: list[str] = []
    group_cols: list[str] = []
    for g in group_by:
        gc = _require_column(col_map, g, what="group_by column")
        group_cols.append(gc)
        select_parts.append(gc)
        used_aliases.add(gc)

    metric_aliases: list[str] = []
    for m in metrics:
        if not isinstance(m, dict):
            raise DbReadError("each metric must be an object", "BAD_ARGUMENT")
        fn = (m.get("fn") or "").lower().strip()
        column = m.get("column")
        if m.get("alias"):
            try:
                alias = sanitize_identifier(str(m["alias"]))
            except ValueError as e:
                raise DbReadError(str(e), "BAD_ARGUMENT") from e
            if alias in used_aliases:
                alias = _default_metric_alias(fn, column, used_aliases)
            else:
                used_aliases.add(alias)
        else:
            alias = _default_metric_alias(fn, column, used_aliases)
        select_parts.append(_metric_sql(fn, column, alias, col_map))
        metric_aliases.append(alias)

    where_parts = [_filter_sql(f, col_map) for f in filters]

    order_parts: list[str] = []
    for ob in order_by:
        if not isinstance(ob, dict):
            raise DbReadError("each order_by must be an object", "BAD_ARGUMENT")
        by = ob.get("by")
        direction = (ob.get("dir") or "desc").lower().strip()
        if direction not in {"asc", "desc"}:
            raise DbReadError("order_by.dir must be asc or desc", "BAD_ARGUMENT")
        try:
            by_id = sanitize_identifier(str(by))
        except ValueError as e:
            raise DbReadError(str(e), "BAD_ARGUMENT") from e
        if by_id not in used_aliases and by_id not in col_map:
            raise DbReadError(f"order_by references unknown column/alias: {by_id!r}", "BAD_ARGUMENT")
        order_parts.append(f"{by_id} {direction.upper()}")

    sql = f"SELECT {', '.join(select_parts)} FROM {_qualified(db, name)}"
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    if group_cols:
        sql += " GROUP BY " + ", ".join(group_cols)
    if order_parts:
        sql += " ORDER BY " + ", ".join(order_parts)
    sql += f" LIMIT {lim}"
    sql += _readonly_settings(limit=lim)

    meta = {
        "database": db,
        "table": name,
        "limit": lim,
        "metric_aliases": metric_aliases,
        "group_by": group_cols,
    }
    return sql, meta


def aggregate(store, **kwargs) -> dict[str, Any]:
    """Run a constrained single-table aggregation."""
    sql, meta = build_aggregate_sql(store, **kwargs)
    rows, elapsed_ms = _run_select(store, sql)
    # Normalize to list-of-dicts already; also provide list-of-lists for compact use
    columns = list(rows[0].keys()) if rows else (meta["group_by"] + meta["metric_aliases"])
    return {
        "sql": _strip_settings(sql),
        "database": meta["database"],
        "table": meta["table"],
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "limit": meta["limit"],
        "elapsed_ms": elapsed_ms,
    }


def sample_rows(
    store,
    *,
    table: str,
    columns: list[str] | None = None,
    filters: list[dict] | None = None,
    limit: int | None = None,
    order_by: dict | str | None = None,
    include_meta: bool = False,
) -> dict[str, Any]:
    """Tiny row preview."""
    db, name = _parse_table_ref(table, store, include_meta=include_meta)
    col_map = _column_map(store, db, name)
    if not col_map and not store.table_exists(name) and db == _analytics_db(store):
        raise DbReadError(f"table not found: {db}.{name}", "NOT_FOUND")

    filters = filters or []
    if not isinstance(filters, list) or len(filters) > AGGREGATE_MAX_FILTERS:
        raise DbReadError(f"filters allows at most {AGGREGATE_MAX_FILTERS} predicates", "BAD_ARGUMENT")

    lim = SAMPLE_DEFAULT_LIMIT if limit is None else int(limit)
    if lim < 1:
        raise DbReadError("limit must be >= 1", "BAD_ARGUMENT")
    if lim > SAMPLE_MAX_LIMIT:
        lim = SAMPLE_MAX_LIMIT

    if columns:
        if not isinstance(columns, list) or not columns:
            raise DbReadError("columns must be a non-empty array when provided", "BAD_ARGUMENT")
        if len(columns) > SAMPLE_DEFAULT_COLUMNS:
            columns = columns[:SAMPLE_DEFAULT_COLUMNS]
        select_cols = [_require_column(col_map, c) for c in columns]
    else:
        select_cols = list(col_map.keys())[:SAMPLE_DEFAULT_COLUMNS]
        if not select_cols:
            select_cols = ["*"]  # pragma: no cover - empty schema edge

    where_parts = [_filter_sql(f, col_map) for f in filters]

    order_sql = ""
    if order_by:
        if isinstance(order_by, str):
            by, direction = order_by, "desc"
        elif isinstance(order_by, dict):
            by, direction = order_by.get("by"), (order_by.get("dir") or "desc").lower()
        else:
            raise DbReadError("order_by must be a string or object", "BAD_ARGUMENT")
        if direction not in {"asc", "desc"}:
            raise DbReadError("order_by.dir must be asc or desc", "BAD_ARGUMENT")
        by_id = _require_column(col_map, str(by), what="order_by column")
        order_sql = f" ORDER BY {by_id} {direction.upper()}"

    cols_sql = ", ".join(select_cols)
    sql = f"SELECT {cols_sql} FROM {_qualified(db, name)}"
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    sql += order_sql
    sql += f" LIMIT {lim}"
    sql += _readonly_settings(limit=lim)

    rows, elapsed_ms = _run_select(store, sql)
    return {
        "sql": _strip_settings(sql),
        "database": db,
        "table": name,
        "columns": select_cols if select_cols != ["*"] else (list(rows[0].keys()) if rows else []),
        "rows": rows,
        "row_count": len(rows),
        "limit": lim,
        "elapsed_ms": elapsed_ms,
    }


def tool_error(exc: BaseException) -> dict[str, Any]:
    """Map exceptions to MCP-friendly error dicts."""
    if isinstance(exc, DbReadError):
        return exc.to_dict()
    if isinstance(exc, ClickHouseOpError):
        code = "TIMEOUT" if exc.error_class == TIMEOUT_QUERY else "QUERY_FAILED"
        return {"error": exc.message, "code": code, "retriable": bool(exc.retryable)}
    return {"error": str(exc), "code": "QUERY_FAILED", "retriable": False}
