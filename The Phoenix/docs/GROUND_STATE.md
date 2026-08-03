# Ground state

**As of 2026-08-01 13:45 UTC.** What is actually on the server, measured this session.

Every claim carries a tag. A verified claim is written `[V:<id>]`, where the id resolves to
a row in [`evidence/LEDGER.tsv`](../evidence/LEDGER.tsv) naming the command that produced it
and the artifact holding its output. `[A]` marks an assumption and states what would falsify
it and who decides. Nothing here is left unverified: anything that would have qualified was
either measured or deleted. `./scripts/check_docs.sh` enforces both rules.

Reproduce the whole document:

```
./scripts/inventory.sh phoenix     # structure
./scripts/ground_state.sh          # the 33 frozen-slice metrics
./scripts/ingest_probe.sh 3 20     # live stream state and blast radius
./scripts/frozen_gate.sh 120       # the stability gate
```

## 0. How these numbers were obtained, and one deviation

`[V:inventory_phoenix]` Server version is **26.2.1.525**, ClickHouse Cloud, `ap-south-1`.
Every table engine is a `Shared*MergeTree` variant, which is Cloud's replicated
implementation, not the `MergeTree` names in `sql/schema/`.

`[A]` **Introspection ran over the native protocol via `scripts/ch.sh`, not the ClickHouse
MCP server.** `TASK.md` section 0.5 mandates MCP for introspection. No ClickHouse MCP server is
exposed in this session; a tool search returned none. `ch.sh` reaches the same `system.*`
tables over port 9440, so nothing is unmeasurable as a result, but the deviation is recorded
rather than papered over. **Falsified by:** an MCP ClickHouse server appearing in the tool
list. **Decided by:** whoever configures the session.

### Two measurement rules, both learned the hard way

These are not style preferences. They are the difference between a reproducible number and a
number that happened to be true when someone looked.

1. **Never `system.tables.total_rows`.** `[V:inventory_phoenix]` It is an estimate that
   tracks parts, not data. Measured this session: `concurrency_deltas` reported **34,644**
   there and **26,904** from `count()` minutes apart, because background merges were still
   collapsing rows. Nothing had changed in the data.

2. **Never a bare `count()` on a Summing or Collapsing table.** `count()` reads physical
   rows, and physical rows are a function of merge timing. The stable quantity is the
   aggregate the engine maintains: `sum(sign)` for Collapsing, `sum(delta)` and
   `uniqExact(minute)` for Summing. `[V:ingest_probe]` The gap is not academic:
   `session_minute_runs` holds **7,593** physical August rows but only **1,545** asserted
   ones, because retractions are stored rather than applied.

Every number below is an aggregate under an explicit `event_timestamp < {frozen_before}`
predicate. That is what makes the gate in section 4 reproducible rather than lucky.

## 1. What exists

`[V:inventory_phoenix]` Full column lists, engines, keys, part counts, on-disk sizes and the
verbatim `SELECT` of every view are in the `inventory_phoenix` artifact. Summary:

| Table | Engine | ORDER BY | Partition | Parts | Disk |
|---|---|---|---|---:|---|
| `raw_events` | SharedMergeTree | `video_session_id, event_timestamp` | `toYYYYMMDD(event_timestamp)` | 11 | 4.12 MiB |
| `raw_events_landing` | Null | none | none | 0 | 0 B |
| `content` | SharedReplacingMergeTree | `content_id` | none | 1 | 220.41 KiB |
| `foreground_intervals` | SharedMergeTree | `video_session_id, interval_start` | none | 2 | 2.96 MiB |
| `session_minute_runs` | SharedCollapsingMergeTree | `video_session_id, run_start, run_end` | none | 2 | 1001.81 KiB |
| `concurrency_deltas` | SharedSummingMergeTree | `platform, country, video_type, content_id, app_version, minute` | none | 1 | 61.03 KiB |
| `user_minute_runs` | SharedCollapsingMergeTree | `user_id, run_start, run_end` | none | 1 | 476.14 KiB |
| `user_concurrency_deltas` | SharedSummingMergeTree | `platform, country, video_type, content_id, app_version, minute` | none | 3 | 69.77 KiB |
| `concurrency_deltas_naive` | SharedSummingMergeTree | same as `concurrency_deltas` | none | 1 | 40.79 KiB |

`[V:inventory_phoenix]` Views: `event_state` (plain View, the shared state machine),
`raw_events_mv`, `concurrency_deltas_mv`, `user_concurrency_deltas_mv`. The live definitions
read back from `system.tables.as_select` match the committed files in `sql/schema/`.

`[V:inventory_phoenix]` **All materialized views are healthy.** `system.query_views_log`
reports `QueryFinish` and `no exceptions` for all three: `raw_events_mv` x835,
`concurrency_deltas_mv` x86, `user_concurrency_deltas_mv` x60. None has silently failed.

`[V:inventory_phoenix]` `raw_events` and `content` both carry an `ingested_at DateTime`
column that is **not** in the committed DDL. It was added by an out-of-band `ALTER`. See section 3.

`[V:inventory_phoenix]` Two scratch tables, `open_test_sessions` and
`open_test_bystanders`, are left in `phoenix` by `scripts/test_open_sessions.sh`. They are
fixtures, read by nothing in the serving path.

### Vocabulary

`[V:frozen_slice_stability]` The frozen slice contains **7** distinct `event_type` values and
**47** distinct `event` values. `docs/ROADMAP.md` says 46; the measured figure is 47.

`[A]` The data dictionary calls its list "current event types", which is an admission that it
is not exhaustive, and the live stream has already proved it: two `event` values appear only
in the August slice, taking the whole-table count to 49. Both are classified conservatively
by the existing state machine. The `UNKNOWN_VOCABULARY` report that makes this a standing
check rather than a one-off observation is Phase 3 work. **Falsified by:** a value appearing
that the classifier maps to active without a human deciding it should. **Decided by:** the
team, before the unseen day.

## 2. What is contaminated

The live August stream shares `phoenix.raw_events` with the validated July corpus, and the
contamination has propagated to every derived table, because the materialized views fire on
insert and the batch derive was re-run at some point over the whole table.

`[V:ingest_probe]` Blast radius, per table, as rows attributable to the live slice:

| Table | Live rows | Measured as |
|---|---:|---|
| `raw_events` | 55,293 | `count()` |
| `foreground_intervals` | 31,966 | `count()` |
| `session_minute_runs` | 1,545 | `sum(sign)`, asserted |
| `user_minute_runs` | 1,545 | `sum(sign)`, asserted |
| `concurrency_deltas` | 48 | `uniqExact(minute)` |
| `user_concurrency_deltas` | 48 | `uniqExact(minute)` |

**The contamination is cleanly separable, and this is the central Phase 1 finding.**

`[V:ingest_probe]` `sessions_spanning_the_boundary = 0`. No `video_session_id` has events on
both sides of `2026-08-01`.

`[V:ingest_probe]` `blast.runs_straddling_boundary = 0`. No row in `session_minute_runs` has
`run_start` before the boundary and `run_end` after it. The cut is clean on the derived
tables too, not only on `raw_events`.

`[V:frozen_slice_stability]` Every derived table's frozen-slice content still equals the
validated figures exactly: `foreground_intervals` **599,137**, `session_minute_runs`
**17,604** asserted, `user_minute_runs` **16,600** asserted, `raw_events` **905,558**.

**Therefore no rebuild of `phoenix` is required.** The frozen predicate recovers the
validated dataset intact from the shared table. This is a measurement, not a hope: had
sessions straddled the boundary, a rebuild into a separate generation would have been
mandatory.

## 3. Isolation

The frozen-slice predicate is **`event_timestamp < {frozen_before:String}`**, defaulting to
`2026-08-01`, wired as a single parameter injected by `scripts/ch.sh` from `$FROZEN_BEFORE`.
On the unseen day it is one variable, not a grep across the SQL tree at hour 22.

### Why not `ingested_at`

`[V:ingested_at_nondeterminism]` Because it would have inverted the dataset silently.

`ingested_at DateTime DEFAULT now()` was added to `raw_events` by an `ALTER` after the July
rows were already loaded. ClickHouse does not rewrite existing parts on such an `ALTER`, so
for those rows the column has no stored value and the `DEFAULT now()` is evaluated **at read
time**. The column therefore equals the wall clock of whichever query happens to read it.

Measured three times, four seconds apart: `uniqExact(ingested_at)` over the July rows
returned **1** each time, and the single value was the reading query's own clock
(13:03:40, then 13:03:44, then 13:03:48).

The consequence, measured rather than reasoned about: applying a watermark filter
`ingested_at <= '<now>'` retained **0 of 905,558** July rows and **all 34,302** August rows
that existed at the time. Precisely backwards.

`[V:ingest_probe]` `event_timestamp`, by contrast, is a stored value in both slices, and the
two slices are disjoint in it. That is why it is the freeze key.

## 4. The gate

`[V:frozen_slice_stability]` The 33-metric frozen-slice set was run twice, 60 seconds apart:
**0 differing lines**. `metrics_compared = 33`, `differing_lines = 0`.

`[V:ingest_probe]` **Verdict was `PASS_BUT_INGEST_IDLE`, not `PASS`**, and the distinction is
deliberate. `rows_ingested_between_runs = 0`: the stream had stopped at 13:20:52, before the
gate ran. See [`issues/ingest-2.md`](issues/ingest-2.md). A run with no concurrent writes
cannot demonstrate stability *under* concurrent writes, and recording it as a pass would be
the unearned confidence this repo has already paid for once.

The gate upgrades itself with no code change once the stream is live again: `PASS` requires
both `differing_lines = 0` **and** `rows_ingested_between_runs > 0`.

What the gate compares is the payload, not the evidence header. The header carries `run_utc`
and the live `row_count`, which are supposed to differ between runs; comparing them would
fail the gate for the single reason that proves it is working.

## 5. The frozen slice, measured

`[V:frozen_slice_stability]` All 33 metrics are in the artifact. The ones that matter:

| Metric | Value |
|---|---|
| `rows.raw_events` | 905,558 |
| `uniq.sessions` / `uniq.users` / `uniq.contents` | 10,866 / 9,618 / 3,357 |
| `span.first_event` → `span.last_event` | 2026-07-14 15:43:58.144 → 2026-07-26 11:30:04.847 |
| `rows.foreground_intervals` | 599,137 |
| `runs.session_minute_runs.asserted` | 17,604 |
| `runs.user_minute_runs.asserted` | 16,600 |
| `serving.peak_concurrency` | **2,828** at 2026-07-26 10:56:00 |
| `serving.user_peak_concurrency` | **2,748** at 2026-07-26 10:56:00 |
| `serving.minutes_with_audience` | **3,663** |
<!-- These serving.* rows are CORPUS-WIDE, over the 17,029 minutes from the first delta to the
     last, and not the single headline day. The day figures are different and both are correct:
     88.06 over 1,440 minutes and 200.00 over 634. Confusing the two is easy and was done once. -->
| `serving.avg_all_minutes` | **7.87** (denominator 17,029 minutes, zeros included) |
| `serving.avg_active_minutes` | **36.59** (denominator 3,663 minutes) |

### Invariants, all at their required value

| Invariant | Required | Measured |
|---|---:|---:|
| `invariant.closure.session_deltas` | 0 | 0 |
| `invariant.closure.user_deltas` | 0 | 0 |
| `invariant.runs_inverted` | 0 | 0 |
| `invariant.intervals_inverted` | 0 | 0 |
| `invariant.max_runs_per_session_minute` | 1 | **1** |
| `serving.min_concurrency` | 0 | 0 |

The last two carry the most weight. `max_runs_per_session_minute = 1` says no session-minute
is covered by two asserted runs, so no session can contribute more than 1 to concurrency at
one instant. `min_concurrency = 0` says the running sum never goes negative, so the `+1` and
`-1` deltas balance in order and not merely in total.

### One thing that looks like a defect and is not

`[V:frozen_slice_stability]` **253,590 of 599,137 foreground intervals (42.3%) are
zero-length**, `interval_end = interval_start`.

This is a consequence of storage precision, not of the interval logic.
`foreground_intervals` stores second-resolution `DateTime` while `event_state` runs at
millisecond resolution, so any segment shorter than a second truncates to a point.

It does not affect any output. `timeSlots(t, 0, 60)` returns exactly one slot, so a
zero-length interval contributes exactly one minute, which is the correct answer: a viewer
seen at 10:00:30 was watching during the 10:00 minute. The invariant that would catch real
damage here is `max_runs_per_session_minute`, and it is 1.

Recorded because 42% is alarming at a glance, and a reviewer who finds it unaided will
reasonably assume the worst.

## 6. What could not be verified

Stated plainly rather than left as a gap someone else has to find.

- **`PASS` on the stability gate.** Blocked on ingest being live. Everything else about the
  gate is measured; only the concurrency of the write is missing. `issues/ingest-2.md`.
- **Whether the live stream will resume**, and whether its vocabulary drifts further. Both
  are the ingest owner's to answer.
- **`naive_baseline_gate` is a committed `FAIL`** and remains unresolved. The naive and
  corrected delta tables span ranges differing by one minute (11:31 vs 11:32), which the gate
  treats as invalidating the comparison. The one-minute difference is explained by the
  tolerance tail, but the gate has not been re-run since. It stays `FAIL` in the ledger
  rather than being reasoned away.
