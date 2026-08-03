"""Deterministic ClickHouse SQL builders from a typed AnalyticsPlan."""

from __future__ import annotations

import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from conversation_agent import config

AnalyticsKind = Literal[
    "funnel",
    "timeseries",
    "breakdown",
    "metric",
    "top_n",
    "comparison",
]

ALLOWED_SEGMENTS = frozenset(
    {
        "device_type",
        "os",
        "geoip_country_code",
        "destination",
        "event_name",
        "application_id",
    }
)

# SAS event discriminator column (not the AnalyticsPlan.event_names list field)
EVENT_COL = "event_name"
# Live activity_events.timestamp is DateTime64(3); windowFunnel needs DateTime/UInt
FUNNEL_TS = "toDateTime(timestamp)"

CORE_FUNNEL_STEPS = [
    "destination_card_clicked",
    "application_started",
    "document_uploaded",
    "purchase_completed",
]

_EVENT_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")
_LAST_DAYS_RE = re.compile(r"last[_\s-]?(\d+)[_\s-]?days?", re.I)


class AnalyticsPlan(BaseModel):
    """Structured analytics intent — builders turn this into SQL."""

    kind: AnalyticsKind
    event_names: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    metric_names: list[str] = Field(default_factory=list)
    time_window: Optional[str] = Field(
        default="last_30_days",
        description="e.g. last_7_days, last_30_days",
    )
    window_seconds: int = Field(default=86400, description="windowFunnel window")
    filters: dict[str, Any] = Field(default_factory=dict)
    table: str = Field(default="")
    limit: int = Field(default=20, ge=1, le=500)
    title: Optional[str] = None


class BuildResult(BaseModel):
    sql: str
    tables_used: list[str]
    caveats: Optional[str] = None
    step_names: list[str] = Field(default_factory=list)
    window_seconds: Optional[int] = None


def _qualified_table(table: str | None = None) -> str:
    raw = (table or "").strip() or config.activity_table_fqn()
    if "." not in raw:
        raw = f"{config.CLICKHOUSE_DATABASE}.{raw}"
    # allowlist simple identifiers
    parts = raw.split(".")
    if len(parts) != 2 or not all(_EVENT_RE.match(p) for p in parts):
        raise ValueError(f"Invalid table name: {table!r}")
    return raw


def _quote_ident(name: str) -> str:
    if name not in ALLOWED_SEGMENTS and not _EVENT_RE.match(name):
        raise ValueError(f"Disallowed identifier: {name!r}")
    return name


def _quote_str(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _validate_events(events: list[str]) -> list[str]:
    out: list[str] = []
    for e in events:
        e = e.strip()
        if not e or not _EVENT_RE.match(e):
            raise ValueError(f"Invalid event name: {e!r}")
        out.append(e)
    return out


def _parse_last_days(time_window: str | None) -> int:
    if not time_window:
        return 30
    m = _LAST_DAYS_RE.search(time_window.replace(" ", "_"))
    if m:
        return max(1, min(int(m.group(1)), 365))
    return 30


def _time_predicate(time_window: str | None, *, table: str) -> str:
    """Window relative to max(timestamp) in the table (contest data is historical)."""
    days = _parse_last_days(time_window)
    # now() often sits after the dataset end → empty results; anchor to data.
    return (
        f"timestamp >= (SELECT max(timestamp) FROM {table}) - INTERVAL {days} DAY "
        f"AND timestamp <= (SELECT max(timestamp) FROM {table})"
    )


def _filter_predicates(filters: dict[str, Any]) -> list[str]:
    preds: list[str] = []
    for key, value in (filters or {}).items():
        if key in {"start_date", "end_date", "segment"}:
            continue
        col = _quote_ident(str(key))
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            vals = ", ".join(_quote_str(str(v)) for v in value)
            preds.append(f"{col} IN ({vals})")
        else:
            preds.append(f"{col} = {_quote_str(str(value))}")
    return preds


def _where_clause(
    time_window: str | None, filters: dict[str, Any], *, table: str
) -> str:
    parts = [_time_predicate(time_window, table=table), *_filter_predicates(filters)]
    return " AND ".join(parts)


def build_funnel_sql(plan: AnalyticsPlan) -> BuildResult:
    steps = _validate_events(plan.event_names) or list(CORE_FUNNEL_STEPS)
    if len(steps) < 2:
        raise ValueError("funnel requires at least 2 event_names")

    table = _qualified_table(plan.table)
    segment = plan.dimensions[0] if plan.dimensions else None
    if segment:
        segment = _quote_ident(segment)

    conditions = ",\n            ".join(
        f"{EVENT_COL} = {_quote_str(s)}" for s in steps
    )
    where = _where_clause(plan.time_window, plan.filters, table=table)
    window = int(plan.window_seconds)

    if segment:
        inner_seg = f"any({segment}) AS {segment},"
        outer_group = f"GROUP BY {segment}\nORDER BY {segment}"
        outer_select_seg = f"    {segment},\n"
    else:
        inner_seg = ""
        outer_group = ""
        outer_select_seg = ""

    step_cols = []
    for i, name in enumerate(steps, start=1):
        step_cols.append(f"countIf(level >= {i}) AS entities_step_{i}")
    conv = (
        f"countIf(level >= {len(steps)}) / nullIf(countIf(level >= 1), 0) "
        f"AS conversion_from_start"
    )

    sql = f"""-- window: {window} seconds (cast DateTime64 → DateTime for windowFunnel)
WITH funnel_levels AS (
    SELECT
        user_id,
        {inner_seg}
        windowFunnel({window})(
            {FUNNEL_TS},
            {conditions}
        ) AS level
    FROM {table}
    WHERE {where}
    GROUP BY user_id
)
SELECT
{outer_select_seg}    {", ".join(step_cols)},
    {conv}
FROM funnel_levels
{outer_group}
""".strip()

    return BuildResult(
        sql=sql,
        tables_used=[table.split(".")[-1]],
        caveats=(
            f"windowFunnel({FUNNEL_TS}) on {table.split('.')[-1]} ({EVENT_COL}); "
            "timestamp is DateTime64(3) — cast required; "
            "payload fields live in payload (JSONExtract when needed)"
        ),
        step_names=steps,
        window_seconds=window,
    )


def build_timeseries_sql(plan: AnalyticsPlan) -> BuildResult:
    events = _validate_events(plan.event_names)
    table = _qualified_table(plan.table)
    where = _where_clause(plan.time_window, plan.filters, table=table)
    if events:
        ev_list = ", ".join(_quote_str(e) for e in events)
        where = f"{where} AND {EVENT_COL} IN ({ev_list})"

    sql = f"""
SELECT
    toStartOfDay(timestamp) AS day,
    {EVENT_COL},
    count() AS events,
    uniqExact(user_id) AS users
FROM {table}
WHERE {where}
GROUP BY day, {EVENT_COL}
ORDER BY day, {EVENT_COL}
""".strip()

    return BuildResult(
        sql=sql,
        tables_used=[table.split(".")[-1]],
        caveats="Daily grain; uniqExact(user_id) per event_name",
        step_names=events,
    )


def build_breakdown_sql(plan: AnalyticsPlan) -> BuildResult:
    events = _validate_events(plan.event_names)
    if not plan.dimensions:
        raise ValueError("breakdown requires at least one dimension")
    dims = [_quote_ident(d) for d in plan.dimensions]
    table = _qualified_table(plan.table)
    where = _where_clause(plan.time_window, plan.filters, table=table)
    if events:
        ev_list = ", ".join(_quote_str(e) for e in events)
        where = f"{where} AND {EVENT_COL} IN ({ev_list})"

    dim_select = ", ".join(dims)
    sql = f"""
SELECT
    {dim_select},
    count() AS events,
    uniqExact(user_id) AS users
FROM {table}
WHERE {where}
GROUP BY {dim_select}
ORDER BY users DESC
LIMIT {int(plan.limit)}
""".strip()

    return BuildResult(
        sql=sql,
        tables_used=[table.split(".")[-1]],
        caveats=None,
        step_names=events,
    )


def build_metric_sql(plan: AnalyticsPlan) -> BuildResult:
    """Rate / count metrics. event_names: [numerator, denominator] for rates."""
    events = _validate_events(plan.event_names)
    table = _qualified_table(plan.table)
    where = _where_clause(plan.time_window, plan.filters, table=table)
    dims = [_quote_ident(d) for d in plan.dimensions] if plan.dimensions else []

    if len(events) >= 2:
        num_e, den_e = events[0], events[1]
        metric_select = (
            f"uniqExactIf(user_id, {EVENT_COL} = {_quote_str(num_e)}) AS numerator_users,\n"
            f"    uniqExactIf(user_id, {EVENT_COL} = {_quote_str(den_e)}) AS denominator_users,\n"
            f"    uniqExactIf(user_id, {EVENT_COL} = {_quote_str(num_e)}) "
            f"/ nullIf(uniqExactIf(user_id, {EVENT_COL} = {_quote_str(den_e)}), 0) AS rate"
        )
        where = (
            f"{where} AND {EVENT_COL} IN ({_quote_str(num_e)}, {_quote_str(den_e)})"
        )
        caveats = f"rate = uniq({num_e}) / uniq({den_e})"
        order_col = "rate"
    elif len(events) == 1:
        e = events[0]
        metric_select = (
            f"countIf({EVENT_COL} = {_quote_str(e)}) AS events,\n"
            f"    uniqExactIf(user_id, {EVENT_COL} = {_quote_str(e)}) AS users"
        )
        where = f"{where} AND {EVENT_COL} = {_quote_str(e)}"
        caveats = f"counts for event_name {e}"
        order_col = "users"
    else:
        metric_select = "count() AS events,\n    uniqExact(user_id) AS users"
        caveats = "overall event/user counts in window"
        order_col = "users"

    if dims:
        dim_select = ", ".join(dims) + ",\n    "
        group = f"GROUP BY {', '.join(dims)}\nORDER BY {order_col} DESC"
    else:
        dim_select = ""
        group = ""

    sql = f"""
SELECT
    {dim_select}{metric_select}
FROM {table}
WHERE {where}
{group}
""".strip()

    return BuildResult(
        sql=sql,
        tables_used=[table.split(".")[-1]],
        caveats=caveats,
        step_names=events,
    )


def build_top_n_sql(plan: AnalyticsPlan) -> BuildResult:
    if not plan.dimensions:
        raise ValueError("top_n requires a dimension (e.g. destination)")
    # Reuse breakdown with limit
    return build_breakdown_sql(plan)


def build_comparison_sql(plan: AnalyticsPlan) -> BuildResult:
    """Compare two halves of the time window for the same metric/events."""
    events = _validate_events(plan.event_names)
    table = _qualified_table(plan.table)
    days = _parse_last_days(plan.time_window)
    half = max(1, days // 2)
    event_pred = ""
    if events:
        ev_list = ", ".join(_quote_str(e) for e in events)
        event_pred = f" AND {EVENT_COL} IN ({ev_list})"

    sql = f"""
SELECT
    multiIf(
        timestamp >= (SELECT max(timestamp) FROM {table}) - INTERVAL {days} DAY
            AND timestamp < (SELECT max(timestamp) FROM {table}) - INTERVAL {half} DAY,
        'previous',
        'current'
    ) AS period,
    count() AS events,
    uniqExact(user_id) AS users
FROM {table}
WHERE timestamp >= (SELECT max(timestamp) FROM {table}) - INTERVAL {days} DAY
  AND timestamp <= (SELECT max(timestamp) FROM {table})
  {event_pred}
GROUP BY period
ORDER BY period
""".strip()

    return BuildResult(
        sql=sql,
        tables_used=[table.split(".")[-1]],
        caveats=(
            f"Compares last {half}d vs prior {days - half}d "
            f"relative to max(timestamp) in {table}"
        ),
        step_names=events,
    )


_BUILDERS = {
    "funnel": build_funnel_sql,
    "timeseries": build_timeseries_sql,
    "breakdown": build_breakdown_sql,
    "metric": build_metric_sql,
    "top_n": build_top_n_sql,
    "comparison": build_comparison_sql,
}


def build_sql(plan: AnalyticsPlan) -> BuildResult:
    kind = plan.kind
    if kind not in _BUILDERS:
        raise ValueError(f"Unsupported analytics kind: {kind!r}")
    return _BUILDERS[kind](plan)


def plan_from_viz_spec(viz: Any) -> AnalyticsPlan:
    """Map VizSpec (or dict) → AnalyticsPlan."""
    if hasattr(viz, "model_dump"):
        data = viz.model_dump()
    elif isinstance(viz, dict):
        data = viz
    else:
        raise TypeError(f"Cannot map VizSpec from {type(viz)}")

    kind_raw = str(data.get("kind") or "breakdown").strip().lower()
    kind_map = {
        "funnel": "funnel",
        "timeseries": "timeseries",
        "time_series": "timeseries",
        "breakdown": "breakdown",
        "table": "breakdown",
        "comparison": "comparison",
        "metric": "metric",
        "top_n": "top_n",
        "topn": "top_n",
    }
    kind = kind_map.get(kind_raw)
    if kind is None:
        raise ValueError(f"No deterministic builder for viz kind {kind_raw!r}")

    events = list(data.get("event_names") or [])
    dims = list(data.get("dimensions") or [])
    # Funnel default steps when planner omitted them
    if kind == "funnel" and len(events) < 2:
        events = list(CORE_FUNNEL_STEPS)

    filters: dict[str, Any] = {}
    if dims:
        filters["segment"] = dims[0]

    return AnalyticsPlan(
        kind=kind,  # type: ignore[arg-type]
        event_names=events,
        dimensions=dims,
        metric_names=list(data.get("metric_names") or []),
        time_window=data.get("time_window") or "last_30_days",
        filters=filters,
        title=data.get("title"),
        table=config.activity_table_fqn(),
    )
