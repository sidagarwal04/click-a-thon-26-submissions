# Unseen Incident Bundle — sealed slice (Jul 6–10, 2026)

The system's output for the unseen release: 1.5M events loaded into ClickHouse database
`rca_unseen` with the **regenerated** dimension tables from the release (verified
byte-identical to the release CSVs before the run). Nothing here is hand-written — the
pipeline ran once and produced all three artifacts.

| File | What |
|---|---|
| [`DIAGNOSIS.md`](DIAGNOSIS.md) | Plain-language diagnosis, verbatim system output — 3 incidents localized, 55 segments ruled out |
| [`bundle.json`](bundle.json) | Full evidence bundle — every number as `{value, sql, query_id}` (15/15 evidence items carry a `query_id`) |
| [`TRACE.md`](TRACE.md) | Public Langfuse trace link + [`trace_export.json`](trace_export.json) API export fallback |
| [`run_output.txt`](run_output.txt) | Complete console output of the run (incident table + full ruled-out ledger) |

## How it was produced (one command, no code edits)

```bash
python scripts/load_clickhouse.py --database rca_unseen --parquet InMobi/unseen_data/ad_events.parquet
python run_incident.py --db rca_unseen --rebuild-cube --narrate --trace \
                       --json unseen-incident/bundle.json
```

Scan wall clock: **9.9 s** over the pre-aggregated cube (724,007 rows from 1.5M events).
Reproduce any number by running the SQL stored next to it in `bundle.json`; its
`query_id` matches the span in the Langfuse trace.
