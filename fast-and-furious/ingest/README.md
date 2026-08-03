# `ingest/` — Go → ClickHouse ingestion pipeline

Two binaries and the DDL they depend on.

| | |
|---|---|
| **`sonyliv-ingest`** | Applies the schema, loads the two supplied CSVs, and reports on what landed |
| **`sonyliv-gen`** | Generates a synthetic event stream at a target *concurrency* and ingests it through the same write path |

The design decisions and their evidence are in **[ARCHITECTURE.md](ARCHITECTURE.md)**.
The DDL in [`sql/`](sql/) is heavily commented and is the other half of the
explanation.

---

## Quick start

```bash
cp .env.example .env      # fill in your ClickHouse Cloud service details
make build
make doctor               # preflight: is this service safe to load into?
make load DATA=/path/to/click-a-thon-2026/SonyLiv/data
make verify
```

`make load` applies the schema, loads the content catalogue, then the 905K-row
event file. Every step is idempotent — running it twice does not double the data.

For local development without a Cloud service:

```bash
make ch-up                # ClickHouse in Docker on :9000 / :8123
# then uncomment the local block in .env
```

---

## Pointing this at a real service

Run `sonyliv-ingest doctor` first. It exists because a laptop and a Cloud
service differ in ways a successful connection does not reveal, and each
difference is silent — the load works and a guarantee is quietly weaker.

```
$ sonyliv-ingest doctor
target      : clickhouse+tls://default@your-service.clickhouse.cloud:9440/default
tls         : true
server      : ClickHouse 25.x
deployment  : ClickHouse Cloud (SharedMergeTree — deduplication uses the replicated window)
database    : default (exists)

session defaults this pipeline overrides:
  async_insert            server=1  pipeline=0 for bulk, 1 for control rows

deduplication settings in place (blank = table not created yet):
  table              engine               non_repl   repl       repl_seconds
  events_raw         SharedMergeTree      1000       1000       2592000
  content_dim        SharedReplacingMerge 100        100        2592000

no problems found — safe to run `sonyliv-ingest schema`
```

### What actually differs on Cloud

**`ENGINE = MergeTree` becomes SharedMergeTree.** The DDL is unchanged; the
engine is substituted. That moves deduplication from
`non_replicated_deduplication_window` onto `replicated_deduplication_window`,
which the schema now sets to the same value so the guarantee means one thing in
both places.

**The replicated window expires on a timer.** `replicated_deduplication_window_seconds`
defaults to **3600**. The non-replicated window has no time component at all, so
"re-running a load is a no-op" is true indefinitely on a laptop and would stop
being true one hour in on Cloud. The schema sets it to 30 days. This is the one
difference most likely to be discovered as a mysteriously doubled row count, and
it is what `doctor` checks hardest for.

**`async_insert` is on by default.** Correct for small writers, wrong for a
pipeline that already sends 50K-row blocks. The connection forces it off and the
control-plane writers turn it back on per query.

**The database is not created for you.** `schema` creates tables, not databases.
`default` always exists; anything else needs `CREATE DATABASE sonyliv` first —
and a dedicated database is what you want here, since the objects are
unprefixed.

Re-running `sonyliv-ingest schema` against an existing database *converges* it —
the settings corrections are `ALTER TABLE ... MODIFY SETTING`, which is
metadata-only — so a database created by an older version of this schema is
fixed by running it again rather than rebuilt.

---

## Configuration

Credentials live in `.env`, which is gitignored. Environment variables override
the file, so CI can inject secrets without editing anything.

| Variable | Default | Notes |
|---|---|---|
| `CLICKHOUSE_HOST` | `localhost` | Service endpoint, no protocol or port |
| `CLICKHOUSE_PORT` | `9440` secure / `9000` plain | Native protocol |
| `CLICKHOUSE_SECURE` | `true` | `false` for local Docker |
| `CLICKHOUSE_USER` | `default` | |
| `CLICKHOUSE_PASSWORD` | — | |
| `CLICKHOUSE_DATABASE` | `default` | **Point this at a dedicated database.** Objects are unprefixed, so `default` risks collisions. Must already exist — `schema` creates tables, not databases |

---

## `sonyliv-ingest`

```
sonyliv-ingest doctor                          preflight a service before loading
sonyliv-ingest schema                          apply the DDL (idempotent, converging)
sonyliv-ingest schema --dry-run                print the DDL, password redacted
sonyliv-ingest content --file <content.csv>    load the catalogue
sonyliv-ingest events  --file <raw.csv>        load the event stream
sonyliv-ingest verify                          integrity + storage report
```

Every subcommand takes `--env <path>` to select a `.env`; without it the nearest
`.env` walking up from the working directory is used.

`events` flags:

| Flag | Default | |
|---|---|---|
| `--batch-size` | `50000` | Rows per INSERT. Rejected below 1,000 |
| `--workers` | `6` | Concurrent INSERT streams |
| `--retries` | `3` | Retry attempts, reusing the same dedup token |
| `--async` | `false` | Route through the server-side async buffer |
| `--limit` | `0` | Stop after N rows, for a fast smoke test |

### What `verify` reports

Row counts against the source, exact-duplicate rate (on `events_raw`, where it is
stable), the dedup layer's three counts, conflicting-payload keys,
content-dictionary join coverage, the normalized event taxonomy, the
raw→clean normalization effect, the ingest audit trail, quarantined rows,
dirty-session queue depth, parts per partition, compression by part format for
both event tables, and — where the format allows it — compression by column.

Three of those panels are worth knowing how to read:

- **`clean_rows_unmerged` drifts downward** between runs as `ReplacingMergeTree`
  merges fire. That is normal.
- **`dedup_rows` must not move** unless new data arrived. If it does, the
  conflict resolution order is wrong.
- **`conflicting_keys`** is not an error. It counts event keys whose copies
  disagree on payload and were therefore resolved by the documented
  last-write-wins rule rather than being unambiguous. The supplied extract has
  exactly one. It is read from `events_raw` and cannot be read from
  `events_clean` — RMT deletes the losing copy, so the clean layer reports zero
  once a merge has run.

Measured on ClickHouse Cloud 26.2 (`sonyliv`, aws ap-south-1, 2 replicas),
supplied extract, post-split schema:

```
events 905,558 · sessions 10,866 · users 9,618
range  2026-07-14 15:43:58.144 .. 2026-07-26 11:30:04.847 UTC
source csv:ch-hackathon-raw-data.csv

landed rows         905,558     events_raw
clean rows          901,348     events_clean, after merges
dedup rows          901,348     events_dedup  (semantic-key excess 0)
collapsed by merges   4,210     = 4,209 exact duplicates + 1 conflicting payload

duplicate rows      4,209 (0.4648%)   measured on events_raw
conflicting keys    1 key / 2 rows / 2 distinct payloads, in events_raw
unjoinable content  0 of 3,357 distinct ids
rejected rows       0
subtitle values     11 raw -> 5 normalized
audio values        41 raw -> 17 normalized

signal      liveness 780,754 (86.6%)  resume 31,590  pause 27,202
            background 14,616  foreground 14,291  session_end 10,870
            session_start 10,866  play 10,866  error 293

events_raw       5.20 MiB on disk / 197.09 MiB uncompressed (37.9x, 6.02 B/row)
                    4 parts, 1 partition  (monthly, lifecycle only)
events_clean     5.81 MiB on disk / 197.44 MiB uncompressed (34.0x, 6.76 B/row)
                    16 parts, 7 partitions  (daily by session start)
both tables     11.01 MiB on disk / 394.53 MiB uncompressed (35.8x)
dirty_sessions  701.78 KiB, 10,943 rows covering 10,866 distinct sessions
content_dim     221.02 KiB, 33,464 rows

load                19 batches, 0 failed, 0 retries, avg 714 ms / max 1,090 ms
```

**The split roughly doubles event storage** — 11.01 MiB against 4.78 MiB for the
previous single table — because every event is now kept twice, verbatim and
normalized. That is the price of the landing zone being evidence, and at this
scale it is 11 MiB. `events_clean` costs slightly more per row than `events_raw`
despite carrying more columns and 4,210 fewer rows: it holds both the hex ids
*and* the `UInt64` keys derived from them, which is what makes the touched-session
read a point lookup on an integer.

`events_raw` sitting in **1 partition** and `events_clean` in **7** is the
partitioning decision showing up in the data: monthly on event time for
lifecycle, daily on session start so a session never straddles a partition and
`ReplacingMergeTree` can collapse completely. `semantic_key_excess = 0` confirms
it did.

The conflicting-payload row is the split justifying itself. It is **invisible in
`events_clean`** — RMT deleted the losing copy — and **fully recoverable from
`events_raw`**, which still holds both rows and both payloads. Had the landing
table been a `ReplacingMergeTree`, that row would be unrecoverable and the
duplicate rate unmeasurable.

**Per-column compression is empty on Cloud, and that is not a fault.**
`system.parts_columns` stores per-column byte counts only for Wide parts; a
Compact part holds every column in one file and reports zero for all of them.
`min_bytes_for_wide_part` decides which you get (10 MiB of uncompressed data per
part by default), and Cloud raises it because object storage prefers fewer,
larger files. The by-part-format panel above answers the same question and works
everywhere. Forcing Wide parts to populate a report would be the wrong trade
against the storage layer.

Latency figures are one client on one laptop against one region. Benchmark
numbers for the submission should come from `system.query_log` on the service.

---

## `sonyliv-gen`

The primary dial is **concurrency**, not row count — this workload is described
in "how many sessions are active right now", and event volume follows from that
times the heartbeat cadence. `--max-events` and `--eps` cap output when a fixed
budget matters.

```bash
# live demo: 2,000 concurrent sessions, 10 event-minutes at 30x real time
sonyliv-gen --concurrency 2000 --duration 10m --speed 30

# load test: 5M events as fast as the service accepts them
sonyliv-gen --concurrency 20000 --max-events 5000000

# producer that cannot batch: 500-row batches via the async insert buffer
sonyliv-gen --concurrency 200 --duration 2m --batch-size 500 --async

# count without writing
sonyliv-gen --concurrency 500 --duration 5m --dry-run
```

### Volume and pacing

| Flag | Default | |
|---|---|---|
| `--concurrency` | `500` | Steady-state simultaneously-active sessions |
| `--duration` | — | Event-time span, e.g. `10m` |
| `--max-events` | `0` | Hard cap on rows emitted |
| `--ramp-up` | `30s` | Event-time to climb to target concurrency |
| `--speed` | `0` | Event-seconds per wall-second. `30` = 30x real time; `0` = unthrottled backfill |
| `--eps` | `0` | Wall-clock events/second ceiling |
| `--flush-every` | auto | Partial-batch flush, in *event* time. Auto-set to ~1 wall-second in live mode |
| `--drain` | `false` | Let sessions finish past the cutoff instead of leaving them open |
| `--start-at` | now | Event-time origin, RFC3339 |

At least one of `--duration` or `--max-events` is required; without either the
run would never terminate.

### Realism

Defaults come from the measured extract. The generator reproduces the awkward
parts on purpose — a clean stream would validate nothing:

| Flag | Default | Measured basis |
|---|---|---|
| `--heartbeat` | `40s` | The real cadence is 40.00s at p50, **not** the 60s the data dictionary claims |
| `--session-median` / `--session-p99` | `12m` / `74m` | Lognormal; reproduces the marathon tail |
| `--bg-episodes` | `1.35` | Background windows: p50 35s, p90 512s, mean 229s (lognormal) |
| `--pause-episodes` | `2.5` | Pause windows: p50 21s, p90 291s |
| `--late-fraction` / `--late-max` | `0.07` / `2m` | 7.0% of source rows are out of order within their own session |
| `--dup-fraction` | `0.005` | 0.465% of source rows are byte-identical repeats |
| `--error-prob` | `0.027` | `VideoError` never terminates a session |
| `--bot-share` | `0` | Off by default. Set it to route sessions to one shared identity, reproducing the observed 301-session / 95-concurrent outlier |
| `--seed` | `20260801` | Same seed + same flags = byte-identical output |

Behaviours baked in, not configurable:

- **Heartbeats stop while backgrounded** — only 17.7% of real background windows
  contain any event, and 78.5% of windows over 120s contain none.
- **Heartbeats continue during a foreground pause**, at ~39% of nominal rate. So
  pause is *not* detectable from silence; it must be read from the explicit event.
- **74% of iPhone sessions never emit the periodic trio**, so a liveness rule
  based on the trio silently drops most iOS traffic.
- **`pause`/`resume` are lowercase sub-values of `VideoHeartbeat`**, never their
  own `event_type`.
- **A session does not close mid-background** — its End arrives after the user
  returns.
- **Playback does not start while backgrounded** — background and pause episodes
  are drawn from the moment play begins, not from the session start.
- **Content ids are drawn from the real catalogue**, so generated traffic
  exercises the same dictionary join as replayed traffic. Load the catalogue
  first.

By default the run stops dead at the cutoff, leaving the steady-state population
**open** — the "sessions still open when the day ends" case the problem statement
calls out. `--drain` closes everything instead.

The cutoff bounds *event* time, not arrival time. In-flight rows that happened
inside the window still arrive after it — that is the boundary case worth
generating — but a row whose event time lands beyond the cutoff is dropped and
counted, so the emitted data never exceeds the window the run advertises.

### Determinism

The same `--seed` and flags produce byte-identical rows in identical batches.
Because the deduplication token includes the config fingerprint, **re-running the
exact same generation is a no-op**, while changing any knob produces a genuinely
new load. The fingerprint is printed at startup.

The fingerprint covers the sampled catalogue as well as the flags. `--content-pool`
and a catalogue reload both change which content ids appear in the output while
every flag stays the same; without that, the second run would inherit the first
run's token and ClickHouse would drop it as a replay.

---

## Schema

Applied in file-name order; every statement is idempotent.

| Object | |
|---|---|
| `content_dim` | Catalogue, `ReplacingMergeTree(source_version)` |
| `content_current` | `argMax` view resolving replacements without `FINAL` |
| `content_dict` | `COMPLEX_KEY_HASHED()` enrichment dictionary — complex-key because a simple key is coerced to `UInt64` and the catalogue contains one negative id |
| `events_raw` | Landing zone. Source rows verbatim, `MergeTree`, append-only, never deduplicated in place |
| `events_clean` | Normalized derivation, `ReplacingMergeTree(row_version)` keyed on the semantic event key |
| `events_raw_to_clean_mv` | Row-local normalization MV — the only place a normalization rule exists |
| `events_dedup` | **Read this, not `events_clean`.** `argMax` view: one row per event key, correct before any merge runs |
| `dirty_sessions` | Touched-session work queue |
| `events_raw_to_dirty_mv` | Block-local MV feeding the queue |
| `ingest_batches` | One row per acknowledged batch — the pipeline evidence |
| `ingest_rejects` | Quarantine, 30-day TTL |

Objects are **unprefixed**, so point `CLICKHOUSE_DATABASE` at a dedicated
database rather than `default` — `events_raw` is an easy name to collide with.

### The two event tables

Duplicates get handled three times, at three different costs, and the split is
deliberate:

| Duplicate kind | Handled by | Cost |
|---|---|---|
| Retried or replayed INSERT batch | `insert_deduplication_token` + the dedup windows on `events_raw` | Free — the rows are never written |
| Re-delivered row, storage | `ReplacingMergeTree` on `events_clean` | Background merge |
| Re-delivered or conflicting row, *answer* | `events_dedup` (`argMax` by `row_version`) | One `GROUP BY`, already needed |

`events_raw` is **not** a `ReplacingMergeTree`, on purpose. Its row count and its
duplicate rate have to be stable and measurable — "the extract contains 4,209
excess exact rows and one conflicting-payload row" stops being a checkable claim
the moment merges start deleting the losing copy. It is also what makes a
normalization rule correctable: `events_clean` can be rebuilt from it under a new
rule, which is impossible once the raw casing has been overwritten.

`events_clean` is the opposite — derived, disposable, and free to collapse. Its
row count *is* merge-dependent, which is why the duplicate-rate check in
`sonyliv-ingest verify` reads `events_raw` and never `events_clean`.

The engine and the view are both needed. The engine reclaims space that would
otherwise accumulate forever under an at-least-once producer; the view guarantees
the answer, because replacement is eventual and both copies stay visible until a
merge fires. Verified: `events_dedup` returns identical rows and identical
conflict resolution before and after `OPTIMIZE FINAL`.

The DDL is parameterized with `{{db}}`, `{{ch_user}}`, `{{ch_password}}`,
substituted from `.env` at apply time. Credentials are needed only for the
content dictionary's `SOURCE` clause, which authenticates even against a table
on the same server; they are redacted in `--dry-run` output and in error
messages. See the comment in [`sql/001_content.sql`](sql/001_content.sql) for the
named-collection alternative.

### Where this stops

This is the ingestion boundary, not the concurrency model. Session compaction,
interval extraction, boundary deltas and the minute serving cache read from
`events_dedup` and `dirty_sessions`. No dashboard query should touch either
event table directly, and nothing downstream should read `events_clean` without
going through `events_dedup` — a raw read of a `ReplacingMergeTree` can see both
copies of a duplicate.

---

## Development

```bash
make check     # tests + vet + gofmt
make test
```

Tests cover the parts where being wrong is silent: content-id sign handling,
timestamp unit detection, header-name column mapping, quarantine behaviour in
both readers, comment-aware DDL splitting, password redaction, dedup-token and
fingerprint collisions, retry classification, audit rows surviving a failed
flush, generator determinism, the event-time cutoff bound, and the invariant
that playback never starts on a backgrounded session.
