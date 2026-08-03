"""Lane B (JAL-37): assemble a schema-valid EvidenceBundle from detection + decomposition + drill-down.

This is the object the whole system flows through — the RCA engine produces it, the Narrator and
Dashboard consume it. Every number in it must trace to a query in `queries`. The flow:

    incident scan (window + anomaly)  ->  decompose (which factor)  ->  drill (which segment)
                                       ->  ruled_out (flat factors)  ->  EvidenceBundle

narrative / trace_url are filled later by Lane C.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from config import config
from config import hourly_source as _hourly
from data.client import run_query
from metrics import metric_sql, safe_div
from models import (
    Anomaly,
    BaselineWindow,
    EvidenceBundle,
    FactorDecomposition,
    RuledOut,
    Window,
)
from narrator.tracing import phase
from rca.decomposition import decompose
from rca.drilldown import baseline_window, drill
from rca.incidents import scan_incidents
from rca.robust import mad, med, robust_z

_RCA = config()["rca"]
_DET = config()["detection"]
_FLAT_MOVE = 0.01  # a non-primary factor whose OWN value moved < this (1%) is flat -> ruled out
_SCORE_PRIORS = 3  # prior same-shape windows sampled to score the anomaly's surprise

# Map an identity factor to the ruled-out hypothesis name the narrator/schema expect.
_HYPOTHESIS = {"requests": "request_volume", "fill_rate": "fill_rate",
               "render_rate": "render_rate", "ecpm": "ecpm_price"}


def build_bundle(metric: str, target: Window | None = None) -> EvidenceBundle:
    """Run one investigation into a schema-valid EvidenceBundle (no narrative — that's Lane C).

    Each stage runs inside a phase() span whose verdict records the decision AND the numbers
    that drove it — the trace must read as: what was checked, in what order, and why.
    """
    with phase("detect", input={"metric": metric}) as p:
        window, anomaly, q_detect = _window_and_anomaly(metric, target)
        p.verdict(detected=anomaly.detected, observed=anomaly.observed, expected=anomaly.expected,
                  score=anomaly.score, direction=anomaly.direction,
                  window=[_fmt(window.start), _fmt(window.end)])
    baseline = baseline_window(window)

    with phase("decompose", input={"metric": metric}) as p:
        factors, q_decomp = decompose(metric, window, baseline)
        p.verdict(primary_factor=factors.primary_factor,
                  factors={f.factor: f.contribution_pct for f in factors.factors})
    # Revenue investigations drill the factor that moved; a direct-metric investigation drills itself.
    factor = factors.primary_factor if metric == "revenue" else metric

    with phase("drilldown", input={"factor": factor}) as p:
        path, localized, q_drill = drill(metric, factor, window, baseline)
        p.verdict(localized_segment=localized, depth=len(path),
                  culprit_contribution_pct=path[-1].contribution_pct if path else None)

    with phase("ruled-out") as p:
        ruled = _ruled_out(factors, q_decomp[0]["id"])
        p.verdict(cleared={r.hypothesis: r.evidence for r in ruled})

    return EvidenceBundle(
        investigation_id=str(uuid.uuid4()),
        created_at=datetime.now(UTC),
        metric=metric,
        target_window=window,
        baseline_window=BaselineWindow(
            method="same_weekday_trailing_weeks",
            description=f"same window shifted back {_RCA['baseline_weeks']} weeks (weekday-aligned)",
            weeks=_RCA["baseline_weeks"],
        ),
        anomaly=anomaly,
        factor_decomposition=factors,
        drilldown=path,
        localized_segment=localized,
        ruled_out=ruled,
        queries=[*q_detect, *q_decomp, *q_drill],
    )


# ---- window + anomaly (incident scan, with a not-detected fallback) ---------

def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _data_range() -> tuple[datetime, datetime]:
    row = run_query(
        f"SELECT toStartOfDay(min(hour)), toStartOfDay(max(hour)) + INTERVAL 1 DAY FROM {_hourly()}",
        name="sql:data-range",
    )["rows"][0]
    return row[0], row[1]


def _metric_over(metric: str, w: Window) -> tuple[float, str]:
    sql = (f"SELECT {metric_sql(metric, 'rollup')} FROM {_hourly()} "
           f"WHERE hour >= toDateTime({{s:String}}) AND hour < toDateTime({{e:String}})")
    res = run_query(sql, {"s": _fmt(w.start), "e": _fmt(w.end)}, name=f"sql:window-metric:{metric}")
    return float(res["rows"][0][0] or 0.0), res["resolved_sql"]


def _window_and_anomaly(metric: str, target: Window | None) -> tuple[Window, Anomaly, list[dict]]:
    """The incident scanner sets `detected` (and narrows the window when it fires); the anomaly's
    observed/expected/score are always computed at window grain, so a diluted-but-real move still
    reports a genuine robust z instead of 0 — the drill-down then localises it."""
    lo, hi = (target.start, target.end) if target else _data_range()
    scan = scan_incidents(lo, hi, metrics=[metric], grain="day")
    incident = next((i for i in scan.incidents if i.metric == metric), None)
    window = (Window(start=incident.window_start, end=incident.window_end)
              if incident is not None else (target or Window(start=lo, end=hi)))

    observed, expected, score, direction, q_anom = _window_anomaly(metric, window)
    anomaly = Anomaly(
        detected=incident is not None, observed=observed, expected=expected,
        abs_delta=observed - expected, pct_delta=(observed - expected) / expected if expected else 0.0,
        score=score, direction=direction,
    )
    return window, anomaly, [*scan.queries, *q_anom]


def _window_anomaly(metric: str, window: Window) -> tuple[float, float, float, str, list[dict]]:
    """Observed over the window vs the median/MAD of prior same-shape windows -> a real robust z."""
    observed, sql_obs = _metric_over(metric, window)
    queries = [{"id": "q_observed", "sql": sql_obs, "result_summary": {"observed": observed}}]

    priors = []
    for w in range(1, _SCORE_PRIORS + 1):
        shift = timedelta(weeks=w)
        value, sql = _metric_over(metric, Window(start=window.start - shift, end=window.end - shift))
        if value:  # 0 => that window is outside the loaded data range; skip it
            priors.append(value)
            queries.append({"id": f"q_baseline_{w}w", "sql": sql, "result_summary": {"value": value}})

    center = med(priors) if priors else observed
    spread = mad(priors, center) if priors else 0.0
    score = robust_z(observed, center, spread, _DET["mad_scale"])
    direction = "drop" if observed < center else "spike"
    return observed, center, score, direction, queries


# ---- ruled_out (flat, non-primary factors) — pure --------------------------

def _ruled_out(factors: FactorDecomposition, query_id: str) -> list[RuledOut]:
    out = []
    for f in factors.factors:
        # Rule out on the factor's OWN move, not contribution_pct (which can blow up when factors
        # offset). A factor that barely moved didn't cause the change, whatever its share reads as.
        move = safe_div(f.to - f.from_, f.from_)
        if f.factor == factors.primary_factor or abs(move) >= _FLAT_MOVE:
            continue
        out.append(RuledOut(
            hypothesis=_HYPOTHESIS.get(f.factor, f.factor),
            evidence=f"{f.factor} moved {move * 100:+.1f}% ({f.from_:.4g} -> {f.to:.4g}) — within noise",
            query_id=query_id,
        ))
    return out
