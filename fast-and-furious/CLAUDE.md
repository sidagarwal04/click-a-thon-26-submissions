# SonyLIV Click-a-thon 2026

Foreground-only concurrency at streaming scale on ClickHouse. Two halves:

- `ingest/` — Go pipeline, CSV and generator into ClickHouse Cloud. **Deployed and working.**
- `solution/` — analytics design, SQL, and a chDB-verified correctness harness. **Verified, not deployed.**
- `pipeline/` — the Cloud-deployed analytics stages. **Stages 01 and 02 deployed and verified
  on the service** (`010` DDL, `011` build, `020` serving DDL, `022` populate).

Live service: `sonyliv` (aws ap-south-1, ClickHouse 26.2, **2 replicas**, idle timeout 15 min).
Database `sonyliv`. Objects are unprefixed. There is also a `sonyliv_prod` database on the
same service carrying a separate, diverged deployment — **not ours, and not the submission**.
Never read it for a reference number: its `events_clean` is a different row count, so it
cannot agree with anything below.

Reference figures under policy `sonyliv-active-v1`: **31,947** active intervals over 10,848
sessions, hot-hour peak **2,305** at `2026-07-26 10:55:28.614`. These are our own oracle's
output, not organizer-published. Both now reproduce **on the service** (not only in chDB) and
through **two independent paths** — swept directly off `active_intervals_current`, and read
back out of `concurrency_deltas` + `concurrency_bucket_net` + `concurrency_day_anchor`.

---

## Verified ClickHouse Cloud behaviours

Everything here was measured against the live service, not inferred. Each one cost
real time to find; none of it reproduces on a single-node laptop.

### Dictionaries load per replica, and an empty one reports LOADED

**The trap.** `system.dictionaries.status = 'LOADED'` says nothing about whether the
dictionary has any rows, and each replica loads independently. Observed on the live
service, both replicas reporting `LOADED` at the same instant:

```
c-salmonaws-ak-30-server-7v70m4s-0   LOADED   element_count = 33464
c-salmonaws-ak-30-server-xtd9zjc-0   LOADED   element_count = 0
```

A query routed to the cold replica gets the *default value* from every
`dictGetOrDefault` — no error, no warning. `content_dict` returned `__unknown__` for
all 3,357 content ids on one replica and correct values on the other, depending
purely on routing.

**Observed timeline** (both replicas booted 15:50:37 when the service woke from idle):

```
16:22:15   xtd9zjc   first load, triggered by a dictGetOrDefault   ->  0 elements
16:30:54   7v70m4s   first load                                    ->  33,464
16:32:04   xtd9zjc   LIFETIME-driven reload, ~10 min later         ->  33,464
```

**It self-heals.** `LIFETIME(MIN 300 MAX 600)` retries and recovers. The exposure is
a window of up to ten minutes, not a permanent split.

**Root cause is NOT established.** `content_dim` had 33,464 rows hours before the
empty load, `content_current` reads correctly, and `last_exception` is empty. Cloud
defaults to `dictionaries_lazy_load = 1` and `CREATE OR REPLACE DICTIONARY` replicates
the definition rather than the loaded state, so the load is per-replica and on first
use — but why that particular load returned zero rows is unexplained. Do not write
this up as solved. Because the cause is unknown, "reload it once" is not a fix.

**This affects dictionaries only.** Verified across both replicas: `events_raw`,
`events_clean`, `content_dim`, `dirty_sessions` and `ingest_batches` report identical
row *and* part counts. SharedMergeTree keeps one copy in shared object storage, so
there is nothing to diverge. A dictionary is an in-memory per-replica cache — the
only object in this schema with independent per-replica state.

**Never check a dictionary locally.** Always go across replicas:

```sql
SELECT hostName(), toString(status), element_count
FROM clusterAllReplicas(default, system.dictionaries)
WHERE database = 'sonyliv' AND name = 'content_dict';
```

**Rules.** Keep the dictionary — it is the right pattern and it recovers on its own.
What must change is that the failure was silent.

- **Assert enrichment resolved before writing.** A dimension that is 100% fallback is
  a failure, not a data characteristic. This is the part that generalises: it holds
  whatever the root cause turns out to be, and for any later stage.
- **Force the load rather than relying on lazy load.** `SYSTEM RELOAD DICTIONARY` is
  synchronous and closes the window deterministically. It has to reach every replica.
- Do not swap a dictionary for a JOIN to dodge this. That treats the symptom, and the
  silent-fallback problem would still exist the next time something is enriched.

### `ENGINE = MergeTree` becomes SharedMergeTree, which changes deduplication

Cloud substitutes the engine silently. That moves insert deduplication from
`non_replicated_deduplication_window` onto `replicated_deduplication_window`, which
also expires on a timer — `replicated_deduplication_window_seconds`, server default
**3600**. The non-replicated window has no time component at all.

So "re-running a load is a no-op" holds indefinitely on a laptop and stops holding
one hour into production, with no error and a doubled row count.

**Every new MergeTree table in this project must carry all three settings**, and must
re-issue them as `ALTER TABLE … MODIFY SETTING`, because `CREATE TABLE IF NOT EXISTS`
is a no-op against an existing table and the correction would never arrive. See
`ingest/sql/002_events_raw.sql` and `pipeline/sql/010_active_intervals.sql`.

### `insert_deduplication_token` does not make a large `INSERT SELECT` idempotent

**And a doubled Summing curve passes every balance invariant.** These two together are how
stage 02 silently produced the wrong answer on 2026-08-01.

`022` statement A was run twice, four seconds apart, with a byte-identical
`insert_deduplication_token`. Both wrote:

```
20:12:18  QueryFinish  written_rows = 524292  token = stage02:sonyliv-active-v1:full:rev1
20:12:22  QueryFinish  written_rows = 524292  token = stage02:sonyliv-active-v1:full:rev1
```

`concurrency_deltas` is a SummingMergeTree, so the second load **added** to the first and the
peak became **4,610 — exactly 2 × 2,305**. The likely mechanism is that a 524k-row insert is
split across several blocks and the token is suffixed per block, so two runs whose block
boundaries differ produce different dedup keys. Not proven; the doubling is.

**The part that generalises, and matters more than the cause.** Every invariant still passed:
`sum(net) = 0`, `min(running) = 0`, `opens = closes`. A doubled curve is *perfectly balanced*.
Internal-consistency checks are structurally incapable of detecting a scalar multiple, and we
only caught it because 2,305 happened to be known — on the unseen day it would have been
invisible.

- **A verification must compare against a source outside the layer it verifies.** `022`'s V0
  asserts `sum(opens)` in `concurrency_deltas` equals `count()` in `active_intervals_current`
  and throws with the ratio. That is the only check in the file that works without already
  knowing the answer, and therefore the only one worth anything on judging day.
- **Guard on the target being empty; do not rely on dedup.** Re-running into a Summing table is
  a correctness event, not a retry. `TRUNCATE` deliberately, or pass an explicit override.
- The token is still worth setting — it catches an exact single-block replay. It is not an
  idempotency guarantee, and no file here treats it as one.

### SummingMergeTree keeps the OLDEST value, and a bare column list sums your dimensions

Two separate traps in one engine, both silent.

**Non-summable columns keep the first row in merge order.** `DateTime64` overrides
`isSummable() → false`, so `SummingSortedAlgorithm` neither sums nor maxes it. `setRow()` runs
only in `startGroup()` and `addRow()` never refreshes it, so the survivor is the
**earliest-inserted value** — not "arbitrary" as the docs say, and systematically the *oldest*.
For a lease timestamp that means the lease reads as already expired: measured, **91.05%** of
sessions have more than 60 s between their candidate timestamps. Do not quote a
`sum(DateTime64)` error as proof of this — `sum()` gates on a *different* predicate
(`isNumber() || isDecimal()`) and they coincide only by that explicit override.

**With no explicit `columns` list, every summable non-key column is summed** — including
`content_id` and `user_key`. Measured across sessions: **96.7% exceed 2⁶⁴** and 49.6% land
*below* a single input, so a wrapped `user_key` passes every plausibility check and a corrupted
`content_id` misses `content_dict` entirely, taking the silent fallback described above.
Always write `ENGINE = SummingMergeTree((col_a, col_b))`.

**And do not reach for `CollapsingMergeTree` instead.** It reduces each key group to at most two
rows, so a bucket with net +26 collapses to a single `Sign = +1` and `sum(Sign)` returns 1.
Measured damage: **86.9% undercount**. It is also not a storage win — 1.11× Summing.

### An `AggregateFunction`'s argument types are part of its type identity

`argMaxState(ts, 1)` produces `AggregateFunction(argMax, DateTime64(3,'UTC'), UInt8)`, which
**cannot be inserted** into a column declared with `UInt64` — there is no coercion, because the
type is identity, not a value:

```
Conversion from AggregateFunction(argMax, DateTime64(3,'UTC'), UInt8)
to AggregateFunction(argMax, DateTime64(3,'UTC'), UInt64) is not supported
```

A bound `{state_revision:UInt64}` parameter is fine. This only bites when parameters are
**inlined as literals**, which is exactly what happens when a `--param_*` script is rewritten
for the Cloud SQL console. Pin it with `toUInt64(...)` in the file itself so both paths behave
the same — see `pipeline/sql/022_populate_serving.sql`.

Related, same family: `argMax` is **not** on the `SimpleAggregateFunction` whitelist in 26.2
(`any, anyLast, min, max, sum, sumWithOverflow, groupBitAnd/Or/Xor, sumMap, min/maxMap,
groupArrayArray, groupUniqArrayArray, …`), so revision-resolved fields need full
`-State`/`-Merge`. And `max` is not a substitute: it is a ratchet, while a late correction can
legitimately move a value *backward*.

### Projections throw on every Replacing/Summing/Aggregating table by default

`deduplicate_merge_projection_mode` is **`throw`** on both replicas (default,
unchanged). Its in-server description restricts projections to "classic" MergeTree;
Shared**Replacing**/**Summing**/**Aggregating** are not classic, so `ADD PROJECTION`
**throws**. Measured: **9 of 16** MergeTree tables in `sonyliv_prod` and **7 of 13** in
`sonyliv` are blocked — including `events_clean`, `concurrency_deltas` and
`session_live_state`. The escapes all cost something: `drop` discards the projection on
merge, `rebuild` pays on every merge, and `ignore` is documented as possibly producing an
**incorrect answer**. `events_clean` is blocked twice over — a `SELECT ... FINAL` cannot
use a projection at all.

Projections remain available on the classic `SharedMergeTree` tables: `events_raw`,
`dirty_sessions`, `serving_concurrency_minute`, `ingest_batches`. See
`optimizations/sql/020_projections.sql`.

### The published projection docs are ahead of the server

`docs/sql-reference/statements/alter/projection` documents `WHERE` inside a projection
definition; `docs/data-modeling/projections` simultaneously lists "No WHERE clauses in
projection definitions" as a limitation. **The two pages contradict each other** — the site
publishes *latest*, not 26.2. Projection `WHERE` arrived in **26.7** (changelog #102347)
and is a **parser error** on 26.2. Verify version-dependent syntax with `EXPLAIN AST`
against the service rather than trusting the docs page.

Related gate: `_part_offset` filter projections do exist in 26.2, but
`min_table_rows_to_use_projection_index` and `max_projection_rows_to_use_projection_index`
both default to **1,000,000**, so on a smaller table the projection index is a silent no-op.

### `async_insert` defaults to 1 in 26.2, and the dedup token is inert on that path

Cloud measures `async_insert = 1, default = 1, changed = 0` — a change from the
long-standing OSS default of 0. Any client forcing it to 0 is fighting the default.

The trap underneath: **`async_insert_deduplicate` defaults to 0**, so
`insert_deduplication_token` does **nothing** on the async path and a retry duplicates
silently. If a write is async and wants idempotency it must set both. Separately, the docs
say not to combine `deduplicate_blocks_in_dependent_materialized_views` with async inserts
where dependent MVs exist — and the setting that used to make that pairing throw is
obsolete in 26.2, so it now proceeds without warning. Both corrections are in
`ingest/internal/chx/loader.go`.

### System log retention is longer than it looks — union the numbered tables

`system.query_log` appearing to start two hours ago does **not** mean the history is gone.
ClickHouse renames a system log table to a numbered suffix when the generation changes at
startup, and the old ones remain queryable: `query_log_1`, `query_log_2`, `query_log_3`,
and likewise for `metric_log`, `session_log`, `text_log`, `part_log`, `error_log`,
`asynchronous_metric_log`. On 2026-08-02 the current `query_log` began at 22:23:46 while
the numbered tables reached back to **08:38:54** — the difference between "lost to
retention" and a complete answer.

Caveat: a numbered table may exist on only one replica, so `clusterAllReplicas` over it
fails with "Table does not exist". Enumerate first:

```sql
SELECT hostName(), name, total_rows FROM clusterAllReplicas(default, system.tables)
WHERE database = 'system' AND name LIKE '%log\_%' ORDER BY name, hostName();
```

De-duplicate on `(hostname, event_time)` when unioning — `clusterAllReplicas` can return
the same row from both replicas' copies.

### An output alias shadows the column it filters on, silently

`toUInt16(13) AS rollup_mask ... WHERE rollup_mask = 5` in one query level does
**not** filter the stored column — the alias wins, the predicate becomes `13 = 5`,
and the result is **zero rows with no error**. This shipped: the deployed
`concurrency_minute_mask13` returned 0 against 85,553 mask-5 rows in its source.
Isolated on the service against the same data:

```
toUInt16(13) AS rollup_mask + WHERE rollup_mask = 5   ->      0
output alias renamed                                  -> 85,553
WHERE pushed into a subquery                          -> 85,553
```

Put the filter in a subquery when a projection alias reuses a source column name.
And assert derived views are non-empty while their source is not — that is a
reference-free check and it is the only reason this was found (`041` G6).

### Adjacent string literals are a parse error, so a `throwIf` message must be ONE literal

ClickHouse has no C-style implicit concatenation. This:

```sql
throwIf(cond,
  'part one '
  'part two')
```

is `Code: 62. Syntax error`, not a joined string. **Every gate in `041` was written
this way and had therefore never executed** — the 272,070-row minute tier was
deployed with none of its verification firing, including the check its own header
called "the only reference-free check". Write one long literal (as `011` and `022`
already do) or use `concat()`. Detect the pattern with:

```bash
python3 - <<'PY'
import re, glob
for f in glob.glob('**/*.sql', recursive=True):
    lines = open(f).read().split('\n')
    for i, l in enumerate(lines):
        if not re.fullmatch(r"\s+'.*'\s*", l): continue
        j = i - 1
        while j >= 0 and (not lines[j].strip() or lines[j].strip().startswith('--')): j -= 1
        if j >= 0 and lines[j].rstrip().endswith("'"): print(f"{f}:{i+1}")
PY
```

The generalisable rule: **a verification file that has never been executed is worse
than no verification**, because its presence is read as coverage. Run it, break
something on purpose, and confirm the gate fires.

### 26.2 does not push a filter through a `Window` step, even when the predicate is in the `PARTITION BY`

Replacing an `IN (SELECT … GROUP BY …)` revision-resolution with
`max(rev) OVER (PARTITION BY policy_version, clip_variant, session_key)` looks like
it should let a `policy_version`/`clip_variant` predicate prune, since both are in
the `PARTITION BY`. It does not: `EXPLAIN indexes = 1` shows `Condition: true`,
`Granules: 8/8`, with the `Filter` node **above** the `Window`, plus an added full
`Sorting` step. Measured 63,894 rows against a 32,768 prefix-bounded floor.

### Aggregate projections work on classic SharedMergeTree, and they can serve an `IN`-subquery

A normal view is inlined, so a caller's predicate pushes into the view's **outer**
scan — but nothing pushes it into an `IN (SELECT … GROUP BY …)` subquery, which
therefore scans the whole table on every read. `active_intervals_current` read
**96,662 rows to return 31,947** (= 63,894 unprunable inner + 32,768 pruned outer)
against a 32,768 floor.

An aggregate projection whose body is *exactly* the subquery is substituted for it:
`ReadFromMergeTree (active_intervals) Granules 8/8` becomes
`ReadFromMergeTree (proj_session_revision) Granules 3/8`. Confirm with
`force_optimize_projection = 1` — and always pair it with a negative control, since
an unrelated aggregate must throw `PROJECTION_NOT_USED` or the test proves nothing.

Eligibility splits the schema. `deduplicate_merge_projection_mode = throw` blocks
`ADD PROJECTION` on Replacing/Summing/Aggregating; of the 13 MergeTree tables in
`sonyliv`, **6 are eligible** (`active_intervals`, `concurrency_minute_versions`,
`events_raw`, `dirty_sessions`, `ingest_batches`, `ingest_rejects`) and **7 are
blocked**. Note the consequence for any redesign: turning a classic table into a
`ReplacingMergeTree` **forfeits projections on it**.

(`min_table_rows_to_use_projection_index` and
`max_projection_rows_to_use_projection_index` live in `system.settings`, not
`system.merge_tree_settings` — both 1,000,000. Querying the wrong table returns zero
rows and reads as "the setting does not exist".)

### A conflict check against a ReplacingMergeTree is a tautology

Checking for duplicate keys that disagree on payload returns zero trivially once
merges have run — the losing copy is already gone. Conflict checks must run against
the append-only landing table (`events_raw`), never the Replacing layer
(`events_clean`). Measured correctly, exactly one key in the extract conflicts, on
`subtitle_language` alone.

### `events_dedup` costs 7× on a hot path

The view groups on all four sort-key columns and runs 16 `argMax` aggregates.
Column pruning does not reach through the `GROUP BY`, so selecting two columns still
costs **0.59 s / 24.4 MB** versus **0.086 s / 15.3 MB** reading `events_clean`
directly. Use the view only for count-based checks at generation boundaries. Never
per query.

### `INNER ANY JOIN` collapses the left side too

`query-join-use-any` reads as though `ANY` bounds only the right side. In ClickHouse
an `INNER ANY JOIN` also returns at most one row per key from the **left**. Applied
to the interval builder it silently returned **zero** intervals instead of 31,947,
because every session was reduced to a single event. Do not apply that rule to a
join whose left side is the fact stream.

### `toDateTime64OrNull('')` returns the epoch, not NULL

So `ifNull(toDateTime64OrNull(param), fallback)` never reaches the fallback, and a
derived-timestamp default silently becomes 1970-01-01 — which then filters out every
row. Use an explicit `if(param = '', …, …)` instead.

### Per-column compression is empty on Cloud, and that is not data loss

`system.parts_columns` stores per-column byte counts only for Wide parts. Cloud
raises `min_bytes_for_wide_part`, so everything is Compact and reports zero for every
column. Read the by-part-format panel instead.

---

## Working rules for this repo

- **Measure on the service, don't infer.** Every Cloud-specific defect above was
  invisible on a laptop and invisible in code review. If a claim is about behaviour,
  run it against `sonyliv` and quote the number.
- **Silent wrong answers are the enemy.** This problem is scored against a private
  key, so a wrong number costs the same as a crash but arrives without warning.
  Prefer failing loud over guessing, everywhere.
- **A check that only inspects one layer cannot validate that layer.** 31,947 and 2,305
  are known *here* and will not be known on the judging day, so any assertion that
  depends on recognising them is worthless then. Every stage needs at least one
  conservation check tying its output back to its input — `022`'s V0 is the pattern.
  This rule exists because a doubled concurrency curve passed every internal invariant
  we had; see the `insert_deduplication_token` section above.
- **Don't hand over a command that has been changed but not re-run.** Both defects in
  `022` — the `UInt8` literal and the double insert — were introduced by rewriting a
  parameterised script into console literals *after* verifying the parameterised form.
  Re-verify the exact text being handed over, read-only, before handing it over.
- **The user runs commands against live infrastructure.** Hand over the exact
  command; do not execute it.
- Read-only exploration via the `clickhouse-sonyliv-cloud` MCP is fine and expected.

## Testing

- Go: `cd ingest && make check` (tests + vet + gofmt).
- Analytics correctness: `python3 solution/tools/verify_embedded.py` — runs in chDB
  against the CSVs, so it cannot see any of the Cloud behaviours above. Engine-level
  assertions must run against the service.
- Pipeline correctness on the service: the verification statements at the foot of
  `pipeline/sql/022_populate_serving.sql`. V0 is conservation (reference-free, throws),
  V1 is the peak swept straight off the deltas, V2 is the same peak via the checkpoint
  path, V4 exercises the live-count read. V1 and V2 must agree; if they disagree, the
  checkpoint layer is wrong, not the intervals.
