"""Stateless FastAPI service, per Docs/Mindmap/PRODUCTION_PLAN.md Phase 3.
Pure JSON API -- the UI lives in ui/ (a separate React app) and talks to
this over HTTP, per the user's explicit "full UI module, API connected"
request. Genuinely stateless: no in-process background task lives here.

The real-time monitor is deliberately a SEPARATE process (the `scanner`
docker-compose service, `python -m engine.scanner --interval`) rather than a
FastAPI lifespan task -- this API runs multi-worker (see Dockerfile's
`--workers 2`), and each uvicorn worker is its own process with its own
lifespan. An in-process background task here would run once *per worker*,
producing duplicate scan ticks (found via a live test: the event feed showed
every tick twice with 2 workers). Keeping the scanner as its own
single-instance service is what lets the API tier scale to N replicas
without duplicating anything -- see CLAUDE.md's Production & scalability
principles.
"""

import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine import datasets, monitor_store, ops_view, store, tracing
from engine.causal_chain import build_chain
from engine.chat import ask as chat_ask
from engine.config import METRIC_DEFS, REVENUE_DECOMPOSITION_FACTORS, settings
from engine.grains import DRIFT_GRAIN, GRAIN_REGISTRY, monitored_grains, monitored_metrics
from engine.pipeline import run_investigation
from engine.provenance import provenance_payload, verify_fact
from engine.scanner import WATCHLIST, check_new_data
from engine.scopes import SCOPE_REGISTRY, monitored_scopes
from engine.sweep import data_floor as sweep_data_floor

_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
# Repo root, for reading generated artefacts such as the backtest scorecard. Resolved
# from this file rather than the process cwd, which differs between `uvicorn` locally
# and the container's WORKDIR.
_REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Shutdown-only: flush buffered Langfuse spans so nothing is lost when
    the container stops. Deliberately does NOT start any background task --
    the scanner is its own compose service precisely because a lifespan task
    runs once per uvicorn worker and duplicated every scan tick (see the
    module docstring above)."""
    yield
    tracing.flush()


app = FastAPI(title="Automated Root-Cause Analyst", version="0.2.0", lifespan=lifespan)

# The UI is a separate service (ui/, its own origin in dev at :5173, proxied
# same-origin via nginx in the docker-compose prod setup) -- CORS is wide
# open here because this is synthetic hackathon data with no auth, not
# because it's a pattern to reuse for anything handling real user data.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def select_dataset(request: Request, call_next):
    """Binds the whole request to the dataset named by `?dataset=`.

    ONE middleware instead of a parameter on fourteen routes. It works because
    every query in engine/ is unqualified, so the dataset is a property of the
    CONNECTION rather than of any query -- engine/ch_client.py asks
    datasets.current_database() when it opens one, and nothing in between needs to
    know a dataset exists. No route signature changes, so no existing caller breaks.

    Setting a ContextVar here does reach the route: sync `def` routes run via
    anyio.to_thread.run_sync, which copies the caller's context into the worker
    thread, and fan-out threads below that are covered by tracing.in_parent_context.

    An unrecognised key is a 400, never a silent fallback. Quietly serving the
    primary dataset under another dataset's name is the precise failure this
    codebase calls fails-silent-wrong: every number would be real, correctly
    computed, and about the wrong world.
    """
    key = request.query_params.get("dataset")
    try:
        datasets.resolve(key)
    except datasets.UnknownDataset as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})
    token = datasets.set_current(key)
    try:
        response = await call_next(request)
    finally:
        # Reset even on failure: this worker task is reused, and a leaked selection
        # would silently apply to whatever request lands on it next.
        datasets.reset_current(token)
    # Lets a client (and a human reading devtools) confirm which database answered,
    # rather than inferring it from the numbers.
    response.headers["X-Dataset"] = datasets.resolve(key).key
    return response


class InvestigateRequest(BaseModel):
    metric: str = "revenue"
    window_start: datetime
    window_end: datetime


class NarrationOut(BaseModel):
    text: Optional[str]
    available: bool
    provider: str
    error: Optional[str] = None


class InvestigateResponse(BaseModel):
    id: Optional[str] = None
    evidence: dict
    narration: NarrationOut
    langfuse_trace_url: Optional[str] = None


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: Optional[str]
    available: bool
    provider: str
    error: Optional[str] = None


def _validate_investigate(metric: str, window_start: datetime, window_end: datetime) -> None:
    if metric not in METRIC_DEFS:
        raise HTTPException(status_code=400, detail=f"Unknown metric '{metric}'. Valid: {list(METRIC_DEFS.keys())}")
    if window_end <= window_start:
        raise HTTPException(status_code=400, detail="window_end must be after window_start")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/api/metrics")
def list_metrics():
    """Lets the UI populate its metric dropdown without hardcoding the list twice."""
    return {"metrics": list(METRIC_DEFS.keys()), "watchlist": WATCHLIST}


@app.get("/api/datasets")
def list_datasets():
    """The switcher's own data: what can be selected, and what is in each one.

    The UI must not hardcode dataset names, date ranges or row counts -- the same
    rule /api/registry states for metrics and grains. A second copy of these facts
    would be free to drift, and here it would drift into the most misleading shape
    available: a label claiming a date range the data does not have.

    `provisioned` is the honest part. A dataset whose `baselines` table is empty has
    nothing to detect against, so the console would render a blank -- correct, but
    indistinguishable from "nothing is wrong". Reporting it lets the switcher say
    which datasets have actually been swept, and the counts say how thoroughly.

    Each dataset is measured through its OWN connection (`use_dataset`), so this one
    route also exercises the isolation the rest of the feature depends on: if the
    clocks it returns are identical, the keying is broken.
    """
    out = []
    for spec in datasets.all_datasets():
        entry = {"key": spec.key, "label": spec.label, "database": spec.database, "note": spec.note}
        try:
            with datasets.use_dataset(spec.key):
                clock = ops_view.data_clock()
                counts = monitor_store.dataset_state_counts()
                # The switcher labels each option with its span, so it needs the START
                # too. data_floor() is the existing definition of "first event" and is
                # already cached per database for the sweep's window-completeness
                # guard, so this is a dictionary hit after the first call rather than a
                # second aggregate over 9M rows.
                first_event = sweep_data_floor()
            entry.update({
                "as_of": clock["as_of"],
                "min_event_time": first_event,
                "max_event_time": clock["max_event_time"],
                "total_rows": clock["total_rows"],
                "clock_source": clock["source"],
                "baselines": counts["baselines"],
                "incidents": counts["incidents"],
                "sweeps": counts["sweep_runs"],
                "provisioned": counts["baselines"] > 0,
                "available": True,
            })
        except Exception as e:
            # A dataset that cannot be reached must not take the switcher down with
            # it -- the other one is still usable, and saying which failed and why is
            # more useful than a 500 on a page that is otherwise fine.
            entry.update({"available": False, "provisioned": False, "error": str(e)[:300]})
        out.append(entry)
    return {"datasets": out, "active": datasets.active_key(), "default": datasets.DEFAULT_KEY}


@app.post("/investigate", response_model=InvestigateResponse)
def investigate(req: InvestigateRequest) -> InvestigateResponse:
    _validate_investigate(req.metric, req.window_start, req.window_end)

    try:
        result = run_investigation(req.metric, req.window_start, req.window_end)
    except Exception as e:
        # ClickHouse/engine failure: never fabricate a result -- surface the error.
        raise HTTPException(status_code=502, detail=f"Investigation failed: {e}")

    inv_id = store.save_investigation(result, triggered_by="manual")

    return InvestigateResponse(
        id=inv_id,
        evidence=result.evidence.model_dump(mode="json"),
        narration=NarrationOut(
            text=result.narration.narration,
            available=result.narration.available,
            provider=result.narration.provider,
            error=result.narration.error,
        ),
        langfuse_trace_url=result.langfuse_trace_url,
    )


@app.get("/api/investigations")
def list_investigations(limit: int = 50):
    """History feed for the UI -- most recent first, bounded."""
    return {"investigations": store.list_investigations(limit=limit)}


@app.get("/api/investigations/{investigation_id}")
def get_investigation(investigation_id: str):
    row = store.get_investigation(investigation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    row["chat"] = store.list_chat_turns(investigation_id)
    return row


def _investigation_evidence_for_llm(evidence: Optional[dict]) -> Optional[dict]:
    """An investigation's evidence bundle with the verbatim SQL trace removed.

    This is the same contract EvidenceBundle.to_llm_json() enforces for the narrator
    (engine/evidence.py) -- "every computed number, no raw SQL text" -- applied to the
    persisted form, which chat reads back from ClickHouse as a plain dict and so cannot
    call that method on. Chat previously reached around it and shipped all 96 queries:
    46,817 characters of SQL that the system prompt explicitly forbids the model to
    compute from, on every single turn. The trace is not lost, it is simply not the
    model's business -- it is still returned in full by the investigation route and
    still rendered by SqlTrace.tsx.
    """
    if not evidence:
        return evidence
    return {k: v for k, v in evidence.items() if k != "queries"}


def _run_chat_turn(subject_kind: str, subject_id: str, evidence: dict, message: str,
                   background: BackgroundTasks) -> ChatResponse:
    """One follow-up turn against one already-computed evidence bundle.

    Shared by the investigation and incident routes because the guardrail is the same
    for both and must not be able to differ between them: the model sees an evidence
    bundle and a transcript, never the database.

    Ordering note -- the user's turn is persisted BEFORE the model is called, so a
    question that crashes or times out is still in the transcript. A conversation that
    silently loses the turns it failed on is a conversation whose history is a lie.
    """
    history = [{"role": t["role"], "content": t["content"]} for t in store.list_chat_turns(subject_id)]
    next_turn = len(history)
    store.save_chat_turn(subject_id, next_turn, "user", message)

    with tracing.traced_chat(subject_kind, subject_id, message, {"history_turns": len(history)}):
        reply = chat_ask(evidence, history, message)
        if reply.available:
            store.save_chat_turn(subject_id, next_turn + 1, "assistant", reply.reply)
    # Langfuse buffers, so a short-lived request must not end with the span unexported
    # -- but the export is a blocking round trip to Langfuse's region, and making the
    # operator wait for it before seeing their answer buys them nothing. It still runs
    # on this request, just after the reply is on the wire; atexit still covers the
    # process. "No trace, no credit" is unchanged.
    background.add_task(tracing.flush)

    return ChatResponse(reply=reply.reply, available=reply.available,
                        provider=reply.provider, error=reply.error)


@app.post("/api/investigations/{investigation_id}/chat", response_model=ChatResponse)
def investigation_chat(investigation_id: str, req: ChatRequest,
                       background: BackgroundTasks) -> ChatResponse:
    row = store.get_investigation(investigation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return _run_chat_turn("investigation", investigation_id,
                          _investigation_evidence_for_llm(row["evidence"]), req.message, background)


@app.get("/api/scanner/ticks")
def scanner_ticks(limit: int = 100):
    """The "list all the events" feed -- every real scan tick the background
    monitor has recorded, anomalous or not."""
    return {"ticks": store.list_scan_ticks(limit=limit)}


@app.get("/api/dashboard")
def dashboard(as_of: Optional[datetime] = None):
    """One call for the UI's live dashboard: recent hourly_overall series for
    charts, the latest tick per watchlist metric (for the metric-tree tiles),
    and a genuine data-freshness check (max(event_time)/row count -- not a
    fake heartbeat). Deliberately ONE grouped query for the whole 7-day
    series, not one query per hour -- see CLAUDE.md's "bounded, resilient
    ClickHouse access" and "concurrency where independent" principles; this
    is the "where independent" counterpart -- don't fan out at all when a
    single GROUP BY already does the job.

    `as_of` overrides "now" (ISO datetime) -- needed to demo against the
    static sample dataset (Jun 1 - Jul 5 2026), which has no data anywhere
    near the real wall clock. Omit it once pointed at a dataset with live,
    real-time-ish timestamps (e.g. the unseen incident)."""
    from engine.ch_client import Trace, get_client

    client = get_client()
    trace = Trace()

    now = as_of or datetime.utcnow()
    hour = now.replace(minute=0, second=0, microsecond=0)
    range_start = hour - timedelta(hours=168)

    rows = client.query(
        "SELECT hour, sum(requests) AS requests, sum(fills) AS fills, sum(impressions) AS impressions, "
        "sum(clicks) AS clicks, sum(revenue) AS revenue FROM hourly_overall "
        f"WHERE hour >= '{range_start:%Y-%m-%d %H:%M:%S}' AND hour < '{hour + timedelta(hours=1):%Y-%m-%d %H:%M:%S}' "
        "GROUP BY hour ORDER BY hour",
        step="dashboard:series",
        trace=trace,
    )
    series = [
        {
            "hour": r["hour"].isoformat(), "requests": int(r["requests"] or 0), "fills": int(r["fills"] or 0),
            "impressions": int(r["impressions"] or 0), "clicks": int(r["clicks"] or 0), "revenue": float(r["revenue"] or 0),
        }
        for r in rows
    ]

    ticks = store.list_scan_ticks(limit=len(WATCHLIST) * 5)
    latest_by_metric = {}
    for t in ticks:
        if t["metric"] not in latest_by_metric:
            latest_by_metric[t["metric"]] = t

    return {
        "series": series,
        "metric_tiles": [latest_by_metric[m] for m in WATCHLIST if m in latest_by_metric],
        "data_freshness": check_new_data(client),
        "scanner": {"enabled": settings.scanner_enabled, "interval_seconds": settings.scanner_interval_seconds},
    }


# ---------------------------------------------------------------------------
# Operations console
#
# Everything below is a stateless read, and none of it takes a metric or a
# window. That is the whole point: the monitoring layer already knows what moved,
# what it cost and who owns it, so an ad-ops reader should never have to tell the
# system what to look at. Requiring them to pick a metric and type two timestamps
# -- which is what the old UI did -- is the manual dashboard-drilling this project
# exists to replace.
#
# The one route that DOES take a metric and a window is POST /investigate, which
# is kept for reproducing a specific window (the Analyst panel) and is off the
# operations path.
# ---------------------------------------------------------------------------


@app.get("/api/ops/summary")
def ops_summary():
    """The operations home screen, in one call, with NO parameters.

    Carries the data clock (so the UI never needs a date picker), the
    green/amber/red metric tree over the exact revenue identity, the largest
    movement currently outside its band, the chronological incident queue, and
    the sweep receipt. Exposure totals are carried too, as supporting detail
    rather than as the headline.

    One round trip by design -- assembling this client-side from four endpoints
    produces a screen that renders in four stages and shows a different total in
    each of them.
    """
    try:
        summary = ops_view.ops_summary()
        # Which dataset produced these numbers, stated in the payload rather than left
        # to the caller's memory of what it asked for. The screen shows one set of
        # figures at a time and they are indistinguishable by eye, so this is what lets
        # the UI label them and what makes a wrong-dataset bug visible in one response.
        summary["dataset"] = datasets.active_key()
        summary["database"] = datasets.current_database()
        return summary
    except Exception as e:
        # Fail loudly with the reason rather than returning a hollow shell that
        # renders as a healthy, all-green dashboard.
        raise HTTPException(status_code=502, detail=f"Operations summary failed: {e}")


@app.get("/api/incidents")
def list_incidents(limit: int = 100, open_only: bool = False, include_gated: bool = True):
    """The work queue: clustered incidents, newest first.

    Each row carries how far its root metric actually moved -- deviation in band-widths,
    the observed value and the seasonal centre it was compared against -- alongside the
    exposure estimate, which is retained as detail rather than as the ordering.

    `include_gated=False` hides incidents below the impact gate. They are always
    persisted and always queryable -- suppression is a display choice here, never a
    silent discard -- and the gate value is returned alongside so the UI can say
    what it is hiding and why.
    """
    rows = monitor_store.list_incidents(limit=limit, open_only=open_only)
    if not include_gated:
        rows = [r for r in rows if not r.get("gated_by_impact")]
    return {
        "incidents": rows,
        "impact_gate_usd": settings.impact_usd_gate,
        "gate_note": (
            "Movements on slices too small to matter are recorded but not raised: a large "
            "deviation on a commercially immaterial slice is not an incident. The threshold "
            f"is an exposure estimate of ${settings.impact_usd_gate:,.2f} a day."
        ),
    }


@app.get("/api/incidents/{incident_id}")
def get_incident(incident_id: str):
    """One incident, with everything needed to judge it: the deterministic
    mechanism, the dollar decomposition, the spread evidence behind the
    localisation, the seasonality disproof, recurrence history, the member
    breaches, the absorbed symptom clusters, and the evidence-score breakdown."""
    row = monitor_store.get_incident(incident_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    # The transcript, so a reload does not empty the conversation on screen while the
    # model keeps using it as history. The two must not be able to diverge: the same
    # list is what _run_chat_turn replays into the prompt.
    row["chat"] = store.list_chat_turns(incident_id)
    # THE SUPPORTING SQL TRAVELS WITH THE INCIDENT.
    #
    # Not behind a second call: whoever holds the incident holds the proof for its
    # numbers, with nothing further to fetch and nothing to correlate by hand. This is
    # what closes the gap that `evidence.queries` never could -- that field is written
    # only for the top few incidents per sweep, so 821 of 825 incidents carried no SQL
    # at all and the trace section rendered nothing on almost every page.
    #
    # Cheap enough to be unconditional: build_provenance() is pure (no queries), and the
    # payload is ~30 facts of a few hundred characters -- single-digit KB against the
    # 249 KB this response already carries.
    row["provenance"] = provenance_payload(row)
    # Incident ids do not cross datasets, so a page opened against the wrong one 404s
    # rather than showing something plausible. Naming the dataset that DID serve it is
    # what lets the UI say which world this incident is from.
    row["dataset"] = datasets.active_key()
    row["database"] = datasets.current_database()
    return row


class VerifyRequest(BaseModel):
    """A fact KEY, never SQL.

    This shape is the security boundary, not a convenience. `ch_client.query()` runs an
    arbitrary statement verbatim and `command()` is a live write path, so a route that
    accepted a query string would be a SQL-execution endpoint wearing a verification
    costume. The server re-derives the statement from the incident's own stored fields
    and runs it through `query_readonly` (allowlisted statement kinds, readonly=2,
    row-capped, short timeout). No field on this model reaches the query text.
    """

    fact: str


@app.post("/api/incidents/{incident_id}/verify")
def verify_incident_fact(incident_id: str, req: VerifyRequest):
    """Re-runs the query behind one number and reports whether it still reproduces it.

    This is what makes the provenance PROVEN rather than merely shown. A figure that has
    drifted from what the database now returns fails here in the open, on the page, next
    to the number -- which is the opposite of the usual failure mode where a stale
    number keeps looking authoritative because nothing re-checks it.

    A `derived` or `config` fact is not an error: it answers with its formula and the
    input keys the reader can verify individually, because that is the honest account of
    a figure no single query produces.
    """
    row = monitor_store.get_incident(incident_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    try:
        return verify_fact(row, req.fact)
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown fact '{req.fact}' for this incident. Valid keys are the "
                   f"keys of provenance.facts on GET /api/incidents/{incident_id}.",
        )
    except ValueError as e:
        # query_readonly's statement allowlist. Reaching this means a reconstruction
        # produced something that is not a read, which is a bug in provenance.py rather
        # than anything the caller did -- so it is a 500, not a 400.
        raise HTTPException(status_code=500, detail=f"refused to run reconstructed SQL: {e}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"verification query failed: {e}")


@app.get("/api/incidents/{incident_id}/causal-chain")
def incident_causal_chain(incident_id: str):
    """The diagnosis as one because-ladder, for a reader who is not an analyst.

    Derived entirely from fields the incident already carries -- no query, no
    arithmetic, no LLM -- so it is available whether or not narration is, and it cannot
    disagree with the charts it summarises. See engine/causal_chain.py.
    """
    row = monitor_store.get_incident(incident_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return build_chain(row).to_dict()


def _incident_chat_evidence(row: dict) -> dict:
    """What the model is allowed to see about an incident.

    Assembled from fields the incident ALREADY carries -- nothing is computed here and
    no query is run, so every number the model can reach is one that was already
    persisted with its source_step attached. The evidence bundle is included when the
    incident was investigated; when it was not, the deterministic blocks below are the
    whole of it, which is exactly the case this route exists for.
    """
    keys = (
        "incident_id", "signature", "mechanism", "signature_confidence", "owner",
        "root_scope_type", "root_scope_value", "root_metric", "grain", "direction",
        "breached_metrics", "impact_usd", "impact_usd_per_day", "windows_spanned",
        "opened_at", "last_seen_at", "member_event_count", "gated_by_impact",
        "ruled_out", "seasonality", "impact_breakdown", "history", "absorbed",
        "evidence_score_detail", "narration", "label",
    )
    payload = {k: row.get(k) for k in keys if row.get(k) is not None}
    if row.get("evidence"):
        payload["investigation_evidence"] = _investigation_evidence_for_llm(row["evidence"])
    # Members and absorbed clusters are the audit trail beneath the incident. Both are
    # capped for the same reason the UI caps them: they are supporting detail, and a
    # prompt stuffed with hundreds of near-identical rows crowds out the argument the
    # model is supposed to be answering from. Measured before capping: one real
    # incident's prompt was 975,728 characters -- roughly a quarter of a million tokens
    # of prefill on EVERY turn -- of which 900,412 were 2,520 absorbed entries.
    #
    # Every cap reports its own total, and the note below states plainly that these are
    # previews. A truncated list the model reads as complete is how "3 apps breached"
    # gets said about 170 (the same failure gotcha 37 records for the incident queue).
    members = row.get("members") or []
    absorbed = row.get("absorbed") or []
    payload["members_shown"] = members[:settings.chat_members_preview_limit]
    # The incident's OWN count, not the length of the fetched list -- get_incident
    # fetches at most 500 members, so a 765-member incident would otherwise be
    # described to the model as having 500.
    payload["members_total"] = int(row.get("member_event_count") or len(members))
    payload["absorbed"] = absorbed[:settings.absorbed_preview_limit]
    payload["absorbed_total"] = row.get("absorbed_total", len(absorbed))
    # WHAT THE MODEL IS TOLD TO CITE, IT CAN NOW ACTUALLY SEE.
    #
    # chat.py's system prompt orders the model to name the source_step behind each figure
    # and to refuse when a number has none. Until now the only steps it received were the
    # ones on `ruled_out` and `history`, so the page's own suggested question -- "Which
    # queries produced these numbers?" -- was unanswerable: `queries` is stripped below
    # and nothing else carried a step.
    #
    # Sent as step/formula/kind per fact and deliberately WITHOUT `sql`: the same
    # contract EvidenceBundle.to_llm_json() has always enforced. The model is forbidden
    # to compute, so query text is inert context that once cost 46,817 characters a turn.
    prov = row.get("provenance") or provenance_payload(row)
    payload["number_provenance"] = {
        key: {k: v for k, v in f.items()
              if k in ("kind", "step", "table", "formula", "config_path", "inputs")}
        for key, f in (prov.get("facts") or {}).items()
    }
    payload["provenance_note"] = (
        "number_provenance maps each figure to how it is established: kind='measured' "
        "means one logged query returns it (cite its step), 'derived' means the stated "
        "formula over the listed input keys (cite those), 'config' means a configured "
        "constant and NOT a measurement. The query text itself is deliberately withheld: "
        "you must not compute from SQL, only cite the step."
    )
    payload["truncation_note"] = (
        f"members_shown lists {len(payload['members_shown'])} of {payload['members_total']} "
        f"member breaches and 'absorbed' lists {len(payload['absorbed'])} of "
        f"{payload['absorbed_total']} absorbed clusters, both ordered by significance. "
        "They are previews: never state or imply that they are the complete set, and "
        "when a question needs the full list, say it is not in this evidence."
    )
    return payload


@app.post("/api/incidents/{incident_id}/chat", response_model=ChatResponse)
def incident_chat(incident_id: str, req: ChatRequest, background: BackgroundTasks) -> ChatResponse:
    """Follow-up chat grounded in ONE incident's own evidence.

    Separate from the investigation route because only the top few incidents per sweep
    are fully investigated (settings.max_investigations_per_sweep = 3). Every other
    incident has no investigation_id, and so had no chat at all -- on a queue of 33
    alertable incidents, that is most of them. The incident itself always carries a
    mechanism, a spread argument, ruled-out checks and a dollar decomposition, which is
    enough to answer questions from.
    """
    row = monitor_store.get_incident(incident_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="message must be a non-empty string")
    return _run_chat_turn("incident", incident_id, _incident_chat_evidence(row), req.message, background)


class LabelRequest(BaseModel):
    label: str


@app.post("/api/incidents/{incident_id}/label")
def label_incident(incident_id: str, req: LabelRequest):
    """Records a post-mortem verdict ('true_positive', 'false_positive',
    'known_seasonal', ...) on an incident and its member events.

    This is the feedback loop the design calls for: with labels accumulated,
    per-slice precision becomes measurable and the band thresholds can be tuned
    from evidence instead of taste. It was computed for and stored on both tables
    from day one but had no way in until now.
    """
    if monitor_store.get_incident(incident_id) is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    if not req.label or not req.label.strip():
        raise HTTPException(status_code=400, detail="label must be a non-empty string")
    ok = monitor_store.set_label(incident_id, req.label)
    if not ok:
        raise HTTPException(status_code=502, detail="Failed to persist label")
    return {"incident_id": incident_id, "label": req.label.strip(), "saved": True}


@app.get("/api/events")
def list_events(limit: int = 200, grain: Optional[str] = None, scope_type: Optional[str] = None,
                min_impact: Optional[float] = None, only_alertable: bool = False):
    """Raw band breaches -- the audit history beneath the incidents.

    `grain` accepts the 14 monitored grains AND 'drift' (CUSUM events), which is
    deliberately not in GRAIN_REGISTRY; a filter built only from the registry would
    silently hide every drift finding.
    """
    valid = set(monitored_grains()) | {DRIFT_GRAIN}
    if grain is not None and grain not in valid:
        raise HTTPException(status_code=400, detail=f"grain must be one of {sorted(valid)}")
    if scope_type is not None and scope_type not in SCOPE_REGISTRY:
        raise HTTPException(status_code=400, detail=f"scope_type must be one of {sorted(SCOPE_REGISTRY)}")
    return {
        "events": monitor_store.list_events(
            limit=limit, grain=grain, scope_type=scope_type,
            min_impact=min_impact, only_alertable=only_alertable,
        )
    }


@app.get("/api/coverage")
def coverage(run_id: Optional[str] = None):
    """What the last sweep actually evaluated, and what it did not.

    This is the queryable form of the "everything is monitored" claim. Each
    (scope, metric, grain) cell reports evaluated / skipped-low-power / no-band /
    skipped-cadence counts with the number that caused the skip -- so the honest
    gaps (per-app CTR has no valid grain; the 1mo grain has no usable baseline on a
    35-day dataset) are visible rather than discovered.
    """
    return {
        "sweep": monitor_store.latest_sweep(),
        "cells": monitor_store.coverage_matrix(run_id=run_id),
    }


@app.get("/api/calibration")
def calibration():
    """How often this detector cries wolf, measured rather than claimed.

    Serves the JSON twin of Docs/BACKTEST_SCORECARD.md, written by scripts/backtest.py
    in the same pass that writes the markdown -- so the /method page cannot drift from
    the scorecard by being transcribed by hand.

    It is a file read, not a live replay: a 35-day replay takes minutes and must not be
    triggerable from an HTTP request. When the file is absent the route says so
    explicitly, because an empty calibration page and a perfectly calibrated one must
    not look the same.
    """
    path = os.path.join(_REPO_DIR, "Docs", "backtest_scorecard.json")
    if not os.path.exists(path):
        return {
            "available": False,
            "reason": ("No backtest has been run against this build. Run "
                       "`python scripts/backtest.py --k 3` to generate it. Until then "
                       "this system's false-positive rate is unmeasured, and no claim "
                       "about it should be believed."),
        }
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, ValueError) as e:
        raise HTTPException(status_code=500, detail=f"calibration file unreadable: {e}")
    payload["available"] = True
    # WHICH DATASET THIS CALIBRATION IS ABOUT, and why it is not the active one.
    #
    # This is a file on disk describing a 35-day replay of the PRIMARY dataset. It does
    # not change when the switcher changes, and it cannot: the replay is minutes of work
    # and the unseen dataset has 5 days of history, far too little to replay 35 of.
    #
    # So the number is stated with its subject attached rather than hidden. A false-alarm
    # rate measured on one dataset, displayed unlabelled beside another dataset's
    # incidents, would be a fabricated claim about data that was never tested -- the one
    # thing this project treats as worse than having no number at all. The UI captions it
    # when `measured_on_active` is false; it does not silently drop it, because removing
    # an unflattering measurement is its own kind of dishonesty.
    payload["measured_on"] = settings.clickhouse_database
    payload["measured_on_dataset"] = datasets.DEFAULT_KEY
    payload["active_dataset"] = datasets.active_key()
    payload["measured_on_active"] = datasets.current_database() == settings.clickhouse_database
    return payload


@app.get("/api/registry")
def registry():
    """Metric, scope, grain and threshold metadata, so the UI never duplicates the
    backend's tables.

    Without this, a client has to hardcode its own copy of the metric labels, the
    owner mapping, which metrics are structurally unsupported per scope, and the
    severity thresholds -- and every one of those copies is free to drift out of
    agreement with the engine that produced the numbers.
    """
    return {
        "metrics": [
            {
                "name": name,
                "label": ops_view.METRIC_LABELS.get(name, (name, ""))[0],
                "unit": ops_view.METRIC_LABELS.get(name, (name, ""))[1],
                "meaning": ops_view.METRIC_MEANING.get(name, ""),
                "owner": spec.owner,
                "bad_direction": spec.bad_direction,
                "numerator": spec.numerator,
                "denominator": spec.denominator,
                "multiplier": spec.multiplier,
                "power_base": spec.power_base,
                "power_floor": spec.power_floor,
                "monitored": name in monitored_metrics(),
            }
            for name, spec in METRIC_DEFS.items()
        ],
        "scopes": [
            {
                "name": s.name,
                "label": s.label,
                "implicates": s.implicates,
                "key_columns": list(s.key_columns),
                "is_entity": s.is_entity,
                "is_composite": s.is_composite,
                "unsupported_metrics": list(s.unsupported_metrics),
                "sub_hour_capable": s.minute5_table is not None,
                "monitored": s.name in monitored_scopes(),
            }
            for s in SCOPE_REGISTRY.values()
        ],
        "grains": [
            {"name": n, "seconds": GRAIN_REGISTRY[n].seconds,
             "is_rolling": GRAIN_REGISTRY[n].is_rolling}
            for n in monitored_grains()
        ] + [{"name": DRIFT_GRAIN, "seconds": None, "is_rolling": False}],
        "tree": {
            "root": ops_view.TREE_ROOT,
            "factors": ops_view.TREE_FACTORS,
            "siblings": ops_view.TREE_SIBLINGS,
            "identity": "Revenue = Requests x Fill rate x Show rate x eCPM / 1000",
            "decomposition_factors": REVENUE_DECOMPOSITION_FACTORS,
            "grain": ops_view.DEFAULT_TREE_GRAIN,
        },
        "thresholds": {
            "band_k_amber": settings.band_k_amber,
            "band_k_red": settings.band_k_red,
            "impact_usd_gate": settings.impact_usd_gate,
            "consecutive_points_required": settings.consecutive_points_required,
            "band_min_samples": settings.band_min_samples,
            "band_method": settings.band_method,
        },
        "owners": ["demand", "engineering", "pricing", "growth", "creative", "external", "unassigned"],
    }


@app.get("/")
def index():
    """Points at the real console rather than serving a second one.

    This used to return api/static/index.html -- a standalone demo page with its own
    metric dropdown, its own two date pickers and its own copy of the status colour
    logic. Two dashboards reading the same database through different code paths will
    eventually disagree, and a reader has no way to tell which one is wrong. The
    superseded page is still on disk and still reachable at /static/index.html for
    reference; it is simply no longer what this route hands out.
    """
    return {
        "service": "Automated Root-Cause Analyst",
        "console": "http://127.0.0.1:8089",
        "note": (
            "This is the JSON API. The operations console is the React app on port 8089. "
            "Start here: GET /api/ops/summary (no parameters -- the system already knows "
            "what moved, what it cost and who owns it)."
        ),
        "routes": {
            "operations_summary": "/api/ops/summary",
            "incidents": "/api/incidents",
            "incident_detail": "/api/incidents/{incident_id}",
            "label_incident": "POST /api/incidents/{incident_id}/label",
            "breach_events": "/api/events",
            "coverage": "/api/coverage",
            "registry": "/api/registry",
            "manual_investigation": "POST /investigate",
            "health": "/healthz",
        },
    }


app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
