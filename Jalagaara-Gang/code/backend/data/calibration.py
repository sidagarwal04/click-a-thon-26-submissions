"""Lane A: unsupervised effect-size calibration.

The detector needs to know "how big a move is big enough to care about" per metric. That
number cannot be hardcoded across datasets — it depends on each metric's natural volatility,
which depends on volume per hour, which differs between data slices.

It also cannot be derived the way we originally tuned it (sweeping thresholds against known
incident days), because on a fresh dataset we don't know which days are incidents — that's
the thing we're trying to find.

So we measure it unsupervised: for each metric, look at how much it naturally varies between
like-for-like hours (same weekday + hour-of-day), and set the threshold to a multiple of
that. Uses median-of-absolute-relative-deviations, which is robust — verified that including
real anomalies in the measurement only inflates the estimate 5-22% and does not break
detection (see docs/TEST_CASES.md).

Validated on the 5-week dataset at multiplier 8: fill_rate 0 false positives / 71 of 72
known-anomaly hours kept, requests 0 / 24 of 24, revenue 0 / 24 of 24.
"""
from __future__ import annotations

import statistics
from functools import lru_cache

from config import config
from data.baseline import METRIC_COLUMNS, _metric_value
from data.client import run_query

_HOURLY_SERIES_SQL = """
    SELECT hour,
           sum(requests)    AS requests,
           sum(fills)       AS fills,
           sum(impressions) AS impressions,
           sum(clicks)      AS clicks,
           sum(revenue)     AS revenue
    FROM hourly_summary
    GROUP BY hour
    ORDER BY hour
""".strip()


@lru_cache(maxsize=1)
def _hourly_series() -> tuple[dict, ...]:
    """Whole-dataset hourly series, aggregated in ClickHouse. ~840 rows for a 5-week slice —
    small enough to do the robust-statistics pass in Python, which the coding standards
    permit for already-aggregated series."""
    result = run_query(_HOURLY_SERIES_SQL)
    return tuple(dict(zip(result["columns"], row)) for row in result["rows"])


@lru_cache(maxsize=None)
def measure_natural_noise(metric: str) -> float | None:
    """Typical relative deviation between like-for-like hours for `metric`.

    Buckets by (weekday, hour-of-day) — the same comparison unit the detector uses — then
    normalizes each bucket by its own median so buckets at different absolute levels (3am vs
    3pm) pool together, and takes the median absolute relative deviation across all of them.

    Returns None if there isn't enough data to measure.
    """
    if metric not in METRIC_COLUMNS:
        raise ValueError(f"unknown metric: {metric!r}")
    numerator_col, denominator_col = METRIC_COLUMNS[metric]

    buckets: dict[tuple[int, int], list[float]] = {}
    for row in _hourly_series():
        hour = row["hour"]
        value = _metric_value(
            row[numerator_col],
            row[denominator_col] if denominator_col else None,
            metric,
        )
        buckets.setdefault((hour.isoweekday(), hour.hour), []).append(value)

    relative_deviations = []
    for values in buckets.values():
        if len(values) < 2:
            continue
        bucket_median = statistics.median(values)
        if bucket_median:
            relative_deviations.extend((v - bucket_median) / bucket_median for v in values)

    if len(relative_deviations) < 20:
        return None
    return statistics.median([abs(d) for d in relative_deviations])


def effect_threshold(metric: str) -> float:
    """Minimum |pct_delta| for `metric` to count as a real move.

    Auto-calibrated from the data currently in ClickHouse. Falls back to the static
    per-metric values in config if the dataset is too small to measure.
    """
    cfg = config()["detection"]
    multiplier = cfg["effect_multiplier_overrides"].get(metric, cfg["effect_multiplier"])

    noise = measure_natural_noise(metric)
    if noise is None:
        fallbacks = cfg["min_effect_pct"]
        return fallbacks.get(metric, fallbacks["_default"])
    return multiplier * noise


def reset_calibration() -> None:
    """Drop cached measurements. Call after loading a new dataset within a running process —
    otherwise calibration is computed once per process start, which is the intended lifecycle."""
    _hourly_series.cache_clear()
    measure_natural_noise.cache_clear()
