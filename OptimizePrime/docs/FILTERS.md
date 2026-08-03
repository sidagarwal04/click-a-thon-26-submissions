# FILTERS — the filter-to-column map, with proof each one moves the curve

> **Summary:** The 12 dashboard filters the ClickStack candidate declares, each mapped to the exact
> dataset column and table that backs it, with MEASURED cardinality, example values, and a
> before/after peak proving the filter changes the concurrency curve. Measured on the **official
> unseen build** (`codex_official_green_20260802_075132`, 7,000,000 raw events), every number
> carrying a `query_id`. **11 of 12 filters move the curve. `Country` does not and cannot — the
> column is a single constant `'india'` in both the provided and the unseen file.** Two
> DATA_DICTIONARY entries are stale for the unseen day (`platform` distinct count; the `event_type`
> count table). Peak is NOT summable across dimensions — see §5 before adding any two rows here.

Requirement being answered: [SONYLIV_SUBMISSION_GUIDELINES.md](upstream/SONYLIV_SUBMISSION_GUIDELINES.md)
§2 — *"Your product must expose filters matching the dimensions available in the dataset… Document in
your README which dataset columns back each filter."* Filters must also apply to the concurrency curve
and work live, not as a screenshot.

---

## 0 · Where these numbers come from

| | |
|---|---|
| Database | `codex_official_green_20260802_075132` (local ClickHouse, container `ch`) |
| Dataset | official SonyLIV unseen release — `ch-hackathon-raw-data_surprise.csv`, sha256 `06897bd6…7775c95` |
| Rows | `ev_raw` 7,000,000 · `content_dim` 33,326 · `session_intervals` 159,426 |
| Provenance | built by the canonical pipeline; reconciled PASS against raw, `mismatched=0`, `max_abs_diff=0` — [evidence/unseen/official-20260802-codex-validation.txt](../evidence/unseen/official-20260802-codex-validation.txt) |
| Filter surface | `v_session_minutes` ([sql/87_viz.sql](../sql/87_viz.sql)) — one row per (active session, minute) |
| Filter declaration | [tools/clickstack-cloud.sh](../tools/clickstack-cloud.sh), dashboard *"SonyLIV drilldown — sessions & users"* |

**Nothing was written.** Every statement below is a `SELECT`. The graded `sonyliv` database was read
twice (§6) and never written.

### Why filters read `v_session_minutes` and not the delta table

`cc_minute_delta` is the serving path: it stores signed opens/closes and the curve is a running sum.
A running sum **cannot be filtered after the fact** — pinning a dimension changes which deltas
participate, so the sum must be rebuilt *before* the accumulation, which no chart builder can express.
`v_session_minutes` expands each active interval to its minutes, so `uniqExact(video_session_id)`
per minute stays correct under **any** combination of the 12 predicates.

The two agree exactly at the unfiltered peak, which is the check that licenses the substitution:

```sql
-- Serving path (delta + running sum)          query_id: flt-baseline-delta-852000
SELECT max(concurrent) AS peak, argMax(minute, concurrent) AS peak_minute
FROM v_concurrency_minute_delta_total;
-- → 23324 @ 2026-07-31 11:17:00

-- Filter surface (session-minute expansion)   query_id: flt-sm-baseline-peak-479000
SELECT max(c) AS peak, argMax(minute, c) AS peak_minute
FROM (SELECT minute, uniqExact(video_session_id) AS c FROM v_session_minutes GROUP BY minute);
-- → 23324 @ 2026-07-31 11:17:00
```

**Unfiltered baseline for every row below: peak `23,324` at `2026-07-31 11:17:00`, over `4,334`
minutes carrying traffic.**

---

## 1 · The 12 filters → the columns that back them

`v_session_minutes` column → where the value physically originates.

| # | UI filter name | Column in `v_session_minutes` | Physical origin | Raw or derived |
|---|---|---|---|---|
| 1 | Platform | `platform` | `ev_raw.platform` → `session_intervals.platform` | raw event column |
| 2 | Country | `country` | `ev_raw.country` → `session_intervals.country` | raw event column |
| 3 | Title | `title` | `content_dim.title` (join on `content_id`) | raw content column, joined |
| 4 | Content id | `content_id` | `ev_raw.content_id` → `session_intervals.content_id` | raw event column |
| 5 | App version | `app_version` | `ev_raw.app_version` → `session_intervals.app_version` | raw event column |
| 6 | Audio language | `audio_language` | `ev_raw.audio_language` → `session_intervals.audio_language` | raw event column |
| 7 | Subtitle language | `subtitle_language` | `ev_raw.subtitle_language` → `session_intervals.subtitle_language` | raw event column |
| 8 | Player version | `player_version` | `ev_raw.player_version` → `session_intervals.player_version` | raw event column |
| 9 | Video resolution | `video_resolution` | `ev_raw.extra['video_resolution']` → `session_intervals.extra_dimensions['video_resolution']` | **derived — map lookup** |
| 10 | Show name | `show_name` | `content_dim.extra['show_name']` (join on `content_id`) | **derived — map lookup, joined** |
| 11 | Video type | `video_type` | `content_dim.video_type` (join on `content_id`) | raw content column, joined |
| 12 | Category | `category` | `content_dim.category` (join on `content_id`) | raw content column, joined |

Schema types are unchanged from source: `content_id` is **`Int64`** (filter on `content_id = 2078157818`,
not `'2078157818'`); the other ten are `LowCardinality(String)` in the base tables and widen to `String`
through the view.

### How the event-side eight survive interval construction

An event dimension is not constant over a session — 93,205 unseen sessions change resolution mid-play.
`session_intervals` collapses each dimension to **one deterministic modal value per interval**
([sql/30_build_intervals.sql](../sql/30_build_intervals.sql) — `arraySort` over `countEqual`, ties
broken by value, so it is reproducible). `v_session_minutes` then collapses a session that has two
intervals touching the same minute to the interval with the later start. That makes every
(session, minute) cell occur exactly once, which is what allows dimension slices to be additive at a
single minute — verified below in §5.

---

## 2 · Cardinality and example values — MEASURED

`query_id: flt-card-all-274000` (cardinality and blanks) · `flt-top-values-392000`,
`flt-top-rest-884000`, `flt-top-video_type-820000`, `flt-top-category-791000`, `flt-top-audio-617000`
(example values, ranked by distinct sessions).

```sql
SELECT 'platform' AS col, uniqExact(platform) AS card, countIf(platform = '') AS blank_rows
FROM v_session_minutes
UNION ALL ...  -- one arm per filter column
```

| # | Filter | Distinct values | Blank-valued rows | Example values (top by distinct sessions) |
|---|---|---:|---:|---|
| 1 | Platform | 21 | 0 | `ANDROID_PHONE` (39,466 sess) · `JIO_ANDROID_TV` (23,665) · `SONY_ANDROID_TV` (12,996) · `IPHONE` (5,227) · `SAMSUNG_HTML_TV` (4,507) · `Web` (3,698) |
| 2 | Country | **1** | 0 | `india` — **and nothing else, across all 7,000,000 rows** |
| 3 | Title | 14,096 | 0 | `wekek ked` (27,722) · `wimim big` (2,539) · `dirir fad` (2,346) · `jewuw keh` (2,230) |
| 4 | Content id | 14,671 | 0 (no `0` ids) | `2078157818` (27,722) · `2078157680` (2,539) · `2078155114` (2,346) · `2078157821` (2,230) |
| 5 | App version | 138 | 0 | `6.34.8` (26,177) · `3.11.1` (18,810) · `6.25.1` (10,285) · `6.36.8` (9,351) |
| 6 | Audio language | 66 | 3,139 | `hin` (48,945) · `eng` (28,874) · `hin-hindi` (7,086) · `HIN` (5,107) · `unk` (3,880) · `eng-english` (3,193) |
| 7 | Subtitle language | 12 | 3,218 | `UNK` (74,342) · `off` (10,356) · `OFF` (7,296) · `UND` (4,942) |
| 8 | Player version | 97 | 1,630 | `1.8.2` (83,029) · `1.1` (5,426) · `3.29.71_adE` (3,959) · `3.33.60_ADE` (3,151) |
| 9 | Video resolution | 1,485 served (2,071 raw spellings) | 3,156 | `Auto-1280*720` (18,506) · `1920*1080` (16,033) · `NA` (8,303) · `1080*1920` (7,500) |
| 10 | Show name | 360 | 0 | `ggdkb` (27,858) · `bjdjb` (3,157) · `djbdb` (2,815) · `gdckb` (2,599) |
| 11 | Video type | 3 | 0 | `vod` (64,814) · `live` (34,738) · `(blank)` (3,470) |
| 12 | Category | 84 | 0 | `cdbgg` (28,347) · `ddddd` (4,858) · `cgdgn` (3,017) · `bhcfm` (2,934) |

Three things a judge will notice, stated here rather than discovered:

- **`audio_language` shows Hindi four ways** — `hin`, `HIN`, `hin-hindi`, `hin-Hindi`. Real
  un-normalised source data, not a panel bug. Normalisation exists
  ([ADR 0011](adr/0011-normalise-filter-dimensions-at-query-time.md)) and is deliberately not applied
  to the filter surface, because collapsing them would silently change a number judges may reconcile
  against the raw file.
- **`video_resolution` serves 1,485 of 2,071 raw spellings** (`flt-res-served-004000` and
  `flt-dyn-profile-233000`). The difference is spellings that only ever appear on events outside a
  modelled active interval — background, paused or post-end telemetry — which by definition contribute
  no foreground concurrency.
- **`title` is not a key.** 2,759 titles are shared by more than one `content_id`
  (`flt-title-collide-175000`). Filters #3 and #4 return identical curves below only because the
  chosen title `wekek ked` happens to resolve to exactly one `content_id`
  (`flt-title-check-804000` → 1). Prefer `content_id` when a number must be exact.
- **`video_type` / `category` / `title` / `show_name` carry a `(blank)` and an `(unknown)` sentinel.**
  `(unknown)` means no catalog row matched; `(blank)` means the catalog row exists with an empty
  value. On the unseen day there are **0 unknown-catalog rows** — every used `content_id` joined —
  so only `(blank)` appears.

---

## 3 · PROOF: each filter moves the curve

One query per filter, one `query_id` per measurement, same shape for all twelve:

```sql
SELECT max(c)                                          AS filtered_peak,
       argMax(minute, c)                               AS filtered_peak_minute,
       maxIf(c, minute = toDateTime('2026-07-31 11:17:00')) AS at_unfiltered_peak_minute,
       count()                                         AS minutes_with_traffic
FROM (
  SELECT minute, uniqExact(video_session_id) AS c
  FROM v_session_minutes
  WHERE <filter column> = <value>       -- the only line that changes
  GROUP BY minute
);
```

Baseline row (`WHERE 1 = 1`, `query_id flt-peak-UNFILTERED-448000`): peak **23,324** @
`2026-07-31 11:17:00`, **4,334** minutes with traffic.

The **Δ vs 23,324** column is not hand-computed either — it is a single measured query over all
twelve predicates, `query_id: flt-deltapct-847000`.

| # | Filter | Value applied | Filtered peak | Peak minute | Peak minute moved? | Value at 11:17 | Minutes with traffic | Δ vs 23,324 | Moves the curve? | query_id |
|---|---|---|---:|---|---|---:|---:|---:|---|---|
| 1 | Platform | `ANDROID_PHONE` | 7,159 | 2026-07-31 11:17 | no | 7,159 | 3,336 | **−69.3%** | ✅ yes | `flt-peak-platform-654000` |
| 2 | Country | `india` | **23,324** | 2026-07-31 11:17 | no | **23,324** | **4,334** | **0.0%** | ❌ **NO — see §4** | `flt-peak-country-539000` |
| 3 | Title | `wekek ked` | 9,143 | 2026-07-31 **11:16** | **yes** | 8,829 | 493 | **−60.8%** | ✅ yes | `flt-peak-title-457000` |
| 4 | Content id | `2078157818` | 9,143 | 2026-07-31 **11:16** | **yes** | 8,829 | 493 | **−60.8%** | ✅ yes | `flt-peak-content_id-445000` |
| 5 | App version | `6.34.8` | 4,922 | 2026-07-31 11:17 | no | 4,922 | 2,996 | **−78.9%** | ✅ yes | `flt-peak-app_version-502000` |
| 6 | Audio language | `hin` | 11,801 | 2026-07-31 **10:32** | **yes** | 10,895 | 3,313 | **−49.4%** | ✅ yes | `flt-peak-audio_language-957000` |
| 7 | Subtitle language | `UNK` | 18,257 | 2026-07-31 11:17 | no | 18,257 | 3,505 | **−21.7%** | ✅ yes | `flt-peak-subtitle_language-003000` |
| 8 | Player version | `1.8.2` | 18,958 | 2026-07-31 11:17 | no | 18,958 | 3,597 | **−18.7%** | ✅ yes | `flt-peak-player_version-452000` |
| 9 | Video resolution | `1920*1080` | 5,289 | 2026-07-31 **10:32** | **yes** | 5,043 | 367 | **−77.3%** | ✅ yes | `flt-peak-video_resolution-497000` |
| 10 | Show name | `ggdkb` | 9,179 | 2026-07-31 **11:16** | **yes** | 8,863 | 598 | **−60.6%** | ✅ yes | `flt-peak-show_name-636000` |
| 11 | Video type | `live` | 10,778 | 2026-07-31 **11:16** | **yes** | 10,500 | 732 | **−53.8%** | ✅ yes | `flt-peak-video_type-848000` |
| 12 | Category | `cdbgg` | 9,317 | 2026-07-31 **11:16** | **yes** | 8,996 | 603 | **−60.1%** | ✅ yes | `flt-peak-category-908000` |

Two independent signals of a genuinely different curve, not just a smaller one:

- **The peak minute itself moves** for 7 of the 12. `audio_language = 'hin'` and
  `video_resolution = '1920*1080'` peak at **10:32**, 45 minutes before the unfiltered peak — Hindi
  and 1080p demand crest during the ramp, not at the top. That is a shape change no rescaling
  reproduces.
- **The support shrinks.** `minutes_with_traffic` falls from 4,334 to as few as 367
  (`video_resolution`), so the filtered series is non-zero over an entirely different time domain.

### The curve has visible peaks and ramps

`query_id: flt-curve-sample-851000` — peak-of-each-20-minute-bucket over the event window, total
against two filters, showing the ramp, the crest and the collapse:

```sql
SELECT toStartOfInterval(minute, INTERVAL 20 MINUTE) AS t,
       max(total) AS total_peak, max(live) AS live_peak, max(android) AS android_peak
FROM (
  SELECT minute,
         uniqExact(video_session_id)                                AS total,
         uniqExactIf(video_session_id, video_type = 'live')         AS live,
         uniqExactIf(video_session_id, platform = 'ANDROID_PHONE')  AS android
  FROM v_session_minutes
  WHERE minute >= '2026-07-31 09:00:00' AND minute < '2026-07-31 13:00:00'
  GROUP BY minute
) GROUP BY t ORDER BY t;
```

| bucket start | total | `video_type='live'` | `platform='ANDROID_PHONE'` |
|---|---:|---:|---:|
| 09:00 | 43 | 7 | 33 |
| 09:20 | 60 | 7 | 48 |
| 09:40 | 78 | 11 | 53 |
| 10:00 | 127 | 33 | 90 |
| 10:20 | 22,708 | 8,643 | 6,241 |
| 10:40 | 22,830 | 9,644 | 6,733 |
| **11:00** | **23,324** | **10,778** | **7,159** |
| 11:20 | 21,920 | 9,349 | 6,145 |
| 11:40 | 3 | 0 | 1 |
| 12:00 | 1 | 0 | 0 |

The three series ramp, crest and fall together but at visibly different amplitudes — the filtered
curves are **not a constant fraction** of the total. `video_type = 'live'` climbs from 26.0% of the
total at 10:00 to 38.1%, 42.2% and 46.2% as the event peaks (`query_id: flt-liveshare-298000`), so
the filtered curve is a genuinely different shape, not the total rescaled.

---

## 4 · ❗ The filter that does NOT move the curve: **Country**

**`Country` is a dead filter on this dataset, and it is dead by the data, not by our code.**

`country` has exactly **one distinct value** — `'india'` — in every row of both files:

| Source | Rows | Distinct `country` | query_id |
|---|---:|---:|---|
| unseen `ev_raw` (7M events) | 7,000,000 | 1 (`india`) | `flt-country-raw-552000` |
| unseen `session_intervals` | 159,426 | 1 (`india`) | `flt-country-si-228000` |
| unseen `v_session_minutes` | 1,370,363 | 1 (`india`) | `flt-country-vals-774000` |
| **graded `sonyliv.ev_raw` (provided file)** | 905,558 | 1 (`india`) | via `clickhouse` MCP, read-only |

Applying `WHERE country = 'india'` therefore returns the identity: peak **23,324**, same peak minute
`2026-07-31 11:17:00`, same **4,334** minutes of traffic — byte-for-byte the unfiltered curve
(`flt-peak-country-539000` vs `flt-peak-UNFILTERED-448000`).

**Do not quietly drop it, and do not claim it works.** The honest position, and the one this repo
takes:

- The guidelines ask for filters matching *"the dimensions available in the dataset"*, and name
  **geo/region** as an example. `country` is the dataset's only geo column, so exposing it is the
  correct mapping — the requirement is satisfied at the mapping level.
- It is nonetheless a **no-op on the concurrency curve**, and the requirement that filters *"actually
  alter"* the curve is **not** met by this one. Eleven of twelve meet it; this one cannot, because a
  single-valued column has no second slice to show.
- The dashboard keeps the control **with its single value visible**, so a judge sees `india` and
  immediately understands the dataset is single-geo, rather than seeing a geo filter absent and
  wondering whether we missed the dimension.

If a future release ships multi-country data, this filter starts working with zero code change — the
column, the view and the control are already wired.

---

## 5 · ⚠ Peak is NOT summable across dimensions

Nothing in §3 may be added together. Each filtered peak is the maximum of *its own* series, and the
sub-peaks land at **different minutes** — that is precisely what §3 measured. Summing them overstates
the true peak:

`query_id: flt-notsummable-278000`

| Grain | Σ of per-value peaks | True peak | Overstatement |
|---|---:|---:|---:|
| `platform` (21 values) | 24,028 | 23,324 | **+3.0%** |
| `video_type` (3 values) | 25,358 | 23,324 | **+8.7%** |
| `content_id` (14,671 values) | 41,326 | 23,324 | **+77.2%** |

What *is* additive is the **per-minute slice at a fixed minute** — because `v_session_minutes` makes
each (session, minute) cell unique, the slices at 11:17 partition the 23,324 exactly (verified in
[evidence/unseen/official-20260802-codex-validation.txt](../evidence/unseen/official-20260802-codex-validation.txt):
`total 23,324 = sum(resolution slices) 23,324 = sum(show slices) 23,324`). Peak is also summable
across *time* after hour-clipping ([ADR 0003](adr/0003-hour-clipped-interval-splitting.md)). Across
dimensions it is not. See [ARCHITECTURE.md](ARCHITECTURE.md) rule 1.

---

## 6 · What exists in the data but is NOT a filter

Judges will diff this section against [DATA_DICTIONARY.md](DATA_DICTIONARY.md). Every column in the
two source files is accounted for.

### `ev_raw` — the 15 columns

| Column | Exposed as a filter? | Why not |
|---|---|---|
| `platform`, `country`, `content_id`, `app_version`, `audio_language`, `subtitle_language`, `player_version` | ✅ filters 1, 2, 4, 5, 6, 7, 8 | — |
| `extra['video_resolution']` | ✅ filter 9 | — |
| `video_session_id` | ❌ | It is the **measure**, not a dimension — `uniqExact(video_session_id)` *is* the curve. 108,486 values; a filter would select one line. |
| `user_id` | ❌ | The measure of the user-level curve (`uniqExact(user_id)`, 82,958 values). Exposed as a *metric* on the drilldown and user-level dashboards, never as a predicate. |
| `event_timestamp` | ❌ | The **time axis**. Driven by the dashboard time-range picker, which is a filter in every practical sense. |
| `event_type` | ❌ | 7 values (`VideoHeartbeat`, `VideoSessionStart`, `VideoPlay`, `VideoSessionEnd`, `AppBackgrounded`, `AppForegrounded`, `VideoError`). **Deliberately not a filter**: it is an input to the model, already consumed to decide which minutes are foreground-active. Filtering the curve by it would mean "concurrency among heartbeat events", which is not a concurrency. `flt-evtype-unseen-848000` |
| `event` | ❌ | 48 sub-event names under those types. Same reason — model input, notably `pause`/`resume`. `flt-unexposed-413000` |
| `session_start_epoch` | ❌ | Stored, never modelled ([DATA_DICTIONARY](DATA_DICTIONARY.md)); the derivation takes run starts from event timestamps. Filtering on it would filter on a field the answer does not depend on. |
| `extra` (whole map) | ⚠ partly | Only `video_resolution` is promoted to a named filter, because that is the only key present. Any *future* key is queryable the moment it lands, with no schema change, via `v_dynamic_dimension_values` / `extra_dimensions['<key>']`. |

### `content_dim` — the 6 columns

| Column | Exposed as a filter? | Why not |
|---|---|---|
| `title`, `content_id`, `video_type`, `category`, `extra['show_name']` | ✅ filters 3, 4, 11, 10 | — |
| `extra` (whole map) | ⚠ partly | Only `show_name` is present; future keys reachable via `v_dynamic_content_dimension_values`. |

### Modelled dimensions that exist but are not filters

| Column | Table | Why not a filter |
|---|---|---|
| `is_open` | `session_intervals` | 59,361 of 159,426 intervals are still open (`flt-isopen-219000`). This is the **provisional/final** distinction, surfaced as a *watermark label* on the curve ([ADR 0029](adr/0029-provisional-and-final-buckets-labelled-off-the-watermark.md), [LIVE_INTERVALS.md](LIVE_INTERVALS.md)) rather than a user-togglable predicate — hiding open intervals would silently under-report the live edge by −14.8%. |
| `interval_start` / `interval_end` | `session_intervals` | Internal to the model; expanded into the `minute` axis. |
| `build_version` | `session_intervals` | Build bookkeeping ([ADR 0034](adr/0034-generation-pinned-serving-surface.md)), not a data dimension. |

### Filters backed by something DERIVED rather than a raw column — the full list

Only **two** of the twelve, and both are honest map lookups over a losslessly retained source column,
not a computed or inferred value:

| Filter | Derivation | Note |
|---|---|---|
| **9 · Video resolution** | `extra['video_resolution']` — an **`ALIAS` column** on `ev_raw`, and `extra_dimensions['video_resolution']` on `session_intervals` (also `ALIAS`). `v_session_minutes` reads the map directly. | The unseen file's new raw column. It is not in the fixed schema because it did not exist in the provided file; the `extra` map caught it losslessly. Verified `ALIAS` in `system.columns`: `flt-alias-check-850000`. Named column and map lookup agree exactly (5,043 = 5,043 at the peak minute, per the codex validation evidence). |
| **10 · Show name** | `content_dim.extra['show_name']` — likewise an `ALIAS` column. | The unseen content file's new column. Same mechanism, same verification (8,863 = 8,863 at the peak minute). |

The other ten are **first-class named columns** in `ev_raw` or `content_dim`. Three of them
(`title`, `video_type`, `category`) plus `show_name` reach the curve through a `LEFT ANY JOIN
content_dim FINAL` on `content_id` — that is a join, not a derivation, and it is exact: **0 orphan
content IDs** on the unseen day (`flt-orphans-046000`).

---

## 7 · DATA_DICTIONARY cross-check — what agrees, what is stale

Every claim in [DATA_DICTIONARY.md](DATA_DICTIONARY.md) touching a filter dimension was re-measured
against the official unseen build.

### Agrees ✅

| Dictionary claim | Measured | query_id |
|---|---|---|
| raw rows / sessions / users = 7,000,000 / 108,486 / 82,958 | exact match | `flt-unexposed-413000` |
| content rows 33,326 · used content IDs 15,094 · orphans 0 | exact match | `flt-content-usage-950000`, `flt-orphans-046000` |
| raw resolution spellings 2,071 · blank rows 15,961 | exact match | `flt-blankres-147000` |
| `content_id` is **`Int64`**, not `UInt64` | confirmed | `flt-sm-schema-112000` |
| `video_resolution` is a String **`ALIAS`** of `extra['video_resolution']` | confirmed on `ev_raw` **and** `session_intervals` | `flt-alias-check-850000` |
| `show_name` exposed as `extra['show_name']` | confirmed — genuine `ALIAS` on `content_dim` | `flt-alias-check-850000` |
| `event_type` enum is exactly those 7 values | confirmed, all 7 present | `flt-evtype-unseen-848000` |

### Disagrees — three findings ⚠

**1. `platform` "· 10 distinct" is stale for the unseen day.**
The dictionary's raw-events table annotates `platform` as *"filter dimension · 10 distinct"* with no
file qualifier. Measured:

| File | Distinct `platform` |
|---|---:|
| provided file (`sonyliv.ev_raw`, 905,558 rows) | **10** |
| **official unseen (`ev_raw`, 7,000,000 rows)** | **21** |

`query_id: flt-platform-card-926000` (unseen) and a read-only `sonyliv` query via the `clickhouse`
MCP (provided). The count is right for the provided file and wrong for the day we are submitting
against. **Suggested fix:** `filter dimension · 10 distinct in the provided file, 21 in the official
unseen release`.

**2. `country` "only 1 value in the provided file" understates the problem.**
The qualifier *"in the provided file"* implies the unseen release might differ. It does not:
`country` is the constant `'india'` across all 7,000,000 unseen rows too
(`flt-country-raw-552000`). Because this is the single fact that makes filter #2 a no-op, the
qualifier is actively misleading in a submission. **Suggested fix:** `only 1 value (india) in BOTH
the provided file and the official unseen release — see FILTERS.md §4`.

**3. The `event_type` "measured counts" table is the provided file, not the unseen release.**
The dictionary's per-`event_type` count table sums to 905,558 — the provided file — under a heading
that reads *"with measured counts"* with no file named. The unseen distribution is materially
different (`flt-evtype-unseen-848000`):

| event_type | dictionary (provided) | share | **official unseen** | share |
|---|---:|---:|---:|---:|
| `VideoHeartbeat` | 843,600 | 93.16% | **6,736,343** | **96.23%** |
| `VideoSessionStart` | 10,880 | 1.20% | **83,198** | 1.19% |
| `VideoPlay` | 10,883 | 1.20% | **73,928** | 1.06% |
| `VideoSessionEnd` | 10,881 | 1.20% | **70,955** | 1.01% |
| `AppBackgrounded` | 14,700 | 1.62% | **19,981** | **0.29%** |
| `AppForegrounded` | 14,321 | 1.58% | **11,932** | **0.17%** |
| `VideoError` | 293 | 0.03% | **3,663** | 0.05% |

The shape change is worth stating rather than hiding: background/foreground markers are **9× rarer
by share** on the unseen day (1.62%/1.58% → 0.29%/0.17%), and `AppForegrounded` no longer even
roughly balances `AppBackgrounded` (11,932 vs 19,981 — 40% unpaired). The model does not depend on
them pairing (trap 1, `query_id: flt-fgbg-809000`), which is why the accurate curve still reconciles at `max_abs_diff = 0` — but
a judge comparing the two files will see this, and the dictionary should label which file each count
table describes.

**Not a disagreement, but note:** [CLICKSTACK_DASHBOARDS.md](CLICKSTACK_DASHBOARDS.md) states
*"2,773 titles are shared by 2–4 different `content_id`s"*. On the unseen release the figure is
**2,759** (`flt-title-collide-175000`). The 2,773 is correct for the provided file; the claim just
needs its file named.

---

## 8 · Reproducing every number here

```bash
DB=codex_official_green_20260802_075132

# any single row of §3
docker exec -i ch clickhouse-client --database "$DB" --use_query_cache 0 --query "
  SELECT max(c) AS filtered_peak, argMax(minute, c) AS filtered_peak_minute,
         maxIf(c, minute = toDateTime('2026-07-31 11:17:00')) AS at_unfiltered_peak_minute,
         count() AS minutes_with_traffic
  FROM (SELECT minute, uniqExact(video_session_id) AS c
        FROM v_session_minutes WHERE platform = 'ANDROID_PHONE' GROUP BY minute)"

# the evidence trail for any query_id quoted above
docker exec -i ch clickhouse-client --query "
  SELECT query_id, query_duration_ms, read_rows, formatReadableSize(read_bytes) AS read,
         formatReadableSize(memory_usage) AS mem
  FROM system.query_log
  WHERE query_id LIKE 'flt-%' AND type = 'QueryFinish' ORDER BY event_time"
```

### Cost of a filtered curve

From the same build, one warm run with the query cache disabled
([evidence/unseen/official-20260802-codex-validation.txt](../evidence/unseen/official-20260802-codex-validation.txt)):

| Query | Latency | read_rows | Read | Memory |
|---|---:|---:|---:|---:|
| total 24 h curve (promoted delta path) | **15 ms** | 139,925 | 1.60 MiB | 769 KiB |
| `video_resolution = '1920*1080'` 24 h curve | 1,310 ms | 192,752 | 18.12 MiB | 750 MiB |
| `show_name = 'ggdkb'` 24 h curve | 450 ms | 192,752 | 14.79 MiB | 411 MiB |
| both filters combined | 1,727 ms | 192,752 | 18.82 MiB | 754 MiB |

Read honestly: the **unfiltered** curve is served from the promoted delta tier and is fast. The
filtered curves take the generic exact-filter fallback over `v_session_minutes`, which is correct on
7M events and interactive, but memory-heavy — it is not evidence of production-scale latency for
arbitrary future dimensions. The promotion path for a dimension that earns it is
[sql/40_deltas.sql](../sql/40_deltas.sql)'s fixed delta key.

---

## 9 · For the README

The guidelines require the **README** to map filters to columns. The minimum it must carry is the
table in §1 plus one line naming the dead filter; §3's proof table is what makes the claim credible.
Suggested README wording:

> The product exposes 12 filters, all backed by columns in the SonyLIV dataset and all applied to the
> concurrency curve. `docs/FILTERS.md` maps each filter to its exact column and table, with measured
> cardinality and a before/after peak proving the filter changes the curve. Eleven of the twelve move
> the curve; **`Country` provably cannot — the column holds the single value `india` in both the
> provided and the official unseen file** — and we say so rather than hide the control.
