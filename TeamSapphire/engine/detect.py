"""Stage 1 — detection.

Finds hours where a headline metric deviates from what that hour should
normally look like. No LLM involved: this is arithmetic over the hourly rollup.

BASELINE CHOICE
---------------
The dataset has genuine daily (hour-of-day) and weekly (weekends lower)
seasonality, and the metrics glossary states outright that at least one planted
movement is *pure seasonality* that must be ruled out rather than alarmed on.

A flat average makes every weekend look like an incident. So the baseline for
any hour is the same weekday and the same hour-of-day from the trailing weeks —
Tuesday 14:00 is compared against previous Tuesdays at 14:00, never against
"the average hour".

The centre is the MEDIAN of those comparable hours, not the mean. With only a
handful of baseline samples, one previously-anomalous week would drag a mean
badly; the median ignores it. Note this is a statement about estimating a
*baseline*, and does not conflict with the glossary's sum/sum rule — that rule
governs how a metric is computed within any group, which is exactly how each
individual hour's fill rate, CTR and eCPM are computed below.

TWO GATES, NOT ONE
------------------
An hour is only flagged when the movement is both statistically unusual
(robust z-score) AND materially large (percentage change). Requiring both is
what stops the system crying wolf: in a 9M-row dataset, tiny deviations reach
statistical significance constantly while meaning nothing. The judging
criterion explicitly penalises false alarms.
"""
from dataclasses import dataclass, asdict
from typing import Any

from .db import DB

# Metrics we watch, and how each is computed from the rollup's additive columns.
# Every ratio is sum/sum within the hour, per the metrics glossary.
#
# `denom` is what makes the noise model honest. For a proportion, the hour-to-hour
# variance is dominated by counting noise in the numerator, and that noise scales
# with the denominator — so the denominator has to travel with the metric.
METRICS: dict[str, dict[str, str]] = {
    "revenue":   {"expr": "revenue", "kind": "sum"},
    "requests":  {"expr": "requests", "kind": "sum"},
    "fill_rate": {"expr": "if(requests > 0, fills / requests, 0)",
                  "kind": "proportion", "denom": "requests"},
    "ecpm":      {"expr": "if(impressions > 0, revenue / impressions * 1000, 0)",
                  "kind": "sum"},
    "ctr":       {"expr": "if(impressions > 0, clicks / impressions, 0)",
                  "kind": "proportion", "denom": "impressions"},
}

# Both gates must be passed to raise a finding.
DEFAULT_Z_THRESHOLD = 3.0        # robust z-score
DEFAULT_MIN_PCT_CHANGE = 0.08    # 8% — below this we do not care, however significant
DEFAULT_BASELINE_WEEKS = 4
MIN_BASELINE_SAMPLES = 2


@dataclass
class Finding:
    hour: str
    metric: str
    actual: float
    baseline: float
    pct_change: float
    z_score: float
    baseline_samples: int
    direction: str
    # Set when the finding came from the per-segment scan rather than the
    # global one. None means "the platform as a whole".
    dim_name: str | None = None
    dim_value: str | None = None

    @property
    def scope(self) -> str:
        return f"{self.dim_name}={self.dim_value}" if self.dim_name else "global"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Incident:
    """A contiguous run of flagged hours on one metric in one direction.

    Hours are the wrong unit to alarm on. Measured against the training window,
    hourly CTR flagged 102 of 600 hours scattered across nearly every day —
    clicks are only 0.83% of requests, so hourly CTR is inherently volatile and
    alarming per-hour is precisely the "crying wolf" that destroys trust in an
    alerting system.

    An incident is the honest unit: a sustained run of deviation. It suppresses
    isolated noise while a genuine event — 24 consecutive hours of revenue at
    -45% — stands out immediately and gets ranked by the impact it actually had.
    """
    metric: str
    start_hour: str
    end_hour: str
    hours: int
    direction: str
    peak_pct_change: float
    mean_pct_change: float
    peak_z: float
    total_actual: float
    total_baseline: float
    total_impact: float
    findings: list[Finding]
    dim_name: str | None = None
    dim_value: str | None = None

    @property
    def scope(self) -> str:
        return f"{self.dim_name}={self.dim_value}" if self.dim_name else "global"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["findings"] = [f.to_dict() for f in self.findings]
        return d

    def summary(self) -> dict[str, Any]:
        """Incident without the per-hour detail — what goes to the narrator."""
        d = self.to_dict()
        d.pop("findings")
        return d


def _build_sql(metric_expr: str, denom_expr: str) -> str:
    """Compare each hour against the same weekday+hour in trailing weeks."""
    return f"""
    WITH
        target AS (
            SELECT hour, toDayOfWeek(hour) AS dow, toHour(hour) AS hod,
                   requests, fills, impressions, clicks, revenue,
                   {metric_expr} AS metric_value,
                   {denom_expr}  AS denom
            FROM inmobi.events_hourly
            WHERE hour >= {{start:DateTime}} AND hour < {{end:DateTime}}
        ),
        hist AS (
            SELECT hour, toDayOfWeek(hour) AS dow, toHour(hour) AS hod,
                   {metric_expr} AS metric_value
            FROM inmobi.events_hourly
            WHERE hour < {{end:DateTime}}
        )
    SELECT
        t.hour                             AS hour,
        t.metric_value                     AS actual,
        t.denom                            AS denom,
        quantileExact(0.5)(h.metric_value) AS baseline,
        stddevPop(h.metric_value)          AS spread,
        count()                            AS baseline_samples
    FROM target AS t
    INNER JOIN hist AS h ON t.dow = h.dow AND t.hod = h.hod
    WHERE h.hour < t.hour
      AND h.hour >= t.hour - toIntervalWeek({{weeks:UInt8}})
    GROUP BY t.hour, t.metric_value, t.denom
    ORDER BY t.hour
    """


def _spread_for(kind: str, baseline: float, empirical: float, denom: float) -> float:
    """How much this metric moves when nothing is wrong.

    Using the empirical standard deviation alone is not safe here. It is
    estimated from only a handful of baseline hours, so it frequently comes out
    far too small, and a tiny denominator then produces an enormous z-score from
    pure counting noise.

    Measured on the training window: hourly CTR flagged 102 of 600 hours. Clicks
    are 0.83% of requests, so with ~8,200 impressions an hour the standard error
    of the CTR proportion is ~10.5% of CTR itself — meaning a 21% swing is about
    2 sigma, not the 10+ sigma a 2%-of-baseline floor implied. Every one of those
    flags was noise dressed up as significance.

    So for a proportion the floor is the binomial standard error, which scales
    correctly with the denominator. For sums and rates there is no such closed
    form, and a small relative floor keeps a degenerate spread from exploding.
    """
    if kind == "proportion" and denom > 0 and 0 < baseline < 1:
        binomial_se = (baseline * (1 - baseline) / denom) ** 0.5
        return max(empirical, binomial_se)
    return max(empirical, abs(baseline) * 0.02)


def detect(
    db: DB,
    start: str,
    end: str,
    metrics: list[str] | None = None,
    weeks: int = DEFAULT_BASELINE_WEEKS,
    z_threshold: float = DEFAULT_Z_THRESHOLD,
    min_pct_change: float = DEFAULT_MIN_PCT_CHANGE,
) -> tuple[list[Finding], list[dict]]:
    """Scan [start, end) for anomalous hours.

    Returns (findings, checked) where `checked` records every metric examined
    including the ones that came back clean — the ruled-out ledger starts here.
    """
    metrics = metrics or list(METRICS)
    findings: list[Finding] = []
    checked: list[dict] = []

    for metric in metrics:
        spec = METRICS[metric]
        res = db.query(
            _build_sql(spec["expr"], spec.get("denom", "0")),
            label=f"detect:{metric}",
            params={"start": start, "end": end, "weeks": weeks},
        )

        flagged_this_metric = 0
        worst_z = 0.0

        for row in res.rows:
            baseline = float(row["baseline"])
            actual = float(row["actual"])
            samples = int(row["baseline_samples"])

            if samples < MIN_BASELINE_SAMPLES or baseline == 0:
                continue

            spread = _spread_for(
                spec["kind"], baseline, float(row["spread"]), float(row["denom"])
            )
            z = (actual - baseline) / spread
            pct = (actual - baseline) / baseline

            worst_z = max(worst_z, abs(z))

            if abs(z) >= z_threshold and abs(pct) >= min_pct_change:
                flagged_this_metric += 1
                findings.append(Finding(
                    hour=str(row["hour"]),
                    metric=metric,
                    actual=actual,
                    baseline=baseline,
                    pct_change=pct,
                    z_score=z,
                    baseline_samples=samples,
                    direction="drop" if pct < 0 else "spike",
                ))

        checked.append({
            "metric": metric,
            "hours_examined": len(res.rows),
            "hours_flagged": flagged_this_metric,
            "max_abs_z": round(worst_z, 2),
            "verdict": "anomalous" if flagged_this_metric else "clean",
            "query_ms": round(res.query_ms, 1),
            "rows_read": res.rows_read,
        })

    # Most severe first: the largest absolute movement is the incident to chase.
    findings.sort(key=lambda f: abs(f.pct_change), reverse=True)
    return findings, checked


# An isolated flagged hour is noise until proven otherwise. A run this long, or
# a single hour this extreme, is an event worth investigating.
DEFAULT_MIN_RUN_HOURS = 3
DEFAULT_EXTREME_Z = 10.0


def cluster_incidents(
    findings: list[Finding],
    min_run_hours: int = DEFAULT_MIN_RUN_HOURS,
    extreme_z: float = DEFAULT_EXTREME_Z,
) -> tuple[list[Incident], list[dict]]:
    """Group flagged hours into incidents; report what was discarded as noise.

    Returns (incidents, discarded) — the discarded runs are kept because
    "we saw this and judged it noise" is itself evidence a reader can check,
    and silently dropping findings is indistinguishable from missing them.
    """
    from datetime import datetime

    def parse(h: str) -> datetime:
        return datetime.fromisoformat(h)

    runs: list[list[Finding]] = []
    keys = {(f.metric, f.direction, f.dim_name or "", f.dim_value or "") for f in findings}
    for metric, direction, dname, dvalue in sorted(keys):
        group = sorted(
            (f for f in findings
             if f.metric == metric and f.direction == direction
             and (f.dim_name or "") == dname and (f.dim_value or "") == dvalue),
            key=lambda f: f.hour,
        )
        current: list[Finding] = []
        for f in group:
            if current and (parse(f.hour) - parse(current[-1].hour)).total_seconds() <= 3600:
                current.append(f)
            else:
                if current:
                    runs.append(current)
                current = [f]
        if current:
            runs.append(current)

    incidents: list[Incident] = []
    discarded: list[dict] = []

    for run in runs:
        peak = max(run, key=lambda f: abs(f.z_score))
        is_incident = len(run) >= min_run_hours or abs(peak.z_score) >= extreme_z

        total_actual = sum(f.actual for f in run)
        total_baseline = sum(f.baseline for f in run)

        if not is_incident:
            discarded.append({
                "metric": run[0].metric,
                "scope": run[0].scope,
                "direction": run[0].direction,
                "start_hour": run[0].hour,
                "hours": len(run),
                "peak_z": round(peak.z_score, 2),
                "reason": f"run of {len(run)}h below {min_run_hours}h minimum "
                          f"and peak |z| {abs(peak.z_score):.1f} below {extreme_z}",
            })
            continue

        incidents.append(Incident(
            metric=run[0].metric,
            start_hour=run[0].hour,
            end_hour=run[-1].hour,
            hours=len(run),
            direction=run[0].direction,
            peak_pct_change=peak.pct_change,
            mean_pct_change=sum(f.pct_change for f in run) / len(run),
            peak_z=peak.z_score,
            total_actual=total_actual,
            total_baseline=total_baseline,
            total_impact=abs(total_actual - total_baseline),
            findings=run,
            dim_name=run[0].dim_name,
            dim_value=run[0].dim_value,
        ))

    # Rank by sustained severity: how far off, for how long.
    incidents.sort(key=lambda i: abs(i.mean_pct_change) * i.hours, reverse=True)
    return incidents, discarded


# ---------------------------------------------------------------------------
# Per-segment scan
# ---------------------------------------------------------------------------
# The global scan above can only see an incident large enough to move the
# platform-wide number. The problem statement says anomalies are planted "in
# specific segments and time windows", and a segment holding a few percent of
# traffic can lose half its revenue while the global metric barely twitches —
# well inside the 8% materiality gate, so the global scan would report nothing
# and the anomaly would be scored as missed.
#
# This scan applies the identical baseline, two-gate and clustering logic to
# every (dim_name, dim_value) independently, using the unpivoted rollup that
# exists precisely for this shape.
#
# A volume floor is required. Relative noise explodes as a segment shrinks, and
# without a floor the smallest segments generate almost all the findings — the
# same crying-wolf failure the binomial spread floor fixed for CTR.
DEFAULT_MIN_SEGMENT_VOLUME = 500


def _build_segment_sql(metric_expr: str, denom_expr: str) -> str:
    return f"""
    WITH
        target AS (
            SELECT hour, dim_name, dim_value,
                   toDayOfWeek(hour) AS dow, toHour(hour) AS hod,
                   requests, fills, impressions, clicks, revenue,
                   {metric_expr} AS metric_value,
                   {denom_expr}  AS denom
            FROM inmobi.events_hourly_by_dim
            WHERE hour >= {{start:DateTime}} AND hour < {{end:DateTime}}
              AND requests >= {{min_volume:UInt32}}
        ),
        hist AS (
            SELECT hour, dim_name, dim_value,
                   toDayOfWeek(hour) AS dow, toHour(hour) AS hod,
                   {metric_expr} AS metric_value
            FROM inmobi.events_hourly_by_dim
            WHERE hour < {{end:DateTime}}
        )
    SELECT
        t.hour      AS hour,
        t.dim_name  AS dim_name,
        t.dim_value AS dim_value,
        t.metric_value AS actual,
        t.denom        AS denom,
        quantileExact(0.5)(h.metric_value) AS baseline,
        stddevPop(h.metric_value)          AS spread,
        count()                            AS baseline_samples
    FROM target AS t
    INNER JOIN hist AS h
        ON  t.dim_name  = h.dim_name
        AND t.dim_value = h.dim_value
        AND t.dow = h.dow AND t.hod = h.hod
    WHERE h.hour < t.hour
      AND h.hour >= t.hour - toIntervalWeek({{weeks:UInt8}})
    GROUP BY t.hour, t.dim_name, t.dim_value, t.metric_value, t.denom
    ORDER BY t.hour
    """


def detect_segments(
    db: DB,
    start: str,
    end: str,
    metrics: list[str] | None = None,
    weeks: int = DEFAULT_BASELINE_WEEKS,
    z_threshold: float = DEFAULT_Z_THRESHOLD,
    min_pct_change: float = DEFAULT_MIN_PCT_CHANGE,
    min_volume: int = DEFAULT_MIN_SEGMENT_VOLUME,
) -> tuple[list[Finding], list[dict]]:
    """Scan every (dim_name, dim_value) for anomalies invisible at platform level."""
    metrics = metrics or list(METRICS)
    findings: list[Finding] = []
    checked: list[dict] = []

    for metric in metrics:
        spec = METRICS[metric]
        res = db.query(
            _build_segment_sql(spec["expr"], spec.get("denom", "0")),
            label=f"detect_segments:{metric}",
            params={"start": start, "end": end, "weeks": weeks, "min_volume": min_volume},
        )

        flagged = 0
        worst_z = 0.0
        for row in res.rows:
            baseline = float(row["baseline"])
            actual = float(row["actual"])
            samples = int(row["baseline_samples"])
            if samples < MIN_BASELINE_SAMPLES or baseline == 0:
                continue

            spread = _spread_for(spec["kind"], baseline, float(row["spread"]), float(row["denom"]))
            z = (actual - baseline) / spread
            pct = (actual - baseline) / baseline
            worst_z = max(worst_z, abs(z))

            if abs(z) >= z_threshold and abs(pct) >= min_pct_change:
                flagged += 1
                findings.append(Finding(
                    hour=str(row["hour"]), metric=metric,
                    actual=actual, baseline=baseline,
                    pct_change=pct, z_score=z, baseline_samples=samples,
                    direction="drop" if pct < 0 else "spike",
                    dim_name=row["dim_name"], dim_value=row["dim_value"],
                ))

        checked.append({
            "scan": "segment", "metric": metric,
            "segment_hours_examined": len(res.rows),
            "segment_hours_flagged": flagged,
            "max_abs_z": round(worst_z, 2),
            "verdict": "anomalous" if flagged else "clean",
            "query_ms": round(res.query_ms, 1), "rows_read": res.rows_read,
        })

    findings.sort(key=lambda f: abs(f.pct_change), reverse=True)
    return findings, checked
