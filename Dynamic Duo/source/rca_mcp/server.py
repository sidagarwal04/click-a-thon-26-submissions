"""rca-mcp — the MCP server LibreChat calls for incidents and live drill-downs.

Three tools, all backed by the deterministic runner (agent/runner.py): the LLM in the
chat never computes a root cause, it only relays what these tools return. Every
investigation writes its trace to rca.investigation_steps as it runs.

Runs as a compose sidecar speaking streamable HTTP:
    python -m rca_mcp.server          # serves http://0.0.0.0:8100/mcp

Env: CH_HOST/CH_TRANSPORT/... (detector/chdb.py), RCA_DATASET, ANTHROPIC_API_KEY +
NARRATOR_MODEL (narrator; template fallback without a key), RCA_MCP_HOST/RCA_MCP_PORT.
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from agent import runner

mcp = FastMCP(
    "rca-analyst",
    instructions=(
        "Automated root-cause analysis over the rca ClickHouse database. "
        "Use list_incidents to see what detection found; investigate to drill into an "
        "incident by id; investigate_window for any ad-hoc (metric, window, scope). "
        "Answers are computed by a fixed, deterministic query sequence — never by an "
        "LLM — and every step is logged to rca.investigation_steps."),
    host=os.environ.get("RCA_MCP_HOST", "0.0.0.0"),
    port=int(os.environ.get("RCA_MCP_PORT", "8100")),
)


@mcp.tool()
def list_incidents(status: str = "", limit: int = 50) -> list[dict]:
    """List incidents (detected anomalies, ruled-out seasonal windows, diagnoses).

    Args:
        status: optional filter — one of detected | investigating | diagnosed |
            ruled_out_seasonal | dismissed. Empty string returns all.
        limit: max rows (default 50).

    Returns rows with incident_id, metric, scope, window, status, z_score,
    pct_change_pct, and the stored headline when a diagnosis exists. Present these as
    a table; investigate(incident_id) drills into one.
    """
    return runner.list_incidents(status or None, limit)


@mcp.tool()
def investigate(incident_id: str, force: bool = False) -> dict:
    """Run the full root-cause drill-down for one incident from list_incidents.

    Executes the fixed query sequence (decompose -> dimension sweeps -> confounder
    elimination / mix-shift gate / peer comparison) live against ClickHouse, logging
    every step, then returns the guard-railed diagnosis: headline, narrative, verdict,
    the evidence bundle every cited number comes from, and the step-by-step trace.

    Re-invocations return the stored diagnosis (idempotent); force=True re-runs.
    Relay the narrative and cite its numbers exactly — never adjust or recompute them.
    """
    return runner.investigate(incident_id, force=force)


@mcp.tool()
def investigate_window(metric: str, window_start: str, window_end: str,
                       scope: str = "global", force: bool = False) -> dict:
    """Investigate any ad-hoc (metric, window, scope) — no prior incident needed.

    Creates an incident row on demand and runs the same fixed drill-down as
    investigate. "Nothing moved beyond noise, here's what was checked" is a valid
    outcome (verdict NO_MOVEMENT).

    Args:
        metric: one of requests | fills | impressions | clicks | revenue | fill_rate |
            render_rate | ctr | ecpm.
        window_start: 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM[:SS]' (UTC).
        window_end: same formats; a bare date means "through that whole day".
        scope: 'global' (default) or 'dimension=value', e.g. 'country=ID',
            'os_version=Android 15', 'ad_format=rewarded'.
    """
    return runner.investigate_window(metric, window_start, window_end,
                                     scope=scope or "global", force=force)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
