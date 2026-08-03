# DATA_DICTIONARY — the SonyLIV event stream

> **Summary:** Field-by-field reference for both the original SonyLIV files and the official 7M-event
> unseen release. The unseen raw file adds `video_resolution`; its content file adds `show_name`.
> Unknown future columns land losslessly in `extra Map(String,String)` and selected hot fields are
> promoted through aliases and named filter views. `event_timestamp` is epoch **milliseconds**.
> Background/foreground markers are not guaranteed to pair, while heartbeat gaps have a strong
> 40-second mode in both releases. The official unseen data also contains multi-incarnation session
> IDs, time-varying resolution, exact duplicates, out-of-order rows, and three quarantined timestamps.

Both files are gitignored (223 MB). Get them with `tools/fetch_data.sh` — checksum-pinned against the
[organiser repo](https://github.com/sidagarwal04/click-a-thon-2026/tree/main/SonyLiv/data).

## Raw events — `ev_raw`

| Column | Type | Notes |
|---|---|---|
| `video_session_id` | String | session-level concurrency derives from this |
| `user_id` | String | user-level concurrency derives from this (a user may have several sessions) |
| `content_id` | **Int64** | join key to `content_dim`; filter dimension. **NOT UInt64** — see trap 5 |
| `event_type` | LowCardinality(String) | see the enum below |
| `event` | LowCardinality(String) | the specific event within the type |
| `event_timestamp` | DateTime64(3) | **source is epoch MILLIS** — divide by 1000 on load |
| `platform` | LowCardinality(String) | filter dimension · 10 distinct |
| `app_version`, `player_version` | LowCardinality(String) | filter dimensions |
| `country` | LowCardinality(String) | filter dimension · **only 1 value in the provided file** |
| `audio_language`, `subtitle_language` | LowCardinality(String) | filter dimensions |
| `session_start_epoch` | DateTime64(3) | session start, repeated on every event of the session. **Stored, never modeled** — the derivation takes run starts from the min/gap-split event timestamps instead. On this file that is provably harmless (every session's value matches its `VideoSessionStart` timestamp exactly, 0 mismatches, max diff 0 ms); it is *not* a validated invariant for an unseen file ([codex-validation/002.md](codex-validation/002.md) §3.3) |
| `extra` | Map(LowCardinality(String), String) | all source columns beyond the known contract, keyed by header name; carried into accepted intervals by a deterministic per-key vote |
| `video_resolution` | String ALIAS | `extra['video_resolution']`; mandatory unseen filter dimension, 2,071 raw spellings and highly time-varying |

### `event_type` enum, with measured counts

| event_type | count | share | meaning |
|---|---:|---:|---|
| `VideoHeartbeat` | 843,600 | 93.16% | **not one signal and not a 60s beat** — 41 telemetry sub-streams under one label. See [trap 6](#trap6) |
| `AppBackgrounded` | 14,700 | 1.62% | app went to background — **not guaranteed** |
| `AppForegrounded` | 14,321 | 1.58% | app returned — **not guaranteed** |
| `VideoPlay` | 10,883 | 1.20% | playback started/resumed |
| `VideoSessionEnd` | 10,881 | 1.20% | session closed |
| `VideoSessionStart` | 10,880 | 1.20% | session opened |
| `VideoError` | 293 | 0.03% | playback error |

**How the model actually treats these** — only two things carry explicit semantics in the accurate
derivation (`sql/30_build_intervals.sql`): exact lowercase `pause`/`resume` sub-events, and
`VideoSessionEnd` (solely to set `is_open`). `VideoSessionStart`, `VideoPlay`, `AppBackgrounded`,
`AppForegrounded` and `VideoError` participate **only as generic timestamps** in the gap arithmetic —
there is no branch on any of them. That means an observed `AppBackgrounded` does not itself close
active state (it can even renew a run and earn tail grace), and an unknown new `event_type` on the
unseen day silently becomes a generic activity timestamp rather than failing for review. Deliberate
(bg/fg are not guaranteed to pair — trap 1), but it is a modeling *policy*; whether the private truth
expects immediate inactivity at a background event is an open mentor question
([codex-validation/002.md](codex-validation/002.md) §4). Of `VideoHeartbeat`'s 41 sub-event names,
only `pause` (27,340 rows) and `resume` (31,780) are matched; look-alikes such as `speed-pause`,
`AdPause` and `download_resumed` are intentionally not.

## Content dimension — `content_dim`

`content_id` · `title` · `video_type` · `category` · `extra`, with `show_name` exposed as
`extra['show_name']`. The table is small (~33K rows). A dictionary remains an optional Cloud
accelerator, but serving correctness uses `LEFT ANY JOIN content_dim FINAL`: a self-source dictionary
failed authentication on a fresh secured local ClickHouse instance, while the direct join is portable
and exposes catalog corrections immediately.

## Official unseen release — measured, not inferred

| Property | Measured result |
|---|---:|
| raw rows / sessions / users | 7,000,000 / 108,486 / 82,958 |
| content rows / used content IDs / orphans | 33,326 / 15,094 / 0 |
| declared day | 2026-07-31 |
| rows outside that date | 63,848 |
| exact duplicate rows | about 24,964 |
| physical-order backwards timestamp pairs | 355,121 global; 281,502 within session |
| session IDs with multiple start epochs / users / content IDs / platforms | 159 / 303 / 23 / 448 |
| raw resolution spellings / blank rows | 2,071 / 15,961 |
| sessions with more than one resolution | 93,205 |
| adjacent resolution changes | 440,646 |
| semantic quarantine | 3 `ts_out_of_range`; 6,999,997 accepted model rows |

The file label says one day, but timestamps span outside it. Date filters must be explicit and the
model must not derive its policy or target day from physical CSV order. Resolution attribution is an
open semantic contract: deterministic per-interval modal attribution differs from a latest-event
as-of-minute interpretation in **209,778 of 1,370,363 session-minute cells (15.31%)**. The current
filter surface uses modal attribution and keeps buckets additive; it must not be described as private
judge spot-check expectations until the organiser confirms the intended mid-minute/change semantics.

## Measured shape of the provided file

```
sessions               10,866
events                905,558        ← ClickHouse-parsed rows. `wc -l` says 905,559: that counts
                                       the CSV header. Every other number here reproduced exactly
                                       on the Cloud load; this one was the off-by-one.
span                   2026-07-14 15:43:58 → 2026-07-26 11:30:04  (283.8 h ≈ 11.8 days)
distinct content_id     3,357
distinct platform          10
distinct country            1        ← do not hard-code around this
avg heartbeats/session   77.6        ← says NOTHING about duration. See below.
session duration       p50 11.9 min · p90 33 min · p99 74 min · max 43.6 HOURS
events per session     min 6 · p50 53 · p90 180 · p99 434 · max 1,803
sessions with a background event  10,866  (ALL of them)
sessions that background and never return   418
sessions with no VideoSessionEnd        0   ← but see trap 3
```

**Correction (2026-08-01).** This block used to read *"avg heartbeats/session 77.6 ← ≈ 78 min average
session"*. That inference assumed one beat per minute, and there is no such beat — see
[trap 6](#trap6). **Measured, the median session is 11.9 minutes**, not ~78
([EXPLAINER §B.2](EXPLAINER.md)). [ADR 0003](adr/0003-hour-clipped-interval-splitting.md)'s
*"~1.3 hour crossings per session"* is derived from the same discredited ~78-minute figure and
inherits the error; it is not corrected there yet (that file is owned elsewhere) — treat the *count*
of hour crossings in ADR 0003 as unverified, while its hour-clipping **design** stands on its own.

## <a id="traps"></a>The traps

**1 · Background/foreground events do not pair.** 14,700 backgrounds vs 14,321 foregrounds — **379
unmatched**, and 418 sessions background and never come back. The dictionary says outright they
"are not guaranteed events and sometimes depend on the system." Any model that reconstructs inactivity
by blindly pairing `AppBackgrounded` → `AppForegrounded` needs a defined unmatched-marker policy.
Heartbeat gaps are the current primary signal, but that does not prove an observed background marker
should be ignored. On unseen data, removing the background gate alone changed only 3.38 active hours;
the much larger research-model difference came from heartbeat-only liveness. Evaluate those two axes
separately. Gaps do not find a pause; see trap 7.

**2 · Backgrounding is universal, not an edge case.** Every one of the 10,866 sessions has at least one
background event. Foreground-only exclusion is the entire problem, not a correction term.

**3 · The provided file has ZERO open sessions — the unseen day will have them.** The statement is
explicit: *"sessions in the dataset include ones still open when the day ends and heartbeats that keep
arriving."* Tuning on this file will not exercise that path at all. Test it by truncating the file at
an arbitrary timestamp and re-running.

**5 · `content_id` can be NEGATIVE.** `content_dim` contains exactly one row with
`content_id = -987654322` (1 of 33,464; zero such rows in the event file). A `UInt64` column fails the
load with `Code: 6 CANNOT_PARSE_NUMBER` on row 1193. Use **`Int64`**. This is a planted poison row —
assume the unseen day has one too, possibly in the *event* stream where it would also break joins.

**4 · One country, ten platforms.** `country` has a single value here, so a bug in country filtering is
invisible in testing and fatal on the unseen day. Always test filters against `platform` too.

**<a id="trap6"></a>6 · `VideoHeartbeat` is not a periodic 60-second beat.** The organiser's
`dataset_details.md` says the heartbeat "is currently passed every 1 minute"; the shipped file does
not agree. `VideoHeartbeat` is **41 distinct telemetry sub-streams** under one `event_type`. Measured
mixed together they look aperiodic (inter-arrival p50 **0.14 s**, p90 40 s, p99 49 s, rate 4.72/min) —
which is how this repo once concluded "there is no cadence". Separated, three of them are metronomes:

```
 network-activity  177,485 events   p50 = p90 = 40.0 s
 buffer-health     167,460          p50 = p90 = 40.0 s
 video-resize      141,250          p50 = p90 = 40.0 s
 network-bandwidth  30,637          ~120 s

 gap histogram over ALL within-session events — the MODE is the 40 s bucket, 100,099 gaps
```

Consequences: the cadence is **40 s**, so `GAP_S = 150` is 3.75 missed beats (not "3× a p99 of 49 s")
and `TAIL_S = 60` is 1.5 cadences, not the "one cadence" its comment claims. Which cadence the private
judge interpretation is unanswerable from the data — dossier and the exact question to ask:
[doubts/01](../doubts/01-heartbeat-cadence.md), which **supersedes Q17** in
[MENTOR_QUESTIONS.md](MENTOR_QUESTIONS.md). Do not use the heartbeat as a "reliable periodic activity
signal": gaps detect backgrounding, and pause must be subtracted explicitly (trap 7).

**7 · Heartbeats SURVIVE a pause — gaps alone cannot find it.** Backgrounded sessions drop to
0.047 events/min against 4.72/min active (a 100× drop, so a gap detects them), but **paused** sessions
still emit 0.756/min — one event every ~79 s, comfortably inside any sane gap threshold. A gap-only
model therefore counts paused time as watching, which the statement forbids. The shipped model is a
**hybrid**: gaps for backgrounding, explicit `pause`/`resume` subtraction for pausing
([ADR 0007](adr/0007-gate-answers-pause-needs-explicit-handling.md), `sql/30_build_intervals.sql`).

**8 · Identifiers and dimensions are not stable inside a session — the model votes.** In this file
120 sessions change `user_id` mid-session, 95 change `platform`, 1 changes `content_id`. The model
does **not** split an interval at the change point: each interval carries the single **dominant**
value per dimension (most frequent, deterministic value tie-break — ADR 0009). Totals stay additive
and rebuilds deterministic, but a filtered cell can disagree with true multi-bucket occupancy, and
whole-interval attribution to one user/platform is a policy, not a data-dictionary fact
([codex-validation/002.md](codex-validation/002.md) §3.2, §8.3). Related: 4,210 byte-duplicate rows
plus exactly **one** duplicate group that conflicts on `subtitle_language` — dedup is proven inert
for totals/peak but **not at filter grain** (6 attributions and three audio curves move;
`WORKTREE_QUEUE.md` Q5).

## Traffic is extremely concentrated — this is a live-event dataset

```
2026-07-26 10:00   425,108 events   ← 47% of the entire file in ONE hour
2026-07-26 11:00   374,053 events   ← another 41%
2026-07-26 09:00    17,806 events
2026-07-14         152 events, then a GAP until 07-21
```

**88% of all events fall in two consecutive hours.** This is a live-sport concurrency spike, and it is
the demo: the curve should climb steeply into 10:00 on 26 July. It also means any benchmark run on a
random hour is measuring almost nothing — always state which window a number came from.

## Loading

`tools/load.sh` handles the millisecond conversion and column typing. It expects the CSVs in `data/`
(gitignored — they are 222 MB).
