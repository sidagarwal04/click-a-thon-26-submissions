#!/usr/bin/env python3
"""Create/update LibreChat RCA agents, wire Orchestrator→specialists, patch yaml."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
YAML = ROOT / "stack" / "librechat.yaml"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

RCA = {
    "get_metrics_glossary_tool": "get_metrics_glossary_tool_mcp_Clickathon-RCA",
    "get_clickathon_github_file": "get_clickathon_github_file_mcp_Clickathon-RCA",
    "list_all_anomalies": "list_all_anomalies_mcp_Clickathon-RCA",
    "explain_anomaly": "explain_anomaly_mcp_Clickathon-RCA",
    "counterfactual": "counterfactual_mcp_Clickathon-RCA",
    "plot_anomaly": "plot_anomaly_mcp_Clickathon-RCA",
    "scan_anomalies_tool": "scan_anomalies_tool_mcp_Clickathon-RCA",
    "detect_day": "detect_day_mcp_Clickathon-RCA",
    "expected_baseline": "expected_baseline_mcp_Clickathon-RCA",
    "decompose_day": "decompose_day_mcp_Clickathon-RCA",
    "drill_dim": "drill_dim_mcp_Clickathon-RCA",
    "drill_combo_tool": "drill_combo_tool_mcp_Clickathon-RCA",
    "segment_scan_tool": "segment_scan_tool_mcp_Clickathon-RCA",
    "localize_day": "localize_day_mcp_Clickathon-RCA",
    "investigate_day": "investigate_day_mcp_Clickathon-RCA",
    "list_langfuse_sessions_tool": "list_langfuse_sessions_tool_mcp_Clickathon-RCA",
    "get_langfuse_session_tool": "get_langfuse_session_tool_mcp_Clickathon-RCA",
    "list_langfuse_clickhouse_queries_tool": "list_langfuse_clickhouse_queries_tool_mcp_Clickathon-RCA",
    "get_latest_langfuse_trace_tool": "get_latest_langfuse_trace_tool_mcp_Clickathon-RCA",
    "get_langfuse_trace_tool": "get_langfuse_trace_tool_mcp_Clickathon-RCA",
}
CH = {
    "list_databases": "list_databases_mcp_ClickHouse-Cloud-MCP",
    "list_tables": "list_tables_mcp_ClickHouse-Cloud-MCP",
    "run_select_query": "run_select_query_mcp_ClickHouse-Cloud-MCP",
}

GLOSSARY_HINT = """
## Metrics glossary (locked repo — no general GitHub access)
Official docs are ONLY from sidagarwal04/click-a-thon-2026 via:
- `get_metrics_glossary_tool` → InMobi/metrics_glossary.md
- `get_clickathon_github_file` → any path in that repo only (e.g. InMobi/…)
Do NOT ask for other GitHub owners/repos — those tools reject them.
Rules: sum/sum ratios; Revenue ≈ Requests × Fill × eCPM/1000; NAM not NA;
advertiser dims only on fills; same-weekday baselines.
"""

STORE_HINT = """
## Precomputed ClickHouse-native RCA tables (do not invent anomalies)
Incidents are assembled entirely in ClickHouse SQL by `clickathon materialize` (dictionaries, seasonality z-scores, gap-and-island clustering, counterfactuals) into eda.rca_* — not by the LLM.
- list_all_anomalies → rca_incidents (catalog / short list)
- explain_anomaly(incident_id|probe_day) → DETAILED multi-section RCA (always use when explaining)
- counterfactual(incident_id|probe_day) → what-if revenues if fill/eCPM/requests stayed at T-7
- plot_anomaly(incident_id, chart=window|factors|counterfactual) → precomputed PNG chart (~1s)
- expected_baseline(day) → ClickHouse simpleLinearRegression expected vs actual (residual_z)
- investigate_day(date) → day pack with explanation + narrative
- detect_day / decompose_day / drill_* → rca_daily_wow / rca_factor_day / rca_segment_day / rca_combo_day
For deeper digs, use ClickHouse MCP `run_select_query` on those tables or ad_events.
"""

DEEP_RCA_HINT = """
## Detailed RCA (required when explaining why something broke)
Do NOT stop at the one-line list summary.
1. list_all_anomalies (if needed) to get incident ids / probe days.
2. For EACH anomaly you explain, call `explain_anomaly` with that incident_id (preferred) or probe_day.
3. Then call `counterfactual(incident_id=...)` and include the what-if revenue numbers.
4. Call `plot_anomaly(incident_id=..., chart='window')` so the user sees a chart.
   Also plot `factors` and/or `counterfactual` when those sections matter.
   Do NOT invent Chart.js, Mermaid, or HTML artifacts for charts.
   If the image does not render in chat, paste the tool's `markdown` URL line.
5. Present the tool's `explanation` sections in full (Diagnosis → Method), or the `narrative` if present.
6. Cover: global WoW, factor shares, primary segment, counterfactual, window days, ruled out.
7. Quote ONLY tool numbers. Never invent segments or percentages.
"""

LANGFUSE_HINT = """
## Langfuse traces (user can ask "give me the trace for this")
When the user asks for the trace / Langfuse / what ran / verify this:
1. Call `get_latest_langfuse_trace_tool` (no id needed for "this").
2. Present clearly: langfuse_url, user_question, tools_and_steps, clickhouse_queries, final_answer.
If they paste a trace_id → `get_langfuse_trace_tool(trace_id)`.
Also available: list_langfuse_sessions_tool, get_langfuse_session_tool, list_langfuse_clickhouse_queries_tool.
"""

ORCH_INSTRUCTIONS = f"""You are the InMobi RCA Orchestrator for Click-a-thon 2026.

You coordinate specialist subagents AND MCP tools (Clickathon-RCA, ClickHouse).
Baseline = same weekday −7. Identity: Revenue ~= Requests × Fill × eCPM/1000.
NEVER invent numbers or incidents — only quote tool/subagent JSON. Prefer eda. Do not mutate data.
{GLOSSARY_HINT}
{STORE_HINT}
{DEEP_RCA_HINT}
{LANGFUSE_HINT}
## When the user asks "what are the anomalies" / "scan everything" / no date
1. ALWAYS call `list_all_anomalies` (reads rca_incidents).
2. For each incident, call `explain_anomaly(incident_id=...)` then `counterfactual(incident_id=...)`
   then `plot_anomaly(incident_id=..., chart='window')`.
3. Do NOT invent extra incidents; do not list recoveries.

## When the user gives a date or asks why something broke
1. Call `explain_anomaly(probe_day=date)` and/or `investigate_day(date)`.
2. Optionally spawn Factor / Localizer for extra drills.
3. Narrate from tool JSON only; dig with ClickHouse MCP if needed.

## When the user asks about metric definitions / formulas
Call `get_metrics_glossary_tool` (or `get_clickathon_github_file` for other InMobi/ docs).

## When the user asks to verify / show Langfuse / "give me the trace for this"
Call `get_latest_langfuse_trace_tool` and present the card (URL, tools, SQL, answer).
If they give a trace_id, use `get_langfuse_trace_tool`.
"""

DETECTOR_INSTRUCTIONS = f"""You are the RCA Detector.
When asked for anomalies, ALWAYS call `list_all_anomalies` (rca_incidents).
Then for EACH incident call `explain_anomaly(incident_id=...)` and present the detailed explanation.
Do not invent incidents. Do not add recovery days.
Only use `scan_anomalies_tool` if the user explicitly wants raw day-level wow flags.
{GLOSSARY_HINT}
{STORE_HINT}
{DEEP_RCA_HINT}
"""

FACTOR_INSTRUCTIONS = f"""You are the RCA Factor Analyst.
Call `get_metrics_glossary_tool` if formulas are in doubt, then `decompose_day` (rca_factor_day).
For a full write-up of a day, also call `explain_anomaly(probe_day=...)`.
Quote only tool numbers. Identity: Revenue ~= Requests × Fill × eCPM/1000.
Report primary_factor and shares. CTR is context, not a revenue factor.
{GLOSSARY_HINT}
{STORE_HINT}
{DEEP_RCA_HINT}
"""

LOCALIZER_INSTRUCTIONS = f"""You are the RCA Localizer.
Use `localize_day`, `drill_dim`, `drill_combo_tool` (from rca_segment_day / rca_combo_day).
For a full write-up, call `explain_anomaly(probe_day=...)` which already ranks supporting segments.
Rank by impact. No advertiser dims for fill (glossary: advertiser_id empty when unfilled).
Numbers from tools only. Region code NAM not NA. Dig deeper via ClickHouse MCP if needed.
{GLOSSARY_HINT}
{STORE_HINT}
{DEEP_RCA_HINT}
"""

AGENTS = [
    {
        "key": "detector",
        "name": "RCA Detector",
        "description": "Scans the full eda dataset (or a range) for same-DOW anomalies",
        "instructions": DETECTOR_INSTRUCTIONS,
        "tools": [
            RCA["get_metrics_glossary_tool"],
            RCA["get_clickathon_github_file"],
            RCA["list_all_anomalies"],
            RCA["explain_anomaly"],
            RCA["counterfactual"],
            RCA["plot_anomaly"],
            RCA["scan_anomalies_tool"],
            RCA["detect_day"],
            RCA["expected_baseline"],
            CH["run_select_query"],
            CH["list_tables"],
        ],
        "starters": [
            "What are the anomalies across the entire dataset?",
            "Explain anomaly C in detail",
            "Scan 2026-06-19 to 2026-06-30 for anomalies",
            "Plot the window chart for anomaly A",
        ],
    },
    {
        "key": "factor",
        "name": "RCA Factor Analyst",
        "description": "Decomposes revenue WoW into requests vs fill vs eCPM",
        "instructions": FACTOR_INSTRUCTIONS,
        "tools": [
            RCA["get_metrics_glossary_tool"],
            RCA["get_clickathon_github_file"],
            RCA["decompose_day"],
            RCA["detect_day"],
            RCA["expected_baseline"],
            RCA["explain_anomaly"],
            RCA["counterfactual"],
            RCA["plot_anomaly"],
        ],
        "starters": ["Decompose 2026-06-23", "What is eCPM per the official glossary?"],
    },
    {
        "key": "localizer",
        "name": "RCA Localizer",
        "description": "Localizes incidents to OS/region/format segments",
        "instructions": LOCALIZER_INSTRUCTIONS,
        "tools": [
            RCA["get_metrics_glossary_tool"],
            RCA["get_clickathon_github_file"],
            RCA["localize_day"],
            RCA["drill_dim"],
            RCA["drill_combo_tool"],
            RCA["segment_scan_tool"],
            RCA["explain_anomaly"],
            RCA["counterfactual"],
            RCA["plot_anomaly"],
            CH["run_select_query"],
        ],
        "starters": ["Localize the fill drop on 2026-06-23"],
    },
    {
        "key": "orchestrator",
        "name": "InMobi RCA Orchestrator",
        "description": "Coordinates Detector → Factor → Localizer; full RCA",
        "instructions": ORCH_INSTRUCTIONS,
        "tools": list(RCA.values()) + list(CH.values()),
        "starters": [
            "What are the anomalies?",
            "Explain the Android 15 fill drop in detail",
            "Show the counterfactual for anomaly C",
            "Plot charts for anomaly A",
            "Investigate 2026-06-23 and explain the root cause",
            "Quote the official fill rate and eCPM definitions from the glossary",
            "List recent Langfuse sessions and verify the latest one's tools and SQL",
            "Give me the trace for this",
        ],
    },
]

SPEC_MAP = {
    "orchestrator": "inmobi-rca-orchestrator",
    "detector": "inmobi-rca-detector",
    "factor": "inmobi-rca-factor",
    "localizer": "inmobi-rca-localizer",
}


def load_env() -> dict[str, str]:
    out: dict[str, str] = {}
    if not ENV.exists():
        return out
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def client_for(base: str) -> httpx.Client:
    return httpx.Client(
        base_url=base,
        timeout=90.0,
        follow_redirects=True,
        headers={"User-Agent": UA},
    )


def login(c: httpx.Client, email: str, password: str) -> str:
    c.get("/")
    r = c.post(
        "/api/auth/login",
        json={"email": email, "password": password},
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    r.raise_for_status()
    token = r.json().get("token") or ""
    if not token:
        raise RuntimeError(f"no token: {r.text[:300]}")
    c.cookies.set("token", token)
    return token


def auth_headers(base: str, token: str, cookies: httpx.Cookies) -> dict[str, str]:
    h = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": base,
        "Referer": f"{base}/c/new",
        "User-Agent": UA,
    }
    for name, val in cookies.items():
        if "csrf" in name.lower():
            h["x-csrf-token"] = val
            h["X-CSRFToken"] = val
    return h


def list_agents(c: httpx.Client, headers: dict[str, str]) -> dict[str, dict]:
    r = c.get("/api/agents", headers=headers)
    r.raise_for_status()
    body = r.json()
    items = body.get("data") if isinstance(body, dict) else body
    out: dict[str, dict] = {}
    for a in items or []:
        if isinstance(a, dict) and a.get("name") and a.get("id"):
            out[a["name"]] = a
    return out


def upsert_agent(
    c: httpx.Client,
    headers: dict[str, str],
    *,
    existing: dict | None,
    spec: dict,
    model: str,
) -> str:
    payload = {
        "name": spec["name"],
        "description": spec["description"],
        "instructions": spec["instructions"],
        "provider": "openAI",
        "model": model,
        "tools": spec["tools"],
        "category": "general",
        "conversation_starters": spec.get("starters") or [],
    }
    if existing and existing.get("id"):
        aid = existing["id"]
        r = c.patch(f"/api/agents/{aid}", headers=headers, json=payload)
        if r.status_code >= 400:
            raise RuntimeError(f"PATCH {spec['name']}: {r.status_code} {r.text[:400]}")
        print(f"updated {spec['name']} -> {aid}")
        return aid
    r = c.post("/api/agents", headers=headers, json=payload)
    if r.status_code >= 400:
        raise RuntimeError(f"POST {spec['name']}: {r.status_code} {r.text[:400]}")
    aid = r.json().get("id")
    print(f"created {spec['name']} -> {aid}")
    return aid


def wire_orchestrator_subagents(
    c: httpx.Client,
    headers: dict[str, str],
    orch_id: str,
    child_ids: list[str],
) -> None:
    payload = {
        "subagents": {
            "enabled": True,
            "allowSelf": False,
            "agent_ids": child_ids,
        }
    }
    r = c.patch(f"/api/agents/{orch_id}", headers=headers, json=payload)
    if r.status_code >= 400:
        # older shape: top-level agent_ids
        r2 = c.patch(
            f"/api/agents/{orch_id}",
            headers=headers,
            json={"agent_ids": child_ids, "subagents": payload["subagents"]},
        )
        if r2.status_code >= 400:
            raise RuntimeError(
                f"wire subagents failed: {r.status_code} {r.text[:300]} | "
                f"{r2.status_code} {r2.text[:300]}"
            )
        print(f"wired orchestrator subagents (fallback) -> {child_ids}")
        return
    print(f"wired orchestrator subagents -> {child_ids}")


def delete_probe_agents(c: httpx.Client, headers: dict[str, str], by_name: dict[str, dict]) -> None:
    for name, a in list(by_name.items()):
        if "Probe" in name:
            aid = a["id"]
            d = c.delete(f"/api/agents/{aid}", headers=headers)
            print(f"deleted probe {name} ({d.status_code})")


def patch_yaml(ids: dict[str, str]) -> None:
    text = YAML.read_text(encoding="utf-8")

    # Ensure orchestrator modelSpec uses agents endpoint + agent_id + subagents
    orch = ids.get("orchestrator", "")
    det, fac, loc = ids.get("detector", ""), ids.get("factor", ""), ids.get("localizer", "")

    # Replace entire modelSpecs list with connected agents version
    new_specs = f"""modelSpecs:
  prioritize: true
  enforce: false
  addedEndpoints:
    - agents
    - openAI
  list:
    - name: "inmobi-rca-orchestrator"
      label: "InMobi RCA Orchestrator"
      description: "Delegates to Detector / Factor / Localizer; full-dataset anomaly scan"
      default: true
      mcpServers:
        - Clickathon-RCA
        - ClickHouse-Cloud-MCP
      subagents:
        enabled: true
        allowSelf: false
        agent_ids:
          - "{det}"
          - "{fac}"
          - "{loc}"
      preset:
        endpoint: "agents"
        agent_id: "{orch}"
        model: "gpt-5.6-sol"

    - name: "inmobi-rca-detector"
      label: "RCA Detector"
      description: "Full-dataset or ranged same-DOW anomaly scan"
      mcpServers:
        - Clickathon-RCA
        - ClickHouse-Cloud-MCP
      preset:
        endpoint: "agents"
        agent_id: "{det}"
        model: "gpt-5.6-sol"

    - name: "inmobi-rca-factor"
      label: "RCA Factor Analyst"
      description: "Requests vs fill vs eCPM decomposition"
      mcpServers:
        - Clickathon-RCA
      preset:
        endpoint: "agents"
        agent_id: "{fac}"
        model: "gpt-5.6-sol"

    - name: "inmobi-rca-localizer"
      label: "RCA Localizer"
      description: "Dimension and combo contribution drill"
      mcpServers:
        - Clickathon-RCA
        - ClickHouse-Cloud-MCP
      preset:
        endpoint: "agents"
        agent_id: "{loc}"
        model: "gpt-5.6-sol"
"""

    # Swap from modelSpecs: through endpoints: (keep endpoints block)
    m = re.search(r"(?ms)^modelSpecs:.*?^(?=endpoints:)", text)
    if not m:
        raise RuntimeError("could not find modelSpecs block in librechat.yaml")
    text = text[: m.start()] + new_specs + "\n" + text[m.end() :]
    YAML.write_text(text, encoding="utf-8")
    print(f"Updated {YAML}")


def main() -> int:
    env = load_env()
    base = os.environ.get("LIBRECHAT_URL", "http://localhost:3080").rstrip("/")
    email = env.get("LIBRECHAT_USER_EMAIL", "admin@clickathon.local")
    password = env.get("LIBRECHAT_USER_PASSWORD", "")
    model = env.get("OPENAI_MODEL", "gpt-5.6-sol")
    if not password:
        print("LIBRECHAT_USER_PASSWORD missing", file=sys.stderr)
        return 1

    with client_for(base) as c:
        token = login(c, email, password)
        headers = auth_headers(base, token, c.cookies)
        existing = list_agents(c, headers)
        delete_probe_agents(c, headers, existing)
        existing = list_agents(c, headers)

        ids: dict[str, str] = {}
        # Create specialists first, then orchestrator
        order = ["detector", "factor", "localizer", "orchestrator"]
        by_key = {a["key"]: a for a in AGENTS}
        for key in order:
            spec = by_key[key]
            prev = existing.get(spec["name"])
            ids[key] = upsert_agent(c, headers, existing=prev, spec=spec, model=model)

        wire_orchestrator_subagents(
            c,
            headers,
            ids["orchestrator"],
            [ids["detector"], ids["factor"], ids["localizer"]],
        )

    patch_yaml(ids)
    print(json.dumps({SPEC_MAP[k]: v for k, v in ids.items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
