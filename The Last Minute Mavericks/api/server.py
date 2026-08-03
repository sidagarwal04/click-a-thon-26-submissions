#!/usr/bin/env python3
"""RCA Engine API — serves the REAL engine output (live ClickHouse) so the frontend can wire to it
instead of fixtures. CORS-open for local dev. The scan is computed once and cached (data is static);
POST /refresh recomputes.

  uvicorn api.server:app --host 0.0.0.0 --port 8000     (then open /docs)
"""
import os, sys, threading, time
from typing import Optional
from datetime import datetime, timezone
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "tests", "e2e"))
from integrations import otel as _otel
import run_incident as ri
import run_incident_v2 as riv2
import adjudicate as adj
from agent.narrate import narrate
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="RCA Engine API", description="Live root-cause investigations from ClickHouse", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_cache: dict = {}

# Background-recompute state. A scan is ~25 s, so POST /refresh must not run it inline.
# ponytail: one in-flight recompute per db, no queue — a second request while one is
# running is answered "already_running" rather than stacking another 200-query scan.
_recompute: dict = {}
_recompute_lock = threading.Lock()


def _stamp(bundle: dict, db: str) -> dict:
    """Record WHEN this bundle was computed, so the UI can show data age instead of
    implying every render is live."""
    try:
        bundle.setdefault("scan_summary", {})["computed_at"] = \
            datetime.now(timezone.utc).isoformat(timespec="seconds")
    except Exception:  # noqa: BLE001 — a stamp must never break a served bundle
        pass
    return bundle


def _recompute_status(db: str) -> dict:
    st = _recompute.get(db, {})
    return {"recomputing": bool(st.get("running")),
            "started_at": st.get("started_at"),
            "finished_at": st.get("finished_at"),
            "error": st.get("error"),
            "computed_at": (_cache.get(db, {}).get("scan_summary", {}) or {}).get("computed_at")}


def _recompute_into_cache(db: str) -> None:
    """Run the scan off-thread and swap the cache in ONE assignment when it succeeds.
    A failed recompute must leave the previous good bundle serving."""
    err = None
    try:
        fresh = _stamp(compute(db, rebuild=True), db)   # refresh == re-read raw data, cube included
        _cache[db] = fresh          # atomic swap; readers never see a half-built bundle
    except Exception as e:  # noqa: BLE001 — keep serving the last good scan
        err = str(e)
        print("background refresh failed (serving previous scan):", e)
    with _recompute_lock:
        _recompute[db] = {"running": False, "error": err,
                          "started_at": _recompute.get(db, {}).get("started_at"),
                          "finished_at": datetime.now(timezone.utc).isoformat()}

def compute(db: Optional[str] = None, do_narrate: bool = True, rebuild: bool = False) -> dict:
    db = db or ri.default_db()
    # One ClickStack span per stage, so "how long does an investigation take, and where does
    # the time go" is a SQL question against otel_traces instead of a claim in a slide.
    t0 = time.perf_counter()
    with _otel.span("rca.scan", **{"rca.database": db}):
        with _otel.span("rca.connect"):
            # rebuild=True ONLY on an explicit refresh. The cube is a snapshot: without this,
            # a refresh re-scans stale pre-aggregates and serves confidently wrong numbers
            # after new data lands. Normal page loads skip the rebuild and stay fast.
            cfg = ri.env(); cx = ri.connect(cfg); ri.ensure_cube(cx, db, rebuild=rebuild)
        # The root engine is the default: it is what test-sql/ grades, what the CLI runs, and the
        # only one with contamination exclusion (a prior -40% window poisoning the next baseline).
        # We serve what we test — the two used to differ, so every blind-fixture score described
        # code the demo never executed. Measured before switching: identical incidents on all 6
        # e2e slices, both test-sql slices, and the real rca data (same 6, magnitudes within 1.5pp).
        # v1 already runs recall-mode floors (fill_rate/ecpm 0.05) and now carries snr, so the
        # adjudicator keeps both of its noise-aware rules. RCOS_ENGINE=v2-recall restores the fork.
        engine = "v2-recall" if os.environ.get("RCOS_ENGINE", "root") == "v2-recall" else "root"
        with _otel.span("rca.detect", **{"rca.engine": engine}):
            if engine == "v2-recall":
                riv2.MINRELS["fill_rate"] = riv2.MINRELS["ecpm"] = 0.05
                inc, fp = riv2.scan(cx, db)
            else:
                inc, fp = ri.scan(cx, db)
        with _otel.span("rca.decompose"):
            # measured, not 0.0: this is the number the demo claims ("found in seconds")
            bundle = ri.build_bundle(cx, db, inc, fp, time.perf_counter() - t0)
            # snr passthrough — build_bundle keeps only dimension/segment/deviation_pct, and the
            # adjudicator needs the noise ratio to rule the 5-10% band. Both engines emit it now.
            by_win = {(i["metric"], tuple(i["win"])): (i.get("culprit") or {}).get("snr") for i in inc}
            for i in bundle["investigations"]:
                snr = by_win.get((i["metric"], tuple(i["window"])))
                if snr and i.get("culprit"): i["culprit"]["snr"] = snr
        # LLM adjudication -> trays (reported / needs_review / suppressed). Failure-safe by
        # construction: no backend (e.g. the deployed VM has no Ollama) => deterministic
        # fallback inside apply(); an exception here leaves the bundle un-adjudicated.
        if os.environ.get("RCOS_ADJUDICATE", "on") != "off":
            with _otel.span("rca.adjudicate"):
                try:
                    verdicts, source, latency = adj.adjudicate(bundle)
                    bundle = adj.apply(bundle, verdicts, source, latency)
                except Exception as e:
                    print("adjudication failed (serving un-adjudicated):", e)
        if do_narrate:
            with _otel.span("rca.narrate", **{"rca.investigations": len(bundle["investigations"])}):
                for i in bundle["investigations"]:
                    i["diagnosis"] = narrate(i, cfg)
    # Publish a public Langfuse trace (after narration, so the diagnosis is in it) and stamp its
    # URL on every investigation — the PS is "no trace, no credit", so an API-backed card must
    # carry a trace link. One trace per scan; each incident is a span the judge can open.
    try:
        with _otel.span("rca.publish_trace"):
            url = ri.log_bundle(bundle, db, cfg)
        if url:
            bundle["scan_summary"]["trace_url"] = url
            for i in bundle["investigations"]:
                i.setdefault("trace_url", url)
    except Exception as e:  # tracing must never take the API down
        print("trace logging failed:", e)
    return bundle

@app.on_event("startup")
def _warm():
    db = ri.default_db()
    try: _cache[db] = _stamp(compute(db), db)
    except Exception as e: print("startup scan failed:", e)

@app.get("/health")
def health():
    db = ri.default_db()
    b = _cache.get(db, {})
    return {"status": "ok", "db": db, "investigations": len(b.get("investigations", []))}

@app.get("/scan", summary="The full investigation bundle {scan_summary, investigations:[...]}")
def scan(db: Optional[str] = Query(None)):
    db = db or ri.default_db()
    if db not in _cache:
        _cache[db] = _stamp(compute(db), db)
    return _cache[db]

@app.get("/investigations", summary="Just the list of incidents (what the UI incidents() renders)")
def investigations(db: Optional[str] = Query(None)):
    db = db or ri.default_db()
    if db not in _cache:
        _cache[db] = _stamp(compute(db), db)
    return _cache[db]["investigations"]

@app.get("/investigation/{inv_id}", summary="One incident by id")
def investigation(inv_id: str, db: Optional[str] = Query(None)):
    db = db or ri.default_db()
    if db not in _cache:
        _cache[db] = _stamp(compute(db), db)
    for n, i in enumerate(_cache[db]["investigations"], 1):
        # accept the raw engine `id`, the short `INC-n`, `incident_id`, or
        # `engine_id` — the dashboard dock sends whichever id the Incidents tab
        # assigned, so match against all of them (ENG chat incident-resolution).
        if (inv_id.upper() == f"INC-{n}"
                or inv_id in (i.get("id"), i.get("incident_id"), i.get("engine_id"))):
            return i
    return {"error": "not found", "id": inv_id}

@app.post("/refresh", summary="Kick a recompute from ClickHouse (returns immediately)")
def refresh(db: Optional[str] = Query(None), wait: bool = Query(False)):
    """NON-BLOCKING by default.

    A scan is ~200 ClickHouse round-trips and takes ~25 s. This used to run inline, so the
    dashboard's Refresh button blocked for its whole 8 s client timeout, swallowed the
    timeout, and then re-read a cache the recompute had not replaced yet — a long freeze
    that returned the SAME data. Now the recompute runs in the background and the caller
    returns in milliseconds; GET /scan keeps serving the last good bundle until the new
    one is ready, so the dashboard is never blank.

    Pass ?wait=1 for the old synchronous behaviour (scripts, tests).
    """
    db = db or ri.default_db()
    if wait:
        _cache[db] = _stamp(compute(db, rebuild=True), db)
        return {"status": "done", "db": db, **_recompute_status(db)}
    with _recompute_lock:
        if _recompute.get(db, {}).get("running"):
            return {"status": "already_running", "db": db, **_recompute_status(db)}
        _recompute[db] = {"running": True, "error": None,
                          "started_at": datetime.now(timezone.utc).isoformat()}
    threading.Thread(target=_recompute_into_cache, args=(db,), daemon=True).start()
    return {"status": "started", "db": db, **_recompute_status(db)}


@app.get("/refresh_status", summary="Is a background recompute in flight, and how old is the data?")
def refresh_status(db: Optional[str] = Query(None)):
    db = db or ri.default_db()
    return {"db": db, **_recompute_status(db)}
