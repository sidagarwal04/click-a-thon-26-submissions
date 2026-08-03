"""REST endpoints for the React dashboard + chat proxy (ENGINEERING.md §4.2 `api.py`, §6.3).

Thin SELECTs over `meta.*` + `atlys.event_log` — the dashboard's read path and
the spec-upload path (drag-drop → Atlys/specs/<feature>/).

Also exposes:
  POST /api/proxy/chat   — streaming proxy to LibreChat's Agents API; auto-injects
                           the agent_id so the React shell never needs to know it.
  GET  /api/agent-status — health check for the provisioned agent.
  /api/conversations*    — Atlys-owned chat history (docs/chat-history-plan.md Option B).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, AsyncGenerator

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from .chat_runs import chat_runs
from .chat_store import ChatStore, is_valid_id, new_conversation_id
from .schema import _slug

log = logging.getLogger("atlys.api")

router = APIRouter(prefix="/api", tags=["dashboard"])

# Hackathon-safe caps — enough for the unseen spec, not enough to OOM the box.
MAX_SPEC_BYTES = 1_048_576       # 1 MiB markdown
MAX_EVENTS_BYTES = 10_485_760    # 10 MiB NDJSON
MAX_EVENT_LINES = 100_000


def _check_store():
    from .app import app_state  # noqa: PLC0415
    if app_state is None:
        raise HTTPException(503, "Service not yet initialized — try again in a moment.")
    return app_state


def _rest_span(state, name: str, **meta):
    """Wrap a dashboard read in a tracer span (plan §4.4) — never breaks the request."""
    tracer = getattr(state, "tracer", None)
    if tracer is None:
        import contextlib
        return contextlib.nullcontext()
    try:
        return tracer.span(f"rest:{name}", **meta)
    except Exception:  # noqa: BLE001
        import contextlib
        return contextlib.nullcontext()


def _newest_created(rows: list[dict]) -> str:
    """Newest created_at across rows (for the X-Atlys-Updated change-detection header)."""
    newest = None
    for r in rows:
        ts = r.get("created_at")
        if ts is not None and (newest is None or str(ts) > str(newest)):
            newest = ts
    return str(newest) if newest is not None else ""


def _chat_store() -> ChatStore:
    """Resolve chat store even when ClickHouse/app_state is still warming up."""
    try:
        state = _check_store()
        root = state.settings.generated_dir / "chats"
    except HTTPException:
        from .settings import Settings as _Settings  # noqa: PLC0415
        root = _Settings().generated_dir / "chats"
    return ChatStore(root)


def _read_insights(store) -> list[dict]:
    rows = store.query_rows(
        "SELECT spec, title, summary, confidence, evidence, trace_id, created_at "
        "FROM meta.insights ORDER BY created_at DESC"
    )
    out = []
    for r in rows:
        out.append({
            "spec": r["spec"], "title": r["title"], "summary": r["summary"],
            "confidence": r["confidence"],
            "evidence": json.loads(r["evidence"]) if r["evidence"] else [],
            "trace_id": r["trace_id"], "created_at": str(r["created_at"]),
        })
    return out


@router.get("/insights")
def list_insights():
    return _read_insights(_check_store().store)


@router.get("/insights/{feature}")
def get_insight(feature: str):
    store = _check_store().store
    rows = store.query_rows(
        "SELECT spec, title, summary, confidence, evidence, trace_id, created_at "
        "FROM meta.insights WHERE spec LIKE {f:String} ORDER BY created_at DESC LIMIT 1",
        {"f": f"%{feature}%"},
    )
    if not rows:
        raise HTTPException(404, "no insight for that feature")
    r = rows[0]
    return {
        "spec": r["spec"], "title": r["title"], "summary": r["summary"],
        "confidence": r["confidence"], "evidence": json.loads(r["evidence"]),
        "trace_id": r["trace_id"], "created_at": str(r["created_at"]),
    }


@router.get("/changelog")
def changelog(scope: str = "context", limit: int = 50):
    store = _check_store().store
    if scope == "context":
        rows = store.query_rows(
            "SELECT version, agent, action, object, diff, rationale, trace_id, created_at "
            "FROM meta.context_changelog ORDER BY version DESC LIMIT {n:UInt32}", {"n": limit})
    elif scope == "schema":
        rows = store.query_rows(
            "SELECT version, agent, action, object, diff, rationale, trace_id, created_at "
            "FROM meta.schema_changelog ORDER BY version DESC LIMIT {n:UInt32}", {"n": limit})
    else:
        rows = store.query_rows(
            "SELECT event_id, event_type, aggregate_id, actor, payload, trace_id, created_at "
            "FROM atlys.event_log ORDER BY created_at DESC LIMIT {n:UInt32}", {"n": limit})
    return [dict(r, created_at=str(r["created_at"])) for r in rows]


@router.get("/context")
def context(version: int | None = None):
    store = _check_store().store
    if version:
        rows = store.query_rows(
            "SELECT version, content, content_hash, diff_from_prev, trace_id, created_at "
            "FROM meta.context_snapshots WHERE version = {v:UInt64}", {"v": version})
    else:
        rows = store.query_rows(
            "SELECT version, content, content_hash, diff_from_prev, trace_id, created_at "
            "FROM meta.context_snapshots ORDER BY version DESC LIMIT 1")
    if not rows:
        return {}
    r = rows[0]
    return {"version": r["version"], "content": r["content"], "content_hash": r["content_hash"],
            "diff_from_prev": r["diff_from_prev"], "trace_id": r["trace_id"], "created_at": str(r["created_at"])}


@router.get("/context-versions")
def context_versions():
    store = _check_store().store
    rows = store.query_rows(
        "SELECT version FROM meta.context_snapshots ORDER BY version DESC"
    )
    return [r["version"] for r in rows]



@router.get("/event-log")
def event_log(limit: int = 100, run_id: str | None = None,
              event_type: str | None = None, actor: str | None = None,
              before: str | None = None, after: str | None = None,
              count: int = 0, response: Response = None):
    """Event log with filters + keyset pagination (plan §2.2 A1).

    Bare-array shape is preserved when no new params are passed (backward
    compatible with the pre-Inspect Events tab). When filters are used the
    response is `{events, next_cursor, total}`.
    """
    state = _check_store()
    store = state.store
    limit = max(1, min(int(limit), 500))
    where, params = [], {}
    if event_type:
        where.append("event_type = {et:String}")
        params["et"] = event_type
    if actor:
        where.append("actor = {a:String}")
        params["a"] = actor
    if before:
        where.append("created_at < {bf:DateTime64(3)}")
        params["bf"] = before
    if after:
        where.append("created_at > {af:DateTime64(3)}")
        params["af"] = after

    # run_id → the run's trace_id(s); also match payload-embedded run_id for
    # runs that never got a pending_runs row (plan §2.4 edge case).
    run_trace_ids: list[str] = []
    if run_id:
        rows = store.query_rows(
            "SELECT trace_id FROM meta.pending_runs WHERE run_id = {rid:String}",
            {"rid": run_id},
        )
        run_trace_ids = [r["trace_id"] for r in rows if r.get("trace_id")]
        if run_trace_ids:
            # inline literal list — clickhouse-connect Array params are not
            # portable to the DryRunStore's mini-SQL evaluator
            from .sqlsafe import sql_string_literal  # noqa: PLC0415
            where.append("trace_id IN (" + ", ".join(
                sql_string_literal(t) for t in run_trace_ids
            ) + ")")
        else:
            # fall back to a payload scan (rare) — bounded by the event log TTL
            where.append("payload LIKE {pl:String}")
            params["pl"] = f"%{run_id}%"

    sql = "SELECT event_id, event_type, aggregate_id, version, actor, payload, trace_id, created_at " \
          "FROM atlys.event_log"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT {n:UInt32}"

    with _rest_span(state, "event-log", filters=bool(where), limit=limit):
        rows = store.query_rows(sql, {**params, "n": limit})
        out = []
        for r in rows:
            try:
                payload = json.loads(r["payload"]) if r["payload"] else {}
            except Exception:  # noqa: BLE001
                payload = {}
            out.append({**r, "payload": payload, "created_at": str(r["created_at"])})

    if response is not None:
        response.headers["X-Atlys-Updated"] = _newest_created(rows)

    has_filters = bool(run_id or event_type or actor or before or after)
    if not has_filters and not count:
        return out  # backward-compatible bare array
    total = None
    if count:
        cnt_sql = "SELECT count() AS c FROM atlys.event_log"
        if where:
            cnt_sql += " WHERE " + " AND ".join(where)
        total = int(store.query_rows(cnt_sql, params)[0]["c"])
    next_cursor = str(rows[-1]["created_at"]) if rows else None
    return {"events": out, "next_cursor": next_cursor, "total": total}


@router.get("/runs")
def runs(limit: int = 50, state: str | None = None, response: Response = None):
    """Run registry — one row per spec run, enriched from the event log (A2)."""
    state_obj = _check_store()
    store = state_obj.store
    limit = max(1, min(int(limit), 200))
    where, params = "", {}
    if state:
        where = " WHERE state = {s:String}"
        params["s"] = state

    with _rest_span(state_obj, "runs", run_state=state or "any", limit=limit):
        pending = store.query_rows(
            "SELECT run_id, state, spec_dir, trace_id, created_at FROM meta.pending_runs"
            + where + " ORDER BY created_at DESC LIMIT {n:UInt32}",
            {**params, "n": limit},
        )
        trace_ids = [r["trace_id"] for r in pending if r.get("trace_id")]
        by_trace: dict[str, dict] = {}
        if trace_ids:
            from .sqlsafe import sql_string_literal  # noqa: PLC0415
            ev_rows = store.query_rows(
                "SELECT trace_id, event_type, created_at FROM atlys.event_log "
                "WHERE trace_id IN (" + ", ".join(
                    sql_string_literal(t) for t in trace_ids
                ) + ") ORDER BY created_at ASC"
            )
            for r in ev_rows:
                b = by_trace.setdefault(r["trace_id"], {"events": [], "types": set()})
                b["events"].append(r)
                b["types"].add(r["event_type"])
        insight_titles = {
            r["trace_id"]: r["title"]
            for r in store.query_rows(
                "SELECT trace_id, title FROM meta.insights WHERE trace_id != ''"
            )
        } if trace_ids else {}

        out = []
        for r in pending:
            trace_id = r.get("trace_id") or ""
            bucket = by_trace.get(trace_id) or {"events": [], "types": set()}
            evs = bucket["events"]
            first = evs[0]["created_at"] if evs else None
            last = evs[-1]["created_at"] if evs else None
            duration_ms = None
            if first is not None and last is not None:
                try:
                    duration_ms = int(
                        (last - first).total_seconds() * 1000
                    )
                except Exception:  # noqa: BLE001 — strings in dry-run
                    duration_ms = None
            out.append({
                "run_id": r["run_id"],
                "trace_id": trace_id,
                "spec_dir": r["spec_dir"],
                "state": r["state"],
                "event_types": sorted(bucket["types"]),
                "event_count": len(evs),
                "first_event_at": str(first) if first is not None else None,
                "last_event_at": str(last) if last is not None else None,
                "duration_ms": duration_ms,
                "insight_title": insight_titles.get(trace_id),
                "created_at": str(r["created_at"]),
            })
    if response is not None:
        response.headers["X-Atlys-Updated"] = _newest_created(pending)
    return out


@router.get("/runs/{run_id}")
def get_run(run_id: str, response: Response = None):
    """Full event chain for one run (A3).

    Resolves the run's trace_id via meta.pending_runs; falls back to a payload
    scan when the run never got a pending_runs row (plan §2.4).
    """
    state_obj = _check_store()
    store = state_obj.store
    with _rest_span(state_obj, "run", run_id=run_id):
        pending = store.query_rows(
            "SELECT run_id, state, spec_dir, trace_id, created_at FROM meta.pending_runs "
            "WHERE run_id = {rid:String} ORDER BY created_at DESC LIMIT 1",
            {"rid": run_id},
        )
        trace_id = pending[0].get("trace_id") if pending else None
        if not trace_id:
            hits = store.query_rows(
                "SELECT trace_id FROM atlys.event_log WHERE payload LIKE {pl:String} "
                "AND trace_id != '' ORDER BY created_at DESC LIMIT 1",
                {"pl": f"%{run_id}%"},
            )
            trace_id = hits[0]["trace_id"] if hits else None
        if not trace_id:
            raise HTTPException(404, f"no trace found for run {run_id}")

        chain_rows = store.query_rows(
            "SELECT event_id, event_type, aggregate_id, version, actor, payload, trace_id, created_at "
            "FROM atlys.event_log WHERE trace_id = {t:String} ORDER BY created_at ASC",
            {"t": trace_id},
        )
        chain = []
        for r in chain_rows:
            try:
                payload = json.loads(r["payload"]) if r["payload"] else {}
            except Exception:  # noqa: BLE001
                payload = {}
            chain.append({**r, "payload": payload, "created_at": str(r["created_at"])})

        run_obj = {
            "run_id": run_id,
            "trace_id": trace_id,
            "spec_dir": pending[0].get("spec_dir") if pending else None,
            "state": pending[0].get("state") if pending else "unknown",
            "event_count": len(chain),
            "first_event_at": chain[0]["created_at"] if chain else None,
            "last_event_at": chain[-1]["created_at"] if chain else None,
            "created_at": str(pending[0]["created_at"]) if pending else None,
        }
    if response is not None:
        response.headers["X-Atlys-Updated"] = _newest_created(chain_rows)
    return {"run": run_obj, "chain": chain}


@router.get("/tool-calls")
def tool_calls(limit: int = 100, tool: str | None = None,
               run_id: str | None = None, response: Response = None):
    """tool.called events as a flat PM-readable list (A4)."""
    state_obj = _check_store()
    store = state_obj.store
    limit = max(1, min(int(limit), 500))
    run_trace_ids: list[str] = []
    if run_id:
        rows = store.query_rows(
            "SELECT trace_id FROM meta.pending_runs WHERE run_id = {rid:String}",
            {"rid": run_id},
        )
        run_trace_ids = [r["trace_id"] for r in rows if r.get("trace_id")]

    with _rest_span(state_obj, "tool-calls", tool=tool or "any", limit=limit):
        rows = store.query_rows(
            "SELECT event_id, payload, trace_id, created_at FROM atlys.event_log "
            "WHERE event_type = 'tool.called' ORDER BY created_at DESC LIMIT {n:UInt32}",
            {"n": limit},
        )
        out = []
        for r in rows:
            try:
                payload = json.loads(r["payload"]) if r["payload"] else {}
            except Exception:  # noqa: BLE001
                payload = {}
            name = payload.get("tool") or ""
            if tool and name != tool:
                continue
            if run_id and r.get("trace_id") not in run_trace_ids:
                continue
            out.append({
                "event_id": r["event_id"],
                "tool": name,
                "arguments": payload.get("arguments", {}),
                "trace_id": r.get("trace_id") or "",
                "created_at": str(r["created_at"]),
            })
    if response is not None:
        response.headers["X-Atlys-Updated"] = _newest_created(rows)
    return out


@router.get("/schema-catalog")
def schema_catalog():
    store = _check_store().store
    rows = store.query_rows(
        "SELECT table_name, source_spec, event_order, columns, row_count, trace_id, created_at "
        "FROM meta.schema_catalog ORDER BY created_at DESC")
    out = []
    for r in rows:
        try:
            columns = json.loads(r["columns"]) if r["columns"] else {}
            event_order = json.loads(r["event_order"]) if r["event_order"] else []
        except Exception:  # noqa: BLE001
            columns, event_order = {}, []
        out.append({**r, "columns": columns, "event_order": event_order, "created_at": str(r["created_at"])})
    return out


@router.get("/migrations")
def migrations(table: str | None = None, limit: int = 50):
    """Migration journal — recent plan lifecycle rows (planned/approved/applied/…)."""
    from .migration_journal import list_recent
    store = _check_store().store
    return list_recent(store, table_name=table, limit=limit)


@router.get("/pending-runs")
def pending_runs():
    store = _check_store().store
    rows = store.query_rows(
        "SELECT run_id, state, spec_dir, trace_id, created_at FROM meta.pending_runs ORDER BY created_at DESC")
    return [dict(r, created_at=str(r["created_at"])) for r in rows]


@router.get("/specs")
def list_specs():
    state = _check_store()
    specs_dir = state.settings.specs_dir
    out = []
    if specs_dir.exists():
        for d in sorted(specs_dir.iterdir()):
            if d.is_dir() and (d / "spec.md").exists():
                out.append({
                    "dir": d.name,
                    "feature": _slug(d.name),
                    "has_events": (d / "events.ndjson").exists(),
                })
    return out


async def _read_capped(upload: UploadFile, *, max_bytes: int, label: str) -> bytes:
    """Read an upload with a hard byte cap (avoids OOM on huge drag-drops)."""
    chunks: list[bytes] = []
    total = 0
    while True:
        piece = await upload.read(64 * 1024)
        if not piece:
            break
        total += len(piece)
        if total > max_bytes:
            raise HTTPException(
                413,
                f"{label} exceeds {max_bytes} bytes — shrink the file and retry",
            )
        chunks.append(piece)
    return b"".join(chunks)


@router.post("/specs")
async def upload_spec(spec: UploadFile = File(...), events: UploadFile = File(...),
                      feature: str | None = Form(None)):
    """Drag-drop delivery: writes Atlys/specs/<feature>/spec.md + events.ndjson (§6.3).

    `feature` (optional form field) names the spec dir; if absent we fall back to
    the events filename stem. The chat only ever references the path — spec
    bodies never enter the LLM.
    """
    state = _check_store()
    if not spec.filename or not events.filename:
        raise HTTPException(400, "spec.md and events.ndjson required")

    spec_name = Path(spec.filename).name.lower()
    events_name = Path(events.filename).name.lower()
    if not spec_name.endswith(".md"):
        raise HTTPException(400, "spec file must be a .md")
    if not events_name.endswith(".ndjson"):
        raise HTTPException(400, "events file must be a .ndjson")

    spec_bytes = await _read_capped(spec, max_bytes=MAX_SPEC_BYTES, label="spec.md")
    events_bytes = await _read_capped(events, max_bytes=MAX_EVENTS_BYTES, label="events.ndjson")

    event_lines = sum(1 for line in events_bytes.splitlines() if line.strip())
    if event_lines == 0:
        raise HTTPException(400, "events.ndjson has no non-empty lines")
    if event_lines > MAX_EVENT_LINES:
        raise HTTPException(
            400,
            f"events.ndjson has {event_lines} lines (max {MAX_EVENT_LINES})",
        )

    feature = _slug(feature or Path(events.filename).stem or Path(spec.filename).stem)
    target = state.settings.specs_dir / feature
    target.mkdir(parents=True, exist_ok=True)
    (target / "spec.md").write_bytes(spec_bytes)
    (target / "events.ndjson").write_bytes(events_bytes)
    return {
        "dir": str(target.relative_to(state.settings.atlys_root)),
        "feature": feature,
        "event_lines": event_lines,
        "spec_bytes": len(spec_bytes),
        "events_bytes": len(events_bytes),
    }


# ---------------------------------------------------------------------------
# Chat history (Atlys JSON store — Option B)
# ---------------------------------------------------------------------------

class CreateConversationRequest(BaseModel):
    id: str | None = None


class SaveMessagesRequest(BaseModel):
    messages: list[dict[str, Any]] = Field(default_factory=list)
    # Optional: `idle` | `running`. Omitted → leave existing status unchanged.
    status: str | None = None


@router.post("/conversations", tags=["chat"])
def create_conversation(req: CreateConversationRequest | None = None):
    """Create an empty conversation (or return existing if id already present)."""
    req = req or CreateConversationRequest()
    if req.id is not None and not is_valid_id(req.id):
        raise HTTPException(400, "conversation id must be a UUID")
    try:
        data = _chat_store().create(req.id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {
        "id": data["id"],
        "title": data["title"],
        "createdAt": data["createdAt"],
        "updatedAt": data["updatedAt"],
    }


@router.get("/conversations", tags=["chat"])
def list_conversations(limit: int = 50):
    return _chat_store().list(limit=limit)


@router.get("/conversations/{conversation_id}", tags=["chat"])
def get_conversation(conversation_id: str):
    if not is_valid_id(conversation_id):
        raise HTTPException(400, "conversation id must be a UUID")
    meta = _chat_store().get(conversation_id)
    if meta is None:
        raise HTTPException(404, "conversation not found")
    return meta


@router.get("/conversations/{conversation_id}/messages", tags=["chat"])
def get_conversation_messages(conversation_id: str):
    if not is_valid_id(conversation_id):
        raise HTTPException(400, "conversation id must be a UUID")
    store = _chat_store()
    msgs = store.get_messages(conversation_id)
    if msgs is None:
        raise HTTPException(404, "conversation not found")
    status = store.get_status(conversation_id) or "idle"
    if chat_runs.is_running(conversation_id):
        status = "running"
    return {"id": conversation_id, "messages": msgs, "status": status}


@router.post("/conversations/{conversation_id}/stop", tags=["chat"])
async def stop_conversation(conversation_id: str):
    """Cancel a background generation for this chat (Stop button / navigate away)."""
    if not is_valid_id(conversation_id):
        raise HTTPException(400, "conversation id must be a UUID")
    store = _chat_store()
    stopped = await chat_runs.stop(conversation_id)
    try:
        store.set_status(conversation_id, "idle")
    except Exception:  # noqa: BLE001
        pass
    return {"id": conversation_id, "stopped": stopped, "status": "idle"}


@router.put("/conversations/{conversation_id}/messages", tags=["chat"])
def save_conversation_messages(conversation_id: str, req: SaveMessagesRequest):
    """Replace the transcript for a conversation (creates the file if missing)."""
    if not is_valid_id(conversation_id):
        raise HTTPException(400, "conversation id must be a UUID")
    try:
        return _chat_store().save_messages(
            conversation_id, req.messages, status=req.status,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


# ---------------------------------------------------------------------------
# Chat proxy (D12) — streams LibreChat Agents API with auto-injected agent_id
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    messages: list[dict]
    conversationId: str | None = None
    stream: bool = True
    # True for silent UI auto-continues — keep the same tool-call budget series.
    extendSeries: bool = False


def _get_agent_id() -> str | None:
    """Read agent_id from the settings/file without requiring ClickHouse.

    Falls back to reading .atlys_agent_id directly from the filesystem so this
    works even in dry-run mode (no ClickHouse, no store).
    """
    try:
        state = _check_store()
        return state.settings.load_agent_id()
    except HTTPException:
        raise
    except Exception:
        pass
    # Direct file fallback (no app_state needed)
    from pathlib import Path as _Path
    from .settings import Settings as _Settings
    try:
        return _Settings().load_agent_id()
    except Exception:
        return None


def _get_librechat_api_key() -> str | None:
    """Agents API key for /api/agents/v1/* (login JWTs are not accepted)."""
    try:
        state = _check_store()
        return state.settings.load_librechat_api_key()
    except HTTPException:
        raise
    except Exception:
        pass
    from .settings import Settings as _Settings
    try:
        return _Settings().load_librechat_api_key()
    except Exception:
        return None


@router.post("/proxy/chat", tags=["chat"])
async def proxy_chat(req: ChatRequest, request: Request):
    """Streaming proxy → LibreChat Agents API.

    Injects `agent_id` automatically. The LibreChat upstream runs as a
    background task so a browser reload does not cancel the agent — the UI
    can poll `/conversations/{id}/messages` for the latest transcript.
    """
    import asyncio

    agent_id = _get_agent_id()
    if not agent_id:
        raise HTTPException(
            503,
            "Atlys PM agent not yet provisioned. Run scripts/provision_agent.py "
            "or wait for the service startup hook to complete.",
        )

    state = _check_store()
    librechat_url = state.settings.librechat_url.rstrip("/")
    tool_limit = int(state.settings.max_tool_calls_per_series)
    store = _chat_store()

    conversation_id = req.conversationId
    if conversation_id and not is_valid_id(conversation_id):
        raise HTTPException(400, "conversationId must be a UUID")
    if not conversation_id:
        conversation_id = new_conversation_id()
    try:
        store.create(conversation_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    if chat_runs.is_running(conversation_id):
        raise HTTPException(
            409,
            "This chat is already generating. Wait for it to finish or press Stop.",
        )

    # /api/agents/v1/chat/completions requires an Agents API key (not a login JWT).
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1]
    if not token:
        token = _get_librechat_api_key()
    if not token:
        raise HTTPException(
            503,
            "LibreChat Agents API key not provisioned. Ensure interface.remoteAgents "
            "is enabled and re-run scripts/provision_agent.py (or restart fastapi).",
        )

    payload = {
        "model": agent_id,
        "agentId": agent_id,
        "agent_id": agent_id,
        "messages": req.messages,
        "stream": req.stream,
        "conversationId": conversation_id,
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Authorization": f"Bearer {token}",
    }

    url = f"{librechat_url}/api/agents/v1/chat/completions"

    def _mark_idle() -> None:
        try:
            store.set_status(conversation_id, "idle")
        except Exception:  # noqa: BLE001
            pass

    # Open upstream before StreamingResponse so 4xx/5xx become HTTP errors.
    client = httpx.AsyncClient(timeout=120)
    try:
        req_obj = client.build_request("POST", url, json=payload, headers=headers)
        resp = await client.send(req_obj, stream=True)
        if resp.status_code >= 400:
            body = await resp.aread()
            await resp.aclose()
            await client.aclose()
            log.error(
                "LibreChat proxy failed with status %s: %s",
                resp.status_code, body.decode(errors="replace"),
            )
            raise HTTPException(resp.status_code, body.decode(errors="replace"))
    except HTTPException:
        raise
    except Exception:
        await client.aclose()
        raise

    # Mark running only after upstream accepted the request.
    try:
        store.set_status(conversation_id, "running")
    except Exception:  # noqa: BLE001
        pass

    try:
        run = await chat_runs.start(
            conversation_id,
            client=client,
            resp=resp,
            store=store,
            tool_limit=tool_limit,
            extend_series=bool(req.extendSeries),
        )
    except RuntimeError as e:
        await resp.aclose()
        await client.aclose()
        _mark_idle()
        raise HTTPException(409, str(e)) from e
    except Exception:
        await resp.aclose()
        await client.aclose()
        _mark_idle()
        raise

    async def generator() -> AsyncGenerator[bytes, None]:
        """Fan-out subscriber. Client disconnect must NOT cancel the run."""
        q = run.subscribe()
        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    if run.done:
                        break
                    yield b": subscriber-keepalive\n\n"
                    continue
                if chunk is None:
                    break
                yield chunk
        except asyncio.CancelledError:
            # Browser navigated away / reloaded — leave background run alone.
            log.info(
                "chat SSE subscriber cancelled (conversationId=%s); run continues",
                conversation_id,
            )
            raise
        finally:
            run.unsubscribe(q)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Conversation-Id": conversation_id,
        },
    )


@router.get("/documents/metadata", tags=["documents"])
def get_document_metadata(path: str):
    """Get metadata for a document in the Atlys root workspace."""
    state = _check_store()
    root = state.settings.atlys_root
    target = (root / path).resolve()
    
    # Path traversal validation
    try:
        target.relative_to(root)
    except ValueError:
        raise HTTPException(403, "Access denied")
        
    if not target.exists() or not target.is_file():
        return {"exists": False}
        
    return {
        "exists": True,
        "name": target.name,
        "size": target.stat().st_size,
        "extension": target.suffix.lower(),
        "path": path,
    }


@router.get("/documents/content", tags=["documents"])
def get_document_content(path: str):
    """Get content for a document in the Atlys root workspace."""
    state = _check_store()
    root = state.settings.atlys_root
    target = (root / path).resolve()
    
    try:
        target.relative_to(root)
    except ValueError:
        raise HTTPException(403, "Access denied")
        
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "File not found")
        
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(500, f"Failed to read file: {e}")
        
    return {"name": target.name, "content": content, "path": path}


@router.get("/documents/download", tags=["documents"])
def download_document(path: str):
    """Download a document from the Atlys root workspace."""
    state = _check_store()
    root = state.settings.atlys_root
    target = (root / path).resolve()
    
    try:
        target.relative_to(root)
    except ValueError:
        raise HTTPException(403, "Access denied")
        
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "File not found")
        
    return FileResponse(target, media_type="application/octet-stream", filename=target.name)


@router.get("/agent-status", tags=["chat"])
def agent_status():
    """Returns provisioning status so the UI can show a ready indicator."""
    state = _check_store()
    agent_id = state.settings.load_agent_id()
    return {
        "provisioned": agent_id is not None,
        "agent_id": agent_id,
        "agent_name": "Atlys PM" if agent_id else None,
        "librechat_url": state.settings.librechat_url,
        "langfuse_base_url": state.settings.langfuse_base_url or "https://us.cloud.langfuse.com",
        "langfuse_project_id": state.settings.langfuse_project_id,
        "max_tool_calls_per_series": state.settings.max_tool_calls_per_series,
        # Matches librechat.yaml tokenConfig for glm-5.2 — UI context-usage gauge.
        "context_window": 1_000_000,
    }
