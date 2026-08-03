# CLICKSTACK_DASHBOARDS — what every panel shows, and how to read it

> **Summary:** Panel-by-panel reference for the seven HyperDX dashboards on hosted ClickStack.
> The **2026-08-01 capture** proves 7 dashboards, 53 tiles, 24 sources, 1 connection and eight filters.
> The current provisioning candidate exposes all 12 declared filter dimensions plus generic sources
> for future columns, but those additions are not yet deployed or captured live. Dashboards
> 1–3 and 7 open with a markdown
> CAPTION tile stating the trap a viewer would otherwise fall into (peaks not summable, title not a
> key, users are a set). Read this with [CLICKSTACK.md](CLICKSTACK.md) (*bringing the stack up*); this
> file covers *what is on screen*. **The single most common failure is the time range** — data ends
> 2026-07-26; set **2026-07-14 → 2026-07-26** before concluding anything is broken.

**Captured:** 2026-08-01 · hosted HyperDX in ClickHouse Cloud · connection `ClickathonProject` ·
database `sonyliv` · all tiles read our own serving views, never raw events. Every tile below was
**executed signed-in through HyperDX's own query path** this session —
[evidence/clickstack/](../evidence/clickstack/) holds the per-tile results.

**Verified rendering 2026-08-01**, all four headline tiles live on the graded service:

```
 Peak — ACCURATE (foreground-only)   2,917      ← the graded number
 Peak — stateless baseline           2,894
 Peak — NAIVE session-span           3,743      ← its OWN peak; see the note in §1
 Peak — distinct users               2,844
```

---

## 0 · The shape of it

```
                          ClickHouse Cloud · sonyliv
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        │ serving views              │ system.query_log           │
        ▼                            ▼                            ▼
   24 HyperDX sources ────────────────────────────────────────────┘
        │
        ├─▶ 1. SonyLIV concurrency          11 tiles   THE HEADLINE (+ caption)
        ├─▶ 2. SonyLIV drilldown            9 tiles + 8 filters    (+ caption)
        ├─▶ 3. SonyLIV content              8 tiles                (+ caption)
        ├─▶ 4. SonyLIV time-window trend    4 tiles
        ├─▶ 5. SonyLIV pipeline health      7 tiles    ← observes US
        ├─▶ 6. SonyLIV query cost           5 tiles    ← observes US
        └─▶ 7. SonyLIV user-level           9 tiles    (+ caption)
                                            ────────
                                            53 tiles
```

Dashboards 1–4 and 7 chart **the product**. Dashboards 5–6 chart **our own pipeline** — that is the
both-directions claim: ClickStack is not only where our data is drawn, it is where our *pipeline's*
health is observed. Delete it and the freshness and cost panels have nowhere to come from.

---

## 1 · `SonyLIV concurrency` — the headline

The dashboard to open first, and the one the demo leads with. It now **opens with a markdown
caption — “The gap IS the thesis”** — stating on screen what §1 below explains: 3,708 vs 2,917
at 10:56 (21.3% over-count eliminated), 33.6% of apparent watch time excluded, naive peaking
higher *and later*, and the accurate-vs-stateless gap being the pause exclusion.

```
 ┌────────────────────────────────────────────────────────────┐
 │ CAPTION — The gap IS the thesis                            │  ← markdown tile
 ┌──────────────┬──────────────┬──────────────┬──────────────┐
 │ Peak         │ Peak         │ Peak         │ Peak         │  ← 4 number tiles
 │ ACCURATE     │ stateless    │ NAIVE        │ distinct     │
 │ (green)      │ baseline     │ session-span │ users        │
 └──────────────┴──────────────┴──────────────┴──────────────┘
 ┌────────────────────────────────────────────────────────────┐
 │ Concurrency — ACCURATE, gap + pause excluded               │  ← the money chart
 │ (peak 2,917 @ 2026-07-26 10:56)                            │
 └────────────────────────────────────────────────────────────┘
 ┌───────────────┬───────────────┬────────────────────────────┐
 │ ACCURATE      │ STATELESS     │ NAIVE session-span         │  ← the comparison,
 │ session-aware │ session-indep │ "the over-count"           │    side by side
 └───────────────┴───────────────┴────────────────────────────┘
 ┌──────────────────────────┬─────────────────────────────────┐
 │ Distinct users           │ Rolling 15-min peak             │
 │ (uniqExact, NOT deltas)  │                                 │
 └──────────────────────────┴─────────────────────────────────┘
```

| Tile | Reads | What it means |
|---|---|---|
| **Peak — ACCURATE** | `Concurrency ACCURATE (minute)` → `max(concurrent)` | The graded number. Foreground-only: gaps exclude backgrounding, explicit pause/resume excludes pausing. **2,917** |
| **Peak — stateless** | `Concurrency total (minute)` | The session-**in**dependent model, straight from event state. **2,894** |
| **Peak — NAIVE** | `Concurrency NAIVE session-span` | What you get counting session start→end overlap. **3,708** |
| **Peak — distinct users** | `User concurrency (minute)` → `max(concurrent_users)` | Distinct *people*, not sessions. **2,844.** Note the column is `concurrent_users`, **not** `concurrent` |
| **The ACCURATE curve** | same source, `max(concurrent)` per bucket | The live-sport shape: flat, then a near-vertical climb into 10:00 on 26 July |
| **Three curves side by side** | three sources | **This trio is the deliverable.** The spec demands both models *and* a comparison; naive is the third for contrast |
| **Distinct users** | `concurrent_users` | Users are **not summable** across dimensions — a `uniqExact` set union, never a delta sum |
| **Rolling 15-min peak** | `Rolling windows (minute)` → `peak_15m` | Smooths the spike; see dashboard 4 |

### ⚠ The naive tile reads **3,743**, but the deck says **3,708**. Both are right.

They answer different questions, and a judge comparing the two will notice:

```
 3,708  =  naive concurrency AT THE ACCURATE MODEL'S PEAK MINUTE (10:56)
           the like-for-like comparison — same minute, three definitions
           this is the 21.3% over-count figure

 3,743  =  naive's OWN peak, which lands at 10:59
           a max() over the naive curve has no reason to peak at the same
           minute the accurate curve does — and it doesn't
```

The number tile shows `max(concurrent)` over the whole range, so it necessarily reports 3,743. When
quoting the over-count, use **3,708 vs 2,917 at 10:56** and say "at the peak minute" out loud. When
pointing at the tile, say "naive peaks higher *and later*" — which is itself a good observation: the
naive model keeps counting sessions after their viewers have gone.

**How to read the trio.** The gap between naive and accurate *is* the answer:

```
  3,708  naive        ████████████████████████████████████  session start→end overlap
  2,917  accurate     ████████████████████████████          foreground-only
  2,894  stateless    ███████████████████████████▉          session-independent
                      └────── 791 viewers ──────┘  = 21.3% over-count eliminated
```

Accurate sits *slightly below* stateless because the stateless model still counts paused viewers —
heartbeats survive a pause. That small gap is the pause exclusion, made visible.

---

## 2 · `SonyLIV drilldown — sessions & users` — the filter story

Ten data tiles, all from one source (`Session minutes (drilldown)`). The live 2026-08-01 capture
has **8 dashboard filters**: platform, country, title, content_id, app_version, audio_language,
subtitle_language and player_version. The current candidate provisions **all 12 declared filters**,
adding `video_resolution`, `show_name`, `video_type` and `category`; deployment and a signed-in
capture are still required. Generic event/content dimension sources provide a slower fallback for
later unknown columns. One control drives every tile. A **caption tile — “⚠ Peak is NOT summable across
dimensions”** — heads the dashboard: summing per-platform peaks overstates the true peak by
**+2.4%**, per-content by **+94.7%** (re-measured 2026-08-01, [EXPLAINER §E.1](EXPLAINER.md)), and
it restates the zoom caveat and the Hindi-four-ways artifact so a viewer cannot miss them.

```
 ┌────────────────────────────────────────────────────────────┐
 │ CAPTION — ⚠ Peak is NOT summable across dimensions         │  ← markdown tile
 ┌────────────────────────────────────────────────────────────┐
 │ Sessions vs distinct users (= concurrency at 1-min zoom)   │
 └────────────────────────────────────────────────────────────┘
 ┌─────────────────────────┬──────────────────────────────────┐
 │ by platform             │ by country                       │
 ├─────────────────────────┼──────────────────────────────────┤
 │ by app_version          │ by audio_language                │
 ├─────────────────────────┼──────────────────────────────────┤
 │ by subtitle_language    │ by player_version                │
 ├─────────────────────────┼──────────────────────────────────┤
 │ top video_resolution    │ top show_name                    │
 └─────────────────────────┴──────────────────────────────────┘
 ┌────────────────────────────────────────────────────────────┐
 │ by title (top 20)                                          │
 └────────────────────────────────────────────────────────────┘

 FILTERS:  platform · country · title · content_id · app_version
           audio_language · subtitle_language · player_version
 CANDIDATE: video_resolution · show_name · video_type · category
```

Tiles use `count_distinct(video_session_id)` and `count_distinct(user_id)` **per bucket**. At
1-minute zoom that equals concurrency; zoom out and it becomes "distinct sessions active anywhere in
the bucket", which is a **larger** number. Say which you mean before quoting it.

⚠ **`audio_language` will show Hindi four times** — `hin`, `HIN`, `hin-hindi`, `hin-Hindi`. That is
real, un-normalised source data, not a bug in the panel. Normalisation exists
([ADR 0011](adr/0011-normalise-filter-dimensions-at-query-time.md)) but is **not deployed to Cloud**.

---

## 3 · `SonyLIV content` — demand by title

Headed by a **caption tile — “⚠ Read the labels carefully”** — carrying the two caveats below
(title is not a key; video_type's blank third value) plus the +94.7% content-grain
peak-summing warning, so they are stated on screen before a judge finds them.

```
 ┌────────────────────────────────────────────────────────────┐
 │ CAPTION — ⚠ Read the labels carefully                      │  ← markdown tile
 ┌──────────────────────────┬─────────────────────────────────┐
 │ Top titles by peak       │ NOW — by title (last minute)    │  tables
 ├──────────────────────────┼─────────────────────────────────┤
 │ by video_type            │ by category (top 20)            │  lines
 ├──────────────────────────┼─────────────────────────────────┤
 │ Top titles over time (top 20)                              │  line, full width
 ├──────────────────────────┼─────────────────────────────────┤
 │ NOW — by video_type      │ NOW — by category               │  tables
 └──────────────────────────┴─────────────────────────────────┘
```

The **NOW** tiles use `argMax(concurrent, minute)` — the value at the newest minute the delta layer
has produced. They answer "what is being watched *right now*".

Two caveats worth stating before a judge finds them:

- **`title` is not a key.** 2,773 titles are shared by 2–4 different `content_id`s, and 1,418 of those
  collisions span different categories. A title row therefore merges distinct assets. The arithmetic
  is right; the label is ambiguous.
- **`video_type` has three values, not two** — `vod`, `live`, and the **empty string** (1,089 catalog
  rows, 2.85% of events). Expect a blank third series.

---

## 4 · `SonyLIV time-window trend` — the required aggregation

```
 ┌────────────────────────────────────────────────────────────┐
 │ Rolling peaks — instantaneous vs 5 / 15 / 60-min windows   │
 └────────────────────────────────────────────────────────────┘
 ┌────────────────────────────────────────────────────────────┐
 │ Rolling time-weighted averages — 5 / 15 / 60-min           │
 └────────────────────────────────────────────────────────────┘
 ┌──────────────────────────┬─────────────────────────────────┐
 │ Tumbling 15-min          │ Tumbling 1-hour                 │
 │ (raw SQL tile)           │ (straight from cc_hour_agg)     │
 └──────────────────────────┴─────────────────────────────────┘
```

This dashboard answers the organiser's third core aggregation — *"time-window trend: window duration,
watermarking, refresh latency"*.

- **Rolling** panels use `RANGE` window frames, not `ROWS`. The delta layer stores a row only where
  concurrency *changes*, so "5 rows back" is not "5 minutes back". `RANGE` is defined on the values of
  the ordering column, so the frame is a real time window.
- **Tumbling 15-min** is the only **raw-SQL tile** on any dashboard. It calls a parameterised view:
  `SELECT window_start, peak, avg FROM sonyliv.v_cc_tumbling_total(win=15)`. The width must divide 60,
  or a bucket would straddle an hour boundary and its max would not be a real peak.
- **Tumbling 1-hour** does **no computation at all** — the hour *is* the storage grain of
  `cc_hour_agg`, so peak and average are stored columns. It pins the cube sentinels
  `platform='*' AND country='*' AND content_id=-1`. That is the payoff of hour-clipping
  ([ADR 0003](adr/0003-hour-clipped-interval-splitting.md)): a day peak reads 24 rows, not 1,440.

---

## 5 · `SonyLIV pipeline health` — ClickStack observing **us**

```
 ┌──────────────────┬──────────────────┬──────────────────────┐
 │ Watermark sealed │ Hour tier: last  │ Raw→sealed gap       │
 │ lag (s)          │ hour complete?   │ (min, abs)           │
 │ NEGATIVE = HEALTHY│ 1/0             │                      │
 └──────────────────┴──────────────────┴──────────────────────┘
 ┌──────────────────────────┬─────────────────────────────────┐
 │ Build-stage duration ms  │ Build-stage rows written        │
 ├──────────────────────────┼─────────────────────────────────┤
 │ Reconcile gate runs+ms   │ Query exceptions (flat 0)       │
 └──────────────────────────┴─────────────────────────────────┘
```

**The counter-intuitive one, and the reason this panel has a long title:**

```
  sealed_lag_s  =  raw_watermark − sealed_watermark

  NEGATIVE  ▸ the sealed tier LEADS the raw tier ▸ HEALTHY
            an interval's close delta lands at end-minute + 1, and `end`
            already carries TAIL_S = 60 s of grace, so on a caught-up model
            the sealed watermark sits up to ~2 minutes AHEAD of the newest
            event. Measured healthy steady state: −116 s.

  POSITIVE  ▸ the finalizer is genuinely behind.
```

Anything in `[−120 s, 0]` is caught up. A reader who assumes "negative lag = broken" will raise a
false alarm; that is why the sign convention is in the tile name.

The build-stage tiles read `system.query_log` and identify each stage by the **tables it touched**,
not by a label — e.g. the interval build is an `Insert` touching both `session_intervals` *and*
`ev_raw`, while the delta build touches `cc_minute_delta` and `session_intervals` but **not** `ev_raw`.
So the timings are what ClickHouse actually measured, never re-timed by a wrapper.

⚠ **Known defect:** `sonyliv observe` currently reports `reconcile pass=false` while the gate is green
(17,028 minutes, 0 mismatched). The Go parser expects the pre-`81c0161` five-column table; the gate now
emits `ord` and `scope`, so it parses zero rows and correctly calls "no evidence" a failure. Queued as
**Q1** in [WORKTREE_QUEUE.md](WORKTREE_QUEUE.md). The *dashboard* tiles above are unaffected — they read
`query_log` directly.

---

## 6 · `SonyLIV query cost` — what our queries *read*

```
 ┌──────────────────────────┬─────────────────────────────────┐
 │ Latency p95 / p50 / max  │ BYTES read (total + max single) │
 ├──────────────────────────┼─────────────────────────────────┤
 │ Rows read                │ Peak memory per bucket          │
 └──────────────────────────┴─────────────────────────────────┘
 ┌────────────────────────────────────────────────────────────┐
 │ Heaviest query shapes by bytes read  (table)               │
 └────────────────────────────────────────────────────────────┘
```

This dashboard exists because of one line in the problem statement: *"Judges will look at what your
queries read, not just how fast they return."* Latency alone is cheap to fake with a warm cache; bytes
read is not.

All tiles filter `type = 'QueryFinish' AND query_kind = 'Select'` and
`arrayExists(t -> startsWith(t, 'sonyliv.'), tables)` — so they measure **our** queries, not
ClickHouse's internal traffic. The heaviest-shapes table groups by `substring(query, 1, 80)`, which is
enough to identify a shape without exploding on parameter values.

---

## 7 · `SonyLIV user-level` — signed-in concurrency (added 2026-08-01)

The seventh dashboard, closing the required-aggregation list: **user-level distinct counts**.
URL: `https://hyperdx.clickhouse.cloud/dashboards/6a6e289aa561469a8f4ee7bd`.

```
 ┌────────────────────────────────────────────────────────────┐
 │ CAPTION — Users are a set, not a sum                       │  ← markdown tile
 └────────────────────────────────────────────────────────────┘
 ┌──────────────────┬──────────────────┬──────────────────────┐
 │ Peak users       │ Peak sessions    │ Multi-session gap at │  ← number tiles
 │ (uniqExact) 2,844│ (ACCURATE) 2,917 │ the peak minute: 73  │
 └──────────────────┴──────────────────┴──────────────────────┘
 ┌────────────────────────────────────────────────────────────┐
 │ Users vs sessions — the multi-session gap over time        │  ← raw-SQL join
 └────────────────────────────────────────────────────────────┘
 ┌──────────────────────────┬─────────────────────────────────┐
 │ Sessions per user ratio  │ Users by platform               │
 ├──────────────────────────┼─────────────────────────────────┤
 │ Users by country         │ Users by title (top 20)         │
 └──────────────────────────┴─────────────────────────────────┘

 FILTERS:  platform · country   (apply to the three per-dimension tiles)
```

| Tile | Reads | What it means |
|---|---|---|
| **Caption** | — | Users are `uniqExact(user_id)` per minute, never a sum of per-session deltas (one user can run several sessions — sum would count them once per session). Peaks not summable across dimensions |
| **Peak — concurrent users** | `User concurrency (minute)` → `max(concurrent_users)` | **2,844.** The uniqExact tier of [sql/45_user_concurrency.sql](../sql/45_user_concurrency.sql), exact not HLL (ADR 0005) |
| **Peak — concurrent sessions** | `Concurrency ACCURATE (minute)` | **2,917**, for contrast |
| **Multi-session gap** | raw-SQL join of the session and user total views, row at max sessions | **73** multi-session viewers at 10:56 |
| **Users vs sessions over time** | same raw-SQL join, `$__timeInterval` bucketed | The gap on every bucket — the two curves never touch |
| **Sessions per user** | same join, `max(sessions)/nullIf(max(users),0)` | 1.0257 at the peak (1.0 = nobody multi-streams) |
| **Users by platform / country / title** | `Session minutes (drilldown)` → `count_distinct(user_id)` | Set cardinality per bucket — at 1-min zoom it IS per-dimension user concurrency. **Cross-check:** by-country india = 2,844 at 10:56, agreeing with the uniqExact tier through a completely different path |

Two deliberate design points:

- The **`User concurrency by dimension` source is NOT charted per dimension** here: its grain is
  (platform, country, content_id, minute), so `max()` per platform is the max single *combination*
  (ANDROID_PHONE 308) — the same 285-vs-1,837 trap §8 records. Per-dimension users come from
  `count_distinct(user_id)` over session-minute rows instead (ClickHouse's `count_distinct` *is*
  `uniqExact` by default).
- The three **raw-SQL tiles carry a control-plane warning** about missing `$__filters` /
  `$__sourceTable`. Expected: they JOIN the session tier to the user tier, so no single `sourceId`
  applies. The Platform/Country dashboard filters therefore drive only the per-dimension tiles.

---

## 8 · Operating notes

| Trap | What happens | Fix |
|---|---|---|
| 🔴 **The Cloud service goes IDLE** | **every tile at once** shows *"Error loading chart, please check your query or try again later."* It looks exactly like a dead service or broken dashboards. It is neither | **wake it first:** `tools/ch -c "SELECT 1"` — takes ~30 s cold, then everything is warm. Make this **step 0** of the demo, above the time range |
| **Default time range** | every panel empty — data ends 2026-07-26 | set **2026-07-14 → 2026-07-26** *before* screen-sharing |
| **Summing `concurrent` across dimensions** | double counts: a session appears under several content_ids | use the `_total` sources, which re-merge the underlying states |
| **Users vs sessions** | the user sources expose `concurrent_users`, not `concurrent` | a tile selecting the wrong column silently returns nothing. Audited 2026-08-01: all 24 sources token-checked against live view columns, 0 mismatches; both user sources proven returning rows end to end ([evidence/clickstack/](../evidence/clickstack/)) |
| **Zooming out on the drilldown** | `count_distinct` per bucket stops meaning "concurrency" | quote it as "distinct sessions active in the bucket" |
| **Hindi appears four times** | un-normalised source values | real data; ADR 0011 exists but is not deployed |

**Everything is scripted.** `tools/clickstack-cloud.sh` provisions sources, dashboards and saved
searches over the Cloud control-plane API and is idempotent — a re-run **PUTs existing named sources
and dashboards** so the script stays the source of truth and stale select expressions or UI edits
cannot silently outlive it. Two operational
notes added 2026-08-01: **`CLICKSTACK_SKIP_APPLY=1`** runs the script control-plane-only (skips the
`sql/00_schema.sql`, `sql/10_intervals.sql` and `sql/87_viz.sql` migration/view step — required for
sessions that must not write to the graded database; the columns and views must already exist), and
**tile ids regenerate on every PUT**, so reference dashboards by
name/URL, never deep-link a tile.

One value the API cannot yield on an empty service is the `connection` id; get it once from the
clickstack MCP (`clickstack_list_sources` returns a top-level `connections` array even when `sources`
is empty) and put it in `.env` as `CLICKSTACK_CONNECTION_ID`.

## 9 · Provenance

Captured live via the clickstack MCP against the hosted service: `clickstack_list_sources` for the 24
sources and one connection, `clickstack_get_dashboard` for all seven dashboards and their 53 tiles. Every
panel name, source binding, value expression, aggregation and filter above was read from the running
configuration rather than from the provisioning script's intent — the two have drifted before. On
2026-08-01 **every tile was additionally executed signed-in** through HyperDX's query path
(`clickstack_query_tile`), with per-tile results in
[evidence/clickstack/tile-verification-2026-08-01.txt](../evidence/clickstack/tile-verification-2026-08-01.txt).
