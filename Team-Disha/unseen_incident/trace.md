# Trace — unseen incident run

Proves the system generated the Day-2 diagnosis (LibreChat → RCA MCP → ClickHouse `eda.rca_*`).

**Public links:** the Langfuse traces below are shared as public (viewable without project membership).

## Primary Langfuse links

| Kind | Id / URL |
|---|---|
| **LibreChat session** | `ff2cd583-a52d-4b4a-95d3-d7e8d1353bda` |
| **Agent trace** | https://cloud.langfuse.com/project/cmsa43v7s02uoad0dhpcr2e4s/traces/9d61f5d41486e4791073527a9a1b5938 |
| **RCA SQL (incident B explain)** | https://cloud.langfuse.com/project/cmsa43v7s02uoad0dhpcr2e4s/traces/86a312da7460a86ca09add3ab722563f |
| **RCA SQL (incident C explain)** | https://cloud.langfuse.com/project/cmsa43v7s02uoad0dhpcr2e4s/traces/bd4d027186aabc34f4740375732ab370 |

Offline export of the same session/traces: [`langfuse/`](./langfuse/).

## What the run called

LibreChat **InMobi RCA Orchestrator** (unseen Jul 6–10 `eda`):

1. `list_all_anomalies` → 3 incidents A/B/C from `rca_incidents` (bounds 2026-07-06 … 2026-07-10)
2. `explain_anomaly` / `counterfactual` per incident (ClickHouse reads on `rca_daily_wow`, `rca_segment_day`, `rca_combo_day`, `rca_counterfactual`, `rca_ml_expected`)

Sample SQL observations (from session):

- `SELECT * FROM rca_counterfactual WHERE incident_id = 'B'`
- `SELECT * FROM rca_daily_wow WHERE event_date BETWEEN '2026-07-08' AND '2026-07-09'`
- `SELECT * FROM rca_combo_day WHERE event_date = '2026-07-08' …`
- `SELECT * FROM rca_ml_expected WHERE event_date = '2026-07-08'`

## How to re-verify

In LibreChat after the same load:

```
Give me the trace for this
```

Or CLI / MCP: `get_langfuse_session_tool(session_id='ff2cd583-a52d-4b4a-95d3-d7e8d1353bda')`.
