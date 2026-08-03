"""Latency measurement for the investigate/scan pipeline.

Computed entirely from the Tracer's own span durations (traces/*.json) —
the same numbers already written to disk for every real run via
tracing.Tracer, so this reports on actual production behavior rather than a
synthetic benchmark. No new instrumentation, no new run required: point it
at an existing traces/ directory and it aggregates what's already there.
"""

import json
import math
from pathlib import Path

_STAGE_ALIASES = {
    "window_aggregate[baseline]": "window_aggregate_baseline",
    "window_aggregate[current]": "window_aggregate_current",
    "decompose_revenue": "decompose_revenue",
    "narrate": "narrate",
}


def _stage_name(name: str) -> str:
    if name in _STAGE_ALIASES:
        return _STAGE_ALIASES[name]
    if name.startswith("drill_down"):
        return "drill_down"
    if name.startswith("daily_series"):
        return "daily_series"
    if name.startswith("detect_anomalies"):
        return "detect_anomalies"
    return name


def percentile(values: list[float], p: float) -> float | None:
    """Linear-interpolation percentile (numpy's default 'linear' method)."""
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * (p / 100)
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] + (s[c] - s[f]) * (k - f)


def _stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "p50": None, "p90": None, "p95": None, "p99": None, "mean": None, "min": None, "max": None}
    return {
        "n": len(values),
        "p50": round(percentile(values, 50), 3),
        "p90": round(percentile(values, 90), 3),
        "p95": round(percentile(values, 95), 3),
        "p99": round(percentile(values, 99), 3),
        "mean": round(sum(values) / len(values), 3),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
    }


def _load_traces(trace_dir: Path, name_suffix: str) -> list[dict]:
    out = []
    for path in sorted(trace_dir.glob(f"*_{name_suffix}.json")):
        try:
            out.append(json.loads(path.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    return out


def compute_report(trace_dir: str | Path = "traces") -> dict:
    trace_dir = Path(trace_dir)
    investigate_traces = _load_traces(trace_dir, "investigate")
    scan_traces = _load_traces(trace_dir, "scan")

    total = [t["duration_s"] for t in investigate_traces if "duration_s" in t]
    by_stage: dict[str, list[float]] = {}
    by_metric: dict[str, list[float]] = {}
    # Two clean, correctly-computed (not summed-from-percentiles) distributions:
    # the deterministic ClickHouse detect+decompose+drill-down work, vs. the one
    # LLM call that phrases it. Comparing their own percentiles tells the real
    # story of where tail latency comes from.
    pipeline_only: list[float] = []
    narrate_only: list[float] = []

    for t in investigate_traces:
        metric = (t.get("input") or {}).get("metric", "unknown")
        if "duration_s" in t:
            by_metric.setdefault(metric, []).append(t["duration_s"])
        narrate_s = None
        for child in t.get("children", []):
            if "duration_s" in child:
                stage = _stage_name(child["name"])
                by_stage.setdefault(stage, []).append(child["duration_s"])
                if stage == "narrate":
                    narrate_s = child["duration_s"]
        if "duration_s" in t and narrate_s is not None:
            narrate_only.append(narrate_s)
            pipeline_only.append(max(t["duration_s"] - narrate_s, 0.0))

    scan_total = [t["duration_s"] for t in scan_traces if "duration_s" in t]

    return {
        "investigate": {
            "end_to_end": _stats(total),
            "pipeline_only": _stats(pipeline_only),
            "narrate_only": _stats(narrate_only),
            "by_stage": {k: _stats(v) for k, v in sorted(by_stage.items())},
            "by_metric": {k: _stats(v) for k, v in sorted(by_metric.items())},
        },
        "scan": {
            "end_to_end": _stats(scan_total),
        },
    }
