"""LibreChat data plane: trend / contributor / pivot + dimension values."""

from __future__ import annotations

import re
import time
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any, Optional

from conversation_agent import cache as analytics_cache
from conversation_agent import catalog
from conversation_agent.clickhouse_client import run_query
from conversation_agent.models import (
    AnalyticsDataPayload,
    AnalyticsDataRequest,
    AnalyticsDataResponse,
    AnalyticsDimensionFilter,
    AnalyticsDimensionsRequest,
    AnalyticsDimensionsResponse,
    DataInsightType,
    DataTimeGrain,
)

_IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DIMENSION_LIMIT = 50

_GRAIN_START = {
    "day": "toStartOfDay",
    "week": "toStartOfWeek",
    "month": "toStartOfMonth",
}


def _quote_str(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _validate_date(value: str, *, field: str) -> str:
    if not _DATE_RE.match(value):
        raise ValueError(f"{field} must be YYYY-MM-DD, got {value!r}")
    date.fromisoformat(value)
    return value


def _quote_ident(name: str) -> str:
    if not _IDENT_RE.match(name):
        raise ValueError(f"Invalid identifier: {name!r}")
    return name


def _resolve_column(dim_key: str) -> tuple[str, str]:
    """Return (wire_key, physical_column). Unknown keys pass through if valid ident."""
    d = catalog.resolve_dimension(dim_key)
    if d:
        return d.key, d.column
    if _IDENT_RE.match(dim_key):
        return dim_key, dim_key
    raise ValueError(f"Unknown dimension: {dim_key!r}")


def _metric_or_raise(metric_name: str) -> catalog.MetricDef:
    m = catalog.resolve_metric(metric_name)
    if m is None:
        raise ValueError(
            f"Unknown metric {metric_name!r}. "
            f"Allowed: {', '.join(catalog.METRICS)}"
        )
    return m


def _table_for_metric(metric: catalog.MetricDef) -> str:
    return catalog.qualified_table(metric.table)


def _default_table() -> str:
    return catalog.qualified_table(catalog.ACTIVITY_TABLE)


def _infer_grain(fromtime: str, totime: str, grain: Optional[DataTimeGrain]) -> DataTimeGrain:
    if grain in ("day", "week", "month"):
        return grain
    start = date.fromisoformat(fromtime)
    end = date.fromisoformat(totime)
    span = (end - start).days
    if span <= 45:
        return "day"
    if span <= 120:
        return "week"
    return "month"


def _bucket_end(bucket_start: date, grain: DataTimeGrain, window_end: date) -> date:
    if grain == "day":
        end = bucket_start
    elif grain == "week":
        end = bucket_start + timedelta(days=6)
    else:
        last = monthrange(bucket_start.year, bucket_start.month)[1]
        end = date(bucket_start.year, bucket_start.month, last)
    return min(end, window_end)


def _filters_sql(
    filters: Optional[list[AnalyticsDimensionFilter]],
) -> list[str]:
    preds: list[str] = []
    for f in filters or []:
        _, col = _resolve_column(f.key)
        preds.append(f"{_quote_ident(col)} = {_quote_str(f.value)}")
    return preds


def _time_and_filters_where(
    *,
    fromtime: str,
    totime: str,
    filters: Optional[list[AnalyticsDimensionFilter]],
    event_filter: Optional[str] = None,
) -> str:
    parts = [
        f"timestamp >= toDateTime({_quote_str(fromtime)})",
        f"timestamp < toDateTime({_quote_str(totime)}) + INTERVAL 1 DAY",
        *_filters_sql(filters),
    ]
    if event_filter:
        parts.append(f"event_name = {_quote_str(event_filter)}")
    return " AND ".join(parts)


def _column_exists(table: str, column: str) -> bool:
    """Check system.columns for physical presence."""
    from conversation_agent import config

    if "." in table:
        db, name = table.split(".", 1)
    else:
        db, name = config.CLICKHOUSE_DATABASE, table
    sql = f"""
SELECT count()
FROM system.columns
WHERE database = {_quote_str(db)}
  AND table = {_quote_str(name)}
  AND name = {_quote_str(column)}
""".strip()
    try:
        _cols, rows = run_query(sql)
        return bool(rows and int(rows[0][0]) > 0)
    except Exception:
        return False


def build_trend_sql(
    payload: AnalyticsDataPayload,
    *,
    metric: catalog.MetricDef,
    grain: DataTimeGrain,
) -> str:
    table = _table_for_metric(metric)
    where = _time_and_filters_where(
        fromtime=payload.fromtime,
        totime=payload.totime,
        filters=payload.filters,
        event_filter=metric.event_filter,
    )
    start_fn = _GRAIN_START[grain]
    metric_alias = _quote_ident(metric.key)
    return f"""
SELECT
    {start_fn}(timestamp) AS bucket,
    {metric.expression} AS {metric_alias}
FROM {table}
WHERE {where}
GROUP BY bucket
ORDER BY bucket
""".strip()


def build_contributor_sql(
    payload: AnalyticsDataPayload,
    *,
    metric: catalog.MetricDef,
    dim_column: str,
    limit: int = _DIMENSION_LIMIT,
) -> str:
    table = _table_for_metric(metric)
    where = _time_and_filters_where(
        fromtime=payload.fromtime,
        totime=payload.totime,
        filters=payload.filters,
        event_filter=metric.event_filter,
    )
    col = _quote_ident(dim_column)
    return f"""
SELECT
    {col} AS member,
    {metric.expression} AS value
FROM {table}
WHERE {where}
  AND {col} IS NOT NULL
  AND toString({col}) != ''
GROUP BY member
ORDER BY value DESC
LIMIT {int(limit)}
""".strip()


def build_pivot_sql(
    payload: AnalyticsDataPayload,
    *,
    metric: catalog.MetricDef,
    row_column: str,
    col_column: str,
    limit: int = 500,
) -> str:
    table = _table_for_metric(metric)
    where = _time_and_filters_where(
        fromtime=payload.fromtime,
        totime=payload.totime,
        filters=payload.filters,
        event_filter=metric.event_filter,
    )
    r = _quote_ident(row_column)
    c = _quote_ident(col_column)
    metric_alias = _quote_ident(metric.key)
    return f"""
SELECT
    {r} AS row_member,
    {c} AS col_member,
    {metric.expression} AS {metric_alias}
FROM {table}
WHERE {where}
  AND {r} IS NOT NULL AND toString({r}) != ''
  AND {c} IS NOT NULL AND toString({c}) != ''
GROUP BY row_member, col_member
ORDER BY {metric_alias} DESC
LIMIT {int(limit)}
""".strip()


def build_dimension_values_sql(
    *,
    table: str,
    column: str,
    fromtime: Optional[str],
    totime: Optional[str],
    filters: Optional[list[AnalyticsDimensionFilter]],
    event_filter: Optional[str] = None,
    limit: int = _DIMENSION_LIMIT,
) -> str:
    col = _quote_ident(column)
    parts: list[str] = [
        f"{col} IS NOT NULL",
        f"toString({col}) != ''",
    ]
    if fromtime and totime:
        _validate_date(fromtime, field="fromtime")
        _validate_date(totime, field="totime")
        parts.append(f"timestamp >= toDateTime({_quote_str(fromtime)})")
        parts.append(f"timestamp < toDateTime({_quote_str(totime)}) + INTERVAL 1 DAY")
    parts.extend(_filters_sql(filters))
    if event_filter:
        parts.append(f"event_name = {_quote_str(event_filter)}")
    where = " AND ".join(parts)
    return f"""
SELECT
    {col} AS member,
    count() AS c
FROM {table}
WHERE {where}
GROUP BY member
ORDER BY c DESC
LIMIT {int(limit)}
""".strip()


def _shape_trend_rows(
    columns: list[str],
    rows: list[list[Any]],
    *,
    metric_name: str,
    grain: DataTimeGrain,
    window_end: date,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        mapping = dict(zip(columns, row))
        bucket = mapping.get("bucket")
        if isinstance(bucket, datetime):
            bucket_d = bucket.date()
        elif isinstance(bucket, date):
            bucket_d = bucket
        else:
            bucket_d = date.fromisoformat(str(bucket)[:10])
        end_d = _bucket_end(bucket_d, grain, window_end)
        value = mapping.get(metric_name, mapping.get(columns[-1]))
        try:
            num = float(value) if value is not None else 0.0
        except (TypeError, ValueError):
            num = 0.0
        out.append(
            {
                "fromtime": bucket_d.isoformat(),
                "totime": end_d.isoformat(),
                metric_name: num,
            }
        )
    return out


def _shape_contributor_rows(
    columns: list[str],
    rows: list[list[Any]],
    *,
    fromtime: str,
    totime: str,
) -> list[dict[str, Any]]:
    wide: dict[str, Any] = {"fromtime": fromtime, "totime": totime}
    for row in rows:
        mapping = dict(zip(columns, row))
        member = str(mapping.get("member", ""))
        if not member:
            continue
        value = mapping.get("value", 0)
        try:
            wide[member] = float(value) if value is not None else 0.0
        except (TypeError, ValueError):
            wide[member] = 0.0
    return [wide]


def _shape_pivot_rows(
    columns: list[str],
    rows: list[list[Any]],
    *,
    row_dim: str,
    col_dim: str,
    metric_name: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        mapping = dict(zip(columns, row))
        value = mapping.get(metric_name, mapping.get("value", mapping.get(columns[-1])))
        try:
            num = float(value) if value is not None else 0.0
        except (TypeError, ValueError):
            num = 0.0
        out.append(
            {
                row_dim: str(mapping.get("row_member", "")),
                col_dim: str(mapping.get("col_member", "")),
                metric_name: num,
            }
        )
    return out


def fetch_insight_data(request: AnalyticsDataRequest) -> AnalyticsDataResponse:
    """Execute trend/contributor/pivot and shape rows for da-insight-sdk."""
    t0 = time.perf_counter()
    try:
        result = _fetch_insight_data_uncached(request)
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"ClickHouse query failed: {exc}") from exc

    result.latency_ms = int((time.perf_counter() - t0) * 1000)
    return result


def _fetch_insight_data_uncached(request: AnalyticsDataRequest) -> AnalyticsDataResponse:
    payload = request.payload
    insight: DataInsightType = request.insight_type
    _validate_date(payload.fromtime, field="fromtime")
    _validate_date(payload.totime, field="totime")
    metric = _metric_or_raise(payload.metric_name)
    grain = _infer_grain(payload.fromtime, payload.totime, payload.timegrain)
    window_end = date.fromisoformat(payload.totime)
    dims = list(payload.dimensions or [])

    if insight == "trend":
        sql = build_trend_sql(payload, metric=metric, grain=grain)
        columns, rows = run_query(sql)
        data = _shape_trend_rows(
            columns,
            rows,
            metric_name=metric.key,
            grain=grain,
            window_end=window_end,
        )
        return AnalyticsDataResponse(data=data, query=sql)

    if insight == "contributor":
        if not dims:
            raise ValueError("contributor requires payload.dimensions[0]")
        wire_key, col = _resolve_column(dims[0])
        sql = build_contributor_sql(payload, metric=metric, dim_column=col)
        columns, rows = run_query(sql)
        data = _shape_contributor_rows(
            columns,
            rows,
            fromtime=payload.fromtime,
            totime=payload.totime,
        )
        return AnalyticsDataResponse(data=data, query=sql)

    if insight == "pivot":
        if len(dims) < 2:
            raise ValueError("pivot requires payload.dimensions[row, col]")
        row_wire, row_col = _resolve_column(dims[0])
        col_wire, col_col = _resolve_column(dims[1])
        sql = build_pivot_sql(
            payload, metric=metric, row_column=row_col, col_column=col_col
        )
        columns, rows = run_query(sql)
        data = _shape_pivot_rows(
            columns,
            rows,
            row_dim=row_wire,
            col_dim=col_wire,
            metric_name=metric.key,
        )
        return AnalyticsDataResponse(data=data, query=sql)

    return AnalyticsDataResponse(data=[], query=None)


def fetch_dimension_values(
    request: AnalyticsDimensionsRequest,
) -> AnalyticsDimensionsResponse:
    """Ordered dimension members from raw table; fallback extract-from-data."""
    t0 = time.perf_counter()
    cache_payload = request.model_dump(mode="json")
    key = analytics_cache.cache_key("dimensions", cache_payload)
    cached = analytics_cache.get(key)
    if isinstance(cached, dict):
        return AnalyticsDimensionsResponse.model_validate(cached)

    try:
        result = _fetch_dimension_values_uncached(request)
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"ClickHouse dimensions failed: {exc}") from exc

    latency_ms = int((time.perf_counter() - t0) * 1000)
    result.latency_ms = latency_ms
    analytics_cache.set(key, result.model_dump(mode="json"))
    return result


def _fetch_dimension_values_uncached(
    request: AnalyticsDimensionsRequest,
) -> AnalyticsDimensionsResponse:
    wire_key, column = _resolve_column(request.dimension)
    metric = (
        catalog.resolve_metric(request.metric_name)
        if request.metric_name
        else catalog.resolve_metric("users")
    )
    table = (
        catalog.qualified_table(metric.table)
        if metric
        else _default_table()
    )
    event_filter = metric.event_filter if metric else None

    # Prefer raw table that owns the dimension when catalog knows it
    dim_def = catalog.resolve_dimension(request.dimension)
    if dim_def:
        table = catalog.qualified_table(dim_def.table)
        column = dim_def.column
        wire_key = dim_def.key

    values: list[str] = []
    used_fallback = False

    if _column_exists(table, column):
        sql = build_dimension_values_sql(
            table=table,
            column=column,
            fromtime=request.fromtime,
            totime=request.totime,
            filters=request.filters,
            event_filter=event_filter if catalog.ACTIVITY_TABLE in table else None,
        )
        try:
            _cols, rows = run_query(sql)
            values = [str(r[0]) for r in rows if r and r[0] is not None and str(r[0])]
        except Exception:
            used_fallback = True
    else:
        used_fallback = True

    if used_fallback or not values:
        # Extract from data: contributor-style GROUP BY on best-effort column
        fromtime = request.fromtime or "2026-01-01"
        totime = request.totime or "2026-06-30"
        metric_name = (metric.key if metric else "users")
        payload = AnalyticsDataPayload(
            fromtime=fromtime,
            totime=totime,
            metric_name=metric_name,
            dimensions=[request.dimension],
            filters=request.filters,
        )
        try:
            # If column missing on primary table, try activity_events with same name
            fallback_table = _default_table()
            if _column_exists(fallback_table, column):
                sql = build_dimension_values_sql(
                    table=fallback_table,
                    column=column,
                    fromtime=fromtime,
                    totime=totime,
                    filters=request.filters,
                )
                _cols, rows = run_query(sql)
                values = [
                    str(r[0]) for r in rows if r and r[0] is not None and str(r[0])
                ]
            else:
                # Last resort: run contributor and take member keys from wide row
                m = _metric_or_raise(metric_name)
                # Try querying with the raw wire key as column even if system.columns missed
                sql = build_contributor_sql(payload, metric=m, dim_column=column)
                try:
                    columns, rows = run_query(sql)
                    shaped = _shape_contributor_rows(
                        columns, rows, fromtime=fromtime, totime=totime
                    )
                    if shaped:
                        values = [
                            k
                            for k in shaped[0].keys()
                            if k not in {"fromtime", "totime"}
                        ]
                except Exception:
                    values = []
        except Exception:
            values = values or []

    return AnalyticsDimensionsResponse(dimension=wire_key, values=values)
