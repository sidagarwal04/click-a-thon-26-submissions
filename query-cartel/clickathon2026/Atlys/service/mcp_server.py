"""MCP server — tool definitions over SSE (ENGINEERING.md §4.2, §6.1).

Each tool handler is wrapped in a Langfuse span manually (Langfuse has no MCP
middleware — §6.2 gotcha) and emits `tool.called` to the event bus. Tools are
wired to the same agents the REST API uses, so the dashboard and the chat front
door are two faces of one pipeline.
"""
from __future__ import annotations

import json
import logging
import uuid

from . import db_read
from . import events as ev
from .agents.context import ContextAgent
from .agents.instrumentation import InstrumentationAgent
from .bus import EventBus
from .chat_progress import conversation_id_from_mcp_request, progress_hub
from .chat_store import is_valid_id
from .events import new_event
from .payloads import truncate_for_mcp

log = logging.getLogger("atlys.mcp")

try:
    from mcp.server import Server
    from mcp.server.sse import SseServerTransport
    from mcp.types import TextContent, Tool
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route
    MCP_AVAILABLE = True
except ImportError:  # pragma: no cover - mcp is optional for REST-only mode
    MCP_AVAILABLE = False
    Server = None  # type: ignore


class AtlysMcpServer:
    """Builds an MCP Server exposing the Atlys tools over SSE.

    Usage:
        mcp = AtlysMcpServer(bus, instrumentation, context, analytics, store, tracer)
        starlette_app = mcp.build_starlette_app()   # mount under /mcp
    """

    def __init__(self, bus: EventBus, instrumentation: InstrumentationAgent,
                 context: ContextAgent, analytics, store, tracer=None, settings=None):
        self.bus = bus
        self.instrumentation = instrumentation
        self.context = context
        self.analytics = analytics
        self.store = store
        self.tracer = tracer
        self.settings = settings
        self._server: Server | None = None
        self._run_in_flight = False   # True while a spec.run chain is unwinding

    # -- tool implementation ------------------------------------------------
    # Read-only tools that are not part of the pipeline chain — they get their
    # own `explore:*` trace so PM ad-hoc questions are replayable in Langfuse
    # (docs/inspect-tab-plan.md §4.2).
    EXPLORE_TOOLS = frozenset({
        "db_schema", "table_stats", "aggregate", "sample_rows",
        "get_insight", "list_insights", "get_changelog", "get_context",
        "propose_context_update", "save_document",
    })

    def _tool_called(self, name: str, arguments: dict, trace_id: str = "") -> None:
        """Emit tool.called, defaulting trace_id to the active tracer trace.

        W0 fix (docs/inspect-tab-plan.md §4.1): previously tool.called rows were
        persisted with trace_id='' so the audit log could not be joined to
        Langfuse on tool events. Guard: never persist an empty trace_id — if no
        tracer (or no active trace) is available, synthesize one and log so the
        row stays joinable (a synthetic id simply won't resolve in Langfuse).
        """
        tid = trace_id or (getattr(self.tracer, "trace_id", None) or "")
        if not tid:
            tid = f"synthetic-{uuid.uuid4().hex[:12]}"
            log.warning(
                "tool.called for %s had no active tracer trace_id — "
                "synthesized %s so the audit row stays traceable",
                name, tid,
            )
        self.bus.emit(new_event(
            ev.TOOL_CALLED, f"mcp/{name}", ev.ACTOR_MCP,
            payload={"tool": name, "arguments": arguments}, trace_id=tid,
        ))

    def _maybe_start_explore(self, name: str) -> None:
        """Start an `explore:*` Langfuse trace for read-only tools outside a run.

        Read tools run under the stale trace_id from the last spec run today;
        giving them their own trace makes PM exploration visible and replayable
        (§4.2). No-op when the tool is pipeline-scoped or a run is in flight.
        """
        if self.tracer is None or self._run_in_flight:
            return
        if name not in self.EXPLORE_TOOLS:
            return
        try:
            self.tracer.start(f"explore:{name}")
        except Exception:  # noqa: BLE001 — never let tracing break a tool call
            log.exception("explore trace start failed for %s", name)

    def _span(self, name: str, **meta):
        if self.tracer is None:
            import contextlib
            return contextlib.nullcontext()
        return self.tracer.span(name, **meta)

    # handlers return JSON strings (TextContent) — the chat agent narrates.
    def _run_spec(self, spec_dir: str, auto_approve: bool = False) -> dict:
        run_id = str(uuid.uuid4())
        # one Langfuse trace per run (§5.4), session_id = run_id for the
        # dual-trace cross-link (§6.2) — the trace id flows into every event
        trace_id = self.tracer.start(f"spec:{spec_dir}", session_id=run_id)
        self._run_in_flight = True
        try:
            with self._span("mcp_tool:run_spec", spec_dir=spec_dir, run_id=run_id):
                self.bus.emit(new_event(
                    ev.SPEC_RUN_REQUESTED, f"spec/{spec_dir}", ev.ACTOR_MCP,
                    payload={"spec_dir": spec_dir, "run_id": run_id},
                    trace_id=trace_id,
                ))
        finally:
            self._run_in_flight = False
        # fetch the pending schema that the instrumentation handler produced
        pending = self._latest_pending(run_id)
        if auto_approve:
            self._approve_schema(run_id)
            pending = self._latest_pending(run_id)
        return {
            "run_id": run_id,
            "state": (pending or {}).get("state", "unknown"),
            "schema_card": json.loads(pending["schema_card"]) if pending else None,
            "message": "Schema proposed — awaiting approval (D10). Nothing touched ClickHouse yet."
                       if pending and pending["state"] == "proposed"
                       else "No pending schema found for this run.",
        }

    def _approve_schema(self, run_id: str, note: str = "") -> dict:
        pending = self._latest_pending(run_id)
        if not pending:
            return {
                "run_id": run_id,
                "state": "unknown",
                "error": f"no pending run found for {run_id}",
                "code": "NOT_FOUND",
                "retriable": False,
            }
        if pending["state"] != "proposed":
            return {
                "run_id": run_id,
                "state": pending["state"],
                "message": f"Run already in state {pending['state']} — approval ignored.",
                "insight": self._latest_insight_for_run(run_id) if pending["state"] == "approved" else None,
            }
        trace_id = pending.get("trace_id") or getattr(self.tracer, "trace_id", "") or ""
        self._run_in_flight = True
        try:
            with self._span("mcp_tool:approve_schema", run_id=run_id):
                self.bus.emit(new_event(
                    ev.SCHEMA_APPROVED, f"run/{run_id}", ev.ACTOR_USER,
                    payload={"run_id": run_id, "note": note},
                    trace_id=trace_id,
                ))
        except Exception as e:  # noqa: BLE001 — surface failed state to chat
            log.exception("approve_schema failed for %s", run_id)
            after = self._latest_pending(run_id) or {}
            return {
                "run_id": run_id,
                "state": after.get("state", "failed"),
                "error": str(e),
                "code": "RUN_FAILED",
                "retriable": False,
                "hint": "Start a new run_spec for this feature; do not re-approve this run_id.",
            }
        finally:
            self._run_in_flight = False
        after = self._latest_pending(run_id) or {}
        insight = self._latest_insight_for_run(run_id)
        return {
            "run_id": run_id,
            "state": after.get("state", "approved"),
            "insight": insight,
        }

    def _reject_schema(self, run_id: str, note: str = "") -> dict:
        with self._span("mcp_tool:reject_schema", run_id=run_id):
            self.bus.emit(new_event(
                ev.SCHEMA_REJECTED, f"run/{run_id}", ev.ACTOR_USER,
                payload={"run_id": run_id, "note": note},
                trace_id=getattr(self.tracer, "trace_id", "") or "",
            ))
        return {"run_id": run_id, "state": "rejected", "message": "Run aborted — no state change."}

    def _interrogate_spec(self, spec_dir: str) -> dict:
        with self._span("mcp_tool:interrogate_spec", spec_dir=spec_dir):
            return self.instrumentation.interrogate(spec_dir)

    def _get_insight(self, feature: str) -> dict | None:
        rows = self.store.query_rows(
            "SELECT spec, title, summary, confidence, evidence, trace_id, created_at "
            "FROM meta.insights WHERE spec LIKE {f:String} ORDER BY created_at DESC LIMIT 1",
            {"f": f"%{feature}%"},
        )
        if not rows:
            return None
        r = rows[0]
        return {
            "spec": r["spec"], "title": r["title"], "summary": r["summary"],
            "confidence": r["confidence"], "evidence": json.loads(r["evidence"]),
            "trace_id": r["trace_id"], "created_at": r["created_at"],
        }

    def _list_insights(self) -> list[dict]:
        rows = self.store.query_rows(
            "SELECT spec, title, confidence, trace_id, created_at FROM meta.insights "
            "ORDER BY created_at DESC"
        )
        return rows

    def _get_changelog(self, scope: str = "context", limit: int = 20) -> list[dict]:
        if scope == "context":
            rows = self.store.query_rows(
                "SELECT version, agent, action, object, diff, rationale, trace_id, created_at "
                "FROM meta.context_changelog ORDER BY version DESC LIMIT {n:UInt32}",
                {"n": int(limit)},
            )
        elif scope == "schema":
            rows = self.store.query_rows(
                "SELECT version, agent, action, object, diff, rationale, trace_id, created_at "
                "FROM meta.schema_changelog ORDER BY version DESC LIMIT {n:UInt32}",
                {"n": int(limit)},
            )
        else:
            rows = self.store.query_rows(
                "SELECT event_id, event_type, aggregate_id, actor, payload, trace_id, created_at "
                "FROM atlys.event_log ORDER BY created_at DESC LIMIT {n:UInt32}",
                {"n": int(limit)},
            )
        return rows

    def _get_context(self, version: int | None = None) -> dict:
        if version:
            rows = self.store.query_rows(
                "SELECT version, content, content_hash, diff_from_prev, trace_id, created_at "
                "FROM meta.context_snapshots WHERE version = {v:UInt64}",
                {"v": int(version)},
            )
        else:
            rows = self.store.query_rows(
                "SELECT version, content, content_hash, diff_from_prev, trace_id, created_at "
                "FROM meta.context_snapshots ORDER BY version DESC LIMIT 1",
            )
        if not rows:
            return {}
        r = rows[0]
        # Prefer full markdown body over a huge diff blob in the chat path.
        diff = r["diff_from_prev"]
        if isinstance(diff, str) and len(diff) > 8_000:
            diff = diff[:8_000] + "…(diff truncated)"
        return {
            "version": r["version"],
            "content": r["content"],
            "content_hash": r["content_hash"],
            "diff_from_prev": diff,
            "trace_id": r["trace_id"],
            "created_at": r["created_at"],
        }

    def _propose_context_update(self, change: dict) -> dict:
        version = self.context.propose_context_update(change, trace_id="")
        return {"version": version, "status": "pending"}

    def _reconcile(self) -> dict:
        with self._span("mcp_tool:reconcile"):
            findings = self.context._run_reconcile(trace_id="")
        return {"findings": [f.__dict__ for f in findings], "count": len(findings)}

    def _db_schema(self, arguments: dict) -> dict:
        with self._span("mcp_tool:db_schema"):
            # Accept table / tables (string, list, or comma-separated).
            table = arguments.get("table")
            if table is None and arguments.get("tables") is not None:
                table = arguments.get("tables")
            try:
                return db_read.db_schema(
                    self.store,
                    table=table,
                    include_engine=bool(arguments.get("include_engine")),
                    include_meta=bool(arguments.get("include_meta")),
                )
            except Exception as e:  # noqa: BLE001
                return db_read.tool_error(e)

    def _table_stats(self, arguments: dict) -> dict:
        with self._span("mcp_tool:table_stats"):
            table = arguments.get("table")
            if table is None:
                return db_read.DbReadError("table is required", "BAD_ARGUMENT").to_dict()
            try:
                return db_read.table_stats(
                    self.store,
                    table,
                    approximate=arguments.get("approximate", True) is not False,
                    include_meta=bool(arguments.get("include_meta")),
                )
            except Exception as e:  # noqa: BLE001
                return db_read.tool_error(e)

    def _aggregate(self, arguments: dict) -> dict:
        with self._span("mcp_tool:aggregate"):
            try:
                return db_read.aggregate(
                    self.store,
                    table=arguments.get("table", ""),
                    metrics=arguments.get("metrics") or [],
                    group_by=arguments.get("group_by") or [],
                    filters=arguments.get("filters") or [],
                    order_by=arguments.get("order_by") or [],
                    limit=arguments.get("limit"),
                    include_meta=bool(arguments.get("include_meta")),
                )
            except Exception as e:  # noqa: BLE001
                return db_read.tool_error(e)

    def _sample_rows(self, arguments: dict) -> dict:
        with self._span("mcp_tool:sample_rows"):
            try:
                return db_read.sample_rows(
                    self.store,
                    table=arguments.get("table", ""),
                    columns=arguments.get("columns"),
                    filters=arguments.get("filters") or [],
                    limit=arguments.get("limit"),
                    order_by=arguments.get("order_by"),
                    include_meta=bool(arguments.get("include_meta")),
                )
            except Exception as e:  # noqa: BLE001
                return db_read.tool_error(e)

    def _ingest_events(self, table: str, rows: list[list]) -> dict:
        # demo helper: bulk-insert rows into an existing table
        if not rows:
            return {"inserted": 0}
        cols = [c["name"] for c in self.store.columns(table)]
        n = self.store.insert(table, cols, rows)
        return {"inserted": n}

    # -- MCP wiring ---------------------------------------------------------
    def _latest_pending(self, run_id: str) -> dict | None:
        rows = self.store.query_rows(
            "SELECT run_id, state, spec_dir, schema_card, trace_id FROM meta.pending_runs "
            "WHERE run_id = {rid:String} ORDER BY created_at DESC LIMIT 1",
            {"rid": run_id},
        )
        return rows[0] if rows else None

    def _latest_insight_for_run(self, run_id: str) -> dict | None:
        """Resolve the insight produced by this run (not merely the newest card).

        Insights are keyed by pipeline `trace_id` (Langfuse / NullTracer id),
        which is stored on `meta.pending_runs` for the run — not by `run_id`.
        """
        pending = self._latest_pending(run_id)
        trace_id = (pending or {}).get("trace_id") or ""
        if trace_id:
            rows = self.store.query_rows(
                "SELECT spec, title, summary, confidence, evidence, trace_id, created_at "
                "FROM meta.insights WHERE trace_id = {t:String} "
                "ORDER BY created_at DESC LIMIT 1",
                {"t": trace_id},
            )
            if rows:
                return rows[0]

        # Fallback: same spec_dir, newest card (best-effort if trace missing)
        spec_dir = (pending or {}).get("spec_dir") or ""
        if spec_dir:
            rows = self.store.query_rows(
                "SELECT spec, title, summary, confidence, evidence, trace_id, created_at "
                "FROM meta.insights WHERE spec = {s:String} "
                "ORDER BY created_at DESC LIMIT 1",
                {"s": spec_dir},
            )
            if rows:
                return rows[0]
        return None

    def build_server(self) -> Server:
        """Configure the MCP `Server` with list_tools / call_tool handlers."""
        if not MCP_AVAILABLE:
            raise RuntimeError("mcp package not installed — REST-only mode")

        server = Server("atlys-orchestrator")

        TOOLS = [
            Tool(name="interrogate_spec", description="Deterministic gaps/questions for a feature spec (no writes)",
                 inputSchema={"type": "object", "properties": {"spec_dir": {"type": "string"}}, "required": ["spec_dir"]}),
            Tool(name="run_spec", description="Run a feature spec: schema proposed → ⏸ waits for approval",
                 inputSchema={"type": "object", "properties": {"spec_dir": {"type": "string"}, "auto_approve": {"type": "boolean"}}, "required": ["spec_dir"]}),
            Tool(name="approve_schema", description="Approve a pending schema (D10 gate) and continue the run",
                 inputSchema={"type": "object", "properties": {"run_id": {"type": "string"}, "note": {"type": "string"}}, "required": ["run_id"]}),
            Tool(name="reject_schema", description="Reject a pending schema — aborts the run",
                 inputSchema={"type": "object", "properties": {"run_id": {"type": "string"}, "note": {"type": "string"}}, "required": ["run_id"]}),
            Tool(name="get_insight", description="Latest insight card for a feature",
                 inputSchema={"type": "object", "properties": {"feature": {"type": "string"}}, "required": ["feature"]}),
            Tool(name="list_insights", description="List all insight cards",
                 inputSchema={"type": "object", "properties": {}}),
            Tool(name="get_changelog", description="Changelog entries (context|schema|event_log)",
                 inputSchema={"type": "object", "properties": {"scope": {"type": "string"}, "limit": {"type": "integer"}}}),
            Tool(name="get_context", description="Latest (or versioned) context snapshot",
                 inputSchema={"type": "object", "properties": {"version": {"type": "integer"}}}),
            Tool(name="propose_context_update", description="Propose a human context edit",
                 inputSchema={"type": "object", "properties": {"change": {"type": "object"}}, "required": ["change"]}),
            Tool(name="reconcile", description="Run schema-vs-context reconciliation, return findings",
                 inputSchema={"type": "object", "properties": {}}),
            Tool(
                name="db_schema",
                description=(
                    "List tables, or describe columns for one or many tables in a SINGLE call "
                    "(pass table as a name, comma-separated names, or array). Read-only."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table": {
                            "description": (
                                "Omit to list table names. To describe schemas: one name, "
                                "comma-separated names, or array of names (max 20) — prefer one "
                                "batched call over multiple db_schema calls."
                            ),
                        },
                        "tables": {
                            "description": "Alias for table when passing an array of names",
                        },
                        "include_engine": {"type": "boolean"},
                        "include_meta": {"type": "boolean", "description": "Also include meta.* ops tables"},
                    },
                },
            ),
            Tool(
                name="table_stats",
                description="Row counts / size stats for one or more tables (read-only; approximate by default)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table": {
                            "description": "Table name, or JSON array of names (max 20)",
                        },
                        "approximate": {"type": "boolean", "default": True},
                        "include_meta": {"type": "boolean"},
                    },
                    "required": ["table"],
                },
            ),
            Tool(
                name="aggregate",
                description=(
                    "Constrained single-table aggregate (count/uniq/sum/avg/min/max/p50/p90) "
                    "with optional group_by + filters. Filter op: eq|neq|in|gt|gte|lt|lte|like "
                    "(aliases = != > >= < <= also accepted). No free-form SQL. Read-only."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table": {"type": "string"},
                        "metrics": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "fn": {"type": "string"},
                                    "column": {"type": "string"},
                                    "alias": {"type": "string"},
                                },
                                "required": ["fn"],
                            },
                        },
                        "group_by": {"type": "array", "items": {"type": "string"}},
                        "filters": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "column": {"type": "string"},
                                    "op": {
                                        "type": "string",
                                        "description": "eq|neq|in|gt|gte|lt|lte|like (or = != > >= < <=)",
                                    },
                                    "value": {},
                                },
                                "required": ["column", "op", "value"],
                            },
                        },
                        "order_by": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "by": {"type": "string"},
                                    "dir": {"type": "string"},
                                },
                                "required": ["by"],
                            },
                        },
                        "limit": {"type": "integer"},
                        "include_meta": {"type": "boolean"},
                    },
                    "required": ["table", "metrics"],
                },
            ),
            Tool(
                name="sample_rows",
                description="Tiny row preview from one table (default 5, max 20). Prefer aggregate for metrics.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table": {"type": "string"},
                        "columns": {"type": "array", "items": {"type": "string"}},
                        "filters": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "column": {"type": "string"},
                                    "op": {"type": "string"},
                                    "value": {},
                                },
                                "required": ["column", "op", "value"],
                            },
                        },
                        "limit": {"type": "integer"},
                        "order_by": {
                            "description": "Column name string, or {by, dir} object",
                        },
                        "include_meta": {"type": "boolean"},
                    },
                    "required": ["table"],
                },
            ),
            Tool(
                name="save_document",
                description="Save a document (report, text file, markdown summary, SQL query, etc.) to the project workspace so the user can download and preview it. Path should be under 'generated/'.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filename": {"type": "string", "description": "Filename, e.g. 'pay_now_os_geo_breakdown.md' or 'analytics_report.csv'"},
                        "content": {"type": "string", "description": "The full text content of the document"},
                        "subdirectory": {"type": "string", "description": "Optional subdirectory under generated/ (default is 'reports')"}
                    },
                    "required": ["filename", "content"]
                }
            ),
            # ingest_events intentionally omitted from the demo tool surface
        ]

        @server.list_tools()
        async def list_tools() -> list[Tool]:
            return TOOLS

        @server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            call_id = str(uuid.uuid4())
            # LibreChat sets X-Atlys-Conversation-Id from the Agents API body
            # (see librechat.yaml). Scopes progress + tool budget per chat.
            raw_cid = conversation_id_from_mcp_request(server)
            cid = raw_cid if raw_cid and is_valid_id(raw_cid) else None
            if raw_cid and cid is None:
                log.warning("ignoring invalid X-Atlys-Conversation-Id: %r", raw_cid)

            allowed, budget = progress_hub.try_consume_tool(cid)
            if not allowed:
                limit = int(budget.get("limit") or 50)
                used = int(budget.get("used") or limit)
                progress_hub.publish({
                    "type": "tool_limit",
                    "id": call_id,
                    "name": name,
                    "used": used,
                    "limit": limit,
                }, conversation_id=cid)
                result = {
                    "error": (
                        f"Tool-call limit reached ({used}/{limit} in this series). "
                        "Stop and tell the user to reply with \"continue\" "
                        "(or another message) to allow another round of tools. "
                        "Do not retry tools until they continue."
                    ),
                    "code": "TOOL_LIMIT",
                    "used": used,
                    "limit": limit,
                    "retriable": False,
                }
                safe = truncate_for_mcp(result)
                return [TextContent(type="text", text=json.dumps(safe, indent=2, default=str))]

            # W0: attach the current trace (run trace, or a fresh explore trace
            # for read-only tools outside a run) to the tool.called audit row.
            self._maybe_start_explore(name)
            self._tool_called(name, arguments)
            # Side-channel for the React shell — LibreChat often buffers tool
            # deltas until the agent step finishes.
            progress_hub.publish({
                "type": "tool_call",
                "id": call_id,
                "name": name,
                "arguments": arguments or {},
                "used": budget.get("used"),
                "limit": budget.get("limit"),
            }, conversation_id=cid)
            try:
                result = self._dispatch(name, arguments)
            except Exception as e:  # noqa: BLE001
                log.exception("mcp tool %s failed", name)
                result = {"error": str(e)}
            ok = not (isinstance(result, dict) and result.get("error"))
            progress_hub.publish({
                "type": "tool_done",
                "id": call_id,
                "name": name,
                "ok": ok,
            }, conversation_id=cid)
            # Context snapshots are markdown docs — keep known-issues / metrics
            # intact (default str_limit=4k previously cut mid-document).
            if name == "get_context":
                safe = truncate_for_mcp(result, max_bytes=200_000)
            else:
                safe = truncate_for_mcp(result)
            return [TextContent(type="text", text=json.dumps(safe, indent=2, default=str))]

        self._server = server
        return server

    def _dispatch(self, name: str, arguments: dict) -> dict:
        if name == "run_spec":
            return self._run_spec(arguments.get("spec_dir", ""),
                                  auto_approve=bool(arguments.get("auto_approve")))
        if name == "approve_schema":
            return self._approve_schema(arguments.get("run_id", ""), arguments.get("note", ""))
        if name == "reject_schema":
            return self._reject_schema(arguments.get("run_id", ""), arguments.get("note", ""))
        if name == "interrogate_spec":
            return self._interrogate_spec(arguments.get("spec_dir", ""))
        if name == "get_insight":
            return self._get_insight(arguments.get("feature", "")) or {"error": "no insight"}
        if name == "list_insights":
            return {"insights": self._list_insights()}
        if name == "get_changelog":
            return {"entries": self._get_changelog(arguments.get("scope", "context"),
                                                   arguments.get("limit", 20))}
        if name == "get_context":
            return self._get_context(arguments.get("version"))
        if name == "propose_context_update":
            return self._propose_context_update(arguments.get("change", {}))
        if name == "reconcile":
            return self._reconcile()
        if name == "db_schema":
            return self._db_schema(arguments)
        if name == "table_stats":
            return self._table_stats(arguments)
        if name == "aggregate":
            return self._aggregate(arguments)
        if name == "sample_rows":
            return self._sample_rows(arguments)
        if name == "save_document":
            return self._save_document(
                arguments.get("filename", ""),
                arguments.get("content", ""),
                arguments.get("subdirectory", "reports")
            )
        if name == "ingest_events":
            return {
                "error": "ingest_events is disabled on the demo MCP surface",
                "code": "TOOL_DISABLED",
                "retriable": False,
            }
        return {"error": f"unknown tool {name}"}

    def _save_document(self, filename: str, content: str, subdirectory: str = "reports") -> dict:
        with self._span("mcp_tool:save_document", filename=filename, subdirectory=subdirectory):
            if not filename:
                return {"error": "filename is required"}
            
            if "/" in filename or "\\" in filename or ".." in filename:
                return {"error": "invalid filename"}
                
            generated_dir = self.settings.generated_dir.resolve()
            target_dir = (generated_dir / subdirectory).resolve()
            
            try:
                target_dir.relative_to(generated_dir)
            except ValueError:
                return {"error": "invalid subdirectory path"}
                
            target_path = (target_dir / filename).resolve()
            
            try:
                target_dir.mkdir(parents=True, exist_ok=True)
                target_path.write_text(content, encoding="utf-8")
                
                rel_path = target_path.relative_to(self.settings.atlys_root)
                return {
                    "success": True,
                    "filename": filename,
                    "path": str(rel_path),
                    "size": len(content),
                    "message": f"Document saved successfully to {rel_path}."
                }
            except Exception as e:
                log.exception("Failed to save document")
                return {"error": f"Failed to save document: {e}"}

    def register_routes(self, app) -> None:
        """Register flat SSE and POST message routes directly on FastAPI app.

        Using flat routing prevents Starlette's Mount from stripping path prefixes
        so that SseServerTransport receives the exact path matching its initialized URL.
        """
        server = self.build_server()
        sse = SseServerTransport("/mcp/messages/")

        async def handle_sse(request):
            async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
                await server.run(streams[0], streams[1], server.create_initialization_options())
            from starlette.responses import Response
            return Response()

        class McpMessageHandler:
            def __init__(self, transport):
                self.transport = transport
            async def __call__(self, scope, receive, send):
                await self.transport.handle_post_message(scope, receive, send)

        app.add_route("/mcp/sse", handle_sse, methods=["GET"])
        app.add_route("/mcp/messages/", McpMessageHandler(sse), methods=["POST"])


