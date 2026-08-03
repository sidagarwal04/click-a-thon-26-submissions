"""Step 1: Validate baseline. Compares an incident window against a
like-for-like baseline (same hour-of-day range, same weekday, trailing N
weeks) rather than a flat global average -- a flat average would flag every
weekend as anomalous (see CLAUDE.md's seasonality caveat). Always queries
hourly_overall; never raw ad_events.
"""

import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from engine.ch_client import ChClient, Trace
from engine.config import METRIC_DEFS, settings


@dataclass
class WindowStats:
    start: datetime
    end: datetime
    requests: int
    fills: int
    impressions: int
    clicks: int
    revenue: float

    def metric(self, name: str) -> float:
        spec = METRIC_DEFS[name]
        num = getattr(self, _COLUMN_ALIAS.get(spec.numerator, spec.numerator))
        if spec.denominator is None:
            return float(num)
        den = getattr(self, _COLUMN_ALIAS.get(spec.denominator, spec.denominator))
        return (num / den * spec.multiplier) if den else 0.0


_COLUMN_ALIAS = {"fills": "fills", "requests": "requests", "impressions": "impressions", "clicks": "clicks", "revenue": "revenue"}


@dataclass
class BaselineResult:
    metric: str
    window: WindowStats
    baseline_windows: list  # list[WindowStats], one per trailing like-for-like week
    baseline_mean: float
    baseline_stdev: float
    baseline_sample_count: int  # how many trailing weeks actually had data
    current_value: float
    zscore: float
    pct_change: Optional[float]  # None when baseline_mean is 0 -- "% change from zero" isn't a real number
    is_anomalous: bool
    insufficient_baseline: bool  # fewer than 2 trailing weeks had data -- too little history to judge; never flagged anomalous

    @property
    def windows(self) -> list:
        """[current, trailing_1, ... trailing_N] in the order check_baseline's
        `windows` parameter expects -- so another metric over the same range can be
        derived from these instead of re-querying them."""
        return [self.window] + list(self.baseline_windows)


def _query_windows(client: ChClient, trace: Trace, step: str, windows: list) -> list:
    """Every window in ONE query, returned in the order asked for.

    This used to be one round trip per window, issued serially -- 5 for a baseline
    check, and 25 for a revenue investigation once engine/graph.py's decompose step
    re-ran the whole thing for each of the 4 factors. Each round trip is only 15-35 ms
    against ClickHouse Cloud, which is exactly why serialising 25 of them was worth
    ~1 s of an investigation's wall clock while looking like nothing.

    Each window gets its OWN sumIf per measure rather than a GROUP BY over a window
    index, and that is deliberate: a window index would have to assign each hour to
    exactly one window, so windows longer than the baseline shift (a 2-week
    investigation window against a 1-week-shifted baseline) would overlap and the
    shared hours would be counted for one window instead of both. sumIf gives each
    window an independent predicate, so the result is identical to the one-query-per-
    window version for any window length, overlapping or not.

    An empty window yields zeros rather than a missing row, which matters: check_baseline
    counts `w.requests > 0` to decide how much history exists. tests/test_baseline.py
    pins this for 2026-06-01, the first day in the dataset, where all four trailing
    weeks are empty.
    """
    measures = ("requests", "fills", "impressions", "clicks", "revenue")
    cols, ranges = [], []
    for i, (s, e) in enumerate(windows):
        pred = f"(hour >= '{s:%Y-%m-%d %H:%M:%S}' AND hour < '{e:%Y-%m-%d %H:%M:%S}')"
        ranges.append(pred)
        cols.extend(f"sumIf({m}, {pred}) AS {m}_{i}" for m in measures)
    sql = (
        f"SELECT {', '.join(cols)} FROM hourly_overall WHERE {' OR '.join(ranges)}"
    )
    rows = client.query(sql, step=step, trace=trace)
    # An aggregate with no GROUP BY always returns exactly one row, even when nothing
    # matched -- but never assume it.
    r = rows[0] if rows else {}

    out = []
    for i, (start, end) in enumerate(windows):
        out.append(WindowStats(
            start=start,
            end=end,
            requests=int(r.get(f"requests_{i}") or 0),
            fills=int(r.get(f"fills_{i}") or 0),
            impressions=int(r.get(f"impressions_{i}") or 0),
            clicks=int(r.get(f"clicks_{i}") or 0),
            revenue=float(r.get(f"revenue_{i}") or 0),
        ))
    return out


def check_baseline(
    client: ChClient,
    trace: Trace,
    metric: str,
    window_start: datetime,
    window_end: datetime,
    trailing_weeks: Optional[int] = None,
    windows: Optional[list] = None,
) -> BaselineResult:
    """Compares `metric` over [window_start, window_end) against the same
    hour-of-day/weekday range in each of the `trailing_weeks` prior weeks.

    `windows` is an optional pre-fetched [current, trailing_1, ... trailing_N] from a
    previous call over the SAME range -- pass it and no query is issued at all. A
    WindowStats carries all five raw measures and WindowStats.metric() derives any
    metric from them in Python, so the four factor baselines engine/graph.py needs for
    the revenue decomposition are the same five windows the revenue baseline already
    fetched. Re-querying them was 20 further serial round trips for numbers already in
    memory; the arithmetic is the same function over the same sums either way.
    """
    trailing_weeks = trailing_weeks or settings.baseline_trailing_weeks

    if windows is None:
        ranges = [(window_start, window_end)]
        ranges += [
            (window_start - timedelta(weeks=k), window_end - timedelta(weeks=k))
            for k in range(1, trailing_weeks + 1)
        ]
        windows = _query_windows(client, trace, "baseline_check:windows", ranges)
    current, baseline_windows = windows[0], list(windows[1:])

    current_value = current.metric(metric)
    baseline_values = [w.metric(metric) for w in baseline_windows if w.requests > 0]
    baseline_sample_count = len(baseline_values)
    # Fewer than 2 samples means there's no way to estimate variance -- flagging
    # an "anomaly" off a single data point (or zero) would be pure noise, and
    # a fabricated-looking infinite z-score is worse than admitting we can't
    # judge yet. See CLAUDE.md: avoid crying wolf, never invent a number.
    insufficient_baseline = baseline_sample_count < 2

    if baseline_sample_count >= 2:
        baseline_mean = statistics.mean(baseline_values)
        baseline_stdev = statistics.stdev(baseline_values)
    elif baseline_sample_count == 1:
        baseline_mean = baseline_values[0]
        baseline_stdev = 0.0
    else:
        baseline_mean = 0.0
        baseline_stdev = 0.0

    # % change from a zero baseline is mathematically undefined, not a real
    # number -- report None rather than a fabricated Infinity.
    pct_change = ((current_value - baseline_mean) / baseline_mean) if baseline_mean else None

    if insufficient_baseline:
        zscore = 0.0
        is_anomalous = False
    elif baseline_stdev > 0:
        zscore = (current_value - baseline_mean) / baseline_stdev
        is_anomalous = abs(zscore) >= settings.anomaly_zscore_threshold
    elif current_value != baseline_mean:
        # Baseline was perfectly constant across all trailing weeks and this
        # window differs -- a real signal, but "infinite" isn't a valid JSON
        # number, so cap it at a large, clearly-out-of-range finite value.
        zscore = math.copysign(100.0, current_value - baseline_mean)
        is_anomalous = True
    else:
        zscore = 0.0
        is_anomalous = False

    return BaselineResult(
        metric=metric,
        window=current,
        baseline_windows=baseline_windows,
        baseline_mean=baseline_mean,
        baseline_stdev=baseline_stdev,
        baseline_sample_count=baseline_sample_count,
        current_value=current_value,
        zscore=zscore,
        pct_change=pct_change,
        is_anomalous=is_anomalous,
        insufficient_baseline=insufficient_baseline,
    )
