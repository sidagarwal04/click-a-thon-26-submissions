# Data Profiling Evidence Base

*Produced by 6 parallel profiling investigations over the real dataset (905,558 events), 2026-08-01. Every fact below was measured with ClickHouse SQL (chdb) — key queries preserved in the investigation transcripts.*

# EVIDENCE BASE: SonyLIV Foreground-Only Streaming Concurrency (ClickHouse)

Sources: I1=event taxonomy, I2=heartbeat cadence, I3=bg/fg, I4=dimensions/joins, I5=disorder/duplicates, I6=ground-truth concurrency.

**Timezone resolution (applies to everything below):** I1/I2/I3/I5 reported timestamps as rendered by a local ClickHouse in Asia/Kolkata (IST, +5:30); I6 normalized to UTC. They describe the same instants: dataset end "2026-07-26 17:00:04.847" (I1/I5) = 11:30:04 UTC (I6); hot hour "16:00" (I1/I5) = 10:30–11:30 UTC; peak minute "16:29" (I1) = 10:59 UTC (I6). All facts below state UTC with IST in parens where the source used IST.

---

## 1) FACTS (design-critical, numbered, contradictions resolved)

**F1. Scale & shape** [I1,I4,I5]: 905,558 events; 10,866 distinct video_session_id; 9,618 user_id; 3,357 content_id played (of 33,464 in content dim); span 2026-07-14 21:13 → 2026-07-26 11:30:04 UTC (17:00:04 IST), with NO events Jul 15–20.

**F2. Pathological temporal skew** [I1,I5,I6]: 2026-07-26 holds 852,625 events (94.2%); the single hour 10:30–11:30 UTC ("16:00" IST) holds 780,934 (86.2%) across 10,180 sessions. Peak minute 10:59 UTC (16:29 IST): 18,434 events, ~2,944 naive-active sessions. Peak second: 426 events. Data cuts off abruptly at 11:30:04 UTC mid-live-event.

**F3. event_type is a lie; the 'event' column is the truth** [I1,I2,I5]: 47 distinct (event_type, event) pairs; 41 event names hide under event_type='VideoHeartbeat'. Pause/Resume exist ONLY as lowercase heartbeat events 'pause' (27,340) / 'resume' (31,780), plus speed-pause/resume (380/380), AdPause/AdResume (45/27). Casing is inconsistent ('BufferStart' vs 'pause'). *Contradiction flagged:* I6 counted 36 distinct heartbeat event values vs I1's 41; I1's full-taxonomy arithmetic (47 pairs − 6 non-heartbeat types) is authoritative → 41.

**F4. Heartbeat row count** [I2,I5 vs I1]: *Contradiction resolved:* heartbeat-type rows = **843,600 (93.16%)** (I2, I5; verified by 905,558 − 61,958 lifecycle/bg/fg/error events). I1's "847,600 / 93.6%" is an arithmetic error.

**F5. True periodic heartbeat = 40s trio, not 60s** [I2]: The periodic ping is the bundle {network-activity, buffer-health, video-resize} at identical ms timestamps = 486,195 rows (53.69% of all data). Cadence p50=40.00s, p90=40.01s, p99=321s; 66.8% of gaps in [39,41)s. The data dictionary's 60s cadence assumption is wrong.

**F6. iPhone doesn't emit the trio** [I2]: 74.4% of IPHONE sessions (1,139 of 1,530) have ZERO periodic-trio pings (vs 0.2% ANDROID_PHONE); 1,158 sessions (10.7%) overall lack it. Where present, cadence is 40s on all 10 platforms. Liveness must use ANY event name, not the trio.

**F7. Heartbeats stop when backgrounded; only partially stop when paused** [I2]: Of 14,354 bg→fg windows, only 17.7% contain any heartbeat inside (72.8% of those within 5s of the bg edge — the pause burst); for windows >120s, 78.5% have zero heartbeats (0.37 observed vs 17.9 expected). During foreground pause the trio continues at ~39% of nominal rate → pause is NOT detectable from silence; backgrounding IS.

**F8. Legit-gap threshold data** [I2]: Gaps between consecutive heartbeats with no bg/pause between: p99=40.01s, p99.5=49.0s, p99.9=312s. Threshold cut-rates: 60s→0.446%, 90s→0.253%, **120s→0.201%**, 180s→0.157%, 300s→0.103%. Residual ~0.2% is genuine stalls, not jitter.

**F9. Every session is closed** [I1,I5]: 0 of 10,866 sessions lack VideoSessionStart or VideoSessionEnd. Zero open sessions at rest — live concurrency exists only mid-replay. session_start_epoch is perfectly clean: constant per session, exactly equals the Start event timestamp (0 mismatches).

**F10. VideoSessionEnd is not a hard terminator** [I1,I3,I5]: 239 sessions (802 events) have events after their End — 239 AppBackgrounded, 522 heartbeats (in 22 sessions), 28 AppForegrounded, 13 VideoPlay. Last-event-type distribution: VideoSessionEnd 10,627 (97.8%), AppBackgrounded 217, VideoHeartbeat 16, AppForegrounded 6.

**F11. Duplicate lifecycle events** [I1,I5; I6 miscount resolved]: **13** sessions have multiple VideoSessionStart (10,880 starts, all exact same-timestamp dups, max 3) and **14** have multiple VideoSessionEnd (10,881 ends; 10 same-timestamp, 4 at DIFFERENT timestamps — first-end vs last-end changes durations). I6's "14 sessions with duplicate starts" conflated 14 excess start *events* with session count; 13 sessions is correct.

**F12. bg/fg is universal but messy** [I1,I3]: 100% of sessions contain both AppBackgrounded (14,700) and AppForegrounded (14,321); modal pattern 1bg+1fg (8,403 sessions, 77.3%). Only 95.55% (10,382) alternate cleanly. Anomalies: 109 double-bg occurrences (101 sessions), 74 fg-without-open-bg (67 sessions), 344 sessions with unclosed final bg (216 of those after VideoSessionEnd, 128 genuinely in-session), 29 sessions whose first bg/fg event is a foreground. *Note:* I1's "418 sessions with bg>fg count" vs I3's 344 unclosed-final-bg differ because raw count imbalance ≠ state-machine unclosed windows; use I3's state-machine numbers. Event-level excess: 379 bg never closed (I6, = 14,700−14,321).

**F13. Backgrounded time is huge** [I3]: Paired bg→fg windows (14,247): p50=35.1s, p90=8.5min, p99=36min, max=39.6h. Explicit backgrounded time = 54,660 min = **30.6%** of 178,343 naive session-minutes. Silent gaps (>3min, no bg): 1,034 gaps in 984 sessions (9.1%), 12,305 min total. Naive→bg-excluded→+silent-gap-excluded: 178,343 → 123,683 (−30.6%) → 114,480 (−35.8%).

**F14. Ground-truth concurrency** [I6]: Peak NAIVE = 3,743 at 10:59 UTC; peak FOREGROUND = 2,970 at 10:56 UTC. Overcount: 26.03% peak-vs-peak, 34.58% in aggregate session-minutes (189,429 vs 140,751). 1,383 of 5,255 naive-active minutes (26.3%) have foreground=0. Ground-truth CSV: `/private/tmp/claude-501/-Users-dahiya-Work-sonyliv/fb664459-f44c-49cf-b6a2-4edcd8a9c7a7/scratchpad/ground_truth_foreground_per_minute.csv` (3,872 rows, minute_ts epoch-sec, max 2,970 at 1785063360); semantics in I6 findings[0] are the diff contract.

**F15. Per-slice peaks differ from global** [I6]: JIO_ANDROID_TV peaks at 10:59 UTC (230) not the global peak minute 10:56 (219, −4.8%). Per-(dimension, minute) state is mandatory; global series cannot be apportioned. Platform sums exceed global (2,982 vs 2,970) because 95 sessions span >1 platform.

**F16. Session keys collide** [I1,I4]: 120 sessions (1.1%) span 2 user_ids with time-interleaved events; 95 span >1 platform; 1 spans 2 content_ids. Safe session key = (user_id, video_session_id); attribute dims via argMax/any.

**F17. Cardinalities** [I4]: platform=10 (ANDROID_PHONE 629,646 = 69.5%), country=1 ('india', zero information), app_version=65, audio_language=41, subtitle_language=11, player_version=14, content_id=3,357 played / 33,464 in dim (unique, 100% join coverage, 0 events fail to enrich). Actual (platform × content_id) combos = 4,349 = full serving-dimension grid (video_type is a function of content_id; country constant).

**F18. Dimension dirt** [I4]: Languages case-inconsistent by event type ('unk'/'' on VideoSessionStart vs 'UNK'/'OFF' later); after normalization only 23 sessions truly change subtitles but 1,749 (16.1%) genuinely switch audio mid-session. 1,534 Start rows have empty player_version. Content dim has one negative-cast id (18446744072721897294 = −987654322); 1,089 rows ('' video_type, 142 played). One bot/shared user (4CE58A95…): 301 sessions, up to 95 simultaneous; excluding it, max 5 concurrent sessions/user (60 users overlap).

**F19. File order is session-major, not arrival order** [I5]: 10,866 sessions in 11,242 contiguous runs; block position uncorrelated with time (corr=−0.0097); "lateness" vs file order up to 283.77h is pure layout artifact. Within-session disorder is real: 99.65% of sessions have ≥1 out-of-order event, 7.0% of rows locally out of order, p99 within-session lateness ~2.3h, max ~43.3h.

**F20. Duplicates & density** [I5]: Exact dups on (session, event_type, event, ts) = 4,210 rows (0.465%, max multiplicity 6). 92.08% of heartbeat session-minutes contain >1 heartbeat (avg 6.21, max 195); minute-grain rollup collapses 707,671 rows (83.89% of heartbeats).

**F21. Marathon tails** [I1,I3,I5]: Session duration p50 ≈ 11.7–11.9 min (p50=13 min under I6's end-event definition — minor definitional variance, not a contradiction), p99 ≈ 70–74 min, max 2,618 min (43.6h). Max bg window 39.6h. 16 sessions (0.147%) cross a calendar day (identical in UTC and IST); 1 spans 3 days. VideoError (293, one per session) NEVER terminates a session — quality metric only.

**F22. Rates** [I5]: Hot hour sustained ~217 ev/s, peak minute 307 ev/s, peak second 426 ev/s. Brute-force ground truth on laptop: 0.46s build / 0.52s with reporting for 906K events, materializing ~386K intermediate (session,minute) rows.

---

## 2) ACTIVE-INTERVAL DEFINITION (recommended, data-justified)

A session S contributes to foreground concurrency at instant/minute M iff ALL of:

1. **Liveness (gap rule):** some qualifying event of S occurred in (M − 120s, M]. **T = 120s** = 3 missed 40s ticks; justified by F5/F8 — legit-gap p99.5 = 49s, T=120s falsely splits only 0.201% of continuous playback, and going to 180s recovers just 0.044pp while adding 60s of phantom activity after every real stop. (90s is defensible if freshness > completeness.)
2. **Qualifying events = ANY event name**, not the periodic trio (F6: trio-only silently drops 74.4% of iPhone sessions). Concretely: event_type IN (VideoSessionStart, VideoPlay, VideoHeartbeat, AppForegrounded) — this matches the I6 ground-truth contract.
3. **Foreground gate (hard edge):** AppBackgrounded immediately deactivates (F7: heartbeats stop within ~5s of bg; do not wait out T, or the bg-edge pause burst extends activity by up to 120s). AppForegrounded (or any subsequent qualifying event) reactivates — fg→next heartbeat is p50=0.91s, 82% <5s (I3), so fg itself is a reliable open marker; do NOT wait for VideoPlay (fires on resume only 2.2% of the time, I3-f).
4. **Terminator:** VideoSessionEnd closes the session immediately, using **last-End-wins (argMax)**, and all later events are ignored/clipped (F10, F11: 4 sessions have Ends at different timestamps; 239 sessions trail events, 217 of them AppBackgrounded exit telemetry).
5. **Defensive state machine (F12):** double-bg → keep first open bg; fg-without-open-bg → treat as no-op/reactivation; unclosed bg → backgrounded until session end; resume-without-pause → no-op (+4,440 resume/pause imbalance, I2).
6. **Zombie cap:** cap any single interval's silent contribution at T; a session re-opens on its next event (F21: without this, the 43.6h session and 39.6h bg window inflate concurrency for hours; 0.2% long-tail gaps run 300s–42h).
7. **Pause handling:** foreground 'pause' is NOT part of the default definition (undetectable from silence, F7). If "actively watching" is required, model 'pause'/'resume' as an explicit optional state on top.

Note: the ground-truth CSV (F14) uses rules 1–4 at minute grain (coverage {m0, m0+60, m0+120} clamped to session span; bg exclusion of wholly-contained minutes). Any implementation diffing against it must match those exact conventions or expect off-by-one-minute diffs.

---

## 3) SCHEMA DRIVERS

- **Session key:** (user_id, video_session_id) — video_session_id alone collides across 120 users / 95 platforms (F16). Attribute per-session dims via argMax(dim, event_timestamp); take dims from non-SessionStart events (Start rows have empty player_version/languages, F18). Decide event-attributed vs session-attributed platform explicitly (F15: sums differ, 2,982 vs 2,970).
- **ORDER BY:** raw table (video_session_id, event_timestamp) — data arrives session-clustered (F19), compresses and inserts well. Serving/rollup tables: (minute, platform, content_id …) — time-bucket first; never platform-first (69.5% skew) and never country (constant). session_start_epoch is a clean, correction-free sort/partition helper (F9).
- **Types:** DateTime64(3) via fromUnixTimestamp64Milli (ms ties matter — duplicate starts share exact timestamps, F11). LowCardinality(String) for platform, country, app_version, audio/subtitle_language, player_version, video_type, category (all ≤84 values). content_id UInt64 (raw fits UInt32 max 2.078e9, but content dim contains a negative-cast id, F18). user_id/video_session_id: 64-hex strings — plain String or FixedString(64)/UInt128. Cast Nullable parquet columns with assumeNotNull before use in sorting keys (I6 footgun). Consider a MATERIALIZED Enum/normalized column over the ~47 event names.
- **Normalization at ingest (MV):** lowerUTF8 + strip '-suffix' on languages; map ''/unk/und → 'unknown'; video_type '' → 'unknown' (142 played ids) — else every GROUP BY double-counts OFF/off, UNK/unk (F18).
- **Content enrichment:** dictionary (dictGet) over content.parquet — unique key, 33,464 rows, 100% coverage (F17).
- **Serving dimensionality is tiny:** 4,349 actual (platform × content_id) combos = worst-case rows per time bucket (F17). Session-state table ≈ 10.9K rows. Pre-aggregation is cheap; keep all dimensions.
- **Storage hot path:** 93.16% of rows are heartbeats; the trio alone is 53.69% (F4/F5). Collapse to interval/minute state via MV; optionally TTL/filter trio subtypes out of the hot path. Minute grain kills 83.89% of heartbeat rows (F20).

---

## 4) UPDATE MODEL DRIVERS

- **No fixed watermark short of hours works:** within-session disorder touches 99.65% of sessions, p99 lateness ~2.3h, max ~43.3h (F19). Choose **order-insensitive, commutative aggregate states** — AggregatingMergeTree with max/min/sum/uniq/argMax states — over lateness-sensitive windowing. Replay must re-sort by event_timestamp; file order is meaningless (F19).
- **AggregatingMergeTree over raw +1/−1 counters:** duplicate starts/ends (13/14 sessions, F11), 4,210 exact dup rows (F20), and 379 unclosed bg events (F12) make naive delta counters drift; max/argMax semantics are idempotent. If deltas are used, dedupe on (session_id, event_type) first.
- **ReplacingMergeTree role:** exact dups are only 0.465% — RMT keyed (video_session_id, event_type, event, event_timestamp) or query-time GROUP BY handles them cheaply; but RMT is NOT the concurrency engine — 92% of session-minutes need aggregation, not dedup (F20).
- **Liveness is event-driven, never absence-of-End:** every session in the extract is closed (F9); the open-session problem exists only mid-replay. Expire a session's contribution 120s after its last event; treat VideoSessionEnd as immediate terminator with argMax(End) and clip the 239 post-End trails (F10).
- **Partitioning:** PARTITION BY day is safe — 0.147% of sessions cross a day (F21) — but finalize sessions on End events (or scan a 2-day window), not at partition close, for the 43.6h outlier.
- **Ingest:** batched inserts ≥10K rows or async_insert to survive the hot hour without too-many-parts (F22).
- **Serving:** per-minute MV rollup keyed (minute, dims) with uniqState(video_session_id) or clean transitions — brute force is O(events) per query and dies under dashboard fan-out at 100x (F14/F22). Emit explicit zeros or define missing-minute=0 (26.3% of naive-active minutes have fg=0, F14).

---

## 5) SCALE ENVELOPE

At-rest (1x): 905,558 events / 10,866 sessions / 9,618 users / 3,357 contents; 843,600 heartbeat rows; 189,429 naive session-minutes, 140,751 foreground session-minutes, ~386K intermediate (session,minute) pairs for ground truth; peak concurrency 2,970 fg / 3,743 naive; hot hour 780,934 events.

Rates (1x): sustained ~217 ev/s for an hour, 307 ev/s peak minute, 426 ev/s peak second.

**100x extrapolation:** ~90.6M events, ~1.09M sessions; ~21,700 ev/s sustained, ~30,700 ev/s peak-minute, ~42,600 ev/s peak-second; ~19M naive session-minutes and ~15M cover pairs *per brute-force query* — seconds of CPU and GBs of dedup hash tables per widget × filter × 10–30s refresh × viewer. Conclusion: comfortable for ClickHouse ingest with batching; impossible for interactive serving without the per-minute pre-aggregated MV. Peak fg concurrency scales to ~297K sessions; per-minute serving rows stay bounded by dims (~4.3K × minutes at 1x grid; grows with content catalog).

Benchmark caveat: run all benchmarks on the hot window (2026-07-26 09:00–11:30 UTC holds 93.9% of events), never the 12-day average; note the data truncates the busiest hour to 31 minutes.

---

## 6) OPEN QUESTIONS (decide by fiat)

1. **"Foreground" vs "watching":** does a foregrounded-but-paused player count? Data cannot decide (pause pings continue at ~39% rate; silence detection impossible). Ground truth counts paused-in-foreground as active.
2. **Liveness threshold T:** 120s recommended, but 90s (fresher, cuts 0.253%) vs 300s (0.103%) is a freshness-vs-stability policy call.
3. **Duplicate-End convention:** last-End-wins vs first-End-wins — changes 4 sessions' durations; pick one and state it.
4. **Post-End clipping:** treat End as absolutely terminal (recommended) even though 22 sessions heartbeat up to ~35min after — or allow re-open?
5. **Dimension attribution:** event-attributed (per-platform sums may exceed global) vs session-attributed via argMin/first-event (sums add up). 95 sessions force the choice; ground truth used event-attribution.
6. **Bot/shared user 4CE58A95… (301 sessions, 95 concurrent):** exclude, cap, or keep? Dominates any user-level metric.
7. **Replay realism:** the extract has zero open sessions and cuts off at 11:30:04 UTC mid-event — the demo must define replay speed, whether to replay in event-time order (required) and how to simulate the live tail.
8. **Missing-minute semantics:** serving layer emits explicit zeros vs dashboard treats absent minutes as 0.
9. **Zombie cap policy:** cap interval contribution at T only, or also hard-cap session length (e.g. ignore >6h) — 12 sessions span >6h.
10. **Heartbeat retention:** TTL/drop the periodic trio (53.69% of rows) after MV rollup, or retain raw for reprocessing? Storage-vs-auditability tradeoff the data can't answer.
11. **Timezone of record:** store/serve UTC (recommended; IST rendering already caused a cross-investigator discrepancy) — dashboard display timezone is a product choice.

---

# Appendix: Per-Investigation Findings

## investigation_1_event_taxonomy_session_anatomy

- (a) 47 distinct (event_type, event) pairs. Non-heartbeat types are 1:1 with event: VideoSessionStart/VideoSessionStart 10,880; VideoSessionEnd/VideoSessionEnd 10,881; VideoPlay/Play 10,883; AppBackgrounded 14,700; AppForegrounded 14,321; VideoError/VideoError 293. All 41 remaining event names hide under event_type='VideoHeartbeat' (847,600 events, 93.6% of all rows).
- (a) YES, Pause/Resume exist but only inside the 'event' column under event_type='VideoHeartbeat': 'pause' 27,340 and 'resume' 31,780 (lowercase), plus 'speed-pause' 380 / 'speed-resume' 380 and 'AdPause' 45 / 'AdResume' 27. There is NO Pause/Resume event_type — any play-state machine must parse the event column.
- (a) Top heartbeat events: network-activity 177,485; buffer-health 167,460; video-resize 141,250; BufferStart 66,641; BufferEnd 66,289; video_forward 49,879; Seek 32,036; resume 31,780; network-bandwidth 30,637; pause 27,340; upshift 19,400; dropped-frames 11,089; downshift 7,294; video_rewind 6,587. Long tail includes AdSkipTrueView 1,889, download_* events, chromecast_*, premium_button_click (1).
- (b) 905,558 events; 10,866 distinct video_session_id; 9,618 distinct user_id; 3,357 distinct content_id appear in events (of 33,464 in content dim). Events per session: p50=53, p90=180, p99=434, max=1,803, min=6, mean=83.3.
- (c) ZERO sessions missing VideoSessionStart and ZERO missing VideoSessionEnd — every one of the 10,866 sessions has both. There are no genuinely open sessions in this extract; the 'open session' problem must be simulated at replay time (the dataset ends at 2026-07-26 17:00:04.847, seconds after the event finishes). However, 239 sessions (802 events) have events AFTER their VideoSessionEnd timestamp (last event: AppBackgrounded 217, VideoHeartbeat 16, AppForegrounded 6); 219 of those 239 have their last event in the 16:00 hour of 07-26, the rest scattered.
- (d) Session duration (last ts - first ts): p50=11.9 min, p90=33.17 min, p99=74.12 min, max=2,618.35 min (~43.6 h), mean=16.44 min.
- (e) session_start_epoch is perfectly clean: constant within every session (0 of 10,866 sessions have >1 distinct value) and exactly equals the VideoSessionStart event_timestamp for all 10,866 sessions (0 ms diff, 0% mismatch). It is a reliable session key companion / MergeTree sort helper.
- (f) VideoError does NOT terminate sessions: 293 VideoError events in 293 distinct sessions (exactly 1 each), and in ALL 293 cases further events follow the error; 0 sessions have VideoError as their last event. Sessions ending by last-event-type: VideoSessionEnd 10,627 (97.8%), AppBackgrounded 217, VideoHeartbeat 16, AppForegrounded 6.
- (g) Duplicates exist but are rare: 13 sessions have multiple VideoSessionStart (27 events total, all 13 are exact same-timestamp duplicates) and 14 sessions have multiple VideoSessionEnd (29 events; 10 same-timestamp, 4 with differing timestamps).
- (h) Date range 2026-07-14 21:13 to 2026-07-26 17:00. Events/day: 07-14: 152; 07-21: 31; 07-22: 4,271; 07-23: 9,723; 07-24: 10,075; 07-25: 28,681; 07-26: 852,625 (94.2% of all events). Within 07-26, hour 16:00 alone has 780,934 events (86.2% of the entire dataset) across 10,180 sessions — this is one big live-event hour plus quiet days. Peak minute: 16:29 with 18,434 events and 2,944 active sessions.
- (bonus, foreground/background) ALL 10,866 sessions contain AppBackgrounded/AppForegrounded events. 10,400 sessions are balanced (bg count = fg count), 418 have more backgrounds than foregrounds (ended while backgrounded), 48 have more foregrounds; first bg/fg event is AppBackgrounded in 10,837 sessions but AppForegrounded in 29 (a foreground with no preceding background — handle in the state machine). Max backgrounds in one session: 17.

**Anomalies:**

- Pause/Resume are lowercase 'pause'/'resume' buried in event_type='VideoHeartbeat' — the data dictionary's event_type list has no Pause/Resume type; case-sensitive matching on the event column is required (also 'BufferStart' is CamelCase while 'pause' is lowercase — casing is inconsistent across event names).
- 120 sessions (1.1%) contain MORE THAN ONE user_id (e.g. session 6D4DA9A9... has 2 user_ids, same platform IPHONE); 95 sessions span >1 platform; only 1 session spans >1 content_id. video_session_id is therefore not strictly unique per (user, platform) — dedupe/attribution must pick argMin/argMax or any().
- 239 sessions emit events after VideoSessionEnd (mostly AppBackgrounded) — VideoSessionEnd is not a hard terminator; a max-timestamp-based session close differs from an end-event-based close for 2.2% of sessions.
- Zero open sessions: the extract is suspiciously complete (every session has start AND end), so the hackathon's 'still-streaming' concurrency scenario cannot be observed at rest — it only exists mid-replay of the stream.
- Duplicate VideoSessionStart events are always exact same-timestamp duplicates (13 sessions); 4 sessions have VideoSessionEnd duplicates at DIFFERENT timestamps — 'last end wins' vs 'first end wins' changes those sessions' durations.
- Volume is pathologically skewed: 86.2% of events fall in a single hour (2026-07-26 16:00), consistent with one live sports/event stream; earlier days are 31–29k events. One session lasts ~43.6 hours (2,618 min), far beyond p99 of 74 min — likely a stuck/left-open player.
- VideoPlay count (10,883) ≈ sessions (10,866): essentially exactly one Play per session; replays/resumes are signaled via heartbeat 'resume', not additional VideoPlay events.

## investigation_2_heartbeat_cadence

- CRITICAL SEMANTICS: event_type='VideoHeartbeat' is NOT a periodic ping — it is a grab-bag of 40+ player telemetry event names (BufferStart/End, Seek, pause, resume, video_forward, upshift/downshift, network-activity, buffer-health, video-resize, download_*, Ad*, etc.). The actual periodic heartbeat is the trio {network-activity, buffer-health, video-resize} which fires as a bundle at identical millisecond timestamps: 486,195 of 905,558 rows (53.69%).
- (a) Nominal cadence is 40 seconds, NOT 60s. Per-session gaps between consecutive 'network-activity' pings (n=167,855): p50=40.00s, p75=40.01s, p90=40.01s, p95=57.98s, p99=321.24s, max=152,683.9s. Jitter at the nominal tick is tiny (66.8% of gaps land in [39s,41s); only 1.156% in [35,39) and 0.419% in [41,45)). 21.6% of gaps are 10-35s (early re-fires around player activity), 4.4% are <10s.
- (a-bis) Gaps between consecutive VideoHeartbeat events of ANY name (n=832,734): p50=0.14s, p75=10.92s, p90=40.00s, p95=40.00s, p99=48.84s, p99.9=805s, max=142,541.9s — dense sub-second bursts during buffering/seeking, with the 40s ping as the ceiling of normal behavior.
- (b) VideoSessionStart -> first heartbeat (n=10,866 sessions): p50=4.93s, p75=16.73s, p90=38.57s, p95=41.83s, p99=103.66s, max=2,813s. VideoPlay -> first heartbeat (n=10,456): p50=1.02s, p75=3.32s, p90=12.32s, p95=36.89s, p99=40.15s, max=1,027s. 410 sessions have a heartbeat-type event BEFORE the first Play (e.g. upshift during startup). 0 heartbeats precede VideoSessionStart.
- (c) Last heartbeat -> VideoSessionEnd (n=10,866): p50=0.041s, p75=0.167s, p90=9.18s, p95=29.83s, p99=407.9s, max=21,575.8s; 22 sessions have a heartbeat AFTER VideoSessionEnd (min gap -2,080.6s). SessionEnd almost always arrives immediately after the last heartbeat.
- (d) HEARTBEATS STOP WHILE BACKGROUNDED. Of 14,354 paired (AppBackgrounded -> next AppForegrounded) windows, only 2,546 (17.7%) contain ANY heartbeat-type event strictly inside, totaling 3,826 events — and 72.8% of those land within 5s of the bg edge (dominated by 'pause' x1676 and 'dropped-frames' x796, i.e. the player pausing on backgrounding). Only 234 windows (1.63%) contain the periodic trio, 409 trio events total vs ~tens of thousands expected. For windows >120s (n=4,184): 78.5% have ZERO heartbeats inside; mean 0.37 observed vs 17.9 expected at 40s cadence. Example silent windows: session 000E0056BB12...75A4 bg=1785063871709 fg=1785065314540 (1,442.8s, 0 heartbeats); session 00205B3AEAA8...3011 bg=1785064418016 fg=1785065076391 (658.4s, 0 heartbeats).
- (e) ZERO sessions (0 of 10,866) have no VideoHeartbeat-type events at all — but that is an artifact of the grab-bag typing. 1,158 sessions (10.7%) have ZERO periodic-trio pings; 74.4% of IPHONE sessions (1,139 of 1,530) lack the trio entirely (vs 0.2% on ANDROID_PHONE), i.e. the iOS client does not emit the periodic bundle. Their sequences look like: 'VideoSessionStart > AppBackgrounded > AppForegrounded > Play > pause > VideoSessionEnd'. Where the trio IS present, cadence is 40s on every platform (p50=40.00s on all 10 platforms).
- (f) Pause exists as event='pause' (27,340 rows) / 'resume' (31,780 rows), both typed as VideoHeartbeat. Across 21,216 pause->resume windows (dur p50=20.8s, p90=290.7s): 28.4% contain periodic-trio pings (25,503 trio events inside). For pause windows >120s with no backgrounding (n=875): 51.8% still receive trio pings, but at ~39% of the nominal rate (mean 4.49 observed vs 11.4 expected). So heartbeats PARTIALLY continue during foreground pause (unlike backgrounding, where they stop) — pause is not reliably detectable from heartbeat silence alone.
- (g) Heartbeat-type rows are 843,600 of 905,558 total events = 93.16% of the stream (periodic trio alone = 53.69%). Session-lifecycle events (Start/Play/End/Error) are only ~3.6%; bg/fg are 3.2%.
- (h) Legit-gap sensitivity (gaps between consecutive deduplicated heartbeat timestamps with NO AppBackgrounded and NO pause event in between; n=608,938): p90=p95=40.00s, p99=40.01s, p99.5=49.0s, p99.9=312s. Threshold cut rates: T=60s cuts 0.446% of legit gaps, T=90s cuts 0.253%, T=120s cuts 0.201%, T=150s cuts 0.177%, T=180s cuts 0.157%, T=300s cuts 0.103%. RECOMMENDATION: T=120s (= 3 missed 40s ticks). p99.5 of legit gaps is 49s so even 90s is safe at the 99.7% level; going from 120s to 180s only recovers 0.044pp more legit gaps while adding 60s of phantom 'active' time after every real stop. The residual ~0.2% above any threshold is a long-tail of genuinely stalled/offline-buffered playback, not cadence jitter.
- Data integrity notes: 10,866 distinct video_session_id; 13 sessions have 2 VideoSessionStart rows, 14 have 2 VideoSessionEnd rows; every session has >=1 start and >=1 end. Dataset spans 2026-07-14 21:13:58 to 2026-07-26 17:00:05 UTC (283.8h); 12 sessions span >6h, explaining max intra-session gaps of ~142,000s.

**Anomalies:**

- Data dictionary implied a heartbeat cadence check at 60s — actual periodic cadence is exactly 40s (p50=40.000s, sub-10ms jitter at the tick).
- event_type='VideoHeartbeat' mislabels ~47 distinct event names including user actions (pause, resume, Seek) and QoE telemetry — 'heartbeat' cannot be taken as 'proof of playback' without filtering by event name (BufferStart, pause, dropped-frames all arrive under this type while video is NOT progressing).
- iPhone client is a different animal: 74.4% of IPHONE sessions emit zero periodic-trio pings, so trio-only activity detection silently drops most iOS traffic; ANDROID/TV/web platforms emit the trio uniformly at 40s.
- 410 sessions have heartbeat-type events before the first VideoPlay; 22 sessions have heartbeats up to ~35min AFTER VideoSessionEnd (negative end-gap min of -2,080s) — end events are not a hard stream terminator.
- 13 duplicate VideoSessionStart and 14 duplicate VideoSessionEnd session ids; 12 sessions span >6 hours producing intra-session gaps up to 152,684s (~42h) — likely resumed/reused session ids across days.
- 'pause' (27,340) and 'resume' (31,780) counts are unbalanced by +4,440 resumes — resume also fires on foregrounding/buffer recovery, so pause/resume cannot be naively paired.
- Periodic pings continue during foreground pause at ~39% of nominal rate — heartbeat presence does not imply the user is watching; heartbeat absence >120s does imply not-active.

## investigation_3_background_foreground

- a) 100% of sessions contain bg AND fg: all 10,866 distinct video_session_ids have at least one AppBackgrounded (14,700 events total) and at least one AppForegrounded (14,321 events total). Zero bg-only or fg-only sessions. Modal pattern is exactly 1 bg + 1 fg (8,403 sessions, 77.3%); 2/2 in 1,397 sessions; tail up to 17/17.
- b) Pairing is mostly but not strictly alternating: 10,382 of 10,866 sessions (95.55%) are a clean bg->fg->bg->fg sequence fully closed. Anomalies: 109 double-backgrounded (bg,bg) occurrences across 101 sessions; 74 fg-with-no-open-bg occurrences across 67 sessions; 344 sessions where the final bg is never followed by fg. Of those 344, 216 have the orphan bg AFTER VideoSessionEnd (exit-to-background telemetry), and 128 have an open bg genuinely inside the session that runs to session end.
- c) Paired bg->fg window durations (14,247 windows, all non-negative): p50 = 35.1 s, p90 = 511.6 s (8.5 min), p99 = 2,164 s (36 min), max = 142,528 s (39.6 h), mean = 228.8 s. Explicit backgrounded time clipped to [SessionStart, SessionEnd] totals 54,660 minutes = 30.6% of the 178,343 naive session-minutes.
- d) 134 sessions have VideoSessionEnd fire while still backgrounded (a bg <= end_ts with no fg before end_ts); those open-bg-to-end tails have p50 = 25 s, max = 60.1 min, total 405 min. Separately, 229 sessions emit an AppBackgrounded AFTER VideoSessionEnd (239 sessions have any post-end events: 522 heartbeats in 22 sessions, 239 bg, 28 fg, 13 VideoPlay).
- e) After AppForegrounded the next heartbeat/play arrives fast: n = 13,770 fg events with a subsequent heartbeat/play; p50 = 0.91 s, p90 = 11.2 s, p99 = 213.6 s, max = 15,085 s. 82.0% within 5 s, 95.5% within 30 s.
- f) Resume-via-VideoPlay exists but is rare: of 14,293 in-session fg events, the immediate next event is VideoHeartbeat 90.1% (12,884), AppBackgrounded 612, VideoSessionEnd 413, VideoPlay only 329 (2.3%), AppForegrounded 34, VideoError 21. Only 311 fg events (2.2%) are followed by a VideoPlay within 10 s. Resume is instead signalled by the heartbeat event='resume' (31,780 occurrences vs pause 27,340).
- g) Silent gaps are real but the minority: within [start,end], inter-event gaps > 3 min number 3,607 total; 2,573 (71.3%) immediately follow an AppBackgrounded (explained), while 1,034 gaps (28.7%) across 984 sessions (9.1% of all sessions) have no preceding bg — silent backgrounding/network loss. Silent gap sizes: p50 = 6.5 min, p90 = 19.6 min, p99 = 76.6 min, max = 459 min; total silent-gap time 12,305 min.
- h) Session-minutes under three definitions: naive (SessionStart..SessionEnd) = 178,343 min; excluding explicit bg windows = 123,683 min (-54,660, -30.6%); additionally excluding silent-gap excess beyond 3 min (gap-180s per silent gap) = 114,480 min (-9,203 more, cumulative -35.8%). Explicit bg exclusion is ~6x the impact of the silent-gap correction.
- Context: 905,558 events, 10,866 sessions, span 2026-07-14 21:13 to 2026-07-26 17:00 UTC (~12 days). Session duration (start..end): p50 = 11.7 min, p90 = 32.8 min, p99 = 70.5 min, max = 2,618 min (43.6 h). Every session has >=1 VideoSessionStart and >=1 VideoSessionEnd; 13 session_ids have multiple starts and 14 multiple ends (id reuse).

**Anomalies:**

- Data-dictionary claim that bg/fg are 'not guaranteed events' is FALSE at the session level in this dataset: 100% of sessions have both. The real un-guarantee is per-window: ~9% of sessions contain a >3-min heartbeat gap with no bg event, and 4.45% of sessions have malformed bg/fg alternation.
- 229 sessions emit AppBackgrounded AFTER VideoSessionEnd (and 28 post-end fg, 522 post-end heartbeats in 22 sessions, 13 post-end VideoPlay) — event streams do not terminate cleanly at VideoSessionEnd.
- 13 video_session_ids have >1 VideoSessionStart and 14 have >1 VideoSessionEnd — session id reuse/duplication; session-scoped aggregations must tolerate multiple start/end rows.
- Extreme tails: one bg window lasts 39.6 h and one session spans 43.6 h start-to-end; naive concurrency would count such sessions as live the whole time.
- VideoPlay count (10,883) ~= VideoSessionStart (10,880): 'Play' fires once at playback start, NOT on resume-from-background (only 2.2% of fg events are followed by VideoPlay within 10 s). Resume semantics live in VideoHeartbeat event='resume' (31,780) / 'pause' (27,340) — pause/resume are heartbeat sub-events, contradicting any assumption that VideoPlay handles resumes.
- Small event-count imbalance: 14,700 bg vs 14,321 fg (379 excess bg), mostly the 344 never-closed bg (216 of them after session end).

## investigation_4_dimensions_cardinalities_join

- (a) Distinct counts over 905,558 events: platform=10, country=1, app_version=65, audio_language=41, subtitle_language=11, player_version=14, content_id=3,357, user_id=9,618, video_session_id=10,866.
- (a) Platform is heavily skewed: ANDROID_PHONE 629,646 (69.5%), SONY_ANDROID_TV 79,850, IPHONE 78,020, JIO_ANDROID_TV 56,567, Mweb 16,166, ANDROID_TAB 13,021, XIAOMI_ANDROID_TV 10,322, SAMSUNG_HTML_TV 9,969, FIRE_TV 7,260, LG_HTML_TV 4,737.
- (a) Country has exactly one value: 'india' (all 905,558 rows). It carries zero information.
- (a) app_version top values: 6.34.8 = 490,940 (54.2%), 6.34.4 = 89,349, 6.25.1 = 72,693, 3.11.1 = 46,098, 8.9.5 = 39,428; long tail of 65 total. player_version: 1.8.2 = 794,717 (87.8%), 1.1 = 76,486, plus messy strings like '3.33.50_ADE' and 'v-0.0.117.12.05.1_adNE_gaBlocked'; 1,534 rows empty.
- (b) Per-session constancy over 10,866 sessions: country varies in 0, app_version in 0, session_start_epoch in 0, content_id in 1 session (session 47523FDA... has content_ids 2078158713 and 2078157818), platform in 95 sessions, user_id in 120 sessions (same video_session_id shared by 2 users with time-interleaved events, e.g. session 8A77E210... has 2 users on IPHONE overlapping in time -> genuine session-id collisions/reuse, so (user_id, video_session_id) is the safe session key, not video_session_id alone).
- (b) subtitle_language raw-varies in 10,862 of 10,866 sessions (99.96%) but this is mostly a schema artifact: VideoSessionStart emits lowercase 'unk' (8,861) or empty '' (1,991) while all later events emit uppercase 'UNK'/'OFF'/'ENG' etc. After lowercasing + stripping the 'eng-English' suffix, only 4,340 sessions vary; after also excluding placeholder values unk/und/'', only 23 sessions show a real mid-session subtitle change. The 'OFF' vs 'off' and 'UNK' vs 'unk' pairs are pure case inconsistency across event types.
- (b) audio_language raw-varies in 8,796 sessions; excluding VideoSessionStart placeholders and case-normalizing, 2,441 vary; excluding all unk/und/'' placeholders, 1,749 sessions (16.1%) show a genuine mid-session audio-track switch (e.g. hin -> eng). Audio language is a real per-event-varying dimension; subtitle is effectively per-session-constant.
- (b) player_version raw-varies in 1,600 sessions, but 1,534 VideoSessionStart rows have empty player_version; excluding empties, only 70 sessions truly vary.
- (c) Content join coverage is 100%: 0 of 3,357 distinct content_ids in raw events are missing from content.parquet; 0 events (0.000%) would fail to enrich. Raw event content_ids span 20,971,538 to 2,078,177,474 (all fit in UInt32).
- (c/d anomaly) content.parquet has one content_id = 18446744072721897294, i.e. -987654322 stored as UInt64 (a negative id cast to unsigned); it is never referenced by events. content_id IS unique in content.parquet: 33,464 rows, 33,464 distinct ids, 0 duplicates.
- (d) video_type in content table: 'vod' 32,182, '' (empty) 1,089, 'live' 193. Among the 3,357 content_ids actually played: vod 3,206, empty 142, live 9. category: 84 distinct 5-letter anonymized codes, fairly uniform (top 'dcchh' 431, 'bhdbj' 431 ... ~400 each), no empty categories, no empty titles.
- (e) User concurrency (sweep-line over per-session [min,max] event-timestamp windows): 61 of 9,618 users (0.63%) ever have >1 overlapping session. One outlier user (4CE58A95...) has 301 sessions, 19,479 events, and up to 95 simultaneous sessions — clearly a shared/test/bot id. Excluding it: 60 users overlap, max 5 simultaneous sessions; all but 2 remaining users max out at 2.
- (f) Actual distinct (platform, country, content_id, video_type) combos = 4,349, and this exactly equals distinct (platform, content_id) combos — country is constant and video_type is a pure function of content_id. Theoretical cross product 10 x 1 x 3,357 x 3 = 100,710 (4.3% occupancy); even vs the tighter 10 x 3,357 = 33,570 platform-content grid, only 13.0% of cells occur.
- (g) Per-session-constant dims: country, app_version, platform (99.1% of sessions), content_id (all but 1), player_version (once empty session-start rows are excluded), subtitle_language (effectively, after normalization), session_start_epoch, user_id (98.9%). Per-event-varying dims: audio_language (real switches in 1,749 sessions) and of course event_type/event/event_timestamp.

**Anomalies:**

- video_session_id is NOT globally unique to one user/platform: 120 sessions span 2 user_ids and 95 span 2 platforms, with time-interleaved events (not sequential reuse). Use (user_id, video_session_id) or (user_id, platform, video_session_id) as the session key.
- subtitle_language and audio_language have case-inconsistent encoding by event type: VideoSessionStart emits lowercase 'unk'/''; other events emit uppercase 'UNK'/'OFF'/'ENG'. 'OFF' vs 'off', 'UNK' vs 'unk', 'UND' vs 'und', and 'eng-English'/'hin-hindi' suffix forms all coexist — normalization (lower + strip suffix) is required before any grouping. The data-dictionary hint about OFF/unk in early rows is confirmed as this artifact.
- content.parquet contains content_id 18446744072721897294 = -987654322 cast to UInt64; harmless (never played) but shows the source system emits negative ids.
- 1,089 content rows (142 of them actually played) have empty video_type — enrichment must handle '' as 'unknown', not assume vod/live covers everything.
- One user (4CE58A95...) is an extreme outlier: 301 sessions, 19,479 events, up to 95 simultaneous sessions — a shared/test id that will dominate any user-level concurrency metric unless capped or excluded.
- 1,534 VideoSessionStart rows have empty player_version; 1,991 have empty subtitle_language and audio_language — the session-start event fires before player/track metadata is known.
- One session (47523FDA...) carries two different content_ids — a violation of the one-content-per-session assumption, rare enough to handle with argMax/any.

## investigation_5_disorder_duplicates_watermarks

- (a) Global disorder vs arrival (file) order is extreme but ARTIFICIAL: 905,353 of 905,558 events (99.977%) arrive below the running max; 99.777% are >1min late, 97.633% >5min, 13.759% >1h, 4.065% >1day; max lateness = 1,021,562,672 ms = 283.77 hours (~11.8 days). p50 lateness 2,057,842 ms (~34 min), p99 248,490,469 ms (~69 h).
- (a-root-cause) The file is SESSION-MAJOR, not time-ordered: 10,866 distinct video_session_ids appear in only 11,242 contiguous runs (~97% of sessions are one contiguous block), and session-block position in the file is uncorrelated with session time (corr(first_row, min_ts) = -0.0097). The first session in the file starts 2026-07-26 16:03 — near the dataset MAX timestamp. So global 'lateness' measures file layout, not network late-arrival; a realistic replay must re-sort by event_timestamp.
- (b) Within-session disorder is real and pervasive: 10,828 of 10,866 sessions (99.65%) contain at least one event whose timestamp is lower than the previous event's (in file order); 63,389 events (7.0% of all rows) are locally out-of-order. Measured against the per-session running max, 137,115 events are >1min late and 99,719 are >5min late within their own session; median lateness-when-late = 70.25 s, p99 = 8,307 s (~2.3 h); max within-session lateness = 155,764,222 ms (~43.3 h, from the longest session). Example seen in raw rows: a 16:07:29 heartbeat precedes a 16:06:49 heartbeat in file order.
- (c) Exact duplicates on (video_session_id, event_type, event, event_timestamp): 905,558 rows vs 901,348 distinct keys = 4,210 duplicate rows (0.465%). Max multiplicity 6 (e.g. session 693B5A9C... network-activity at ts 1785064171052 appears 6 times); all top duplicate keys are VideoHeartbeat. Near-duplicates: 45,004 pairs of same (session, event_type, event) strictly within 1s of each other, plus the 4,210 identical-timestamp pairs. At (session, event_type) grain, VideoHeartbeat has 520,760 pairs within 1s — different heartbeat event names (video-resize, buffer-health, network-activity) routinely fire at the same instant.
- (d) Heartbeat density per session-minute: 843,600 VideoHeartbeat events fall into 135,929 (session, minute) groups; 125,159 groups (92.08%) contain >1 heartbeat; average 6.21, max 195 heartbeats in one session-minute. A minute-grain model collapses 707,671 rows — 83.89% of all heartbeats.
- (e) ZERO genuinely-live sessions: every one of the 10,866 sessions has at least one VideoSessionEnd (0 sessions with no end). 2,466 sessions have their last event within 10 min of the dataset max ts (2026-07-26 17:00:04.847), but all of them are closed. The dataset is a complete post-hoc dump, not a live tail. Note: 239 sessions have events AFTER their VideoSessionEnd (last event type: 217 AppBackgrounded, 16 VideoHeartbeat, 6 AppForegrounded).
- (f) Day-boundary crossing is rare: 16 sessions (0.147%) span a calendar-day boundary — identical count in both UTC and Asia/Kolkata. Exactly 1 session spans 3 calendar days (session F9EAD46E..., 400 events, 2026-07-24 17:13 to 2026-07-26 12:52 = 43.64 h span). p99 session span = 74.1 min.
- (g) No clock skew against session start: 0 of 905,558 events have event_timestamp < session_start_epoch. The session_start_epoch field is internally consistent.
- (h) Volume is violently skewed to one hour: dataset spans 2026-07-14 21:13:58 to 2026-07-26 17:00:04 (with NO events on Jul 15-20; only 152 events on Jul 14 and 31 on Jul 21). 2026-07-26 alone has 852,625 events (94.2%); the single hour 2026-07-26 16:00 UTC has 780,934 events (86.2% of everything). Peak hour average rate = 216.9 events/s; peak minute = 18,434 events (307.2 ev/s); peak single second = 426 events. Real-time replay must sustain ~217 ev/s for an hour with 426 ev/s bursts; at 100x: ~21,700 ev/s sustained, ~30,700 ev/s peak-minute, ~42,600 ev/s peak-second bursts.
- (bonus) Session lifecycle counts: 10,880 VideoSessionStart and 10,881 VideoSessionEnd events for 10,866 sessions — 13 sessions have multiple Starts (max 3) and 14 have multiple Ends (max 3); 0 sessions lack a Start. The 'event' column holds 47 distinct values; 'Pause' exists as lowercase 'pause' (27,340) and 'resume' (31,780) under event_type=VideoHeartbeat, not under VideoPlay.

**Anomalies:**

- The 'arrival order' premise from the data dictionary is misleading: the physical row order is session-grouped (10,866 sessions in 11,242 contiguous runs) with blocks in near-random time order (corr = -0.0097 between a session's first row number and its min timestamp). The first rows of the file are from 2026-07-26 16:03 — the last hour of the dataset.
- Every session has a VideoSessionEnd — there are zero open/live sessions at dataset end, contradicting the expectation of 'genuinely-live' sessions. Live-concurrency behavior only emerges when the data is replayed in event-time order.
- 6-day gap in the data: no events at all from 2026-07-15 through 2026-07-20; Jul 14 has only 152 events (2 sessions) and Jul 21 only 31 events (1 session) — these look like stray test/straggler sessions far outside the main Jul 22-26 window.
- 86.2% of all events (780,934) fall in the single hour 2026-07-26 16:00 UTC — the dataset is effectively one live-event spike plus a thin tail.
- 239 sessions emit events AFTER their VideoSessionEnd (217 end on AppBackgrounded, 16 on VideoHeartbeat, 6 on AppForegrounded).
- 13 sessions have duplicate VideoSessionStart (up to 3) and 14 have duplicate VideoSessionEnd (up to 3) — session lifecycle events are not unique per session.
- The 'event' column has 47 distinct values, far beyond the documented examples: pause/resume/Seek/BufferStart/BufferEnd/upshift/downshift plus download_*, Ad*, chromecast_* events all live under event_type=VideoHeartbeat. 'Pause' appears only as lowercase 'pause' (27,340 events).
- One session spans 43.64 hours (2026-07-24 17:13 to 2026-07-26 12:52) — plausibly a TV device left attached; it also drives the max within-session lateness of ~43.3 h.

## investigation_6_ground_truth_concurrency

- SEMANTICS USED (state precisely, other agents must match): all minutes are epoch-second minute starts m = floor(ts_ms/1000/60)*60. NAIVE: session counts in minute M iff toStartOfMinute(first_event) <= M <= toStartOfMinute(last_event). FOREGROUND: activity events = event_type IN (VideoSessionStart, VideoPlay, VideoHeartbeat, AppForegrounded); an activity event at time t covers minutes M with M-120s <= t < M+60s, which is exactly {m0, m0+60s, m0+120s} where m0=toStartOfMinute(t); coverage is clamped to the session's naive minute span (guarantees foreground <= naive); additionally, for each AppBackgrounded at b with next AppForegrounded at f in the same session (f=+infinity if none), minute M is excluded iff the whole minute lies inside the window (b <= M AND f >= M+60). foreground(M) = count of sessions covered-and-not-excluded at M.
- a) Peak NAIVE concurrency = 3,743 sessions at minute 2026-07-26 10:59:00 UTC (epoch 1785063540). Peak FOREGROUND concurrency = 2,970 sessions at 2026-07-26 10:56:00 UTC (epoch 1785063360). Note: all timestamps here are UTC; the local server renders them as IST (+5:30), e.g. naive peak displays as 16:29 IST.
- a) Overcount: peak-vs-peak (3743 vs 2970) = 26.03%. At the naive peak minute (10:59 UTC): naive 3743 vs foreground 2965 = 26.24%. At the foreground peak minute (10:56 UTC): naive 3708 vs foreground 2970 = 24.85%. Average overcount in aggregate session-minutes: naive 189,429 vs foreground 140,751 = 34.58%. Unweighted mean per-minute overcount (3,872 minutes with fg>0) = 107.49% — heavily skewed by low-traffic tail minutes where naive counts idle sessions; 1,383 of 5,255 naive-active minutes (26.3%) have foreground = 0 entirely.
- b) Top-5 foreground peak minutes (UTC, epoch, value): 10:56:00 (1785063360) = 2,970; 10:59:00 (1785063540) = 2,965; 10:58:00 (1785063480) = 2,940; 10:57:00 (1785063420) = 2,939; 10:55:00 (1785063300) = 2,938 — all on 2026-07-26.
- b) Per-platform foreground at the global peak minute (10:56 UTC): ANDROID_PHONE 1,818; IPHONE 362; SONY_ANDROID_TV 321; JIO_ANDROID_TV 219; Mweb 59; SAMSUNG_HTML_TV 57; ANDROID_TAB 50; XIAOMI_ANDROID_TV 41; FIRE_TV 33; LG_HTML_TV 22. Platform sum = 2,982 vs global 2,970 (12 double-counts: 95 of 10,866 sessions emit events under >1 platform — 10,961 distinct session-platform pairs).
- c) Top-3 busiest hours by avg foreground concurrency (UTC hour): 2026-07-26 11:00 = 1,874.16 avg over its 31 present minutes (data ends 11:30:04 UTC, so avg over a full 60-min denominator = 968.32; max 2,921); 2026-07-26 10:00 = 1,118.43 avg (full hour, max 2,970); 2026-07-26 09:00 = 42.30 avg (full hour, max 55).
- d) Slice peak differs from global peak: JIO_ANDROID_TV peak foreground = 230 at 10:59:00 UTC (epoch 1785063540), NOT at the global peak minute 10:56:00 where JIO has only 219 (4.8% below its own peak). Its next peaks: 229 at 11:00, 228 at 10:57. Biggest platform ANDROID_PHONE peaks at 10:56 (1,818), coinciding with (and driving) the global peak.
- e) Cost of brute force: single pass materializes 905,558 events into MergeTree, explodes to 189,429 naive session-minute rows, 149,543 distinct covered (session, minute) pairs, 46,925 excluded background (session, minute) pairs, plus a window function over 29,021 background/foreground events and a LEFT ANTI JOIN of cover vs excl. Wall time: 0.46 s to build all tables, 0.52 s including all reporting queries (chdb/ClickHouse local, single laptop). The dataset spans 12 days but 93.9% of events (849,888) and 10,524 of 10,866 sessions fall on 2026-07-26, mostly in a 2.5-hour window (09:00-11:30 UTC).
- f) Sanity checks PASS: 0 minutes where foreground > naive (the clamp of activity coverage to the session's naive span guarantees this by construction); 0 foreground minutes outside the naive minute set; max naive 3,743 and max foreground 2,970 both well under 10,866 distinct sessions.
- DELIVERABLE: /private/tmp/claude-501/-Users-dahiya-Work-sonyliv/fb664459-f44c-49cf-b6a2-4edcd8a9c7a7/scratchpad/ground_truth_foreground_per_minute.csv written via INTO OUTFILE (CSVWithNames, columns minute_ts = epoch seconds of minute start, concurrent_sessions). Exactly 3,872 data rows, all minutes distinct, range 1784043780 (2026-07-14 15:43 UTC) to 1785065400 (2026-07-26 11:30 UTC), max value 2,970. Round-trip verified: re-reading the CSV and FULL OUTER JOINing against the in-memory series yields 0 differing rows. Computation script: /private/tmp/claude-501/-Users-dahiya-Work-sonyliv/fb664459-f44c-49cf-b6a2-4edcd8a9c7a7/scratchpad/ground_truth3.py.
- Event taxonomy verified (do NOT trust the dictionary blindly): event_type VideoHeartbeat is a grab-bag of 36 distinct 'event' values including pause (27,340), resume (31,780), Seek (32,036), BufferStart/End (66,641/66,289), network-activity (177,485) — so under the event_type-based activity definition, a paused player still counts as foreground-active as long as it keeps emitting heartbeat-type telemetry. Pause exists only as event='pause' under VideoHeartbeat, never as its own event_type.
- Background/foreground pairing: 14,700 AppBackgrounded vs 14,321 AppForegrounded events — 379 background windows never close (treated as backgrounded until session end, then clamped to last event's minute). VideoSessionStart count 10,880 vs 10,866 distinct session ids (14 sessions with duplicate starts); VideoSessionEnd 10,881.

**Anomalies:**

- event_type=VideoHeartbeat contains 36 heterogeneous 'event' values (pause, resume, Seek, BufferStart/End, network-activity, download_*, Ad*, chromecast_*), so 'heartbeat' is really 'any player telemetry'; pause/resume live here, not as their own event_types — the data dictionary's flat event_type list hides this.
- 379 AppBackgrounded events (of 14,700) have no matching subsequent AppForegrounded in the same session — sessions that end while backgrounded.
- 95 sessions (0.9%) emit events under more than one platform value (10,961 distinct session-platform pairs vs 10,866 sessions), so platform is not a stable session attribute.
- 14 sessions have duplicate VideoSessionStart events (10,880 starts vs 10,866 distinct session ids); VideoSessionEnd count is 10,881.
- Extreme skew: 849,888 of 905,558 events (93.9%) and 10,524 of 10,866 sessions occur on 2026-07-26, almost all between 09:00 and 11:30 UTC; the remaining 11 days hold under 56K events. The data stops abruptly at 2026-07-26 11:30:04 UTC, truncating the busiest hour to 31 minutes.
- Longest session spans 2,620 minutes (~43.7 hours) versus p50 of 13 minutes and p99 of 71 minutes — a few marathon sessions inflate naive concurrency for hours; 26.3% of naive-active minutes have zero foreground activity.
- Local ClickHouse renders epoch timestamps in Asia/Kolkata (+5:30) by default — all reported times were normalized to UTC (naive peak 10:59 UTC = 16:29 IST); other agents must not mix the two.
- Parquet columns are Nullable (though containing no NULLs), which breaks MergeTree sorting keys unless cast with assumeNotNull — a schema-design footgun for ingestion.

