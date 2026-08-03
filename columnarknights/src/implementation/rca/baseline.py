"""Anomaly detection: compare each day against a like-for-like baseline built
from the same weekday in trailing weeks (median + MAD), instead of a flat
global average. A flat average makes every weekend look anomalous; comparing
Sunday-to-Sunday (etc.) does not. See metrics_glossary.md, "Notes on normal".
"""

import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta

from .metrics import METRICS


@dataclass
class DayPoint:
    event_date: date
    numerator: float
    denominator: float

    @property
    def value(self) -> float:
        return self.numerator / self.denominator if self.denominator else 0.0


@dataclass
class Anomaly:
    event_date: date
    metric: str
    value: float
    baseline_median: float
    baseline_points: list[float]
    robust_z: float
    rel_delta: float
    direction: str  # "up" or "down"


@dataclass
class DayEvaluation:
    """Same baseline math as Anomaly, computed for every day (not just the
    ones that clear the anomaly threshold) -- e.g. for drawing a baseline
    line on a chart alongside the actual value. baseline_expected is None
    where there isn't enough same-weekday history yet to compute one."""
    event_date: date
    value: float
    baseline_expected: float | None
    robust_z: float
    rel_delta: float | None
    is_anomaly: bool
    direction: str | None


def daily_series(client, metric_name: str, start: date, end: date) -> list[DayPoint]:
    metric = METRICS[metric_name]
    query = f"""
        SELECT
            event_date,
            ({metric.numerator}) AS num,
            ({metric.denominator}) AS den
        FROM fact_events
        WHERE event_date BETWEEN {{start:Date}} AND {{end:Date}}
        GROUP BY event_date
        ORDER BY event_date
    """
    result = client.query(query, parameters={"start": start, "end": end})
    return [DayPoint(row[0], float(row[1]), float(row[2])) for row in result.result_rows]


def _robust_z(x: float, points: list[float]) -> float:
    if len(points) < 2:
        return 0.0
    median = statistics.median(points)
    mad = statistics.median(abs(p - median) for p in points)
    if mad == 0:
        return 0.0
    return 0.6745 * (x - median) / mad


def _linreg_predict(xs: list[float], ys: list[float], x0: float) -> tuple[float, list[float]]:
    """OLS fit y = a + b*x over the trailing same-weekday points, extrapolated
    to x0 (today). Nets out the slow growth trend the glossary describes, so a
    later week isn't flagged as "up" purely for being later — only a flat
    median of trailing weeks would make that mistake."""
    n = len(xs)
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    var_x = sum((x - mean_x) ** 2 for x in xs)
    if var_x == 0:
        return mean_y, [y - mean_y for y in ys]
    b = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / var_x
    a = mean_y - b * mean_x
    residuals = [y - (a + b * x) for x, y in zip(xs, ys)]
    return a + b * x0, residuals


def evaluate_series(
    series: list[DayPoint],
    metric_name: str,
    lookback_weeks: int = 4,
    z_thresh: float = 3.5,
    min_rel_delta: float = 0.02,
    min_history: int = 2,
    trend_min_points: int = 3,
) -> list[DayEvaluation]:
    """Two passes: the first uses every trailing same-weekday point as-is and
    may itself get fooled where a genuine one-day incident sits inside a later
    date's trend baseline (a single contaminated point can drag an OLS fit
    badly off, producing a knock-on false positive on a perfectly normal
    later date). The second pass excludes dates from anyone's baseline that
    the first pass flagged as *grossly* anomalous (a much stricter bar than
    final detection) and re-fits. Using the same threshold for both passes
    would cascade: a date only flagged because ITS OWN baseline was
    contaminated would itself get excluded, stripping otherwise-clean data
    out of a third date's baseline for no reason. The strict/loose split
    keeps exclusion limited to the genuinely gross outliers.

    Returns one DayEvaluation per input point (not just the anomalous ones),
    so a caller that wants "what was the expected baseline on an ordinary
    day" (e.g. to draw a baseline line on a chart) has it, not only the days
    that cleared the anomaly threshold."""
    by_date = {p.event_date: p for p in series}

    def _run(exclude: set, z_cut: float, rel_cut: float) -> dict[date, DayEvaluation]:
        out: dict[date, DayEvaluation] = {}
        for point in series:
            weeks_back = [
                k
                for k in range(1, lookback_weeks + 1)
                if (point.event_date - timedelta(weeks=k)) in by_date
                and (point.event_date - timedelta(weeks=k)) not in exclude
            ]
            if len(weeks_back) < min_history:
                out[point.event_date] = DayEvaluation(
                    event_date=point.event_date, value=point.value, baseline_expected=None,
                    robust_z=0.0, rel_delta=None, is_anomaly=False, direction=None,
                )
                continue
            baseline_points = [by_date[point.event_date - timedelta(weeks=k)].value for k in weeks_back]

            if len(baseline_points) >= trend_min_points:
                xs = [-float(k) for k in weeks_back]
                expected, residuals = _linreg_predict(xs, baseline_points, 0.0)
                mad = statistics.median(abs(r) for r in residuals)
                z = 0.6745 * (point.value - expected) / mad if mad else 0.0
            else:
                expected = statistics.median(baseline_points)
                z = _robust_z(point.value, baseline_points)

            rel_delta = (point.value - expected) / expected if expected else 0.0
            is_anomaly = abs(z) >= z_cut and abs(rel_delta) >= rel_cut
            out[point.event_date] = DayEvaluation(
                event_date=point.event_date, value=point.value, baseline_expected=expected,
                robust_z=z, rel_delta=rel_delta, is_anomaly=is_anomaly,
                direction="up" if point.value > expected else "down",
            )
        return out

    gross = _run(exclude=set(), z_cut=max(z_thresh * 1.5, 8.0), rel_cut=max(min_rel_delta * 5, 0.10))
    gross_dates = {d for d, e in gross.items() if e.is_anomaly}
    final = _run(exclude=gross_dates, z_cut=z_thresh, rel_cut=min_rel_delta)
    return [final[p.event_date] for p in series]


def detect_anomalies(
    series: list[DayPoint],
    metric_name: str,
    lookback_weeks: int = 4,
    z_thresh: float = 3.5,
    min_rel_delta: float = 0.02,
    min_history: int = 2,
    trend_min_points: int = 3,
) -> list[Anomaly]:
    evaluations = evaluate_series(
        series, metric_name, lookback_weeks, z_thresh, min_rel_delta, min_history, trend_min_points,
    )
    return [
        Anomaly(
            event_date=e.event_date, metric=metric_name, value=e.value,
            baseline_median=e.baseline_expected, baseline_points=[],
            robust_z=e.robust_z, rel_delta=e.rel_delta, direction=e.direction,
        )
        for e in evaluations if e.is_anomaly
    ]


@dataclass
class Incident:
    metric: str
    start: date
    end: date
    anomalies: list[Anomaly] = field(default_factory=list)

    @property
    def peak(self) -> Anomaly:
        return max(self.anomalies, key=lambda a: abs(a.rel_delta))


def merge_into_incidents(anomalies: list[Anomaly]) -> list[Incident]:
    """Collapse consecutive anomalous days (e.g. a 3-day dip) into one incident
    window, so the pipeline investigates it once instead of three times."""
    if not anomalies:
        return []
    ordered = sorted(anomalies, key=lambda a: a.event_date)
    incidents: list[Incident] = [
        Incident(metric=ordered[0].metric, start=ordered[0].event_date, end=ordered[0].event_date, anomalies=[ordered[0]])
    ]
    for a in ordered[1:]:
        current = incidents[-1]
        if (a.event_date - current.end).days <= 1:
            current.end = a.event_date
            current.anomalies.append(a)
        else:
            incidents.append(Incident(metric=a.metric, start=a.event_date, end=a.event_date, anomalies=[a]))
    return incidents
