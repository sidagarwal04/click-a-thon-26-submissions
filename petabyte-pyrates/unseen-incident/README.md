# Unseen incident bundle

Investigation outputs for graded runs. **Agent trace is mandatory** — see [`trace/`](trace/).

## Artifacts in this folder

| File / folder | Status |
|---------------|--------|
| [`diagnosis.md`](diagnosis.md) | 9 RCA summaries from `gold.metric_anomalies` |
| [`queries.sql`](queries.sql) | Reproducible ClickHouse SQL |
| [`trace/outstanding-anomalies-analysis.json`](trace/outstanding-anomalies-analysis.json) | ClickHouse Agent export (proof) |
| [`metric_anomalies_rows.json`](metric_anomalies_rows.json) | Full writeback rows (`rca_description`, `evidence_json`) |

## Trace

ClickHouse Agent conversation **Outstanding Anomalies Analysis** — prompt: `analyse outstanding anomalies`.  
See [`trace/README.md`](trace/README.md) for conversation ID and agent ID.

> **Note:** If organizers release a separate surprise dataset at code freeze, re-run the pipeline on that data and add a second trace + diagnoses here before final PR update.
