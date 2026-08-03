"""Clickathon RCA MCP server — thin readers over ClickHouse rca_* tables."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from mcp.server.mcpserver import Image, MCPServer
from mcp.types import CallToolResult, TextContent
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from clickathon.charts import (
    CHART_KINDS,
    chart_url,
    charts_dir,
    load_chart_bytes,
    resolve_kind,
)
from clickathon.explain import explain_anomaly_from_store
from clickathon.glossary import get_clickathon_repo_file, get_metrics_glossary
from clickathon.investigate import scan_anomalies
from clickathon.langfuse_verify import (
    get_langfuse_session,
    get_langfuse_trace,
    get_latest_langfuse_trace,
    list_langfuse_clickhouse_queries,
    list_langfuse_sessions,
)
from clickathon.rca_store import (
    counterfactual_from_store,
    decompose_day_from_store,
    detect_day_from_store,
    drill_combo_from_store,
    drill_dim_from_store,
    expected_baseline_from_store,
    investigate_day_from_store,
    list_incidents_from_store,
)
from clickathon.telemetry import flush_telemetry, init_telemetry

logger = logging.getLogger(__name__)

mcp = MCPServer(
    name="clickathon-rca",
    title="Clickathon RCA",
    description=(
        "Thin RCA tools over precomputed eda.rca_* tables "
        "(materialize via `clickathon materialize`). Numbers from ClickHouse only."
    ),
    instructions=(
        "Incidents come ONLY from list_all_anomalies / rca_incidents — never invent them. "
        "For a detailed root-cause write-up, call explain_anomaly(incident_id) or "
        "explain_anomaly(probe_day=...) and present the explanation / narrative in full. "
        "After explaining, call counterfactual(incident_id) for ClickHouse what-if revenues. "
        "After explain_anomaly, call plot_anomaly(incident_id, chart='window') "
        "(also factors / counterfactual) so the user sees a chart — do NOT invent Chart.js/Mermaid. "
        "If the image does not render, include the markdown image URL from the tool text. "
        "When asked about metric definitions, call get_metrics_glossary_tool. "
        "For deeper digs, use ClickHouse MCP against rca_segment_day / rca_combo_day / ad_events. "
        "To verify or show a Langfuse trace, call get_latest_langfuse_trace_tool "
        "(for 'give me the trace for this') or get_langfuse_trace_tool(trace_id). "
        "Also: list_langfuse_sessions_tool / get_langfuse_session_tool / "
        "list_langfuse_clickhouse_queries_tool. "
        "Baseline is same weekday minus 7. Ratio metrics must be sum/sum per the glossary."
    ),
)


def _j(data: Any) -> str:
    flush_telemetry()
    return json.dumps(data, default=str, indent=2)


@mcp.tool(
    description=(
        "Fetch the official Click-a-thon InMobi metrics glossary from the locked repo "
        "sidagarwal04/click-a-thon-2026 (InMobi/metrics_glossary.md). "
        "Call before inventing formulas. Set refresh=true to bypass cache."
    )
)
def get_metrics_glossary_tool(refresh: bool = False) -> str:
    return _j(get_metrics_glossary(refresh=refresh))


@mcp.tool(
    description=(
        "Read a file from the locked Click-a-thon GitHub repo ONLY "
        "(sidagarwal04/click-a-thon-2026). Pass a repo-relative path such as "
        "InMobi/metrics_glossary.md. Other GitHub repositories cannot be accessed."
    )
)
def get_clickathon_github_file(path: str = "InMobi/metrics_glossary.md", ref: str = "main") -> str:
    try:
        return _j(get_clickathon_repo_file(path, ref=ref))
    except Exception as exc:  # noqa: BLE001
        return _j(
            {
                "error": str(exc),
                "allowed_owner": "sidagarwal04",
                "allowed_repo": "click-a-thon-2026",
            }
        )


@mcp.tool(
    description=(
        "Raw day-level wow flags from live scan (includes recoveries). "
        "Prefer list_all_anomalies for clustered incidents from rca_incidents."
    )
)
def scan_anomalies_tool(start_date: str = "", end_date: str = "") -> str:
    return _j(scan_anomalies(start_date or None, end_date or None))


@mcp.tool(
    description=(
        "List precomputed metric incidents from eda.rca_incidents "
        "(built by clickathon materialize — ClickHouse functions + SQL, not the LLM). "
        "Call when the user asks 'what are the anomalies'. "
        "Give a short summary per incident, then call explain_anomaly for each id "
        "when the user wants detail (or always for deep RCA)."
    )
)
def list_all_anomalies() -> str:
    return _j(list_incidents_from_store())


@mcp.tool(
    description=(
        "DETAILED root-cause analysis for one anomaly. "
        "Pass incident_id from list_all_anomalies (e.g. 'A') OR probe_day (YYYY-MM-DD). "
        "Returns multi-section explanation: diagnosis, global WoW, factor shares, "
        "localization, supporting segments, counterfactual, window days, ruled out. "
        "Present explanation (and narrative if present) in full — do not invent numbers."
    )
)
def explain_anomaly(
    incident_id: str = "",
    probe_day: str = "",
    include_narrative: bool = True,
) -> str:
    return _j(
        explain_anomaly_from_store(
            incident_id=incident_id,
            probe_day=probe_day,
            include_narrative=include_narrative,
        )
    )


@mcp.tool(
    description=(
        "ClickHouse counterfactual revenues for an incident "
        "(what revenue would have been if fill/eCPM/requests stayed at T-7 baseline). "
        "Pass incident_id from list_all_anomalies or probe_day. "
        "Numbers from eda.rca_counterfactual only — use after explain_anomaly."
    )
)
def counterfactual(incident_id: str = "", probe_day: str = "") -> str:
    return _j(counterfactual_from_store(incident_id=incident_id, probe_day=probe_day))


@mcp.tool(
    description=(
        "Return a precomputed PNG chart for an anomaly (fast — reads cache from materialize). "
        "chart: window (actual vs T-7 primary metric), factors (contribution shares), "
        "or counterfactual (what-if revenues). Pass incident_id from list_all_anomalies. "
        "Returns an image plus a markdown URL fallback — do NOT invent Chart.js/Mermaid."
    )
)
def plot_anomaly(incident_id: str, chart: str = "window") -> CallToolResult:
    # Skip Langfuse flush here — chart path is latency-critical (~1s SLO).
    # Return CallToolResult so MCP does not JSON-serialize the Image helper.
    iid = (incident_id or "").strip()
    if not iid:
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "error": "pass incident_id from list_all_anomalies",
                            "kinds": list(CHART_KINDS),
                        },
                        default=str,
                        indent=2,
                    ),
                )
            ]
        )
    try:
        kind = resolve_kind(chart)
        png = load_chart_bytes(iid, kind)
    except Exception as exc:  # noqa: BLE001
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "error": str(exc),
                            "incident_id": iid,
                            "chart": chart,
                            "kinds": list(CHART_KINDS),
                        },
                        default=str,
                        indent=2,
                    ),
                )
            ]
        )
    url = chart_url(iid, kind)
    summary = {
        "incident_id": iid,
        "chart": kind,
        "url": url,
        "markdown": f"![{iid} {kind}]({url})",
        "note": "Precomputed PNG from ClickHouse rca_* numbers. Prefer the image; else paste markdown.",
    }
    return CallToolResult(
        content=[
            Image(data=png, format="png").to_image_content(),
            TextContent(type="text", text=json.dumps(summary, default=str, indent=2)),
        ]
    )


@mcp.custom_route("/charts/{filename}", methods=["GET"])
async def serve_chart(request: Request) -> Response:
    """Public PNG fallback for LibreChat markdown: ![](http://localhost:8001/charts/A_window.png)."""
    filename = request.path_params.get("filename") or ""
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.png", filename):
        return JSONResponse({"error": "invalid filename"}, status_code=400)
    path = charts_dir() / filename
    if not path.is_file():
        # Best-effort on-demand: A_window.png → incident A, kind window
        stem = filename[:-4]
        if "_" in stem:
            iid, kind_raw = stem.rsplit("_", 1)
            try:
                kind = resolve_kind(kind_raw)
                load_chart_bytes(iid, kind)
            except Exception as exc:  # noqa: BLE001
                return JSONResponse({"error": str(exc), "path": str(path)}, status_code=404)
    if not path.is_file():
        return JSONResponse({"error": "not found", "path": str(path)}, status_code=404)
    return Response(path.read_bytes(), media_type="image/png")


@mcp.tool(description="Day vs same weekday -7 from rca_daily_wow (precomputed).")
def detect_day(day: str) -> str:
    return _j(detect_day_from_store(day))


@mcp.tool(
    description=(
        "ClickHouse simpleLinearRegression expected baseline for a day "
        "(predicts actual from T-7; returns residual and residual_z). "
        "Use to show how abnormal a day is vs the learned T-7 relationship. "
        "Source: eda.rca_ml_expected."
    )
)
def expected_baseline(day: str) -> str:
    return _j(expected_baseline_from_store(day))


@mcp.tool(description="Factor decomposition from rca_factor_day (precomputed).")
def decompose_day(day: str) -> str:
    return _j(decompose_day_from_store(day))


@mcp.tool(
    description="Drill one dimension from rca_segment_day: os_version|region|ad_format|category."
)
def drill_dim(day: str, dimension: str = "os_version", limit: int = 12) -> str:
    return _j(drill_dim_from_store(day, dimension, limit=limit))


@mcp.tool(description="Drill combo from rca_combo_day: os_region or format_region.")
def drill_combo_tool(day: str, combo: str = "os_region", limit: int = 15) -> str:
    return _j(drill_combo_from_store(day, combo, limit=limit))


@mcp.tool(description="Segment scan helper (alias of drill_dim over rca_segment_day).")
def segment_scan_tool(day: str, dimension: str = "os_version", limit: int = 15) -> str:
    return _j(drill_dim_from_store(day, dimension, limit=limit))


@mcp.tool(
    description=(
        "Localize using precomputed segment/combo tables for the day "
        "(top rows by impact for the primary factor)."
    )
)
def localize_day(day: str, primary_factor: str = "") -> str:
    primary = primary_factor or (decompose_day_from_store(day).get("primary_factor") or "fill_rate")
    segs = drill_dim_from_store(day, "os_version", limit=8)["segments"]
    combos = drill_combo_from_store(day, "os_region", limit=8)["segments"]
    fmt = drill_combo_from_store(day, "format_region", limit=8)["segments"]
    cats = drill_dim_from_store(day, "category", limit=8)["segments"]
    candidates = []
    for s in segs:
        candidates.append({**s, "kind": "dim", "dimension": "os_version"})
    for s in combos:
        candidates.append({**s, "kind": "combo", "dimension": "os_region"})
    for s in fmt:
        candidates.append({**s, "kind": "combo", "dimension": "format_region"})
    for s in cats:
        candidates.append({**s, "kind": "dim", "dimension": "category"})
    if primary == "fill_rate":
        candidates.sort(key=lambda x: x.get("fill_impact") or 0, reverse=True)
    elif primary == "ecpm":
        candidates.sort(
            key=lambda x: abs(x.get("ecpm_chg") or 0) * abs(x.get("d_rev") or 1),
            reverse=True,
        )
    else:
        candidates.sort(key=lambda x: abs(x.get("req_chg") or 0), reverse=True)
    top = candidates[0] if candidates else None
    return _j(
        {
            "day": day,
            "primary_factor": primary,
            "source_tables": ["rca_segment_day", "rca_combo_day"],
            "top_localization": top,
            "top5": candidates[:5],
            "shape": "from_store",
        }
    )


@mcp.tool(
    description=(
        "Day RCA from rca_* tables (detect + factor + localization + detailed explanation). "
        "Set include_narrative=false for JSON-only. Dig deeper via explain_anomaly or ClickHouse MCP."
    )
)
def investigate_day(day: str, include_narrative: bool = True) -> str:
    findings = investigate_day_from_store(day)
    if include_narrative and not findings.get("error"):
        try:
            from clickathon.narrate import narrate_detailed_rca

            # Prefer detailed narrator when explanation pack is present
            if findings.get("explanation"):
                findings["narrative"] = narrate_detailed_rca(
                    {
                        "probe_day": findings.get("day"),
                        "baseline_day": findings.get("baseline_day"),
                        "primary_factor": (findings.get("factors") or {}).get("primary_factor"),
                        "shape": (findings.get("localization") or {}).get("shape"),
                        "segment": (findings.get("localization") or {}).get("segment"),
                        "global_deltas": (findings.get("detection") or {}).get("deltas"),
                        "contribution_shares": (findings.get("factors") or {}).get(
                            "contribution_shares"
                        ),
                        "evidence": {
                            "actual": (findings.get("detection") or {}).get("actual"),
                            "baseline": (findings.get("detection") or {}).get("baseline"),
                            "segment": (findings.get("localization") or {}).get(
                                "top_localization"
                            ),
                        },
                        "contributors": {
                            "top_overall": (findings.get("localization") or {}).get(
                                "supporting"
                            )
                            or []
                        },
                        "window_days": findings.get("window_days") or [],
                        "ruled_out": findings.get("ruled_out") or [],
                        "explanation": findings.get("explanation"),
                    }
                )
            else:
                from clickathon.narrate import narrate_findings

                findings["narrative"] = narrate_findings(findings)
        except Exception as exc:  # noqa: BLE001
            findings["narrative_error"] = str(exc)
    return _j(findings)


@mcp.tool(
    description=(
        "List recent Langfuse sessions (LibreChat thread_id ≈ session id). "
        "Use before get_langfuse_session to pick a session to verify."
    )
)
def list_langfuse_sessions_tool(limit: int = 10) -> str:
    return _j(list_langfuse_sessions(limit=limit))


@mcp.tool(
    description=(
        "Pull a Langfuse session for verification: AgentRun traces, tools called, "
        "and clickhouse.query SQL spans. Pass LibreChat conversation/thread id as session_id. "
        "Use to confirm the agent actually ran grounded tools/SQL (not invented numbers)."
    )
)
def get_langfuse_session_tool(session_id: str, include_sql: bool = True) -> str:
    return _j(get_langfuse_session(session_id, include_sql=include_sql))


@mcp.tool(
    description=(
        "List recent ClickHouse SQL queries logged to Langfuse as clickhouse.query spans "
        "(from RCA MCP). Optional window in minutes (default 60)."
    )
)
def list_langfuse_clickhouse_queries_tool(limit: int = 20, minutes: int = 60) -> str:
    return _j(list_langfuse_clickhouse_queries(limit=limit, minutes=minutes))


@mcp.tool(
    description=(
        "PRIMARY tool when the user says 'give me the trace', 'show the trace for this', "
        "'langfuse for this', or 'what ran'. Returns a readable Langfuse AgentRun card: "
        "user question, tools/steps, final answer, ClickHouse SQL, and langfuse_url. "
        "No id needed — resolves the latest session/trace."
    )
)
def get_latest_langfuse_trace_tool() -> str:
    return _j(get_latest_langfuse_trace())


@mcp.tool(
    description=(
        "Fetch one Langfuse trace by id and return a readable card (tools, answer, SQL, UI link). "
        "Use when the user pastes a specific trace_id."
    )
)
def get_langfuse_trace_tool(trace_id: str) -> str:
    return _j(get_langfuse_trace(trace_id))


def main(host: str = "0.0.0.0", port: int = 8001) -> None:
    import asyncio
    import logging

    logging.basicConfig(level=logging.INFO)
    init_telemetry()
    from mcp.server.transport_security import TransportSecuritySettings

    logger.info("Starting Clickathon RCA MCP on http://%s:%s/mcp", host, port)

    async def _run() -> None:
        await mcp.run_streamable_http_async(
            host=host,
            port=port,
            streamable_http_path="/mcp",
            transport_security=TransportSecuritySettings(
                enable_dns_rebinding_protection=False,
            ),
        )

    asyncio.run(_run())


if __name__ == "__main__":
    main()
