# Table Contract — `sonyliv` on ClickHouse Cloud

**Audience:** whoever is wiring up ClickStack. This is the read contract for the
`sonyliv` database: which table answers which metric, the exact query shape, the
traps that produce a plausible wrong number, and the reference values to check
yourself against.

**Verified against the live service on 2026-08-02** — `sonyliv` (aws ap-south-1,
ClickHouse 26.2, 2 replicas). Every row count, every metric value, and every query
in §5 was run against the service on that date, not inferred.

Three figures are **carried forward from earlier measurement**, not re-run on
2026-08-02, and are marked where they appear: the `events_dedup` 7× read cost, the
6,140-events IST date-shift count, and the 2026-08-01 doubling incident. They come
from `CLAUDE.md` and `solution/README.md`.

> There is also a `sonyliv_prod` database on the same service. **It is not ours.**
> Its `events_clean` has a different row count, so it cannot agree with anything
> here. Never read it for a reference number.

---

## 0. The one-paragraph version

A session is *active* when it is started, not terminated, **foregrounded AND
playing**, and has emitted an eligible signal in the last 120 s. Each active
stretch is stored once as a half-open interval `[start_time, end_time)` in
`active_intervals`. Every interval is then published as `+1` at its start and
`-1` at its end into `concurrency_deltas`. **Concurrency at any instant is the
running sum of those deltas.** Everything else in the schema is either the
ingest path feeding this, or a checkpoint layer that keeps the running sum from
having to start at the beginning of time.

---

## 1. Which table answers which metric

| Metric | Read this | Do **not** read |
|---|---|---|
| Peak concurrency in a window | `concurrency_deltas` (+ `concurrency_day_anchor`, `concurrency_bucket_net` for windowed reads) | `events_clean`, `active_intervals` |
| Time-weighted average concurrency | `concurrency_deltas` | `events_clean` |
| Concurrency sliced by platform / country / content / video_type | `concurrency_deltas`, pick `rollup_mask` | anything else |
| Live viewers right now | `session_live_state` | `concurrency_deltas` — it is a historical curve, it cannot answer "now" |
| Total active intervals / sessions | `active_intervals_current` | `active_intervals` (raw, holds every revision) |
| Content title / category / video_type | `content_dict` via `dictGetOrDefault` | `content_dim` on a hot path |
| Ingest integrity, duplicate & conflict rates | `events_raw` | `events_clean` — a conflict check against it is a tautology |

---

## 2. Tiering — what is load-bearing

Audited across the whole repo (every producer and consumer traced to `file:line`),
then each proposed removal challenged. **Result: 17 critical, 6 supporting, 0
removable.** No object in this database is orphaned.

### Tier 1 — critical, on the read path of a served metric

| Object | Engine | Rows | Role |
|---|---|---:|---|
| `events_raw` | SharedMergeTree | 905,558 | Append-only landing. Sole source of everything. The **only** place a payload conflict is still visible. |
| `events_clean` | SharedReplacingMergeTree | 901,348 | Normalized, semantically deduplicated events. Input to the interval builder. |
| `active_intervals` | SharedMergeTree | 63,894 | Active intervals, all revisions. **Never read directly.** |
| `active_intervals_current` | View | 31,947 / variant | Revision-resolved intervals. This is the interval-layer source of truth. |
| `concurrency_deltas` | SharedSummingMergeTree | 1,274,172 | ±1 boundaries at ms resolution, per rollup mask. The peak and the average both come from here. |
| `concurrency_bucket_net` | SharedSummingMergeTree | 243,116 | Per-minute net, so a windowed read does not prefix-sum from t=0. |
| `concurrency_day_anchor` | SharedReplacingMergeTree | 430,584 | Level at each UTC midnight. Base term of a windowed peak. |
| `concurrency_deltas_to_bucket_mv` | MaterializedView | — | Only writer of `concurrency_bucket_net`. |
| `content_dim` / `content_current` / `content_dict` | RMT / View / Dictionary | 33,464 | Catalogue. `content_dict` is the enrichment path. |
| `concurrency_minute_versions` | SharedMergeTree | 272,070 | **Flat minute tier — start here for dashboards.** One row per (minute, mask, dims), `minute_peak` and `active_entity_ms` precomputed. Deployed 2026-08-02. |
| `concurrency_minute_mask13` | View | — | Mask 13 (platform+content+video_type) off the above, at zero storage cost. |
| `session_live_state` | SharedAggregatingMergeTree | 10,848 | The deployed answer to "who is live now". |
| `events_raw_to_clean_mv`, `events_raw_to_dirty_mv` | MaterializedView | — | Sole writers of `events_clean` and `dirty_sessions`. |

### Tier 2 — supporting: no metric reads them, correctness depends on them

| Object | Rows | Why it stays |
|---|---:|---|
| `dirty_sessions` | 10,943 | Append-only work queue driving incremental recompute. |
| `ingest_batches` | 19 | Load ledger / lineage. |
| `ingest_rejects` | 0 | Empty **is** the passing state. Deleting it deletes the alarm. |
| `pipeline_watermark` | 1 | Only record of which `state_revision` produced the deployed rows. |
| `events_dedup` | — | View for count-based checks at generation boundaries. Costs 7× — never per query. |

### Tier 3 — in the repo, **not deployed** on the service

`session_live_now` + `events_clean_to_live_mv` (`pipeline/sql/030`) — the designed
live path. `policy.yaml` names 030, not 020/022, as the authoritative live
implementation, so today's live answer comes from `session_live_state` while the
designed one sits unapplied.

> `pipeline/sql/040` **was deployed on 2026-08-02** and is now Tier 1 — see
> `concurrency_minute_versions` above and the flat read in §5.7. Two syntax
> defects had to be fixed first; 030 still carries one of them (a `COMMENT` split
> across adjacent string literals, which ClickHouse parses as an error, not a
> concatenation). That is fixed in the file now but 030 has still never run.

---

## 3. Mandatory query parameters

Every read of the serving layer must pin all three. Omitting any of them does not
error — it silently sums across incompatible row sets.

| Parameter | Value today | What happens if you forget |
|---|---|---|
| `policy_version` | `'sonyliv-active-v1'` | Sums across semantic definitions. |
| `clip_variant` | `'unclipped'` (see below) | **Exactly doubles every number.** |
| `rollup_mask` | see §4 | Sums a global row with per-platform rows. |

### On `clip_variant`

Two variants are always built. `unclipped` runs an open session's lease to
`last_eligible_signal + 120s`; `clipped` truncates at the observation horizon.
Which is authoritative is a judgement call against a sealed answer key, so the
pipeline refuses to choose silently.

**Measured on this extract: the two are byte-identical — 0 rows differ.** Every
session here is closed, so no lease outlives the horizon and there is nothing to
clip. They will diverge on a live stream or a day with open sessions. Pick
`unclipped` and pin it; do not assume the two stay interchangeable.

---

## 4. Rollup masks

Bit values: `platform = 1`, `country = 2`, `content_id = 4`, `video_type = 8`.
A dimension not in the mask is stored as `''` / `0`, not as a wildcard.

Materialized: `0, 1, 2, 3, 4, 5, 8, 9, 12, 15`.

| Mask | Dimensions | Rows (per variant) | Note |
|---:|---|---:|---|
| 0 | global | 63,401 | Use for total peak/average. |
| 1 | platform | 63,711 | |
| 2 | country | 63,401 | **≡ mask 0** on this extract |
| 3 | platform + country | 63,711 | **≡ mask 1** on this extract |
| 4 | content_id | 63,881 | |
| 5 | platform + content_id | 63,888 | |
| 8 | video_type | 63,557 | |
| 9 | platform + video_type | 63,767 | |
| 12 | content_id + video_type | 63,881 | **≡ mask 4** — structurally |
| 15 | all four | 63,888 | **≡ mask 5** on this extract |

Measured: 0 disagreement across all boundary instants for each equivalence above.

Two different reasons, and the difference matters:

- **Mask 12 ≡ mask 4 is structural.** `video_type` is functionally determined by
  `content_id` (33,464 catalogue rows, zero with more than one video_type). This
  holds on any data.
- **Masks 2, 3, 15 collapse only because `country` has exactly one value in this
  extract.** That is a property of the sample, not of the schema. An unseen day
  with a second country breaks it immediately.

**Peaks do not sum, so an unmaterialized mask's peak cannot be re-derived.**
Masks 6, 7, 10, 11, 13, 14 are unavailable. Measured proof that this is not
pedantic: platform peaks sum to 2,388 while the global peak is 2,305 — because
each platform peaks at a different instant.

---

## 5. Query recipes

### 5.1 Peak — whole extract, simplest correct form

```sql
SELECT max(running) AS peak_concurrency, argMax(ts, running) AS peak_instant
FROM (
    SELECT ts, sum(net) OVER (ORDER BY ts ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running
    FROM (
        SELECT boundary_ts AS ts, toInt64(sum(opens)) - toInt64(sum(closes)) AS net
        FROM sonyliv.concurrency_deltas
        WHERE policy_version = 'sonyliv-active-v1'
          AND clip_variant   = 'unclipped'
          AND rollup_mask    = 0
        GROUP BY ts
    )
);
-- 2305 @ 2026-07-26 10:55:28.614
```

`GROUP BY boundary_ts` before the running sum is **load-bearing**, not tidiness.
It is what implements stop-wins at the same millisecond, and it is the difference
between exactly 2,305 and approximately right.

### 5.2 Peak — bounded window (the one that scales)

Reads `O(checkpoints before W0) + O(deltas inside W0..W1)` instead of prefix-summing
from t=0. This is the query shape the whole design exists to make cheap.

```sql
WITH toDateTime64('2026-07-26 10:00:00.000', 3, 'UTC') AS w0,
     toDateTime64('2026-07-26 11:00:00.000', 3, 'UTC') AS w1,
base AS (
    SELECT
        ifNull((SELECT level FROM sonyliv.concurrency_day_anchor FINAL
                WHERE policy_version='sonyliv-active-v1' AND clip_variant='unclipped'
                  AND rollup_mask=0 AND platform='' AND country='' AND content_id=0 AND video_type=''
                  AND day = toDate(w0)), 0)
      + ifNull((SELECT toInt64(sum(opens)) - toInt64(sum(closes))
                FROM sonyliv.concurrency_bucket_net
                WHERE policy_version='sonyliv-active-v1' AND clip_variant='unclipped'
                  AND rollup_mask=0 AND platform='' AND country='' AND content_id=0 AND video_type=''
                  AND bucket >= toStartOfDay(w0) AND bucket < w0), 0) AS lvl
),
inner_prefix AS (
    SELECT boundary_ts,
           sum(toInt64(sum(opens)) - toInt64(sum(closes)))
               OVER (ORDER BY boundary_ts ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS pfx
    FROM sonyliv.concurrency_deltas
    WHERE policy_version='sonyliv-active-v1' AND clip_variant='unclipped'
      AND rollup_mask=0 AND platform='' AND country='' AND content_id=0 AND video_type=''
      AND boundary_ts >= w0 AND boundary_ts < w1
    GROUP BY boundary_ts
)
SELECT (SELECT lvl FROM base) AS level_at_window_start,
       greatest((SELECT lvl FROM base),
                (SELECT lvl FROM base) + (SELECT max(pfx) FROM inner_prefix)) AS peak,
       (SELECT argMax(boundary_ts, pfx) FROM inner_prefix) AS peak_instant;
-- level_at_window_start = 46, peak = 2305 @ 2026-07-26 10:55:28.614
```

`FINAL` on `concurrency_day_anchor` is the **one** place `FINAL` is sanctioned.
It is a ReplacingMergeTree of one row per (dims, day) and the read is a point
lookup. Do not copy `FINAL` anywhere else.

### 5.3 Time-weighted average over a window

Integrate the step function: level × the time it held.

```sql
WITH toDateTime64('2026-07-26 10:00:00.000',3,'UTC') AS w0,
     toDateTime64('2026-07-26 11:00:00.000',3,'UTC') AS w1,
pts AS (
    SELECT boundary_ts AS ts, toInt64(sum(opens)) - toInt64(sum(closes)) AS net
    FROM sonyliv.concurrency_deltas
    WHERE policy_version='sonyliv-active-v1' AND clip_variant='unclipped' AND rollup_mask=0
    GROUP BY ts
),
run AS (SELECT ts, sum(net) OVER (ORDER BY ts ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS lvl FROM pts),
seg AS (
    SELECT ts, lvl,
           leadInFrame(ts, 1, toDateTime64('2100-01-01 00:00:00.000',3,'UTC'))
               OVER (ORDER BY ts ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) AS nxt
    FROM run
)
SELECT sum(lvl * dateDiff('millisecond', greatest(ts,w0), least(nxt,w1))) / 3600000.0 AS avg_concurrency
FROM seg WHERE ts < w1 AND nxt > w0;
-- 855.5781994444444
```

### 5.4 Per-minute series (what a dashboard actually wants)

**Do not grope for a shortcut here.** The obvious form — `GROUP BY
toStartOfMinute(ts)` over the boundary rows — is wrong in three ways at once, and
all three are silent. It is written out below the correct query so nobody
re-derives it.

```sql
WITH
    {from:DateTime64(3,'UTC')} AS w0,
    {to:DateTime64(3,'UTC')}   AS w1,
pts AS (
    SELECT boundary_ts AS ts, toInt64(sum(opens)) - toInt64(sum(closes)) AS net
    FROM sonyliv.concurrency_deltas
    WHERE policy_version='sonyliv-active-v1' AND clip_variant='unclipped' AND rollup_mask=0
      AND boundary_ts < w1          -- upper bound only: the running sum must start at t=0
    GROUP BY ts
),
run AS (
    SELECT ts, sum(net) OVER (ORDER BY ts ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS lvl
    FROM pts
),
seg AS (
    SELECT ts, lvl,
           leadInFrame(ts, 1, w1) OVER (ORDER BY ts ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) AS nxt
    FROM run
),
spine AS (
    SELECT w0 + toIntervalMinute(number) AS minute
    FROM numbers(toUInt64(dateDiff('minute', w0, w1)))
)
SELECT
    m.minute                                                     AS minute,
    max(s.lvl)                                                   AS minute_peak,
    sum(s.lvl * dateDiff('millisecond',
              greatest(s.ts, m.minute),
              least(s.nxt, m.minute + toIntervalMinute(1)))) / 60000.0 AS minute_avg
FROM spine AS m
CROSS JOIN seg AS s
WHERE s.ts < m.minute + toIntervalMinute(1) AND s.nxt > m.minute
GROUP BY m.minute
ORDER BY m.minute;
```

Verified on the service: for 10:00–11:00 on 2026-07-26 it returns all 60 minutes,
peaks at **2,305** in the 10:55 minute, and its per-minute values sum back to
**855.578199** — the same number §5.3 produces independently. That agreement is
the check worth running after any edit to this query.

<details>
<summary>Why the obvious shortcut is wrong (measured)</summary>

```sql
-- WRONG. Do not use.
SELECT toStartOfMinute(ts) AS minute, max(lvl) AS minute_peak,
       sum(lvl * dateDiff('millisecond', ts, nxt)) / 60000.0 AS minute_avg
FROM seg WHERE ts >= w0 AND ts < w1
GROUP BY minute ORDER BY minute;
```

1. **No clipping at minute boundaries.** A segment running 10:55:30 → 10:56:20
   has all 50 s charged to 10:55.
2. **Minutes containing no boundary produce no row at all.** A flat, busy minute
   silently disappears from the series instead of reporting its level.
3. **The level carried into `w0` is dropped**, because that segment's `ts` is
   before the range and the `WHERE` excludes it.

In the hot hour the boundaries are dense enough that the error hides — worst
minute off by 1.58 out of ~2,280, about 0.07%. On a quiet stretch it is not
subtle. Measured, 2026-07-25 16:50–17:00:

| Minute | Shortcut | Correct | Error |
|---|---:|---:|---:|
| 16:50 | 25.99 | 8.31 | **+213%** |
| 16:51 | *(no row)* | 10.00 | **−100%** |
| 16:59 | 14.59 | 9.32 | +57% |

A dashboard built on the shortcut looks plausible during the match and is
nonsense everywhere else.

</details>

### 5.5 Live viewers right now

```sql
SELECT countIf(terminated = 0 AND active = 1 AND lease > now64(3)) AS live_now,
       countIf(terminated = 1)                                     AS terminated_sessions,
       count()                                                     AS sessions
FROM (
    SELECT session_key,
           argMaxMerge(lease_expiry)  AS lease,
           argMaxMerge(is_active_now) AS active,
           argMaxMerge(is_terminated) AS terminated
    FROM sonyliv.session_live_state
    WHERE policy_version = 'sonyliv-active-v1'
    GROUP BY session_key
);
-- On this frozen extract: live_now = 0, terminated = 10848, sessions = 10848.
-- 0 is CORRECT here, not a bug: every lease in the extract expired in July 2026.
```

`session_live_state` is an AggregatingMergeTree. Read with `GROUP BY` +
`-Merge`. **Never `FINAL`** — it would be both wrong-shaped and expensive.

### 5.6 Slice by dimension

```sql
SELECT platform, max(running) AS peak, argMax(ts, running) AS peak_instant
FROM (
    SELECT platform, ts,
           sum(net) OVER (PARTITION BY platform ORDER BY ts
                          ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running
    FROM (
        SELECT platform, boundary_ts AS ts, toInt64(sum(opens)) - toInt64(sum(closes)) AS net
        FROM sonyliv.concurrency_deltas
        WHERE policy_version='sonyliv-active-v1' AND clip_variant='unclipped' AND rollup_mask = 1
        GROUP BY platform, ts
    )
) GROUP BY platform ORDER BY peak DESC;
```

Verified output:

| platform | peak | peak instant (UTC) |
|---|---:|---|
| ANDROID_PHONE | 1461 | 10:55:27.348 |
| IPHONE | 262 | 10:55:24.325 |
| SONY_ANDROID_TV | 248 | 10:53:24.782 |
| JIO_ANDROID_TV | 187 | 10:57:16.347 |
| Mweb | 53 | 11:03:19.154 |
| SAMSUNG_HTML_TV | 48 | 10:48:33.673 |
| ANDROID_TAB | 40 | 10:56:21.906 |
| XIAOMI_ANDROID_TV | 35 | 10:49:39.642 |
| FIRE_TV | 32 | 10:59:40.595 |
| LG_HTML_TV | 22 | 10:54:39.265 |

Note the instants. **Slice peaks do not coincide with the global peak and do not
sum to it** (2,388 vs 2,305). Any dashboard that adds slice peaks is wrong.

### 5.7 The flat read — use this one for ClickStack

Everything above sweeps boundaries. Since 040 was deployed, peak and average are
one `max()` and one `sum()` over a precomputed minute table. No window function,
no cumsum, nothing to get subtly wrong.

```sql
SELECT max(minute_peak)                                          AS peak_concurrency,
       sum(active_entity_ms) / dateDiff('millisecond',
           {from:DateTime64(3,'UTC')}, {to:DateTime64(3,'UTC')}) AS avg_concurrency
FROM sonyliv.concurrency_minute_versions
WHERE generation = 1
  AND policy_version = 'sonyliv-active-v1'
  AND entity      = 'session'
  AND rollup_mask = 0
  AND minute_start >= {from:DateTime64(3,'UTC')}
  AND minute_start <  {to:DateTime64(3,'UTC')};
-- 10:00-11:00 on 2026-07-26 -> 2305 and 855.5781994444444, one granule, 5.7 ms
```

Both numbers match §5.2 and §5.3 exactly. Prefer this for every panel; keep the
boundary sweeps for auditing it.

**Pin `generation`.** The sort key leads with it and the table is a plain
MergeTree, not Replacing — a second build writes a *new* generation alongside the
old one. A query without `generation =` sums across builds. Today only
generation 1 exists.

**Re-running the producer at the same generation doubles the average, not the
peak.** Duplicate rows leave `max(minute_peak)` at 2,305 — looking perfectly
healthy — while `sum(active_entity_ms)` doubles. It is the inverse of the
SummingMergeTree failure in trap 2, and just as quiet. C4 in
`041_minute_verify.sql` is what catches it. Bump the generation instead.

**One known, benign disagreement.** `041`'s C3 compares `ending_concurrency`
against a cumsum over `concurrency_deltas` and comments "expect 0". On the
deployed table it returns **9** — all nine masks at the single minute
`2026-07-26 10:39`, each off by exactly 1. Cause: one interval ends precisely on
a minute boundary. `ending_concurrency` measures the level *at* `minute_end` and
correctly excludes it under `[start, end)`; the cumsum measures the level *just
before* `minute_end` and still counts it. Different instants, both right. The
producer is correct and C3's expectation is what is mis-specified. Peak and
average are unaffected — C4 is exact to the millisecond.

---

## 6. Traps

Each of these produces a plausible wrong number rather than an error.

1. **Forgetting `clip_variant` doubles everything.** It is the single most likely
   mistake, and the result looks entirely reasonable.
2. **Re-running a populate into a SummingMergeTree adds to it.** It does not
   replace. `insert_deduplication_token` does **not** make a large `INSERT SELECT`
   idempotent — a 524k-row insert splits across blocks and the token is suffixed
   per block. This actually happened on 2026-08-01 and produced a peak of 4,610
   (exactly 2 × 2,305 — *historical incident, recorded in `CLAUDE.md`*).
   **A doubled curve passes every balance invariant:**
   `sum(net) = 0`, `min(running) = 0`, `opens = closes` all still hold. Guard on
   the target being empty; never rely on dedup.
3. **`FINAL` is allowed on `concurrency_day_anchor` only.** Nowhere else.
4. **Never read `active_intervals` directly** — it holds every revision. Use
   `active_intervals_current`.
5. **`events_dedup` costs ~7×** (0.59 s / 24.4 MB vs 0.086 s / 15.3 MB reading
   `events_clean` — *carried forward from `CLAUDE.md`, not re-run 2026-08-02*).
   Column pruning does not reach through its `GROUP BY`. Use it only for
   count-based checks at generation boundaries, never per query.
6. **A conflict check against `events_clean` is a tautology** — the losing copy is
   already gone once merges run. Conflict checks go against `events_raw`.
7. **Dictionaries load per replica, and an empty one still reports `LOADED`.**
   A query routed to a cold replica gets the default from every
   `dictGetOrDefault` — no error, no warning. Always check across replicas:

   ```sql
   SELECT hostName(), toString(status), element_count
   FROM clusterAllReplicas(default, system.dictionaries)
   WHERE database = 'sonyliv' AND name = 'content_dict';
   ```

   Any dashboard panel doing `dictGetOrDefault` should assert enrichment
   resolved — a dimension that is 100% fallback is a failure, not a data
   characteristic.
8. **Time is UTC end to end.** Render `Asia/Kolkata` only in the final projection
   (`toTimeZone(minute_start, 'Asia/Kolkata')`); filters and range bounds stay UTC.
   Rendering in IST moves 6,140 events across 34 sessions onto a different
   calendar date (*carried forward from `solution/README.md`*).

---

## 7. Self-check values

Run these before trusting a dashboard. All verified on the service 2026-08-02.

| Check | Expected |
|---|---:|
| `events_raw` rows | 905,558 |
| `events_clean` rows | 901,348 |
| `ingest_rejects` rows | 0 |
| Unjoinable content ids | 0 |
| Conflicting keys in `events_raw` | 1 (on `subtitle_language` only) |
| `content_dim` rows / dict elements per replica | 33,464 |
| Active intervals (per clip variant) | 31,947 |
| Sessions with ≥1 active interval | 10,848 |
| Sessions in `events_clean` | 10,866 |
| Peak concurrency | **2,305** |
| Peak instant | **2026-07-26 10:55:28.614** |
| Hot-hour time-weighted average (10:00–11:00) | **855.578199** |
| Distinct users at peak | 2,248 |
| `sum(net)` over all boundaries | 0 |
| `min(running)` over all boundaries | 0 |
| Naive session-boundary peak (the wrong answer) | 3,549 |

**The conservation check is the only one worth anything on an unseen day**, because
2,305 will not be known then:

```sql
SELECT d.clip_variant, d.delta_opens, s.source_intervals,
       round(d.delta_opens / s.source_intervals, 6) AS ratio_must_be_1
FROM (SELECT clip_variant, sum(opens) AS delta_opens FROM sonyliv.concurrency_deltas
      WHERE policy_version='sonyliv-active-v1' AND rollup_mask=0 GROUP BY clip_variant) AS d
INNER JOIN (SELECT clip_variant, count() AS source_intervals FROM sonyliv.active_intervals_current
      WHERE policy_version='sonyliv-active-v1' GROUP BY clip_variant) AS s USING (clip_variant);
```

A ratio of 2.0 means the load ran twice. A ratio of 0.5 means half is missing.
It compares the serving layer against a source **outside** that layer, which is
why it works without already knowing the answer.

### The 18-session gap is expected

`events_clean` has 10,866 sessions; only 10,848 have an active interval. Verified
individually — all 18 are correct under the policy:

- **15** emit play signals only *after* their terminal `VideoSessionEnd`, which
  the policy ignores.
- **3** issue `VideoPlay` while backgrounded and only receive `AppForegrounded`
  after a `pause`. Since `AppForegrounded` does not set playing, foreground AND
  playing never hold simultaneously.

---

## 8. Notes for ClickStack specifically

- **Read `concurrency_deltas` for history, `session_live_state` for now.** They
  answer different questions and neither can substitute for the other. A single
  running-sum-from-epoch appears to answer both and scales for neither: a prefix
  sum reads from t=0 by construction, and no sort key, skip index or projection
  prunes it.
- **Build panels on `concurrency_minute_versions` (§5.7).** Deployed 2026-08-02:
  272,070 rows, one flat row per (minute, mask, dims) with `minute_peak` and
  `active_entity_ms` already computed. `max()` + `sum()`, no window function, no
  day-anchored cumsum — 5.7 ms and a single granule for an hour-wide query. This
  is the surface a text-to-SQL layer can actually be trusted with. Always pin
  `generation`.
- **Sort keys, for predicate ordering.** All four `concurrency_*` tables lead with
  `(policy_version, clip_variant, rollup_mask, platform, country, content_id,
  video_type, <time>)`. Filter left-to-right; a predicate on `boundary_ts` alone
  prunes nothing.
- **Instrument the conservation ratio as a panel, not a one-off.** It is the only
  reference-free correctness signal in the system, and the failure it catches —
  a silently doubled curve — is invisible to every other check.
- **Watch dictionary `element_count` per replica**, not just status. A ten-minute
  window of silent `__unknown__` enrichment is the documented failure mode, and
  it self-heals, so it will not be there when you go looking after the fact.
