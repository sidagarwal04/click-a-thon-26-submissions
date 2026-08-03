# Ingestion architecture

Design record for the Go → ClickHouse ingestion layer, produced against the
`clickhouse-architecture-advisor` and `clickhouse-best-practices` skills.

Every recommendation carries a provenance label, per the advisor skill:

- **[official]** — directly backed by ClickHouse documentation or a named rule.
- **[derived]** — follows from documented behaviour plus measurements on the
  supplied extract.
- **[field]** — operational heuristic; situational, and flagged as such.

---

## Workload Summary

| | |
|---|---|
| **Workload** | IoT / telemetry (player heartbeats), append-heavy |
| **Latency target** | Ingest: seconds. Serving: dashboard-grade, sub-second warm — measured on the target service, not claimed here |
| **Data shape** | 905,558 events · 10,866 sessions · 9,618 users · 33,464 catalogue rows. 93.2% heartbeats; the periodic ping trio alone is 53.7% of all rows |
| **Skew** | 94.2% of events on one day; 86.2% in a single hour. ~217 ev/s sustained, 307 ev/s peak minute, 426 ev/s peak second |
| **Disorder** | 7.0% of rows out of order within their own session; 99.65% of sessions contain at least one. 0.465% exact duplicate rows |
| **Primary query patterns** | (a) touched-session history lookup on the correction path; (b) minute/hour/day peak and average concurrency with dimension filters, served from a pre-aggregated layer, never from raw |
| **Operational constraints** | ClickHouse Cloud; `default` database; credentials in `.env`; must behave sanely at 100x (~90M events, ~21,700 ev/s sustained) |

The scale that matters is not 905K rows. It is that the ingest path must stay
correct when the same file is replayed, when a batch fails halfway, and when
events for a session arrive hours after that session's later events.

---

## Key Decisions

| Decision | Choice | Category |
|---|---|---|
| Ingestion mechanism | Client-side native batches, 50K rows, 6 concurrent streams | official |
| Async inserts | Only where the producer genuinely cannot batch (control-plane rows) | official |
| Buffer tables | Rejected | derived |
| Kafka | Right answer at 100x for decoupling; out of scope here, interface left open | derived |
| Event storage | Two tables: verbatim `events_raw`, normalized `events_clean` | derived |
| Normalization placement | Server-side, in the raw→clean MV only; no client computes it | derived |
| Row-level dedup | `ReplacingMergeTree` on clean for space, `argMax` view for the answer | derived |
| Batch-level dedup | `insert_deduplication_token` over deterministically-cut chunks | official |
| Raw `ORDER BY` | `(video_session_id, event_timestamp)` — deliberate exception to low-cardinality-first | derived |
| Clean `ORDER BY` | `(session_key, event_ts, event_type, event)` — the semantic event key, so the engine and the dedup view agree | derived |
| Partitioning | Raw `toYYYYMM(event_timestamp)` for lifecycle; clean `toYYYYMMDD(session_start_ts)` for session locality | official |
| Late arrivals / open sessions | Append-only raw + block-local dirty-session MV; no mutations | official |
| Stored row fingerprint | Removed after measurement; computed on demand | derived |

---

## Recommendations

### 1. Client-side native batching as the primary write path

**What**
Each chunk of 50,000 rows becomes exactly one `INSERT` over the native protocol,
issued by 6 concurrent goroutines against `events_raw`.

**Why**
The decision framework in `decision-ingestion-strategy` keys on one question:
can the producer batch? A CSV loader and a synthetic generator both can, trivially.
That puts this workload in the first row of the table — *"producers can batch to
10K–100K rows → direct inserts"* — and `insert-batch-size` fixes the range.
Native is the cheapest format for the server to ingest (`insert-format-native`);
the Go client sends columnar blocks with no text parsing on either side.

50K is chosen inside the 10K–100K band rather than at the top of it because the
peak-hour arrival rate is ~217 ev/s: a 100K batch would mean one insert every
~7.7 minutes of real time, which is a freshness cost with no throughput benefit.

**How**
`internal/chx/loader.go`. Chunks are cut by the *reader*, at fixed row counts in
source order, and handed to whichever worker is free — never cut by the worker
itself. That separation is what makes chunk N contain the same rows regardless
of how many workers are running.

**Category** official
**Confidence** high
**Source**
- https://clickhouse.com/docs/best-practices/selecting-an-insert-strategy
- rules `insert-batch-size`, `insert-format-native`, `decision-ingestion-strategy`

**Validation** (measured, local Docker ClickHouse 26.7.1, Apple silicon — *not* a
Cloud latency claim)
```
905,558 rows · 19 batches · 638 ms wall
insert latency p50 65 ms · p99 141 ms · retries 0
16 active parts across 7 partitions, max 4 parts per partition
```
Part count is the number to watch, not wall time: `parts_to_throw_insert`
defaults to 3,000 per partition, and at 4 there is three orders of magnitude of
headroom before merges become the bottleneck.

---

### 2. `async_insert` forced OFF on the bulk path, ON for control rows

**What**
The connection sets `async_insert = 0`. The audit and quarantine writers
re-enable it per query with `wait_for_async_insert = 1`.

**Why**
This is the non-obvious half of the async-insert rule. **ClickHouse Cloud enables
`async_insert` by default.** Left alone, an already-correct 50K-row native block
would be copied into the server-side buffer and wait out a flush timeout — a
latency cost and an extra copy, for a problem the client already solved.

The inverse case is real, though, and this pipeline has it. `ingest_batches`
receives one small row per completed batch. There is nothing to batch it with,
which is exactly the condition `insert-async-small-batches` describes. Those
writers buffer in-process *and* enable async inserts, so whatever still arrives
in dribs is coalesced server-side into properly sized parts.

`wait_for_async_insert` stays at `1` everywhere. Fire-and-forget would hide the
failures the audit table exists to record.

For the same reason, a failed flush puts its rows back in the buffer instead of
discarding them, and sends the two tables independently so a failure on one does
not lose the other. Retention is bounded at 10,000 rows; anything trimmed past
that is counted and reported by `Close`, because a short audit table that is
never explained reads as "nothing went wrong".

**How** `internal/chx/client.go` (connection default), `internal/chx/audit.go`
(per-query override).

**Category** official
**Confidence** high
**Source**
- https://clickhouse.com/docs/optimize/asynchronous-inserts
- rule `insert-async-small-batches`

**Validation**
```sql
SELECT query_kind, Settings['async_insert'] AS async, count()
FROM system.query_log
WHERE type = 'QueryFinish' AND query LIKE 'INSERT INTO %events_raw%'
GROUP BY query_kind, async;
```

---

### 3. Buffer tables rejected

**What** No `ENGINE = Buffer` anywhere in the pipeline.

**Why**
Buffer tables solve the same problem as async inserts — absorbing small writes —
but with strictly worse properties for this system:

1. **Durability.** Buffered rows live in RAM and are lost on restart or crash.
   An async insert with `wait_for_async_insert=1` does not return until the data
   is in a part, so an acknowledged row is a durable row.
2. **No deduplication.** Buffer sits outside insert deduplication, so the retry
   safety in decision 5 would simply not apply — a retried batch would duplicate.
3. **Materialized views.** A view attached to a Buffer table does not fire on
   insert; the dirty-session queue would need rewiring around it.
4. **No benefit here.** The producer already emits 50K-row batches. Buffer's
   entire value is fixing small writes, and there are none on this path.

**Category** derived (from documented Buffer semantics plus this workload's shape)
**Confidence** high

---

### 4. Two event tables: a verbatim landing zone and a normalized derivation

**What**
Events land twice, in two tables with different jobs.

| Object | Engine | Job |
|---|---|---|
| `events_raw` | `MergeTree` | Source rows exactly as received. Never mutated, never deduplicated in place. |
| `events_clean` | `ReplacingMergeTree(row_version)` | Normalized, keyed on the semantic event key, duplicates collapsed. |
| `events_raw_to_clean_mv` | MV | The row-local transform between them. The only place a normalization rule exists. |
| `events_dedup` | View | `argMax` resolution — exactly one row per event key, correct before any merge runs. |

Normalization lives entirely in the MV's `SELECT`:

| Output | Fixes |
|---|---|
| `audio_language`, `subtitle_language` | `unk`/`UNK`/`und`/`''` → `unknown`; `eng-English` → `eng`; `OFF`/`off` unified. Measured effect: 41 raw audio values → 17; 11 raw subtitle values → 5 |
| `player_version` | 1,534 empty start rows → `unknown` |
| `signal` (Enum8) | 47 inconsistently-cased event names → 9 semantic classes |
| `is_periodic_ping` | Flags the 53.7% of rows that are the `{network-activity, buffer-health, video-resize}` trio |
| `event_date`, `session_start_date` | Derived date keys |

**Why**

*Why normalize at all:* `VideoSessionStart` emits `unk` and `''` while later
events emit `UNK` and `OFF`. Without normalization every `GROUP BY` on a language
dimension double-counts. And `pause`/`resume` exist **only** as lowercase
sub-values of `event_type = 'VideoHeartbeat'` — a state machine that reads
`event_type` alone cannot see a pause at all.

*Why server-side rather than in the Go producer:* the rule must be identical for
every producer, forever — the CSV backfill, the generator, a future Kafka
consumer. A normalization rule that lives in one client is a rule that will
eventually differ between clients. Putting it in the MV makes agreement
structural instead of a convention. `model.RawEvent` has no normalized fields at
all, so a client physically cannot supply a different answer.

*Why two tables rather than normalized columns alongside the source:* an earlier
revision kept both forms as `MATERIALIZED` columns on one table. Splitting them
buys three things that the single table could not have:

- **The duplicate rate stays measurable.** `events_clean` collapses duplicates;
  `events_raw` never does. Had the collapse happened in the landing table, its
  row count would drift with merge activity and "the extract contains 4,209
  excess exact rows and one conflicting-payload row" would stop being a
  checkable claim.
- **A normalization rule can be corrected.** Rebuilding `events_clean` from
  `events_raw` under a new rule is a re-`INSERT`. With the raw casing overwritten
  it would be unrecoverable.
- **The hot read gets the right sort key.** `events_clean` sorts on
  `(session_key, event_ts, event_type, event)` — the semantic event key, which
  is both what the touched-session read wants and what the engine needs in order
  to consider two rows duplicates. The landing table cannot have that sort key
  and also stay verbatim.

*Why `ReplacingMergeTree` on clean but not on raw:* the two are not the same
decision. On `events_clean` the collapse reclaims space that would otherwise
accumulate forever under an at-least-once producer, and the losing row is
redundant. On `events_raw` the identical collapse would destroy the evidence and
delete the only other copy of a conflicting payload. Same mechanism, opposite
value, because the tables have opposite contracts.

*Why the view is still needed on top of the engine:* replacement is eventual.
Until a merge runs both copies are visible, so an answer that depends on the
engine having collapsed anything is an answer that depends on merge timing.
`events_dedup` resolves with `argMax(…, row_version)` and never `FINAL`.
Verified: identical output before and after `OPTIMIZE FINAL`, including the
conflicting-payload row resolving to the same winner both times.

`signal` is `Enum8`, not a string, because the output set is closed by
construction — the `multiIf` ends in a `'liveness'` fallback. That gets
validation for free and costs one byte. Adding a class later is a metadata-only
`ALTER`. `event_type` in `events_raw` stays an open `LowCardinality(String)`:
the unseen day may introduce a type the dictionary does not list, and an Enum
there would reject the whole insert block rather than land the row.

**Category** derived
**Confidence** high
**Source** rules `schema-types-enum`, `schema-types-lowcardinality`,
`schema-types-avoid-nullable`, `insert-optimize-avoid-final`,
`query-mv-incremental`

**Validation**
```sql
-- normalization is running
SELECT (SELECT uniqExact(subtitle_language) FROM default.events_raw)   AS raw,
       (SELECT uniqExact(subtitle_language) FROM default.events_clean) AS normalized;
                                       -- measured: 11 -> 5

SELECT signal, count() FROM default.events_dedup GROUP BY signal ORDER BY 2 DESC;

-- the dedup answer does not depend on merge state
SELECT count() FROM default.events_clean;   -- drifts downward as merges fire
SELECT count() FROM default.events_dedup;   -- must not move without new data
```
Cross-checked against the independently-measured event taxonomy:
`pause` = **27,340**, `resume` = **31,780** — the bare lowercase events only.

`speed-pause` (380), `speed-resume` (380), `AdPause` (45) and `AdResume` (27)
classify as **`liveness`**, not as play-state transitions. An ad break is the
player pausing itself and a speed-pause/resume pair brackets a rate change;
in neither case has the viewer stopped watching, so neither should remove the
session from a concurrency count. Treating ad breaks as pauses would sag the
metric hardest in the hot hours, where ad load is densest. 832 rows total in
this extract, but both rates are functions of ad load and player features
rather than of this dataset.

---

### 5. Idempotency by deterministic chunking plus a deduplication token

**What**
Every batch carries `insert_deduplication_token = source | file-sha256 |
batch-size | row-count | ordinal`. Retries reuse the same token. The batch UUID
is `uuidv5(namespace, token)`, so it is stable across machines and runs.

**Why**
Three failure modes, one mechanism:

- *A send that fails after the server committed the block.* Retrying without a
  token duplicates the rows; with one, the retry is a no-op. This is the case
  where "just retry" is otherwise silently wrong.
- *A re-run of the whole load.* Common during a hackathon; it must not double
  the table.
- *A different file under the same name.* The SHA-256 is in the token, so this
  is correctly treated as new data rather than swallowed.

The batch size and row count are in the token for a reason found while testing:
without them, loading the same file at `--batch-size 50000` and then at
`--batch-size 10000` produces the same token for chunks holding *different*
rows, and the second load silently loses data.

The generator side has the same hazard in a different shape, and it is the
reason its fingerprint covers the sampled catalogue rather than just the flags.
`--content-pool` and a reloaded catalogue both change which content ids appear
in the output while every other input is identical; a fingerprint blind to that
would hand two genuinely different runs the same token. The fingerprint is taken
from the constructed generator, not from the caller's config, so it reflects the
values actually used after defaults are filled in.

`deduplicate_blocks_in_dependent_materialized_views = 1` extends the same
protection to the dirty-session queue. That setting is normally risky — it can
drop legitimate identical MV output — but here the MV's output is set-like
(its identity derives from session + batch + row sequence), so identical output
can only mean a genuine retry.

**How** `internal/chx/loader.go`, `dedupToken`.

**Category** official
**Confidence** high
**Source** https://clickhouse.com/docs/best-practices/selecting-an-insert-strategy

**Validation** — measured end to end:
```
first  load: events_raw = 905,558 rows
replay same: events_raw = 905,558 rows   (19 batches sent, 0 rows added)
```
Note the table setting that makes this work on a single node:
`non_replicated_deduplication_window = 1000`. Without it, `insert_deduplication_token`
is **ignored** on a non-replicated MergeTree. Replicated / SharedMergeTree
(ClickHouse Cloud) deduplicates independently and ignores the setting. This was
caught in testing when the content catalogue silently loaded twice.

---

### 6. Raw `ORDER BY` leads with the session id — a deliberate rule exception

**What**
```sql
ORDER BY (video_session_id, event_timestamp, event_type, event)
```

**Why**
`schema-pk-cardinality-order` says order low-to-high cardinality, and this does
the opposite. The exception is justified by the access pattern, which is the
thing the rule is a proxy for.

The only hot read on `events_raw` is *"give me the complete history of these
N touched sessions, in event-time order"* — a high-cardinality point lookup on
the correction path. A session-leading key turns that into a handful of granules.
Dashboard filters (platform, content, time grain) **never touch this table**;
they are served from the pre-aggregated boundary and minute tables, which do
order low-cardinality-first exactly as the rule prescribes.

Leading with `platform` or `event_date` here would serve no query and would
destroy the one access pattern that exists.

Two things fall out of it:

- The source file is already session-major, so ingest-order and storage-order
  agree, and the two 64-char hex id columns compress **~58x** because equal
  values land adjacent.
- Byte-identical duplicate rows share both key columns, so they sort into
  consecutive positions and counting them is a local scan rather than a global
  hash aggregation.

`events_clean` extends the key to the full semantic event key,
`(session_key, event_ts, event_type, event)`, for a reason the landing table does
not have: that tuple is simultaneously the touched-session access path, the
`GROUP BY` in `events_dedup`, and the definition of "duplicate" that
`ReplacingMergeTree` enforces. All three have to be the same tuple or the layer
stops collapsing anything, so a static test asserts they match.

Because the sort key gives no help to time-ranged scans, there is a
`minmax` skipping index on `event_timestamp`. It works well here precisely *because*
of the session-major order: a session's events span ~12 minutes at p50, so each
granule's min/max is narrow. (`query-index-skipping-indices`)

**Category** derived
**Confidence** high

**Validation**
```sql
SELECT column, formatReadableSize(sum(column_data_compressed_bytes)) AS compressed,
       round(sum(column_data_uncompressed_bytes)/sum(column_data_compressed_bytes),1) AS ratio
FROM system.parts_columns
WHERE active AND table = 'events_raw' GROUP BY column ORDER BY 2 DESC;
```

---

### 7. Partition the hot layer on session start, not event time

**What**
`events_clean`: `PARTITION BY toYYYYMMDD(session_start_ts)`.
`events_raw`: `PARTITION BY toYYYYMM(event_timestamp)`.

**Why**
`session_start_ts` is constant within a session (verified: 0 of 10,866 sessions
have more than one value). Partitioning on it means every event of a session —
including the 43.6-hour outlier, and including a correction that arrives days
later — lands in exactly **one** partition. Two things depend on that:

- the touched-session read never fans out across partitions; and
- `ReplacingMergeTree` can actually finish the job. RMT only collapses within a
  partition, so a partitioning key that split a session would leave duplicate
  copies of an event permanently uncollapsed on either side of the boundary —
  silently, with no error and no way to notice except by counting.

Partitioning the clean layer on `event_timestamp` would split that 43.6-hour
session across three partitions, split every late correction away from the data
it corrects, and break the dedup.

The landing table has neither concern — nothing reads it on the hot path and it
does not deduplicate — so it partitions monthly on event time, purely for
lifecycle (`DROP PARTITION`, TTL). Coarser is better there: it keeps the
partition count trivial at any retention.

Daily granularity on the clean layer is also for *lifecycle*, not query pruning —
that is what `schema-partition-lifecycle` asks for. At 365 partitions/year it
stays inside the 100–1,000 guidance (`schema-partition-low-cardinality`) for
about two years; past that, switch to `toYYYYMM` **on both**, keeping the clean
layer keyed on session start.

**Category** official (rule) + derived (the session-start choice)
**Confidence** high
**Source** https://clickhouse.com/docs/best-practices/choosing-a-partitioning-key

---

### 8. Late arrivals and open sessions: append-only, never mutate

**What**
`events_raw` is append-only. An incremental MV records which sessions were
touched by each insert block into `dirty_sessions`. Nothing is ever updated
or deleted.

**Why**
`decision-late-arriving-upserts` puts this workload in its first row: an
immutable event log where current state is computed from ordered events. The
measured disorder makes the alternatives untenable — 99.65% of sessions contain
an out-of-order event and within-session lateness reaches ~43 hours, so there is
no watermark short of days that would let a windowed aggregate be correct.

The MV is scoped tightly and deliberately. *"Which sessions appear in the block I
just inserted"* is correct block-locally; it never needs to see another block.
Everything an incremental MV would get **wrong** on this stream is kept out of it:

- `lead`/`lag` across events — the next event may be in another block;
- "was this session foregrounded before?" — prior state is in another block;
- retracting previously-emitted output — an MV only appends.

That is why the concurrency model itself is not an MV over raw events, and it is
the direct application of the documented insert-block semantics of incremental
materialized views.

**Category** official
**Confidence** high
**Source**
- https://clickhouse.com/docs/materialized-view/incremental-materialized-view
- rules `insert-mutation-avoid-update`, `insert-mutation-avoid-delete`, `query-mv-incremental`

---

### 9. Content enrichment by dictionary, not JOIN

**What** `content_dict`, `LAYOUT(COMPLEX_KEY_HASHED())`, sourced from a
deduplicating view over a `ReplacingMergeTree`.

**Why**
33,464 rows, unique key, and **100% join coverage** against the event stream
(measured: 3,357 distinct content ids in events, 0 unjoinable). That is the
textbook dictionary case — `query-join-consider-alternatives` — and it avoids
rebuilding a hash table per query on the enrichment path.

The view resolves `ReplacingMergeTree` duplicates with `argMax` rather than
`FINAL`, because replacement by background merge is eventual and the dictionary
source must not assume it has happened (`insert-optimize-avoid-final`).

The layout is complex-key for a reason that only shows up on one row. A
simple-key dictionary key is always `UInt64`: the declared `Int64` is silently
coerced (visible in `system.dictionaries.key.types`) and every lookup on a
negative id then throws rather than missing. The catalogue holds exactly one,
`-987654322`, stored by the source system as `18446744072721897294` — the id
`csvsrc.ParseContentID` exists to recover. Parsing it correctly at ingest and
then being unable to look it up would defeat the point. Complex-key preserves
the declared type at a small memory cost, which 33K rows will not notice.

**Caveat, stated because it is a correctness trap:** a dictionary refresh does
**not** retract rows already enriched from the old values. Anything denormalized
downstream from this dictionary must be re-derived by explicitly re-dirtying the
affected sessions.

**Category** official
**Confidence** high

**Validation**
```sql
SELECT countIf(dictGetOrDefault(default.content_dict, 'video_type', tuple(content_id), '__miss__') = '__miss__')
FROM default.events_raw;   -- measured: 0, including the negative id
```

---

### 10. Types: measured, not guessed

| Choice | Reason |
|---|---|
| `content_id Int64` | The catalogue contains `18446744072721897294` = `-987654322` written unsigned, so the domain is signed. The largest positive id is 96.8% of `Int32` max — too little headroom for the unseen day. `schema-types-minimize-bitwidth` asks for the smallest type that *fits the domain*, not the smallest that fits one sample |
| `video_session_id`/`user_id` `FixedString(64)` | Length is guaranteed by the source; drops the per-value length prefix. Not `LowCardinality` — 10,866 sessions at 1x becomes ~1.09M at 100x, past where dictionary encoding helps |
| `DateTime64(3,'UTC')` | Millisecond ties are load-bearing: duplicate session starts share an exact timestamp |
| `LowCardinality(String)` for all dimensions | Every one is ≤ 84 distinct values |
| No `Nullable` anywhere | Empty means "not yet known" in this source, not "unknown value". Sentinels (`unknown`) carry that meaning without the extra null-map column (`schema-types-avoid-nullable`) |

**Category** official
**Confidence** high

---

### 11. Measured back: dropping the stored row fingerprint

**What**
An earlier revision stored `source_row_hash UInt64` (XXH64 of the canonical row)
and included it in the sort key. It was removed; the fingerprint is now computed
on demand in SQL.

**Why**
The compression report made the cost visible. A random 64-bit hash is
incompressible by construction:

| | before | after |
|---|---|---|
| `events_raw` on disk | 17.34 MiB | **6.33 MiB** |
| `source_row_hash` | 6.16 MiB @ ratio 1.0 (35% of the table) | removed |
| `batch_row_seq` | 2.94 MiB @ ratio 1.0 | 0.52 MiB @ ratio 5.5 (`T64`) |
| `event_timestamp` | 2.89 MiB @ ratio 2.1 | 1.65 MiB @ ratio 3.5 (`DoubleDelta`) |
| overall ratio | 10.1x | **26.6x** (7.3 bytes/row) |

35% of the table for a column no hot-path query reads is not defensible at 100x,
and the judging criteria explicitly weigh *what the queries read*. Exact
duplicates already sort adjacently under the sort key, and the touched-session
read is a few hundred rows — cheap to hash on the fly.

Computing it server-side also removed a real risk: the Go client and ClickHouse
had to agree on a canonical byte encoding, and any drift between them would have
produced silently wrong duplicate counts. Now there is one definition.

`batch_row_seq` survives with a `T64` codec. It is scrambled on disk (rows are
stored in sort order, not arrival order) so it cannot delta-compress, but its
values only occupy ~17 of 32 bits and `T64` transposes the bit planes to recover
most of the loss regardless of order.

**Category** derived (measured on this data)
**Confidence** high

**Validation** — identical results before and after:
```
duplicate rows: 4,209 of 905,558 (0.4648%)   [both revisions]
```

---

## What this layer deliberately does not do

- **Compute concurrency.** Raw events and a dirty-session queue are the
  ingestion boundary. Session compaction, interval extraction, boundary deltas
  and the minute serving cache read from here.
- **Serve dashboards.** No dashboard query should ever touch `events_raw`.
- **Decide semantics.** The heartbeat timeout, whether a paused-but-foregrounded
  player counts, and the duplicate-End convention are policy, resolved
  downstream. This layer preserves everything needed to apply any of them.

## The 100x question

| | 1x (measured) | 100x (projected) |
|---|---|---|
| Events | 905,558 | ~90.6M |
| `events_raw` on disk | 6.33 MiB | ~630 MiB |
| Sustained rate | 217 ev/s | ~21,700 ev/s |
| Peak second | 426 ev/s | ~42,600 ev/s |
| Inserts at 50K batches | 19 | ~1,800 |

At 21,700 ev/s a single producer emits a 50K batch roughly every 2.3 seconds —
comfortably inside the one-insert-per-second guidance, with parts-per-partition
still two orders of magnitude below `parts_to_throw_insert`.

The structural change at that scale is **not** the batch size; it is putting a
log broker in front. Multiple independent edge producers, replay after an outage,
and ingest fan-out are what Kafka is for — `decision-ingestion-strategy` marks
that path *derived*, and it is the right next step, not a hackathon-scope one.
The loader's interface is a `<-chan *Chunk`, so a Kafka consumer substitutes for
the CSV reader without touching the write path.

**[field]** A reasonable target on a production-sized Cloud service is sub-second
p95 on warm minute-grain queries — but that number has to come from
`system.query_log` on the target service. Nothing in this document is a Cloud
latency claim; the measurements here are single-node Docker on a laptop and are
labelled as such wherever they appear.
