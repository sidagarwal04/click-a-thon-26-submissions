---
type: table
title: document_uploaded_daily_agg
description: Pre-aggregated daily rollup of document_uploaded — upload counts, retry sum/avg, and threshold-crossing counts by day × doc_type × capture_mode × scan_mode × device_type × os × destination. Fed by document_uploaded_daily_mv.
kind: aggregate
source_schema: Atlys/schemas/11_document_uploaded.sql
source_metrics: Atlys/schemas/11_document_uploaded.metrics.json
live: true
timestamp: 2026-08-06
tags: [table, aggregate, rollup, document, live]
---

# Purpose

`SharedAggregatingMergeTree` daily rollup of [document_uploaded](/tables/document_uploaded.md).
Serves the doc-friction metrics (M1–M4) without scanning the base table. Fed incrementally by the
`atlys.document_uploaded_daily_mv` MATERIALIZED VIEW.

> Reports `total_rows = 0` at time of writing — schema landed and base table is ingested (20,446
> rows), but the rollup is not yet populated/merged. This is a freshness caveat for the Analytics
> Agent, not a schema error.

# Grain (ORDER BY)

`event_day × doc_type × capture_mode × scan_mode × device_type × os × destination`

- `event_day` `Date` = `toDate(payload.timestamp)` (event time, **not** ingest time).
- All dimensions are `LowCardinality(String)` in the agg table; the MV coalesces each to `''` on
  NULL (`coalesce(CAST(payload.<dim>,'String'), '')`), so missing dims land as the **empty string**
  bucket rather than SQL NULL.
- PARTITION BY `toYYYYMM(event_day)`.

# Aggregate states

| column | state | measure | finalizer |
|---|---|---|---|
| uploads_state | `AggregateFunction(count)` | upload count | `countMerge(uploads_state)` |
| retry_sum_state | `AggregateFunction(sum, UInt64)` | total retries | `sumMerge(retry_sum_state)` |
| retry_avg_state | `AggregateFunction(avg, UInt8)` | avg retries per upload | `avgMerge(retry_avg_state)` |
| threshold_crossed_state | `AggregateFunction(sum, UInt64)` | uploads with `is_crossed_failed_attempt_threshold = 1` | `sumMerge(threshold_crossed_state)` |

- MV source expressions: `countState()`, `sumState(CAST(payload.retry_count,'UInt64'))`,
  `avgState(CAST(payload.retry_count,'UInt8'))`,
  `sumState(CAST(payload.is_crossed_failed_attempt_threshold,'UInt64'))`, filtered
  `WHERE payload.event = 'document_uploaded'`.
- **Threshold rate** (M2) = `sumMerge(threshold_crossed_state) / countMerge(uploads_state)`.
- **Avg retries** (M1/M3) = `avgMerge(retry_avg_state)` (or `sumMerge(retry_sum_state) / countMerge(uploads_state)`).

# Deviations

- **D2** — TTL keyed on `agg_insert_time` (`DateTime64(3,'UTC') MATERIALIZED now64(3)`),
  `toDateTime(agg_insert_time) + 90 day`, `ttl_only_drop_parts = 1`. **Not** keyed on `event_day`:
  the server clock runs ahead of the historical event span, so keying TTL on the event date would
  silently drop rollups on merge.
- **D3 (gap)** — `os` is a grain dimension here but is **not typed or skip-indexed** on the base
  `document_uploaded`. The `os = ''` bucket (from the MV coalesce) plus Android-null rows means
  OS slices on this rollup are incomplete — prefer `device_type` slices or COALESCE `''` → `Android`.
  See [android-os-null](/contradictions/android-os-null.md).

# Serves

- [retry-count-distribution](/metrics/retry-count-distribution.md) (M1)
- [failed-attempt-threshold-rate](/metrics/failed-attempt-threshold-rate.md) (M2)
- [scan-mode-retry-comparison](/metrics/scan-mode-retry-comparison.md) (M3)
- [platform-upload-failure-rate](/metrics/platform-upload-failure-rate.md) (M4)
- ❌ Does **not** serve [doc-volume-vs-payment-conversion](/metrics/doc-volume-vs-payment-conversion.md) (M5) — cross-table payment join, `served_by_mv: null`.

# Related

- Base table: [document_uploaded](/tables/document_uploaded.md)
- Entities: [document](/entities/document.md), [event](/entities/event.md)
- Contradictions: [android-os-null](/contradictions/android-os-null.md)
- Source: `Atlys/schemas/11_document_uploaded.sql`, live `atlys` schema (`document_uploaded_daily_agg`, `document_uploaded_daily_mv`)
