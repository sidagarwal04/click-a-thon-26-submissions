# Fastlane

## Track

InMobi — *Automated root-cause analyst*

## Project

**InMobi Revenue RCA** — a ClickHouse-first pipeline that detects mobile-ad
revenue anomalies as data lands, attributes them to the responsible factor and
segment, and produces a reproducible diagnosis.

## Team Members

- Haridas Narayanaswamy (`https://github.com/haridas`)
- Adithya Ramanathan (`https://github.com/adithya-r-nathan`)
- Richard Paul Varghese (`https://github.com/aza-cloud-stack`)
- Tejaswini Ramesh (`https://github.com/TEJASWINIRAMESH`)

## What it does

The pipeline models the exact identity:

```text
Revenue = Requests × Fill rate × Render rate × eCPM / 1,000
```

Raw events land once in ClickHouse. Materialized views create the rollups,
driver-based expected values, alerts, and drill-down tables used to explain a
movement. ClickHouse performs the analytical work: dimension ranking, segment
attribution, LMDI revenue decomposition, and rate-versus-mix analysis.

For the released unseen slice, it found two P1 incidents:

- **iOS 17.5 fill-rate collapse** — fill rate moved from `0.792` to `0.478`
  (`−39.7%`), contributing `−$66.00`.
- **Video eCPM collapse** — video eCPM moved from `$6.03` to `$4.23` (`−29.9%`),
  contributing `−$93.74` before rewarded-format displacement.

The quantified evidence and ruled-out alternatives are in
[DIAGNOSIS.md](DIAGNOSIS.md).

## Hosted Demo

https://drive.google.com/file/d/1JwG0B9ynppGyDsxW7wcb1tdy1_hRbsWm/view?usp=sharing

## Demo Video

**Add the public 2–3 minute demo-video URL before submission.**

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the diagram, data model,
anomaly-detection method, attribution approach, trust checks, and reproducible
ClickHouse queries.

## Unseen Incident Evidence

- [Full unseen-incident diagnosis](DIAGNOSIS.md) — diagnoses, quantified
  findings, factor attribution, clean-day checks, and ruled-out alternatives.
- [Agent execution evidence](outputs/llm_agent.json) — diagnosis JSON and the
  two ClickHouse drill-down queries for the video eCPM incident.
- [Exported Langfuse traces](outputs/langfuse_traces.json) — committed trace
  export; judges do not need access to our Langfuse project.
- [Alert fired](outputs/Alert_fire.jpeg), [agent execution 1](outputs/Agent_Executor_1.jpeg),
  [agent execution 2](outputs/Agent_Executor_2.jpeg), and [LibreChat RCA
  screenshot](outputs/Librechat_RCA_1.jpeg).

## How we built it

- **ClickHouse Cloud** is the primary datastore and analytical engine.
  `ad_events` holds the unified 10.5M-event fact table; materialized views build
  minute totals, marginal hourly rollups, and an OS × country cross.
- **Detection and attribution** use driver-keyed median baselines, binomial
  rate scoring, relative eCPM scoring, median/MAD request-volume detection,
  concentration ranking, rate/mix decomposition, and exact LMDI attribution.
- **ClickStack / HyperDX** creates a ClickHouse source over confirmed alerts, a
  saved search, and a webhook to the RCA agent. Provisioning and demo-trigger
  scripts are included in `src/`.
- **Langfuse** traces the LLM agent and its ClickHouse tool calls.
- **LibreChat** provides analyst-facing follow-up investigations. Its redacted
  configuration is committed at [src/librechat_config.yaml](src/librechat_config.yaml).
- **Anthropic Claude Haiku 4.5 via LangChain** narrates constrained,
  ClickHouse-backed results; it is not the analytical engine.

## How to run it

### 1. Build the ClickHouse pipeline

Run the schema files in order against ClickHouse Cloud:

```bash
clickhouse client --secure --host <host> --port 9440 --user default --password '<password>' \
  --multiquery < schemas/u01_schema.sql
clickhouse client --secure --host <host> --port 9440 --user default --password '<password>' \
  --multiquery < schemas/u02_pipeline.sql
clickhouse client --secure --host <host> --port 9440 --user default --password '<password>' \
  --multiquery < schemas/u03_baselines.sql
clickhouse client --secure --host <host> --port 9440 --user default --password '<password>' \
  --multiquery < schemas/u04_alerts.sql
clickhouse client --secure --host <host> --port 9440 --user default --password '<password>' \
  --multiquery < schemas/u05_rca_scan.sql
```

Load the dimension CSVs before `ad_events`; otherwise materialized-view
dictionary lookups resolve to `unknown`. [README-real.md](README-real.md)
contains the detailed onboarding, batch-aware dimensions, and backfill notes.

### 2. Reproduce the unseen-slice findings

```sql
SELECT * FROM `inmobi-hari`.v_incidents_unseen;

SELECT * FROM `inmobi-hari`.rca_scan(
  test_from = '2026-07-08', test_to = '2026-07-09',
  base_from = '2026-07-06', base_to = '2026-07-07',
  metric = 'fill_rate'
);

SELECT * FROM `inmobi-hari`.rca_seg(
  test_from = '2026-07-09', test_to = '2026-07-10',
  base_from = '2026-07-06', base_to = '2026-07-07',
  metric = 'ecpm', dim = 'ad_format'
);
```

### 3. Run the webhook agent (optional live alert flow)

The committed webhook agent is the separate HyperDX demo path. It expects the
`inmobi_unseen` tables named in its source (`alerts_live`,
`alerts_live_confirmed`, `rca_dimscan`, and `rca_segments`); the self-contained
unseen-slice analysis above uses the `inmobi-hari` SQL pipeline.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r src/requirements.txt

export CH_HOST="<clickhouse-host>"
export CH_PORT="8443"
export CH_USER="default"
export CH_PASSWORD="<clickhouse-password>"
export CH_DATABASE="inmobi_unseen"
export CH_SECURE="true"
export ANTHROPIC_API_KEY="<anthropic-api-key>"
export LANGFUSE_PUBLIC_KEY="<langfuse-public-key>"
export LANGFUSE_SECRET_KEY="<langfuse-secret-key>"
export LANGFUSE_HOST="<langfuse-host>"

python -m src.llm_rca_agent
```

For HyperDX provisioning and verified alert replay, use `src/setup_hyperdx.sh`
and `src/trigger_demo_alert.sh`. Never commit credentials.

## Submission Artifacts

- [Architecture](ARCHITECTURE.md)
- [Unseen incident diagnosis](DIAGNOSIS.md)
- [Data onboarding and method notes](README-real.md)
- [Pitch deck](rca-overview-deck.pdf)
- [Source SQL](schemas)

## Future Plan
Currently, we send the RCA to the ClickHouse database. In the future, we will send it to Slack instead.
