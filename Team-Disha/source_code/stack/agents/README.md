# InMobi RCA — multi-agent design (LibreChat)

## Goal
Detect metric anomalies on `eda.*`, localize segments, explain in natural language with
**ClickHouse-backed numbers only** (hackathon criteria).

## Agents (connected)

| Agent | Role | Primary tools |
|---|---|---|
| **RCA Orchestrator** | Coordinates specialists; final narrative | subagent spawn + `investigate_day` / `list_all_anomalies` |
| **RCA Detector** | Full-dataset or ranged same-DOW scan | `list_all_anomalies`, `scan_anomalies_tool`, `detect_day` |
| **Factor Analyst** | Revenue identity | `decompose_day` |
| **Localizer** | Dim + combo contribution | `drill_dim`, `drill_combo_tool`, `localize_day` |

Orchestrator is configured with LibreChat **subagents** pointing at Detector / Factor / Localizer.
Ask “What are the anomalies?” → Detector (or `list_all_anomalies`) scans **all** loaded days.

Seed / refresh:
```bash
uv run python stack/scripts/seed_librechat_agents.py
docker compose -f stack/docker-compose.yml --env-file .env up -d --force-recreate librechat
```

## Tool servers
1. **Clickathon-RCA** (`rca-mcp:8001`) — deterministic SQL wrappers + Langfuse/OTel spans
2. **ClickHouse-Cloud-MCP** (`clickhouse-mcp:8000`) — ad-hoc SELECT when wrappers are insufficient

## Baseline
Daily same weekday `T` vs `T−7`. Hourly optional only.

## Trust boundary
```text
CH SQL → tool JSON → agent/narrator text
```
Never invent numbers not returned by tools.

## Telemetry
- **Langfuse Cloud**: investigation spans from RCA MCP + LibreChat chat traces
- **ClickStack OTel**: RCA MCP runtime traces → collector `:4318` → Cloud `otel`
