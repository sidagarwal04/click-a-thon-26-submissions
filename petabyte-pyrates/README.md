# Petabyte Pyrates

## Track

InMobi — *From alert to answer: the automated root-cause analyst*

## Project

**InMobi RCA Agent** — Automated root-cause analysis for ad metric anomalies. ClickHouse computes every number; a ClickHouse Cloud Agent narrates from evidence and writes back to `gold.metric_anomalies` via Lambda MCP.

## Team Members

- ayushrajchauhan99@gmail.com
- bharath.8199@gmail.com

## What it does

1. **Detect** — hourly baselines (same day-of-week/hour) plus Rule Z + STL agreement flag confirmed anomalies into `gold.metric_anomalies`.
2. **Drill down** — dimensional contribution analysis runs as ClickHouse SQL on `gold.metric_hourly_by_slice` (region, format, app, device, advertiser).
3. **Diagnose** — the agent calls `get_ontology`, queries evidence, and writes `rca_description` + `evidence_json` via `close_anomaly_investigation`. The LLM narrates only from query results.

## Hosted Demo

<!-- TODO: add live demo URL and any judge credentials -->
**Anomaly Radar** — local ops UI for `gold.metric_anomalies` (screenshots in [`docs/assets/anomaly-radar/`](docs/assets/anomaly-radar/)):

```bash
uv sync --extra ops-ui
cp .env.example .env   # CLICKHOUSE_HOST, CLICKHOUSE_PASSWORD
inmobi-ops-ui          # http://localhost:8080
```

**[ClickHouse Agent Builder](https://ai.clickhouse.cloud)** — open **InMobi RCA Agent** and paste a test prompt from [`docs/AGENT_BUILDER.md`](docs/AGENT_BUILDER.md).

| Item | Value |
|------|-------|
| Agent ID | `agent_wUl6a8LPgFzInR31naXSz` |
| Test prompt | See `docs/AGENT_BUILDER.md` §3 |

## Demo Video

[`petabyte.mp4`](petabyte.mp4) (~13 min) — metric drops → anomaly in queue → agent investigates → plain-English diagnosis.

## Pitch Deck

<!-- TODO: export PDF and commit as pitch-deck.pdf -->
[`pitch-deck.pdf`](pitch-deck.pdf) — *add before opening PR*.

## Architecture

Event-driven ingestion from managed Postgres through ClickPipes CDC into ClickHouse, then medallion transforms, anomaly detection, and agent investigation.

**Where analysis runs:** all detection, baselines, slice ranking, and contribution math live in ClickHouse views/tables. The LLM only narrates structured evidence.

```
Hackathon dataset (parquet + csv)
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│ 1. ClickHouse managed Postgres                           │
│    inmobi-ingest → clickathon.ad_events, apps,          │
│    advertisers, geo_device                               │
└────────────────────────────┬─────────────────────────────┘
                             │ ClickPipes (CDC)
                             ▼
┌──────────────────────────────────────────────────────────┐
│ 2. Bronze — default.clickathon_*                         │
└────────────────────────────┬─────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────┐
│ 3. Silver — silver.ad_events_enriched, dim_*              │
└────────────────────────────┬─────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────┐
│ 4. Gold — metrics_hourly_mv, dict_*                      │
└────────────────────────────┬─────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────┐
│ 5. Semantic — metric_hourly_by_slice, baselines          │
└────────────────────────────┬─────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────┐
│ 6. Anomaly — Z + STL → metric_anomalies (RCA queue)     │
└────────────────────────────┬─────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────┐
│ 7. ClickHouse Cloud Agent + Lambda MCPs                  │
│    get_ontology → SELECT evidence → close_anomaly_       │
│    investigation                                         │
└──────────────────────────────────────────────────────────┘
```

### Anomaly detection approach

| Stage | Object | Method |
|-------|--------|--------|
| Baseline | `gold.baseline_hour_of_week` | Same DOW/hour, 14-day trailing window |
| Candidates | `gold.metric_anomaly_candidates` | Rule Z + Rule R |
| Seasonality | `gold.metric_anomaly_stl` | STL decomposition + Tukey on residuals |
| Confirmed | `gold.metric_anomaly_confirmed` | Z ∧ STL ∧ volume gate |
| Queue | `gold.metric_anomalies` | Hourly sync MV; agent writeback |

See [`clickhouse/anomaly/README.md`](clickhouse/anomaly/README.md) and [`solution.md`](solution.md) for full design rationale.

### OSS integration (ClickHouse Cloud Agent + MCP)

| Tool | Role | Evidence in this repo |
|------|------|------------------------|
| **ClickHouse Cloud Agent** | RCA narrator + SQL executor | [`docs/AGENT_BUILDER.md`](docs/AGENT_BUILDER.md), agent instructions, Agents API example |
| **Lambda MCP — ontology** | `get_ontology` before any SELECT | [`src/inmobi_ch_mcp_ontology/`](src/inmobi_ch_mcp_ontology/) + `config/glossary_ontology.yaml` |
| **Lambda MCP — writeback** | `close_anomaly_investigation` | [`src/inmobi_ch_mcp_writeback/`](src/inmobi_ch_mcp_writeback/) |

**LLM:** ClickHouse Cloud Agent (hosted on ClickHouse AI). Chosen so investigation SQL runs against the team's ClickHouse service with ontology constraints enforced via MCP.

<!-- TODO: if using Langfuse, add public trace share links or JSON exports under langfuse-traces/ -->

## How we built it

- **ClickHouse Cloud** — primary datastore and analytical engine (medallion DDL in `clickhouse/`)
- **Managed Postgres + ClickPipes** — CDC ingestion path
- **Python / uv** — bulk load CLI (`inmobi-ingest`), ontology packaging, Lambda MCP handlers
- **AWS Lambda** — streamable HTTP MCP servers for ontology + writeback
- **ClickHouse Agent Builder** — investigation agent with mandatory ontology-first workflow
- **Anomaly Radar** — FastAPI ops UI (`inmobi-ops-ui`) for live anomaly queue + RCA review

## How to run it

### 1. Load Postgres

```bash
uv sync
cp .env.example .env          # DATABASE_URL for managed Postgres
inmobi-ingest init-db --drop
inmobi-ingest load --data-dir /path/to/InMobi/data
inmobi-ingest status
```

### 2. Enable ClickPipes CDC → ClickHouse bronze

Configure ClickPipes on ClickHouse Cloud to replicate `clickathon.*` from managed Postgres into `default.clickathon_*`. Bronze tables are created by the ClickPipes destination (see [`clickhouse/bronze/`](clickhouse/bronze/)).

### 3. Apply ClickHouse transforms

Run DDL in layer order: silver → gold → semantic → anomaly. See [`clickhouse/README.md`](clickhouse/README.md).

```bash
clickhouse-client < clickhouse/silver/00_database.sql
for f in clickhouse/silver/[1-9]*.sql; do clickhouse-client < "$f"; done
clickhouse-client < clickhouse/gold/00_database.sql
clickhouse-client < clickhouse/semantic/01_metrics_hourly.sql
for f in clickhouse/gold/[1-9]*.sql; do clickhouse-client < "$f"; done
clickhouse-client < clickhouse/semantic/02_metric_hourly_by_slice.sql
for f in clickhouse/anomaly/*.sql; do clickhouse-client < "$f"; done
```

After bulk load, refresh anomaly MVs:

```sql
SYSTEM REFRESH VIEW gold.baseline_hour_of_week_mv;
SYSTEM REFRESH VIEW gold.metric_anomalies_sync_mv;
```

### 4. Deploy MCP servers + agent

```bash
# .env also needs CLICKHOUSE_HOST, CLICKHOUSE_PASSWORD
./src/inmobi_ch_mcp_ontology/deploy.sh
./src/inmobi_ch_mcp_writeback/deploy.sh
```

Create the agent in Agent Builder using [`docs/AGENT_BUILDER.md`](docs/AGENT_BUILDER.md). Attach both Lambda Function URLs (Bearer auth from each package's `.mcp_auth_token`).

### 5. Investigate

Pick an open `anomaly_id` from `gold.metric_anomalies`, then chat in Agent Builder or call the [Agents API](https://ai.clickhouse.cloud).

### 6. Anomaly Radar (ops UI)

```bash
uv sync --extra ops-ui
inmobi-ops-ui   # http://localhost:8080
```

Browse detected anomalies, filter by status/disposition, and inspect RCA + evidence JSON in the detail panel.

## Unseen incident bundle

Mandatory at code freeze — see [`unseen-incident/README.md`](unseen-incident/README.md).

## Repository layout

```
config/glossary_ontology.yaml   # Ontology served by get_ontology MCP
clickhouse/                     # Medallion DDL (bronze → … → anomaly)
docs/AGENT_BUILDER.md           # Agent Builder copy-paste fields
src/
  inmobi_ingest/                # Postgres bulk load CLI
  inmobi_ontology/              # YAML → dict (ontology Lambda deploy)
  inmobi_ch_mcp_ontology/       # Lambda MCP — get_ontology
  inmobi_ch_mcp_writeback/      # Lambda MCP — close_anomaly_investigation
  inmobi_ops_ui/                # Anomaly Radar — FastAPI UI for metric_anomalies
unseen-incident/                # Code-freeze outputs (diagnosis + traces)
docs/assets/anomaly-radar/      # Demo screenshots
tests/
```

## Development

```bash
uv sync --extra dev
uv run ruff check src tests
uv run pytest
```

## Further reading

- [`clickhouse/README.md`](clickhouse/README.md) — DDL apply order, RCA read targets
- [`docs/AGENT_BUILDER.md`](docs/AGENT_BUILDER.md) — agent instructions, agent ID, API test
- [`solution.md`](solution.md) — problem statement alignment and design decisions
