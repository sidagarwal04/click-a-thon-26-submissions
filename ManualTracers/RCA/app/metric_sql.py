"""Every metric query in the system is rendered here, from a metric_def row.

There is no metric view and no pre-aggregated rollup: the formula in
`metric_def.sql` is executed directly against `ad_events_enriched`. That means
the baseline and z-score logic has to live in exactly one place or it will
diverge between the alert and the investigation — this module is that place.
The RCA agent renders it with bound parameters; `scripts/print_alert_sql.py`
renders the same builder with `now()`-relative bounds for the HyperDX alert.

Baseline: same hour-of-day AND same day-type (weekday/weekend), trailing up to
20 matching observations. A flat average flags every weekend; this does not.
Spread is a robust IQR rather than stddev, so a planted incident inside the
lookback cannot inflate the band and mask itself.
"""

HISTORY_WEEKS = 10  # enough for 20 same-hour, same-day-type points on weekends too
HISTORY_BUCKETS = HISTORY_WEEKS * 7 * 24  # the same span counted in data-hours
BASELINE_POINTS = 20
MIN_BASE_POINTS = 8  # below this the baseline is not worth scoring against

# ClickStack's shortest alert evaluation interval (the `interval` enum bottoms out at 1m).
# It matters here because one such interval can span many data-hours under a compressed
# replay, and the agent's investigation window has to be at least as wide as the window the
# alert evaluated — otherwise the anomaly that fired the alert sits outside the window the
# agent reproduces, and a real incident reports as not_reproducible.
MIN_ALERT_INTERVAL_S = 60

# A "bucket" is one data-hour. In real time that is 3600 wall-clock seconds; in a
# compressed replay (scripts/compress_replay.py) it is fewer, so 35 days of history can
# stream past a live alert in minutes. Everything below is written in buckets, never in
# hours, so the two cases share one code path.
REAL_BUCKET_SECONDS = 3600


def _clock_exprs(clock: dict | None) -> tuple[str, str, str]:
    """(bucket expression, hour-of-day, is-weekend) for the configured clock.

    Real time: plain calendar functions on the event timestamp.

    Compressed: the calendar is a lie — a whole data-day may occupy 24 wall-clock seconds,
    so toHour()/toDayOfWeek() describe the replay, not the data. Seasonality has to come
    from the bucket INDEX instead: index % 24 is the data hour-of-day, and index / 24
    offset by the weekday the data actually starts on is the data day-of-week. Without
    this the baseline stops being seasonal and every night-time hour reads as an anomaly.
    """
    if not clock or int(clock["bucket_seconds"]) == REAL_BUCKET_SECONDS:
        return "toStartOfHour(event_time)", "toHour(ts)", "toDayOfWeek(ts) >= 6"

    size, anchor, origin_dow = (
        int(clock["bucket_seconds"]),
        int(clock["anchor"]),
        int(clock["origin_dow"]),
    )
    idx = f"intDiv(toUnixTimestamp(ts) - {anchor}, {size})"
    return (
        f"toDateTime(intDiv(toUnixTimestamp(event_time) - {anchor}, {size}) * {size} + {anchor})",
        f"({idx}) % 24",
        f"(intDiv({idx}, 24) + {origin_dow}) % 7 >= 5",
    )


def bucket_seconds(clock: dict | None) -> int:
    return int(clock["bucket_seconds"]) if clock else REAL_BUCKET_SECONDS


def window_seconds(buckets: int, clock: dict | None) -> int:
    """Convert a span expressed in data-hours into wall-clock seconds under this clock.
    A 24-data-hour lookback is 24h of real time, but only 24s at 1 bucket/second.

    Every lookback in this system is authored in data-hours and converted here. Writing one
    directly as a real-time interval (INTERVAL 24 HOUR, timedelta(hours=24)) is the bug this
    exists to prevent: compressed, that reaches past the whole dataset and the "last 24
    hours" silently becomes all 35 days."""
    return buckets * bucket_seconds(clock)


def lookback_buckets(clock: dict | None, default_buckets: int = 24) -> int:
    """How many data-hours the agent should reproduce for one alert.

    At real time an alert interval is minutes and the 24-data-hour default dominates.
    Compressed, a single 1-minute evaluation can cover 60 data-hours, so the default would
    be narrower than what the alert actually looked at."""
    per_interval = -(-MIN_ALERT_INTERVAL_S // bucket_seconds(clock))  # ceil division
    return max(default_buckets, per_interval)


def dim_tuples(dims: list[str]) -> str:
    """ARRAY JOIN fan-out: one output row per (bucket, dimension). 'ALL' is the global
    bucket. toString() because the columns are LowCardinality and a tuple array literal
    needs one common type."""
    return ", ".join(
        "('ALL', '')" if d == "ALL" else f"('{d}', toString({d}))" for d in dims
    )


def _expected_and_z(meta: dict) -> tuple[str, str]:
    """Ratio metrics are tested with proportionsZTest against the pooled baseline counts —
    power then comes from sample size rather than from history, which is what makes five
    weeks of data workable. Everything else gets a robust z against the seasonal median."""
    if meta["detector"] == "proportion":
        return (
            "if(base_den = 0, NULL, base_num / base_den)",
            "if(den > 0 AND base_den > 0, proportionsZTest(toUInt64(num), toUInt64(base_num), "
            "toUInt64(den), toUInt64(base_den), 0.999, 'unpooled').1, NULL)",
        )
    return (
        "base_median",
        "if(expected IS NULL, NULL, (actual - expected) / robust_sigma)",
    )


def deviation_sql(
    meta: dict,
    dims: list[str],
    hist_start: str,
    start: str,
    end: str,
    clock: dict | None = None,
) -> str:
    """Hourly series for `dims`, scored against its own seasonal baseline.

    `hist_start` / `start` / `end` are SQL fragments, not values: the agent passes bound
    parameter placeholders, the alert generator passes now()-relative expressions. Rows
    between hist_start and start exist only to build the baseline; only rows after `start`
    are returned.
    """
    bucket_expr, hour_expr, weekend_expr = _clock_exprs(clock)
    expected_expr, z_expr = _expected_and_z(meta)
    den_expr = meta["denominator"] or "0"
    # an absolute floor of 0 means "no floor" — emit no clause rather than `0 = 0`
    effect_abs = float(meta["min_effect_abs"])
    effect_abs_clause = (
        (f"\n              AND abs(delta_abs) >= {effect_abs}") if effect_abs else ""
    )

    return f"""
WITH points AS (
    SELECT {bucket_expr} AS ts,
           d.1 AS dim_name,
           d.2 AS dim_value,
           {meta["sql"]} AS actual,
           {meta["numerator"]} AS num,
           {den_expr} AS den,
           count() AS sample_count
    FROM inmobi.ad_events_enriched
    ARRAY JOIN [{dim_tuples(dims)}] AS d
    WHERE event_time > {hist_start} AND event_time <= {end}
    GROUP BY ts, dim_name, dim_value
    -- vertical / campaign_type are empty on unfilled requests; that is an absence,
    -- not a segment, and it must never become a candidate slice
    HAVING dim_name = 'ALL' OR dim_value != ''
),
windowed AS (
    SELECT ts, dim_name, dim_value, actual, num, den, sample_count,
           quantileExact(0.5)(actual)  OVER w AS base_median,
           quantileExact(0.25)(actual) OVER w AS base_q25,
           quantileExact(0.75)(actual) OVER w AS base_q75,
           sum(num)                    OVER w AS base_num,
           sum(den)                    OVER w AS base_den,
           count()                     OVER w AS base_points
    FROM points
    WINDOW w AS (
        PARTITION BY dim_name, dim_value, {hour_expr}, {weekend_expr}
        ORDER BY ts
        ROWS BETWEEN {BASELINE_POINTS} PRECEDING AND 1 PRECEDING
    )
),
based AS (
    SELECT ts, dim_name, dim_value, actual, num, den, sample_count, base_points,
           base_num, base_den,
           {expected_expr} AS expected,
           greatest((base_q75 - base_q25) / 1.349, 1e-9) AS robust_sigma
    FROM windowed
    WHERE ts > {start}
),
scored AS (
    SELECT ts, dim_name, dim_value, actual, expected, sample_count, base_points,
           actual - expected AS delta_abs,
           if(expected IS NULL OR expected = 0, NULL,
              (actual - expected) / expected) AS delta_rel,
           {z_expr} AS z_score
    FROM based
)
SELECT ts, dim_name, dim_value, actual, expected, delta_abs, delta_rel, z_score,
       sample_count, base_points,
       ifNull(sample_count >= {int(meta["min_samples"])}
              AND base_points >= {MIN_BASE_POINTS}
              AND abs(z_score) >= {float(meta["z_score_threshold"])}
              AND abs(delta_rel) >= {float(meta["min_effect_rel"])}{effect_abs_clause}, 0) AS is_anomaly
FROM scored
""".strip()


def value_sql(meta: dict, where: str) -> str:
    """The metric on an arbitrary subset — used for the holdout complement. Nothing here
    restates the formula; it is the same `metric_def.sql` under a different WHERE."""
    return (
        f"SELECT {meta['sql']} AS value, count() AS sample_count "
        f"FROM inmobi.ad_events_enriched WHERE {where}"
    )
