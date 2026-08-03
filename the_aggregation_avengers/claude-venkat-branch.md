# `feature-venkat` — branch handoff

**For:** anyone (human or AI) picking up this branch cold.
**Branch:** `feature-venkat`, forked from `ranga/prd`. `ranga/prd` is untouched.
**Owner:** Venkat · **Scope:** started as the silver layer; now covers **bronze → silver → gold → API → dashboard**, all running against live ClickHouse Cloud.

> Architecture overview: [`CLAUDE.md`](CLAUDE.md). This file is the *branch* record — what was found, what was decided, what has been superseded, and every bug worth not rediscovering.

---

## Where this stands

| | |
|---|---|
| **Done and running live** | bronze → silver → gold in ClickHouse Cloud · Express API · React dashboard |
| **Verified** | 2,882 peak agreed by Python-over-CSV, SQL, and the API independently |
| **Done and running live** | ClickStack: traced API + traced pipeline runner, HyperDX UI on `:8081` |
| **Blocked on others** | organisers' benchmark query set · two modelling decisions that are Ranganadh's call |

Nothing here is speculative: every number quoted was produced by running the thing, and every UI claim was checked by rendering it, not by the build passing.

---

## ⚠️ READ THIS FIRST — the concurrency model changed twice

The git history contains **two abandoned models** with elaborate machinery. Do not resurrect them.

| Model | Status |
|---|---|
| Three-mechanism (gap rule + pause markers + background markers) | ❌ **DEAD** |
| Heartbeat liveness with `ACTIVITY_TIMEOUT` + `GRACE` | ❌ **DEAD** |
| **Minute-presence** | ✅ **CURRENT** |

### The current model

> A minute counts for a session if it contains **at least one `event_type = 'VideoHeartbeat'` row.**

```sql
SELECT minute, uniqExactMerge(sessions) AS ccu
FROM gold_ccu_minute GROUP BY minute;
```

**No timeout. No grace. No gap rule. No state machine.** Jury ruling: heartbeats arrive every minute; `pause`/`resume`/`AppBackgrounded`/`AppForegrounded` must **not** gate CCU because those events go missing. They stay available for other analytics.

**The one surviving assumption — and a correction to how it was justified.**

The risk is a minute of genuine viewing containing no heartbeat: it is dropped, and CCU is understated *silently*. That risk is real. What was wrong was the argument used against it.

The old justification was cadence — "beats arrive every ~40s (p99 48.8s), so no active minute can be empty." **That argument does not hold on this data**, for two reasons found by executing it rather than reasoning about it:

- One beat instant emits **several rows** (`network-activity`, `buffer-health`, `video-resize` at the same millisecond). Row-to-row gaps are therefore mostly 0s, and any percentile over them is meaningless — a naive p50 comes out at 0s.
- Beatless minutes **exist anyway**: 47,008 of them, **25.7%** of all the minutes sessions span. A cadence percentile cannot see them at all.

So the failure mode is measured directly instead. Of the **5,701** gaps in heartbeat coverage inside a session, covering all 47,008 minutes, **every single one opens in a minute that also carries an explicit `pause` or `AppBackgrounded`** — 100%, zero unexplained. The user stopped watching; the pipeline is right to stop counting.

That is a **stronger** result than the cadence claim, not a weaker one: minute-presence is not *approximating* foreground viewing on this data, it *coincides* with it. It also explains the naive-vs-model gap — 189,429 minus 135,929 is largely those paused and backgrounded minutes.

Check 2 of `sql/90_verify.sql` asserts exactly this. If it drops below 100% on the unseen day, there are gaps nobody asked for and CCU is understated for those minutes.

### Current numbers — verified three independent ways

Python over raw CSVs, SQL in ClickHouse, and the API all agree exactly.

| Metric | Value |
|---|---|
| **Peak concurrent sessions** | **2,882** @ 2026-07-26 10:56 UTC |
| Peak unique users | 2,807 (75 sessions at peak are a repeat user) |
| Total watch-time | 135,929 session-minutes (2,265 h) |
| Naive (any open session) | 3,743 @ 10:59 · 189,429 min |

Superseded figures that appear in older commits — **do not quote**: 3,035, 3,115, 2,937.

---

## Infrastructure — live

**ClickHouse Cloud**, `mgznlu26zs.ap-south-1.aws.clickhouse.cloud:8443`, version 26.2.1.525, **timezone UTC** (so no bucket shift).

Credentials live in **`.env.local` at the repo root** (gitignored, `chmod 600`). `scripts/ch` and the API both read it. **Rotate the password after the hackathon** — it was pasted into a chat transcript.

```bash
scripts/ch 'SELECT 1'              # run a query
scripts/ch -f sql/20_silver.sql    # run a file, statement by statement
scripts/ch -l table FORMAT < data  # bulk load
```

### Tables

| Table | Rows | Size | Notes |
|---|---|---|---|
| `bronze_events` | 905,558 | 4.23 MiB | exactly as delivered, epoch-ms Int64 |
| `bronze_content` | 33,464 | — | as delivered |
| `silver_events` | 905,558 | 13.56 MiB | **row-complete**; 4,209 flagged as duplicates |
| `silver_content` | 33,464 | — | blank `video_type` → `vod` |
| `silver_session_dims` | 10,866 | — | pinned platform/user/content per session |
| `gold_ccu_minute` | 105,083 | 1.60 MiB | AggregatingMergeTree, `uniqExactState` |

Run order: `sql/00_bronze.sql` → `10_language.sql` → `20_silver.sql` → `30_gold.sql`.

---

## Gold — the serving layer

`gold_ccu_minute`, minute × dimension grain, fed by a materialized view off `silver_events`.

**Three design calls worth defending:**

- **`uniqExactState`, not `uniqState`.** The latter is HyperLogLog — approximate. Against a private ground-truth key that's a correctness risk for no benefit at this scale.
- **Why distinct-count at all.** `platform`/`content_id`/`video_type`/`category` are pinned per session, so their session sets are disjoint and a plain `sum()` would be exact. But `audio_language` is **not** pinned — 81% of sessions change it mid-session — so a session splits across rows in one minute and summing would double-count. `uniqExactMerge` is correct under *any* filter combination.
- **Peak is never stored.** `max()` does not decompose across a filter predicate, so gold holds the **series** and peak is `max()` after filtering.

**On not storing peaks — the concrete evidence.** Sum, count and distinct-count all decompose: the total is recoverable from the parts. `max()` does not, because different slices peak at different *minutes*. Over the 6-hour window on 26 Jul, the ten per-platform peaks add to **2,966**, but the true all-platform peak is **2,882** — an 84-session overstatement, because ANDROID_PHONE and IPHONE do not crest in the same minute. A pre-computed peak per dimension would therefore be wrong for every filter combination it wasn't computed for, and there are more combinations than rows. So gold stores the series and the API applies `max()` *after* the filter — the peak is always the peak of what you are actually looking at. This costs one `GROUP BY minute` and is why every number on the dashboard is filter-exact rather than filter-approximate.

*(This rationale used to be a panel in the UI. It was pulled: it is design reasoning, not analytics, and a live-ops dashboard is not where you argue with the reader. It belongs here and in the demo narration.)*

**Benchmark** (`scripts/benchmark.sh`) — every gold query paired with its silver equivalent:

| query | gold | silver | reads less |
|---|---|---|---|
| `peak_platform` | 11.21 MiB / 18ms | 56.20 MiB / 37ms | **5.0×** |
| `peak_platform_type` | 11.27 MiB / 18ms | 56.81 MiB / 36ms | **5.0×** |
| `top_content` | 17.86 MiB / 38ms | 61.54 MiB / 44ms | 3.4× |
| `hourly_rollup` | 18.67 MiB / 21ms | 62.62 MiB / 40ms | 3.4× |
| `series_2h` | 17.19 MiB / 21ms | 55.43 MiB / 36ms | 3.2× |

**Update handling — proven, not asserted.** Inserted one late heartbeat: the minute moved **2882 → 2883** through the MV. `system.mutations` showed only the one-time `ADD PROJECTION` DDL — **nothing from the data path**. Test row removed, gold rebuilt, dataset verified pristine.

---

## Silver — what it corrects

**Row-complete: 905,558 in, 905,558 out.** Nothing deleted; destructive judgements are flags so both the corrected and as-delivered readings survive.

| # | Correction | Scale |
|---|---|---|
| 1 | Exact duplicates **flagged**, not dropped | 4,209 (0.465%) |
| 2 | epoch-ms → `DateTime64(3)` | all |
| 3 | Languages → BCP 47 shortest subtag (`hin`→`hi`) | 41 → 15 |
| 4 | Content blank `video_type` → `vod` | 1,089 |
| 5 | Odd `content_id`s kept and surfaced, not deleted | 1 |
| 6 | `platform`/`user_id`/`content_id` pinned per session | 95 / 120 / 1 |
| 7 | `player_version` left as-is incl. blanks | 1,534 |

**Flags for downstream:**

```sql
is_heartbeat         -- event_type = 'VideoHeartbeat'. THE liveness signal.
is_state_marker      -- pause/resume/bg/fg. Other analytics ONLY, never CCU.
is_post_session_end  -- 802 events after VideoSessionEnd. Flagged, not decided.
is_duplicate         -- 1 = redelivery. Filter = 0 for corrected counts.
```

**Why dedup is explicit and not `ReplacingMergeTree`:** that engine collapses rows only on background merges, which are asynchronous and not guaranteed to run — `SELECT` without `FINAL` returns duplicates, and the count *changes* as merges land. Irreproducible results are worse than none.

**Why flag rather than delete:** duplication is **not** uniform — 5.103% on Mweb vs 0.078% on JIO_ANDROID_TV, a 65× spread concentrated in web/HTML-TV clients (retry behaviour). Leaving them in distorts cross-platform comparison. But the judges' ground truth may have been computed on raw data, and the key is private. Flagging retires both risks for one `UInt8`.

---

## App

**API** — `app/server`, Express on `:8787`. Credentials stay server-side; the browser sends filters, never SQL; dimension values are bound as ClickHouse `{name:Type}` parameters. Endpoints: `/api/{health,facets,series,summary,hourly,breakdown/:dimension}`.

Every response carries what the query **read**:

```json
{ "data": [...], "stats": { "ms": 85, "readRows": 95977, "readBytes": 19579308 } }
```

**Dashboard** — `app/web`, Vite + React + TS on `:5173`, 68 KB gzipped, **no chart library** (hand-rolled SVG, nothing from a CDN).

```bash
cd app/server && node src/index.js     # API
cd app/web    && npm run dev           # dashboard
```

**Where things live:**

```
app/server/src/clickhouse.js   query builder — whitelisted shapes, bound params
app/server/src/index.js        Express routes
app/web/src/App.tsx            layout, data fetching, theme + range state
app/web/src/theme.css          all design tokens, both themes, the wordmark
app/web/src/lib/api.ts         typed client + formatters
app/web/src/components/
  CcuChart.tsx                 hand-rolled SVG line chart, hover + drag-to-zoom
  TimeRange.tsx                quick picks + absolute picker, the TimeRange union
  Panels.tsx                   stat tiles, breakdown bars, filter bar, hourly, query cost
  Select.tsx                   portalled dropdown replacing the native <select>
```

**SonyLIV palette, computed not chosen.** Page black `#000`, cards `#141416`, wordmark in the logo gold `#F2C230` (see the gradient below). That gold is *only* ever text — at OKLCH L 0.834 it sits well outside the 0.48–0.67 band a dark-mode series colour has to occupy, so as a data mark it glows and reads inconsistently next to the blue. The series uses the nearest passing step of the same hue (`#BA8A15`). Both pairs went through the dataviz validator: dark `#BA8A15`+`#1668E3` on `#141416` and light `#8A6410`+`#1668E3` on `#FAFAF8`, all checks PASS, CVD ΔE 32.0 / 29.9 against a target of 8. **Dark is the default** — SonyLIV is a dark-first brand — with a header toggle; light is the alternate, its own selected steps rather than an inversion.

**Panels:** filter bar (time range + 5 dimensions, custom portalled dropdowns) → four stat tiles → minute-grain line chart with an optional distinct-users overlay → per-dimension peak bars (click to filter) → time rollup showing peak-vs-average per bucket.

**The rollup grain is the server's choice, and empty buckets are filled.** "By hour" is only right for a range measured in days — over a year it is 8,760 bars, a response nobody reads and a page that dies long before the data does. The server picks the coarsest grain that keeps the count near 24 (minute → 5m → 15m → hour → 3h → 6h → day → week), caps at 200 as a backstop, and reports which grain it chose so the panel can label itself. **Pagination would have been the wrong fix**: nobody pages through time buckets to see a shape — they narrow the range, which the picker and drag-to-zoom already do — and paging would make "peak" mean "peak on this page", which is the non-additivity trap all over again.

What that means at scale, measured rather than assumed:

| range | grain chosen | rows |
|---|---|---|
| 30 minutes | 5 minutes | 7 |
| 2 hours | 15 minutes | 9 |
| 6 hours | 30 minutes | 13 |
| 1 day | 3 hours | 9 |
| 1 week | 12 hours | 15 |
| 1 month | 2 days | 16 |
| **1 year** | **month** | **13** |
| 10 years | year | 11 |

Every range fits the card without scrolling. The target is **16 buckets, not 24**: at 24 the panel kept landing on ~25 bars, which scrolls at any sensible card height — and bars you scroll between are bars you cannot compare, which is the entire job of the panel. A day is 9 three-hour bars rather than 25 hourly ones: less resolution, more actually read. Minute detail is one panel up in the chart, and drag-to-zoom exists to go get it.

A year never returns 8,760 hourly rows — it returns **13 monthly** ones. Getting there took three fixes, each found by measuring rather than reasoning:

- **The ladder must be dense.** Each rung is the first grain that *fits*, so a gap between rungs is resolution thrown away: with `day` followed straight by `week`, a one-month range (30 buckets, barely over target) fell all the way to **5 bars**. The 30m/12h/2d/3d rungs catch those overshoots.
- **The ladder must reach the top.** Stopping at `week` left a year with nowhere coarser to go — 53 bars, a list you scroll, and bars you cannot compare because you cannot see them together. Bounding the panel height fixed the page layout but not the reading problem; `month`/`quarter`/`year` fixed the actual cause. Calendar units are not expressible in seconds (a fixed 2,629,800-second "month" drifts until a bar labelled Mar no longer starts in March), so the approximate seconds choose the rung and the SQL always uses the real `toIntervalMonth`/`Quarter`/`Year`.
- **The threshold needs two buckets of slack.** `to` is exclusive, so every range carries one extra minute — making a one-day range 24.02 hourly buckets. Compared strictly against 24 it tipped over and dropped a rung, rendering a day as **9 three-hour bars** instead of the 24 hourly ones anyone asking for "1d" expects.

The 520px scroll box survives purely as a backstop for a pathological range; no normal range reaches it.

**Two readability fixes that only showed up on screen:**

- **`2,882 / 197` did not say what either number was.** The legend explaining it sat at the bottom of the card, too far from the numbers to answer the question at the moment it is asked. There is now a column header (`peak / avg`) directly above them, and the legend spells out "busiest single minute" vs "average across the bucket".
- **The encoding fought the label.** Peak and average were two nested fills, and the *brighter* inner fill was the *smaller* number — so the eye went to the average while the label led with the peak. It is now a bullet: the bar is the peak, a 2px tick marks the average. A tick cannot be misread as a share of the bar.

Also: at 6h–12h grain the labels read `12:00 / 00:00 / 12:00 / 00:00…`, where no two bars can be told apart across days. Labels now carry the date from 6-hour grain upward.

**Card heights are `alignItems: start`, not stretched.** Stretch forces both bottom cards to the taller one's height, and their row counts are unrelated — a 2-row `video_type` breakdown beside a 16-bar rollup left ~700px of void *inside* a card. A ragged bottom edge reads as two panels of different size; a card two-thirds empty reads as broken. The breakdown also states `top 20 by peak` when it hits the server's limit, since `content_id` has thousands of values and would otherwise look like it had twenty.

Coarsening the DISPLAY must not coarsen the ANSWER: each bucket's peak is `max()` over the *minutes* inside it, so "Full range" at day grain still reports 2,882.

`WITH FILL` is load-bearing, not cosmetic. Without it a bucket with no data is simply absent, so the full range came back as **7 rows covering 14–26 Jul — 15–20 Jul missing entirely**, drawn as if those days were adjacent. It also made the bar count depend on sparsity rather than on the range (3 days → 25 bars, 12 days → 7), which is what made the behaviour look arbitrary. Quiet days are data: a day with zero concurrency must be a zero bar, not an absent one. Paired fix in the bar renderer — the `Math.max(pct, 1.5)` minimum width now applies only to non-zero values, or every empty bucket draws the same stub as a bucket with one session and the quiet days come back looking like faint traffic.

**The chart's x axis is positioned by TIME, not by index.** It was `x = i / (n-1)` — even spacing by *order*, which is an ordinal axis wearing a time axis's clothes. gold is sparse (21 Jul has 9 populated minutes, 22 Jul has 168), so a near-empty day got the same width as a busy one and the six days with no data at all vanished rather than showing as a gap. Every distance along the axis was meaningless. The axis is also drawn over the **requested window**, not over whichever samples exist: a range starting 15 Jul was rendering an axis starting 21 Jul, which read as the picker having been ignored when it had applied perfectly. Runs of missing minutes now break the path rather than drawing a straight line across them — a line across a hole asserts traffic that was never measured. Hover does a binary search on time instead of a proportional guess, which would land on the wrong minute wherever data is sparse.

**The chart has the same unbounded-range problem, with worse consequences** — one point per minute means a year is ~525,000 points in one SVG, and the browser does not error, it stops responding. Above 6,000 minutes of span the series is bucketed keeping each bucket's **maximum**, chosen over an average because max preserves the peak exactly. The cost is the troughs: the drawn curve becomes an upper envelope, reading slightly busier than reality between peaks. The tiles are unaffected — they come from `/summary`, always minute-exact — and the UI states the grain rather than leaving it to be discovered. The threshold is on span, not rows returned (rows are only knowable by running the query being guarded), and gold is sparse, so "Full range" does downsample today, to 3-minute grain.

**Time range — one piece of state, two ways to say it.** `TimeRange` is a union: `{mode:'rel', minutes}` or `{mode:'abs', from, to}`. Quick picks (30m/1h/3h/6h/12h/1d/3d/All) are a CloudWatch-style segmented row, and a Custom popover takes absolute start/end. Relative picks anchor to the **last minute in the data**, not wall-clock now — the data is a fixed historical day, so anchoring to now returns an empty chart for every preset.

**Drag on the chart to zoom.** The drag emits an absolute range into that same state, which is why a brush shows up in the control as "Custom" and why a quick-pick clears the zoom — two separate controls would have needed hand-syncing and would eventually have disagreed. Double-click zooms out. Crucially the drag is **not a client-side crop**: it re-filters, so the tiles, breakdown and hourly panels all follow the selection and the query-cost strip shows the read shrink with it (97,423 → 49,152 rows on a 6h → 31m zoom). Zooming is filtering here, not a viewport transform.

Everything in the picker is **UTC and says so**. The inputs are handled as literal wall-clock strings in the data's own timezone and never passed through `Date` parsing — a viewer in IST asking for 05:30 would otherwise silently get 00:00 of the data's day.

**The wordmark is the app's one gradient.** It matches the Liv mark's metal — warm highlight at the top left, brand gold through the middle, deep amber at the base, lit at 165° rather than a flat vertical:

```css
dark   linear-gradient(165deg, #F9DC82, #F2C230 30%, #EAB423 54%, #D1920F 78%, #A96D09)
light  linear-gradient(165deg, #C9A24A, #A97F1D 32%, #8A6410 58%, #6F4E0B)
```

Light mode is a re-lit copy, not the same values: the dark gradient's top stop `#F9DC82` is effectively invisible on `#FAFAF8`, and a wordmark that vanishes at its highlight is not a wordmark. It is `background-clip: text`, with `color: var(--brand)` set *first* and only made transparent inside an `@supports` block — set unconditionally, the word would disappear entirely anywhere clipping is unsupported, including Windows forced-colors mode, which drops background images but keeps `color`. A `forced-colors` block hands it `CanvasText`.

It stays the only gradient on purpose: on a data mark a gradient implies a magnitude that isn't there, so everything carrying a number is flat and in text ink.

No webfont anywhere: system sans at weight 800 with tightened tracking. A CDN request would be blocked and bundling a display face is not worth the bytes.

---

## Bugs found — the catalogue

Kept because several are non-obvious and two recur as a *class*.

### SQL (found by executing what had only been reasoned about)

1. **Alias shadowing, `silver_content`.** `toInt64(content_id) AS content_id` made `WHERE toInt64OrNull(content_id)` receive an Int64 → `ILLEGAL_TYPE_OF_ARGUMENT`. Fixed with an explicit subquery renaming the source.
2. **Alias shadowing, `series()`** — same class. `toString(minute) AS minute` made the `WHERE` compare String against DateTime → `NO_COMMON_TYPE`. ClickHouse already renders DateTime as a string in JSON, so the cast was never needed. **Watch for this pattern.**
3. **Validation query too narrow.** The no-duplicates check grouped on 4 columns and false-flagged a real pair: session `4C5EE22A…` emits `BufferStart` twice at the same millisecond, differing **only** in `subtitle_language` (`UNK`→`und` vs `OFF`→`zxx`) because the user toggled subtitles off at that instant. The dedup was right; the check was wrong. Now compares full row identity.
4. **`SharedAggregatingMergeTree` rejects `ADD PROJECTION`** (error 344) unless `deduplicate_merge_projection_mode` is set. Using `'rebuild'`; `'drop'` would silently discard projection parts on merge.
5. **`system.query_log` is PER-REPLICA on Cloud.** A plain read returns a partial, non-deterministic subset of a benchmark run. Use `clusterAllReplicas(default, system.query_log)`. This cost two confusing report passes.

### Dashboard (found only by rendering and looking — build and typecheck both passed)

6. **Blank page.** `StatTiles` called `.toLocaleString()` on `avg_ccu`, which is **null** when a filter matches no rows — SQL aggregates over an empty set return one row of *nulls*, not zero rows.
7. **Duplicate React keys.** The y-tick generator rounded *after* stepping, so a small max collapsed distinct steps into duplicate integers (`0, 1, 1, 2, 2`).
8. **Unreadable default view.** The dataset spans 12 days but 94% of events land on the last one, so the full range squashed the curve into a spike at the right edge. Added time-range presets anchored to the data's own last minute, defaulting to 6 hours.
9. **Native `<select>` popup** rendered at the macOS default size and in the OS *light* palette, ignoring font-size and dark tokens. Options can't be styled around this — rebuilt as `components/Select.tsx`, which also gained type-to-filter and keyboard nav.
10. **White band down the right in dark mode.** `body`'s background propagates to the canvas only for the initial containing block; any horizontal overflow falls back to `html`'s default white. Paint **both**.
11. **Dropdown clipped by the filter card.** `overflow-x` on an ancestor creates a clipping context an absolutely-positioned child cannot escape. Menu is now portalled to `document.body` with fixed positioning.
12. **`ReferenceError: cannot access 'close' before initialization`.** An effect referenced a `const` declared below it — `const` is not hoisted, so it's a temporal-dead-zone error at render time. **The type-checker does not catch this.**
13. **Content capped at 1240px** left most of a wide monitor empty. Raised to 1760 with fluid padding.
14. **ResizeObserver attached in `useMemo`.** `useMemo` runs *during* render, when the ref is still `null`, so the observer was never attached — width stayed at its initial 900 and the `viewBox` stayed `0 0 900 300` while the element rendered up to 1646px. SVG then stretched a 900-unit space to fill it, scaling every axis label and mark by up to **1.83×**. The chart looked oversized and misaligned with its card, and nothing in the console said so. **Must be `useEffect`.** This was the one behind several rounds of "the UI is still buggy".
15. **Stale index into a shrunk array.** Drag-to-zoom cut the series from 361 points to 51 while `hover` still held ~300, so `data[hover].ccu` read past the end and the page went blank. Hover and drag are *indexes*, and the array they index is replaced on every zoom, filter and range change. Fixed by clamping on read (the array can shrink between a mousemove and the render that consumes it) **and** clearing on `data` identity change, so no crosshair lingers over a curve it was never measured against.

**The class worth remembering:** 6, 7, 14 and 15 are all *state that outlived the data it described* — a null from an empty result set, a rounded step, a width, an index. TypeScript caught none of them. Every one surfaced by rendering the page and looking at it.

---

## Review of `ranga/ddl`

Ranganadh's `queries/ddl__backfill.sql` (branch `ranga/ddl`). Checked against real data.

### Two issues that would bite

**`content_id UInt32` cannot hold our data.** There is a negative content id:

```
content_id = -987654322,  title 'necec ceg'
toUInt32OrNull('-987654322') → NULL
```

That row silently becomes NULL or fails on load. Our silver uses `Int64` and keeps it, surfaced rather than deleted.

**`substring(lower(audio_language), 1, 3)` does not merge `jap`/`jpn`.** Verified:

| his output | ours | events |
|---|---|---|
| `jap` | `ja` | 1,374 |
| `jpn` | `ja` | 675 |

2,049 Japanese events split into two buckets. No string rule can merge them — it needs a curated alias map (`sql/dim_language_normalization.sql`). His approach also yields 3-letter codes rather than BCP 47.

Also absent: duplicate handling, and session-dimension pinning (the 95 platform-flipping sessions).

### Three things of his worth adopting

- **Compression codecs** — `T64`, `DoubleDelta`, `ZSTD(1)` on the right columns. Real wins we skipped; `DoubleDelta` on a monotonic `event_timestamp` especially.
- **`FixedString(64)`** for `user_id` / `video_session_id`. Verified safe — every id is exactly 64 hex chars.
- **Separate `bronze` / `silver` databases** rather than prefixed tables in one. Cleaner namespacing.

**Suggested merge:** keep our silver/gold logic and correctness handling, adopt his codecs and `FixedString(64)`, and settle `Int64` vs `UInt32` for `content_id` in his favour only if the negative id is confirmed droppable — which we decided it is not.

---

## Open items

**Next, in order:**

1. **Unseen-day dry run.** The pipeline has never been executed end-to-end on a file it had not already seen. `scripts/profile_dataset.py` → `scripts/run_pipeline.mjs` → `sql/90_verify.sql` should be rehearsed against a *withheld slice* of the provided day, so the first unrehearsed run is not the graded one.
2. **Merge with `ranga/ddl`** (codecs + `FixedString(64)`; see the review above).
3. **Browser-side spans**, to close the last leg of cross-system attribution. The API→ClickHouse half is instrumented; the browser→API half is still inferred rather than measured.

**Blocked on the organisers:**
- **Benchmark query set still absent** from their package. Our six shapes are inferred from the problem statement, and they determine whether the gold ordering key is optimal. Worth chasing directly.

**Decisions outstanding:**
- Do the 802 post-`VideoSessionEnd` events count? Flagged, not decided. *(Ranganadh)*
- Should a mid-session audio-track switch split interval attribution? 81% of sessions change `audio_language`.
- Merge strategy with `ranga/ddl` (above).

**Known gap:** the provided data has **zero open sessions** and **zero missing background markers**, so incremental-update handling can only be tested via the synthetic insert described above. Both cases appear only on the unseen day.

**Resolved, was listed as unverified:** a white band reported down the right in dark mode turned out to be **DevTools docked right in its light theme**, confirmed from a screenshot of the reporting machine — not a page bug. The `html`+`body` background fix (bug 10) was still correct and stays. Recording it because it cost a debugging pass and would otherwise get re-reported.

---

## ClickStack — built and running

```bash
scripts/clickstack.sh up        # start it (first run: create the account in the UI)
scripts/clickstack.sh status    # container + receivers + span count
scripts/clickstack.sh spans     # what has been recorded, by service
scripts/clickstack.sh trace     # the most recent full trace, nested
scripts/clickstack.sh down
```

HyperDX all-in-one in Docker. **UI at `http://localhost:8081`**, OTLP at `4418` — *not* the documented 8080/4317/4318, all three of which were already taken on the build machine (8080 by an unrelated node process, 4317/4318 by Docker Desktop's own collector). Credentials and the ingest key are in `.env.local`.

**Two traps, both of which fail silently:**

1. **A fresh container has NO OTLP receivers.** They are pushed to the bundled collector over OpAMP only after a team exists in the UI. Before that it accepts connections and drops everything — `otel_traces` stays empty with no error anywhere. Finish the UI setup first.
2. **ESM hoists every `import` above every body statement.** Writing `startTelemetry()` between imports loads `express` *unpatched*, so incoming HTTP spans never appear — while outgoing ClickHouse spans still do, which makes it look like it is working. `telemetry.js` therefore starts the SDK **at import time**, and is the first import in every entry point. Ordering is a property of the module graph, not a comment.

**What is instrumented, and what is deliberately not.** Not query latency, bytes or errors *as the point* — `system.query_log` already has all three at higher fidelity, and duplicating it is the "superficial inclusion" the rubric warns against. It is here for what query_log structurally cannot do:

| | |
|---|---|
| **Cross-system attribution** | one trace = browser → API → ClickHouse. A real one: `GET` 84.8ms → `clickhouse.query` 84.3ms → `POST` 83.7ms, so API overhead is ~1ms and the wait is the round trip. query_log sees only the innermost bar. |
| **Pipeline run evidence** | `scripts/run_pipeline.mjs` emits one trace per run, one span per stage and per statement, each with rows read/written. Evidence produced *by* the run — the only kind that proves it happened. |
| **Freshness lag** | event time → queryable time, as a histogram. query_log records when the INSERT ran, never how stale the row already was. |
| **A UI judges can open** | HyperDX. |

Query cost still rides along as span attributes because it is free to attach and makes a trace self-contained. It is not the reason this exists.

**Fail-open, always.** Collector down, never started, or `OTEL_SDK_DISABLED=true` → the API and pipeline behave exactly as before. An observability outage taking down the thing being observed would be an own goal on demo day.

---

## The pipeline runner and the verify stage

```bash
scripts/run_pipeline.mjs                  # every stage, traced
scripts/run_pipeline.mjs sql/90_verify.sql   # just the checks (read-only, safe)
```

`sql/90_verify.sql` is read-only and asserts **invariants, not numbers** — hard-coding 2,882 would turn a correct run on new data into a failure. Current state, all passing:

| check | result |
|---|---|
| `row_completeness` | 905,558 bronze = 905,558 silver |
| `beatless_minutes_explained` | 5,701 gaps / 47,008 minutes, **0 unexplained** |
| `gold_matches_silver` | 2,882 = 2,882 |
| `session_dims_pinned` | 0 split platform / user / content |
| `headline` | 2,882 @ 10:56 · avg 35.25 · 135,929 watch-minutes |

A FAIL verdict exits non-zero even though the SQL itself succeeded — a broken pipeline must not pass silently.

> **Do not run `sql/30_gold.sql` casually.** Its DDL is `IF NOT EXISTS`, but the backfill `INSERT` is not guarded: re-running duplicates gold's stored rows. `TRUNCATE gold_ccu_minute` first. (CCU itself would survive — merging identical `uniqExactState`s is idempotent — but storage and row counts would not.)

---

## Why ClickStack, in one paragraph

Worth keeping, because the question recurs. For the **SonyLIV data**, ClickStack adds nothing — that's business data, already in our tables. For **pipeline health**, `system.query_log` already covers query latency, bytes read and errors. ClickStack earns its place on exactly four things query_log cannot do:

- **Cross-system spans** — is a slow filter the browser, the API, or ClickHouse?
- **Freshness lag** — event time → queryable time (a scored NFR; query_log logs the INSERT, not the lag)
- **Agent traces**, if the agent gets built
- **A UI** for judges

Plus the decisive one: it is a scoring requirement, and the only option that doubles as the mandatory unseen-day evidence. **Instrument only those four** — pushing query latency into ClickStack when query_log already has it is the "superficial inclusion" the rubric warns will not count.

---

## Reproduce from scratch

```bash
# 1. Data (Git LFS — a plain fetch gives 132-byte stubs)
#    github.com/sidagarwal04/click-a-thon-2026/tree/main/SonyLiv/data

# 2. Validate the model assumption + data hygiene
python3 scripts/profile_dataset.py RAW.csv CONTENT.csv
#    >> OK. p99 = 48.8s < 60s

# 3. Build the pipeline
scripts/ch -f sql/00_bronze.sql
scripts/ch -l bronze_content CSVWithNames < CONTENT.csv
scripts/ch -l bronze_events  CSVWithNames < RAW.csv
scripts/ch -f sql/10_language.sql
scripts/ch -f sql/20_silver.sql
scripts/ch -f sql/30_gold.sql

# 4. Verify — expect 2,882 @ 2026-07-26 10:56, 135,929 watch-minutes
scripts/ch 'SELECT * FROM v_ccu_summary FORMAT Vertical'

# 5. Benchmark
scripts/benchmark.sh

# 6. Run the app
cd app/server && node src/index.js &
cd app/web    && npm run dev
```
