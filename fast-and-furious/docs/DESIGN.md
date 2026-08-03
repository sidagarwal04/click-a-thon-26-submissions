# Foreground-Only Concurrency at Streaming Scale — Solution Design

> **Legacy, non-authoritative draft.** It is retained for the end-of-session
> comparison only. The verified implementation and current UTC contract are in
> [`solution/`](../solution/README.md).

**Team submission for Click-a-thon 2026 · SonyLIV problem statement**
**Status: draft v1 — every decision cites measured evidence (`docs/EVIDENCE.md`)**

---

## 0. TL;DR

A two-tier ClickHouse model:

1. **Tier 1 — session state** (`AggregatingMergeTree`, keyed by session): absorbs the raw event stream through an insert-time incremental MV into *commutative aggregate states* (min/max/argMax/groupUniqArray). Order-insensitive and duplicate-insensitive by construction — this is what makes the model update-friendly under the measured disorder (99.65% of sessions have out-of-order events, p99 within-session lateness ≈ 2.3 h).
2. **Tier 2 — serving deltas** (`SummingMergeTree`, keyed by dims + minute): a watermark-driven **compactor** turns each session's state into *foreground-active intervals* (bg/fg state machine + 120s liveness rule), splits them at day boundaries, and emits **+1/−1 deltas at interval edges**. Concurrency at minute M = cumulative sum of deltas from midnight. Peak/avg over any range and any filter = window functions over a few thousand pre-aggregated rows, never the raw history.

Late events re-open a session's state; the compactor re-emits *correction deltas* (new − old) so the serving layer absorbs updates **incrementally, no rebuild**.

A third, session-independent approximate path (per-minute `uniqState`) is maintained for cross-validation, as the problem's README explicitly requests a comparison of both approaches.

---

## 1. What the data actually says (evidence-driven constraints)

Full profiling in `docs/EVIDENCE.md`. The facts that shape the design:

| # | Fact (measured, not assumed) | Design consequence |
|---|---|---|
| E1 | The periodic heartbeat is a **40s trio** {network-activity, buffer-health, video-resize}, not 60s (p50 gap = 40.00s; 66.8% of gaps in [39,41)s) | Liveness threshold must be a multiple of 40s, not 60s |
| E2 | **74.4% of iPhone sessions emit zero trio pings** — the iOS client doesn't send the periodic bundle | Liveness must accept **any** event name, not just the trio, or we silently drop most iOS traffic |
| E3 | `event_type='VideoHeartbeat'` hides **41 distinct event names**, incl. lowercase `pause` (27,340) / `resume` (31,780) | State machine parses the `event` column; the dictionary's event_type list is incomplete |
| E4 | **Heartbeats stop when backgrounded**: 78.5% of bg-windows >120s contain zero heartbeats (0.37 observed vs 17.9 expected) | The liveness gap rule catches *silent* backgrounding too (9.1% of sessions have >3min silent gaps with no bg event) |
| E5 | **Pause pings keep flowing** at ~39% of nominal rate during foreground pause | Pause is *not* detectable from silence; paused-in-foreground counts as active in the default definition (explicit knob to change) |
| E6 | Legit heartbeat gaps: p99 = 40.01s, p99.5 = 49s. Cut-rate at T=120s is **0.201%** vs 0.446% at 60s, 0.157% at 180s | **T = 120s** (3 missed ticks) — the knee of the curve; 180s adds 60s phantom tail for only 0.044pp gain |
| E7 | Naive concurrency **overcounts foreground by 26.0% at peak** (3,743 vs 2,970) and 34.6% in aggregate session-minutes | The business case for the whole model, measured on real data |
| E8 | 99.65% of sessions have ≥1 out-of-order event; p99 within-session lateness ≈ 2.3h, max 43.3h | No fixed short watermark works → commutative states + re-compaction, not ordered windowing |
| E9 | **Every session in the extract is closed**; open sessions exist only mid-replay | Open-session handling is validated via event-time replay, not at-rest data |
| E10 | `VideoSessionEnd` is not terminal: 239 sessions trail events after End (217 end on AppBackgrounded) | End = hard terminator (argMax of End events), later events clipped |
| E11 | Duplicate lifecycle events: 13 sessions with multiple Starts, 14 with multiple Ends (4 at *different* timestamps); 4,210 exact duplicate rows (0.465%) | min/argMax semantics make dups harmless; `groupUniqArray` (not `groupArray`) for bg/fg |
| E12 | **`video_session_id` collides**: 120 sessions span 2 user_ids, 95 span 2 platforms | Session key = `(user_id, video_session_id)` |
| E13 | Cardinalities: platform=10, country=1 (constant!), content_id=3,357 played / 33,464 dim (100% join coverage), video_type = f(content_id). Actual (platform × content) combos = **4,349** | Serving grid is tiny; content enrichment via dictionary; country carried but worthless |
| E14 | Slice peaks ≠ global peak: JIO_ANDROID_TV peaks at 10:59 UTC (230), global at 10:56 UTC | Serving layer must keep per-(dims, minute) state — confirmed requirement, and our delta model provides it |
| E15 | bg/fg pairing is 95.55% clean; anomalies: double-bg (101 sessions), fg-without-bg (67), unclosed final bg (344) | Defensive state machine rules, specified below |
| E16 | Explicit backgrounded time = **30.6%** of naive session-minutes; silent gaps add 5.2pp more | bg exclusion is 6× the impact of the gap rule — both are required |
| E17 | 86.2% of all events sit in one hour (~217 ev/s sustained, 426 ev/s peak-second → ~21.7K/42.6K ev/s at 100x) | Batched/async inserts; benchmark on the hot window, not the 12-day average |
| E18 | Languages are case-inconsistent by event type (`unk`/`UNK`/`OFF`/`off`, `eng-English` suffix); Start rows carry empty player_version | Normalization at ingest MV, else every GROUP BY double-counts |
| E19 | 16 sessions (0.147%) cross a day boundary; 1 spans 3 days | Day-splitting intervals is cheap; day-anchored cumsum is safe |
| E20 | Brute force ground truth = 0.5s over 906K events on a laptop, materializing ~386K intermediate rows | Fine once, dies at 100x × dashboard fan-out — motivates the serving layer (judges' "what do queries read") |

---

## 2. Active-interval definition (the correctness contract)

A session contributes to concurrency at minute M **iff all of**:

1. **Liveness**: some qualifying event occurred in `(M − 120s, M]`. Qualifying = *any* event of the session (E2), i.e. `event_type ∈ {VideoSessionStart, VideoPlay, VideoHeartbeat, AppForegrounded}`. T = 120s per E6.
2. **Foreground gate**: `AppBackgrounded` deactivates **immediately** (E4: pings stop within ~5s; waiting out T would add up to 120s phantom per bg). `AppForegrounded` or any later qualifying event reactivates (fg→next heartbeat p50 = 0.91s).
3. **Terminator**: `VideoSessionEnd` closes the session at `argMax(end_ts)` (last-End-wins, E11); events after End are clipped (E10).
4. **Defensive rules** (E15): double-bg → first bg wins; fg-without-open-bg → no-op reactivation; unclosed final bg → backgrounded through session end; `resume`-without-`pause` → no-op.
5. **Zombie cap**: any silent period contributes at most T; re-open on next event (kills the 43.6h session inflating hours of concurrency).
6. **Pause**: foreground `pause` does **not** deactivate by default (E5; undetectable from silence — a paused-but-foregrounded player is "app open, watching surface visible"). Parameterized: the compactor can treat `pause`/`resume` as edges if the benchmark defines active = playing.

**Session identity** = `(user_id, video_session_id)` (E12). **Dimension attribution**: per-interval `argMax` (a session's interval carries one dims tuple → slice sums remain additive and equal global; the 95 dual-platform sessions cause ≤0.4% divergence vs event-attribution at peak, documented).

---

## 3. Schema (ClickHouse, per best-practices skill rules)

### 3.1 Landing table — append-only raw events

```sql
CREATE TABLE raw_events (
    event_date        Date MATERIALIZED toDate(event_time),
    event_time        DateTime64(3),                -- fromUnixTimestamp64Milli(event_timestamp)
    user_id           String,
    video_session_id  String,
    session_start     DateTime64(3),
    content_id        UInt64,
    event_type        LowCardinality(String),
    event             LowCardinality(String),       -- 47 values
    platform          LowCardinality(String),       -- 10 values
    country           LowCardinality(String),       -- 1 value, kept for schema fidelity
    app_version       LowCardinality(String),       -- 65
    audio_language    LowCardinality(String),       -- normalized at ingest (E18)
    subtitle_language LowCardinality(String),
    player_version    LowCardinality(String)
) ENGINE = MergeTree
PARTITION BY event_date
ORDER BY (video_session_id, event_time);
```

- `ORDER BY (video_session_id, event_time)`: ingestion is session-clustered (compresses well), and the compactor's per-session scans align with the sort key. Per `schema-pk-cardinality-order`, a leading low-card column buys nothing here because *all* reads of this table are session-keyed or full-window scans.
- `PARTITION BY day` per `schema-partition-lifecycle` — lifecycle + unseen-day isolation, ~12 partitions at 1x (well under limits).
- All ≤84-value strings are `LowCardinality` per `schema-types-lowcardinality`; no Nullable anywhere per `schema-types-avoid-nullable`.
- Ingest normalization (MV or insert SELECT): `lowerUTF8` + suffix-strip on languages, `'' → 'unknown'`.

### 3.2 Content enrichment — dictionary, not JOIN

```sql
CREATE DICTIONARY dict_content (
    content_id UInt64,
    title String,
    video_type String,   -- '' normalized to 'unknown' (E13: 142 played ids)
    category String
) PRIMARY KEY content_id
SOURCE(CLICKHOUSE(TABLE 'content'))
LAYOUT(HASHED()) LIFETIME(MIN 300 MAX 600);
```

33,464 rows, unique key, 100% coverage, slowly changing → textbook dictionary case per `decision-join-enrichment` (official). `dictGet` at compaction time = denormalized into serving rows.

### 3.3 Tier 1 — session state (order-insensitive absorption)

```sql
CREATE TABLE session_state (
    user_id           String,
    video_session_id  String,
    first_ts          SimpleAggregateFunction(min, DateTime64(3)),
    end_ts            SimpleAggregateFunction(max, DateTime64(3)),   -- max over VideoSessionEnd events only
    last_activity_ts  SimpleAggregateFunction(max, DateTime64(3)),
    activity_minutes  AggregateFunction(groupUniqArray, DateTime),    -- distinct qualifying-event minutes
    bg_ts             AggregateFunction(groupUniqArray, DateTime64(3)),
    fg_ts             AggregateFunction(groupUniqArray, DateTime64(3)),
    platform          AggregateFunction(argMax, String, DateTime64(3)),
    content_id        AggregateFunction(argMax, UInt64, DateTime64(3)),
    dirty_since       SimpleAggregateFunction(max, DateTime)          -- ingest wall-clock, drives compaction
) ENGINE = AggregatingMergeTree
ORDER BY (user_id, video_session_id);
```

Fed by an incremental MV on `raw_events` (per `query-mv-incremental` / `decision-real-time-preaggregation`, official). Why this shape:

- **Every aggregate is commutative** → arbitrary disorder, duplicates, and lateness merge to the same state (E8, E11). This is the property no ordered/windowed pipeline gives us.
- `groupUniqArray(minute)` bounds state: a 43h session = ≤2,618 distinct minutes ≈ KBs, and dedups the 92% of session-minutes with >1 heartbeat (E: minute-grain collapses 83.89% of heartbeat rows).
- bg/fg arrays are tiny (3.2% of events; modal count 1+1 per session).
- `dirty_since` lets the compactor find exactly the sessions touched since the last run — **incremental by construction**.

### 3.4 Tier 2 — serving deltas + compactor

```sql
CREATE TABLE concurrency_deltas (
    day        Date,
    minute     DateTime,                  -- interval edge, minute grain
    platform   LowCardinality(String),
    content_id UInt64,
    video_type LowCardinality(String),
    delta      Int32                      -- +1 open, −1 close; corrections are compensating pairs
) ENGINE = SummingMergeTree(delta)
PARTITION BY day
ORDER BY (platform, content_id, minute);

-- roll-ups for filter-light dashboards (chained MVs):
--   deltas_platform (day, minute, platform)  and  deltas_global (day, minute)
```

**Compactor** (scheduled refreshable-MV / cron `INSERT…SELECT`, every 30–60s):

1. Pick sessions with `dirty_since > last_watermark`.
2. Rebuild each session's foreground intervals from Tier-1 state: merge `activity_minutes` into runs (gap ≤ T), subtract bg/fg windows (state machine of §2.4), clip at `end_ts`, **split at day boundaries** (E19: 0.147% of sessions — negligible cost, buys day-anchored cumsum).
3. Diff against `emitted_intervals` (ReplacingMergeTree memo of what each session last published) and emit **only the correction deltas** (new − old).

Per `decision-late-arriving-upserts` (official): append + version semantics, zero mutations. A late heartbeat re-dirties its session; the serving layer absorbs the correction as two tiny delta rows. **No rebuild, ever.**

### 3.5 Serving queries (what the dashboard reads)

Concurrency series for any filter/grain:

```sql
SELECT minute, sum(d) OVER (ORDER BY minute) AS concurrent
FROM (
    SELECT minute, sum(delta) AS d
    FROM concurrency_deltas
    WHERE day = {d} AND platform = {p}          -- ORDER BY prefix per schema-pk-filter-on-orderby
    GROUP BY minute
)
ORDER BY minute;
```

- Day-anchored: cumsum starts at 0 at midnight (intervals were split at day edges) → reads **one day of deltas for the filtered combos**, never history. Peak = `max(concurrent)`, average = `avg(concurrent)` (zero-filled via `WITH FILL` for missing minutes). Hour/day grain = same query, `max/avg` regrouped.
- What it reads at 1x: ≤ a few thousand rows per day per filter; at 100x: deltas/day ≈ 2 × intervals/day — bounded by *sessions*, not events, and ~50× smaller than the raw stream (E20 motivates: judges look at what queries read).

### 3.6 Session-independent comparison path (README deliverable)

`AggregatingMergeTree (minute, platform, content_id) → uniqCombinedState(session)` fed by a direct MV on raw events (each event covers its minute + 2 forward). No bg-exclusion (that needs session context) → measurably overcounts around bg edges; approximate uniq. We publish the measured accuracy delta vs the session-aware path — this *is* the comparison the README asks for, with numbers.

### 3.7 Live "right now" number

`SELECT count() FROM session_state WHERE last_activity_ts > now() − 120s AND end_ts = 0-sentinel` (finalized sessions excluded) — a bounded scan of ~10.9K state rows (1.09M at 100x, still trivial with the minute filter). The demo replay shows the curve building in near-real-time from the same tables.

---

## 4. Trade-offs we're claiming (the defense)

| Choice | Alternative rejected | Why (evidence) |
|---|---|---|
| Delta model (+1/−1) | Per-minute exploded rows | Problem statement calls explosion prohibitively large; deltas = 2 rows/interval vs ~16 minute-rows for the median 12-min session; storage bounded by sessions not minutes |
| Compactor (scheduled) for interval finalization | Pure insert-time MV | "Activity stopped" = *absence* of events; an insert-time MV can never observe absence. Watermark compaction is the documented incremental pattern (problem hints list it) |
| Commutative Tier-1 states | Ordered window pipeline | E8: p99 lateness 2.3h, 99.65% sessions disordered — any short watermark drops data, any long one delays serving. States are order-free; compaction handles time |
| T = 120s | 60s / 180s | E6: 0.201% false-cut at 120s; 60s cuts 2.2× more legit playback; 180s adds phantom tail for 0.044pp gain |
| bg = immediate close, gap = 120s close | Gap rule alone | E16: explicit bg exclusion is 6× the silent-gap correction; E4 shows silence usually follows bg anyway — using both matches ground truth |
| `(user_id, video_session_id)` key | `video_session_id` alone | E12: 1.1% of session ids collide across users — silent undercount |
| Dictionary enrichment | Runtime JOIN | 33K rows, static, unique, 100% coverage — official dictionary use-case |
| SummingMergeTree serving | AggregatingMergeTree uniq states | Deltas are exact, additive across dims (slice-peak correctness, E14), and ~32B/row; uniqExact states at 100x peak ≈ 300K sessions/minute get heavy; HLL is approximate |
| Day-split intervals | Continuous cumsum since epoch | Bounded reads (1 day), clean partition drops, self-contained unseen-day load; cost = 0.147% of sessions split |

## 5. Unseen-day protocol

New CSV → `INSERT INTO raw_events SELECT …` (same normalization SELECT) → MV populates Tier 1 → compactor drains dirty sessions (idempotent) → benchmark queries read `concurrency_deltas` for the new `day` partition → evidence = `system.query_log` extract (read rows/bytes + latency per benchmark query). Nothing about the pipeline is tuned to Jul 26; every threshold traces to measured invariants (cadence, gap distribution) that we re-verify on the unseen day with one profiling query before answering.

## 6. OSS integration (hackathon requirement)

Primary: **LibreChat + ClickHouse MCP** over the serving tables ("what was peak concurrency on Android in the last hour?") — natural fit called out by the problem statement itself. Secondary (if time): ClickStack on the pipeline's own ingest lag + compactor latency. Decision deferred to build phase.

## 7. Parameterized policy knobs (judge-proofing)

| Knob | Default | Why parameterized |
|---|---|---|
| Liveness T | 120s | Policy: freshness vs stability (data supports 90–180s) |
| Pause = inactive? | No | "Foreground" vs "actively playing" is a product definition; both computable |
| Post-End events | Clipped | 239 trailing sessions; judges' key may differ |
| Duplicate Ends | Last wins | 4 sessions differ; explicit convention |
| Dimension attribution | Per-interval argMax | Additivity; event-attribution available via (session×platform) emission |
| Bot user 4CE58A95… | Kept | Session-level metrics unaffected; excluded only from user-level metrics |
