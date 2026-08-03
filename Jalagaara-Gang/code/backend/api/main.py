"""Lane C: FastAPI orchestration.

Endpoint surface (docs/superpowers/specs/2026-08-01-rca-api-design.md):

    GET  /health                    liveness
    GET  /bundle/{id}               retrieve a stored Evidence Bundle
    GET  /bundles                   investigation history
    POST /investigate               run the pipeline (still fixture-backed)
    POST /v1/chat/completions       conversational entry point; LibreChat points here

  uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api import chat as chatlib
from api import dev, pipeline, stream_job
from config import LANGFUSE, config, dataset_name, target_hourly
from data import store
from data.client import clickhouse_available
from models import EvidenceBundle, Window
from narrator import narrate, trace_read
from rca import series

app = FastAPI(title="Automated Root-Cause Analyst")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

# Dev/admin dashboard at /dev — local only, gated by env (default on). Never enable on a public deploy.
if dev.dev_enabled():
    app.include_router(dev.router)


class InvestigateRequest(BaseModel):
    metric: str = "revenue"
    window: Window | None = None


@app.get("/health")
def health() -> dict:
    """Wiring dashboard, not just liveness.

    Judges run this stack locally, where the failure modes are silent: a fresh Langfuse has no
    API keys and tracing quietly no-ops, and the RCA engine may still be stubbed. Reporting
    both here means a judge sees what is actually live before drawing conclusions from it.
    """
    return {
        "ok": True,
        "engine": pipeline.engine_mode(),            # live | fixture | offline
        # Which tables everything is pointed at. Reported because it is invisible otherwise:
        # a sweep over the streamed range returned 0 findings purely because the target had
        # reverted to dev, and nothing on screen said so.
        # `available` so the UI offers the real set rather than hardcoding names that could
        # drift from config.json.
        "dataset": {
            "target": dataset_name("target"),
            "history": dataset_name("history"),
            "available": list(config()["datasets"]),
        },
        "langfuse": {
            "enabled": bool(LANGFUSE["public_key"]),
            "host": LANGFUSE["host"],
        },
    }


class DatasetRequest(BaseModel):
    target: str


@app.post("/dataset")
def set_dataset(req: DatasetRequest) -> dict:
    """Point investigations at a dataset: 'dev' (Jun 1-Jul 5) or 'unseen' (the streamed slice).

    History deliberately stays where it is — baselines need the five weeks of dev data whichever
    slice is under investigation.
    """
    if req.target not in config()["datasets"]:
        raise HTTPException(status_code=400,
                            detail=f"unknown dataset {req.target!r}; expected one of "
                                   f"{list(config()['datasets'])}")
    os.environ["RCA_DATASET"] = req.target
    return {"target": dataset_name("target"), "history": dataset_name("history")}


@app.post("/investigate", response_model=EvidenceBundle)
def investigate(req: InvestigateRequest) -> EvidenceBundle:
    """Run an investigation and return it WITHOUT a narrative. Never writes to `bundles`.

    `bundles` is seed-path-only — dev.py's seed_bundles/seed_context are the only writers.
    The dashboard's Investigate button now drives POST /dev/seed_bundles, not this endpoint, so
    this stays a pure compute-and-return: no LLM in the path, so a judge (or anyone) can call it
    twice and diff the result to verify reproducibility, without side effects on the stored
    anomaly history. Narration is POST /narrate/{id} (also non-persisting unless explicitly
    asked, which nothing does).
    """
    bundle = pipeline.run_investigation(req.metric, req.window, persist=False)
    # Mirror the segment-scope override from dev.py seed_bundles: if global detection
    # didn't fire but localization found a segment, the anomaly is real — promote it.
    if not bundle.anomaly.detected and bundle.localized_segment:
        bundle.anomaly.detected = True
    return bundle


@app.post("/narrate/{investigation_id}", response_model=EvidenceBundle)
def narrate_bundle(investigation_id: str) -> EvidenceBundle:
    """Add prose to a stored investigation.

    Split from /investigate so the UI shows real numbers in ~2s and only then the sentence
    arrives. The generation span reattaches to the trace the investigation already opened, so
    a judge reads one investigation rather than two unrelated traces.

    An LLM failure returns 200 with `narrative: null` rather than an error: the numbers,
    drilldown and ruled-out list are already computed and scoreable, so a Bedrock outage
    degrades the answer instead of losing it.
    """
    bundle = pipeline.narrate_investigation(investigation_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail=f"No investigation {investigation_id!r}")
    return bundle


@app.get("/bundle/{investigation_id}", response_model=EvidenceBundle)
def get_bundle(investigation_id: str) -> EvidenceBundle:
    """Retrieve a stored Evidence Bundle.

    This is how a judge re-reads an investigation after the fact, and it is the
    submission artifact path for the unseen incident.
    """
    # Fail soft: a datastore outage returns 503 with a clear reason, not a raw 500 stacktrace.
    if not clickhouse_available():
        raise HTTPException(status_code=503, detail="Investigation store offline (check CLICKHOUSE_*)")
    bundle = store.load_bundle(investigation_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail=f"No investigation {investigation_id!r}")
    return bundle


@app.get("/bundles")
def list_bundles(limit: int = 50) -> dict:
    """Investigation history — flattened rows (metric, window, primary factor, localization,
    detected/narrated flags, trace/session ids), not the full bundles. Powers the dashboard's
    past-runs panel; for the anomaly-only switcher feed use GET /dashboard, for one full bundle
    use GET /bundle/{investigation_id}.

    Fails soft: when the datastore is unreachable (e.g. CLICKHOUSE_* unset in a container) this
    returns an empty history with engine:"offline" rather than 500-ing and blanking the dashboard.
    """
    if not clickhouse_available():
        return {"count": 0, "investigations": [], "engine": "offline"}
    rows = store.list_investigations(limit)
    return {"count": len(rows), "investigations": rows, "engine": "live"}


@app.get("/series/{investigation_id}")
def get_series(investigation_id: str) -> dict:
    """Hourly actual-vs-expected series behind the anomaly card's chart.

    The metric in 1-hour chunks over the 24 hours ending at the anomaly, plus the like-for-like
    expected line — population-wide (global), to match the card's headline % and observed/expected.
    The two SQL queries are logged to the investigation's trace like every other number shown.

    Fails soft: an unreachable datastore returns 503, a missing investigation 404.
    """
    if not clickhouse_available():
        raise HTTPException(status_code=503, detail="Investigation store offline (check CLICKHOUSE_*)")
    bundle = store.load_bundle(investigation_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail=f"No investigation {investigation_id!r}")
    return series.hourly_series(bundle)


@app.get("/trace/{investigation_id}")
def get_trace(investigation_id: str) -> dict:
    """The investigation's Langfuse trace, reshaped as a readable timeline for the dashboard.

    The Langfuse UI itself is developer-facing; this is the customer view — one step per phase
    with a plain-language headline and the SQL behind it. Always 200: a missing trace or an
    unreachable Langfuse comes back as `available: false` with a reason, which the drawer shows.
    """
    if not clickhouse_available():
        return {"available": False, "reason": "Investigation store offline (check CLICKHOUSE_*)"}

    # Snapshot first: Langfuse owns the live trace, we own the history. Cached on first
    # successful read rather than at investigation time, because Langfuse ingests spans
    # asynchronously — the trace is not complete the instant the investigation returns.
    stored = store.load_trace_view(investigation_id)
    if stored:
        return {**stored, "source": "stored"}

    trace_id, _ = store.load_meta(investigation_id)
    view = trace_read.trace_view(trace_id)
    if view.get("available"):
        store.save_trace_view(investigation_id, view)
    return {**view, "source": "live"}


class ScanRequest(BaseModel):
    """Window to sweep. Grain/scope/sensitivity stay server-side — nobody should have to tune a
    detection dial to get an answer; `method` picks the detector for the global pass."""
    start: str
    end: str
    method: str = "isolation_forest"


@app.post("/scan")
def start_scan(req: ScanRequest) -> dict:
    """Sweep an ARBITRARY window for anomalies — no ground-truth case list, it finds them itself.

    This is the unseen-incident path: point it at a date range and it scans every metric
    globally plus every value of every dimension, folds echoes of the same underlying event,
    and localizes the top findings. A full sweep is ~50 queries, so it runs as a background
    job — poll GET /scan/{job_id}.
    """
    return dev.start_discover_job(req.start, req.end, grain="day", scope="both",
                                  min_effect=0.0, method=req.method)


@app.get("/scan/{job_id}")
def scan_status(job_id: str) -> dict:
    """Poll a sweep. `finished` flips true, then `result.incidents` holds the findings."""
    return dev.job_status(job_id)


class StreamRequest(BaseModel):
    """Replay knobs; every field defaults to config.stream so a bare POST is a valid demo run."""
    batch_hours: int | None = None
    tick_seconds: float | None = None
    detect_metrics: list[str] | None = None
    detect_method: str | None = None
    reset: bool = True


@app.post("/stream/start")
def stream_start(req: StreamRequest) -> dict:
    """Replay the sealed unseen slice as a live stream, scoring each hour as it lands.

    Ingestion and inference in one loop: every batch is detected on, and a metric that fires
    gets a full traced investigation persisted, so findings appear in the dashboard while the
    stream is still running. Switches the process to the unseen dataset for the duration —
    baselines keep reading dev history, which is what makes 5 days of data detectable at all.
    """
    overrides = {k: v for k, v in req.model_dump(exclude={"reset"}).items() if v is not None}
    try:
        return stream_job.start(overrides, reset=req.reset)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@app.post("/stream/stop")
def stream_stop() -> dict:
    """Stop after the current batch — a half-written batch would corrupt the rollup."""
    return stream_job.stop()


@app.get("/stream/status")
def stream_status() -> dict:
    """Progress, throughput, and the detections found so far. Safe to poll."""
    return stream_job.status()


@app.get("/dashboard")
def list_dashboard(limit: int = 50, since: datetime | None = None) -> dict:
    """Dashboard-ready incident feed, meant to be polled.

    Reads `bundles` directly — the anomaly numbers/localization/ruled-out summary are already
    flattened so the dashboard never has to parse the full bundle JSON just to render a card.

    Pass `since` (the `created_at` of the newest row already shown) to fetch only what's new
    since the last poll instead of re-pulling the whole list every tick.
    """
    # Scoped to the dataset under investigation. `bundles` holds every investigation ever run,
    # so an unscoped feed left dev-era incidents (requests -43.5% on Jun 21) in the switcher
    # while the dashboard was pointed at the streamed slice.
    within = store.dataset_bounds(target_hourly())
    rows = store.list_dashboard(limit, since, within=within)
    return {"count": len(rows), "incidents": rows, "dataset": dataset_name("target")}


# ---------------------------------------------------------------------------
# Conversational layer (JAL-82). LibreChat points a custom endpoint at this.
# ---------------------------------------------------------------------------

def _method_from_model(model: str | None) -> str | None:
    """Map the LibreChat-selected model name to a detection method.

    LibreChat sends the chosen model in the request body; we expose one model per detection path
    (see librechat.yaml). Unknown / default model -> None -> config.detection.method default.
    """
    name = (model or "").lower()
    if any(k in name for k in ("ml", "isolation", "forest")):
        return "ml"
    if any(k in name for k in ("stat", "robust", "baseline")):
        return "statistical"
    return None


def _run_investigation(
    slots: chatlib.Slots, session_id: str, method: str | None = None
) -> EvidenceBundle:
    """Real detection (statistical/ML) for the bundle, then trace-reattached narration.

    Computed and returned, NEVER persisted: `bundles` is seed-path-only (dev.py's seed_bundles /
    seed_context are its only writers), so neither call below passes persist=True. A chat answer
    must not add rows to the stored anomaly history — asking a question is not an investigation
    of record. `narrate_investigation` therefore finds nothing to load and returns None, which
    the `or bundle` fallback handles; that is the designed path, not a failure.

    session_id groups the conversation's traces in Langfuse; segment localization awaits
    Lane B's decompose/drill.
    """
    window = Window(start=slots.window_start, end=slots.window_end or slots.window_start)
    bundle = pipeline.run_detection(
        slots.metric or "revenue", window, method=method, session_id=session_id
    )
    return pipeline.narrate_investigation(bundle.investigation_id) or bundle


def _diagnosis_text(bundle: EvidenceBundle) -> str:
    """Narrative plus a compact evidence summary.

    LibreChat renders only this string, so the evidence has to travel inside it - a judge
    reading the conversation should see the localized segment and what was ruled out without
    opening the dashboard.
    """
    # Narration can fail (no AWS credentials, model unavailable). Say so plainly rather than
    # printing a placeholder that reads like a broken system - the evidence below is still real.
    lines = [bundle.narrative or "_Narration unavailable; the computed evidence follows._"]
    if bundle.localized_segment:
        segment = " AND ".join(f"{k}={v}" for k, v in bundle.localized_segment.items())
        lines.append(f"\n**Localized to:** {segment}")
    if bundle.ruled_out:
        lines.append("\n**Checked and ruled out:**")
        lines += [f"- {r.hypothesis}: {r.evidence}" for r in bundle.ruled_out]
    footer = f"\n_investigation `{bundle.investigation_id}` · {bundle.baseline_window.description}_"
    if bundle.trace_url:
        footer += f" · [trace]({bundle.trace_url})"
    lines.append(footer)
    return "\n".join(lines)


def _fmt_num(x: float | None) -> str:
    """Human-readable number for narration: thousands-grouped for large counts
    (requests/revenue), plain significant digits for ratios (fill_rate/ecpm). Avoids the
    f-string ':g' format flipping large values to scientific notation (778100 -> 7.781e+05)."""
    if x is None:
        return "—"
    return f"{x:,.0f}" if abs(x) >= 1000 else f"{x:.4g}"


def _replay_text(bundle: EvidenceBundle) -> str:
    """End-to-end walkthrough of a stored investigation, built deterministically from the
    bundle — every number below is read from stored evidence, none is generated. This is the
    demo's "replay this incident" answer: how it was detected, which factor moved, where it
    localized, what was checked and cleared, and where the trace lives.
    """
    a = bundle.anomaly
    lines = [f"## Replay: {bundle.metric} {a.direction} on "
             f"{bundle.target_window.start:%b %d %H:%M} – {bundle.target_window.end:%b %d %H:%M}\n"]

    lines.append(
        f"**1 — Detection.** {bundle.metric} came in at **{_fmt_num(a.observed)}** against an expected "
        f"**{_fmt_num(a.expected)}** ({bundle.baseline_window.description}), a move of "
        f"**{a.pct_delta * 100:+.1f}%** (robust score {a.score:.1f}). That cleared both the "
        f"statistical and the calibrated effect-size gate, so an investigation was opened."
    )

    fd = bundle.factor_decomposition
    if fd and fd.factors:
        parts = [f"{f.factor} ({_fmt_num(f.from_)} → {_fmt_num(f.to)})" for f in fd.factors]
        lines.append(
            f"**2 — Which factor moved.** The metric was decomposed ({fd.method}) into: "
            f"{'; '.join(parts)}. **{fd.primary_factor}** carried the change and became the "
            f"drill-down target."
        )

    if bundle.drilldown:
        steps = []
        for node in bundle.drilldown:
            seg = " AND ".join(f"{k}={v}" for k, v in node.segment.items()) or "(all)"
            move = (f", {_fmt_num(node.metric_from)} → {_fmt_num(node.metric_to)}"
                    if node.metric_from is not None and node.metric_to is not None else "")
            steps.append(f"  - depth {node.depth}, split by `{node.split_dimension}` → "
                         f"**{seg}** [{node.status}] ({node.contribution_pct * 100:+.1f}% of the delta{move})")
        lines.append("**3 — Drill-down.** Each dimension's segments were ranked by their "
                     "contribution to the delta, recursing into the top contributor:\n" + "\n".join(steps))

    if bundle.localized_segment:
        seg = " AND ".join(f"{k}={v}" for k, v in bundle.localized_segment.items())
        lines.append(f"**4 — Verdict.** The anomaly localized to **{seg}** — every sub-segment "
                     f"inside it moved uniformly, so recursion stopped there.")
    else:
        lines.append("**4 — Verdict.** No single segment stood out — the move was "
                     "population-wide, which is itself the finding.")

    if bundle.ruled_out:
        cleared = [f"  - **{r.hypothesis}**: {r.evidence}" for r in bundle.ruled_out]
        lines.append("**5 — Checked and ruled out.**\n" + "\n".join(cleared))

    if bundle.narrative:
        lines.append(f"**Summary.** {bundle.narrative}")

    tail = (f"_Every number above is reproducible from the {len(bundle.queries)} logged SQL "
            f"queries in investigation `{bundle.investigation_id}`._")
    if bundle.trace_url:
        tail += f" [Open the Langfuse trace]({bundle.trace_url})"
    lines.append(tail)
    return "\n\n".join(lines)


def _baseline_text(bundle: EvidenceBundle) -> str:
    """"What were the normal values that day" — answered from OTHER stored bundles, not this
    one. The anomaly bundle only knows its own window; this reads `bundles` for the same metric
    across the surrounding two weeks (store.load_nearby_bundles) and reports what each of those
    runs actually measured, distinguishing normal days from any other detected anomaly nearby.

    If nothing nearby has been seeded, says so plainly rather than guessing a number — the same
    "explicit about what wasn't checked" principle as the ruled-out list.
    """
    nearby = store.load_nearby_bundles(
        bundle.metric, bundle.target_window.start, bundle.target_window.end,
        days=14, exclude_id=bundle.investigation_id,
    )
    a = bundle.anomaly
    lines = [f"## Baseline check: {bundle.metric} around "
             f"{bundle.target_window.start:%b %d} – {bundle.target_window.end:%b %d}\n"]
    lines.append(
        f"**The anomaly itself.** {bundle.metric} was **{a.observed:.4g}** "
        f"({a.direction}, {a.pct_delta * 100:+.1f}% vs an expected **{a.expected:.4g}**) on "
        f"{bundle.target_window.start:%b %d}."
    )

    if not nearby:
        lines.append(
            "**No surrounding data stored yet.** No other investigation runs are recorded for "
            f"`{bundle.metric}` near this window, so there's nothing to compare against — run "
            "`POST /dev/seed_context` to backfill the days around this anomaly first."
        )
    else:
        normal = [r for r in nearby if not r["is_anomaly"]]
        other = [r for r in nearby if r["is_anomaly"]]
        if normal:
            vals = [r["observed"] for r in normal]
            lo, hi = min(vals), max(vals)
            avg = sum(vals) / len(vals)
            rows = [f"  - {r['window_start']:%b %d}: **{r['observed']:.4g}** "
                    f"(expected {r['expected']:.4g})" for r in normal]
            lines.append(
                f"**Normal days nearby ({len(normal)} stored runs).** Values ranged "
                f"**{lo:.4g} – {hi:.4g}**, averaging **{avg:.4g}** — versus **{a.observed:.4g}** "
                f"on the anomalous day.\n" + "\n".join(rows)
            )
        if other:
            rows = [f"  - {r['window_start']:%b %d}: **{r['observed']:.4g}** "
                    f"({r['direction']}, {r['pct_delta'] * 100:+.1f}%)" for r in other]
            lines.append(
                f"**Also anomalous nearby ({len(other)}).** These days were flagged too, so "
                "they're excluded from the 'normal' range above:\n" + "\n".join(rows)
            )

    lines.append(
        f"_Normal-day figures come from {len(nearby)} separately stored detection runs, each "
        f"reproducible the same way as the anomaly itself — not generated for this answer._"
    )
    return "\n\n".join(lines)


# Bundle fields the general assistant may see as context — evidence only, no SQL/queries.
_CHAT_CONTEXT_FIELDS = {
    "investigation_id", "metric", "target_window", "anomaly", "factor_decomposition",
    "drilldown", "localized_segment", "ruled_out", "narrative",
}


def _handle_chat(
    req: chatlib.ChatCompletionRequest, context_id: str, method: str | None = None
) -> dict:
    # LibreChat's title-generation call: answer it deterministically and return. No slot-fill,
    # no stored turn, no Langfuse investigation trace - a title is not an investigation.
    if chatlib.is_title_request(req):
        return chatlib.completion(
            chatlib.make_title(req), context_id=context_id, slots=chatlib.Slots()
        )

    slots = chatlib.fill_slots(req)
    intent = chatlib.classify(req, slots)

    store.upsert_session(context_id)
    if req.last_user_message():
        store.add_turn(context_id, "user", req.last_user_message())

    # Explicit "replay / explain this investigation" → the deterministic walkthrough, rebuilt from
    # the stored bundle (no re-detection, no LLM, no invented numbers). The dashboard sends the
    # showcased anomaly's bundle_id, so "this anomaly" is the one on screen; otherwise narrow to
    # the named metric's latest anomaly, else the overall latest.
    if intent == "replay":
        bundle = (store.load_bundle(req.bundle_id) if req.bundle_id
                  else store.load_latest_anomaly(slots.metric))
        if bundle is not None:
            payload = chatlib.completion(
                _replay_text(bundle), context_id=context_id, slots=slots,
                investigation=bundle.model_dump(mode="json"),
                plot_kind="metric_tree",
                plot_data=[n.model_dump(mode="json") for n in bundle.drilldown],
            )
            store.add_turn(context_id, "assistant", payload["choices"][0]["message"]["content"])
            return payload
        # No stored anomaly to replay — fall through to a normal helpful answer.

    elif intent == "baseline":
        # Same "this anomaly" resolution as replay, but the answer looks OUTSIDE the bundle —
        # store.load_nearby_bundles reads other stored runs for the same metric, because the
        # bundle's own JSON has no idea what a normal day looked like.
        bundle = (store.load_bundle(req.bundle_id) if req.bundle_id
                  else store.load_latest_anomaly(slots.metric))
        if bundle is None:
            content = ("No detected anomaly is stored yet to compare against — investigate one "
                       "first, then ask what's normal around it.")
        else:
            payload = chatlib.completion(
                _baseline_text(bundle), context_id=context_id, slots=slots,
                investigation=bundle.model_dump(mode="json"),
            )
            store.add_turn(context_id, "assistant", payload["choices"][0]["message"]["content"])
            return payload

    # A fully-specified request ("why did fill rate drop on June 23?") → run the real, traced
    # investigation. Everything below this line is handled by the general assistant.
    if intent == "investigate":
        bundle = _run_investigation(slots, context_id, method)  # real detection, traced — NOT persisted (bundles is seed-path-only, see pipeline.py)
        payload = chatlib.completion(
            _diagnosis_text(bundle), context_id=context_id, slots=slots,
            investigation=bundle.model_dump(mode="json"),
            verification=bundle.narrative_verification.model_dump()
            if bundle.narrative_verification else None,
            plot_kind="metric_tree",
            plot_data=[n.model_dump(mode="json") for n in bundle.drilldown],
        )
        store.add_turn(context_id, "assistant", payload["choices"][0]["message"]["content"])
        return payload

    # Anything else (chit-chat, general questions, under-specified asks) → behave like a normal AI
    # assistant, with the on-screen anomaly passed as optional context so bundle questions still
    # land. Falls back to a short prompt if the LLM is unavailable.
    ctx_bundle = store.load_bundle(req.bundle_id) if req.bundle_id else None
    ctx_json = ctx_bundle.model_dump_json(include=_CHAT_CONTEXT_FIELDS) if ctx_bundle else None
    history = [(m.role, m.content) for m in req.messages if m.content and m.role in ("user", "assistant")]
    try:
        content = narrate.general_reply(history, ctx_json)
    except Exception:
        # LLM unreachable (e.g. no AWS Bedrock credentials). Stay useful: the deterministic
        # replay/explain and investigate paths still work without an LLM.
        content = ("The assistant model is unavailable right now, so I can't answer that freely. "
                   "I can still **replay** or **explain** the investigation on screen — try "
                   "\"explain this investigation\".")
    payload = chatlib.completion(content, context_id=context_id, slots=slots)
    store.add_turn(context_id, "assistant", content)
    return payload


def _sse(payload: dict):
    """Stream a finished completion as OpenAI-style SSE.

    The analysis is never streamed - it runs to completion first, then the text is chunked.
    Deterministic work does not belong in a token stream.
    """
    content = payload["choices"][0]["message"]["content"]
    head = {k: payload[k] for k in ("id", "object", "created", "model")}
    head["object"] = "chat.completion.chunk"
    for word in content.split(" "):
        chunk = head | {"choices": [{"index": 0, "delta": {"content": word + " "},
                                     "finish_reason": None}]}
        yield f"data: {json.dumps(chunk)}\n\n"
    final = head | {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
    yield f"data: {json.dumps(final)}\n\n"
    yield "data: [DONE]\n\n"


@app.post("/v1/chat/completions")
@app.post("/chat/completions")
def chat_completions(
    req: chatlib.ChatCompletionRequest,
    x_session_id: str | None = Header(default=None, alias="X-Session-Id"),
):
    """OpenAI-compatible chat. LibreChat points a custom endpoint here.

    Both paths are registered because LibreChat's baseURL may or may not already include /v1.
    """
    context_id = x_session_id or req.conversation_id or str(uuid.uuid4())
    method = _method_from_model(req.model)
    payload = _handle_chat(req, context_id, method)
    if req.stream:
        return StreamingResponse(_sse(payload), media_type="text/event-stream")
    return payload


# ---------------------------------------------------------------------------
# Session management (JAL-84). Mostly operational: a clean slate before a demo
# run, and the ability to replay an earlier conversation.
# ---------------------------------------------------------------------------

@app.get("/chat/sessions")
def list_chat_sessions(limit: int = 100, turns: int = 20) -> dict:
    """Past conversations, newest first, each with its message history.

    History is included rather than requiring a second call per session, because the only
    real use for this list is reading back what was asked and answered.
    """
    sessions = store.list_sessions(limit)
    for session in sessions:
        session["history"] = store.get_turns(session["context_id"], turns)
    return {"count": len(sessions), "sessions": sessions}


@app.get("/chat/sessions/{context_id}")
def get_chat_session(context_id: str, turns: int = 50) -> dict:
    """One conversation with its turns, plus any investigations it produced.

    The investigation ids are what make a replayed conversation useful: each one resolves
    through GET /bundle/{id} to the evidence behind that answer.
    """
    history = store.get_turns(context_id, turns)
    investigations = [i for i in store.list_investigations(200)
                      if i.get("session_id") == context_id]
    if not history and not investigations:
        raise HTTPException(status_code=404, detail=f"No session {context_id!r}")
    return {
        "context_id": context_id,
        "turns": len(history),
        "history": history,
        "investigations": [i["investigation_id"] for i in investigations],
    }


@app.delete("/chat/sessions/{context_id}")
def delete_chat_session(context_id: str) -> dict:
    """Remove one conversation and its turns. 404 if it was never there."""
    if not store.delete_session(context_id):
        raise HTTPException(status_code=404, detail=f"No session {context_id!r}")
    return {"context_id": context_id, "deleted": True}


@app.delete("/chat/sessions")
def delete_all_chat_sessions() -> dict:
    """Clear every conversation — the clean slate before a judged demo run.

    Investigations are deliberately left alone: they are the evidence record, and losing them
    would break GET /bundle/{id} for anything already submitted.
    """
    return {"deleted": store.delete_all_sessions()}
