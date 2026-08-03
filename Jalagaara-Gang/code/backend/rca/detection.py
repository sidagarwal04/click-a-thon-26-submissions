"""Lane B: detection dispatcher.

Selects a detector strategy from config.detection.method and delegates. Every detector returns the
identical (Anomaly, queries) contract, so everything downstream is agnostic to which one ran.

  * robust_z         — deterministic like-for-like baseline (median/MAD over trailing weeks).
  * seasonal_ml      — unsupervised seasonal-residual model over all history.
  * isolation_forest — unsupervised sklearn IsolationForest over engineered features. Default.

`detect()` scores the GLOBAL aggregate. `detect_in_window()` adds the segment pass, and that
distinction is load-bearing — see its docstring.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from config import config
from models import Anomaly, Window
from rca import baseline
from rca.detectors import isolation_forest, robust_z, seasonal_ml

Runner = Callable[[str, Window], "tuple[Anomaly, list[dict]]"]

_DETECTORS: dict[str, Runner] = {
    "robust_z": robust_z.run,
    "seasonal_ml": seasonal_ml.run,
    "isolation_forest": isolation_forest.run,
}


def _select(method: str) -> Runner:
    try:
        return _DETECTORS[method]
    except KeyError:
        raise ValueError(f"unknown detection method: {method!r} (known: {sorted(_DETECTORS)})")


def detect(
    metric: str, target: Window, method: str | None = None
) -> tuple[Anomaly, list[dict]]:
    """Return (Anomaly, queries) for `metric` at `target`.

    `method` overrides config.detection.method for this one call (used by the chat endpoint to
    let a caller pick statistical vs ML per request); falls back to the configured default.
    """
    return _select(method or config()["detection"]["method"])(metric, target)


def _hours_in(window: Window) -> list[datetime]:
    hours, t = [], window.start.replace(minute=0, second=0, microsecond=0)
    while t < window.end:
        hours.append(t)
        t += timedelta(hours=1)
    return hours or [window.start]


def _spread(items: list, k: int) -> list:
    """k items spread evenly across the list (not the first k, which would bunch at the start)."""
    if len(items) <= k:
        return items
    step = len(items) / k
    return [items[int(step * i + step / 2)] for i in range(k)]


def detect_in_window(
    metric: str,
    window: Window,
    method: str | None = None,
    dimensions: list[str] | None = None,
    segment_sample_hours: int = 3,
) -> tuple[Anomaly, list[dict], Window, dict]:
    """Segment-aware detection over a window. Returns (anomaly, queries, hour, segment).

    WHY THIS EXISTS. Scoring only the global aggregate cannot see a localised anomaly, because
    the rest of the population dilutes it below the noise floor. Measured on this dataset:
    the APAC x iOS 18.1 fill_rate collapse is -51% inside its segment but moves the global
    figure just -1.2%, against a 2.79% calibrated floor. Every detector we have (robust_z,
    seasonal_ml, IsolationForest uni/multi) scores 0/3 on it — not because any of them is
    weak, but because they were all asked about a number that genuinely did not move. Adding
    the segment pass takes the benchmark from 3/5 cases detected to 5/5 with no detector change.

    Two phases, cheapest first:
      1. Score every hour globally (the existing behaviour). If anything fires, the move is big
         enough to be visible in the population — report it with segment={} (genuinely global,
         which is itself the right answer for e.g. the Jun 21 collapse).
      2. Only if nothing fired: re-score the worst few hours per dimension value, and report the
         most extreme segment that fires. Vectorised — 2 queries per dimension regardless of
         cardinality, so this is ~18 extra queries, not one per segment value.

    Cost note: phase 2 runs on a sample of hours (default 3), not all of them. A planted anomaly
    spans hours-to-days, so sampling finds it; scanning all 24 hours x 9 dimensions would be 432
    queries for one day's investigation.
    """
    dims = dimensions or config()["rca"]["drilldown_dimensions"][:9]  # low-cardinality only
    queries: list[dict] = []

    best = None
    for hour in _hours_in(window):
        target = Window(start=hour, end=hour + timedelta(hours=1))
        anomaly, qs = detect(metric, target, method)
        rank = (anomaly.detected, abs(anomaly.score))
        if best is None or rank > best[0]:
            best = (rank, anomaly, qs, target)

    _, anomaly, qs, target = best
    queries.extend(qs)
    if anomaly.detected:
        return anomaly, queries, target, {}

    # Phase 2 — nothing moved the population; look inside it.
    worst_seg = None
    for hour in _spread(_hours_in(window), segment_sample_hours):
        for dim in dims:
            result = baseline.scan(metric, hour, dim)
            queries.extend(result.queries)
            for stat in result.stats:
                if not stat.detected or stat.n_baseline < 2:
                    continue
                if worst_seg is None or abs(stat.pct_delta) > abs(worst_seg[0].pct_delta):
                    worst_seg = (stat, hour)

    if worst_seg is None:
        return anomaly, queries, target, {}

    stat, hour = worst_seg
    return (
        robust_z.to_anomaly(stat),
        queries,
        Window(start=hour, end=hour + timedelta(hours=1)),
        dict(stat.segment),
    )
