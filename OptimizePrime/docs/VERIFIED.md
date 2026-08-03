# VERIFIED — facts we executed, not read

> **Summary:** Every claim here was **run** — against ClickHouse 26.7.1.1315 (local), ClickHouse
> Cloud 26.2.1.525 (the graded service), ClickStack, Langfuse, LibreChat and the ClickHouse MCP
> server, over 30 Jul–1 Aug 2026. This file is the short list that changes what you type. **Read it
> before trusting any ClickHouse claim, including your own memory.** Dated sections at the bottom
> record later corrections — including two reversals of facts this file itself used to state
> (dictGet 34×, `IN (subquery)` never using a projection). If something here turns out wrong on
> Cloud, fix it here in the same commit.

## Things that will silently waste your time

| # | Fact | Consequence |
|---|---|---|
| 1 | The server image **disables network access for `default`** unless `CLICKHOUSE_USER` *and* `CLICKHOUSE_PASSWORD` are set | `Code: 194` on every query |
| 2 | `${VAR}` in a **`.sql`** init file is **not interpolated** | user gets the literal string as its password |
| 3 | A `.env` feeds **compose's** substitution, not the container | var must also be under `environment:`, else **empty password** |
| 4 | `docker-entrypoint-initdb.d` runs **only on first boot** | iterate with `down -v`; plain `down` keeps the volume |
| 5 | **A failed init script does not stop the container** | status `Up`, `/api/health` `200`, schema half-applied |
| 6 | `readonly = 1` blocks the client setting `max_execution_time` | `Code: 164`; agents/MCP need `readonly = 2` + `MAX` constraints |
| 7 | `non_replicated_deduplication_window` defaults to **0** | insert dedup is **OFF** on plain MergeTree |
| 8 | `system.query_views_log` etc. **do not exist** until first used | guard with `EXISTS TABLE`; always `SYSTEM FLUSH LOGS` first |
| 9 | Per-column compression reads **0 for COMPACT parts** | set `min_bytes_for_wide_part = 0`, or load ≥10 MiB per part |
| 10 | `set -e` does **not** fire inside `cmd \| tee` | use `set -euo pipefail` or scripts lie about succeeding |
| 11 | `SYSTEM STOP VIEW` is a **refreshable**-MV command | on an incremental MV it is accepted and **does nothing**; use `DETACH`/`ATTACH` |

## 26.7 breaking changes, both confirmed

```sql
-- a plain column in an AggregatingMergeTree that is neither in the sort key nor an aggregate:
→ Code: 36. Column(s) `x` ... neither part of the sorting key nor aggregate measures
-- s3() with server-managed credentials:
→ Code: 497. S3 access from user queries is not allowed to use server-managed credentials
```

## Measured, on comparable data

| Technique | Effect |
|---|---|
| Entity-first sort key vs time-only | **122×** fewer rows read (5,000,000 → 40,960; granules 5/611) |
| `dictGet` vs `LEFT JOIN` on a small dimension | **3.7× less memory** — reproduced. The **34× time** figure did NOT reproduce; see the note below |
| Rollup that sums a distinct count | **9× over-count** (45,000 vs a truth of 5,000) |
| Skip index on clustered vs spread values | 366× vs ~nothing |
| A `PROJECTION` on a badly-keyed table | recovers the good key's row count exactly |

## ClickStack (the OSS integration)

- Needs a **TTY** or it exits 129 after a clean boot.
- OTLP 4317/4318 **do not bind until a team exists**; registration is `POST /register/password` at the
  **root**, not `/api`. And the collector binds **late** — poll, don't sleep.
- Bundles its **own** ClickHouse **26.5.6**. Never build the project on it.
- Default TTL is **30 days**; `SeverityText` is stored **lower-cased**.
- One OTel emitter feeds ClickStack **and** Langfuse — same `trace_id` lands in both (verified).

## Submission-contract update verified 2026-08-02

The official submission repository at commit `c446938` now adds explicit evidence requirements for
ClickStack, Langfuse and LibreChat. For ClickStack, commit deployment/integration and OTel wiring,
use a secrets-redacted `.env.example`, name the ClickHouse service and destination tables, include
the dashboards/searches actually used in the README, and show them live in the hosted demo and video.
Screenshots are supporting evidence, not proof by themselves. The same official rules require a
self-contained team folder and `[Submission] Team Name` PR; they do not say this project repository
must be public or that only a named Team Captain may submit.

The official problem/unseen repository then moved to `c1e1c69`. It no longer promises a fixed
benchmark-query set or private answer key. It requires peak and average concurrency at minute, hour
and day grain with dimension filters, latency and pipeline evidence; judges spot-check results
against raw events. The repository's 13 queries are therefore a coverage matrix, not official SQL.

## MCP

- Env names are `CLICKHOUSE_MCP_*`; `MCP_SERVER_TRANSPORT` is **silently ignored**.
- Exactly 3 tools: `list_databases`, `list_tables`, `run_query`. `run_chdb_select_query` needs the
  chdb extra installed, not just `CHDB_ENABLED=true`.
- The server enforces read-only **itself**: a write returns `Code: 164` even as a privileged user.
- stdio works on the host; it does **not** work inside the LibreChat container (no C compiler → `lz4`
  cannot build). Use `streamable-http` there, plus `mcpSettings.allowedAddresses`.


## Correction — the dictGet "34×" figure (2026-08-01)

Re-measured on this workload while building `sql/80_content.sql`, against `content_dim` (33,464 rows):

| Scale | Metric | JOIN | dictGet |
|---|---|---|---|
| `ev_raw` (905,558 rows) | elapsed, median of 3 | 35.6 ms | 19.9 ms — **1.8×** |
| `ev_raw` | memory | ~26 MB | 7.56 MB — **3.7×** |
| `cc_minute_delta` (24,951 rows — the views' real workload) | elapsed | 12.8 ms | 9.8 ms — **1.3×** |

> **Row count as measured**, at `34c3f05`. `cc_minute_delta` now holds **28,074** rows (ADR 0008 added
> dimensions, ADR 0009 redistributed tuples). The timings above have **not** been re-run at the new
> row count and are left as measured — this file is for facts, and a re-scaled guess is not one. The
> conclusion is unchanged either way: at single- to double-digit ms, wall clock is round-trip
> dominated, so a 12% row increase cannot rehabilitate a 34× claim.

**The memory ratio reproduces almost exactly.** The 34× *time* multiplier does not, at this scale:
wall clock here is single- to double-digit ms and round-trip dominated, and the JOIN's extra cost is
mostly the 3.7% additional rows read from the dimension side. The advantage is real and directionally
consistent, and it grows with table size — but quoting 34× for this data would be quoting a number
our own query log does not support.

Kept as a standing lesson: a figure inherited from a different dataset is a hypothesis, not a
verified fact, and this file is specifically for facts.

## Verified for ADR 0016 — replaceable uniqExact buckets (2026-08-01, Cloud 26.2.1.525)

Probed on a scratch database before `sql/45_user_concurrency.sql` was rewritten:

- `ReplacingMergeTree(DateTime64 version)` **accepts an `AggregateFunction(uniqExact, String)`
  payload column** (Cloud maps it to `SharedReplacingMergeTree`). `FINAL` keeps the newest version
  per key, and a bucket re-inserted with FEWER members reads back smaller (2 → 1 across 4 physical
  rows) — replacement genuinely retracts, which a set-union `AggregatingMergeTree` cannot.
- `uniqExactStateIf(x, cond)` **is assignable into a plain `AggregateFunction(uniqExact, String)`
  column** — the `-If` state is compatible — and over zero qualifying rows it produces a valid
  EMPTY state that merges as identity and reads back as 0. That empty state is what makes an
  explicit retraction row expressible in one INSERT.
- In the hour-cube INSERT shape, **`WHERE` cannot precede `ARRAY JOIN`** (`Code: 62`); a templated
  scope must ride the `ARRAY JOIN` line, not the `FROM` line. `tools/publish.sh` does exactly that.

## Correction — a dictionary layout trap not previously recorded (2026-08-01)

A simple-key `LAYOUT(HASHED())`, `FLAT()` or `CACHE()` dictionary **cannot serve a negative key via
`dictGet`**, regardless of the declared column type — they key on `UInt64` internally. `content_dim`
contains `content_id = -987654322` (DATA_DICTIONARY trap 5). The dictionary loads all 33,464 elements
without complaint and then throws on lookup:

```
Code: 70. Value in column Int64 cannot be safely converted into type UInt64
```

`LAYOUT(COMPLEX_KEY_HASHED())` with `dictGet(..., tuple(content_id))` is required. `FLAT` was never
viable regardless: it allocates an array sized to the maximum key, and the maximum here is
2,078,179,327.

## Correction — `IN (subquery)` CAN use a projection on 26.2 (2026-08-01, Cloud 26.2.1.525)

WALKTHROUGH §5 recorded the `ev_raw` projection as "1.00× for +94% storage" because "the actual
straggler path uses `IN (subquery)`, which full-scans anyway". Re-measured on the finalizer's real
query shape (`WHERE video_session_id IN (subquery)` **plus an event-time window**): the optimizer
**does choose the projection** — a one-session read drops from 104,640 rows (11.6% of `ev_raw`) to
8,193 (0.9%), 12.8× fewer rows, for +91% storage. Numbers in `evidence/publish.txt` PHASE 8/10.

Still not shipped — the finalizer meets its target without it and the storage trade is an operator
call — but the *reason* on record changed from "the optimizer can't" to "we choose not to". Same
standing lesson as the dictGet correction above: a claim inherited from an earlier measurement is a
hypothesis until re-run on the shape that matters.

## Verified 2026-08-01 — during the benchmark, publisher and target-resolution work

| # | Fact | Consequence |
|---|---|---|
| 12 | ClickHouse Cloud **auto-suspends when idle**; the first query after suspend measured **29.3 s** | benchmark or demo without a warm-up query reports garbage latency; `tools/bench.sh` and `demo/run.sh` both warm up and discard |
| 13 | `X-ClickHouse-Summary` (HTTP header) carries server-side `elapsed_ns`, `read_rows`, `read_bytes` per query | timing evidence without `SYSTEM FLUSH LOGS` round-trips; every bench number is also query-log auditable via `log_comment` |
| 14 | `CREATE TABLE IF NOT EXISTS` **never migrates an existing table** | re-applying evolved schema files silently keeps the old columns — local drifted to `uniq`/`UInt64` where Cloud had `uniqExact`/`Int64`. Diff `system.columns` against intent; ADR 0018 closed this (4 drifted columns found, 0 remain, `evidence/target-resolution.txt`) |
| 15 | An incremental MV sees **only inserts after its creation** — never existing rows | turning the publication layer (`sql/12_publish.sql`) on over an already-loaded table starts its cursor at "now": adoption is one DDL round-trip, **no catch-up rebuild** (`evidence/publish.txt` PHASE 11) |

## Measured 2026-08-01 — the model at 1×/10×/100× audience (`evidence/scale.txt`)

- Row growth of every tier fits **linear** exponents (time k ≤ 0.98, memory k ≤ 0.81) from 1× to
  100×; the serving-vs-expansion reconcile still passes at 100× (6,799 minutes, peak 251,668).
- **What breaks first is the interval derivation's memory**, not any serving read: at 100×
  (~2.9 M intervals) it wants 4.2–5.2 GiB against a 5.6 GiB laptop-server ceiling and FAILED at
  max_threads=10 while completing at 4 and 2 threads with ~550 MiB spilled. The wall is
  thread-count-dependent — the finding is the shape, not the exact GiB.
- The other classic candidates measured and cleared at 100×: max 28 parts per partition (limit
  3,000), dictionary fixed at 17 MiB (keyed on catalog, not audience), stateless tier 42.7 MiB.
