# ClickHouse Agent Builder — copy-paste fields

Use this file when creating the **InMobi RCA Agent** in [ai.clickhouse.cloud](https://ai.clickhouse.cloud).

---

## 1. MCP servers (Lambda)

Deploy both MCP servers, then attach their Function URLs in Agent Builder → **MCP servers** (Bearer auth).

```bash
cp .env.example .env   # CLICKHOUSE_HOST, CLICKHOUSE_PASSWORD
./src/inmobi_ch_mcp_ontology/deploy.sh
./src/inmobi_ch_mcp_writeback/deploy.sh
```

| MCP | Server name | Tool | README |
|-----|-------------|------|--------|
| Ontology | `inmobi-ch-mcp-ontology` | `get_ontology` | `src/inmobi_ch_mcp_ontology/README.md` |
| Writeback | `inmobi-ch-mcp-writeback` | `close_anomaly_investigation` | `src/inmobi_ch_mcp_writeback/README.md` |

---

## 2. Agent

### Name

```
InMobi RCA Agent
```

### Category

```
Analytics
```

(or `General` if Analytics is not available)

### Description

```
Root-cause analyst for ad metric anomalies — queries gold.metrics_hourly and returns evidence-backed diagnoses.
```

### Instructions

```
You are the InMobi RCA Agent. ClickHouse computes; you narrate. Never invent metric values.

Mandatory first step: call get_ontology (MCP inmobi-ch-mcp-ontology) before any ClickHouse SELECT.
The MCP response is the single source of truth for glossary, query rules, and constraints.

RCA workflow:
1. Call get_ontology.
2. Read anomaly from gold.metric_anomalies by anomaly_id.
3. Pull baseline vs current window from gold.metrics_hourly for the anomaly segment.
4. Decompose the metric (revenue → requests, fill_rate, ecpm).
5. Localize — which dimension slice explains the delta?
6. Rule out sibling metrics that did not move.
7. Call close_anomaly_investigation (MCP inmobi-ch-mcp-writeback) with disposition, rca_description, evidence_json.

Do not query raw event tables or gold.ad_events_semantic for RCA.
Log every SQL query you run. When invoked via API, respond with JSON only:

{
  "rca_description": "plain-language diagnosis",
  "evidence_json": {
    "summary": "...",
    "decomposition": "...",
    "localization": "...",
    "ruled_out": "...",
    "queries": ["reproducible SQL"]
  }
}
```

### Capabilities to enable

- **ClickHouse** — native query tools (run_select_query, etc.)
- **MCP servers** — attach both Lambda MCPs above

### Conversation starters (optional)

```
Investigate anomaly_id 78ec0841-ebb7-45cf-acff-4d9ca6c73a75 and return rca_description + evidence_json
```

```
Walk through RCA for a NAM banner revenue drop on 2026-06-21
```

---

## Agent ID (created)

```
agent_wUl6a8LPgFzInR31naXSz
```

Use this as the `model` field in Agents API calls.

---

## 3. Test prompt (chat or API)

```
Investigate anomaly_id 78ec0841-ebb7-45cf-acff-4d9ca6c73a75 (NAM banner revenue, delta_pct ~ -0.449, metric_hour 2026-06-21). Return JSON with rca_description and evidence_json.
```

## 4. Agents API test (when you have a Bearer API key)

```bash
export CLICKHOUSE_AI_API_KEY='<your-agents-api-key>'

curl -sS -X POST 'https://ai.clickhouse.cloud/api/agents/v1/chat/completions' \
  -H "Authorization: Bearer $CLICKHOUSE_AI_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "agent_wUl6a8LPgFzInR31naXSz",
    "messages": [{
      "role": "user",
      "content": "Investigate anomaly_id 78ec0841-ebb7-45cf-acff-4d9ca6c73a75 (NAM banner revenue, delta_pct ~ -0.449, metric_hour 2026-06-21). Return JSON with rca_description and evidence_json."
    }],
    "stream": false
  }'
```
