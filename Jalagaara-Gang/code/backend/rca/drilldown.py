"""Lane B: recursive contribution drill-down (JAL-77).

Localises the segment responsible for a metric move. At each level we rank every value of every
remaining dimension by how much of the metric gap it explains (a counterfactual: restore that
segment's underlying sums to baseline and see how much the gap closes) RELATIVE to its traffic share
(lift). A segment that's simply big closes ~its share of the gap (lift ~1); a genuine culprit closes
far more than its share (lift >> 1). We descend into the top disproportionate contributor, add it to
the cumulative filter, and recurse. We stop when no remaining value is both material
(>= stop_contribution_threshold) and disproportionate (>= min_lift), or at max_depth — so a uniform
move (no concentrated segment) correctly localises to NOTHING.

Built generically over config.rca.drilldown_dimensions — never hardcodes a segment.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from config import config
from config import hourly_source as _hourly
from data.calibration import measure_natural_noise
from data.client import run_query
from metrics import safe_div
from models import DrilldownNode, Window
from narrator.tracing import phase

_M = config()["metrics"]
_RCA = config()["rca"]
_DET = config()["detection"]
_ALLOWED = set(_RCA["drilldown_dimensions"])
_COMPONENTS = ("requests", "fills", "impressions", "clicks", "revenue")

# Aggregate the whole anomaly window vs an equal-length baseline window (weekday-aligned, k weeks
# earlier) — multi-day anomalies are far more stable than a single noisy hour, and equal durations
# make observed/baseline component sums directly comparable for both ratio and count metrics.
_TGT = "hour >= toDateTime({target_start:String}) AND hour < toDateTime({target_end:String})"
_BASE = "hour >= toDateTime({base_start:String}) AND hour < toDateTime({base_end:String})"


# ---- pure scoring (no DB) --------------------------------------------------

def _metric_from_sums(factor: str, s: dict) -> float:
    if factor in _COMPONENTS:
        return float(s.get(factor, 0))
    if factor == "ecpm":
        return safe_div(s["revenue"], s["impressions"]) * _M["ecpm_multiplier"]
    num, den = _M["ratios"][factor]
    return safe_div(s[num], s[den])


def _volume_base(factor: str) -> str:
    """The component that 'weights' a segment for this metric — its denominator, so lift compares a
    segment's gap-share to its share of the RELEVANT volume (impressions for ecpm/ctr, not requests)."""
    if factor in _COMPONENTS:
        return factor
    if factor == "ecpm":
        return "impressions"
    return _M["ratios"][factor][1]


def _score(factor: str, pop_obs: dict, pop_exp: dict, seg_obs: dict, seg_exp: dict) -> tuple[float, float]:
    """(contribution, lift): fraction of the metric gap this segment explains, and that fraction
    relative to its share of the metric's volume. lift ~1 => merely big; lift >> 1 => culprit."""
    obs = _metric_from_sums(factor, pop_obs)
    exp = _metric_from_sums(factor, pop_exp)
    total_gap = obs - exp
    if total_gap == 0:
        return 0.0, 0.0
    counterfactual = {c: pop_obs.get(c, 0) - seg_obs.get(c, 0) + seg_exp.get(c, 0) for c in _COMPONENTS}
    gap_closed = abs(total_gap) - abs(_metric_from_sums(factor, counterfactual) - exp)
    contribution = gap_closed / abs(total_gap)
    base = _volume_base(factor)
    volume_share = safe_div(seg_obs.get(base, 0), pop_obs.get(base, 0))
    return contribution, safe_div(contribution, volume_share)


# ---- SQL (component sums: observed at target hour + baseline average) -------

def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _where(filt: dict) -> tuple[str, dict]:
    clauses, params = [], {}
    for i, (col, val) in enumerate(filt.items()):
        if col not in _ALLOWED:
            raise ValueError(f"dimension not allowed: {col}")
        clauses.append(f"{col} = {{f{i}:String}}")
        params[f"f{i}"] = val
    return (" AND " + " AND ".join(clauses)) if clauses else "", params


def _sum_cols() -> str:
    parts = []
    for c in _COMPONENTS:
        parts.append(f"sumIf({c}, {_TGT}) AS {c}_obs")
        parts.append(f"sumIf({c}, {_BASE}) AS {c}_bt")
    return ", ".join(parts)


def _split(row: list, offset: int) -> tuple[dict, dict]:
    obs, base, idx = {}, {}, offset
    for c in _COMPONENTS:
        obs[c] = row[idx] or 0
        base[c] = row[idx + 1] or 0
        idx += 2
    return obs, base


def _pop(where_sql: str, params: dict, depth: int) -> tuple[dict, dict, str]:
    sql = f"SELECT {_sum_cols()} FROM {_hourly()} WHERE ({_TGT} OR {_BASE}){where_sql}"
    res = run_query(sql, params, name=f"sql:population:{depth}")
    obs, exp = _split(res["rows"][0], 0)  # equal-length windows -> baseline sums ARE the expectation
    return obs, exp, res["resolved_sql"]


def _by_dim(dim: str, where_sql: str, params: dict, depth: int) -> tuple[list, str]:
    sql = f"SELECT {dim} AS seg, {_sum_cols()} FROM {_hourly()} WHERE ({_TGT} OR {_BASE}){where_sql} GROUP BY {dim}"
    res = run_query(sql, params, name=f"sql:contribution:{dim}")
    out = [(row[0], *_split(row, 1)) for row in res["rows"]]
    return out, res["resolved_sql"]


# ---- recursion -------------------------------------------------------------

def drill(metric: str, factor: str, target: Window, baseline: Window) -> tuple[list[DrilldownNode], dict, list[dict]]:
    """Return (drilldown_path, localized_segment, queries). Localises `factor` at target.start."""
    thr = _RCA["stop_contribution_threshold"]
    min_lift = _RCA["min_lift"]
    params_base = {
        "target_start": _fmt(target.start), "target_end": _fmt(target.end),
        "base_start": _fmt(baseline.start), "base_end": _fmt(baseline.end),
    }

    filt: dict = {}
    path: list[DrilldownNode] = []
    queries: list[dict] = []

    for depth in range(_RCA["max_depth"]):
        where_sql, wparams = _where(filt)
        params = {**params_base, **wparams}
        pop_obs, pop_exp, pop_sql = _pop(where_sql, params, depth)
        queries.append({"id": f"q_drill_pop_{depth}", "sql": pop_sql,
                        "result_summary": {"filter": dict(filt), "observed": _metric_from_sums(factor, pop_obs)}})

        # Materiality gate: contribution is gap_closed / |total_gap|, so when the population
        # barely moved, |total_gap| ~ 0 and ANY segment's noise "explains" ~100% of it. Without
        # this the drill returns a confident 4-level culprit for a non-event: measured on ecpm
        # Jun 16-18 (a +0.4% move) it produced vertical=auto -> publisher_tier=tier_2 ->
        # region=NAM -> device_model=Redmi Note 12, all on a gap that does not exist.
        #
        # Gate on the gap relative to the metric's OWN natural noise, NOT on an absolute percent
        # floor. A localised anomaly is often small globally while being severe in its segment —
        # that is the entire reason to drill. Measured global gaps: fill_rate Jun 28-30 is only
        # -1.2% (yet APAC/iOS 18.1 inside it is -51%), ecpm Jun 19-22 is -4.2% (finance is -35%).
        # An absolute floor big enough to reject the +0.4% non-event would also reject both of
        # those. Against natural noise they separate cleanly: 3.4x and 7.0x versus 0.7x.
        if depth == 0:
            observed = _metric_from_sums(factor, pop_obs)
            expected = _metric_from_sums(factor, pop_exp)
            gap_pct = safe_div(observed - expected, abs(expected))
            noise = measure_natural_noise(factor)
            floor = (noise or 0.0) * _RCA.get("min_gap_noise_multiple", 2.0)
            if floor and abs(gap_pct) < floor:
                reason = (
                    f"population moved {gap_pct:+.2%}, under {floor:.2%} "
                    f"({_RCA.get('min_gap_noise_multiple', 2.0)}x {factor}'s natural noise of "
                    f"{noise:.2%}) — no material gap to localise"
                )
                queries[-1]["result_summary"]["skipped"] = reason
                with phase(f"depth-{depth}:stop", input={"filter": dict(filt)}) as p:
                    p.verdict(decision="stop", reason=reason)
                break

        best = None  # (contribution, lift, dim, val, seg_obs, seg_exp, sql)
        with phase(f"depth-{depth}", input={"filter": dict(filt), "factor": factor}) as p:
            for dim in (d for d in _RCA["drilldown_dimensions"] if d not in filt):
                rows, sql = _by_dim(dim, where_sql, params, depth)
                for val, seg_obs, seg_exp in rows:
                    if val in ("", None):  # empty dim value = "unknown/unfilled" artifact, never a culprit
                        continue
                    contribution, lift = _score(factor, pop_obs, pop_exp, seg_obs, seg_exp)
                    if contribution >= thr and lift >= min_lift and (best is None or contribution > best[0]):
                        best = (contribution, lift, dim, val, seg_obs, seg_exp, sql)

            if best is None:
                p.rename(f"depth-{depth}:stop")
                p.verdict(decision="stop",
                          reason=f"no segment clears contribution>={thr} and lift>={min_lift}")
                break

            contribution, lift, dim, val, seg_obs, seg_exp, sql = best
            filt = {**filt, dim: val}
            p.rename(f"depth-{depth}:{dim}")
            p.verdict(decision="descend", winner={dim: val},
                      contribution_pct=round(contribution, 4), lift=round(lift, 2))

        queries.append({"id": f"q_drill_{depth}", "sql": sql,
                        "result_summary": {"split": dim, "value": val, "contribution_pct": round(contribution, 4), "lift": round(lift, 2)}})
        path.append(DrilldownNode(
            depth=depth, split_dimension=dim, segment=dict(filt),
            metric_from=_metric_from_sums(factor, seg_exp), metric_to=_metric_from_sums(factor, seg_obs),
            contribution_pct=round(contribution, 4), status="contributor", query_id=f"q_drill_{depth}",
        ))

    if path:
        path[-1].status = "culprit"
    return path, dict(filt), queries


def baseline_window(target: Window) -> Window:
    """Same-shape window shifted back k weeks (weekday-aligned, equal duration)."""
    shift = timedelta(weeks=_RCA["baseline_weeks"])
    return Window(start=target.start - shift, end=target.end - shift)
