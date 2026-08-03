"""Dev/admin dashboard — data & table ops + a detection benchmarker, served at /dev.

LOCAL DEV ONLY. Mounted (in api/main.py) only when env ENABLE_DEV_DASHBOARD is truthy (default on).
Destructive ops (drop/load) require a typed confirm that is re-checked server-side, and table names
are allow-listed against the live SHOW TABLES set so a path can't smuggle arbitrary SQL.

Core logic lives in plain functions (unit-tested with the DB patched); the router is a thin wrapper.
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from config import config, env
from data import store
from data.client import get_client, run_query
from models import Window
from rca import drilldown, incidents
from rca.bundle import build_bundle
from rca.detection import detect, detect_in_window

_HTML = Path(__file__).resolve().parent / "dev_dashboard.html"
_CASES = Path(__file__).resolve().parent / "benchmark_cases.json"

_JOBS: dict[str, dict] = {}  # process-local load-job registry

# Drill-down is the expensive part (a query per dimension per level), so only the top-ranked
# incidents get localised — the tail is almost always echoes of the same event.
_DISCOVER_LOCALIZE_TOP = 8


def dev_enabled() -> bool:
    val = (env("ENABLE_DEV_DASHBOARD", "1") or "").strip().lower()
    return val not in ("", "0", "false", "no", "off")


# ---- tables & data ---------------------------------------------------------

def _table_names() -> list[str]:
    return [r[0] for r in run_query("SHOW TABLES")["rows"]]


def list_tables() -> list[dict]:
    out = []
    for name in _table_names():
        count = run_query(f"SELECT count() FROM {name}")["rows"][0][0]
        out.append({"name": name, "rows": count})
    return out


def preview_table(name: str, limit: int = 20) -> dict:
    if name not in _table_names():
        raise ValueError(f"unknown table: {name!r}")
    res = run_query(f"SELECT * FROM {name} LIMIT {int(limit)}")
    return {"columns": res["columns"], "rows": res["rows"]}


def drop_table(name: str, confirm: str) -> dict:
    if name not in _table_names():
        raise ValueError(f"unknown table: {name!r}")
    if confirm != name:
        raise ValueError("confirm must exactly equal the table name")
    get_client().command(f"DROP TABLE IF EXISTS {name}")
    return {"dropped": name}


# ---- load job (background) -------------------------------------------------

def start_load_job(confirm: str) -> dict:
    if confirm != "LOAD":
        raise ValueError('confirm must equal "LOAD"')
    job_id = uuid4().hex[:8]
    _JOBS[job_id] = {"status": "running", "log": "", "finished": False}
    threading.Thread(target=_run_load, args=(job_id,), daemon=True).start()
    return {"job_id": job_id}


def _run_load(job_id: str) -> None:
    buf = io.StringIO()
    try:
        from data.load import main as load_main
        with contextlib.redirect_stdout(buf):
            load_main()
        _JOBS[job_id].update(status="done", log=buf.getvalue(), finished=True)
    except Exception as exc:  # noqa: BLE001 — surface any load failure to the UI
        _JOBS[job_id].update(status="error", log=f"{buf.getvalue()}\nERROR: {exc}", finished=True)


def job_status(job_id: str) -> dict:
    job = _JOBS.get(job_id)
    if job is None:
        raise ValueError(f"unknown job: {job_id!r}")
    return {"job_id": job_id, **job}


# ---- benchmarker: playground ----------------------------------------------

def _deep_merge(dst: dict, src: dict) -> None:
    """Recursive merge so a nested override (e.g. isolation_forest.features) keeps sibling keys."""
    for key, val in src.items():
        if isinstance(val, dict) and isinstance(dst.get(key), dict):
            _deep_merge(dst[key], val)
        else:
            dst[key] = val


# Each detector's score is on a DIFFERENT scale — surfacing this stops cross-method confusion.
_SCORE_KIND = {
    "robust_z": "robust z-score (|z| vs threshold)",
    "seasonal_ml": "residual z-score (|z| vs threshold)",
    "isolation_forest": "IsolationForest score (sign = verdict; ~-0.5..0.5)",
}


def _score_kind(method: str) -> str:
    return _SCORE_KIND.get(method, method)


def run_detect(metric: str, at: str, method: str | None = None, overrides: dict | None = None,
               segment_aware: bool = False) -> dict:
    """Run detection with IN-MEMORY config overrides, restoring config afterward (never writes disk).

    segment_aware=False scores only the GLOBAL aggregate. That is blind to a localised anomaly by
    construction — the APAC x iOS 18.1 fill_rate drop is -51% in-segment but only -1.2% globally,
    so every detector scores 0 on it regardless of quality. segment_aware=True adds the second
    phase (per-dimension scan when the global pass finds nothing), which is what takes the
    ground-truth harness from 3/5 cases to 5/5. See rca.detection.detect_in_window.
    """
    start = datetime.fromisoformat(at)
    window = Window(start=start, end=start + timedelta(hours=1))
    det = config()["detection"]
    snapshot = copy.deepcopy(det)
    segment: dict = {}
    try:
        if method:
            det["method"] = method
        if overrides:
            _deep_merge(det, overrides)
        if segment_aware:
            anomaly, queries, _, segment = detect_in_window(metric, window, method)
        else:
            anomaly, queries = detect(metric, window)
    finally:
        det.clear()
        det.update(snapshot)
    resolved = method or snapshot["method"]
    return {"method": resolved, "score_kind": _score_kind(resolved), "anomaly": anomaly.model_dump(),
            "queries": queries, "found_in_segment": segment}


def run_compare(metric: str, at: str) -> list[dict]:
    return [run_detect(metric, at, method=m) for m in ("robust_z", "seasonal_ml")]


# ---- benchmarker: ground-truth harness (stubbed; localization -> JAL-77) ---

def benchmark_cases() -> list[dict]:
    return json.loads(_CASES.read_text())


def _case_target(window: str) -> datetime:
    # "2026-06-23..25" or "2026-06-21" -> the window's first day at noon (detection sample hour).
    return datetime.fromisoformat(window.split("..")[0] + "T12:00")


def _case_window(window: str) -> Window:
    """Parse "2026-06-23..25" / "2026-06-21" into a [start, end) window (end exclusive, whole days)."""
    parts = window.split("..")
    start = datetime.fromisoformat(parts[0])
    if len(parts) == 2:
        end = datetime.fromisoformat(parts[0][:8] + f"{int(parts[1]):02d}") + timedelta(days=1)
    else:
        end = start + timedelta(days=1)
    return Window(start=start, end=end)


def localize(metric: str, start: str, end: str) -> dict:
    """Run the drill-down over a window and return the localized segment + path + queries."""
    window = Window(start=datetime.fromisoformat(start), end=datetime.fromisoformat(end))
    path, localized, queries = drilldown.drill(metric, metric, window, drilldown.baseline_window(window))
    return {"localized": localized, "path": [n.model_dump() for n in path], "queries": queries}


def discover(start: str, end: str, grain: str = "day", scope: str = "both", min_effect: float = 0.0,
            method: str = "isolation_forest") -> dict:
    """Find anomalies in an ARBITRARY window — no ground-truth case list involved.

    This is what the fixed benchmark cases can't do: point it at any date range (e.g. the
    unseen-incident slice) and let it sweep. Two scopes, because they catch different things:

      global   — rca.incidents.scan_incidents: one series per metric. Catches anomalies big
                 enough to move the population (Jun 21 collapse, Jun 23-25 fill_rate).
      segment  — rca.incidents.scan_segments: every value of every low-cardinality dimension.
                 Catches anomalies that are severe inside a segment but diluted globally —
                 the APAC/iOS 18.1 fill_rate drop moves the global figure only -1.2% and is
                 invisible to a global-only sweep.

    `method` (robust_z / seasonal_ml / isolation_forest) selects the detector for the GLOBAL
    pass only — see rca.incidents.scan_incidents_with_method for why. Segment localization
    always uses the calibrated robust_z path regardless of `method`, because that is the only
    one vectorized to scan every segment cheaply; a non-default method costs one DB round trip
    per bucket instead of one per metric, so it is opt-in, not the default.

    Each incident is then run through the drill-down to name the responsible segment.
    """
    window_start, window_end = datetime.fromisoformat(start), datetime.fromisoformat(end)
    raw: list[incidents.Incident] = []
    scopes: dict[int, str] = {}

    if scope in ("global", "both"):
        global_result = incidents.scan_incidents_with_method(window_start, window_end, method, grain=grain)
        for inc in global_result.incidents:
            raw.append(inc); scopes[id(inc)] = "global"
    if scope in ("segment", "both"):
        for inc in incidents.scan_segments(window_start, window_end, grain=grain, min_effect=min_effect).incidents:
            raw.append(inc); scopes[id(inc)] = "segment"

    # Label echoes before drilling, so the expensive drill-down is spent on distinct findings
    # rather than on the ~120 rows that are all the same Jun 21 collapse seen per segment.
    found = incidents.classify_echoes(raw)
    by_key = {(i.metric, i.window_start.isoformat()): scopes[id(i)] for i in raw}
    for row in found:
        row["scope"] = by_key.get((row["metric"], row["window_start"]), "segment")

    primaries = [r for r in found if r["role"] == "primary"]
    for row in primaries[:_DISCOVER_LOCALIZE_TOP]:
        try:
            window = Window(start=datetime.fromisoformat(row["window_start"]),
                            end=datetime.fromisoformat(row["window_end"]))
            metric = incidents.base_metric(row["metric"])
            _, localized, _ = drilldown.drill(metric, metric, window, drilldown.baseline_window(window))
            row["localized"] = localized
        except Exception as exc:  # noqa: BLE001
            row["localized"] = {"error": str(exc)}

    # Two more folds, run AFTER localization (fold_revenue_identity needs `localized` to match
    # a global factor finding like fill_rate back to the segment it was drilled to). Neither is
    # visible to classify_echoes, which only knows "same metric, overlapping window" — these
    # catch "different metric, same underlying cause" (the revenue identity) and "different
    # metric, but this segment's whole sample got noisier because volume collapsed that day".
    incidents.fold_revenue_identity(found)
    incidents.fold_volume_driven_noise(found)
    incidents.fold_contained_same_metric(found)
    primary_count = sum(1 for r in found if r["role"] == "primary")

    return {"window": {"start": start, "end": end, "grain": grain, "scope": scope, "method": method},
            "count": len(found), "primary_count": primary_count, "incidents": found}


def run_benchmark(method: str | None = None, overrides: dict | None = None) -> list[dict]:
    """Detect (chosen method) AND localise (drill-down) each case; score both vs ground truth."""
    out = []
    for case in benchmark_cases():
        try:
            det = run_detect(case["metric"], _case_target(case["window"]).isoformat(),
                             method=method, overrides=overrides, segment_aware=True)
            window = _case_window(case["window"])
            _, localized, _ = drilldown.drill(case["metric"], case["metric"], window, drilldown.baseline_window(window))
            expected = case["expect_segment"] or {}
            out.append({
                "id": case["id"], "metric": case["metric"], "method": det["method"], "score_kind": det["score_kind"],
                "detected": det["anomaly"]["detected"], "score": round(det["anomaly"]["score"], 2),
                "expect_segment": case["expect_segment"], "localized": localized,
                "hit": localized == expected,
            })
        except Exception as exc:  # noqa: BLE001
            out.append({"id": case["id"], "metric": case["metric"], "error": str(exc)})
    return out


# ---- mega comparison: every method x every case x several sample hours -------

_MEGA_METHODS = [
    {"label": "robust_z", "method": "robust_z", "overrides": None},
    {"label": "seasonal_ml", "method": "seasonal_ml", "overrides": None},
    {"label": "iforest/univariate", "method": "isolation_forest", "overrides": {"isolation_forest": {"features": "univariate"}}},
    {"label": "iforest/multivariate", "method": "isolation_forest", "overrides": {"isolation_forest": {"features": "multivariate"}}},
]


def _sample_hours(window: Window, k: int) -> list[datetime]:
    """k hours spread evenly across [start, end) — tests each method at several points, not one."""
    total = int((window.end - window.start).total_seconds() // 3600)
    if total <= 1:
        return [window.start]
    k = min(k, total)
    step = total / k
    return [window.start + timedelta(hours=int(step * i + step / 2)) for i in range(k)]


def run_mega(hours_per_case: int = 3) -> dict:
    """Run every detector variant against every case at several hours; localise once per case.

    Detection is the variable being compared (method x hour); localisation is deterministic so it's
    computed once per case and reused. Returns per-(variant,case) rows + a per-variant summary.
    """
    cases = benchmark_cases()
    localized_by_case = {}
    for case in cases:
        window = _case_window(case["window"])
        try:
            _, localized, _ = drilldown.drill(case["metric"], case["metric"], window, drilldown.baseline_window(window))
        except Exception:  # noqa: BLE001
            localized = None
        localized_by_case[case["id"]] = localized

    rows = []
    for variant in _MEGA_METHODS:
        for case in cases:
            hours = _sample_hours(_case_window(case["window"]), hours_per_case)
            detected, scores = 0, []
            for hour in hours:
                try:
                    r = run_detect(case["metric"], hour.isoformat(), method=variant["method"],
                                   overrides=variant["overrides"], segment_aware=True)
                    detected += 1 if r["anomaly"]["detected"] else 0
                    scores.append(r["anomaly"]["score"])
                except Exception:  # noqa: BLE001, S110 -- a failed hour just doesn't count
                    pass
            localized = localized_by_case[case["id"]]
            rows.append({
                "variant": variant["label"], "method": variant["method"], "score_kind": _score_kind(variant["method"]),
                "case": case["id"], "metric": case["metric"], "detected": detected, "hours": len(hours),
                "mean_score": round(sum(scores) / len(scores), 3) if scores else None,
                "localized": localized, "hit": localized == (case["expect_segment"] or {}),
            })

    summary = []
    for variant in _MEGA_METHODS:
        vrows = [r for r in rows if r["variant"] == variant["label"]]
        det, tot = sum(r["detected"] for r in vrows), sum(r["hours"] for r in vrows)
        summary.append({
            "variant": variant["label"], "score_kind": _score_kind(variant["method"]),
            "detection_rate": round(det / tot, 3) if tot else 0.0,
            "cases_fired": sum(1 for r in vrows if r["detected"] > 0), "cases": len(vrows),
            "localized_correct": sum(1 for r in vrows if r["hit"]),
        })
    return {"hours_per_case": hours_per_case, "rows": rows, "summary": summary}


def start_mega_job(hours_per_case: int = 3) -> dict:
    job_id = uuid4().hex[:8]
    _JOBS[job_id] = {"status": "running", "log": "", "finished": False, "result": None}
    threading.Thread(target=_run_mega_job, args=(job_id, hours_per_case), daemon=True).start()
    return {"job_id": job_id}


def _run_mega_job(job_id: str, hours_per_case: int) -> None:
    try:
        result = run_mega(hours_per_case)
        _JOBS[job_id].update(status="done", finished=True, result=result, log=f"{len(result['rows'])} rows")
    except Exception as exc:  # noqa: BLE001
        _JOBS[job_id].update(status="error", finished=True, log=str(exc))


# ---- full engine: build_bundle per case (the real end-to-end EvidenceBundle) ----

def run_engine_benchmark() -> list[dict]:
    """Run the WHOLE engine (build_bundle) per ground-truth case and summarize each bundle.

    Method-independent (build_bundle uses the incident scanner + deterministic decompose/drill), so
    it's one bundle per case — the end-to-end artifact, not just detect/drill."""
    out = []
    for case in benchmark_cases():
        window = _case_window(case["window"])
        row = {"id": case["id"], "metric": case["metric"],
               "start": window.start.isoformat(), "end": window.end.isoformat()}  # for click-to-view
        try:
            b = build_bundle(case["metric"], window)
            row.update({
                "detected": b.anomaly.detected, "score": round(b.anomaly.score, 2),
                "primary_factor": b.factor_decomposition.primary_factor,
                "localized": b.localized_segment, "hit": b.localized_segment == (case["expect_segment"] or {}),
                "ruled_out": [r.hypothesis for r in b.ruled_out], "n_queries": len(b.queries),
            })
        except Exception as exc:  # noqa: BLE001
            row["error"] = str(exc)
        out.append(row)
    return out


def full_bundle(metric: str, start: str, end: str) -> dict:
    """Build one bundle and return it as schema-shaped JSON (for the click-to-view drawer)."""
    window = Window(start=datetime.fromisoformat(start), end=datetime.fromisoformat(end))
    return build_bundle(metric, window).model_dump(mode="json", by_alias=True, exclude_none=True)


def start_engine_job() -> dict:
    job_id = uuid4().hex[:8]
    _JOBS[job_id] = {"status": "running", "log": "", "finished": False, "result": None}
    threading.Thread(target=_run_engine_job, args=(job_id,), daemon=True).start()
    return {"job_id": job_id}


def _run_engine_job(job_id: str) -> None:
    try:
        rows = run_engine_benchmark()
        _JOBS[job_id].update(status="done", finished=True, result={"rows": rows}, log=f"{len(rows)} bundles")
    except Exception as exc:  # noqa: BLE001
        _JOBS[job_id].update(status="error", finished=True, log=str(exc))


def _bundle_exists(metric: str, window: Window) -> bool:
    """A `bundles` row already covering this exact metric+window — regardless of is_anomaly, so
    a previously-seeded 'checked, normal' row also counts as already done, not just a hit."""
    rows = get_client().query(
        "SELECT 1 FROM bundles FINAL WHERE metric = {m:String} "
        "AND window_start = {s:DateTime} AND window_end = {e:DateTime} LIMIT 1",
        parameters={"m": metric, "s": window.start, "e": window.end},
    ).result_rows
    return bool(rows)


def seed_bundles(start: str, end: str, method: str = "isolation_forest") -> dict:
    """Run discover, then a FULL investigation (decompose + drill + narrate + persist) for each
    primary incident — one Evidence Bundle per real anomaly, stored in `bundles` for the
    dashboard's anomaly switcher. Echo/secondary rows are skipped: they are the same underlying
    incident seen from another angle, and each would otherwise burn a full pipeline run.

    Idempotent: a (metric, exact window) pair already present in `bundles` is skipped rather than
    re-investigated — re-running this over the same range doesn't create duplicate rows with
    fresh ids for events already seeded, it only fills in genuinely new findings."""
    from api import pipeline as pipe

    try:
        found = discover(start, end, method=method)
    except Exception as exc:  # noqa: BLE001 — a failed sweep must surface, not vanish as a bare job error
        return {"seeded": 0, "errors": 1, "already_present": 0, "echoes_skipped": 0,
                "bundles": [{"error": f"sweep failed before any incident could be investigated: {exc}"}]}

    seeded, skipped, already_present = [], 0, 0
    for row in found["incidents"]:
        if row["role"] != "primary":
            skipped += 1
            continue
        metric = incidents.base_metric(row["metric"])
        window = Window(start=datetime.fromisoformat(row["window_start"]),
                        end=datetime.fromisoformat(row["window_end"]))
        if _bundle_exists(metric, window):
            already_present += 1
            seeded.append({"metric": metric, "window": row["window_start"],
                           "scope": row.get("scope"), "skipped": "already in bundles"})
            continue
        try:
            b = pipe.run_investigation(metric, window, persist=True)
            # Segment-scoped incidents were detected by the SEGMENT sweep; the bundle's global
            # window-grain re-score is diluted by construction (the APAC/iOS 18.1 drop is -51%
            # in-segment but ~-1% globally), so a weak/undetected global re-score alone must not
            # be trusted to overrule the sweep. But the sweep's own flag isn't enough evidence
            # either — measured live: 3 of an earlier 8 seeded "anomalies" (two render_rate moves
            # with z≈0, one ecpm move below the calibrated threshold) got promoted this way with
            # NOTHING for drill() to find, because they were never real. The corroborating
            # evidence that's actually trustworthy is drill() independently finding a genuine
            # concentrated culprit (b.localized_segment non-empty) — every real segment-diluted
            # case checked (fill_rate/Android 15, fill_rate/APAC+iOS 18.1, ecpm/finance) clears
            # this with contribution/lift far past threshold; none of the 3 false positives could
            # have, since a globally-flat move has no segment with disproportionate lift.
            if row.get("scope") == "segment" and not b.anomaly.detected and b.localized_segment:
                b.anomaly.detected = True
                from data import store as _store
                _store.save_bundle(b, *_store.load_meta(b.investigation_id))
            pipe.narrate_investigation(b.investigation_id, persist=True)
            seeded.append({"investigation_id": b.investigation_id, "metric": metric,
                           "window": row["window_start"], "scope": row.get("scope"),
                           "localized": b.localized_segment, "detected": b.anomaly.detected})
        except Exception as exc:  # noqa: BLE001 — one bad incident must not sink the batch
            seeded.append({"metric": metric, "window": row["window_start"], "error": str(exc)})
    return {"seeded": len([s for s in seeded if "error" not in s and "skipped" not in s]),
            "errors": len([s for s in seeded if "error" in s]),
            "already_present": already_present, "echoes_skipped": skipped, "bundles": seeded}


def start_seed_job(start: str, end: str, method: str = "isolation_forest") -> dict:
    """8+ full investigations (each: detect + decompose + drill + LLM narrate) takes minutes —
    background job like /discover; poll /dev/jobs/{id}."""
    job_id = uuid4().hex[:8]
    _JOBS[job_id] = {"status": "running", "log": "", "finished": False, "result": None}

    def _run() -> None:
        try:
            result = seed_bundles(start, end, method)
            _JOBS[job_id].update(status="done", finished=True, result=result,
                                 log=f"{result['seeded']} bundles seeded, {result['errors']} errors")
        except Exception as exc:  # noqa: BLE001
            _JOBS[job_id].update(status="error", finished=True, log=str(exc))

    threading.Thread(target=_run, daemon=True).start()
    return {"job_id": job_id}


def seed_context(days_before: int = 3, days_after: int = 3) -> dict:
    """Day-grain runs for the days around each ANOMALY already in `bundles`, so "what was normal
    that week" has real stored numbers to answer from instead of just the one anomalous window.
    No narrate here (context rows aren't shown as prose) — but decompose/drill DO run, via
    pipeline.run_investigation, because that scores the whole day as ONE point against its
    same-weekday baseline (rca.bundle._window_anomaly). detect_in_window (used by the chat path,
    pipeline.run_detection) instead scans all 24 hours and reports the worst one — appropriate
    for finding a real incident, but run across every context day it performs 24 hypothesis
    tests per day and floods the result with false positives (measured: nearly every day fired).
    A single whole-day test doesn't have that problem.

    Idempotent: a (metric, day) pair already present in `bundles` is skipped, so calling this
    again after seeding more anomalies only fills in the new gaps.
    """
    from api import pipeline as pipe

    anomalies = get_client().query(
        "SELECT DISTINCT metric, toDate(window_start) AS day FROM bundles FINAL WHERE is_anomaly = 1"
    ).result_rows
    existing = {
        (r[0], r[1]) for r in get_client().query(
            "SELECT DISTINCT metric, toDate(window_start) AS day FROM bundles FINAL"
        ).result_rows
    }

    targets: set[tuple[str, object]] = set()
    for metric, day in anomalies:
        for offset in range(-days_before, days_after + 1):
            if offset == 0:
                continue
            target_day = day + timedelta(days=offset)
            if (metric, target_day) not in existing:
                targets.add((metric, target_day))

    seeded, errors = [], []
    for metric, day in sorted(targets, key=lambda t: (t[0], t[1])):
        window = Window(start=datetime.combine(day, datetime.min.time()),
                        end=datetime.combine(day, datetime.min.time()) + timedelta(days=1))
        try:
            b = pipe.run_investigation(metric, window, persist=True)
            seeded.append({"metric": metric, "day": day.isoformat(), "is_anomaly": b.anomaly.detected})
        except Exception as exc:  # noqa: BLE001 — one bad day must not sink the batch
            errors.append({"metric": metric, "day": day.isoformat(), "error": str(exc)})

    return {"seeded": len(seeded), "errors": len(errors), "already_present": len(existing),
            "rows": seeded, "error_rows": errors}


def start_seed_context_job(days_before: int = 3, days_after: int = 3) -> dict:
    """One detection call per (metric, day) target — can be dozens of ClickHouse round trips,
    so background job like /seed_bundles; poll /dev/jobs/{id}."""
    job_id = uuid4().hex[:8]
    _JOBS[job_id] = {"status": "running", "log": "", "finished": False, "result": None}

    def _run() -> None:
        try:
            result = seed_context(days_before, days_after)
            _JOBS[job_id].update(status="done", finished=True, result=result,
                                 log=f"{result['seeded']} context rows seeded, {result['errors']} errors")
        except Exception as exc:  # noqa: BLE001
            _JOBS[job_id].update(status="error", finished=True, log=str(exc))

    threading.Thread(target=_run, daemon=True).start()
    return {"job_id": job_id}


def start_discover_job(start: str, end: str, grain: str, scope: str, min_effect: float,
                       method: str = "isolation_forest") -> dict:
    """A full segment sweep is ~50 queries (a metric x dimension pass each), so run it in the
    background like /mega rather than holding the request open."""
    job_id = uuid4().hex[:8]
    _JOBS[job_id] = {"status": "running", "log": "", "finished": False, "result": None}
    threading.Thread(target=_run_discover_job, args=(job_id, start, end, grain, scope, min_effect, method), daemon=True).start()
    return {"job_id": job_id}


def _run_discover_job(job_id: str, start: str, end: str, grain: str, scope: str, min_effect: float,
                      method: str = "isolation_forest") -> None:
    try:
        result = discover(start, end, grain, scope, min_effect, method)
        _JOBS[job_id].update(status="done", finished=True, result=result,
                             log=f"{result['count']} incidents in {start}..{end} ({method})")
    except Exception as exc:  # noqa: BLE001
        _JOBS[job_id].update(status="error", finished=True, log=str(exc))


# ---- router (thin wrapper; ValueError -> 400) ------------------------------

router = APIRouter(prefix="/dev", tags=["dev"])


def _guard(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


class DropReq(BaseModel):
    confirm: str


class LoadReq(BaseModel):
    confirm: str


class DetectReq(BaseModel):
    metric: str = "revenue"
    at: str = "2026-07-04T10:00"
    method: str | None = None
    overrides: dict | None = None


class CompareReq(BaseModel):
    metric: str = "revenue"
    at: str = "2026-07-04T10:00"


class BenchmarkReq(BaseModel):
    method: str | None = None
    overrides: dict | None = None


class LocalizeReq(BaseModel):
    metric: str = "fill_rate"
    start: str = "2026-06-23"
    end: str = "2026-06-26"


@router.get("", response_class=HTMLResponse)
def dashboard() -> str:
    return _HTML.read_text(encoding="utf-8")


@router.get("/tables")
def tables() -> dict:
    return {"tables": list_tables()}


@router.get("/table/{name}")
def table_preview(name: str, limit: int = 20) -> dict:
    return _guard(preview_table, name, limit)


@router.post("/table/{name}/drop")
def table_drop(name: str, req: DropReq) -> dict:
    return _guard(drop_table, name, req.confirm)


@router.post("/load")
def load(req: LoadReq) -> dict:
    return _guard(start_load_job, req.confirm)


@router.get("/jobs/{job_id}")
def job(job_id: str) -> dict:
    return _guard(job_status, job_id)


@router.get("/runs")
def runs(limit: int = 50) -> dict:
    return {"runs": store.list_investigations(limit)}


@router.get("/runs/{investigation_id}")
def run_detail(investigation_id: str) -> dict:
    bundle = store.load_bundle(investigation_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail=f"no investigation {investigation_id!r}")
    return bundle.model_dump(mode="json")


@router.post("/detect")
def detect_endpoint(req: DetectReq) -> dict:
    return _guard(run_detect, req.metric, req.at, req.method, req.overrides)


@router.post("/compare")
def compare_endpoint(req: CompareReq) -> dict:
    return {"results": _guard(run_compare, req.metric, req.at)}


@router.get("/benchmark/cases")
def benchmark_cases_endpoint() -> dict:
    return {"cases": benchmark_cases()}


@router.post("/benchmark/run")
def benchmark_run_endpoint(req: BenchmarkReq) -> dict:
    return {"results": run_benchmark(req.method, req.overrides)}


@router.post("/localize")
def localize_endpoint(req: LocalizeReq) -> dict:
    return _guard(localize, req.metric, req.start, req.end)


class DiscoverReq(BaseModel):
    """Time window + detector choice. Grain, scope, and sensitivity are still decided
    server-side (discover() defaults) — nobody should have to hand-tune a detection dial to
    get an answer. `method` is the one model-comparison knob worth exposing: it picks which
    detector scores the GLOBAL pass (robust_z / seasonal_ml / isolation_forest). Segment
    localization is unaffected — see discover()'s docstring for why."""
    start: str = "2026-06-01"
    end: str = "2026-07-06"
    method: str = "isolation_forest"


@router.post("/seed_bundles")
def seed_bundles_endpoint(req: DiscoverReq) -> dict:
    # Same request shape as /discover; runs the full pipeline per primary incident and
    # persists one Evidence Bundle each. Background job; poll /dev/jobs/{id}.
    return start_seed_job(req.start, req.end, method=req.method)


class SeedContextReq(BaseModel):
    days_before: int = 3
    days_after: int = 3


@router.post("/seed_context")
def seed_context_endpoint(req: SeedContextReq) -> dict:
    # Detection-only day-grain runs around each anomaly already in `bundles` — the baseline
    # data chat's "what was normal that day" answers from. Background job; poll /dev/jobs/{id}.
    return start_seed_context_job(req.days_before, req.days_after)


@router.post("/discover")
def discover_endpoint(req: DiscoverReq) -> dict:
    # grain='day' + scope='both' are the right defaults for "just find anomalies" — day grain
    # matches how every known incident was actually confirmed, and 'both' is what catches a
    # localised anomaly a global-only sweep would miss. background job; poll /dev/jobs/{id}.
    return start_discover_job(req.start, req.end, grain="day", scope="both", min_effect=0.0, method=req.method)


class MegaReq(BaseModel):
    hours_per_case: int = 3


@router.post("/mega")
def mega_endpoint(req: MegaReq) -> dict:
    return start_mega_job(req.hours_per_case)  # background job; poll /dev/jobs/{id} for result


@router.post("/engine")
def engine_endpoint() -> dict:
    return start_engine_job()  # background job; poll /dev/jobs/{id} for result


class BundleReq(BaseModel):
    metric: str = "revenue"
    start: str = "2026-06-21"
    end: str = "2026-06-22"


@router.post("/bundle")
def bundle_endpoint(req: BundleReq) -> dict:
    return _guard(full_bundle, req.metric, req.start, req.end)
