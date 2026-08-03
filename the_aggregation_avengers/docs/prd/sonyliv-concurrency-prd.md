# PRD — Foreground-Only Concurrency at Streaming Scale (SonyLIV track)

**Click-a-thon 2026 · ClickHouse**
Source problem: [SonyLiv/PROBLEM_STATEMENT.md](https://github.com/sidagarwal04/click-a-thon-2026/blob/main/SonyLiv/PROBLEM_STATEMENT.md) · Data dictionary: [SonyLiv/dataset_details.md](https://github.com/sidagarwal04/click-a-thon-2026/blob/main/SonyLiv/dataset_details.md) · Build guide: [SonyLiv/README_START_HERE.md](https://github.com/sidagarwal04/click-a-thon-2026/blob/main/SonyLiv/README_START_HERE.md) · Unseen-day spec: [SonyLiv/unseen_data/spec.md](https://github.com/sidagarwal04/click-a-thon-2026/blob/main/SonyLiv/unseen_data/spec.md)

Status: draft · Owner: team · Horizon: 24-hour hackathon

---

## 1. Problem summary

"How many people are watching right now?" is the most-asked question during a live event and one of the easiest to get wrong. The naive answer — count sessions whose `[start, end]` interval covers minute *M* — overstates the audience, because an open session is not a watching viewer. Users background the app, pause the player, lose the network, or simply stop emitting heartbeats while the session stays nominally open. Every minute of that inactive time inflates the concurrency curve, and the decisions made on that curve (ad load, capacity provisioning, content calls) inherit the error.

The real task is therefore two problems stacked:

1. **Semantics** — reconstruct the *truly active* (foreground, playing, heartbeating) intervals inside each session from an event stream where the state markers are unreliable. Per the data dictionary, `AppBackgrounded` / `AppForegrounded` are explicitly **not guaranteed** to arrive, so absence of a background event cannot be read as presence of foreground activity. Heartbeat presence (nominally every 60s) is the only signal that is actually load-bearing.
2. **Scale & serving** — compute minute-grain peak and average concurrency over those intervals, sliced by arbitrary dimension combinations, at dashboard latency, on a dataset framed as a scaled-down proxy for a petabyte-class problem. Exploding every session into per-minute rows is prohibitively large; recomputing interval overlap from raw history per query is prohibitively slow. And sessions are not static — open sessions keep growing as heartbeats arrive, so the serving layer must absorb updates incrementally rather than rebuild.

**Product one-liner:** a ClickHouse-native concurrency system that ingests raw playback events, derives foreground-only active intervals, and serves minute/hour/day peak-and-average concurrency with dimension filters in dashboard-grade latency, updating incrementally as open sessions evolve.

### 1.1 The non-obvious trap: peak is not additive

Average concurrency composes across time and dimensions; **peak does not**. If Android peaks at 10:05 and India peaks at 10:41, the peak for `Android AND India` may occur at a third minute entirely, and it is *not* derivable from either pre-computed peak. This forces a design rule: **pre-aggregate the per-minute concurrency series (which is additive in deltas), and compute peak as `max()` over that series at query time** — never pre-compute peak per dimension slice and hope to combine it. Any design that stores peaks instead of series will be wrong on filtered queries — and filtered queries are most of what a judge will ask for.

### 1.2 What is supplied

| Asset | Contents |
|---|---|
| [`ch-hackathon-raw-data.csv`](https://github.com/sidagarwal04/click-a-thon-2026/blob/main/SonyLiv/data/ch-hackathon-raw-data.csv) | ~905K event-level streaming events |
| [`ch-hackathon-content-data.csv`](https://github.com/sidagarwal04/click-a-thon-2026/blob/main/SonyLiv/data/ch-hackathon-content-data.csv) | ~33K titles with metadata |
| **Unseen day** | A fresh day of session data from the same universe — now specified, see §1.3 |

> Both CSVs are stored via Git LFS. Run `git lfs install && git lfs pull` before loading — an un-pulled checkout contains 130-byte pointer stubs, not data. A 1000-row head sample of each file is checked out at [`SonyLiv/data/samples/`](../SonyLiv/data/samples/) for schema work without the 232 MB download; §4.3 records what it showed.

**There is no benchmark query set and no ground-truth answer key.** Earlier drafts of this PRD assumed a fixed, scored question list with a private answer key; the problem statement no longer supplies either. Two consequences ripple through the whole document:

1. **We author the question set.** The scored output is now *"peak and average concurrency at minute, hour, and day grain, with dimension filters"* — a shape, not a list. We define the concrete query pack ourselves (FR-4), which means it must be broad enough to demonstrate the model rather than narrow enough to be tuned to.
2. **Correctness is spot-checked against raw events, so we can self-score.** Judges will recompute a sampled answer straight from the event rows and compare. That is a check we can run ourselves — and must (FR-9). A slow, obviously-correct brute-force recomputation over a narrow slice is now a *first-class deliverable*, not a debugging aid: it is the same test the judges will apply.

### 1.3 The unseen day is now specified

[`unseen_data/spec.md`](https://github.com/sidagarwal04/click-a-thon-2026/blob/main/SonyLiv/unseen_data/spec.md) is published. The data itself is sealed until release, but its shape is known — and it is not a scaled copy of the provided file:

| | Provided data | Unseen day |
|---|---|---|
| Events | 905,558 | **7,000,000** (~7.7×) |
| Span | ~11.8 days (§4.3, F0) | **1 day** — Jul 31, 2026 |
| Events/day | ~77K | **~7M (≈90×)** |
| Size | 232 MB | **~1.8 GB** |
| Delivery | Git LFS, in-repo | **Google Drive download** (too large for LFS) |
| Raw schema | 13 columns | **+`video_resolution`** |
| Content schema | 4 columns | **+`show_name`** |

Three design consequences, each of which changes work already planned:

- **Schema evolution is a requirement, not a hypothetical.** §4.2 previously noted that dimensions "may grow" as a caution. It has now happened, before we have written a line of DDL. Both new columns are declared filter dimensions, so the ingest → normalize → enrich → serve path must absorb an added column via `ALTER TABLE … ADD COLUMN` plus a config edit, with **no change to interval-derivation logic and no rebuild of the model**. If adding `video_resolution` means editing the delta pipeline, the design is wrong. This is a testable property: rehearse the ALTER on the provided data before release (Phase 6).
- **The density inversion is the real scale test.** 7.7× the rows is unremarkable; **~90× the events per day is not**. Concurrency is a per-minute overlap count, so it scales with *simultaneous* sessions, not total rows. Extrapolating from §4.3 (~83 events/session), the unseen day holds on the order of **~84K sessions inside a single day**, against 10,866 spread over 11.8 days. Peak concurrency will be orders of magnitude higher, minute buckets will be far denser, and any per-minute-per-session materialization we were tempted by at hackathon scale becomes exactly the failure the problem statement warns about. Nothing may be tuned against the sparse provided curve.
- **Open sessions probably reappear.** §4.3 (F4) found zero open sessions in the provided file — every session had a `VideoSessionEnd`. That file spans 11.8 days, so sessions cut by the export boundary are a rounding error. The unseen day is **one day**, sessions run a 714s median (p90 1,990s), and update handling is explicitly scored — so sessions still open at the day boundary are far more likely to be present, and possibly deliberately so. FR-6 must be genuinely working, not fixture-only.

The 1.8 GB Google Drive download is also a runbook step with a real wall-clock cost, under time pressure, on conference wifi. It belongs in the rehearsal (FR-8), not discovered at release.

---

## 2. Goals & non-goals

### Goals

| # | Goal | Success signal |
|---|---|---|
| G1 | Foreground-only correctness | Concurrency excludes backgrounded, paused, and heartbeat-gap periods, and **survives a raw-event spot-check** — our own recomputation harness (FR-9) agrees with the serving layer |
| G2 | Dashboard latency | Minute-grain filtered queries return fast, reading a serving layer — not rescanning raw events |
| G3 | Incremental updates | Open sessions and late-arriving heartbeats are absorbed without a full rebuild |
| G4 | Filter-friendliness | Platform, country, content, video type, category, app/player version, audio/subtitle language — plus `video_resolution` and `show_name` on the unseen day — at minute/hour/day grain |
| G5 | Defensible design | Written trade-off reasoning on representation, table layout, ordering keys, aggregation strategy — and behaviour at 100× |
| G6 | Unseen-day readiness | End-to-end run on sealed data with query logs/traces as evidence, at ~7M events/day |
| G7 | Ecosystem integration | Meaningful use of ClickStack, Langfuse, or LibreChat (see §8) |
| G8 | Schema tolerance | A new dimension column is absorbed by `ALTER` + config, with no edit to interval derivation and no model rebuild (§1.3) |

### Non-goals

Authentication, production deployment, a polished dashboard product, or a real frontend. A minimal concurrency-over-time visualization is sufficient to demo. AI is not required for the core problem and will not rescue a wrong or slow model.

### Explicit anti-goals (failure modes to design against)

- Pre-computing peak per dimension slice (see §1.1).
- Materializing one row per session per minute across all history — especially given the unseen day's ~90× daily event density (§1.3).
- Treating "no `AppBackgrounded` event seen" as proof of foreground.
- Any path where a late heartbeat triggers a full recompute of the day.
- Hand-computed unseen-day answers — these score zero.
- A hard-coded dimension list anywhere in the pipeline. Two columns already arrived late (§1.3); assume a third could.
- Shipping numbers we have not independently recomputed from raw events. With no answer key, the only correctness evidence we can produce is our own (FR-9).

---

## 3. Users & primary jobs

| User | Job to be done | Requirement it drives |
|---|---|---|
| Live-ops engineer | "Is concurrency dropping because the match ended, or because we're breaking?" | Minute-grain freshness; decline detection (§8) |
| Ad ops / monetization | "How many foreground viewers on CTV in India right now?" | Multi-dimension filters at low latency |
| Content team | "What was peak concurrency for this title, and when?" | Peak **and its timestamp**, per content |
| Capacity / SRE | "What's the peak for today so far, by platform?" | Peak over arbitrary ranges + grains |
| Judge | "Is it correct, fast, incremental, and well-reasoned?" | §9 evaluation mapping |

---

## 4. Data model of the input

### 4.1 Raw events — grain: one row per event

| Column | Role |
|---|---|
| `video_session_id` | Session identity; basis for session-level concurrency |
| `user_id` | Basis for user-level (deduplicated) concurrency |
| `content_id` | Join key to content metadata; filter dimension |
| `event_type` | One of `VideoSessionStart`, `VideoPlay`, `VideoHeartbeat`, `AppBackgrounded`, `AppForegrounded`, `VideoSessionEnd`, `VideoError` |
| `event` | The specific event under that type — **carries the playback-state markers**, see §4.3 |
| `event_timestamp` | **Event time** — the authoritative time axis. **Epoch milliseconds**, not a datetime string |
| `platform`, `country`, `app_version`, `audio_language`, `subtitle_language`, `player_version` | Filter dimensions |
| `session_start_epoch` | Session start (epoch ms), available on every row — useful for session-independent derivations |
| `video_resolution` | **Unseen day only** — filter dimension, absent from the provided file (§1.3) |

The data dictionary states heartbeat cadence is nominally **60 seconds** and that background/foreground markers are **best-effort**. §4.3 shows the first claim does not survive contact with the data. The unseen-day spec restates both unchanged, so the F2 correction (real cadence 40s) should be expected to hold there too — but re-measure it on arrival rather than assume (FR-8).

### 4.2 Content metadata — grain: one row per `content_id`

`content_id`, `title`, `video_type`, `category` — plus **`show_name` on the unseen day**. Small (~33K rows, and the unseen catalogue is the same order) → dictionary-friendly.

> The dictionary warned the real dataset is far larger and that dimensions may grow. That warning has already cashed in: the unseen day adds `video_resolution` to raw events and `show_name` to content (§1.3). The design must not hard-code the dimension list — treat this as demonstrated, not precautionary.

### 4.3 Full-dataset profile (Phase 0 findings)

Profiled over the complete files: **905,558 event rows / 10,866 sessions / 3,357 distinct played titles**, and **33,464 content rows**. This supersedes an earlier profile taken from a 1000-row head sample, which was unrepresentative in three places (noted below as *sample said X, full data says Y*). The samples remain at [`SonyLiv/data/samples/`](../SonyLiv/data/samples/) for quick schema work.

**F0 — The provided data spans ~11.8 days, not one day.** Event time runs **2026-07-14T15:43:58Z → 2026-07-26T11:30:04Z**. Median session duration is 714s (p90 1,990s). Partitioning and the "day" grain must be written against a multi-day range; the unseen day is a *fresh* day from the same universe, so nothing may assume a single-day window.

**F1 — `VideoHeartbeat` is a telemetry envelope, not a periodic beacon.** It is 93% of all rows (843,600) and carries **41 distinct `event` values**, of which the sample showed only 18. Full taxonomy by volume:

```
network-activity 177485   buffer-health 167460   video-resize 141250   BufferStart 66641
BufferEnd 66289   video_forward 49879   Seek 32036   resume 31780   network-bandwidth 30637
pause 27340   upshift 19400   dropped-frames 11089   downshift 7294   video_rewind 6587
AdSkipTrueView 1889   network-change 1178   download_asset_played 1154   next_video_click 619
go_live_click 423   download_initiated 409   speed-change 399   golive 396   speed-pause 380
speed-resume 380   download_completed 362   audio-language 180   preroll-disabled 152
video_quality_change 144   AdBufferStart 83   subtitle-language 83   AdBufferEnd 62
AdPause 45   AdResume 27   preview_watched 25   download_deleted 12
download_asset_play_stop 10   chromecast_clicked 6   chromecast_started 6   AdClick 4
download_resumed 4   premium_button_click 1
```

All other `event_type`s are single-valued (`VideoSessionStart`, `Play`, `AppBackgrounded`, `AppForegrounded`, `VideoSessionEnd`, `VideoError`), so **the `event` column is the only place playback state lives**.

- **`pause` (27,340) / `resume` (31,780)** are the player-level state toggles. Filtering on `event_type` alone counts every paused span as active — the headline failure mode. Resolves D4.
- **Three separate pause-like families exist and must not be conflated:** `pause`/`resume` (player), `speed-pause`/`speed-resume` (playback-speed control — *not* a viewing stop), and `AdPause`/`AdResume` (ad slot). Decide each explicitly; the safe default is that only `pause`/`resume` bound active intervals, and ad playback counts as watching.

**F2 — The real cadence is 40s, not the documented 60s, and the timeout has a clean empirical basis.** Inter-event gap distribution across 894,692 gaps:

| Bucket (s) | Gaps | Share | | Percentile | Gap (s) |
|---|---:|---:|---|---|---:|
| 0–1 | 552,754 | 61.78% | | p50 | 0.2 |
| 1–5 | 89,546 | 10.01% | | p75 | 9.2 |
| 5–15 | 56,018 | 6.26% | | p90 | 40.0 |
| 15–30 | 47,370 | 5.29% | | p95 | 40.0 |
| **30–45** | **139,978** | **15.65%** | | p97 | 40.0 |
| 45–60 | 1,164 | 0.13% | | p99 | 45.9 |
| 60–90 | 2,185 | 0.24% | | p99.5 | 129.9 |
| 90–120 | 968 | 0.11% | | p99.9 | 784.3 |
| 120–300 | 2,264 | 0.25% | | max | 142,527.9 |
| 300+ | 2,445 | 0.27% | | | |

The distribution is strongly **bimodal**: a burst mode below 1s (61.8% — simultaneous telemetry on one player event) and a **hard cadence spike at exactly 40.0s** (p90 = p95 = p97 = 40.0). Then a cliff — p99 is 45.9s but p99.5 jumps to 129.9s. **Only 0.87% of gaps exceed 60s.**

That valley between ~48s and ~130s is where `ACTIVITY_TIMEOUT` belongs, and it makes the choice defensible rather than arbitrary: **90s = 2× the observed 40s cadence + 10s grace**, i.e. tolerate exactly one dropped beat, cut at two. (The originally drafted 90s was right by luck — it was derived from the documented 60s cadence, which is wrong.) The 60–90s bucket is the only genuinely contested region at 2,185 gaps / 0.24%. **Deliverable: run the concurrency curve at 60s and 90s and report the delta** — that sensitivity analysis is a strong "design quality" artifact and cheap to produce.

**F3 — Dimensions are dirty, and the impact is quantified.**

| Column | Distinct | The problem |
|---|---:|---|
| `audio_language` | 41 | Hindi appears as **`hin` (610,889) + `HIN` (69,033) + `hin-hindi` (23,095)**. A naive `= 'hin'` filter misses **13.1%** of Hindi viewing. Same for `eng`/`ENG`/`eng-english`, `mal`/`MAL` |
| `subtitle_language` | 11 | `UNK`/`unk`, `OFF`/`off`, `UND`/`und`, `NON`, `eng-English`/`ENG`, empty (2,006) |
| `player_version` | 14 | `3.33.50_ADE` vs `3.29.71_adE` vs `3.29.71_adNE` — suffix case varies; do **not** blindly case-fold these into each other without checking whether `_ADE`/`_adE` are the same build |
| `app_version` | 65 | High cardinality but clean |
| `platform` | **10** | Clean. `ANDROID_PHONE` 629,646 (69.5%), then `SONY_ANDROID_TV`, `IPHONE`, `JIO_ANDROID_TV`, `Mweb`, `ANDROID_TAB`, `XIAOMI_ANDROID_TV`, `SAMSUNG_HTML_TV`, `FIRE_TV`, `LG_HTML_TV` |
| `country` | **1** | *Sample said this was likely an artifact; it is not.* **Every one of the 905,558 rows is `india`.** |
| `video_type` (content) | 3 | Of 3,357 played titles: `vod` 3,206, **empty 142 (4.2%)**, `live` 9 |

Two design consequences beyond normalization:

- **`country` is dead weight in this dataset** — it carries zero selectivity, so it must not sit high in any ordering key. But it is a declared filter dimension and the unseen day may not be single-country, so the column and its filter path stay.
- **Only 9 `live` titles exist**, yet live sport is the motivating use case. Peak concurrency will be dominated by VOD here. Do not tune exclusively on the live slice.

**F4 — Session integrity: duplicates and unmatched markers are real; open sessions are absent.**

| Check | Count | Implication |
|---|---:|---|
| Sessions with no `VideoSessionStart` | **0** | Every session has a start |
| Sessions with no `VideoSessionEnd` | **0** | **No open sessions in the provided data** |
| Sessions with >1 start | 13 | Duplicate boundary events exist → dedup (R6) is required, not theoretical |
| Sessions with >1 end | 14 | Same |
| Sessions with unmatched `AppBackgrounded` | **418 (3.8%)** | Backgrounded and never foregrounded — 14,700 background vs 14,321 foreground events |
| Max intra-session gap | 142,528s (39.6h) | Some sessions span days with enormous silent gaps |

*Sample said every session had exactly one background/foreground pair.* False at scale: with 14,700 background events across 10,866 sessions, **multiple background/foreground cycles per session are normal**, and 418 sessions background without ever returning. Those must be closed by the gap rule or session end, or they count as active indefinitely.

**The absence of open sessions is the most important operational finding.** The problem statement says judges will test how the serving layer absorbs sessions "still open when the day ends" — but the provided data contains none, so **that path cannot be validated against this file**. FR-6 must be tested with a deliberately synthesized open-session fixture (truncate a known session's tail, replay it late), and that fixture is now a required Phase 4 artifact rather than an optional one. The unseen day is where this gets exercised for real.

**F5 — Content join is currently total, but keep the safety net.** All 3,357 played `content_id`s resolve against the content file (0 unknowns). Only 10% of the 33,464 catalogue titles are ever played, making the dictionary comfortably small. The unknown-`content_id` bucket in FR-5 stays regardless — the unseen day may reference titles this catalogue lacks.

---

## 5. Functional requirements

### FR-1 — Active-interval definition (the correctness core)

The system must derive, per `video_session_id`, a set of half-open active intervals `[t_start, t_end)` from the event stream, under these rules:

- **R1 — Activity is the liveness proof.** A session is active over a minute only if covered by an activity event within the tolerance window. "Activity" means *any* event row for the session, not only `event_type = VideoHeartbeat` — per F2, heartbeat rows are player-driven telemetry rather than a clock tick.
- **R2 — Gap rule.** If the gap between consecutive activity events exceeds `ACTIVITY_TIMEOUT` (**90s**, fitted in F2: 2× the measured 40s cadence + 10s grace), the interval closes at `last_event + GRACE` rather than carrying forward. This is what excludes silent/backgrounded/dead sessions when no explicit marker arrived — including the 418 sessions that background and never return. The documented 60s cadence is wrong; the measured one is 40s.
- **R3 — Explicit state markers win, and they live in two columns.** Two toggle pairs bound intervals and both are authoritative over the gap rule when present:
  - `event_type = AppBackgrounded` / `AppForegrounded` — app-level.
  - `event = 'pause'` / `'resume'` **on `event_type = VideoHeartbeat` rows** (F1) — player-level.

  A session is active only when it is both foregrounded **and** not paused. Model this as a small state machine over the union of both pairs, not as two independent filters.
- **R4 — Session boundaries.** `VideoSessionStart` / `VideoPlay` (`event = 'Play'`) open; `VideoSessionEnd` closes. `VideoError` closes pending confirmation (see decision D3).
- **R5 — Open sessions.** A session with no `VideoSessionEnd` and a recent heartbeat stays open; its active interval extends to `min(now, last_heartbeat + timeout)` and must **not** be extrapolated beyond the watermark.
- **R6 — Idempotence.** Duplicate and out-of-order events must not double-count. Reprocessing the same input must produce the same output.

All thresholds must be **named constants in one place**, tunable without touching pipeline logic, since the unseen day may have a different cadence profile.

### FR-2 — Dual computation paths

The start-here guide asks for both, and comparing them is itself a deliverable:

- **Session-aware** — reconstruct per-session intervals, then count overlapping sessions. Exact; higher state cost.
- **Session-independent** — derive foreground presence directly from event state per (minute, dimension) without materializing session objects — e.g. a minute is "covered" if a heartbeat for that session falls in it. Cheaper, streaming-friendly, approximate at interval edges.

**Requirement:** produce both, quantify the delta between them (absolute and %, at minute grain), and document where and why they diverge. A reconciliation table is a scoring asset under "design quality."

### FR-3 — Representation & storage

The chosen representation must be justified against the alternatives named in the problem statement (interval arrays per session / normalized intervals / pre-aggregated minute deltas / hybrid).

**Recommended: interval → delta, served from an aggregating table.**

Each active interval `[s, e)` becomes `+1` at `toStartOfMinute(s)` and `−1` at `toStartOfMinute(e)`. Concurrency at any minute is the running sum of deltas up to that minute. This is the one representation where the stored quantity is **additive across both time and dimensions**, which is what makes filtered peak queries correct (§1.1) and incremental updates cheap (a late heartbeat is a small delta correction, not a rebuild).

Sketch:

```sql
-- Layer 1: raw landing (MergeTree)
CREATE TABLE events_raw (...)
ENGINE = MergeTree
ORDER BY (toStartOfHour(event_timestamp), video_session_id, event_timestamp);

-- Layer 2: derived active intervals, one row per (session, interval)
CREATE TABLE session_intervals (
  video_session_id String,
  interval_start   DateTime,
  interval_end     DateTime,
  is_open          UInt8,
  content_id       String,
  platform LowCardinality(String),
  country  LowCardinality(String),
  ...
) ENGINE = ReplacingMergeTree(version)
ORDER BY (video_session_id, interval_start);

-- Layer 3: serving — minute deltas per dimension tuple
CREATE TABLE concurrency_deltas (
  minute   DateTime,
  platform LowCardinality(String),
  country  LowCardinality(String),
  content_id String,
  video_type LowCardinality(String),
  delta    SimpleAggregateFunction(sum, Int64)
) ENGINE = AggregatingMergeTree
ORDER BY (minute, platform, country, content_id);
```

Peak over a range with a filter then becomes: filter → sum deltas per minute → running sum → `max()`. Average is the mean of that same series. **Both read from the same series; neither stores a peak.**

Design notes to resolve during build: ordering-key column order (time-first favours range scans; dimension-first favours filtered scans — measure both against the actual filter shapes in the FR-4 query pack), `LowCardinality` on every dimension, dictionary-backed `content_id` enrichment instead of a runtime join, and a **hybrid tier** (fine intervals for the recent window, compacted minute deltas for history) if the fine tier proves too large.

### FR-4 — Query surface

Must answer, at minute / hour / day grain, over an arbitrary time range, with any conjunction of the available dimensions:

1. **Peak concurrency** in range — value **and** the minute at which it occurred.
2. **Average concurrency** in range.
3. **Concurrency time series** for plotting.
4. **Content-level concurrency** — same three, grouped by title / show / video type / category.
5. **Session-level and user-level** variants (user-level de-duplicates multiple sessions per `user_id`).

**We define the query pack ourselves.** There is no supplied benchmark set (§1.2); the scored deliverable is *"peak and average concurrency at minute, hour, and day grain, with dimension filters."* That is a specification of coverage, so the pack must span it rather than cherry-pick:

| Axis | Must include |
|---|---|
| Metric | peak (with its minute), average, full series |
| Grain | minute, hour, day |
| Filter arity | unfiltered; single dimension; **≥2-dimension conjunction** (the §1.1 peak-composition trap only bites here) |
| Dimensions | at minimum platform, country, content, video type — plus `video_resolution` / `show_name` on the unseen day |
| Range | narrow (one hour) and wide (full day) — these stress different parts of the ordering key |
| Subject | session-level and user-level |

Every query in the pack ships with its latency and its bytes/rows read (§6). Because we choose the pack, a judge's first instinct will be to ask for a query we *didn't* pick — so the surface must be general and the pack merely a demonstration of it, never a set of special-cased shapes.

### FR-5 — Enrichment and dimension normalization

**Enrichment.** Join `content_id` → `title`, `video_type`, `category` (and `show_name` on the unseen day) at ingest (preferably via a ClickHouse dictionary for O(1) lookup) so the serving layer needs no runtime join. Must handle unknown `content_id` on the unseen day gracefully — bucket as `unknown`, never drop the event, never fail the query.

**Dimension registry.** The set of dimensions is data, not code. Declare it once — a list consumed by DDL generation, normalization, the delta MV, and the query pack — so that adding `video_resolution` and `show_name` (§1.3) is an `ALTER TABLE … ADD COLUMN` plus one list entry. A dimension appearing in a `SELECT` written by hand in three files is the anti-pattern; G8 fails the moment that happens.

**Normalization (from F3).** Every dimension is canonicalized once, at ingest, before it reaches the serving layer:

- Case-fold and trim all string dimensions (`hin`/`HIN` → `hin`, `UNK`/`unk` → `unk`).
- Map empty string to an explicit `unknown` sentinel — never leave `''` as a distinct filterable value, including `video_type`, where 39/1000 sampled content rows were blank.
- Fold known synonym sets (`unk` / `und` / `non` → `unknown`; `off` stays distinct from `unknown` — "subtitles off" is a real user state, "unspecified" is not).
- Timestamps: parse `event_timestamp` and `session_start_epoch` from **epoch milliseconds** to `DateTime64(3)`. Getting the unit wrong puts every event in 1970 or 58000 AD, which is loud; getting *seconds vs milliseconds* wrong silently on a subset would not be.

Normalization rules live in one place and are applied identically to the provided data and the unseen day. Emit a per-dimension distinct-value report after each load — an unseen-day file introducing a new casing variant should be visible, not silent.

### FR-6 — Incremental update handling

- New heartbeats extend an open session's interval by emitting corrective deltas; no rebuild.
- Late-arriving events within the lateness tolerance are folded in correctly; beyond it, they are counted and reported, not silently dropped.
- Materialized views drive Layer 2 → Layer 3 propagation.
- A **watermark** marks how far the served curve is trustworthy; queries beyond it are marked provisional.

> **Validation gap (F4).** The provided dataset contains **zero open sessions** — all 10,866 have a `VideoSessionEnd`. This requirement therefore cannot be tested against the supplied file. Build a fixture: truncate a known session's tail, ingest the head, assert the served curve, then replay the tail and assert only the affected minutes changed. Without this, update handling ships untested into the unseen day.
>
> **But do not conclude the unseen day has none.** The provided file spans 11.8 days, so boundary-truncated sessions are negligible; the unseen day is a **single day** with a 714s median session (§1.3). Sessions still running at the day boundary are likely there, and update handling is explicitly scored — the fixture proves the mechanism, the unseen day is where it earns points.

### FR-7 — Demo

Replay a live-event day: ingest the stream → the concurrency curve builds in near real time → apply a platform/country filter → the minute-grain view answers instantly → optionally ask a follow-up in chat. Minimal visualization is fine.

### FR-8 — Unseen-day runbook

A single documented, rehearsed command path: download → `ALTER` for the new columns → load → derive → serve → run the query pack → emit results + per-query latencies + pipeline evidence (query logs or ClickStack traces). **No pipeline evidence, no credit.** This must be tested end-to-end on the provided data well before release time, because it will be executed under time pressure.

Steps specific to what §1.3 tells us about the unseen day:

1. **Download ~1.8 GB from Google Drive** — not `git lfs pull`. Time this step during rehearsal; it is the one part of the runbook that depends on the venue's network rather than our design.
2. **Apply the schema delta** — `video_resolution` on raw, `show_name` on content. Pre-write both `ALTER` statements and rehearse them against the provided data; do not compose DDL at release time.
3. **Re-run the profile** (§4.3 checks) on the new file before trusting anything: min/max event time, gap histogram (does the 40s cadence hold?), distinct values per dimension, count of sessions without `VideoSessionEnd`. Ten minutes here prevents shipping a confidently wrong curve.
4. **Load, derive, serve**, then run the FR-4 query pack and FR-9 verification sample.
5. **Package** results + latencies + evidence.

Budget for ~7M events / ~1.8 GB, not for the 232 MB provided file: rehearse the load path at a volume that will not surprise us.

### FR-9 — Self-verification against raw events

With no answer key (§1.2), correctness is judged by spot-check: a judge picks a minute and a filter, recomputes the count from the raw event rows, and compares. **We ship that same check as a tool**, and run it before submitting.

- An independent, deliberately naive recomputation: for a given minute + filter, scan raw events, derive active intervals per session by the FR-1 rules, count sessions covering the minute. Optimized for being obviously right, not for speed.
- It must **not** share code with the serving pipeline — a shared bug would agree with itself and prove nothing. Different implementation path, same documented rules.
- Run it over a random sample of (minute, filter) pairs after every load, including the unseen day, and report the agreement rate. Any disagreement is a release blocker, not a footnote.
- The output table — sampled slice, serving-layer value, brute-force value, delta — is a scoring artifact under correctness. It converts "trust our numbers" into "here is the audit, reproduce it."

This makes systematic what Phase 1 previously did informally by hand-tracing sessions.

---

## 6. Non-functional requirements

| Area | Requirement |
|---|---|
| Latency | Dashboard-grade on minute-grain filtered queries. Judges inspect **bytes/rows read**, not just wall time — record `EXPLAIN` / `system.query_log` metrics for every query in the pack (FR-4) |
| Scale | Design must hold at ~100× the provided volume. The unseen day is already ~7.7× the rows and **~90× the per-day event density** (§1.3), so this is a near-term requirement, not a thought experiment. No full rescans, no per-minute explosion of all history |
| Schema | A new dimension column is absorbed by `ALTER` + registry entry, with no rebuild and no change to interval derivation (G8) |
| Correctness | Deterministic and idempotent under replay; documented tie-breaking for duplicate/out-of-order events; verified by independent recomputation (FR-9), not by self-consistency |
| Freshness | Stated end-to-end lag from event ingest to served minute |
| Storage | Report serving-layer size vs raw; the compression ratio is a design argument |
| Portability | ClickHouse Cloud, our own service. Tune the design, not the hardware — latency is compared with service size accounted for |

---

## 7. Architecture

```
ch-hackathon-raw-data.csv ──► events_raw (MergeTree, event-time ordered)
                                   │
content-data.csv ──► content_dict ──┤ enrich (dictGet, no runtime join)
                                   ▼
                      interval derivation (FR-1)
                    ┌──────────────┴──────────────┐
          session-aware path              session-independent path
                    └──────────────┬──────────────┘
                                   ▼
                       session_intervals (ReplacingMergeTree)
                                   │  MV: interval → ±1 deltas
                                   ▼
                       concurrency_deltas (AggregatingMergeTree)
                                   │
              ┌────────────────────┼────────────────────┐
          query pack (FR-4)   minimal viz         LibreChat / MCP
                                   │
                              ClickStack: ingest lag, query perf, decline alerts

        raw events ──► FR-9 brute-force recompute ──► agreement report
                       (independent path, audits the serving layer)
```

---

## 8. Ecosystem integration (mandatory, ≥1, meaningful)

**Primary — ClickStack.** Instrument our own pipeline: ingest lag, MV propagation delay, per-query latency and bytes-read for the FR-4 query pack, and watermark drift. This doubles as the **pipeline evidence** the unseen-day submission requires, which makes it the highest-leverage choice — one integration satisfying two scored requirements.

**Optional stretch — LibreChat + [ClickHouse MCP server](https://github.com/ClickHouse/mcp-clickhouse)** (preconfigured) as a conversational layer: *"what was peak concurrency on Android in the last hour?"* → serving-layer query → answer.

**Optional stretch — concurrency-decline detection.** Alert when the curve drops sharply and classify the cause: asset ended (expected), system issue (heartbeats stop across many sessions at once), or disengagement (gradual drift). An LLM can phrase the diagnosis; the detection itself is a query. Only build this once §5 is solid.

---

## 9. Evaluation mapping

| Judging criterion | What we ship |
|---|---|
| Correctness (spot-checked vs raw events) | FR-1 rules, **FR-9 independent recomputation + agreement report**, FR-2 dual-path reconciliation, idempotence tests |
| Query performance | FR-3 serving layer + recorded bytes/rows read for every query in the FR-4 pack |
| Update handling | FR-6 incremental deltas + open-session and late-arrival test cases |
| Design quality | This PRD + a trade-off write-up: representation, ordering keys, tiering, 100× behaviour, schema evolution (G8) |
| The unseen day | FR-8 runbook, rehearsed at ~7M-event scale, with the schema delta pre-written and logs/traces captured |

Correctness is the criterion whose *evidence method* changed: with the answer key gone, judges reconstruct truth from raw events. FR-9 is the direct answer to that — we perform the audit first and hand it over, rather than waiting to be audited.

---

## 10. Milestones (24h)

| Phase | Target | Exit criterion |
|---|---|---|
| 0 · Setup | ✅ **Data profiled (§4.3).** Remaining: ClickHouse Cloud up, both CSVs loaded with epoch-ms → `DateTime64(3)` and FR-5 normalization applied | Raw tables queryable; loaded min/max event time matches F0; distinct-value report reproduces F3 |
| 1 · Semantics | FR-1 interval derivation, `ACTIVITY_TIMEOUT` = 90s per D1, hand-traced against known sessions including a 418-cohort unmatched-background one | Intervals match manual reading; 60s-vs-90s sensitivity delta reported; thresholds centralized |
| 2 · Serving | FR-3 delta model + MVs; peak/avg/series queries. Dimension registry (FR-5) in place from the start | Minute-grain filtered query answers from the serving layer, not raw |
| 3 · Query pack | FR-4 pack authored to cover the full metric × grain × filter-arity matrix; latency + bytes-read recorded. **FR-9 verification harness built and agreeing** | Pack runs green with metrics captured; agreement report shows zero unexplained deltas |
| 4 · Incremental | FR-6 open sessions, late arrivals, watermark. **Includes building the synthesized open-session fixture** — the provided data has none (F4), the unseen day likely does (§1.3) | Replaying a late batch changes only affected minutes; no rebuild; truncated-session fixture absorbs incrementally |
| 5 · Integration | ClickStack instrumentation (+ optional LibreChat) | Traces visible; evidence artifact generated automatically |
| 6 · Dress rehearsal | Full FR-8 runbook on provided data, timed. **Includes rehearsing the `ALTER` for `video_resolution` / `show_name` and a load at unseen-day volume** | Cold-start → results in a known, comfortable wall-clock time; schema delta applied without touching derivation logic |
| 7 · Unseen day | Download, `ALTER`, re-profile, execute runbook; package results + latencies + evidence | Submitted with pipeline proof |

**Sequencing note:** Phase 6 is not optional polish. The unseen day is scored on a run executed under time pressure, at ~7.7× the data volume, against a schema we have not yet loaded. The rehearsal is what makes that run boring.

**Volume note:** phases 1–5 run against the sparse provided file. At least one rehearsal must run against a synthetically inflated copy (replicate sessions across a compressed time window to approximate ~7M events in one day), or Phase 7 will be the first time the design meets its actual density.

---

## 11. Open decisions

| ID | Decision | Default to start from | Resolve by |
|---|---|---|---|
| D1 | `ACTIVITY_TIMEOUT` | **90s** = 2× the measured 40s cadence + 10s grace, landing in the empty valley between p99 (45.9s) and p99.5 (129.9s). Ship the 60s-vs-90s sensitivity delta alongside | ✅ Fitted from full-data gap histogram (F2) |
| D2 | Grace period after last activity event before closing | 10s (folded into D1's 90s) | Phase 1 |
| D3 | Does `VideoError` end activity immediately? | 293 errors total — rare enough that either choice barely moves the curve. Close the interval; verify whether activity continues after an error | Phase 1, empirically |
| D4 | Does `paused` count as active? | **Resolved: no.** `pause`/`resume` are `event` values on `VideoHeartbeat` rows (F1) and bound intervals per R3 | ✅ Resolved from sample |
| D5 | Lateness tolerance | 5 min | Phase 4 |
| D6 | Serving grain — minute-only vs minute + hour rollup | Minute-only first; add rollup only if hour/day queries are slow. Note the unseen day is a *single* day, so the day grain is one row and the hour grain is 24 — the rollup case is weaker than it looks | Phase 3, on measurement |
| D7 | Dimension tuple in the serving key vs multiple serving tables | Single wide table, ordering key tuned to the FR-4 pack's filter shapes — and it must stay general, since we authored the pack and judges may ask for something outside it | Phase 3, on measurement |
| D8 | Session- vs user-level as the default concurrency metric | Session-level (dictionary calls it session concurrency); expose user-level alongside | Phase 2 |
| D9 | Do `speed-pause`/`speed-resume` and `AdPause`/`AdResume` bound active intervals? | **No** — only `pause`/`resume` do. Speed control and ad slots are still watching. Low volume (380 / 45), so impact is small either way | Phase 1 (F1) |
| D10 | Are `player_version` suffixes `_ADE` / `_adE` the same build? | Do **not** case-fold them together until confirmed; treat as distinct | Phase 1 (F3) |
| D11 | How wide is the FR-4 query pack? | Cover the full metric × grain × filter-arity matrix (§FR-4) rather than a short list — we author it, so a thin pack reads as avoidance | Phase 3 |
| D12 | Does `video_resolution` join the serving-table ordering key, or stay a filterable non-key column? | **Non-key by default.** It arrives only on the unseen day, its cardinality is unmeasured, and promoting an unprofiled column into the ordering key at release time is how a fast design becomes a slow one. Revisit if it proves highly selective | Phase 7, after the §4.3 re-profile |
| D13 | FR-9 sample size — how many (minute, filter) pairs to verify? | Enough that a systematic error cannot hide: cover each dimension at least once, both grain extremes, and at least one 2-dimension conjunction. Cheap to widen; widen it | Phase 3 |

**With D1 and D4 resolved from data, the dominant risks are now the two things the provided file cannot exercise.** First, F4: zero open sessions here, while update handling is scored — validated only by a synthesized fixture until the unseen day. Second, §1.3: a schema and a per-day density we have never loaded. Both meet real input for the first time in Phase 7. Treat both paths as untested until Phases 4 and 6 prove them.

---

## 12. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Background markers unreliable (stated in the dictionary) | Overcounting — the headline failure mode | Never depend on markers alone; the gap rule (R2) is the primary mechanism, markers are a refinement |
| `pause`/`resume` missed because they hide in `event`, not `event_type` (F1) | All paused time counted as active | R3 state machine over both columns; assert in tests that a sampled paused span is excluded |
| Dirty dimension values (F3) split filter results | Measured: a naive `audio_language = 'hin'` filter misses **13.1%** of Hindi viewing. Wrong in a way that looks like a model bug | FR-5 canonicalization at ingest + post-load distinct-value report |
| **Open-session path never validated** — the provided file has zero open sessions (F4) | Update handling is a scored criterion, and it meets real input for the first time on the unseen day | Synthesized open-session fixture is a required Phase 4 artifact; replay a truncated session and assert incremental absorption |
| Multi-day span (F0) mistaken for a single day | Day-grain queries and partitioning silently wrong | Assert the loaded min/max event time; never hard-code a single-day window |
| Epoch-ms timestamps mis-parsed | Whole-dataset time axis wrong | Explicit `DateTime64(3)` from ms; assert min/max event time lands on a plausible date after load |
| Tuning thresholds to the provided day | Unseen day degrades | Derive thresholds from cadence semantics, not from fitting; keep them in one config; re-profile on the unseen file before the final run (FR-8 step 3) |
| Peak treated as combinable across dimensions | Wrong answers on every filtered query | Store series, never peaks (§1.1) — enforce in review |
| **No answer key — we cannot know we are wrong** | Silent correctness failure discovered by a judge, not by us | FR-9 independent recomputation on a sampled slice set, run before submission; agreement report shipped as evidence |
| **Unseen-day schema delta not rehearsed** (§1.3) | Two new columns to absorb under time pressure, with `ALTER` composed live | Dimension registry (FR-5); pre-written `ALTER` statements; Phase 6 rehearses the whole delta on provided data |
| **~90× per-day event density** (§1.3) | Design that is comfortable on the sparse file falls over on a real day's concurrency | Rehearse on an inflated copy (Phase 6 volume note); never accept a per-minute-per-session materialization |
| 1.8 GB download at release, over venue wifi | Runbook stalls before any of our code runs | Time the download during rehearsal; start it the moment the link opens; parallelize with nothing that depends on it |
| Query pack authored by us reads as self-serving | "Design quality" and "correctness" both discounted | Cover the full matrix (D11), keep the surface general, publish latencies for all of it — including the queries that are slowest |
| Serving-table cardinality explosion from wide dimension tuples | Slow queries, large storage | LowCardinality everywhere; consider a narrow hot table for the most-filtered dimensions plus a wide cold one |
| Unseen-day run fails under time pressure | Significant score loss | Phase 6 rehearsal; scripted runbook; evidence capture automated, not manual |
| Data not LFS-pulled / late environment setup | Everything downstream slips | Phase 0 first, before any modeling |

---

## 13. Deliverables checklist

- [ ] ClickHouse schemas + load scripts (raw, intervals, serving, dictionary), driven by a dimension registry
- [ ] Interval-derivation logic with centralized, documented thresholds
- [ ] Session-aware and session-independent paths + reconciliation table
- [ ] FR-4 query pack covering the metric × grain × filter-arity matrix, with recorded latency and bytes/rows read
- [ ] **FR-9 verification harness + agreement report** (independent recomputation from raw events)
- [ ] Incremental-update demo (open session, late arrival)
- [ ] **Pre-written schema-delta `ALTER`s for `video_resolution` / `show_name`, rehearsed**
- [ ] ClickStack instrumentation (+ optional LibreChat/MCP layer)
- [ ] Minimal concurrency-over-time visualization
- [ ] Trade-off write-up, including 100× behaviour and schema evolution
- [ ] Unseen-day runbook + executed results + pipeline evidence

**Submission packaging** (per the [repo README](https://github.com/sidagarwal04/click-a-thon-2026/blob/main/README.md) — collected in [click-a-thon-26-submissions](https://github.com/sidagarwal04/click-a-thon-26-submissions), read the [SonyLIV guidelines](https://github.com/sidagarwal04/click-a-thon-26-submissions/blob/main/SONYLIV_SUBMISSION_GUIDELINES.md) before submitting):

- [ ] Fork the submissions repo, team-named folder, PR titled `[Submission] <Team Name>`
- [ ] Source code + README with a **hosted demo link**
- [ ] Architecture write-up (the §7 diagram plus the trade-off doc)
- [ ] 2–3 minute demo video
- [ ] Pitch deck PDF
