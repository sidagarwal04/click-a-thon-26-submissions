"""Drill-down pipeline: given a metric + day, find which factor moved and
which segment is responsible, recording what was checked and ruled out.
Every number comes from ClickHouse; the LLM is called once, at the end."""
import json
from datetime import date
from typing import Optional

from . import baseline as baseline_module
from . import config, coverage as coverage_module, db, llm, metrics, thresholds as thresholds_module, timing, tracing

_DECOMPOSITION_FACTORS = ("requests", "fill_rate", "render_rate", "ecpm")

_OVERALL_QUERY = """
    WITH daily AS (
        SELECT
            toDate(hour) AS day,
            countMerge(requests) AS requests,
            sumMerge(fills) AS fills,
            sumMerge(impressions) AS impressions,
            sumMerge(clicks) AS clicks,
            sumMerge(revenue) AS revenue
        FROM inmobi_rca.hourly_segment_metrics
        {where_clause}
        GROUP BY day
    )
    SELECT
        day,
        {metric_expr} AS actual_value,
        {baseline_cols}
    FROM daily
    ORDER BY day
"""

_SEGMENT_QUERY = """
    WITH daily AS (
        SELECT
            toDate(hour) AS day,
            {dim_col} AS segment_value,
            countMerge(requests) AS requests,
            sumMerge(fills) AS fills,
            sumMerge(impressions) AS impressions,
            sumMerge(clicks) AS clicks,
            sumMerge(revenue) AS revenue
        FROM inmobi_rca.hourly_segment_metrics
        {where_clause}
        GROUP BY day, segment_value
    )
    SELECT
        day,
        segment_value,
        requests,
        {metric_expr} AS actual_value,
        {baseline_cols}
    FROM daily
    ORDER BY segment_value, day
"""


def _build_overall_query(metric_expr: str, hour_cutoff=None) -> str:
    hour_filter = coverage_module.hour_filter_sql(hour_cutoff)
    return _OVERALL_QUERY.format(
        metric_expr=metric_expr,
        where_clause=f"WHERE {hour_filter}" if hour_filter else "",
        baseline_cols=baseline_module.baseline_select(
            metric_expr, "toDayOfWeek(day)", config.TRAILING_WEEKS
        ),
    )


def _build_segment_query(dim_col: str, metric_expr: str, hour_cutoff=None) -> str:
    hour_filter = coverage_module.hour_filter_sql(hour_cutoff)
    return _SEGMENT_QUERY.format(
        dim_col=dim_col,
        metric_expr=metric_expr,
        where_clause=f"WHERE {hour_filter}" if hour_filter else "",
        baseline_cols=baseline_module.baseline_select(
            metric_expr, "segment_value, toDayOfWeek(day)", config.TRAILING_WEEKS
        ),
    )


# No `WHERE day = ...` here on purpose - filtering to one day before the
# window function runs leaves the trailing baseline with zero prior rows.
# Fetch the full range, filter to the target day in Python instead.


def daily_deviation_series(client, metric_name: str) -> list:
    coverage = coverage_module.day_coverage(client)
    metric_expr = metrics.METRIC_EXPRESSIONS[metric_name]

    rows_by_day = {}
    passes = [(None, {d for d, i in coverage.items() if i["complete"]})]
    for partial_day in coverage_module.partial_days(coverage):
        passes.append((coverage_module.hour_cutoff_for(coverage, partial_day), {partial_day}))

    for hour_cutoff, days_in_pass in passes:
        if not days_in_pass:
            continue
        query = _build_overall_query(metric_expr, hour_cutoff)
        for row in client.query(query).result_rows:
            row_day, actual, baseline, baseline_mean, _stddev, baseline_n = row
            if row_day in days_in_pass:
                rows_by_day[row_day] = (actual, baseline, baseline_mean, baseline_n, hour_cutoff)

    series = []
    for row_day in sorted(rows_by_day):
        actual, baseline, baseline_mean, baseline_n, hour_cutoff = rows_by_day[row_day]
        point = {
            "day": row_day.isoformat(),
            "actual": None if metrics.is_invalid_number(actual) else float(actual),
            "baseline": None,
            "pct_deviation": None,
            "baseline_n": int(baseline_n or 0),
            "evaluated_hours": "" if hour_cutoff is None else f"00:00-{hour_cutoff:02d}:59",
            "not_evaluated_reason": None,
        }
        if point["actual"] is None:
            point["not_evaluated_reason"] = "no data for this day"
        elif metrics.is_invalid_number(baseline) or baseline == 0:
            point["not_evaluated_reason"] = "no trailing same-weekday history to compare against"
        elif (baseline_n or 0) < config.MIN_BASELINE_SAMPLES:
            point["baseline"] = float(baseline)
            point["not_evaluated_reason"] = (
                f"only {int(baseline_n or 0)} prior same-weekday observation(s); "
                f"{config.MIN_BASELINE_SAMPLES} required before a deviation is treated as evidence"
            )
        else:
            point["baseline"] = float(baseline)
            point["pct_deviation"] = float((actual - baseline) / baseline)
            if not metrics.is_invalid_number(baseline_mean):
                point["baseline_mean"] = float(baseline_mean)
        series.append(point)
    return series


def compute_daily_deviation(client, day: date, metric_name: str) -> Optional[dict]:
    day_str = day.isoformat()
    for point in daily_deviation_series(client, metric_name):
        if point["day"] == day_str:
            return {
                "metric": metric_name,
                "actual": point["actual"],
                "baseline": point["baseline"],
                "pct_deviation": point["pct_deviation"],
                "baseline_n": point["baseline_n"],
                "evaluated_hours": point["evaluated_hours"],
                "not_evaluated_reason": point["not_evaluated_reason"],
            }
    return None


_UNSET = object()


def segment_ranking(
    client,
    day: date,
    metric_name: str,
    dim_col: str,
    volume_floor: Optional[int] = None,
    hour_cutoff=_UNSET,
) -> list:
    if volume_floor is None:
        volume_floor = config.MIN_VOLUME_FLOOR
    if hour_cutoff is _UNSET:
        coverage = coverage_module.day_coverage(client)
        hour_cutoff = coverage_module.hour_cutoff_for(coverage, day)
    query = _build_segment_query(dim_col, metrics.METRIC_EXPRESSIONS[metric_name], hour_cutoff)
    rows = client.query(query).result_rows

    ranked = []
    for row_day, segment_value, requests, actual, baseline, baseline_mean, _stddev, baseline_n in rows:
        if row_day != day or requests < volume_floor:
            continue
        if str(segment_value) == metrics.BLANK_SEGMENT_VALUE:
            continue
        if metrics.is_invalid_number(actual) or metrics.is_invalid_number(baseline) or baseline == 0:
            continue
        if (baseline_n or 0) < config.MIN_BASELINE_SAMPLES:
            continue
        pct_dev = (actual - baseline) / baseline
        ranked.append(
            {
                "dimension": dim_col,
                "value": segment_value,
                "requests": requests,
                "actual": float(actual),
                "baseline": float(baseline),
                "pct_deviation": float(pct_dev),
                "baseline_n": int(baseline_n or 0),
                "baseline_mean": (
                    None if metrics.is_invalid_number(baseline_mean) else float(baseline_mean)
                ),
            }
        )
    ranked.sort(key=lambda r: abs(r["pct_deviation"]), reverse=True)
    return ranked


def segment_value_lookup(client, day: date, metric_name: str, dim_col: str, value: str) -> dict:
    for r in segment_ranking(client, day, metric_name, dim_col):
        if str(r["value"]) == str(value):
            return r
    return {"dimension": dim_col, "value": value, "metric": metric_name, "note": "no data for this segment/day/metric combination"}


_COMBO_SEGMENT_QUERY = """
    WITH daily AS (
        SELECT
            toDate(hour) AS day,
            {inner_dim} AS segment_value,
            countMerge(requests) AS requests,
            sumMerge(fills) AS fills,
            sumMerge(impressions) AS impressions,
            sumMerge(clicks) AS clicks,
            sumMerge(revenue) AS revenue
        FROM inmobi_rca.hourly_segment_metrics
        WHERE {outer_dim} = {{outer_value:String}} {extra_filter}
        GROUP BY day, segment_value
    )
    SELECT
        day,
        segment_value,
        requests,
        {metric_expr} AS actual_value,
        {baseline_cols}
    FROM daily
    ORDER BY segment_value, day
"""


def _build_combo_query(inner_dim: str, outer_dim: str, metric_expr: str, hour_cutoff=None) -> str:
    hour_filter = coverage_module.hour_filter_sql(hour_cutoff)
    return _COMBO_SEGMENT_QUERY.format(
        inner_dim=inner_dim,
        outer_dim=outer_dim,
        metric_expr=metric_expr,
        extra_filter=f"AND {hour_filter}" if hour_filter else "",
        baseline_cols=baseline_module.baseline_select(
            metric_expr, "segment_value, toDayOfWeek(day)", config.TRAILING_WEEKS
        ),
    )


def refine_segment(
    client,
    day: date,
    metric_name: str,
    outer_dim: str,
    outer_value,
    single_pct_dev: float,
    thresholds: dict,
    hour_cutoff=_UNSET,
) -> Optional[dict]:
    """Within the winning segment, checks every other dimension for a
    sharper intersection (e.g. country=IN alone +25% vs country=IN AND
    device_model=iPhone +52%). Single dimensions only where the marginal
    dimension also shows signal - full pairwise scanning isn't done here."""
    metric_thresholds = thresholds.get(
        metric_name, {"pct_threshold": config.PCT_DEVIATION_THRESHOLD, "volume_floor": config.MIN_VOLUME_FLOOR}
    )
    pct_threshold = metric_thresholds["pct_threshold"]
    volume_floor = metric_thresholds["volume_floor"]
    if hour_cutoff is _UNSET:
        hour_cutoff = coverage_module.hour_cutoff_for(coverage_module.day_coverage(client), day)

    best_combo = None
    for inner_dim in metrics.scannable_dimensions(metric_name):
        if inner_dim == outer_dim:
            continue
        query = _build_combo_query(
            inner_dim, outer_dim, metrics.METRIC_EXPRESSIONS[metric_name], hour_cutoff
        )
        rows = client.query(query, parameters={"outer_value": str(outer_value)}).result_rows
        for row_day, segment_value, requests, actual, baseline, _mean, _stddev, baseline_n in rows:
            if row_day != day or requests < volume_floor:
                continue
            if str(segment_value) == metrics.BLANK_SEGMENT_VALUE:
                continue
            if metrics.is_invalid_number(actual) or metrics.is_invalid_number(baseline) or baseline == 0:
                continue
            if (baseline_n or 0) < config.MIN_BASELINE_SAMPLES:
                continue
            pct_dev = (actual - baseline) / baseline
            if best_combo is None or abs(pct_dev) > abs(best_combo["pct_deviation"]):
                best_combo = {
                    "dimension": inner_dim,
                    "value": segment_value,
                    "requests": requests,
                    "actual": float(actual),
                    "baseline": float(baseline),
                    "pct_deviation": float(pct_dev),
                }

    if (
        best_combo is not None
        and abs(best_combo["pct_deviation"]) >= pct_threshold
        and abs(best_combo["pct_deviation"]) > abs(single_pct_dev)
    ):
        return best_combo
    return None


def investigate(metric_name: str, day: date, anomaly_candidate_id: Optional[str] = None) -> dict:
    client = db.get_ro_client()
    admin = db.get_admin_client()
    timings = timing.Timings()
    trace = tracing.start_trace(
        name="investigate",
        input={"metric": metric_name, "day": str(day), "anomaly_candidate_id": anomaly_candidate_id},
        metadata={"metric": metric_name, "day": str(day)},
    )

    def timed_span(name, func, input=None):
        return trace.run_span(name, lambda: timings.measure(name, func), input=input)

    day_coverage = timed_span("day_coverage", lambda: coverage_module.day_coverage(client))
    hour_cutoff = coverage_module.hour_cutoff_for(day_coverage, day)
    coverage_note = coverage_module.describe(day_coverage, day)

    metric_set = set(metrics.HEADLINE_METRICS) | set(_DECOMPOSITION_FACTORS) | {metric_name}
    computed_thresholds = timed_span(
        "compute_thresholds",
        lambda: thresholds_module.compute_metric_thresholds(client, metric_set),
        input={"metrics": sorted(metric_set)},
    )

    overall = timed_span(
        "overall_deviation",
        lambda: compute_daily_deviation(client, day, metric_name),
        input={"metric": metric_name, "day": str(day)},
    )

    ruled_out = []
    driving_factors = [dict(overall, metric=metric_name)] if overall else []

    if metric_name == "revenue":
        factor_breakdown = timed_span(
            "factor_decomposition",
            lambda: [compute_daily_deviation(client, day, f) for f in _DECOMPOSITION_FACTORS],
            input={"factors": list(_DECOMPOSITION_FACTORS), "day": str(day)},
        )
        significant = [
            f for f in factor_breakdown
            if f and f.get("pct_deviation") is not None
            and abs(f["pct_deviation"]) >= computed_thresholds[f["metric"]]["pct_threshold"]
        ]
        for f in factor_breakdown:
            if not f:
                continue
            if f in significant:
                continue
            if f.get("pct_deviation") is None:
                reason = f.get("not_evaluated_reason") or "insufficient baseline history to compare"
                ruled_out.append(f"{f['metric']}: not evaluated - {reason}")
            else:
                ruled_out.append(f"{f['metric']}: normal ({f['pct_deviation']:+.1%} vs baseline)")
        if significant:
            driving_factors = sorted(significant, key=lambda f: abs(f["pct_deviation"]), reverse=True)

    scan_metric = driving_factors[0]["metric"] if driving_factors else metric_name
    scan_thresholds = computed_thresholds.get(
        scan_metric, {"pct_threshold": config.PCT_DEVIATION_THRESHOLD, "volume_floor": config.MIN_VOLUME_FLOOR}
    )
    scan_dimensions = metrics.scannable_dimensions(scan_metric)
    ruled_out.extend(metrics.degenerate_notes(scan_metric))

    segment_candidates = timed_span(
        "segment_ranking",
        lambda: {
            dim: segment_ranking(
                client, day, scan_metric, dim,
                volume_floor=scan_thresholds["volume_floor"], hour_cutoff=hour_cutoff,
            )
            for dim in scan_dimensions
        },
        input={"metric": scan_metric, "day": str(day), "dimensions": scan_dimensions},
    )

    best = None
    for dim, ranked in segment_candidates.items():
        if not ranked:
            continue
        top = ranked[0]
        if best is None or abs(top["pct_deviation"]) > abs(best["pct_deviation"]):
            best = top

    for dim, ranked in segment_candidates.items():
        if not ranked:
            ruled_out.append(f"{dim}: no segment met the minimum volume floor on this day")
            continue
        top = ranked[0]
        if best is not None and top is best:
            continue
        if abs(top["pct_deviation"]) < scan_thresholds["pct_threshold"]:
            ruled_out.append(f"{dim}: no segment stands out (closest: {top['value']} at {top['pct_deviation']:+.1%})")

    if best is not None:
        combo = timed_span(
            "refine_segment",
            lambda: refine_segment(
                client, day, scan_metric, best["dimension"], best["value"], best["pct_deviation"],
                computed_thresholds, hour_cutoff=hour_cutoff,
            ),
            input={"metric": scan_metric, "day": str(day), "outer_dimension": best["dimension"], "outer_value": str(best["value"])},
        )
        if combo:
            best = dict(best, refined_by=combo)
            ruled_out.append(
                f"{best['dimension']}={best['value']}: further localized to {combo['dimension']}={combo['value']} "
                f"({combo['pct_deviation']:+.1%}, sharper than the segment alone)"
            )
        else:
            ruled_out.append(f"{best['dimension']}={best['value']}: no intersection with another dimension deviated more sharply than the segment alone")

    findings = {
        "metric": metric_name,
        "day": str(day),
        "overall": overall,
        "driving_factors": driving_factors,
        "responsible_segment": best,
        "checked_and_ruled_out": ruled_out,
    }
    if coverage_note:
        findings["data_coverage_note"] = coverage_note

    diagnosis_text = timed_span("narrate", lambda: llm.narrate(findings), input=findings)

    # Confidence: magnitude past threshold, discounted by how much baseline
    # history backs it - not a hardcoded number, computed from the same
    # data-derived bar as everything else.
    if best is not None:
        driver_pct_dev = best["refined_by"]["pct_deviation"] if best.get("refined_by") else best["pct_deviation"]
        magnitude = min(1.0, abs(driver_pct_dev) / (2 * scan_thresholds["pct_threshold"]))
        baseline_n = best.get("baseline_n") or config.TRAILING_WEEKS
        history_factor = max(0.5, min(1.0, baseline_n / config.TRAILING_WEEKS))
        confidence = round(magnitude * history_factor, 2)
    else:
        confidence = 0.3

    trace_id = trace.finish(output={"diagnosis_text": diagnosis_text, "responsible_segment": best, "confidence": confidence})

    cited_numbers = json.dumps(
        {
            "overall": overall,
            "driving_factors": driving_factors,
            "responsible_segment": best,
        },
        default=str,
    )

    if best is not None:
        responsible_segment_map = {best["dimension"]: str(best["value"])}
        if best.get("refined_by"):
            responsible_segment_map[best["refined_by"]["dimension"]] = str(best["refined_by"]["value"])
    else:
        responsible_segment_map = {}

    admin.insert(
        "inmobi_rca.investigations",
        [
            [
                anomaly_candidate_id,
                metric_name,
                day,
                diagnosis_text,
                responsible_segment_map,
                ruled_out,
                cited_numbers,
                confidence,
                trace_id or "",
            ]
        ],
        column_names=[
            "anomaly_candidate_id",
            "metric",
            "day",
            "diagnosis_text",
            "responsible_segment",
            "checked_and_ruled_out",
            "cited_numbers",
            "confidence",
            "langfuse_trace_id",
        ],
    )

    if anomaly_candidate_id:
        admin.command(
            "ALTER TABLE inmobi_rca.anomaly_candidates UPDATE status = 'investigated' WHERE id = {id:String}",
            parameters={"id": anomaly_candidate_id},
        )

    timings_dict = timings.as_dict(
        clickhouse_stages=(
            "day_coverage", "compute_thresholds", "overall_deviation",
            "factor_decomposition", "segment_ranking", "refine_segment",
        ),
        llm_stages=("narrate",),
    )
    timing.log(admin, "investigate", timings_dict)

    return {
        "metric": metric_name,
        "day": str(day),
        "diagnosis_text": diagnosis_text,
        "overall": overall,
        "driving_factors": driving_factors,
        "responsible_segment": best,
        "checked_and_ruled_out": ruled_out,
        "confidence": confidence,
        "data_coverage_note": coverage_note,
        "timings": timings_dict,
        "langfuse_trace_id": trace_id,
    }
