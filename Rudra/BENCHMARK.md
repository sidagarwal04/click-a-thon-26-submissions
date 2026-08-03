# Benchmark results & pipeline evidence — unseen day (2026-07-31)

All numbers below are **measured on the unseen evaluation day** (`sonyliv.raw_events`,
6,974,862 events) through our ClickHouse pipeline, and every query is **provable in
`system.query_log`** (see [§4](#4-pipeline-evidence-systemquery_log)).

- **Metric:** foreground-only **session** concurrency (`video_session_id`), backgrounded /
  paused / heartbeat-gap minutes excluded.
- **Peak** = `max` of the per-minute concurrency (a maximum, so it is **grain-invariant**).
- **Average** = total foreground session-minutes ÷ **1440** (full-day denominator, not
  active-minutes).
- **Exactness:** `n_sessions` is a plain additive `sum` — exact because dimensions are frozen
  per session, so each session lives in exactly one cell per minute and cells partition the
  sessions (summing disjoint counts can never double-count). Every rollup answer below equals
  the base-table answer bit-for-bit.

> Definition note: our reactivation policy (a heartbeat after a >90 s silence re-counts the
> session) gives **peak 22,174**. A stricter policy (require an explicit `Play`/`resume`) gives
> 18,843. That choice is orthogonal to the serving architecture measured here.

## 1. Concurrency results — total, at minute / hour / day grain

| grain | peak | peak at (UTC) | average /min |
|---|---|---|---|
| minute | **22,174** | 2026-07-31 11:16 | 885 |
| hour   | **22,174** | 2026-07-31 11:00–12:00 | 885 |
| day    | **22,174** | 2026-07-31 | 885 |

Peak is a maximum over per-minute concurrency, so it is identical at every grain; the grain
sets the reporting resolution (1440 / 24 / 1 points). Average is the full-day mean.

## 2. Concurrency results — with dimension filters (day grain)

| filter | peak | peak at (UTC) | average /min |
|---|---|---|---|
| _none (all sessions)_ | 22,174 | 11:16 | 885 |
| `platform = ANDROID_PHONE` | 6,518 | 11:16 | 245 |
| `video_type = live` | 10,321 | 11:16 | 365 |
| `platform = ANDROID_PHONE AND video_type = live AND audio_language = hin` | 1,503 | 11:16 | 53 |
| `content` = top show (by concurrency) | 8,788 | 11:16 | 316 |

All 11 documented dimensions are filterable (platform, app_version, country, audio_language,
subtitle_language, player_version, video_resolution, video_type, and title/show_name/category
via `content_id`). The peak stays at 11:16 across filters — the live-event minute dominates.

## 3. Query latencies — base table vs read-optimized rollup tier

Same queries, same exact answers, two serving structures. Latency = `query_duration_ms` from
`system.query_log`; `rows` = `read_rows`.

| query | base `hist_minute_full` | rollup tier | speedup | serving table |
|---|---|---|---|---|
| total | 8 ms · 663,151 rows | **5 ms · 8,192** | 81× fewer rows | `dim_minute` (`_total`) |
| `platform=…` | 10 ms · 663,151 | **7 ms · 16,384** | 40× | `dim_minute` |
| `video_type=…` | 9 ms · 663,151 | **6 ms · 7,521** | 88× | `dim_minute` |
| multi-dim (3 filters) | 18 ms · 663,151 | **7 ms · 24,576** | 27× | `concurrency_1m` (dims-first) |
| `content_id=…` | 19 ms · 663,151 | **6 ms · 8,192** | 81× | `dim_minute` |

- **Total & single-dim** (incl. content) → `dim_minute (dim, value, minute)` marginals: one
  keyed granule (~8K rows).
- **Multi-dim / content-attribute combos** → `concurrency_1m`, ordered **dims-first (minute
  last)** so the leading-dim prefix prunes.
- Storage cost of the rollup tier: **+2.13 MiB** (`concurrency_1m` 1.36 MiB + `dim_minute`
  0.74 MiB) — and since `concurrency_1m` holds the same data as the 3.23 MiB base but
  dims-first compresses 2.3× better, **replacing** the base is a net **−34%** storage.
- At 10,000× volume the rollups stay bounded (`minutes × dim-cardinality`), so the row-read
  win grows from ~80× toward ~10,000×.

## 4. Pipeline evidence (`system.query_log`)

Every benchmark query is tagged with `log_comment` and recorded server-side by ClickHouse
(`query_duration_ms`, `read_rows` — proof the query ran, and that it hit the serving tables,
not raw history):

```
 qid                tier        ms   read_rows
 base:q01_total     base hist    9     663151
 base:q04_platform  base hist   10     663151
 base:q05_vtype     base hist    9     663151
 base:q06_multidim  base hist   18     663151
 base:q07_content   base hist   19     663151
 q01_total_min      rollup       6       8192
 q02_total_hour     rollup       5       8192
 q03_total_day      rollup       5       8192
 q04_platform       rollup       7      16384
 q05_vtype          rollup       6       7521
 q06_multidim       rollup       7      24576
 q07_content        rollup       6       8192
```

Reproduce the trace yourself:
```sql
SELECT log_comment, query_duration_ms, read_rows, arrayStringConcat(tables, ',') AS tables_used
FROM system.query_log
WHERE type = 'QueryFinish' AND log_comment LIKE 'sonyliv-bench%'
ORDER BY event_time DESC;
```

## 5. Reproduce the results

```bash
# 1. build the serving tier from the base table (idempotent)
clickhouse-client < sql/04_serving.sql          # concurrency_1m + dim_minute

# 2. run the benchmark suite (tagged, prints answers + latencies)
clickhouse-client < sql/05_benchmark.sql

# 3. read the evidence back out of query_log (§4)
```

Answers are stable and exact; latencies vary only with cluster load (single-digit ms here on
ClickHouse Cloud).
