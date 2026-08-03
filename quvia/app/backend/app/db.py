import os
import threading
from datetime import datetime, date

import clickhouse_connect
from langfuse import get_client as get_langfuse_client

from .variable import DATABASE

# The 9 dimensions py has per-segment agg/anomaly tables for. Validated
# allowlist — never interpolate a caller-supplied dimension_name without
# checking this first. Note: unlike the old ganesh pipeline, py does NOT
# have app_id or advertiser_id breakdowns.
DIMENSIONS = [
    "ad_format", "campaign_type", "category", "country",
    "device_model", "os_version", "publisher_tier", "region", "vertical",
]

# "overall" (py.agg_overall_1h / py.anomaly_overall_1h) is a single-segment
# ('all') pseudo-dimension — the total, no breakdown. It's selectable from
# the Category dropdown for the trend chart and drill-down, but deliberately
# excluded from DIMENSIONS above so it doesn't get ranked alongside the real
# 9 categories in the contribution strip.
TREND_DIMENSIONS = DIMENSIONS + ["overall"]

# py has agg_<dim>_<freq> / anomaly_<dim>_<freq> tables at 5 granularities;
# the dashboard only exposes these two so charts stay a reasonable size.
FREQUENCIES = ["1h", "6h"]

# The 4 metrics the category-trend chart can plot on its Y-axis. agg_<dim>_1h
# only stores the raw columns (requests/fills/impressions/revenue), so
# fill_rate/ecpm are derived here; anomaly_<dim>_1h already has all 4
# precomputed (with their avg_<metric> counterpart) so no derivation is
# needed there.
METRICS = {
    "requests": "requests",
    "revenue": "revenue",
    "fill_rate": "fills / nullIf(requests, 0)",
    "ecpm": "revenue / nullIf(impressions, 0) * 1000",
}

# The synthetic dataset only covers this window — used to clamp the
# frontend's calendar date-picker so users can't pick an empty range.
DATA_MIN_DATE = date(2026, 6, 1)
DATA_MAX_DATE = date(2026, 7, 5)

# py's own rolling-baseline partition: segment x (is this a Sat/Sun?) x hour.
# Every live query below must replicate this exactly to match py's own
# anomaly tables (see mv_anomaly_overall_1h) — it does NOT partition by exact
# day-of-week like the old ganesh baseline_1h did.
_WINDOW_PARTITION = "segment, toDayOfWeek(bucket) IN (6, 7), toHour(bucket)"
_WINDOW = (
    f"PARTITION BY {_WINDOW_PARTITION} ORDER BY bucket ASC "
    "ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING"
)


_local = threading.local()


def get_client():
    # FastAPI runs sync endpoints across a thread pool, and clickhouse-connect's
    # client rejects concurrent queries on the same session ("Attempt to
    # execute concurrent queries within the same session") — a single
    # process-wide cached client (e.g. via lru_cache) breaks the moment two
    # requests land on different threads at once. One client per thread,
    # reused across that thread's requests, avoids both the crash and the
    # overhead of reconnecting every call.
    client = getattr(_local, "client", None)
    if client is None:
        client = clickhouse_connect.get_client(
            host=os.environ["CLICKHOUSE_HOST"],
            port=int(os.environ.get("CLICKHOUSE_PORT", "8443")),
            username=os.environ.get("CLICKHOUSE_USER", "default"),
            password=os.environ["CLICKHOUSE_PASSWORD"],
            database=DATABASE,
            secure=True,
        )
        _local.client = client
    return client


def _run_query(sql: str, span_name: str):
    """Every ClickHouse query goes through here so it shows up as its own
    Langfuse span (SQL text as input, row count as output), nested under
    whichever @observe()-decorated route in main.py is currently the active
    trace — the judge-facing traceability guarantee needs the SQL itself
    visible, not just the LLM calls built on top of it."""
    client = get_client()
    with get_langfuse_client().start_as_current_span(
        name=span_name, input={"sql": sql}
    ) as span:
        result = client.query(sql)
        span.update(output={"row_count": len(result.result_rows)})
        return result


def _bucket_str(bucket: datetime) -> str:
    return bucket.strftime("%Y-%m-%d %H:%M:%S")


def parse_bucket(bucket_iso: str) -> datetime:
    # Raises ValueError on malformed input — caller turns this into a 400.
    return datetime.fromisoformat(bucket_iso)


def _day_info(bucket: datetime) -> dict:
    # Python weekday(): Monday=0 ... Sunday=6. Weekend = Saturday/Sunday.
    return {
        "day_name": bucket.strftime("%A"),
        "is_weekend": bucket.weekday() >= 5,
    }


def _with_day_info(row: dict) -> dict:
    return {**row, **_day_info(row["bucket"])}


def _detection_row_to_dict(row: dict) -> dict:
    """Maps a py.anomaly_overall_1h row onto the field names the rest of the
    app expects (kept stable across the ganesh -> py migration)."""
    return {
        "bucket": row["bucket"],
        "revenue": row["revenue"],
        "expected_revenue": row["avg_revenue"],
        "pct_dev": row["pct_revenue"] / 100.0,
        "robust_z": abs(row["z_revenue"]),
        "requests_pct_change": row["pct_requests"] / 100.0 if row["pct_requests"] is not None else None,
        "fill_rate_pct_change": row["pct_fill_rate"] / 100.0 if row["pct_fill_rate"] is not None else None,
        "ecpm_pct_change": row["pct_ecpm"] / 100.0 if row["pct_ecpm"] is not None else None,
    }


def list_anomalies():
    result = _run_query(
        f"""
        SELECT bucket, revenue, avg_revenue, pct_revenue, z_revenue,
               pct_requests, pct_fill_rate, pct_ecpm
        FROM {DATABASE}.anomaly_overall_1h
        WHERE segment = 'all'
        ORDER BY abs(z_revenue) DESC
        """,
        "clickhouse:list_anomalies",
    )
    rows = [dict(zip(result.column_names, row)) for row in result.result_rows]
    return [_with_day_info(_detection_row_to_dict(r)) for r in rows]


def get_detection(bucket: datetime):
    """Computed live, the same way py's own mv_anomaly_overall_1h does, for
    ANY bucket — not just ones that already crossed the anomaly threshold.
    This lets the frontend load a full incident view for any point a user
    clicks on the category trend chart, not only the pre-flagged ones."""
    b = _bucket_str(bucket)
    result = _run_query(
        f"""
        WITH stats AS (
            SELECT bucket, segment, requests, revenue,
                   fills / nullIf(requests, 0) AS fill_rate,
                   (revenue / nullIf(impressions, 0)) * 1000 AS ecpm,
                   row_number() OVER (PARTITION BY {_WINDOW_PARTITION} ORDER BY bucket ASC) AS rn,
                   avg(requests) OVER w AS avg_requests, stddevSamp(requests) OVER w AS std_requests,
                   avg(revenue) OVER w AS avg_revenue, stddevSamp(revenue) OVER w AS std_revenue,
                   avg(fills / nullIf(requests, 0)) OVER w AS avg_fill_rate,
                   avg((revenue / nullIf(impressions, 0)) * 1000) OVER w AS avg_ecpm
            FROM {DATABASE}.agg_overall_1h
            WINDOW w AS ({_WINDOW})
        )
        SELECT bucket, revenue, avg_revenue,
               abs(revenue - avg_revenue) / nullIf(std_revenue, 0) AS robust_z,
               (revenue - avg_revenue) / nullIf(avg_revenue, 0) AS pct_dev,
               (requests - avg_requests) / nullIf(avg_requests, 0) AS requests_pct_change,
               (fill_rate - avg_fill_rate) / nullIf(avg_fill_rate, 0) AS fill_rate_pct_change,
               (ecpm - avg_ecpm) / nullIf(avg_ecpm, 0) AS ecpm_pct_change
        FROM stats
        WHERE bucket = '{b}' AND segment = 'all' AND rn > 4
        """,
        "clickhouse:get_detection",
    )
    if not result.result_rows:
        return None
    row = dict(zip(result.column_names, result.result_rows[0]))
    row["expected_revenue"] = row.pop("avg_revenue")
    return _with_day_info(row)


def get_day_trend(day: date):
    d = day.strftime("%Y-%m-%d")
    result = _run_query(
        f"""
        WITH stats AS (
            SELECT bucket, segment, revenue,
                   row_number() OVER (PARTITION BY {_WINDOW_PARTITION} ORDER BY bucket ASC) AS rn,
                   avg(revenue) OVER w AS avg_revenue
            FROM {DATABASE}.agg_overall_1h
            WINDOW w AS ({_WINDOW})
        )
        SELECT bucket, revenue, avg_revenue AS expected
        FROM stats
        WHERE toDate(bucket) = '{d}' AND segment = 'all' AND rn > 4
        ORDER BY bucket
        """,
        "clickhouse:get_day_trend",
    )
    return [dict(zip(result.column_names, row)) for row in result.result_rows]


def snap_bucket_to_freq(bucket: datetime, freq_key: str) -> datetime:
    """py's 6h tables only have rows at hour 0/6/12/18 — snap an arbitrary
    incident timestamp down to the 6h block it falls in (e.g. 23:00 -> 18:00)
    so a bucket = '...' lookup against agg_<dim>_6h actually matches a row."""
    if freq_key == "6h":
        return bucket.replace(hour=(bucket.hour // 6) * 6, minute=0, second=0, microsecond=0)
    return bucket.replace(minute=0, second=0, microsecond=0)


def get_contribution(bucket: datetime, dimension_names=None, top_n: int = 5, freq_key: str = "1h"):
    """Contribution ranking (delta vs py's own rolling baseline, partitioned
    per dimension_name), for the exact incident bucket — snapped to whichever
    aggregation granularity (freq_key) is currently selected. Each dimension
    lives in its own physical table in py (agg_<dim>_<freq>) — there's no
    single shared dim_metrics_1h like ganesh had — so this UNIONs one
    subquery per requested dimension.

    dimension_names, if given, MUST already be validated against DIMENSIONS,
    and freq_key against FREQUENCIES — this function trusts its input and
    interpolates it directly.
    """
    b = _bucket_str(snap_bucket_to_freq(bucket, freq_key))
    top_n = int(top_n)
    dims = dimension_names if dimension_names else DIMENSIONS

    subqueries = []
    for dim in dims:
        subqueries.append(f"""
        SELECT '{dim}' AS dimension_name, segment AS dimension_value,
               revenue AS revenue_now, requests AS requests_now, fills AS fills_now,
               impressions AS impressions_now, revenue_expected, delta
        FROM (
            SELECT bucket, segment, revenue, requests, fills, impressions,
                   row_number() OVER (PARTITION BY {_WINDOW_PARTITION} ORDER BY bucket ASC) AS rn,
                   avg(revenue) OVER w AS revenue_expected,
                   (revenue - avg(revenue) OVER w) AS delta
            FROM {DATABASE}.agg_{dim}_{freq_key}
            WINDOW w AS ({_WINDOW})
        )
        WHERE bucket = '{b}' AND rn > 4
        """)

    unioned = "\nUNION ALL\n".join(subqueries)
    result = _run_query(
        f"""
        WITH combined AS ({unioned})
        SELECT dimension_name, dimension_value, revenue_now, revenue_expected, delta,
               delta / sum(delta) OVER (PARTITION BY dimension_name) AS pct_of_total_delta,
               fills_now / nullIf(requests_now, 0) AS fill_rate_now,
               revenue_now / nullIf(impressions_now, 0) * 1000 AS ecpm_now,
               row_number() OVER (PARTITION BY dimension_name ORDER BY abs(delta) DESC) AS rnk
        FROM combined
        QUALIFY rnk <= {top_n}
        ORDER BY dimension_name, rnk
        """,
        f"clickhouse:get_contribution[{','.join(dims)}]",
    )
    return [dict(zip(result.column_names, row)) for row in result.result_rows]


def get_dimension_series(dimension_name: str, start: datetime, end: datetime, freq_key: str, metric: str = "revenue"):
    """Every segment's full value series for one dimension, over an
    explicit [start, end] window (picked from the frontend's calendar date
    range), at the requested granularity and metric — plus the list of
    (bucket, segment) points py's own anomaly tables already flagged as a
    deviation, so the frontend can highlight them on the line chart.

    dimension_name MUST already be validated against DIMENSIONS, freq_key
    against FREQUENCIES, and metric against METRICS — this function trusts
    its input and interpolates it directly.
    """
    start_s, end_s = _bucket_str(start), _bucket_str(end)
    metric_expr = METRICS[metric]

    series_result = _run_query(
        f"""
        SELECT bucket, segment, {metric_expr} AS value
        FROM {DATABASE}.agg_{dimension_name}_{freq_key}
        WHERE bucket BETWEEN '{start_s}' AND '{end_s}'
        ORDER BY bucket
        """,
        f"clickhouse:get_dimension_series[{dimension_name}].series",
    )
    series = [dict(zip(series_result.column_names, row)) for row in series_result.result_rows]

    anomaly_result = _run_query(
        f"""
        SELECT bucket, segment, {metric} AS value, avg_{metric} AS avg_value, z_{metric} AS z_value
        FROM {DATABASE}.anomaly_{dimension_name}_{freq_key}
        WHERE bucket BETWEEN '{start_s}' AND '{end_s}'
        """,
        f"clickhouse:get_dimension_series[{dimension_name}].anomalies",
    )
    anomalies = [dict(zip(anomaly_result.column_names, row)) for row in anomaly_result.result_rows]

    return {"series": series, "anomalies": anomalies}
