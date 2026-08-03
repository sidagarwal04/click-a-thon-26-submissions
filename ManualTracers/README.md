# Manual Tracers

## Track
InMobi

## Project
Automated Root-Cause Analyst — a metric moves, the system detects it, drills down
in ClickHouse to isolate the responsible segment, and produces an evidence-backed
diagnosis where every number is computed, not narrated into existence.

## Team Members
- raghvender-1205
- Harsh <!-- TODO: GitHub handle -->

## What it does
A HyperDX alert fires on a metric deviation (global tile or per-dimension marginal
tile) and webhooks into the RCA agent. The agent reproduces the anomaly, decomposes
revenue-style metrics into their funnel factors, scans every depth-1 dimension in
ClickHouse, rules candidates in or out with a z-test and effect-size floors, walks
correlated dependencies, and hands a fully-grounded evidence ledger to an LLM that
only narrates — it never sees a raw row or does arithmetic. Every run is traced in
Langfuse.

## Hosted Demo
<!-- TODO: link to the live, hosted demo (mandatory) -->

## Demo Video
<!-- TODO: link to the recorded 2-3 minute demo video (mandatory) -->

## Architecture
See [architecture.md](architecture.md) and [docs/RCA_AGENT_DESIGN.md](docs/RCA_AGENT_DESIGN.md)
for the full design and reasoning; the summary below is the as-built shape.

- **Architecture:** [architecture.md](architecture.md)
- **As-built RCA agent design:** [docs/RCA_AGENT_DESIGN.md](docs/RCA_AGENT_DESIGN.md)
- **Decomposition math:** [docs/RCA_DECOMPOSITION_MATH.md](docs/RCA_DECOMPOSITION_MATH.md)
- **Problem statement:** [InMobi/PROBLEM_STATEMENT.md](InMobi/PROBLEM_STATEMENT.md)
- **Metric definitions:** [InMobi/metrics_glossary.md](InMobi/metrics_glossary.md)

## Layers

| Layer | Object | Role |
|---|---|---|
| data | `inmobi.ad_events` → `inmobi.ad_events_enriched` | one MV, dictionary-denormalised, `event_time` indexed. Everything reads the second table |
| semantic | `inmobi.metric_def` | `metric_id` · `sql` · `dependencies` (funnel factors) · `z_score_threshold` + guard rails |
| semantic | `inmobi.metric_dim_map` | `(metric_id, dim_id)` · `priority` · `dependencies` (cuts to cross with) |
| detection | `RCA/app/metric_sql.py` | renders a `metric_def` row into one query: hourly series → seasonal baseline → z → `is_anomaly` |
| alert → agent | HyperDX chart on that query → webhook → `RCA/app/` | see [docs/RCA_AGENT_DESIGN.md](docs/RCA_AGENT_DESIGN.md) §3 |

**Nothing is pre-aggregated and nothing is persisted between detection and the
agent.** `metric_def.sql` executes directly against `ad_events_enriched`, and the
detection maths exists in one builder rendered two ways — bound parameters for the
agent, `now()`-relative for HyperDX — so an alert and the investigation behind it
cannot disagree.

## How we built it
- **ClickHouse** as the primary datastore and analytical engine — `ad_events` →
  `ad_events_enriched` (dictionary-denormalised MV), `metric_def` /
  `metric_dim_map` as the semantic layer driving the query builder in
  `RCA/app/metric_sql.py`.
- **ClickStack (HyperDX)** for the alert/dashboard tiles and the webhook that
  triggers the agent.
- **Langfuse** for tracing every investigation end to end.
- **Gemini (via LangChain)** as the narrator LLM — narrates the evidence ledger,
  never computes it.
- **Python (`uv`)** for the RCA agent, **React + Vite** for the RCA report viewer,
  **Node** for the small API serving it.

## How to run it

```bash
cp .env.example .env      # fill in ClickHouse Cloud creds
./scripts/replay.sh       # apply SQL + replay ad_events; MV1 populates the enriched table
```

Modes: `--schema` (DDL only) · `--data` (replay only) · `--dims` (reload dimensions).

```bash
./scripts/metric_query.py alert fill_rate   # SQL to paste into a HyperDX chart
./scripts/metric_query.py scan  fill_rate   # ranked segment scan
cd RCA && uv run pytest -q                  # 39 tests, no ClickHouse needed
```

## RCA viewer (Docker)

```bash
docker compose up --build -d
```

| Service | URL |
|---------|-----|
| RCA UI | http://localhost:8090 |
| RCA API (direct) | http://localhost:3002/health |

Sample reports: Android 15 fill-rate drop, iOS 18.1 cohort. Template spec: [docs/RCA_UI_TEMPLATE.md](docs/RCA_UI_TEMPLATE.md).

**Sealed dataset:** change `AD_EVENTS_FILE` at the top of `scripts/replay.sh`,
truncate manually (helper at the bottom of the script), then re-run. The script
never truncates by itself.

## Confirmed detections

| Day(s) | Segment | Actual | Expected | Peak z |
|---|---|---|---|---|
| Jun 23–25 | `os_version=Android 15` | 0.434 | 0.785 | 28.1 |
| Jun 29–30 | `os_version=iOS 18.1` | 0.683 | 0.780 | 10.6 |
| Jun 23–25 | global fill rate | 0.750 | 0.785 | 11.4 |

Measured over 9M rows before the pipeline was rebuilt without the view chain. The
formulas, baseline and guard rails are unchanged, so these are the numbers to
expect again — re-confirm after ingest rather than quoting them as current.
