# SonyLIV — ClickHouse Architecture Design
## Foreground-Only Concurrency at Streaming Scale

*Reference: `PROBLEM_STATEMENT.md`, `dataset_details.md`, `jira/EPIC.md`, `jira/stories/*`*

---

## 0. Coverage check against the problem statement

### 0.1 The five "possible solution directions" — all explicitly explored

| Direction (from problem statement) | Explored? | Where / what we chose | Why |
|---|---|---|---|
| **Interval-to-delta model** (+1 at start, −1 at end) | ✅ **Adopted (core)** | §4 step 4, `delta_minute` table | additive & idempotent → late events + open-session growth handled by appending, never rebuilding |
| **Dedicated serving table** | ✅ **Adopted (core)** | §5 `serving_minute` (delta sums) | dashboards read only pre-aggregated minute rows; ~60 rows per hour → ms latency, no raw scan |
| **Incremental compaction** | ✅ **Adopted** | §4 `open_sessions` state table; finalize on close / watermark | active tails extended in place; finalized sessions compacted to `delta_minute` once the watermark passes |
| **Hybrid tiering** | ✅ **Adopted** | §4: recent detail tier (`open_sessions`, per-event intervals) vs historical tier (`delta_minute`, compacted deltas) | recent data updates cheaply; history stays query-fast and small |
| **Background exclusion logic** | ✅ **Adopted (all 4 signals)** | §3: heartbeat gaps (90s timeout) + `AppBackgrounded`/`AppForegrounded` cuts + playback-state markers (`pause`/`resume`) + explicit `is_active` flag alternative | markers are *not guaranteed* per the data dictionary, so heartbeat cadence is primary, markers corroborate |

### 0.2 "What great looks like" → design intent

| Great criterion | Design intent |
|---|---|
| **Correct** | Active intervals are the only source of truth; heartbeat-gap timeout (90s, > measured ~40s cadence) closes intervals; background windows contribute 0. Both session-aware and session-independent derivations must agree on closed sessions (US-09 parity check). |
| **Fast** | Queries read `serving_minute` only: cumulative `sum(delta) OVER` over the requested range (1 day = 1440 rows) → dashboard-grade ms, never `raw_events`. |
| **Update-friendly** | `delta_minute` is a SummingMergeTree: appending a new delta for minute 10:06 **never touches** minute 10:04. No full rebuild, no re-scan of the event stream. |
| **Explained** | §7 documents representation, table layout, ordering keys, and aggregation trade-offs — the problem is won on this reasoning. |

### 0.3 Evaluation criteria → design response

| Criterion | Response |
|---|---|
| **Correctness** | Foreground-only by construction: intervals exclude gap/background time before any counting (see §0.1). Ground-truth validation on benchmark queries via US-09 parity + sanity checks (avg ≤ peak; if avg > peak, backgrounded time leaked in — US-03). |
| **Query performance** | Judges look at *what queries read*: every benchmark query hits the serving layer (`EXPLAIN` shows no raw scan). Latency via `system.query_log`. |
| **Update handling** | Open sessions + late arrivals absorb **incrementally** by appending deltas; evidence = a re-query after late insert returns updated value without full rebuild. |
| **Design quality** | §7 trade-off reasoning; every rejection (per-minute explosion, interval arrays, absolute-concurrency MV) is documented with its failure mode. |
| **Unseen day** | Same pipeline, no hand-tuning; evidence bundle = answers CSV + `system.query_log` + `EXPLAIN` + per-query latency (US-16). |

---

## 1. Architectural principles

The design is built on four non-negotiable rules:

| Principle | ClickHouse implementation | Use case |
|---|---|---|
| **Correctness = foreground-only** | Active intervals are the only source of truth; heartbeat-gap timeout (90s) + `AppBackgrounded`/`AppForegrounded` cuts define them | US-01, US-06, US-07 |
| **No raw rescans on query** | Dashboards read a pre-aggregated serving table, never `raw_events` | US-02, US-12 |
| **Updates are incremental** | Serving table stores *delta sums* (SummingMergeTree); new events only append deltas — already-published minutes are untouched | US-08, US-13 |
| **Scale is structural** | Interval→delta compaction: a 30-min session becomes ~2 delta rows, not 30–1800 rows | US-09, US-15 |

**Key architectural decision:** ClickHouse materialized views are *stateless* (fire per-insert). Session-aware active-interval derivation is *stateful* (needs the history of a session's heartbeats). So we **contain all statefulness in one small component** (the delta builder) and keep everything downstream a pure, incremental, stateless SQL chain — **and we never ask a materialized view to compute a global cumulative sum** (that cannot be maintained incrementally; it forces a rebuild). Instead, the serving layer stores per-minute delta sums and reconstructs concurrency with a bounded-range window sum at query time.

### 1.1 Active-range representation — options considered

| Representation | Considered? | Verdict | Reason |
|---|---|---|---|
| Interval arrays per session | ❌ rejected | `Array(Tuple(start,end))` is update-unfriendly in CH (rewrite whole array on tail growth) and awkward to filter/join at scale |
| Normalized interval rows per session | ❌ rejected | 2 rows/session *is* good, but keeping them mutable per-session breaks the stateless-MV chain |
| Pre-aggregated minute deltas | ✅ **chosen** | `delta_minute (+1/−1)` — additive, idempotent, mergeable, update-friendly, filter-friendly |
| Hybrid (recent intervals + historical deltas) | ✅ **chosen for tiering** | recent tier stays detailed; history compacts to deltas |

---

## 2. End-to-end data flow

```
┌─────────────────────────────── SOURCES ───────────────────────────────┐
│  ch-hackathon-raw-data.csv  (~905K events)   ch-hackathon-content.csv │
└───────────────┬─────────────────────────────────────────┬────────────┘
                │  clickhouse-client INSERT … FORMAT CSV   │
                │  async_insert=1 · buffer for micro-batches│
                ▼                                          ▼
┌──────────────────────────────┐          ┌──────────────────────────────┐
│  L1  raw_events   (MergeTree)│          │  L1  content_dim  (MergeTree)│
│  PARTITION BY day            │          │  ORDER BY content_id         │
│  ORDER BY (event_timestamp,  │          │        +                     │
│            video_session_id) │          │  L1b content_dict (Dictionary)│
└──────────────┬───────────────┘          └──────────────┬───────────────┘
               │  dictGet(content_id) → title/video_type/category
               ▼
┌───────────────────────────────────────────────────────────────────────┐
│  L2  enriched_events  (materialized view or view)                     │
│      raw + content metadata  ·  video_type becomes a filter dimension │
└──────────────────────────────┬────────────────────────────────────────┘
                               │  ▼ THE STATEFUL BRAIN (contained) ▼
                               │  ACTIVE-INTERVAL DERIVATION
                               │  · heartbeat gap > 90s → close interval
                               │  · AppBackgrounded → cut; Foregrounded → resume
                               │  · pause/resume markers · VideoSessionEnd → close
                               │  · open sessions: extend tail only (US-08)
                               │  emit →  +1 at active-start minute
                               │          −1 at active-end   minute
                               ▼
┌───────────────────────────────────────────────────────────────────────┐
│  L3  HYBRID TIERING                                                   │
│  ┌── RECENT TIER (0–1h, detailed) ──┐   ┌── HISTORY TIER ────────────┐│
│  │ open_sessions (ReplacingMergeTree)│   │ delta_minute               ││
│  │   active ranges per open session  │ → │  (SummingMergeTree)        ││
│  │   extend in place on heartbeat    │   │  ORDER BY (minute, dims)   ││
│  │   finalize on close/watermark     │   │  delta Int32 → collapses   ││
│  └───────────────────────────────────┘   └───────────────────────────┘│
└──────────────────────────────┬────────────────────────────────────────┘
                               │  additive appends only
                               ▼
┌───────────────────────────────────────────────────────────────────────┐
│  L4  SERVING LAYER  (dashboards read here only)                       │
│      serving_minute: (minute, platform, country, content_id,          │
│                       video_type, category) → delta sums              │
│      → queries: sum(delta) OVER (PARTITION BY dims ORDER BY minute)   │
│        peak = max · avg = mean of reconstructed minute concurrency    │
└──────────────┬────────────────────────────────────────────────────────┘
               │
   ┌───────────┼───────────────┬───────────────┬───────────────┐
   ▼           ▼               ▼               ▼               ▼
 Peak/Avg    Dashboard /     Chat layer     Observability   Unseen-day
 benchmark    live-event      LibreChat +    ClickStack     evidence:
 queries      replay curve    ClickHouse     (ingestion lag,  system.query_log
 (ms latency) (demo)          MCP server     query p95)      + EXPLAIN + latency
```

---

## 3. Layer-by-layer detail

### L1 — Landing (raw + content)
| Table | Engine | Ordering key | Purpose |
|---|---|---|---|
| `raw_events` | `MergeTree` | `(event_timestamp, video_session_id)` | ground truth; never deleted while open sessions exist |
| `content_dim` | `MergeTree` | `content_id` | content metadata |
| `content_dict` | `HashedDictionary` | hash on `content_id` | O(1) enrichment, avoids hot-path join |

Low-cardinality columns (`platform`, `country`, `video_type`, `category`, `event_type`) use `LowCardinality()`. Timestamps are `DateTime64(3)`. Day partitions + TTL support tiering.

### L2 — Enrichment (US-11)
Materialized view joining `raw_events` → `content_dict` via `dictGet(content_id, 'video_type')` so **video_type / title / category become filter dimensions** absent from raw rows. Join consistency: `0` unmapped `content_id` expected; NULLs flagged and documented.

### L3 — The stateful brain: active-interval derivation (US-06/07/09)
The only stateful component. Two co-existing approaches validated against each other:

**Session-aware** (`GROUP BY video_session_id`):
1. Order events by `event_timestamp`.
2. Compute heartbeat gap between consecutive active signals (`VideoPlay`/`VideoHeartbeat`) via window functions (`lagInFrame`) or `groupArray` + `arrayDifference`.
3. Cut an active segment when: heartbeat gap **> 90s** (interval closes at `last_heartbeat + 90s`), OR `AppBackgrounded`, OR `VideoSessionEnd`.
4. Resume after `AppForegrounded`/`VideoPlay`/first heartbeat after a gap.
5. Result: one or more `[active_start, active_end)` intervals per session.

**Session-independent** (no grouping — pure event-state): emit `+1` when a session transitions to active and `−1` when it transitions away, directly from the ordered event sequence.

**Parity (US-09):** both must agree on closed, fully-observed sessions; differences allowed only for open sessions at the boundary — documented.

**Explicit active-flag alternative (direction #5):** a `is_active` column on the interval rows, set by the delta builder, is retained as a traceable flag for audit — but the *counting* uses deltas, so the flag is evidence, not the mechanism.

### L4 — Hybrid tiering + incremental compaction (US-08/13)
- **Recent tier — `open_sessions`** (`ReplacingMergeTree`, keyed `video_session_id`): holds active ranges for sessions still open or < 1h old. A new heartbeat extends only the tail in place → emits a delta only for the newly covered minute. Already-published minutes are never rewritten (US-08: minute 10:04 stays 500 when 10:06 arrives).
- **History tier — `delta_minute`** (`SummingMergeTree`): each finalized `[s, e)` interval becomes `+1` at `toStartOfMinute(s)` and `−1` at `toStartOfMinute(e)`. Rows with identical `(minute, dims)` collapse by summing `delta`.
- **Finalization:** when a session closes OR the watermark (e.g., `now() − 1h`) passes, the delta builder moves its intervals from `open_sessions` into `delta_minute` as deltas.
- **Late/duplicate (US-10):** dedup key `(video_session_id, event_timestamp, event_type)`; additive deltas mean a late correction is just another delta applied to the correct event-time minute.

### L5 — Serving layer (US-12, US-04, US-05)
- **`serving_minute`** stores per-minute **delta sums** (not absolute concurrency — that is the crucial incremental-friendly choice). A query reconstructs concurrency over only its range:
  ```sql
  SELECT minute,
         sum(delta) OVER (PARTITION BY platform, country, content_id, video_type
                          ORDER BY minute) AS concurrency
  FROM serving_minute
  WHERE minute BETWEEN '2026-07-26 19:00' AND '2026-07-26 19:59'
  ```
  - **Peak:** `max(concurrency)` over the range. **Avg:** `mean(concurrency)`. **Hour/day grain:** same window, bucketed (`toStartOfHour`/`toStartOfDay`), or via pre-aggregated `serving_hour`/`serving_day` for fixed-grain dashboards.
  - Bounded range → 1 day = 1440 rows → ms latency. `GROUPING SETS`/rollup can pre-materialize dimension combinations so every combo peaks at its own minute (US-04).
- **Coarse-grain pre-aggregation:** optional `serving_hour`/`serving_day` (`AggregatingMergeTree` with `SimpleAggregateFunction(max, …)` / `avgState`) refreshed incrementally for *fixed* grains; arbitrary-range queries still compute from `serving_minute`.

### L6 — Consumers
- **Benchmark queries** — peak/average at minute/hour/day with arbitrary filters, reading only the serving layer.
- **Demo replay** — feed events at 60x, watch the curve build, filter instantly (US-17).
- **Chat** — LibreChat + ClickHouse MCP: "*peak concurrency on Android in the last hour?*" → real query over `serving_minute`.
- **Observability** — ClickStack over `system.metrics`, `system.asynchronous_metrics`, `system.query_log`.
- **Evidence (US-16)** — benchmark answers CSV + `system.query_log` rows + `EXPLAIN` + per-query latency.

---

## 3.5 Grouping / partitioning columns per layer

Every layer groups on a *specific* column set. These are the exact grouping + ordering keys that make the chain coherent end-to-end:

| Layer | Table / step | Grouping key (semantic) | ClickHouse key | Why this grouping |
|---|---|---|---|---|
| **L1** | `raw_events` | *none — row level* | `PARTITION BY toDate(event_timestamp)` · `ORDER BY (event_timestamp, video_session_id)` | raw landing; no grouping yet, only ordering for scans + session walk |
| **L1** | `content_dim` | `content_id` | `ORDER BY content_id` | metadata lookups by content |
| **L2** | `enriched_events` | *none — row level (dimension-injection)* | same as raw + `dictGet` columns | enrichment adds `video_type/category` as future filter dims; no aggregation yet |
| **L3** | delta builder (session-aware) | `video_session_id` | `GROUP BY video_session_id` + order by `event_timestamp` | stateful per-session interval assembly (heartbeat gaps, bg/fg, end) |
| **L3** | delta builder (session-independent) | *none — pure event-state* | event stream ordered by `event_timestamp` | emits `+1`/`−1` from transitions; no session grouping |
| **L4** | `open_sessions` (recent) | `video_session_id` | `ORDER BY video_session_id` (ReplacingMergeTree) | one current row per open session; tail-extension overwrites by key |
| **L4** | `delta_minute` (history) | `(minute, platform, country, content_id, video_type)` | `ORDER BY (minute, platform, country, content_id, video_type)` · `delta Int32` (SummingMergeTree) | **the canonical aggregation key** — rows collapse by summing delta; defines what concurrency is bucketed by |
| **L5** | `serving_minute` | `(minute, platform, country, content_id, video_type, category)` | same + `category` | dashboard reads; window `PARTITION BY` the same dims, `ORDER BY minute` for cumulative sum |
| **L5** | `serving_hour` / `serving_day` | `(hour/day, platform, country, content_id, video_type, category)` | `ORDER BY (grain, …)` · `SimpleAggregateFunction(max/avg)` | fixed-grain rollups: peak = max / avg = mean over contained minutes |
| **L5** | benchmark queries | arbitrary `GROUP BY` over serving dims | e.g., `GROUP BY platform` / `GROUP BY platform, country` | each dimension combination peaks at its own minute (US-04); pre-materialized via `GROUPING SETS` |

**Design invariant:** the grouping key only ever *widens* as data flows down (L1 none → L3 session → L4 minute+dims → L5 grain+dims). It never splits or re-joins across a different column family, which is why the deltas stay additive and each aggregation layer is a pure refinement of the one above it. `platform`/`country`/`content_id`/`video_type` are the canonical filter dimensions from the problem statement and are preserved through every layer.

---

## 4. How the aggregations form (systematic)

```
raw event stream
   │ 1. land         raw_events (per-event, ms timestamps)
   ▼
   │ 2. enrich       dictGet → +video_type/title/category
   ▼
   │ 3. derive       active intervals per session (gap>90s, bg/fg, end)
   ▼
   │ 4. expand       [s,e) → delta(+1 at s, −1 at e)
   ▼
   │ 5. compact      SummingMergeTree collapses identical (minute,dims) → net delta
   ▼
   │ 6. reconstruct  sum(delta) OVER (dims, minute) → per-minute concurrency
   ▼
   │ 7. aggregate    peak=max · avg=mean · hour/day grains · GROUPING SETS dim combos
   ▼
   │ 8. serve        dashboards / benchmarks / chat — never touch raw
```

Each step is **lossless and additive** except step 7 (intentional compaction). Updates from step 3 flow forward as deltas only — the chain absorbs them incrementally.

---

## 5. DDL sketch (ordering keys / engines)

```sql
-- L1 raw (ground truth)
CREATE TABLE raw_events (
    content_id           UInt64,
    video_session_id     String,
    user_id              String,
    event_type           LowCardinality(String),
    event                LowCardinality(String),
    event_timestamp      DateTime64(3),
    platform             LowCardinality(String),
    app_version          String,
    country              LowCardinality(String),
    audio_language       LowCardinality(String),
    subtitle_language    LowCardinality(String),
    player_version       String,
    session_start_epoch  DateTime64(3)
) ENGINE = MergeTree
PARTITION BY toDate(event_timestamp)
ORDER BY (event_timestamp, video_session_id);

-- L1 content metadata
CREATE TABLE content_dim (
    content_id  UInt64,
    title       String,
    video_type  LowCardinality(String),
    category    LowCardinality(String)
) ENGINE = MergeTree ORDER BY content_id;

-- L1b O(1) enrichment dictionary
CREATE DICTIONARY content_dict (
    content_id UInt64, title String, video_type String, category String
) PRIMARY KEY content_id
SOURCE(CLICKHOUSE(TABLE 'content_dim'))
LIFETIME(3600);

-- L3 RECENT TIER — open sessions, extend in place (US-08)
CREATE TABLE open_sessions (
    video_session_id   String,
    platform           LowCardinality(String),
    country            LowCardinality(String),
    content_id         UInt64,
    video_type         LowCardinality(String),
    last_heartbeat     DateTime64(3),
    active_ranges      Array(Tuple(DateTime64(3), DateTime64(3))),  -- [start,end) pairs
    is_active          UInt8,              -- explicit active flag (evidence)
    watermark_expires  DateTime64(3)
) ENGINE = ReplacingMergeTree
ORDER BY video_session_id;

-- L3 HISTORY TIER — compacted, additive, incremental (US-13)
CREATE TABLE delta_minute (
    minute       DateTime,
    platform     LowCardinality(String),
    country      LowCardinality(String),
    content_id   UInt64,
    video_type   LowCardinality(String),
    delta        Int32
) ENGINE = SummingMergeTree
PARTITION BY toDate(minute)
ORDER BY (minute, platform, country, content_id, video_type);

-- L4 SERVING — per-minute delta sums; dashboards read here only (US-12)
CREATE TABLE serving_minute (
    minute       DateTime,
    platform     LowCardinality(String),
    country      LowCardinality(String),
    content_id   UInt64,
    video_type   LowCardinality(String),
    category     LowCardinality(String),
    delta        Int32
) ENGINE = SummingMergeTree
PARTITION BY toDate(minute)
ORDER BY (minute, platform, country, content_id, video_type, category);

-- L4 optional fixed-grain rollups (US-05)
CREATE TABLE serving_hour (
    hour           DateTime,
    platform       LowCardinality(String),
    country        LowCardinality(String),
    content_id     UInt64,
    video_type     LowCardinality(String),
    category       LowCardinality(String),
    peak           UInt64,                      -- max of its 60 minutes
    avg_concurrency AggregateFunction(avg, UInt64)
) ENGINE = AggregatingMergeTree
ORDER BY (hour, platform, country, content_id, video_type, category);
```

*Streaming path:* materialized views (`TO serving_minute`) copy deltas as they land; the delta builder maintains `open_sessions` and finalizes to `delta_minute` on close/watermark. Note `serving_minute` stores `delta`, NOT absolute concurrency — absolute values are reconstructed by a bounded window sum, which is what keeps updates incremental.

---

## 6. Use-case coverage matrix

| Story | Layer that satisfies it |
|---|---|
| US-01 foreground concurrency / min | L3 interval logic + L4 `serving_minute` |
| US-02 peak over range | L4 `max(concurrency)` after window sum |
| US-03 average over range | L4 `mean(concurrency)` per minute |
| US-04 dimension-filtered | L4 `GROUPING SETS` + `LowCardinality` dims |
| US-05 minute/hour/day grains | L4 `serving_minute` + `serving_hour/day` |
| US-06 exclude backgrounded | L3 `AppBackgrounded` cuts |
| US-07 missing-heartbeat rule | L3 gap-timeout (90s) closes interval |
| US-08 open sessions incremental | L3 tail-extension emits new deltas only |
| US-09 aware vs independent parity | L3 both derivations, reconciled |
| US-10 late / duplicate events | L4 additive deltas + dedup on `(session, ts, type)` |
| US-11 content enrichment | L2 dictionary join |
| US-12 serving layer | L4 pre-aggregated tables |
| US-13 incremental compaction | L3 `open_sessions` → `delta_minute` finalization + TTL |
| US-14 observability integration | L6 ClickStack / LibreChat+CH MCP |
| US-15 scalability 100x | L4 compaction + bounded-range serving (no rescans) |
| US-16 unseen-day evidence | L6 `system.query_log` + `EXPLAIN` + latency |
| US-17 demo replay | L6 live ingestion → curve → filter → chat |

---

## 7. Key trade-offs (why this design)

| Decision | Chose | Rejected | Why |
|---|---|---|---|
| Active representation | interval→delta (+1/−1) | per-minute explosion; interval arrays | additive = incremental; ~2 rows/session; arrays are update-hostile in CH |
| Where statefulness lives | one delta-builder component | stateful MVs everywhere | CH MVs are per-insert; containing state makes the chain stateless |
| Serving content | **delta sums**, window-sum at query | absolute concurrency materialized in MV | absolute cumulative can't be maintained incrementally → full rebuild |
| Serving range size | bounded window (day = 1440 rows) | scan raw history | ms latency, judges see serving-only reads |
| Open sessions | tail-extension deltas in `open_sessions` | re-run full event stream | minute 10:04 must stay 500 when 10:06 arrives |
| Heartbeat gap rule | last heartbeat + 90s closes | naive fixed session window | matches US-07; measured cadence ~40s < threshold |
| Background markers | corroborating, not required | rely on them alone | docs: not guaranteed events |
| History | hybrid tiering (recent detail / compacted deltas) | single flat history | balances update cost vs query speed at 100x |
| Coarse grains | fixed-grain rollups + arbitrary-range window sums | only pre-aggregated | keeps arbitrary queries correct without explosion |
