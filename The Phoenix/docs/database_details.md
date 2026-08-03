# Database Details, Phoenix Concurrency on ClickHouse

### The canonical dictionary for what is actually in the database

Companion to [`problem/dataset_details.md`](problem/dataset_details.md), which describes the two
source CSVs as delivered. This page describes what those CSVs became: every database, every
table, what each column means, how each one has to be counted, and which table answers which
question.

It is written to be read on its own, by a person or by an assistant with no other context. If
you are asking a question about this data and you only have one document, this is the one.

Server is ClickHouse Cloud **26.2.1.525**, region `ap-south-1`. Every engine below is a `Shared*`
variant, which is Cloud's replicated implementation of the engine named in `sql/schema/`:
`SharedMergeTree` behaves as `MergeTree`, `SharedSummingMergeTree` as `SummingMergeTree`, and so
on. Storage is object storage and compute replicas are stateless, so there is no sharding and no
`ON CLUSTER` anywhere in this schema.

Every figure was read live from `system.tables`, `system.columns` and the tables themselves on
**2026-08-01 22:00 UTC**. The stream is live, so counts move. Shapes and meanings do not.

---

## Read this first: two rules for counting anything here

These are the difference between a number that reproduces and a number that happened to be true
when someone looked.

**1. Never use `system.tables.total_rows`.** It is an estimate that tracks parts, not data.
`concurrency_deltas` has reported 34,644 there and 26,904 from `count()` minutes apart with
nothing changed in the data, because background merges were still collapsing rows.

**2. Never use a bare `count()` on a Summing or Collapsing table.** `count()` reads physical rows,
and physical rows are a function of merge timing. Use the aggregate the engine maintains:

| Engine | Tables using it | Count it with | Never with |
|---|---|---|---|
| `CollapsingMergeTree(sign)` | `session_minute_runs`, `user_minute_runs` | `sum(sign)` | `count()` |
| `SummingMergeTree(delta)` | `concurrency_deltas`, `user_concurrency_deltas`, `concurrency_boundary_deltas` | `sum(delta)`, `uniqExact(minute)` | `count()` |
| `ReplacingMergeTree(version)` | `content`, every insight table | `argMax(col, version)`, or `FINAL` | a bare `SELECT` |
| `MergeTree` | `raw_events`, `foreground_intervals` | `count()` is correct here | |

Concretely: `session_minute_runs` holds **566,930 physical rows** and **83,102 asserted** ones.
The gap is retractions stored rather than applied. Both numbers are true; only one answers "how
many active runs are there".

**Every timestamp stored in this database is UTC.** The console displays IST, converting at the
edge. If you are comparing a number on a screen to a number from a query, check which one you
are holding.

---

## The databases

Updated 2026-08-02, when the unseen day arrived with two new columns and the dimension set was
widened from five to nine. The two databases the product reads are `phoenix_live` and
`phoenix_unseen`; everything else is history kept deliberately.

| Database | What it is | Read by |
|---|---|---|
| `phoenix_live` | **Generation three, live.** Concurrency model plus all ten insight tables, on the widened nine-dimension key. Continuously ingested by the `producer` container and derived by the `ticker` container | v2, and v1's "Original corpus" switch position |
| `phoenix_unseen` | **The unseen day.** 7,000,000 events for 2026-07-31, same widened schema, static by intent because these are the graded answers and must not move while being read | v1's "Unseen day" switch position, and v2 when switched |
| `phoenix` | Generation one, the originally validated engine. Untouched by the widening. Every figure in `evidence/` written before 2026-08-02 was measured here | nothing; kept for reproducibility |
| `phoenix_next` | Generation two, pre-widening. Five-dimension key | nothing; kept as rollback |
| `phoenix_unseen_pre_widen` | The unseen day on the five-dimension key, before the widening | nothing; kept as rollback |
| `phoenix_widen_full`, `phoenix_widen_test` | Scratch databases used to PROVE the widening changed no answer, before it was promoted | nothing; kept as the evidence trail |
| `phoenix_schema_ref` | An empty reference database rebuilt from the DDL files by `scripts/check_docs.sh` to detect drift | No data, ever |

Insight tables exist in `phoenix_live` and `phoenix_unseen`. They do **not** exist in `phoenix`.

### Live sizes, measured 2026-08-02

| Table | `phoenix_live` | `phoenix_unseen` |
|---|---|---|
| `raw_events` | 1,161,922 rows, 6.19 MiB | 7,000,000 rows, 29.18 MiB |
| `content` | 41,144 rows, 337.96 KiB | 33,326 rows, 270.99 KiB |
| `foreground_intervals` | 652,549 rows, 3.05 MiB | 4,647,950 rows, 23.63 MiB |
| `session_minute_runs` | 90,399 rows, 1.18 MiB | 118,498 rows, 7.74 MiB |
| `concurrency_deltas` | 32,605 rows, 94.33 KiB | 133,784 rows, **463.14 KiB** |
| `user_concurrency_deltas` | 31,167 rows, 90.58 KiB | 119,337 rows, 425.30 KiB |
| `concurrency_boundary_deltas` | 74,475 rows, 217.07 KiB | 298,048 rows, 1.39 MiB |

`phoenix_live` moves: it is under continuous ingest, so these numbers are a snapshot, not a
constant. `phoenix_unseen` is static and these are reproducible.

**The headline compression still holds at 14x the data.** 7,000,000 raw events, 29.18 MiB on disk,
collapse to a 463 KiB serving table. Cost tracks interval boundaries, not watch time.

---

## Layer 1: raw and reference

### `raw_events`, every event, as delivered

`SharedMergeTree`, `ORDER BY (video_session_id, event_timestamp)`,
`PARTITION BY toYYYYMMDD(event_timestamp)`.
**1,993,252 rows**, 14.32 MiB, spanning **2026-07-14 15:43** to **2026-08-01 21:59** UTC, across
**60,045 sessions** and **52,659 users**.

Ordered by session because every derivation step walks one session's events in time order.
Partitioned by day so a day can be dropped or replaced without touching the rest. A query that
filters only on time therefore full-scans, by design.

| Column | Type | Definition |
|---|---|---|
| `video_session_id` | `String` | One video playback. The unit session-level concurrency counts |
| `user_id` | `String` | The viewer. One user can hold several concurrent sessions across devices |
| `content_id` | `Int64` | Joins to `content` for the title. Also a filter dimension |
| `event_type` | `LowCardinality(String)` | One of `VideoSessionStart`, `VideoPlay`, `VideoHeartbeat`, `AppBackgrounded`, `AppForegrounded`, `VideoSessionEnd`, `VideoError`. Heartbeats arrive roughly once a minute. Background and foreground events are **not guaranteed** to be sent |
| `event` | `LowCardinality(String)` | The specific event within that type: `pause`, `resume`, `AdPause`, `AdResume` and so on |
| `event_timestamp` | `DateTime64(3)` | When it happened, millisecond resolution. The only time column that means anything |
| `platform` | `LowCardinality(String)` | 10 values, e.g. `ANDROID_PHONE`, `IPHONE`, `SONY_ANDROID_TV`, `JIO_ANDROID_TV`, `FIRE_TV`, `ANDROID_TAB`, `Mweb` |
| `app_version` | `LowCardinality(String)` | 65 values |
| `country` | `LowCardinality(String)` | 7 values, `india` dominant |
| `audio_language`, `subtitle_language`, `player_version` | `LowCardinality(String)` | Further filter dimensions, not used by the concurrency model |
| `session_start_epoch` | `DateTime64(3)` | Session start, repeated on every event of that session |
| `ingested_at` | `DateTime` | When the row reached the database. `ingested_at - event_timestamp` is arrival lateness |
| `event_id` | `String` | Per-event identity, so a replayed file is idempotent |

**Gotcha.** `ingested_at` was added by a later `ALTER`, and ClickHouse does not rewrite existing
parts, so for rows written before that `ALTER` the `DEFAULT now()` evaluates at **read** time and
the column equals the reading query's own clock. Never filter on it. Use `event_timestamp`.

`raw_events_landing` (engine `Null`, stores nothing) plus `raw_events_mv` form the ingest path.
The CSV carries timestamps as epoch milliseconds; the landing table accepts the file exactly as
delivered and the view converts to `DateTime64(3)` on the way through, so loading needs no
preprocessing step.

### `content`, the catalogue

`SharedReplacingMergeTree`, `ORDER BY content_id`. **33,464 rows**, 220.67 KiB. Of these, about
**3,363** appear in the serving layer at any moment; the rest have no viewing in the window.

| Column | Type | Definition |
|---|---|---|
| `content_id` | `Int64` | Join key back to `raw_events` |
| `title` | `String` | What a human calls it. The console filters on this, never on the id |
| `video_type` | `LowCardinality(String)` | `vod` or `live` |
| `category` | `LowCardinality(String)` | Genre bucket |
| `ingested_at` | `DateTime` | Load time |

**Gotcha.** Because it is a ReplacingMergeTree, an un-merged part can hold two rows for one
`content_id`. Join with `ANY LEFT JOIN`, or `argMax(title, ingested_at) GROUP BY content_id`.
A plain `LEFT JOIN` leaks duplicates. Use `LEFT` and not `INNER`: playback whose content is
missing from the catalogue is still real viewing and must still be counted.

### `event_state`, a view, not a table

Stores nothing; evaluated on read. Classifies every event into playback state and carries the
last decisive state forward per session.

| Column | Type | Meaning |
|---|---|---|
| `video_session_id` | `String` | |
| `ts` | `DateTime64(3)` | |
| `is_open` | `UInt8` | Foreground **and** playing. This is the definition the project ships |
| `is_open_pause_active` | `UInt8` | The same, except a pause does not stop the clock |

Three buckets decide the state. **Closing**: `AppBackgrounded`, `VideoSessionEnd`, `VideoError`,
and for `is_open` a heartbeat whose event is `pause`, `speed-pause` or `AdPause`. **Opening**:
`VideoSessionStart`, `VideoPlay`, `AppForegrounded`, and a heartbeat whose event is `resume`,
`speed-resume` or `AdResume`. **Everything else is neutral** and carries the previous state
forward, so an event value nobody has seen before can never start counting somebody as watching.

Millisecond resolution matters: 29 percent of events share a second with another event, and at
second resolution a pause and a resume in the same second resolved differently on different runs.
Close beats open at the same instant.

---

## Layer 2: the concurrency model

The chain is `raw_events` -> `foreground_intervals` -> `session_minute_runs` ->
`concurrency_deltas`, with `user_minute_runs` and `user_concurrency_deltas` branching off the
session runs. It narrows hard: two million events become a 113 KiB serving table, because cost
tracks interval **boundaries** rather than watch time. A three-hour session costs the same two
delta rows as a two-minute one.

### `foreground_intervals`, when a session was genuinely watching

`SharedMergeTree`, `ORDER BY (video_session_id, interval_start)`. **1,531,152 rows**, 12.91 MiB.

One row per contiguous stretch of real playback. Backgrounded time, paused time and
heartbeat-silent time are already excluded here. This is where "foreground only" is decided, and
everything downstream inherits it.

| Column | Type | Definition |
|---|---|---|
| `video_session_id` | `String` | The session |
| `user_id` | `String` | The viewer |
| `content_id` | `Int64` | What they were watching |
| `platform`, `country`, `app_version`, `video_type` | `LowCardinality(String)` | Dimensions attached here so nothing downstream joins back |
| `interval_start` | `DateTime` | Inclusive |
| `interval_end` | `DateTime` | Exclusive |

**The boundary rule.** `interval_end = least(if(next_ts > ts, next_ts, ts + tol), ts + tol)`,
where `tol` is a **90 second gap tolerance**. That tolerance comes from the observed gap
distribution (p90 40s, p99 76s), not from the nominal 60s heartbeat: 60s would falsely split
about 1 percent of normal traffic.

**Looks alarming, is not.** Roughly 42 percent of intervals are zero-length,
`interval_end = interval_start`. This table stores second-resolution `DateTime` while
`event_state` runs at milliseconds, so a sub-second segment truncates to a point. It changes no
output, because a viewer seen at 10:00:30 was indeed watching during the 10:00 minute.

### `session_minute_runs`, active ranges, minute aligned, revisable

`SharedCollapsingMergeTree(sign)`, `ORDER BY (video_session_id, run_start, run_end)`.
**566,930 physical rows, 83,102 asserted**, 14.31 MiB.

Intervals snapped to whole minutes and merged into runs. **This is the table that absorbs
updates.** When a new heartbeat changes what a session was doing, the pipeline writes `sign = -1`
rows retracting every run that session currently asserts, then re-asserts from the session's full
history. That is why re-deriving a session is idempotent, and why an open session whose active
range keeps growing never requires a rebuild.

| Column | Type | Definition |
|---|---|---|
| `video_session_id` | `String` | The session |
| `user_id`, `content_id`, `platform`, `country`, `app_version`, `video_type` | | Dimensions |
| `run_start` | `DateTime` | First active minute, inclusive |
| `run_end` | `DateTime` | Last active minute, inclusive |
| `sign` | `Int8` | `+1` asserts this run, `-1` retracts it |

Collapsing rather than mutation because a late heartbeat must be able to revise a published
minute without `ALTER TABLE ... UPDATE`, which on a table this size would be a mutation storm.

### `user_minute_runs`, the same, collapsed per user

`SharedCollapsingMergeTree(sign)`, `ORDER BY (user_id, run_start, run_end)`.
**370,054 physical rows, 73,582 asserted**, 5.64 MiB.

Every session a user had, collapsed into the minutes that user was watching **at all**. Two
sessions overlapping in one minute contribute that minute once. That single difference is the
entire gap between session concurrency and user concurrency: one viewer on a phone and a TV is
two sessions and one user.

Dimensions are those of the user's earliest run, since a viewer can move across platforms
mid-view and one row has to pick.

### `concurrency_deltas`, what the dashboard reads

`SharedSummingMergeTree(delta)`,
`ORDER BY (platform, country, video_type, content_id, app_version, audio_language,
subtitle_language, player_version, video_resolution, minute)`.
On the unseen day: **133,784 physical rows**, 463.14 KiB.

Each active run contributes `+1` at its first minute and `-1` at the minute after its last.
Concurrency at any minute is the running sum of every delta up to and including it.

| Column | Type | Definition |
|---|---|---|
| `platform`, `country`, `video_type` | `LowCardinality(String)` | Filter dimensions, and the ordering-key prefix |
| `content_id` | `Int64` | Filter dimension |
| `app_version` | `LowCardinality(String)` | Filter dimension |
| `audio_language`, `subtitle_language`, `player_version` | `LowCardinality(String)` | Filter dimensions, added 2026-08-02 |
| `video_resolution` | `LowCardinality(String)` | Filter dimension, **new column on the unseen day**. Values are free-form and fuse a quality mode with a pixel size (`1920*1080`, `Auto-1280*720`, `DataSaver-640x360`, `NA`); 2,071 distinct in `raw_events`, 706 in the delta table. Stored VERBATIM, never normalised, because a normalisation changes which rows a filter selects and therefore the graded answer |
| `minute` | `DateTime` | Minute bucket, UTC |
| `delta` | `Int32` | Net change in concurrency at that minute for that dimension tuple |

**Why `minute` sits last in the key.** A cumulative sum must be seeded by every delta *before* the
requested window, so a time predicate cannot prune it: starting the sum inside the window loses
every session that opened earlier and is still watching. What *can* prune is a dimension filter,
so the dimensions occupy the prunable prefix. A `platform` filter cuts the read to 2 of 4 granules
and 16,384 rows where unfiltered reads 30,662.

**Why the four new dimensions were APPENDED rather than sorted in by cardinality, and what that
costs.** The first five columns are the prefix every existing filter prunes on and every published
read figure was measured against. Inserting `video_resolution` (2,071 distinct in raw_events, 706 in the delta table) mid-key would have
silently changed what a `platform` filter prunes, and a headline number would have moved for a
reason no reader could see.

The cost is real and is stated rather than hidden: **a filter on a suffix dimension alone prunes
almost nothing.** Measured through the deployed API on the unseen day, unfiltered reads 354,305
rows and filtering by `video_resolution` reads 354,185. Prefix filters prune; suffix filters do
not. Combining a prefix filter with a suffix one does prune, because the prefix still engages.
Addressing this properly is a filter-key structure (a projection or a second differently-keyed
serving table), which is under review rather than assumed.

**How to query it correctly.** Seed the cumulative sum from before the window. A session that
opened at 09:00 and is still watching at 10:30 must count in a 10:00 window and contributes no
delta inside it. Filtering deltas to the range and summing inside is the single most common way
to get this wrong. `sql/queries/serving/concurrency_curve.sql` does it correctly and documents
every trap it avoids.

**The closure invariant.** `sum(delta) = 0` over the whole table means every session that opened
also closed. A non-zero value means a run was asserted without its retraction and the pipeline is
corrupt. Currently **0**.

### `user_concurrency_deltas`

Same shape, same engine, same ordering key, fed from `user_minute_runs`. **34,002 rows**,
105.06 KiB, closure **0**. Read this for session-independent concurrency. It is not a copy: a user
with two concurrent sessions counts 2 in `concurrency_deltas` and 1 here.

### `concurrency_boundary_deltas`, exact, second resolution

`SharedSummingMergeTree(delta)`,
`ORDER BY (platform, country, video_type, content_id, app_version, ts)`. **178,226 rows**,
757.13 KiB.

Deltas at exact interval boundaries rather than snapped to minutes, for peak and average at
second resolution. Larger than the minute table because boundaries falling in the same minute
cannot merge. Use it when the exact instant of a peak matters; use `concurrency_deltas` for
everything else.

### `concurrency_deltas_naive`, the deliberately wrong baseline

`SharedSummingMergeTree(delta)`, same key and columns as `concurrency_deltas`. **15,725 rows**,
40.79 KiB.

Concurrency computed from raw session open/close spans, with no foreground filtering, so a
backgrounded app counts as watching. It exists so the value of the foreground-only correction is
a measured number rather than an assertion. **Never serve from it.**

### Materialized views

`concurrency_deltas_mv` and `user_concurrency_deltas_mv` turn each run into its two delta rows:

```sql
SELECT platform, country, video_type, content_id, app_version,
       d.1 AS minute, d.2 * sign AS delta
FROM session_minute_runs
ARRAY JOIN [(run_start, 1), (run_end + toIntervalMinute(1), -1)] AS d
```

The `* sign` is the whole trick: a retraction automatically emits the inverse pair, so a revised
run cancels itself out with no bookkeeping. `concurrency_boundary_deltas_mv` does the same at
second resolution, and `raw_events_mv` handles the epoch-millis conversion at ingest.

---

## Layer 3: insights, in `phoenix_next` only

These sit on top of the concurrency model and answer questions about audience **behaviour**
rather than audience **size**. All are `SharedReplacingMergeTree(version)`: a row is recomputed as
more of its aftermath arrives, and the newer version supersedes rather than accumulates. Query
with `argMax(col, version)` grouped by the ordering key, or with `FINAL`.

### `session_insight_facts`, one row per session, with its outcome

`ORDER BY (toDate(session_start), country, platform, content_id, session_start, video_session_id)`.
**119,495 rows**, 6.56 MiB.

The per-session fact table. Answers "what happened to this viewer" rather than "how many were
there".

| Group | Columns | What it tells you |
|---|---|---|
| Identity | `video_session_id`, `user_id`, `content_id`, `title`, `category`, `video_type` | Who watched what. Title is denormalised in, so no join is needed |
| Dimensions | `platform`, `country`, `app_version` | Slicing |
| Timeline | `session_start`, `first_play_at`, `session_end_at`, `first_active_at`, `last_active_at` | Startup delay is `first_play_at - session_start` |
| Engagement | `active_seconds`, `active_interval_count`, `heartbeat_count` | Foreground-only watch time, and how fragmented it was |
| Behaviour | `background_count`, `foreground_return_count`, `pause_count`, `resume_count`, `video_error_count` | Why a session was interrupted, and whether they came back |
| Retention | `reached_first_heartbeat`, `active_after_1m`, `active_after_5m`, `active_after_10m`, `active_after_15m` | `UInt8` flags, `1` if still active at that mark |
| Outcome | `ended_normally`, `abandoned`, `timed_out` | Mutually exclusive. `timed_out` means the heartbeats simply stopped, with no close event |

### `audience_minute_snapshot`, the minute, fully described

`ORDER BY (minute, content_id, platform, country, video_type, app_version)`. **123,171 rows**,
707.18 KiB.

Concurrency **plus the flow that produced it**, per minute per content.

| Column | Meaning |
|---|---|
| `concurrent_sessions`, `concurrent_users` | The level. Reconciles with the delta tables |
| `session_starts`, `first_plays`, `session_ends` | Arrivals and departures behind that level |
| `foreground_entries`, `background_entries` | Attention coming and going |
| `video_errors` | Failures in that minute |
| `title`, `category` | Denormalised for readability |
| `version`, `updated_at` | Replacing-engine bookkeeping |

Use it to **explain** a curve. Do not serve a curve from it; that is what
`concurrency_deltas` is for.

### `playback_health_minute`, is it working, per minute

`ORDER BY (minute, content_id, platform, country, app_version, video_type)`. **123,183 rows**,
296.82 KiB.

| Column | Meaning |
|---|---|
| `active_sessions` | The denominator |
| `video_error_sessions`, `heartbeat_timeout_sessions`, `abandoned_sessions` | Numerators |
| `video_error_rate`, `heartbeat_timeout_rate`, `abandonment_rate` | `Float32`, already divided |

**The reason this table exists.** A concurrency drop with a rising `heartbeat_timeout_rate` is an
infrastructure problem. The same drop with flat rates is the content ending. The curve alone
cannot tell those apart.

### `content_entry_cohorts`, did the audience it gained actually stay

`ORDER BY (video_type, country, platform, app_version, content_id, cohort_minute)`.
**16,967 rows**, 274.89 KiB.

Sessions grouped by the minute they entered a title, then followed forward.

| Column | Meaning |
|---|---|
| `cohort_minute` | The minute this group of sessions arrived |
| `entered_sessions` | Cohort size |
| `active_after_1m`, `active_after_5m`, `active_after_10m`, `active_after_15m` | How many were still active |
| `retention_1m`, `retention_5m`, `retention_10m`, `retention_15m` | The same as `Float32` rates |
| `avg_active_seconds`, `median_active_seconds`, `p90_active_seconds` | Watch-time distribution for the cohort |

This is what separates an audience from a spike of people who left.

### `concurrency_spike_events`, was that spike real

`ORDER BY (content_id, window_start)`. Currently **empty**; populated by
`sql/insights/spike/refresh_spike_events.sql`.

One row per detected ramp, carrying the verdict.

| Group | Columns | What it tells you |
|---|---|---|
| The ramp | `window_start`, `peak_minute`, `baseline_concurrency`, `peak_concurrency`, `absolute_growth`, `growth_percent`, `minutes_to_peak` | How big and how fast |
| Whether it held | `minutes_above_80pct_peak`, `concurrency_after_5m`, `concurrency_after_10m`, `concurrency_after_15m`, `retention_5m_percent`, `retention_10m_percent`, `retention_15m_percent` | The shape after the peak |
| Why it did not | `entered_sessions`, `background_rate_after_peak`, `error_rate_after_peak`, `timeout_rate_after_peak` | Left voluntarily, or were pushed |
| The verdict | `spike_type` (`healthy_sustained`, `short_lived`, `inconclusive`), `confidence` | One row to read instead of a join across two grains |

### `late_event_audit`, what arrived after we had already answered

`SharedMergeTree`, `ORDER BY (lateness_class, event_date, video_session_id, event_timestamp)`.
Currently **empty**; filled by `late_event_audit_mv` as late data arrives.

| Column | Meaning |
|---|---|
| `event_timestamp` | When it happened |
| `arrival_timestamp` | When we heard about it |
| `lateness_seconds` | `Int64`, the gap between them |
| `lateness_class` | `on_time`, `late_acceptable`, `late_after_finalization`, `invalid_future_event` |
| `event_type`, `event`, `video_session_id`, `event_date` | Which event |

`late_after_finalization` is the class that matters: an event that arrived after its minute had
already been served. That is precisely what the retraction mechanism in `session_minute_runs`
exists to absorb, so this table is the measure of how often it is needed.

---

## Answering common questions

| Question | Read | Watch out for |
|---|---|---|
| Peak concurrent sessions in a range | `concurrency_deltas` | Running sum, seeded from before the window. Compute peak **after** filters: a platform slice and a platform-plus-country slice peak at different minutes, so a stored peak is only right for the slice it was stored for |
| Peak concurrent users | `user_concurrency_deltas` | Always at or below the session figure |
| Average concurrency | `concurrency_deltas`, densified to every minute | The denominator is a definition. All minutes in range, or only minutes with an audience. Averaging the sparse delta rows instead of the dense minute series gives a number roughly 2.8x too high |
| The exact second of a peak | `concurrency_boundary_deltas` | Bigger table, use only when the instant matters |
| What foreground-only is worth | `concurrency_deltas` against `concurrency_deltas_naive` | The naive table is wrong on purpose |
| Which sessions are still open | `raw_events` | No `VideoSessionEnd`, last event within the 90s tolerance. Full scan, so treat it as a drill-down, not a refresh-path query |
| Title for a content id | `content` | `ANY LEFT JOIN`, never a plain join |
| Why concurrency dropped | `playback_health_minute`, then `audience_minute_snapshot` | Rates first, then arrivals and departures |
| Whether a spike was a real audience | `concurrency_spike_events`, else `content_entry_cohorts` | |
| What a session actually did | `session_insight_facts` | One row per session, no joins needed |
| Whether late data changed an answer | `late_event_audit` | Filter `lateness_class = 'late_after_finalization'` |
| How far behind ingest is | `raw_events` | `max(ingested_at) - max(event_timestamp)` |

Every shipped query lives in `sql/queries/serving/`. Each one carries a read budget in its
`SETTINGS` clause, so a query that starts scanning more than its design allows fails loudly with
`TOO_MANY_ROWS` instead of quietly getting slower.

---

## Invariants that must always hold

| Invariant | Required | What a breach means |
|---|---:|---|
| `sum(delta)` on `concurrency_deltas` | 0 | A session was counted up and never down |
| `sum(delta)` on `user_concurrency_deltas` | 0 | The same, at user level |
| `max(sum(sign))` per run key | 1 | One session counted twice at one instant |
| `count` of negative `sum(sign)` groups | 0 | A retraction with no matching assertion |
| Minimum served concurrency | 0 | Concurrency went negative, so the deltas do not balance **in order**. A curve can sum to zero overall and still go negative in the middle |
| Runs or intervals where end precedes start | 0 | Time ran backwards |

`./scripts/ground_state.sh` reports all of these.

---

## Re-reading these facts yourself

```bash
# Every table, engine, ordering key and size, in both databases
./scripts/ch.sh --format PrettyCompact --query "
  SELECT database, name, engine, sorting_key, formatReadableSize(total_bytes) AS size
  FROM system.tables
  WHERE database IN ('phoenix','phoenix_next') AND NOT startsWith(name,'.')
  ORDER BY database, name"

# Every column of every table
./scripts/ch.sh --format TSV --query "
  SELECT table, name, type FROM system.columns
  WHERE database = 'phoenix' ORDER BY table, position"

# The counts that are actually stable
./scripts/ch.sh --format TSV --query "
  SELECT 'runs.asserted' k, toString(sum(sign)) v FROM session_minute_runs
  UNION ALL SELECT 'user_runs.asserted', toString(sum(sign)) FROM user_minute_runs
  UNION ALL SELECT 'deltas.minutes', toString(uniqExact(minute)) FROM concurrency_deltas
  UNION ALL SELECT 'deltas.closure', toString(sum(delta)) FROM concurrency_deltas"
```

`scripts/ch.sh` is the only entrypoint. It pins `session_timezone=UTC` on every request, so
local time never leaks into a result, and it injects the `frozen_before` isolation parameter that
the serving queries take. Credentials come from a gitignored `.env`; copy `.env.example` and fill
it from the ClickHouse Cloud console.

`./scripts/inventory.sh` writes a timestamped version of this inventory to `evidence/`.
