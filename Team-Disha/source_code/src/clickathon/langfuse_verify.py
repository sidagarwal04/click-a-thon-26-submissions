"""Pull Langfuse sessions/traces for LibreChat verification."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from clickathon.config import get_settings
from clickathon.telemetry import flush_telemetry, get_langfuse, init_telemetry


def _to_plain(obj: Any) -> Any:
    if obj is None:
        return None
    if hasattr(obj, "dict"):
        try:
            return obj.dict()
        except Exception:  # noqa: BLE001
            pass
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:  # noqa: BLE001
            pass
    if isinstance(obj, (list, tuple)):
        return [_to_plain(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def _trim_str(s: Any, limit: int = 800) -> Any:
    if not isinstance(s, str):
        return s
    if len(s) <= limit:
        return s
    return s[:limit] + f"…[+{len(s) - limit} chars]"


def _summarize_trace(tr: dict[str, Any]) -> dict[str, Any]:
    tools: list[str] = []
    inp = tr.get("input")
    out = tr.get("output")
    # LibreChat AgentRun packs tool calls in langchain messages
    for blob in (out, inp):
        if not isinstance(blob, dict):
            continue
        msgs = blob.get("messages") or []
        for m in msgs:
            kwargs = (m.get("kwargs") if isinstance(m, dict) else None) or {}
            name = kwargs.get("name")
            if name and kwargs.get("tool_call_id"):
                tools.append(str(name))
            for tc in kwargs.get("tool_calls") or []:
                n = tc.get("name") or ((tc.get("function") or {}).get("name"))
                if n:
                    tools.append(str(n))
    # Dedupe preserving order
    seen: set[str] = set()
    tools_u = []
    for t in tools:
        if t not in seen:
            seen.add(t)
            tools_u.append(t)

    return {
        "id": tr.get("id"),
        "name": tr.get("name"),
        "timestamp": tr.get("timestamp") or tr.get("createdAt"),
        "session_id": tr.get("sessionId"),
        "user_id": tr.get("userId"),
        "tags": tr.get("tags") or [],
        "latency": tr.get("latency"),
        "tool_calls_seen": tools_u,
        "html_path": tr.get("htmlPath"),
    }


def _extract_sql_from_obs(obs: dict[str, Any]) -> dict[str, Any] | None:
    name = str(obs.get("name") or "")
    if "clickhouse" not in name.lower() and "query" not in name.lower():
        # still allow explicit clickhouse.query
        if name != "clickhouse.query":
            meta = obs.get("metadata") or {}
            attrs = meta.get("attributes") if isinstance(meta, dict) else {}
            if not (isinstance(attrs, dict) and attrs.get("db.system") == "clickhouse"):
                return None
    inp = obs.get("input") or {}
    out = obs.get("output") or {}
    if isinstance(inp, str):
        try:
            inp = json.loads(inp)
        except json.JSONDecodeError:
            inp = {"raw": inp}
    if isinstance(out, str):
        try:
            out = json.loads(out)
        except json.JSONDecodeError:
            out = {"raw": out}
    return {
        "observation_id": obs.get("id"),
        "trace_id": obs.get("traceId"),
        "name": name,
        "start_time": obs.get("startTime"),
        "latency": obs.get("latency"),
        "sql": _trim_str((inp or {}).get("sql") if isinstance(inp, dict) else None, 2000),
        "parameters": (inp or {}).get("parameters") if isinstance(inp, dict) else None,
        "n_rows": (out or {}).get("n_rows") if isinstance(out, dict) else None,
        "duration_ms": (out or {}).get("duration_ms") if isinstance(out, dict) else None,
        "database": (inp or {}).get("database")
        if isinstance(inp, dict)
        else (out or {}).get("database") if isinstance(out, dict) else None,
        "error": (out or {}).get("error") if isinstance(out, dict) else None,
    }


def list_langfuse_sessions(*, limit: int = 10) -> dict[str, Any]:
    init_telemetry()
    lf = get_langfuse()
    if lf is None:
        return {"error": "Langfuse not configured (LANGFUSE_PUBLIC_KEY / SECRET_KEY)"}
    settings = get_settings()
    resp = lf.api.sessions.list(limit=min(max(limit, 1), 50))
    data = _to_plain(getattr(resp, "data", []) or [])
    return {
        "host": settings.langfuse_base_url,
        "count": len(data),
        "sessions": [
            {
                "id": s.get("id"),
                "created_at": s.get("createdAt") or s.get("created_at"),
                "environment": s.get("environment"),
            }
            for s in data
        ],
        "note": (
            "LibreChat conversation thread_id is typically the Langfuse session id. "
            "Pass an id to get_langfuse_session for full verification."
        ),
    }


def get_langfuse_session(session_id: str, *, include_sql: bool = True) -> dict[str, Any]:
    """Fetch a Langfuse session (LibreChat thread) and summarize tools + SQL queries."""
    init_telemetry()
    lf = get_langfuse()
    if lf is None:
        return {"error": "Langfuse not configured (LANGFUSE_PUBLIC_KEY / SECRET_KEY)"}
    if not (session_id or "").strip():
        return {"error": "session_id required", "hint": list_langfuse_sessions(limit=5)}

    settings = get_settings()
    sid = session_id.strip()
    sess = _to_plain(lf.api.sessions.get(sid))
    traces_raw = sess.get("traces") or []
    traces = [_summarize_trace(t if isinstance(t, dict) else _to_plain(t)) for t in traces_raw]

    sql_queries: list[dict[str, Any]] = []
    tool_obs: list[dict[str, Any]] = []
    if include_sql:
        # Pull full observations for each trace id
        for tr in traces_raw:
            tid = tr.get("id") if isinstance(tr, dict) else getattr(tr, "id", None)
            if not tid:
                continue
            try:
                full = _to_plain(lf.api.trace.get(tid))
            except Exception as exc:  # noqa: BLE001
                tool_obs.append({"trace_id": tid, "error": str(exc)})
                continue
            for obs in full.get("observations") or []:
                o = obs if isinstance(obs, dict) else _to_plain(obs)
                sql = _extract_sql_from_obs(o)
                if sql:
                    sql_queries.append(sql)
                if str(o.get("type") or "").upper() in {"TOOL", "SPAN"} and o.get("name"):
                    tool_obs.append(
                        {
                            "trace_id": tid,
                            "name": o.get("name"),
                            "type": o.get("type"),
                            "latency": o.get("latency"),
                            "input": _trim_str(json.dumps(o.get("input"), default=str) if o.get("input") is not None else None, 400),
                            "output": _trim_str(json.dumps(o.get("output"), default=str) if o.get("output") is not None else None, 400),
                        }
                    )

        # Also scan recent RCA clickhouse.query observations (may be separate MCP traces)
        sql_queries.extend(_recent_clickhouse_queries(lf, limit=30, minutes=120).get("queries") or [])
        # de-dupe by observation_id
        seen: set[str] = set()
        deduped = []
        for q in sql_queries:
            oid = str(q.get("observation_id") or "")
            if oid and oid in seen:
                continue
            if oid:
                seen.add(oid)
            deduped.append(q)
        sql_queries = deduped

    flush_telemetry()
    all_tools = []
    for t in traces:
        all_tools.extend(t.get("tool_calls_seen") or [])
    tools_unique = list(dict.fromkeys(all_tools))

    return {
        "host": settings.langfuse_base_url,
        "session_id": sid,
        "created_at": sess.get("createdAt"),
        "project_id": sess.get("projectId"),
        "trace_count": len(traces),
        "traces": traces,
        "tools_called": tools_unique,
        "clickhouse_queries": sql_queries,
        "observations_sample": tool_obs[:40],
        "verification": {
            "has_agent_run": any(t.get("name") == "AgentRun" for t in traces),
            "has_tool_calls": bool(tools_unique),
            "has_clickhouse_sql": bool(sql_queries),
            "sql_query_count": len(sql_queries),
            "checklist": [
                "Confirm tools_called includes list_all_anomalies / investigate_day / drill_* as expected",
                "Confirm clickhouse_queries SQL matches rca_* or ad_events (no invented numbers)",
                "Open session in Langfuse UI via project sessions page",
            ],
        },
        "ui_hint": f"{settings.langfuse_base_url.rstrip('/')}/project/{sess.get('projectId')}/sessions/{sid}",
    }


def _recent_clickhouse_queries(lf: Any, *, limit: int = 20, minutes: int = 60) -> dict[str, Any]:
    """List recent observations that look like ClickHouse query spans."""
    queries: list[dict[str, Any]] = []
    try:
        try:
            resp = lf.api.observations.get_many(
                name="clickhouse.query",
                limit=min(limit, 100),
                fields="core,basic,io",
            )
        except TypeError:
            resp = lf.api.observations.get_many(
                name="clickhouse.query",
                limit=min(limit, 100),
            )
        except Exception:
            try:
                resp = lf.api.observations.get_many(
                    limit=min(max(limit * 5, 20), 100),
                    fields="core,basic,io",
                )
            except Exception:
                resp = lf.api.observations.get_many(limit=min(max(limit * 5, 20), 100))
        rows = _to_plain(getattr(resp, "data", []) or [])
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=max(minutes, 1))
        for o in rows:
            start = o.get("startTime")
            if isinstance(start, str):
                try:
                    start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                except ValueError:
                    start_dt = None
            elif isinstance(start, datetime):
                start_dt = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
            else:
                start_dt = None
            if start_dt and start_dt < cutoff:
                continue
            sql = _extract_sql_from_obs(o)
            if sql:
                queries.append(sql)
            elif str(o.get("name") or "") == "clickhouse.query":
                queries.append(
                    {
                        "observation_id": o.get("id"),
                        "trace_id": o.get("traceId"),
                        "name": o.get("name"),
                        "start_time": o.get("startTime"),
                        "latency": o.get("latency"),
                        "sql": _trim_str(o.get("input"), 2000),
                        "n_rows": None,
                    }
                )
            if len(queries) >= limit:
                break
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "queries": []}
    return {"queries": queries[:limit]}


def list_langfuse_clickhouse_queries(*, limit: int = 20, minutes: int = 60) -> dict[str, Any]:
    init_telemetry()
    lf = get_langfuse()
    if lf is None:
        return {"error": "Langfuse not configured"}
    settings = get_settings()
    out = _recent_clickhouse_queries(lf, limit=limit, minutes=minutes)
    flush_telemetry()
    return {
        "host": settings.langfuse_base_url,
        "minutes": minutes,
        "count": len(out.get("queries") or []),
        **out,
        "note": "Spans named clickhouse.query are emitted by the RCA ClickHouse client.",
    }


def _message_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return str(content)


def _parse_agent_run(tr: dict[str, Any]) -> dict[str, Any]:
    """Extract user question, tool calls, and final assistant text from an AgentRun trace."""
    user_q = ""
    final_answer = ""
    tool_steps: list[dict[str, Any]] = []
    out = tr.get("output") if isinstance(tr.get("output"), dict) else {}
    msgs = out.get("messages") or []
    for m in msgs:
        if not isinstance(m, dict):
            continue
        kwargs = m.get("kwargs") or {}
        mid = m.get("id") or []
        if isinstance(mid, list) and any("HumanMessage" in str(x) for x in mid):
            text = _message_text(kwargs.get("content"))
            if text and not user_q:
                user_q = text
        if kwargs.get("tool_call_id") and kwargs.get("name"):
            tool_steps.append(
                {
                    "tool": kwargs.get("name"),
                    "status": kwargs.get("status"),
                    "output_preview": _trim_str(_message_text(kwargs.get("content")), 500),
                }
            )
        for tc in kwargs.get("tool_calls") or []:
            n = tc.get("name") or ((tc.get("function") or {}).get("name"))
            args = tc.get("args")
            if args is None and isinstance(tc.get("function"), dict):
                raw = tc["function"].get("arguments")
                try:
                    args = json.loads(raw) if isinstance(raw, str) else raw
                except json.JSONDecodeError:
                    args = raw
            if n:
                tool_steps.append({"tool": n, "args": args})
        if isinstance(mid, list) and any("AIMessage" in str(x) for x in mid):
            text = _message_text(kwargs.get("content"))
            if text.strip():
                final_answer = text
    return {
        "user_question": _trim_str(user_q, 1000),
        "tool_steps": tool_steps[:30],
        "final_answer": _trim_str(final_answer, 2000),
    }


def _ui_trace_url(project_id: str | None, trace_id: str) -> str:
    settings = get_settings()
    base = settings.langfuse_base_url.rstrip("/")
    if project_id:
        return f"{base}/project/{project_id}/traces/{trace_id}"
    return f"{base}/trace/{trace_id}"


def get_langfuse_trace(trace_id: str) -> dict[str, Any]:
    """Full readable Langfuse trace card (for 'give me this trace')."""
    init_telemetry()
    lf = get_langfuse()
    if lf is None:
        return {"error": "Langfuse not configured"}
    tid = (trace_id or "").strip()
    if not tid:
        return {
            "error": "trace_id required",
            "hint": "Pass a Langfuse trace id, or call get_latest_langfuse_trace",
        }

    full = _to_plain(lf.api.trace.get(tid))
    parsed = _parse_agent_run(full) if full.get("name") == "AgentRun" else {}
    observations = []
    sql_queries = []
    for obs in full.get("observations") or []:
        o = obs if isinstance(obs, dict) else _to_plain(obs)
        sql = _extract_sql_from_obs(o)
        if sql:
            sql_queries.append(sql)
        observations.append(
            {
                "id": o.get("id"),
                "name": o.get("name"),
                "type": o.get("type"),
                "latency": o.get("latency"),
                "start_time": o.get("startTime"),
            }
        )

    if not sql_queries:
        sql_queries = _recent_clickhouse_queries(lf, limit=15, minutes=30).get("queries") or []

    flush_telemetry()
    project_id = full.get("projectId")
    return {
        "kind": "langfuse_trace",
        "trace_id": tid,
        "name": full.get("name"),
        "session_id": full.get("sessionId"),
        "timestamp": full.get("timestamp") or full.get("createdAt"),
        "latency": full.get("latency"),
        "tags": full.get("tags") or [],
        "user_question": parsed.get("user_question"),
        "tools_and_steps": parsed.get("tool_steps")
        or _summarize_trace(full).get("tool_calls_seen"),
        "final_answer": parsed.get("final_answer"),
        "observations": observations[:50],
        "clickhouse_queries": sql_queries[:20],
        "langfuse_url": _ui_trace_url(project_id, tid),
        "session_url": (
            f"{get_settings().langfuse_base_url.rstrip('/')}/project/{project_id}/sessions/{full.get('sessionId')}"
            if full.get("sessionId") and project_id
            else None
        ),
        "how_to_read": (
            "Langfuse trace for the agent run. tools_and_steps = tools called; "
            "clickhouse_queries = SQL from RCA; open langfuse_url for the UI."
        ),
    }


def get_latest_langfuse_trace(*, prefer_agent_run: bool = True) -> dict[str, Any]:
    """Resolve 'give me the trace for this' → most recent AgentRun / session trace."""
    init_telemetry()
    lf = get_langfuse()
    if lf is None:
        return {"error": "Langfuse not configured"}

    sessions = list_langfuse_sessions(limit=5).get("sessions") or []
    for sess in sessions:
        sid = sess.get("id")
        if not sid:
            continue
        try:
            detail = _to_plain(lf.api.sessions.get(sid))
        except Exception:  # noqa: BLE001
            continue
        traces = [t if isinstance(t, dict) else _to_plain(t) for t in (detail.get("traces") or [])]

        def _ts(t: dict[str, Any]) -> str:
            return str(t.get("timestamp") or t.get("createdAt") or "")

        traces_sorted = sorted(traces, key=_ts, reverse=True)
        chosen = None
        if prefer_agent_run:
            chosen = next((t for t in traces_sorted if t.get("name") == "AgentRun"), None)
        chosen = chosen or (traces_sorted[0] if traces_sorted else None)
        if chosen and chosen.get("id"):
            card = get_langfuse_trace(str(chosen["id"]))
            card["resolved_from"] = "latest_session"
            card["session_id"] = sid
            card["note"] = (
                "Resolved 'this' to the latest Langfuse session's AgentRun. "
                "For another chat, pass session_id or trace_id explicitly."
            )
            return card

    try:
        listed = lf.api.trace.list(limit=10)
        rows = _to_plain(getattr(listed, "data", []) or [])
        if prefer_agent_run:
            rows = [r for r in rows if r.get("name") == "AgentRun"] or rows
        if rows:
            card = get_langfuse_trace(str(rows[0]["id"]))
            card["resolved_from"] = "latest_trace_list"
            return card
    except Exception as exc:  # noqa: BLE001
        return {"error": f"could not resolve latest trace: {exc}"}

    return {
        "error": "no Langfuse traces found yet — ask an RCA question first, then request the trace"
    }
