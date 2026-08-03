from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from config import config
from config import hourly_source as _hourly
from data.calibration import effect_threshold
from data.client import run_query
from metrics import metric_sql
from models import Window
from rca.baseline import _detected
from rca.robust import mad, med, pct_delta, robust_z

_CFG = config()
_DET = _CFG["detection"]

# Revenue alone is not enough (see module docstring). Overridable via config.
DEFAULT_METRICS = _CFG["rca"].get(
    "incident_scan_metrics",
    ["revenue", "requests", "fill_rate", "render_rate", "ecpm", "ctr"],
)

_GRAIN_SQL = {"day": "toStartOfDay(hour)", "hour": "toStartOfHour(hour)"}
_GRAIN_STEP = {"day": timedelta(days=1), "hour": timedelta(hours=1)}

# Extra flat significance floor on top of the detection rule. DEFAULT 0 = disabled, because
# it is no longer needed: `_detected` now applies a per-metric, auto-calibrated floor
# (data.calibration.effect_threshold = multiplier x that metric's own measured noise), which
# already rejects the near-zero-move buckets this used to exist for.
#
# It was originally 0.1 to stop MAD-collapse buckets (a 0.0% move scoring z=8.6 off a 3-point
# baseline) from bridging gaps and merging Jun 23-25 + Jun 28-30 into one 10-day window.
# Verified that no longer happens: at 0.0 the scan still returns Jun 23 -> Jun 26 as a clean
# 3-day incident. Keeping a flat floor on top would just re-introduce a knob that has to be
# hand-tuned per dataset, and a metric-blind one at that - 10% is nothing for `requests`
# (21% calibrated floor) but enormous for `fill_rate` (2.8%).
#
# Still a parameter so tests and power users can force a coarser sweep; nothing in the UI
# sets it.
MIN_EFFECT = 0.0


@dataclass
class Bucket:
    """One time bucket of one metric, scored against its like-for-like baseline."""
    bucket: datetime
    observed: float
    expected: float
    robust_z: float
    pct_delta: float
    requests: int
    detected: bool


@dataclass
class Incident:
    metric: str
    window_start: datetime
    window_end: datetime          # exclusive
    direction: str                # drop | spike
    peak_z: float
    peak_pct_delta: float
    observed: float               # value at the peak bucket
    expected: float               # baseline at the peak bucket
    affected_requests: int
    buckets: int
    score: float                  # ranking: severity weighted by volume

    def incident_id(self) -> str:
        return f"{self.metric}:{self.window_start:%Y-%m-%dT%H}"

    def as_dict(self) -> dict:
        return {
            "incident_id": self.incident_id(),
            "metric": self.metric,
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "direction": self.direction,
            "peak_z": round(self.peak_z, 2),
            "peak_pct_delta": round(self.peak_pct_delta, 4),
            "observed": self.observed,
            "expected": self.expected,
            "affected_requests": self.affected_requests,
            "buckets": self.buckets,
            "score": round(self.score, 1),
        }


@dataclass
class ScanResult:
    incidents: list[Incident]
    queries: list[dict] = field(default_factory=list)


# ---- pure logic (unit-tested without a database) ---------------------------

def merge_windows(
    flagged: list[datetime], step: timedelta, max_gap: int = 1
) -> list[tuple[datetime, datetime]]:
    """Collapse adjacent flagged buckets into (start, end-exclusive) windows.

    `max_gap` tolerates short recoveries inside one incident: with max_gap=1 a single clean
    bucket between two flagged ones does not split them, which matters because a genuine
    multi-day anomaly often has one hour that scrapes back under the threshold.
    """
    if not flagged:
        return []
    ordered = sorted(flagged)
    windows: list[tuple[datetime, datetime]] = []
    start = prev = ordered[0]
    for current in ordered[1:]:
        if current - prev <= step * (max_gap + 1):
            prev = current
            continue
        windows.append((start, prev + step))
        start = prev = current
    windows.append((start, prev + step))
    return windows


def baseline_series(
    values: dict[datetime, float], bucket: datetime, weeks: int
) -> list[float]:
    """Like-for-like history: the same bucket one, two ... `weeks` weeks earlier.

    Same weekday and same hour-of-day, which is what keeps weekends from firing - Saturday
    traffic runs ~20% below a weekday and a flat mean would alarm every weekend.
    """
    out = []
    for w in range(1, weeks + 1):
        prior = values.get(bucket - timedelta(weeks=w))
        if prior is not None:
            out.append(prior)
    return out


def score_buckets(
    values: dict[datetime, float],
    requests: dict[datetime, int],
    targets: list[datetime],
    weeks: int,
    calibrated_effect: float,
    min_effect: float = MIN_EFFECT,
) -> list[Bucket]:
    """Score each target bucket against its own like-for-like baseline.

    `calibrated_effect` is `_detected`'s per-metric, auto-calibrated effect-size floor (see
    data.calibration.effect_threshold) — computed by the CALLER (scan_incidents, which already
    talks to ClickHouse per metric) and passed in as a plain number, deliberately, so this
    function stays DB-free and unit-testable (see tests/test_incidents.py).

    `min_effect` is an optional flat floor ON TOP of that, defaulting to 0 (disabled) - see
    MIN_EFFECT above for why it is no longer needed. Detection is fully auto-calibrated: nobody
    has to pick a number for a new dataset.
    """
    scored = []
    for bucket in sorted(targets):
        observed = values.get(bucket)
        series = baseline_series(values, bucket, weeks)
        if observed is None or not series:
            continue
        centre = med(series)
        spread = mad(series, centre)
        z = robust_z(observed, centre, spread, _DET["mad_scale"])
        pct = pct_delta(observed, centre)
        scored.append(
            Bucket(
                bucket=bucket, observed=observed, expected=centre, robust_z=z, pct_delta=pct,
                requests=requests.get(bucket, 0),
                detected=_detected(z, spread, pct, calibrated_effect) and abs(pct) >= min_effect,
                # ^ calibrated_effect is a plain number (see docstring); no metric/DB lookup here.
            )
        )
    return scored


def build_incidents(metric: str, scored: list[Bucket], step: timedelta) -> list[Incident]:
    """Group detected buckets into incidents, ranked by severity weighted by volume.

    Volume weighting matters: a 40% swing on a bucket with 12 requests is noise, while the
    same swing across a full day of traffic is the thing you want at the top of the list.
    """
    incidents = []
    for start, end in merge_windows([b.bucket for b in scored if b.detected], step):
        # Include every bucket in the window, not just the flagged ones, so a short
        # recovery inside an incident still counts toward its volume.
        members = [b for b in scored if start <= b.bucket < end]
        peak = max(members, key=lambda b: abs(b.robust_z))
        volume = sum(b.requests for b in members)
        incidents.append(
            Incident(
                metric=metric, window_start=start, window_end=end,
                direction="drop" if peak.observed < peak.expected else "spike",
                peak_z=peak.robust_z, peak_pct_delta=peak.pct_delta,
                observed=peak.observed, expected=peak.expected,
                affected_requests=volume, buckets=len(members),
                score=abs(peak.pct_delta) * volume,
            )
        )
    return incidents


def base_metric(metric: str) -> str:
    """"fill_rate[os_version=iOS 18.1]" -> "fill_rate"."""
    return metric.split("[", 1)[0]


# How much two incidents' windows must coincide before one can be called an echo of the other.
# Jaccard (intersection/union), NOT mere overlap: two independent anomalies on the same metric
# can share a day or two by coincidence, and treating that as an echo silently swallows a real
# finding. Measured: ecpm[ad_format=native] Jun 16-20 and ecpm[category=finance] Jun 19-22 are
# separate planted anomalies overlapping by 2 of 7 days (Jaccard 0.29) — "any overlap" hid the
# finance one entirely. True echoes coincide almost exactly (iOS 18.1 and APAC are both exactly
# Jun 28-30, Jaccard 1.0).
_ECHO_WINDOW_SIMILARITY = 0.6


def _window_similarity(a: Incident, b: Incident) -> float:
    """Jaccard overlap of two time windows: 1.0 = identical, 0.0 = disjoint."""
    inter = (min(a.window_end, b.window_end) - max(a.window_start, b.window_start)).total_seconds()
    if inter <= 0:
        return 0.0
    union = (max(a.window_end, b.window_end) - min(a.window_start, b.window_start)).total_seconds()
    return inter / union if union else 0.0


def _coincides(a: Incident, b: Incident) -> bool:
    return _window_similarity(a, b) >= _ECHO_WINDOW_SIMILARITY


def classify_echoes(incidents: list[Incident]) -> list[dict]:
    """Mark each incident primary | echo, so a human reads a handful instead of ~180.

    A segment sweep necessarily reports the same real event many times over, in two ways:

      1. GLOBAL echo. When the whole population moves (the Jun 21 collapse), every segment
         legitimately shows it too — that one event produced ~120 of the 183 rows, appearing
         under campaign_type=CPM, publisher_tier=tier_2, region=NAM and so on. If the same
         base metric already fired GLOBALLY over an overlapping window, the segment rows are
         echoes of that, not separate findings.

      2. CORRELATED echo. One localised cause lights up every segment correlated with it.
         The Jun 28-30 fill_rate drop is really os_version=iOS 18.1 in APAC, but it also
         flagged region=APAC, country=JP and device_model=iPhone 14 — all just places iOS 18.1
         is common. Within a cluster (same base metric, overlapping window) the true cause
         ranks highest, because score = |pct move| x volume and an echo is a diluted version
         of its cause: it mixes in unaffected traffic, so its percentage move is smaller.
         Verified on both known incidents — iOS 18.1 (10,279) over APAC (9,288) / iPhone 14
         (5,956) / JP (5,891); Android 15 (36,010) over tier_2 (15,860) / EU (15,104).

    Nothing is discarded — echoes are labelled and kept, because "checked, and it is explained
    by X" is exactly the ruled-out evidence the diagnosis needs.
    """
    ranked = sorted(incidents, key=lambda i: i.score, reverse=True)
    globals_ = [i for i in ranked if "[" not in i.metric]
    out: list[dict] = []
    cluster_leads: list[Incident] = []

    for inc in ranked:
        row = inc.as_dict()
        is_segment = "[" in inc.metric
        parent = None

        if is_segment:
            parent = next(
                (g for g in globals_ if base_metric(g.metric) == base_metric(inc.metric) and _coincides(g, inc)),
                None,
            )
            if parent is not None:
                row["role"] = "echo"
                row["echo_of"] = f"{parent.metric} (population-wide over the same window)"

        if "role" not in row:
            lead = next(
                (c for c in cluster_leads
                 if base_metric(c.metric) == base_metric(inc.metric) and _coincides(c, inc) and c is not inc),
                None,
            )
            if lead is not None:
                row["role"] = "echo"
                row["echo_of"] = f"{lead.metric} (stronger overlapping signal, same metric)"
            else:
                row["role"] = "primary"
                cluster_leads.append(inc)

        out.append(row)
    return out


# Revenue = Requests x FillRate x eCPM/1000. When one of these already explains an anomaly,
# revenue/rpr moving in the same segment+window is the mathematical consequence, not a second
# root cause. Confirmed on real data: ecpm[category=finance] and revenue[category=finance] are
# the SAME 4-day window, and revenue[os_version=Android 15] (Jun 21-26, 5 buckets) is really the
# Jun 21 global collapse plus its Android-15 share of the already-explained Jun 23-25 fill_rate
# drop, merged into one window by merge_windows' gap tolerance. Neither is a distinct finding.
_REVENUE_FACTORS = ("requests", "fill_rate", "ecpm")


def _segment_key(metric: str) -> str:
    """"fill_rate[os_version=Android 15]" -> "os_version=Android 15". "" for a global metric."""
    return metric.split("[", 1)[1][:-1] if "[" in metric else ""


def fold_revenue_identity(rows: list[dict]) -> None:
    """Mutates `rows` in place: marks a primary revenue/rpr row as an echo of a primary
    requests/fill_rate/ecpm row when their windows overlap and they're the same segment — or
    the factor is a GLOBAL row whose drill-down `localized` segment matches this row's segment
    (this is why it must run AFTER localization, unlike classify_echoes which is DB-free).
    """
    primaries = [r for r in rows if r["role"] == "primary"]
    for row in primaries:
        if base_metric(row["metric"]) not in ("revenue", "rpr"):
            continue
        seg_key = _segment_key(row["metric"])
        row_start = datetime.fromisoformat(row["window_start"])
        row_end = datetime.fromisoformat(row["window_end"])

        for cand in primaries:
            if cand is row or base_metric(cand["metric"]) not in _REVENUE_FACTORS:
                continue
            cand_start = datetime.fromisoformat(cand["window_start"])
            cand_end = datetime.fromisoformat(cand["window_end"])
            if not (row_start < cand_end and cand_start < row_end):  # any real overlap
                continue

            same_segment = _segment_key(cand["metric"]) == seg_key
            localized = cand.get("localized") or {}
            localized_match = (
                seg_key != "" and "=" in seg_key
                and localized.get(seg_key.split("=", 1)[0]) == seg_key.split("=", 1)[1]
            )
            if same_segment or localized_match:
                row["role"] = "echo"
                row["echo_of"] = f"{cand['metric']} (revenue identity: revenue ~= requests x fill_rate x ecpm)"
                break


# When a segment's total volume collapses (globally or just in that segment), every ratio
# metric there gets noisier that same day purely from the smaller sample - NOT because the
# ratio itself broke. Confirmed: ctr[country=ZA] and ecpm[country=FR] both single-bucket,
# both Jun 21 - ZA's requests fell 6,608 -> 2,984 that day (the already-known global collapse
# reaching a small country), and CTR just wobbled more on a smaller denominator. Scoped
# deliberately narrow (single-bucket only, fully CONTAINED in the volume event's window, not
# just overlapping) so this can't accidentally swallow a genuinely multi-day, independent
# finding like the 3-day Android 15 or iOS 18.1 incidents.
def fold_volume_driven_noise(rows: list[dict]) -> None:
    """Mutates `rows` in place: marks a single-bucket primary row as an echo of any already-
    primary requests/revenue row (global OR same-segment) whose window fully contains it."""
    primaries = [r for r in rows if r["role"] == "primary"]
    volume_events = [
        r for r in primaries
        if base_metric(r["metric"]) in ("requests", "revenue") and r["buckets"] >= 1
    ]
    for row in primaries:
        if row["buckets"] > 1 or base_metric(row["metric"]) in ("requests", "revenue"):
            continue
        seg_key = _segment_key(row["metric"])
        row_start = datetime.fromisoformat(row["window_start"])
        row_end = datetime.fromisoformat(row["window_end"])

        for vol in volume_events:
            if vol is row:
                continue
            vol_seg_key = _segment_key(vol["metric"])
            if vol_seg_key not in ("", seg_key):  # global, or the exact same segment
                continue
            vol_start = datetime.fromisoformat(vol["window_start"])
            vol_end = datetime.fromisoformat(vol["window_end"])
            if vol_start <= row_start and row_end <= vol_end:  # fully contained, not just overlapping
                row["role"] = "echo"
                row["echo_of"] = f"{vol['metric']} (sample-size noise during a volume event, not an independent move)"
                break


# classify_echoes' population-echo rule requires HIGH window similarity (Jaccard >= 0.6) to
# avoid falsely merging distinct events (see test_independent_anomalies_sharing_a_couple_of_
# days_stay_separate). That correctly protects against two SEPARATE events that happen to
# share a couple of days, but it also rejects a genuine sub-window: fill_rate[country=JP]
# (Jun 25, 1 day) sits entirely INSIDE the already-known fill_rate Android 15 event
# (Jun 23-26, 3 days) - Jaccard is only 1/3, so it slipped through as "distinct" even though
# JP is just a smaller, weaker echo of the exact same event (some Android 15 users are in
# Japan). Containment is a stronger, safer test than Jaccard similarity for this specific
# case: a full subset in time, same metric, is not "coincidentally overlapping" the way two
# independent anomalies can be - it can only be inside because it's part of the same thing.
def fold_contained_same_metric(rows: list[dict]) -> None:
    """Mutates `rows` in place: marks a primary row as an echo of another primary row of the
    SAME base metric whose window fully contains it (and is itself larger/stronger)."""
    primaries = [r for r in rows if r["role"] == "primary"]
    for row in primaries:
        bm = base_metric(row["metric"])
        row_start = datetime.fromisoformat(row["window_start"])
        row_end = datetime.fromisoformat(row["window_end"])

        best = None
        for cand in primaries:
            if cand is row or base_metric(cand["metric"]) != bm or cand["score"] <= row["score"]:
                continue
            cand_start = datetime.fromisoformat(cand["window_start"])
            cand_end = datetime.fromisoformat(cand["window_end"])
            if cand_start <= row_start and row_end <= cand_end:  # fully contained
                if best is None or cand["score"] > best["score"]:
                    best = cand
        if best is not None:
            row["role"] = "echo"
            row["echo_of"] = f"{best['metric']} (same metric, contained within its window — a weaker echo of the same event)"


# ---- engine (runs against ClickHouse) --------------------------------------

def _series_sql(metric: str, grain: str) -> str:
    """One pass covering the target range AND its trailing history."""
    # `AS bucket_requests`, not `AS requests`: aliasing to the column name makes ClickHouse
    # resolve the inner `requests` to the alias and reject it as a nested aggregate.
    return (
        f"SELECT {_GRAIN_SQL[grain]} AS bucket, {metric_sql(metric, 'rollup')} AS value, "
        f"sum(requests) AS bucket_requests FROM {_hourly()} "
        f"WHERE hour >= toDateTime({{hist_start:String}}) AND hour < toDateTime({{end:String}}) "
        f"GROUP BY bucket ORDER BY bucket"
    )


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def scan_incidents(
    start: datetime,
    end: datetime,
    metrics: list[str] | None = None,
    grain: str | None = None,
    min_effect: float = MIN_EFFECT,
) -> ScanResult:
    """Sweep [start, end) across every metric and return ranked, merged incidents."""
    grain = grain or "day"
    if grain not in _GRAIN_SQL:
        raise ValueError(f"grain must be one of {sorted(_GRAIN_SQL)}, got {grain!r}")
    metrics = metrics or DEFAULT_METRICS
    weeks = _DET["baseline_weeks"]
    step = _GRAIN_STEP[grain]
    hist_start = start - timedelta(weeks=weeks)

    incidents: list[Incident] = []
    queries: list[dict] = []
    for metric in metrics:
        out = run_query(
            _series_sql(metric, grain),
            {"hist_start": _fmt(hist_start), "end": _fmt(end)},
            name=f"scan:{metric}",
        )
        values = {r[0]: float(r[1]) for r in out["rows"] if r[1] is not None}
        requests = {r[0]: int(r[2]) for r in out["rows"]}
        targets = [b for b in values if start <= b < end]
        calibrated_effect = effect_threshold(metric)  # DB-touching; belongs in this loop, not score_buckets
        scored = score_buckets(values, requests, targets, weeks, calibrated_effect, min_effect)
        found = build_incidents(metric, scored, step)
        incidents.extend(found)
        queries.append({
            "id": f"q_scan_{metric}",
            "sql": out["resolved_sql"],
            "result_summary": {"buckets": len(targets), "incidents": len(found)},
            "langfuse_span_id": out.get("langfuse_span_id"),
        })

    incidents.sort(key=lambda i: i.score, reverse=True)
    return ScanResult(incidents=incidents, queries=queries)


# ---- global scan under a CHOSEN detector (robust_z / seasonal_ml / isolation_forest) -------
#
# scan_incidents() above IS the robust_z path, vectorized into one query per metric because
# robust_z's baseline is a cheap median/MAD over a handful of historical points. seasonal_ml
# and isolation_forest don't have that shortcut - each scores one target hour by fitting/
# comparing against the WHOLE series, so scanning a window means calling detect() once per
# bucket. That's real cost (N buckets x M metrics DB round-trips, not 1 x M), which is why this
# is a separate path rather than the default: robust_z stays the fast, always-on choice, and
# switching detector is something the caller opts into for a specific comparison, not something
# that silently slows down every sweep.
#
# NOTE: this only changes how the GLOBAL/population-level anomaly is scored. Segment
# localization is unaffected - scan_segments() and the drill-down both stay on the calibrated
# robust_z path regardless of the chosen method, because that is the only one vectorized to
# scan every segment value cheaply. Fitting IsolationForest per segment per dimension would be
# the same 5000x-slower mistake we already measured and avoided for robust_z's own drill-down.

def _bucket_volumes(start: datetime, end: datetime, grain: str) -> dict[datetime, int]:
    """requests per bucket, for volume-weighting the incident score regardless of which
    metric/detector produced the anomaly."""
    sql = f"SELECT {_GRAIN_SQL[grain]} AS bucket, sum(requests) AS vol FROM {_hourly()} WHERE hour >= toDateTime({{s:String}}) AND hour < toDateTime({{e:String}}) GROUP BY bucket"
    out = run_query(sql, {"s": _fmt(start), "e": _fmt(end)})
    return {r[0]: int(r[1]) for r in out["rows"]}


def scan_incidents_with_method(
    start: datetime, end: datetime, method: str, metrics: list[str] | None = None,
    grain: str | None = None,
) -> ScanResult:
    """scan_incidents(), but the global pass uses `method` instead of always robust_z.

    method='robust_z' just delegates to scan_incidents() unchanged (no reason to pay the
    per-bucket cost when the vectorized path gives the identical answer).
    """
    if method == "robust_z":
        return scan_incidents(start, end, metrics, grain)

    from rca.detection import detect  # local import: avoids a module-load-time cycle risk

    grain = grain or "day"
    if grain not in _GRAIN_SQL:
        raise ValueError(f"grain must be one of {sorted(_GRAIN_SQL)}, got {grain!r}")
    metrics = metrics or DEFAULT_METRICS
    step = _GRAIN_STEP[grain]
    volumes = _bucket_volumes(start - timedelta(weeks=_DET["baseline_weeks"]), end, grain)

    incidents: list[Incident] = []
    queries: list[dict] = []
    for metric in metrics:
        scored: list[Bucket] = []
        bucket = start
        while bucket < end:
            window = Window(start=bucket, end=bucket + step)
            try:
                anomaly, qs = detect(metric, window, method)
            except Exception:  # noqa: BLE001 -- a failed bucket just doesn't score
                bucket += step
                continue
            queries.extend(qs)
            scored.append(Bucket(
                bucket=bucket, observed=anomaly.observed, expected=anomaly.expected,
                robust_z=anomaly.score, pct_delta=anomaly.pct_delta,
                requests=volumes.get(bucket, 0), detected=anomaly.detected,
            ))
            bucket += step
        found = build_incidents(metric, scored, step)
        incidents.extend(found)

    incidents.sort(key=lambda i: i.score, reverse=True)
    return ScanResult(incidents=incidents, queries=queries)


# ---- per-segment scan: catches anomalies scan_incidents structurally cannot see -----------
#
# scan_incidents() only ever checks the GLOBAL aggregate per metric. That misses anything
# localized to one segment whose effect gets diluted below the detection floor once averaged
# across every other (unaffected, or growing) segment. Confirmed on real data: APAC fill_rate
# collapsed ~6-7% (z in the hundreds) on Jun 28-30, while the GLOBAL fill_rate move that same
# window was only 0.8-2.3% - comfortably under the calibrated floor - because total traffic
# was simultaneously growing (organic volume growth masked a real regional problem). Global-only
# scanning would never surface this; it was only found because a code comment happened to
# mention it. This function exists so "how many anomalies are in this dataset" doesn't depend
# on stumbling across a hint.

# Low-cardinality dimensions only for a broad sweep. app_id (2000 values) and advertiser_id
# (501) are excluded here deliberately: at ~2 requests/hour/app, ratio metrics degenerate
# (fill_rate can only be 0, 0.5, or 1 - see project-clickathon-detection-methodology memory),
# so a broad per-app sweep would mostly surface sampling-noise artifacts, not real incidents.
SEGMENT_SCAN_DIMENSIONS = [
    "region", "country", "os_version", "device_model", "ad_format",
    "category", "publisher_tier", "vertical", "campaign_type",
]

# Below this many requests over the WHOLE scan window, a segment's ratio metrics are too
# sparse to trust (same degenerate-ratio problem as app_id, just for any segment that happens
# to be small). Filters noise without hardcoding which segments to skip.
MIN_SEGMENT_VOLUME = 5_000


def _series_sql_by_segment(metric: str, grain: str, dimension: str) -> str:
    """One pass covering every value of `dimension` at once - vectorized (one query
    regardless of cardinality), not one query per segment value. See the ~5000x benchmark
    in project-clickathon-detection-methodology memory for why this matters."""
    return (
        f"SELECT {dimension} AS seg, {_GRAIN_SQL[grain]} AS bucket, "
        f"{metric_sql(metric, 'rollup')} AS value, sum(requests) AS bucket_requests "
        f"FROM {_hourly()} "
        f"WHERE hour >= toDateTime({{hist_start:String}}) AND hour < toDateTime({{end:String}}) "
        f"GROUP BY seg, bucket ORDER BY seg, bucket"
    )


def scan_segments(
    start: datetime,
    end: datetime,
    metrics: list[str] | None = None,
    dimensions: list[str] | None = None,
    grain: str | None = None,
    min_effect: float = MIN_EFFECT,
    min_segment_volume: int = MIN_SEGMENT_VOLUME,
) -> ScanResult:
    """Sweep [start, end) across every metric AND every value of every dimension.

    One query per (metric, dimension) pair fetches every segment value's series at once
    (vectorized SQL), then the same pure score_buckets()/build_incidents() logic used by
    scan_incidents() runs once per segment in Python - no DB access in that inner loop, so
    looping there is cheap even at high cardinality.

    Incident IDs are namespaced as "metric[dimension=value]" so they're distinguishable from
    scan_incidents()'s plain "metric" IDs in a combined result set.
    """
    grain = grain or "day"
    if grain not in _GRAIN_SQL:
        raise ValueError(f"grain must be one of {sorted(_GRAIN_SQL)}, got {grain!r}")
    metrics = metrics or DEFAULT_METRICS
    dimensions = dimensions or SEGMENT_SCAN_DIMENSIONS
    weeks = _DET["baseline_weeks"]
    step = _GRAIN_STEP[grain]
    hist_start = start - timedelta(weeks=weeks)

    incidents: list[Incident] = []
    queries: list[dict] = []
    for metric in metrics:
        calibrated_effect = effect_threshold(metric)
        for dimension in dimensions:
            out = run_query(
                _series_sql_by_segment(metric, grain, dimension),
                {"hist_start": _fmt(hist_start), "end": _fmt(end)},
                name=f"scan_seg:{metric}:{dimension}",
            )
            by_seg_values: dict[str, dict[datetime, float]] = {}
            by_seg_requests: dict[str, dict[datetime, int]] = {}
            for seg, bucket, value, bucket_requests in out["rows"]:
                if not seg or value is None:  # skip empty-string segments (e.g. unfilled rows)
                    continue
                by_seg_values.setdefault(seg, {})[bucket] = float(value)
                by_seg_requests.setdefault(seg, {})[bucket] = int(bucket_requests)

            found_this_pass = 0
            for seg, values in by_seg_values.items():
                if sum(by_seg_requests[seg].values()) < min_segment_volume:
                    continue
                targets = [b for b in values if start <= b < end]
                scored = score_buckets(values, by_seg_requests[seg], targets, weeks, calibrated_effect, min_effect)
                found = build_incidents(f"{metric}[{dimension}={seg}]", scored, step)
                incidents.extend(found)
                found_this_pass += len(found)

            queries.append({
                "id": f"q_scan_seg_{metric}_{dimension}",
                "sql": out["resolved_sql"],
                "result_summary": {"segments": len(by_seg_values), "incidents": found_this_pass},
                "langfuse_span_id": out.get("langfuse_span_id"),
            })

    incidents.sort(key=lambda i: i.score, reverse=True)
    return ScanResult(incidents=incidents, queries=queries)
