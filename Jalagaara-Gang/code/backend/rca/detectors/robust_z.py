"""Deterministic detector: the robust like-for-like baseline (JAL-26), adapted to the Anomaly contract.

Same weekday + hour-of-day, median center + MAD spread over the trailing N weeks -> robust z-score.
Fully traceable: every number comes from baseline.score()'s logged queries.
"""
from __future__ import annotations

from models import Anomaly, Window
from rca import baseline


def to_anomaly(stat: baseline.Stat) -> Anomaly:
    """Map a baseline Stat onto the Evidence Bundle's Anomaly (pure — no DB)."""
    return Anomaly(
        detected=stat.detected,
        observed=stat.observed,
        expected=stat.expected,
        abs_delta=stat.observed - stat.expected,
        pct_delta=stat.pct_delta,
        score=stat.robust_z,
        direction=stat.direction,
    )


def run(metric: str, target: Window) -> tuple[Anomaly, list[dict]]:
    """Score the GLOBAL metric at the target hour. Returns (Anomaly, queries)."""
    result = baseline.score(metric, target.start)
    return to_anomaly(result.stats[0]), result.queries
