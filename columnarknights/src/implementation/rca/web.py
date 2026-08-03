"""Dashboard + incident-report web app.

Serves live ClickHouse-backed timeseries/detection data and the saved
investigation results (out/*.json) as JSON, plus the static dashboard/
incident-detail pages. Every number shown is either a live query result or a
result already produced (and traced) by the CLI pipeline — nothing here
invents data.
"""

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import attribution, baseline, latency, live_monitor, pipeline
from .config import settings
from .db import get_client
from .metrics import DIMENSIONS, METRICS

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"
TRACE_DIR = ROOT / "traces"
WEBAPP_DIR = Path(__file__).resolve().parent / "webapp"


@asynccontextmanager
async def _lifespan(app: FastAPI):
    live_monitor.monitor.start()
    try:
        yield
    finally:
        live_monitor.monitor.stop()


app = FastAPI(title="InMobi RCA Dashboard", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


@app.get("/api/live/events")
async def live_events(request: Request):
    """SSE stream of the live monitor's state -- ingest/idle/pipeline_start/
    pipeline_complete events, see live_monitor.py. One queue per connected
    tab; the monitor itself is a single shared background task regardless
    of how many tabs are open."""

    async def _generator():
        q = live_monitor.monitor.subscribe()
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            live_monitor.monitor.unsubscribe(q)

    return StreamingResponse(_generator(), media_type="text/event-stream")


@app.get("/api/meta")
def meta():
    client = get_client()
    row = client.query("SELECT min(event_date), max(event_date), count() FROM fact_events").result_rows[0]
    return {
        "min_date": str(row[0]),
        "max_date": str(row[1]),
        "row_count": int(row[2]),
        "metrics": list(METRICS.keys()),
        "dimensions": DIMENSIONS,
        "librechat_base_url": settings.librechat_base_url,
        "librechat_followup_agent_id": settings.librechat_followup_agent_id,
    }


@app.get("/api/timeseries")
def timeseries(metric: str, start: str, end: str, lookback_weeks: int = 4):
    if metric not in METRICS:
        raise HTTPException(400, f"Unknown metric: {metric}")
    client = get_client()
    start_d, end_d = pipeline.parse_date(start), pipeline.parse_date(end)
    from datetime import timedelta

    series = baseline.daily_series(client, metric, start_d - timedelta(weeks=lookback_weeks), end_d)
    evaluations = baseline.evaluate_series(series, metric, lookback_weeks=lookback_weeks)
    eval_by_date = {e.event_date: e for e in evaluations}
    points = [
        {
            "date": str(p.event_date),
            "value": p.value,
            "is_anomaly": eval_by_date[p.event_date].is_anomaly,
            "baseline_expected": eval_by_date[p.event_date].baseline_expected,
            "rel_delta": eval_by_date[p.event_date].rel_delta,
        }
        for p in series
        if p.event_date >= start_d
    ]
    return {"metric": metric, "points": points}


@app.get("/api/scan")
def scan(start: str, end: str, metrics: str | None = None, lookback_weeks: int = 4):
    metric_list = metrics.split(",") if metrics else None
    start_d, end_d = pipeline.parse_date(start), pipeline.parse_date(end)
    results = pipeline.scan(start_d, end_d, metric_list, lookback_weeks)
    out = []
    for entry in results:
        for inc in entry["incidents"]:
            peak = inc.peak
            out.append(
                {
                    "metric": entry["metric"],
                    "start": str(inc.start),
                    "end": str(inc.end),
                    "peak_date": str(peak.event_date),
                    "rel_delta": peak.rel_delta,
                    "robust_z": peak.robust_z,
                    "direction": peak.direction,
                }
            )
    return {"incidents": out}


@app.post("/api/investigate")
def investigate(metric: str, start: str, end: str, max_depth: int = 2, branch_factor: int = 2):
    if metric not in METRICS:
        raise HTTPException(400, f"Unknown metric: {metric}")
    result = pipeline.investigate(
        metric, pipeline.parse_date(start), pipeline.parse_date(end), max_depth=max_depth, branch_factor=branch_factor
    )
    json_path = pipeline.save_investigation_files(result, OUT_DIR)
    result["id"] = json_path.name
    return result


# Severity/confidence aren't pipeline outputs -- the pipeline computes
# explanatory_power/lift per segment, not a single per-incident verdict. These
# are a presentation-layer judgment call on top of those real numbers, made
# ONCE here so every page (list, detail) reads the same value instead of each
# frontend file re-deriving its own copy with its own thresholds.
_SEVERITY_HIGH = 0.15
_SEVERITY_MEDIUM = 0.05


def _severity_for(metric_rel_delta: float | None) -> str:
    if metric_rel_delta is None:
        return "medium"
    abs_delta = abs(metric_rel_delta)
    if abs_delta >= _SEVERITY_HIGH:
        return "high"
    if abs_delta >= _SEVERITY_MEDIUM:
        return "medium"
    return "low"


def _confidence_for(root_primaries: list[dict]) -> int | None:
    """None (not 0) for a broad-based incident -- there's no cause to be
    confident about, which is a different thing from being confident it's 0%.

    Uses the ROOT level's primaries, not any deeper level's. explanatory_power
    at depth > 0 is computed against the movement *within the parent segment's
    filter* (attribution.rank_segments sums totals only from the filtered
    `rows`), not against the original total -- so a deeper segment's EP isn't
    comparable to a root-level EP from a different (shallower) incident. The
    root level has no filter, so it's always a fraction of the true total
    movement, and is the only one that's consistent across incidents regardless
    of how deep any given drill-down happened to go.

    When more than one root-level dimension independently clears the
    localization bar (branch_factor > 1), this takes the STRONGEST one's EP,
    not the sum. The two branches' EPs come from different dimensions' own
    partitions of the same movement (e.g. ad_format's segments sum to ~100%
    of the total on their own; country's segments separately also sum to
    ~100%), so they're two overlapping lenses on the same movement, not
    disjoint slices of one pie -- adding them would double-count whatever
    share of requests both segments have in common. Reporting the strongest
    branch's EP is the same number this function has always reported for a
    single-cause incident; it just doesn't overstate confidence when a
    second, weaker cause is also being shown.
    """
    if not root_primaries:
        return None
    # root_primaries is already sorted strongest-lift-first (attribution.
    # drill_down sorts `qualifying` by |lift| before truncating to
    # branch_factor), so [0] is "the strongest branch" for both the
    # single-primary case (where it's the only element -- byte-identical to
    # the pre-branching formula) and the multi-primary case.
    #
    # Raw explanatory_power can fall outside [0, 1] -- when some segments move
    # opposite the overall trend, the ones moving with it can legitimately
    # explain >100% of the net movement on their own (they're offset by the
    # others). That's correct Adtributor math, but confusing as a displayed
    # percentage, so it's clamped to a sane 0-100 range here.
    pct = round(root_primaries[0]["explanatory_power"] * 100)
    return max(0, min(100, pct))


def _derive_fields(data: dict) -> dict:
    """Everything the frontend needs that isn't already a direct pipeline
    field, computed once here instead of duplicated across app.js/incident.js."""
    metric = data.get("metric")
    decomp = data.get("decomposition") or {}
    baseline_factors = decomp.get("baseline_factors") or {}
    current_factors = decomp.get("current_factors") or {}
    drill_down = data.get("drill_down") or {}

    metric_rel_delta = attribution.metric_rel_delta(metric, decomp)
    # segment_chains: every independent root-to-leaf localization path the
    # drill-down found (usually one; more than one when branch_factor > 1
    # and multiple dimensions independently cleared the bar). Shared with
    # narrate.py so the LLM/fallback narrative and this API agree on what
    # "the causes" of the incident are.
    chains = attribution.segment_chains(drill_down)
    return {
        "metric_rel_delta": metric_rel_delta,
        "metric_baseline": baseline_factors.get(metric),
        "metric_current": current_factors.get(metric),
        "segment_chains": chains,
        "severity": _severity_for(metric_rel_delta),
        "confidence": _confidence_for(drill_down.get("primary_segments") or []),
    }


def _summarize_incident_file(path: Path) -> dict:
    with open(path) as f:
        data = json.load(f)
    decomp = data.get("decomposition") or {}
    return {
        "id": path.name,
        "metric": data.get("metric"),
        "current_window": data.get("current_window"),
        "baseline_window": data.get("baseline_window"),
        "revenue_rel_delta": decomp.get("revenue_rel_delta"),
        "revenue_delta": decomp.get("revenue_delta"),
        "narrative": data.get("narrative"),
        "langfuse_trace_url": data.get("langfuse_trace_url"),
        **_derive_fields(data),
    }


@app.get("/api/incidents")
def list_incidents():
    if not OUT_DIR.exists():
        return {"incidents": []}
    files = sorted(OUT_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return {"incidents": [_summarize_incident_file(p) for p in files]}


@app.get("/api/incidents/{incident_id}")
def get_incident(incident_id: str):
    path = OUT_DIR / incident_id
    if not path.exists() or path.parent != OUT_DIR:
        raise HTTPException(404, "Not found")
    with open(path) as f:
        data = json.load(f)
    data.update(_derive_fields(data))
    return data


@app.get("/api/latency")
def latency_report():
    """p50/p90/p95/p99 for the investigate/scan pipeline, computed from the
    Tracer spans already written for every real run (traces/*.json) —
    measured from actual runs, not a synthetic benchmark."""
    return latency.compute_report(TRACE_DIR)


app.mount("/", StaticFiles(directory=str(WEBAPP_DIR), html=True), name="webapp")
