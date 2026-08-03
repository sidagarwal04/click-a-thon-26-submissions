# `optimizations/` — the 2026-08-01 load test, and what it cost

Everything here was measured against the live service (`sonyliv`, aws
ap-south-1, ClickHouse **26.2.1.525**, 2 replicas) on 2026-08-02. No number is
estimated. Where something could not be established, it says so.

---

## What actually happened

**The headline: 50,000 concurrent connections never reached ClickHouse. Nothing
close did.**

Peak `CurrentMetric_TCPConnection` was **23** on any single replica and **52**
cluster-wide, against a `max_connections` of 4,096 per replica. Peak concurrent
queries was **11** against a limit of 1,000–1,500. Coverage is complete — every
hour from 16:00 to 00:20 reports 3,600/3,600 seconds sampled, no gaps — so no
burst could have hidden between samples. `system.session_log` records **194**
total logins from the ingest client across 7.5 hours, and **zero** `LoginFailure`
rows. There is no code 202 `TOO_MANY_SIMULTANEOUS_QUERIES`, no 203
`NO_FREE_CONNECTION`, no accept failure, anywhere.

**Root cause is a semantic collision, not a failure.** `sonyliv-gen
--concurrency N` sets the number of *simulated viewer sessions inside the
generated event stream* — `*session` structs on an in-process heap. It has never
had anything to do with sockets. The database connection ceiling is
`CLICKHOUSE_MAX_OPEN_CONNS`, **default 16**, passed to the driver as both
`MaxOpenConns` and `MaxIdleConns`. So `--concurrency 50000` asked for 50,000
fake viewers to be served through at most 16 TCP connections by 6 workers. The
50k did not die at the client, the load balancer, or a Cloud cap; it was never a
connection count.

Fixed in [`ingest/cmd/sonyliv-gen/main.go`](../ingest/cmd/sonyliv-gen/main.go):
the flag is relabelled, and the startup banner now prints the real DB pool size
next to it so the two cannot be confused again.

**"No downstream tables were created" is false as stated — and the truth is
worse, because it was silent.** Every downstream object exists. What happened is
that the `sonyliv_prod` serving builder completed its last cycle at
**2026-08-01 23:22:23.774** and never issued another query, while ingest kept
running for a further **51 minutes** to 00:13:37.

The final cycle was perfectly healthy: `build_ms` 478 against an average of 308.
Not a degradation curve — an instantaneous stop. There is **no ClickHouse-side
error**: zero exceptions on either replica between 23:22:20 and 23:24:30. This
was a client-side process death on the host running the builder. `serving_watermark`
is the only place the staleness is visible, and nothing was watching it.

Two plausible-sounding causes were **refuted** by measurement:

- *The empty `serving_concurrency_minute_staging` means the pipeline stalled.*
  No — empty is the correct post-swap state. The builder's minute cycle is
  DROP PARTITION → INSERT → count guard → REPLACE PARTITION → DROP PARTITION,
  and the trailing drop is why it reads zero. It completed successfully many
  times, last at 23:21:47.
- *The `ACCESS_DENIED` on `dictGet` broke a materialized-view chain.* No — it is
  a diagnostic probe against the wrong database. `sonyliv_svc` already holds
  `dictGet ON sonyliv_prod.*`, neither MV calls `dictGet` at all, and it fired at
  00:05:52, forty-three minutes *after* the builder was already dead. Also,
  `materialized_views_ignore_errors` is 0, so a throwing MV fails the whole
  INSERT loudly rather than leaving a silent gap.

**The 22:30 "replica churn" was a graceful rolling restart**, same version
(26.2.1.525, identical git hash) on both generations. The drain log is the most
telling line in the whole investigation: the departing pods reported *"Waiting
for 3 outstanding connections"* and *"Waiting for 2 outstanding connections"* —
**five client connections in total**, at the supposed peak of a 50,000-connection
load test.

**The 31.5 s and 29.6 s latency spikes were not user load.** All twelve of the
slowest queries in that hour belong to the platform user
`observability-internal` scraping its own system tables. The ingest user's own
latency was healthy throughout: p50 95 ms, p99 356 ms over 80,419 queries.

**The 4.3× row discrepancy is producer attribution, not duplication.**
`ingest_batches` accounts for 2,080,671 rows while `events_raw` holds 9,023,668.
Every one of the 22,370 audited batches has exactly as many rows in `events_raw`
as it declared — ratio 1.000, no exceptions. The gap is 6.94M rows written by
`_source_file` values this codebase cannot emit (`fleet` 3,947,986,
`mock-dashboard` 2,088,102, `manual` 10), by producers that write no ledger row
at all. Not a correctness bug in this client; an **ownership gap** — 77% of the
table has no provenance record.

### Two real client defects, both fixed here

1. **A cancelled `Send()` was audited as `failed` although the rows landed.**
   clickhouse-go's watchdog closes the socket on context cancel and returns
   `ctx.Err()`, discarding the server's reply. All three "failed" batches on
   2026-08-01 had every row present in `events_raw` (3/3, 24/24, 51/51). The
   ledger under-reported by 78 rows. Fixed in
   [`chx/loader.go`](../ingest/internal/chx/loader.go) with a third `unknown`
   state — same class of defect as the doubled Summing curve: it passes every
   internal check and is visible only by comparing the audit layer against the
   table it describes.

2. **Live mode silently bypassed the 1,000-row batch floor.** `--batch-size`
   validation refuses anything under 1,000 with an explicit rationale about
   one-part-per-insert. But the generator's one-wall-second timer flush emits
   whatever is buffered, and that path has no floor. Measured result: **55.3
   rows/batch** (generator) and **143.7** (api) against a configured 50,000 —
   22,314 tiny inserts, each its own part, each fanning out to two dependent MVs.
   Fixed in `chx/loader.go`: sub-floor chunks now route through ClickHouse's
   server-side async buffer so the server coalesces them, while properly sized
   blocks still go straight through.

   The same fix corrects a latent idempotency hole. `async_insert_deduplicate`
   defaults to **0**, so `insert_deduplication_token` was **inert** on the
   `--async` path and a retry would have duplicated. It is now set explicitly.

**Not from this codebase, still unattributed:** a `CANNOT_PARSE_INPUT_ASSERTION_FAILED`
(code 27) firing roughly twice a minute — `expected ',' before:
'toDateTime('…'), 1785629475443)'`. Some producer builds `INSERT … VALUES` by
string concatenation and is missing a comma before its penultimate column. It is
not in this worktree (the Go client sends native columnar blocks and never emits
`VALUES` text), and it leaves no trace in `query_log` or `text_log`. Candidates
by elimination are `fleet`, `mock-dashboard`, or `manual`. **This is still
dropping rows on the floor and needs an owner.**

---

## The files

| File | What it is |
|---|---|
| [`sql/010_read_path_rewrites.sql`](sql/010_read_path_rewrites.sql) | Seven measured query rewrites, each with its before/after numbers and an equivalence check |
| [`sql/020_projections.sql`](sql/020_projections.sql) | Two projections, the engine constraint that rules out most of the schema, and what was rejected and why |

Both target clients that are **not in this repository**. They are handover
artifacts: the rewrite, the measurement justifying it, and the invariant proving
it equivalent.

## The biggest single win

`SELECT max(event_ts) FROM sonyliv_prod.events_dedup` — 694 executions reading
**3.13 billion rows and 56.3 GB**, the #1 SELECT by both total time and total
bytes.

Reading the base table returns a provably identical answer, because `event_ts`
is itself a `GROUP BY` key of the view, so grouping cannot change its maximum.
Measured back to back, both returning `2026-08-02 00:13:37.672`:

| | elapsed | bytes read |
|---|---:|---:|
| `FROM events_dedup` | 1.058 s | 162,146,488 |
| `FROM events_clean` | 0.104 s | 72,000,384 |
| | **10.2× faster** | **2.25× fewer** |

## On projections

Short answer for the wide table: **`events_clean` cannot take one**, and that is
a measured constraint, not an opinion.

`deduplicate_merge_projection_mode` is `throw` on both replicas (default,
unchanged). Its in-server description limits projections to "classic" MergeTree;
`SharedReplacingMergeTree`, `SharedSummingMergeTree` and
`SharedAggregatingMergeTree` are not classic, so `ADD PROJECTION` throws.
**9 of 16** MergeTree tables in `sonyliv_prod` are blocked, `events_clean`
among them. The escapes each cost something — `drop` discards the projection on
merge, `rebuild` pays on every merge, and `ignore` is documented as possibly
producing an **incorrect answer**, which is not an option on a scored problem.
`events_clean` is doubly excluded: its readers use `FINAL`, and a `FINAL` query
cannot use a projection at all.

Where projections **do** apply, both on classic `SharedMergeTree` tables whose
hot query filters a column that is not a sort-key prefix:

- **`dirty_sessions`** (5,739,016 rows) — `ORDER BY (session_start_date,
  session_key, last_ingested_at, …)` but the hot query constrains only
  `last_ingested_at`, the third column. 846 executions, 7.87 GiB. A cheaper
  minmax skip index was considered and rejected on measurement: a one-minute
  window holds 911,161 rows spread across an entire `session_start_date` block,
  so granule-level min/max ranges are too wide to prune.
- **`events_raw`** (9,023,668 rows) — `ORDER BY (video_session_id,
  event_timestamp)`, but the ingestion-monitoring dashboard filters on
  `_ingested_at`, which is in neither the sort key nor the partition key. Event
  time and ingest time diverge precisely when ingestion lags, which is the only
  time anyone opens that dashboard.

Both projection bodies were validated against the live schema. `EXPLAIN
projections = 1` currently shows a plain `ReadFromMergeTree` — there are **zero**
projections on this service today, so the baseline is clean and the post-apply
check is unambiguous.

### A live-docs trap worth knowing

`clickhouse.com/docs/sql-reference/statements/alter/projection` documents
`WHERE` clauses inside projection definitions. `clickhouse.com/docs/data-modeling/projections`
simultaneously lists "No WHERE clauses in projection definitions" as a
limitation. **The two pages contradict each other** because the site publishes
*latest*, not 26.2. Projection `WHERE` landed in **26.7** (changelog #102347);
on 26.2 it is a parser error. Do not design filtered projections against that
page.

---

## What was checked and found healthy

The submission database `sonyliv` is **intact and was never touched by the load
test** — its last ingest was 16:22:20, twenty-seven minutes before the run began
at 16:49. Its reference figures reproduce exactly: **31,947** active intervals
over **10,848** sessions per `clip_variant`, and conservation holds —
`sum(opens)` = `sum(closes)` = `count()` of intervals = 31,947, ratio 1.0.

(Reading `active_intervals_current` without pinning `clip_variant` returns
63,894 — exactly 2 × 31,947. That is the documented doubling trap in
`docs/TABLE-CONTRACT.md` §3, not a defect.)
