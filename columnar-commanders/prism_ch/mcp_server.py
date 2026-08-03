"""MCP server exposing the agents as tools, so LibreChat can drive them.

Design notes:

- **`execute` defaults to False.** The first call profiles the events, designs a
  schema, and validates the DDL against a scratch database - but creates nothing.
  A second call with `execute=true` is the human-in-the-loop approval gate the
  brief permits (X7), and it happens in chat where the reviewer can read the
  reasoning first.
- **Every call is traced.** Each tool opens its own `pipeline_run`, so a schema
  designed through the chat UI carries the same provenance as one from the CLI.
  The returned `run_id` is how you find it in Langfuse.
- **This is separate from `mcp-clickhouse`.** That server gives the chat raw SQL
  access for exploration; this one exposes the agent pipeline. Different jobs -
  the agents themselves never go through MCP, they use the direct client.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .config import Settings
from .db import connect
from .tracing import init_tracing, pipeline_run, shutdown

log = logging.getLogger(__name__)


def parse_events(raw: str | list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Accept NDJSON, a JSON array, or an already-parsed list.

    Chat users paste whatever they have; refusing on format would make the tool
    annoying to drive conversationally.
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return [e for e in raw if isinstance(e, dict)]

    text = raw.strip()
    if not text:
        return []

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [e for e in parsed if isinstance(e, dict)]
        if isinstance(parsed, dict):
            return [parsed]
    except json.JSONDecodeError:
        pass

    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip().rstrip(",")
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events


def build_server(settings: Settings) -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - depends on install
        raise RuntimeError("mcp SDK not installed - `pip install mcp`") from exc

    mcp = FastMCP(
        "prism-agents",
        host=settings.mcp_host,
        port=settings.mcp_port,
    )

    @mcp.tool()
    def instrument_spec(
        spec_name: str,
        brief: str,
        events: str,
        execute: bool = False,
    ) -> str:
        """Design a ClickHouse schema for a feature spec and optionally create it.

        Profiles the sample events, designs tables (ordering keys, types,
        partitioning, TTL, and materialized views where they earn their keep),
        validates the DDL against a throwaway database, and returns it with the
        reasoning behind each decision.

        Nothing is created unless `execute` is true - call once to review, then
        again with execute=true to apply.

        Args:
            spec_name: short name for the feature, e.g. "express_checkout"
            brief: the feature description, including how it will be queried
            events: sample raw events as NDJSON or a JSON array
            execute: create the tables for real (default: preview only)
        """
        from .agents import InstrumentationAgent
        from .agents.types import SpecInput

        parsed = parse_events(events)
        if not parsed:
            return json.dumps(
                {
                    "error": "no events could be parsed",
                    "hint": "paste NDJSON (one JSON object per line) or a JSON array",
                }
            )

        spec = SpecInput(name=spec_name, brief=brief, events=parsed)
        client = connect(settings)

        with pipeline_run("instrument", spec_name=spec.name, via="mcp") as run:
            agent = InstrumentationAgent(settings, client)
            try:
                result = agent.run(spec, execute=execute)
            except Exception as exc:  # surfaced to chat rather than killing the server
                log.exception("instrumentation failed")
                return json.dumps({"error": str(exc), "run_id": run.run_id})

            payload = {
                "run_id": run.run_id,
                "trace_id": run.trace_id,
                "executed": execute,
                "events_sampled": len(parsed),
                "ddl": result.statements,
                "proposal": result.proposal.as_dict(),
                "notes": result.proposal.notes,
                "decisions": result.decisions,
                "next_step": (
                    "tables created"
                    if execute
                    else "review the DDL, then call again with execute=true"
                ),
            }
            run.output({"executed": execute, "tables": len(result.proposal.tables)})
            return json.dumps(payload, indent=2, default=str)

    @mcp.tool()
    def profile_events(events: str) -> str:
        """Show what the agent infers from sample events, without designing a schema.

        Useful for checking that the data parsed correctly before instrumenting:
        per-field distinct counts, null rates, inferred types and codecs.

        Args:
            events: sample raw events as NDJSON or a JSON array
        """
        from .agents.profiling import profile_events as run_profile
        from .agents.profiling import profile_summary

        parsed = parse_events(events)
        if not parsed:
            return json.dumps({"error": "no events could be parsed"})
        return json.dumps(
            {"events": len(parsed), "fields": profile_summary(run_profile(parsed))},
            indent=2,
            default=str,
        )

    @mcp.tool()
    def refresh_context() -> str:
        """Update the context layer from the live database.

        Run this after creating tables so the Analytics Agent sees them. Returns
        the new context version, what changed, and any contradictions or gaps.
        """
        from .agents import ContextAgent

        client = connect(settings)
        with pipeline_run("context", spec_name="refresh", via="mcp") as run:
            agent = ContextAgent(settings, client)
            version, delta, insight_report = agent.run(None)
            snapshot = agent.store.load(version)
            run.output(snapshot.as_dict())
            return json.dumps(
                {
                    "run_id": run.run_id,
                    "version": version,
                    "entries": len(snapshot.entries),
                    "diff": delta.as_dict(),
                    "issues": [i.as_dict() for i in snapshot.issues],
                    "insights": insight_report.as_dict(),
                    "analytics_run_id": agent.last_analytics_run_id,
                    "analytics_trace_id": agent.last_analytics_trace_id,
                },
                indent=2,
                default=str,
            )

    @mcp.tool()
    def list_generated_tables() -> str:
        """List tables in the working database with their engine and ordering key."""
        client = connect(settings)
        result = client.query(
            "SELECT name, engine, sorting_key, partition_key, total_rows "
            "FROM system.tables WHERE database = {db:String} ORDER BY name",
            parameters={"db": settings.database},
        )
        rows = getattr(result, "result_rows", None) or []
        return json.dumps(
            [
                {
                    "table": r[0],
                    "engine": r[1],
                    "order_by": r[2],
                    "partition_by": r[3],
                    "rows": r[4],
                }
                for r in rows
            ],
            indent=2,
            default=str,
        )

    return mcp


def serve_mcp(settings: Settings) -> int:
    init_tracing(settings)
    server = build_server(settings)
    log.info(
        "prism MCP server on %s:%d -> ClickHouse %s/%s (%s)",
        settings.mcp_host,
        settings.mcp_port,
        settings.host,
        settings.database,
        settings.clickhouse_target,
    )
    try:
        # streamable-http, not sse: the SSE transport is deprecated in the MCP
        # spec and LibreChat drops/reconnects against it in a tight loop.
        # Served at /mcp.
        server.run(transport=settings.mcp_transport)
    finally:
        shutdown()
    return 0
