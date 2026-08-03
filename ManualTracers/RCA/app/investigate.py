import asyncio
import math
from datetime import timedelta
from statistics import mean

from app import metric_sql
from app.clickhouse_client import query_rows
from app.registry import get_clock, get_dim_deps, get_dim_map, get_metric, known_dims
from app.tracing import traced

# guard against dividing by a near-zero total log-move when identity factors offset each
# other (e.g. fill_rate down, ecpm up, net revenue roughly flat) — see
# docs/RCA_DECOMPOSITION_MATH.md §2.4 "degenerate-G guard rail"
EPSILON_G = 0.005

HOLDOUT_RATIO_THRESHOLD = 0.25

# Share of the parent cut's gross stratum effect that one stratum must carry before the
# culprit is called an interaction rather than the parent alone.
# ponytail: a top-share cut, not a formal interaction test — upgrade path is per-stratum
# significance (proportionsZTest inside vs outside) if the share proves too blunt.
CROSS_SHARE_THRESHOLD = 0.6


async def _dim_col(dim_name: str) -> str:
    """dim_name becomes a raw column reference, not a bound parameter, so it is whitelisted
    against the registry first. Reachable from the alert body now that dimension_id is
    accepted, which makes this a trust boundary, not a formality."""
    if dim_name not in await known_dims():
        raise ValueError(f"unknown dimension column {dim_name!r}")
    return dim_name


def _window_params(start, end, clock: dict) -> dict:
    """The baseline needs history the investigation window itself does not cover.

    The history span is authored in data-hours and converted through the clock, never
    written as timedelta(weeks=...) — under a compressed replay a real-time week bears no
    relation to a data week. See metric_sql.window_seconds."""
    return {
        "hist_start": end
        - timedelta(
            seconds=metric_sql.window_seconds(metric_sql.HISTORY_BUCKETS, clock)
        ),
        "start": start,
        "end": end,
    }


async def _deviation(meta: dict, dims: list[str], clock: dict) -> str:
    return metric_sql.deviation_sql(
        meta,
        dims,
        hist_start="{hist_start:DateTime}",
        start="{start:DateTime}",
        end="{end:DateTime}",
        clock=clock,
    )


async def get_max_ts():
    """least(now(), max(event_time)), NOT max(event_time).

    The replay shifts event_time forward by whole weeks so ClickStack's wall-clock alert
    evaluation has data to see, which leaves the newest rows in the future. Taking the raw
    max would make the agent investigate a window days ahead of the one that alerted, on
    hours that are only partially ingested. Clamping to now() keeps the alert and the
    investigation looking at the same 24 hours."""
    rows = await query_rows(
        "SELECT least(now(), toDateTime(max(event_time))) AS max_ts FROM inmobi.ad_events_enriched"
    )
    return rows[0]["max_ts"]


@traced("reproduce_global")
async def reproduce_global(metric_id: str, start, end) -> list[dict]:
    """The global hourly series, scored. Computed live from silver — there is no stored
    deviation series to trust, and nothing on the alert wire is taken as proof."""
    meta = await get_metric(metric_id)
    clock = await get_clock()
    deviation = await _deviation(meta, ["ALL"], clock)
    return await query_rows(
        f"SELECT ts, actual, expected, z_score, delta_rel, is_anomaly FROM ({deviation}) ORDER BY ts",
        _window_params(start, end, clock),
    )


@traced("reproduce_segment")
async def reproduce_segment(metric_id: str, dim_name: str, start, end) -> list[dict]:
    """Per-value series for one dimension — feeds the UI's segment-series chart
    (docs/RCA_UI_TEMPLATE.md), not the investigation ladder itself. dim_name arrives from
    outside (rca-ui -> rca-api -> here), so it goes through the same _dim_col whitelist as
    every other externally-reachable dimension reference before it is spliced into SQL."""
    meta = await get_metric(metric_id)
    col = await _dim_col(dim_name)
    clock = await get_clock()
    deviation = await _deviation(meta, [col], clock)
    return await query_rows(
        f"SELECT ts, dim_value, actual, expected, z_score, delta_rel, is_anomaly "
        f"FROM ({deviation}) ORDER BY dim_value, ts",
        _window_params(start, end, clock),
    )


def _anomalous(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["is_anomaly"]]


def _scorable(rows: list[dict]) -> list[dict]:
    """Buckets that have a baseline behind them at all.

    A bucket inside the MIN_BASE_POINTS warm-up carries NULL/NaN expected and z_score. The
    anomalous path never sees those (is_anomaly requires a real z), but the marginal fallback
    summarises the *un*-anomalous global series, where they are the majority early in a
    replay — and mean()/max() over a NULL is a crash, not a zero."""
    return [
        r
        for r in rows
        if r["expected"] is not None
        and r["z_score"] is not None
        and math.isfinite(r["expected"])
        and math.isfinite(r["z_score"])
    ]


def _mean_actual_expected(rows: list[dict]) -> tuple[float, float] | None:
    if not rows:
        return None
    return mean(r["actual"] for r in rows), mean(r["expected"] for r in rows)


def _global_summary(rows: list[dict]) -> dict:
    actual, expected = _mean_actual_expected(rows)
    return {
        "actual": actual,
        "expected": expected,
        "hours": len(rows),
        "peak_abs_z": max(abs(r["z_score"]) for r in rows),
    }


def _log_growth(actual: float, expected: float) -> float:
    if actual <= 0 or expected <= 0:
        return 0.0
    return math.log(actual / expected)


def compute_factor_contributions(
    growth: dict[str, float], total_delta_rel: float, min_effect_rel: dict[str, float]
) -> dict:
    """Pure log-share allocation, split out from decompose() so the share/offsetting math is
    unit-testable without a ClickHouse round-trip — same pattern as compute_holdout_verdict.
    ln(Revenue_actual/Revenue_expected) = sum(ln(factor_actual/factor_expected)) is exact
    (log of a product is the sum of logs), so each factor's share of that total log-move is
    used to allocate the *observed* revenue delta_rel — contributions sum to the total by
    construction. See docs/RCA_DECOMPOSITION_MATH.md §2.4."""
    total_growth = sum(growth.values())
    offsetting = abs(total_growth) < EPSILON_G

    factors = []
    for metric_id, g in growth.items():
        contribution_rel = g if offsetting else (g / total_growth) * total_delta_rel
        verdict = (
            "implicated"
            if abs(contribution_rel) >= min_effect_rel[metric_id]
            else "cleared"
        )
        factors.append(
            {
                "metric_id": metric_id,
                "log_growth": g,
                "contribution_rel": contribution_rel,
                "verdict": verdict,
            }
        )
    return {
        "total_revenue_delta_rel": total_delta_rel,
        "offsetting": offsetting,
        "factors": factors,
    }


@traced("decompose")
async def decompose(metric_id: str, anomalous_rows: list[dict], start, end) -> dict:
    """Walk the funnel identity before touching any dimension (CLAUDE.md rule 5). The factor
    list is metric_def.dependencies, in funnel order — not a Python constant — so the
    identity is part of the metric definition and travels with it. Every factor gets a
    verdict, not just the loudest one, per CLAUDE.md rule 6."""
    meta = await get_metric(metric_id)
    factor_ids = list(meta["dependencies"])
    total_actual, total_expected = _mean_actual_expected(anomalous_rows)
    total_delta_rel = (total_actual - total_expected) / total_expected
    anomalous_ts = {r["ts"] for r in anomalous_rows}

    # independent per-factor series — safe and worthwhile to fetch concurrently now that the
    # async client pools requests on one connection instead of needing one client per thread
    factor_series = await asyncio.gather(
        *(reproduce_global(f, start, end) for f in factor_ids)
    )

    factor_rows = {}
    growth = {}
    for factor, series in zip(factor_ids, factor_series):
        rows = [r for r in series if r["ts"] in anomalous_ts]
        factor_rows[factor] = rows
        means = _mean_actual_expected(rows)
        growth[factor] = _log_growth(*means) if means else 0.0

    factor_metas = await asyncio.gather(*(get_metric(f) for f in factor_ids))
    min_effect_rel = {f: m["min_effect_rel"] for f, m in zip(factor_ids, factor_metas)}
    result = compute_factor_contributions(growth, total_delta_rel, min_effect_rel)

    for entry in result["factors"]:
        rows = factor_rows[entry["metric_id"]]
        entry["global"] = _global_summary(rows) if rows else None

    return result


@traced("scan_dims")
async def scan_dims(
    metric_id: str, start, end, first_dim: str | None = None
) -> list[dict]:
    meta = await get_metric(metric_id)
    invalid = set(meta["invalid_dims"] or [])
    dim_map = await get_dim_map(metric_id)
    dims = await known_dims()
    eligible = [
        r["dim_id"]
        for r in dim_map
        if r["dim_id"] not in invalid and r["dim_id"] in dims
    ]
    if not eligible:
        return []
    # Always the full sweep, even when the alert named a dimension.
    #
    # This used to scan the hinted dimension alone and only fall back to the full sweep if
    # that came back empty. It was cheap and it was wrong: with a hint the ladder returned a
    # single candidate and an EMPTY ruled_out list, because `_investigate_factor` can only
    # clear what the scan enumerated. That breaks CLAUDE.md rule 6 and deletes exactly the
    # evidence the brief asks for as its bonus criterion — what was checked and cleared.
    # Measured side by side on the Android 15 incident: unhinted named the culprit and
    # cleared publisher_tier, region, ad_format and two device_models; hinted named the same
    # culprit and cleared nothing.
    #
    # The saving was never real anyway — the fan-out is one ARRAY JOIN pass whether it covers
    # one dimension or all seven. The hint is kept as provenance on the ledger (what the alert
    # claimed) rather than as a scan modifier, so nothing about the verdict depends on the
    # wire being right.
    # ponytail: no ordering tweak either — ranking stays purely by contribution, since
    # promoting a hinted slice above a higher-contribution one is the exact failure
    # "rank by contribution, not percentage change" exists to prevent.
    return await _scan(metric_id, eligible, start, end)


async def _scan(metric_id: str, dims: list[str], start, end) -> list[dict]:
    """One scan covers every candidate dimension: the fan-out is an ARRAY JOIN inside the
    deviation query, so 62 depth-1 slices cost one pass over silver, not 62.
    Ranked by contribution — Σ |delta_abs| × sample_count — never by percentage change."""
    meta = await get_metric(metric_id)
    clock = await get_clock()
    deviation = await _deviation(meta, dims, clock)
    return await query_rows(
        "SELECT dim_name, dim_value, count() AS anomalous_hours, "
        "max(abs(z_score)) AS peak_abs_z, avg(actual) AS avg_actual, "
        "avg(expected) AS avg_expected, avg(delta_rel) AS avg_delta_rel, "
        "sum(abs(delta_abs) * sample_count) AS contribution "
        f"FROM ({deviation}) WHERE is_anomaly = 1 "
        "GROUP BY dim_name, dim_value ORDER BY contribution DESC",
        _window_params(start, end, clock),
    )


def compute_holdout_verdict(
    candidate_delta: float,
    residual_delta: float,
    ratio_threshold: float = HOLDOUT_RATIO_THRESHOLD,
) -> str:
    """Residual close to zero relative to the candidate's own delta => the candidate is the sole cause."""
    if candidate_delta == 0:
        return "inconclusive"
    ratio = abs(residual_delta) / abs(candidate_delta)
    return "localized" if ratio <= ratio_threshold else "inconclusive"


@traced("holdout_check")
async def holdout_check(
    metric_id: str,
    conditions: list[dict],
    candidate_delta: float,
    global_expected_ref: float,
    start,
    end,
) -> dict:
    """Recompute the metric on the COMPLEMENT of the candidate. `conditions` is ANDed, so a
    single entry holds out one depth-1 slice and two entries hold out a crossed pair —
    neither is a stored series, which is why this has to hit silver directly."""
    meta = await get_metric(metric_id)

    clauses, params = [], {"start": start, "end": end}
    for i, c in enumerate(conditions):
        col = await _dim_col(c["dim_name"])
        clauses.append(f"{col} = {{dim_val_{i}:String}}")
        params[f"dim_val_{i}"] = c["dim_value"]

    where = (
        "event_time > {start:DateTime} AND event_time <= {end:DateTime} "
        f"AND NOT ({' AND '.join(clauses)})"
    )
    rows = await query_rows(metric_sql.value_sql(meta, where), params)
    residual_actual = rows[0]["value"]
    # None when the complement matches zero rows (the candidate is ~all the traffic in this
    # window) — nullIf(count(),0) in metric_def.sql, same guard every ratio metric already
    # uses for a dead bucket. No complement means nothing to hold out against: inconclusive,
    # not a crash.
    residual_delta = (
        None if residual_actual is None else residual_actual - global_expected_ref
    )

    return {
        "candidate": [
            {"dim_name": c["dim_name"], "dim_value": c["dim_value"]} for c in conditions
        ],
        "residual_actual": residual_actual,
        "residual_delta": residual_delta,
        "candidate_delta": candidate_delta,
        "verdict": (
            "inconclusive"
            if residual_delta is None
            else compute_holdout_verdict(candidate_delta, residual_delta)
        ),
    }


def compute_interaction(
    child_dim: str, rows: list[dict], share_threshold: float = CROSS_SHARE_THRESHOLD
) -> dict | None:
    """Stratified inside-vs-outside comparison: for every value of the child dimension, how
    much worse is the parent slice than the rest of the population in that same stratum?

        effect_v       = metric(parent AND child=v) - metric(NOT parent AND child=v)
        contribution_v = effect_v * sample_count(parent AND child=v)

    The rest of the population is the control, so no depth-2 baseline is needed — and none
    exists, since nothing is pre-aggregated. If the parent's fault is genuinely at the
    parent's level the effect is spread across strata; if one stratum carries it, the
    culprit is the pair. Returns None when there is nothing to compare."""
    inside, outside = {}, {}
    for r in rows:
        (inside if r["in_parent"] else outside)[r["child_value"]] = r

    strata = []
    for value, row in inside.items():
        control = outside.get(value)
        if row["value"] is None or control is None or control["value"] is None:
            continue
        rate_in, rate_out = row["value"], control["value"]
        effect = rate_in - rate_out
        strata.append(
            {
                "child_value": value,
                "rate_in": rate_in,
                "rate_out": rate_out,
                "effect": effect,
                "contribution": effect * row["sample_count"],
            }
        )

    if len(strata) < 2:
        return None
    # gross (sum of absolute) rather than net: strata pulling in opposite directions must not
    # shrink the denominator and manufacture a fake concentration.
    gross = sum(abs(s["contribution"]) for s in strata)
    if gross == 0:
        return None

    top = max(strata, key=lambda s: abs(s["contribution"]))
    share = abs(top["contribution"]) / gross
    return {
        "child_dim": child_dim,
        "strata_tested": len(strata),
        "top": top,
        "top_share": share,
        "verdict": "interaction" if share >= share_threshold else "uniform",
    }


@traced("scan_interaction")
async def scan_interaction(
    metric_id: str, parent: dict, child_dim: str, start, end
) -> dict | None:
    meta = await get_metric(metric_id)
    parent_col, child_col = (
        await _dim_col(parent["dim_name"]),
        await _dim_col(child_dim),
    )

    rows = await query_rows(
        f"SELECT {child_col} AS child_value, {parent_col} = {{parent_val:String}} AS in_parent, "
        f"{meta['sql']} AS value, count() AS sample_count FROM inmobi.ad_events_enriched "
        "WHERE event_time > {start:DateTime} AND event_time <= {end:DateTime} "
        "GROUP BY child_value, in_parent",
        {"parent_val": parent["dim_value"], "start": start, "end": end},
    )
    return compute_interaction(child_dim, rows)


@traced("cross_check")
async def cross_check(
    metric_id: str, parent: dict, global_expected_ref: float, start, end
) -> dict:
    """Step 5 of the ladder: walk metric_dim_map.dependencies for the cut just made — the
    tree, one level down. Stops at the first dependent dimension that concentrates, since
    the dependency array is priority-ordered."""
    meta = await get_metric(metric_id)
    if not meta["is_ratio"]:
        # An inside-vs-outside comparison needs a rate. A count inside the parent slice has
        # no comparable outside value, so depth-2 on an additive metric would need a
        # depth-2 seasonal baseline, which nothing here stores.
        # ponytail: skip with a stated reason rather than invent a comparison.
        return {"skipped": "additive_metric_needs_depth2_baseline"}

    invalid = set(meta["invalid_dims"] or [])
    dims = await known_dims()
    for child_dim in await get_dim_deps(metric_id, parent["dim_name"]):
        if (
            child_dim in invalid
            or child_dim == parent["dim_name"]
            or child_dim not in dims
        ):
            continue
        interaction = await scan_interaction(metric_id, parent, child_dim, start, end)
        if interaction and interaction["verdict"] == "interaction":
            top = interaction["top"]
            interaction["holdout"] = await holdout_check(
                metric_id,
                [parent, {"dim_name": child_dim, "dim_value": top["child_value"]}],
                top["effect"],
                global_expected_ref,
                start,
                end,
            )
            return interaction
    return {"skipped": "no_dependent_dimension_concentrated"}


@traced("investigate_factor")
async def _investigate_factor(
    target_metric: str, global_summary: dict, start, end, first_dim: str | None = None
) -> dict:
    candidates = await scan_dims(target_metric, start, end, first_dim)
    if not candidates:
        return {
            "factor": target_metric,
            "global": global_summary,
            "verdict": "broad_based",
            "candidates": [],
            "ruled_out": [],
        }

    top = candidates[0]
    parent = {"dim_name": top["dim_name"], "dim_value": top["dim_value"]}
    # No global summary means the whole window is inside the baseline warm-up, which happens
    # early in a compressed replay. The candidate's own seasonal expectation is then the only
    # reference the holdout residual can be measured against.
    expected_ref = (
        global_summary["expected"] if global_summary else top["avg_expected"]
    )

    # independent of each other — the dependency walk conditions on parent, not on holdout —
    # so run both concurrently rather than paying two round trips back to back
    holdout, interaction = await asyncio.gather(
        holdout_check(
            target_metric,
            [parent],
            top["avg_actual"] - top["avg_expected"],
            expected_ref,
            start,
            end,
        ),
        cross_check(target_metric, parent, expected_ref, start, end),
    )

    verdict = holdout["verdict"]
    if interaction.get("holdout", {}).get("verdict") == "localized":
        verdict = "localized"

    return {
        "factor": target_metric,
        "global": global_summary,
        "candidates": candidates[:10],
        "holdout": holdout,
        "interaction": interaction,
        "verdict": verdict,
        "ruled_out": (
            [f"{c['dim_name']}={c['dim_value']}" for c in candidates[1:]]
            if verdict == "localized"
            else []
        ),
    }


@traced("investigate_marginal")
async def _investigate_marginal(
    metric_id: str, dimension_id: str | None, global_rows: list[dict], start, end, window
) -> dict:
    """Step 1 fallback: the global series is clean, so score the depth-1 slices before giving up.

    The marginal sentinel tile alerts on all 62 slices independently, so an incident confined
    to a segment too small to move the global metric can only reach the agent this way.
    Returning not_reproducible on a clean global — which is what this function replaces —
    dropped exactly those incidents on the floor.

    Nothing from the alert is trusted here either: the slices are re-scored live from silver,
    the same query the global path runs, only fanned out.
    """
    candidates = await scan_dims(metric_id, start, end, dimension_id)
    scorable = _scorable(global_rows)
    global_summary = _global_summary(scorable) if scorable else None

    if not candidates:
        return {
            "metric_id": metric_id,
            "window": window,
            "scope": "global",
            "global": global_summary,
            "verdict": "not_reproducible",
        }

    finding = await _investigate_factor(
        metric_id, global_summary, start, end, dimension_id
    )
    # The holdout is near-vacuous in this branch and must not be read as strong evidence:
    # removing the culprit from a population that was already at baseline trivially leaves a
    # residual at baseline. The load-bearing evidence is the slice's own z and contribution,
    # plus the dependency walk. scope=marginal is what tells the narrator to say the global
    # metric did not move.
    return {
        "metric_id": metric_id,
        "window": window,
        "scope": "marginal",
        "dimension_id": dimension_id,
        "global": global_summary,
        "decomposition": None,
        "findings": [finding],
        "verdict": finding["verdict"],
    }


@traced("run_investigation")
async def run_investigation(
    metric_id: str, dimension_id: str | None = None, lookback_hours: int = 24
) -> dict:
    meta = await get_metric(metric_id)
    if meta is None:
        return {"metric_id": metric_id, "verdict": "unknown_metric"}

    # lookback_hours is data-hours, not wall-clock hours, and the two diverge under a
    # compressed replay. lookback_buckets also widens it to cover one alert evaluation, which
    # can span many data-hours when compressed — investigating a narrower window than the
    # alert scored would report a real incident as not_reproducible.
    clock = await get_clock()
    buckets = metric_sql.lookback_buckets(clock, lookback_hours)
    max_ts = await get_max_ts()
    start = max_ts - timedelta(seconds=metric_sql.window_seconds(buckets, clock))
    end = max_ts
    window = {"start": start.isoformat(), "end": end.isoformat(), "buckets": buckets}

    # dimension_id from the alert is only ever a scan-priority hint (see scan_dims). The
    # global series is what has to reproduce, and it is recomputed here, not read back.
    global_rows = await reproduce_global(metric_id, start, end)
    anomalous = _anomalous(global_rows)
    if not anomalous:
        return await _investigate_marginal(
            metric_id, dimension_id, global_rows, start, end, window
        )

    decomposition = None
    if meta["dependencies"]:
        decomposition = await decompose(metric_id, anomalous, start, end)
        implicated = [
            f for f in decomposition["factors"] if f["verdict"] == "implicated"
        ]
        if not implicated:
            return {
                "metric_id": metric_id,
                "window": window,
                "decomposition": decomposition,
                "verdict": "not_reproducible",
            }
        findings = await asyncio.gather(
            *(
                _investigate_factor(
                    f["metric_id"], f["global"], start, end, dimension_id
                )
                for f in implicated
            )
        )
    else:
        findings = [
            await _investigate_factor(
                metric_id, _global_summary(anomalous), start, end, dimension_id
            )
        ]

    verdicts = {f["verdict"] for f in findings}
    overall_verdict = (
        "localized"
        if "localized" in verdicts
        else "inconclusive"
        if "inconclusive" in verdicts
        else "broad_based"
    )

    return {
        "metric_id": metric_id,
        "window": window,
        "scope": "global",
        "dimension_id": dimension_id,
        "decomposition": decomposition,
        "findings": list(findings),
        "verdict": overall_verdict,
    }
