# EXPLAINER — the whole problem in layman terms

> **Summary:** A from-scratch, plain-English walkthrough of what we were asked to build and why the
> obvious approach is wrong, written for someone who has never seen the repo — a new teammate, a judge,
> or the author at hour 18. Its measurements describe the original dataset and are historical after
> the 2026-08-02 official unseen release. For current readiness, new fields and submission rules read
> Codex Validation 009; the public-repo and Team-Captain assumptions below are explicitly retired.
> Deeper treatments:
> [ARCHITECTURE.md](ARCHITECTURE.md) for the model, [adr/](adr/) for the decisions,
> [DATA_DICTIONARY.md](DATA_DICTIONARY.md) for the field-level detail.

**Status:** A–E complete, validated against commits through `cf80acc`. B is measured against a
**fresh reload of both CSVs**
into a local `csv_audit` database with every column typed `String`, so nothing was coerced or rejected
by the parser — that is how the findings marked 🔴 were found at all.

---

# A · What we were asked to build

## The business question, in one line

> *A cricket match is streaming. How many people are watching **right now**?*

That number decides how many servers to spin up, what to charge advertisers, and whether the content
is working. Per the problem statement it is "both the most-asked question in the building and one of
the hardest to answer correctly."

## Why it isn't just "count open sessions"

Because **the app being open is not the same as someone watching.**

Take one viewer, Ravi. He opens SonyLIV at 8:00pm and closes it at 9:00pm. His *session* is 60
minutes long. But:

```
8:00 ─────────────────────────────────────────────────────── 9:00
     ████████████  ▒▒▒▒▒▒▒▒  ██████████  ░░░░░░░░░░░  ████████
       watching     phone     watching     PAUSED      watching
       20 min      in pocket    10 min      15 min       5 min
                    10 min
                   (backgrounded)

     NAIVE  : "Ravi watched for 60 minutes"
     TRUTH  : "Ravi watched for 35 minutes"
```

Two different lies hide in that gap:

- at **8:25pm** the naive count says Ravi is watching — his phone is in his pocket
- at **8:45pm** the naive count says Ravi is watching — he hit pause and walked away

Multiply that across millions of viewers and you have over-sold your ad inventory and
over-provisioned your servers. **The whole problem exists to kill that over-count.**

On our actual file the over-count is not a rounding error: naive session-span counts **2,976.9 hours**
of watch time against the foreground-only model's **1,978.1 hours** — **33.6% of apparent watch time
is backgrounded or paused**. At the peak minute, 3,708 naive against **2,917** actual.

## What we are actually handed

Not a helpful `is_watching = true` column. Just a stream of breadcrumbs:

```
 Ravi's session, as events
 ────────────────────────────────────────────────────────────
 VideoSessionStart    8:00:00
 VideoPlay            8:00:03
 VideoHeartbeat       8:00:15   ┐
 VideoHeartbeat       8:00:31   ├─ "I'm still here" pings
 VideoHeartbeat       8:00:44   ┘
 ...
 AppBackgrounded      8:20:00   ← phone goes in pocket
      ( silence — the pings stop )
 AppForegrounded      8:30:00
 VideoHeartbeat       8:30:02
 ...
 pause                8:40:00   ← hits pause
 VideoHeartbeat       8:41:19   ← ⚠ the pings KEEP COMING
 VideoHeartbeat       8:42:44   ⚠
 resume               8:55:00
 ...
 VideoSessionEnd      9:00:00
```

Our job is to **reconstruct "was he actually watching?"** from those breadcrumbs — for 10,866
sessions and 905,558 events in the sample file, and for a petabyte-class stream in the design we are
asked to defend.

## What "concurrency" means, precisely

For every single minute, how many people were actively watching during it:

```
                8:00   8:10   8:20   8:30   8:40   8:50   9:00
 Ravi           ████████████         ██████████        ████
 Priya                ███████████████████████████
 Arun                        ██████████████████████████████
                ─────────────────────────────────────────────
 CONCURRENCY      1      2      2      2      2      2      1
                                  ↑
                        this curve IS the deliverable
```

From that curve you read **peak** (the highest it ever got over a range) and **average** (the area
under it ÷ the time span). And you must be able to slice it: *peak concurrency on Android, in India,
for this match, this hour.*

## The five things the organiser's spec demands

From [`upstream/`](upstream/) — the three files that are the contract, never edited:

```
 1 · INGEST         raw playback events, timestamped by when they HAPPENED
                    (not when they arrived)
        │
 2 · ENRICH         join each event to content metadata
                    content_id → title, video_type, category
        │
 3 · FILTER + CLEAN foreground-only filtering
                    deduplicate late or repeated events
        │
 4 · AGGREGATE      ┌ foreground concurrency      ← the headline
                    ├ content-level concurrency   ← demand by title
                    └ time-window trend           ← rolling / fixed windows
        │
 5 · PUBLISH        "continuously updated aggregates for downstream consumers"
```

...and running alongside all of it, a comparison the spec insists on:

```
        SESSION-AWARE                    SESSION-INDEPENDENT
   "reconstruct each viewer's       "count active viewers straight
    session, then count"             from event state, no sessions"
        accurate, expensive               cheap, approximate
              └───────────── COMPARE BOTH ─────────────┘
                  "to validate accuracy and
                   operational trade-offs"
```

## Four qualities it is graded on

| | What it means in practice |
|---|---|
| **Correct** | matches a **private** answer key we never see. Foreground-only means foreground-only. |
| **Fast** | dashboard-speed, reading from a purpose-built serving table — *not* rescanning session history per query |
| **Update-friendly** | sessions are still open and heartbeats keep arriving; absorb them **incrementally**, never by rebuilding |
| **Explained** | defend every trade-off out loud — schema, ordering keys, aggregation strategy |

Two hard constraints on top: **ClickHouse must be the primary datastore**, and we must *meaningfully*
integrate one of ClickStack / Langfuse / LibreChat — "superficial inclusion won't count."

And the sting in the tail: **an unseen day of data is released in the final hours**, and our answers
on it carry significant weight. We are not building for the file we have — we are building for a file
we have never seen. See [DATA_DICTIONARY.md#traps](DATA_DICTIONARY.md#traps).

## A in one sentence

> Turn a stream of breadcrumbs into a minute-by-minute "who is really watching" curve — fast enough
> to serve dashboards, honest enough to match a hidden answer key, and flexible enough to absorb data
> that has not arrived yet.

---

# B · What is actually in the data

> Everything below was measured on a **fresh reload of both CSVs** into `csv_audit`, every column typed
> `String` so the parser coerced nothing. Items marked 🔴 **contradict what this repo currently
> documents** and are the reason for re-reading the raw files rather than trusting the loaded tables.

## B.0 · The two files

```
 ch-hackathon-raw-data.csv      905,558 events    10,866 sessions   9,618 users
                                 13 columns · 233 MB · 2026-07-14 → 07-26

 ch-hackathon-content-data.csv   33,464 titles    4 columns · 1.2 MB
                                 only 3,357 of them (10%) are ever watched
```

`wc -l` reports one more of each — that is the CSV header. Every number in this repo is built on
**905,558**.

## B.1 · 🔴 The heartbeat has a pulse, and it is 40 seconds

[ADR 0007](adr/0007-gate-answers-pause-needs-explicit-handling.md) records the heartbeat as aperiodic —
*"bursty telemetry, p50 inter-arrival 0s, there is no cadence."* That conclusion came from measuring
all 41 `VideoHeartbeat` sub-events **mixed together**. Separated, three of them are metronomes.

```
 ALL VideoHeartbeat events, mixed:      gap p50 = 0.14 s   → "no cadence" ✗

 ONE telemetry stream at a time:
   network-activity   ●————40s————●————40s————●————40s————●    177,485 events
   buffer-health        ●————40s————●————40s————●————40s————●  167,460
   video-resize           ●————40s————●————40s————●————40s———  141,250
   network-bandwidth  ●——————————120s——————————●               30,637

        p50 = p90 = 40.0 s for each of the top three, independently

 Gap histogram over ALL events — the MODE is the 40-second bucket:
   40 s  ████████████████████████████████  100,099 gaps
    1 s  █████████████                      40,910
   30 s  ████                               14,167
```

Consequences: `GAP_S = 150` is 3.75 missed beats rather than "3× a p99 of 49 s", and `TAIL_S = 60` was
justified as "one cadence" — the cadence is **40**. Full dossier and the question to ask:
[doubts/01](../doubts/01-heartbeat-cadence.md).

## B.2 · What one session looks like

```
 events per session   min 6 · p50 53 · p90 180 · p99 434 · max 1,803
 duration             p50 11.9 min · p90 33 min · p99 74 min · max 43.6 HOURS
 zero-length 0 · single-event 0
```

🔴 [DATA_DICTIONARY.md](DATA_DICTIONARY.md) says *"avg heartbeats/session 77.6 ← ≈ 78 min average
session."* That inference assumed one beat per minute. **The median session is 11.9 minutes.**
[ADR 0003](adr/0003-hour-clipped-interval-splitting.md)'s "~1.3 hour crossings per session" inherits
the same error.

Two things are exactly reliable and can be trusted as keys:

```
 session_start_epoch  constant within all 10,866 sessions, and EXACTLY equal to
                      the VideoSessionStart timestamp (max difference: 0 ms).
                      NOT unique — 18 values are shared by 2 sessions each.
                      Currently UNUSED by the model; on the unseen day it is the
                      only reliable start for a session truncated at the window edge.

 IDs                  all 905,558 video_session_id and user_id values are 64-char
                      UPPERCASE hex, zero malformed. Lowercase one side of a join
                      and you get zero matches.
```

## B.3 · The two ways of not-watching

```
                       pings/min      median window     longest window
 ─────────────────────────────────────────────────────────────────────
 ACTIVELY WATCHING       4.72              —                 —
 BACKGROUNDED            0.047          35 seconds        39.6 hours
 PAUSED                  0.756          20 seconds        42.4 hours
```

Backgrounding suspends the app, so the player goes **silent** and a gap detector sees it. Pausing
leaves the app alive and still chattering — **one ping every ~79 s**, which slips under any sane
threshold. That asymmetry is the entire reason the model needs two signals, and it is confirmed
exactly as [ADR 0007](adr/0007-gate-answers-pause-needs-explicit-handling.md) recorded it. The
*medians* are new: most interruptions are seconds long, but the tail runs to days.

## B.4 · 🔴 `resume` is overloaded — and it is the largest open number in the model

```
 resume → resume  consecutive     9,958      ← a resume that resumes nothing
 pause  → pause   consecutive       560
 sessions whose FIRST pause/resume event is a resume     900
 pauses with no later resume at all    6,124  (22.4%)
```

`sql/30_build_intervals.sql` closes a paused window at `arrayFirst(x -> x >= p, resumes)` — the first
resume at or after the pause ([ADR 0009](adr/0009-same-second-resume-and-deterministic-attribution.md)
made the comparison inclusive; it was a strict `>`). If that resume is spurious (fired by a seek or
buffer recovery), the window closes early and the remainder is booked as watch time.

Measured end to end over the real file:

| rule | paused time counted |
|---|---|
| **A — shipped** (close at first resume) | **816.1 h** |
| **B** (a burst of resumes is one un-pause) | **1,005.2 h** |
| **difference** | **189.2 h — 9.6% of the 1,978.1 h we report** |

> The **189.2 h** is a separately measured pause-ledger figure from
> [doubts/02](../doubts/02-resume-semantics.md), taken before ADR 0009. It is kept as measured; only
> the **ratio** is recomputed here, because the denominator moved 1,949.3 h → 1,978.1 h (9.7% → 9.6%).

That is **nearly double** the unclosed-pause question that ADR 0007 calls "the single largest
unresolved number in the model." It is not. This is. Dossier:
[doubts/02](../doubts/02-resume-semantics.md).

The bg/fg ledger is imperfect too: **109** `bg→bg` and **45** `fg→fg` illegal same-state transitions
across 132 sessions.

## B.5 · Sessions do not stop when they end

```
 239 sessions emit 802 events AFTER their own VideoSessionEnd
 worst case 2,080.6 s late (~35 min)

 what arrives late:  239 × AppBackgrounded  ← EXACTLY ONE per straggler session
                     275 × network-bandwidth   88 × Seek     43 × pause
                      38 × resume              28 × AppForegrounded
                      13 × VideoPlay        ← an "ended" session starts PLAYING
```

The `AppBackgrounded` count is a discovered *pattern*, not noise: the app fires "end", then fires
"backgrounded". And **4 sessions carry two genuinely different `VideoSessionEnd` timestamps**, up to
11 minutes apart — for those, "when did this session end" has no single answer.

## B.6 · It is one day, not twelve

```
 07-14 │▏                                                        152
 07-15 │  ┐
  ...  │  ├─ SIX DAYS WITH ZERO EVENTS
 07-20 │  ┘
 07-21 │▏                                                         65
 07-22 │▎                                                      6,025
 07-23 │▎                                                      8,195
 07-24 │▍                                                     11,136
 07-25 │█                                                     30,097
 07-26 │████████████████████████████████████████████████    849,888   93.85%

 inside 07-26:  10:00 → 425,108   11:00 → 374,053   (file ends 11:30:04)
                two clock hours = 799,161 events = 88.25% of everything
```

Any benchmark run on a randomly chosen hour measures almost nothing. Every latency number must state
its window.

## B.7 · 🔴 The filter dimensions are not normalised

```
 audio_language — 41 values. Hindi is FOUR of them:
   hin 610,889 │ HIN 69,033 │ hin-hindi 23,095 │ hin-Hindi 507   = 703,524 rows
   jap 1,374 and jpn 386 are both Japanese
   -soundhandler (13 rows) is not a language
   '' empty 1,991

 subtitle_language — 11 values, 91.6% sentinel
   UNK 753,258 │ UND 63,768 │ off 28,982 │ OFF 10,842 │ unk 9,902 │ und 58 │ '' 2,006

 player_version — _ADE/_adE, _ADNE/_adNE     app_version — 5.0.36 vs 5.0.36.00
 platform       — Mweb is mixed-case; the other 9 are UPPER_SNAKE
 country        — ONE value, 'india', lowercase. A filter bug here is INVISIBLE.
```

`WHERE audio_language = 'hin'` returns 610,889 of 703,524 Hindi rows. **This lands directly on
ADR 0008**, which promotes these four columns to filter dimensions — the key-order and row-count
analysis there is sound, but the *values* going into those keys need a normalisation decision first.

**Decided in [ADR 0011](adr/0011-normalise-filter-dimensions-at-query-time.md)** — storage stays raw,
normalisation is a query-time rule (`sql/15_normalise.sql`). At the graded grain the hole is bigger
than the row counts suggest: peak Hindi concurrency is **1,791** as shipped and **2,213** normalised,
**+23.6%**, and at the peak minute `= 'hin'` returns 1,781 of 2,210 Hindi viewers. The **total peak
stays 2,917 either way** — normalisation can only relabel an interval, never move one. Two of the
figures above need a correction: Japanese is *four* values (`jap`, `jpn`, `JPN`, `jpn-japanese`), and
`player_version`'s `_ADE`/`_adE` are **not** case twins — they are different releases, and no two
`player_version` values collide under `lower()`. Mentor dossier: [doubts/04](../doubts/04-dimension-normalisation.md).

> **Re-measured 2026-08-01 on the post-ADR-0009 model.** ADR 0011 branched from `8af15cb`, so the
> figures it records (1,768 → 2,180, **+23.3%**; 1,758 of 2,174; total peak 2,887) were taken under
> the same-second tie bug. Re-run against the current `session_intervals` the shape is unchanged and
> the hole is marginally wider: **1,791 → 2,213, +23.6%**. The ADR is left as written — it is a dated
> record of the decision, and the decision does not turn on the third significant figure.

## B.8 · The content catalog

```
 33,464 titles · content_id is a true primary key (33,464/33,464 unique)
 0 orphans — every event's content_id has a catalog row  ✓ (true of THIS file, not a contract)
 poison row -987654322 exists, has 0 events, and kills a UInt64 column

 video_type   vod 32,182 (96%) │ '' EMPTY 1,089 (3.25%) │ live 193 (0.6%)
              → 25,810 events (2.85%) land on the nameless third bucket

 title is NOT a key   2,773 titles shared by 2–4 content_ids
                      1,418 collisions span multiple CATEGORIES
                      → v_concurrency_minute_title merges distinct assets
                      → 568 of 3,325 SERVED titles (17.1%) name >1 asset,
                        incl. the #1 title 'wekek ked' (peak 433: live+vod)
```

Dossier: [doubts/03](../doubts/03-content-catalog.md).

**Since handled** ([ADR 0010](adr/0010-content-views-are-database-agnostic-and-label-their-ambiguity.md)):
the blank `video_type` is labelled `'(blank)'` — kept distinct from `'(unknown)'`, which means a
dictionary *miss* and nothing else — and `v_concurrency_minute_title` now carries
`catalog_content_ids` so a merged label cannot be read as one asset. Same ADR fixed a
cross-database leak: those views hard-coded `dictGet('sonyliv.dict_content', …)`, so on the unseen
day they would have answered from **production's** catalog.

## B.9 · Duplicates, ordering, and ties

```
 4,209 byte-identical duplicate rows                            (0.46%)
 4,210 duplicates on (session, ts, event_type, event)
       the +1 is the ONE group that differs — in subtitle_language, UNK vs OFF
 863 sessions affected · up to 6 copies of one event

 THE FILE IS NOT TIME-SORTED
   71,171 timestamp inversions in physical read order
   63,334 of them INSIDE a single session

 23.67% of adjacent event pairs share the EXACT SAME MILLISECOND
```

`evidence/dedup.txt` proves the duplicates are inert for concurrency. The **ties** are the live hazard:
the model truncates to whole seconds before splitting runs, so ties are denser still, and
`sql/90_reconcile.sql` already carries a scar from two orderings resolving them differently.

## B.10 · Scorecard

| | |
|---|---|
| **Confirmed exactly** | 0 orphans · poison row · 0 negative clock skew · `session_start_epoch` reliable · the 0.047 / 0.756 / 4.72 asymmetry · 88% in two hours · 4,210 duplicates · `pause`/`resume` lowercase only, under `VideoHeartbeat` only |
| 🔴 **New, and it moves the model** | 40-second cadence exists → `TAIL_S` reasoning is wrong · `resume` overloaded → 9.6% · ~~dimensions un-normalised~~ (fixed, ADR 0011) · ~~23.67% same-millisecond ties~~ (the pause-rule tie fixed, ADR 0009) · title collisions |
| 🔴 **Our docs were wrong** | ~~"≈78-minute average session" (11.9 min median)~~ · ~~"no cadence exists" (40 s)~~ · ~~"one outlier user with 297 sessions" (301)~~ — all three corrected at `6877e87` |
| **Definitions need pinning** | "backgrounds and never returns" = 418 (count-based) or 344 (last-event-based)? Both appear in our docs. |

**B in one sentence:** the data has a hidden 40-second heartbeat we told ourselves did not exist, a
`resume` event that means four different things, and filter dimensions where one language is spelled
four ways — and none of those three were in our docs before this pass.

# C · What we built, what is broken, and how accurate it really is

## C.1 · The machine, in one picture

```
   ch-hackathon-raw-data.csv                    ch-hackathon-content-data.csv
            │ 905,558 events                              │ 33,464 titles
            ▼                                             ▼
     ┌─────────────┐                              ┌──────────────┐
     │   ev_raw    │                              │ content_dim  │──▶ dict_content
     └──────┬──────┘                              └──────────────┘   (COMPLEX_KEY_HASHED,
            │                                                          signed keys)
            │ ① "when was each viewer ACTUALLY watching?"
            │    runs split on 150s gaps  MINUS  explicit pause windows
            ▼
     ┌──────────────────────┐
     │  session_intervals   │  30,323 rows · one row per active stretch
     └──────┬───────────────┘  all 7 raw dimensions (ADR 0008)
            │
            │ ② "turn stretches into +1 / −1, clipped to each hour"
            ▼
     ┌──────────────────────┐
     │   cc_minute_delta    │  28,074 rows ← THE SERVING LAYER
     └──────┬───────────────┘  concurrency = running sum WITHIN the hour
            │
     ┌──────┴───────┬──────────────┬────────────────┐
     ▼              ▼              ▼                ▼
 cc_hour_agg   9 window views   content views   v_concurrency_*
 peak+integral  rolling 5/15/60  by title /       the curve a
 8-level cube   tumbling, ragged  category         chart reads

 ── separately, straight from ev_raw ──
 cc_minute_stateless  ← the session-INDEPENDENT baseline
 cc_user_minute       ← distinct USERS per minute (uniqExact)
```

Why this shape at all:

```
 explode every session to one row per ACTIVE minute        148,900 rows   <- measured
 our delta serving layer                                   28,073 rows
                                                              5.3× smaller

 (a naive dense grid of every session x every minute of the 12-day span would be
  185,015,382 rows — but no implementation would ever build that, so quoting it
  as the comparison overstates the win. 5.3× is the honest number.)
```

## C.2 · Layer by layer

**① `session_intervals` — "when was this person really watching?"** Sort a session's events, cut
wherever silence exceeds `GAP_S = 150 s` (a backgrounding), then subtract the explicit pause windows.

```
 raw events   ●●●● ●●●   ·  ·  ·  ·  ·   ●●●●  ●●[pause]·······[resume]●●●
                          gap > 150s                paused window
              └─── run 1 ───┘            └────────── run 2 ──────────────┘
              └─ interval ─┘             └─ interval ─┘      └─interval─┘
```

Two signals because [§B.3](#b3--the-two-ways-of-not-watching) proved they are opposites. Intervals
rather than per-minute rows because per-minute explosion is the collapse mode the problem statement
names by hand.

**② `cc_minute_delta` — the serving layer.** `+1` when an interval opens, `−1` when it closes,
**clipped at every hour boundary** ([ADR 0003](adr/0003-hour-clipped-interval-splitting.md)):

```
 an interval running 20:59 → 22:04

   UNCLIPPED   +1 @20:59 ..................... −1 @22:05
               to read 21:30 you must sum from t=0. Partition pruning is useless.

   CLIPPED     hour 20 │ +1 @20:59   (survives the hour — no close emitted)
               hour 21 │ +1 @21:00   (fresh open)
               hour 22 │ +1 @22:00 … −1 @22:05
               ↑ every hour is now ABSOLUTE and standalone
```

Two payoffs: no query scans from the beginning of time, and peak becomes summable *across time*, so a
day-grain peak reads 24 stored rows instead of 1,440 minutes.

**③ `cc_hour_agg` — an 8-level cube, because peak does not add up.**

```
 true peak, all platforms      2,917
 sum of per-platform peaks     2,988   (+2.4%)
 sum of per-content peaks      5,680   (+94.7%)
```

Each of the 8 dimension subsets gets its own separately-computed curve and a genuine peak. Nothing is
derived from anything else.

> **Re-measured 2026-08-01** against the post-ADR-0009 model (the previous reading — 2,887 / 2,945 /
> 4,433 — was taken before the tie fix). The per-**content** figure moved far more than the headline
> did (+28% against the headline's +1.04%), and that is expected rather than alarming: it is a sum of
> **3,357 independent maxima**, and **2,827 of them peak at exactly 1** (298 at 2, 232 at ≥3), so
> restoring active time to a long tail of near-empty contents bumps many of them by +1 at once. Mean
> per-content peak went 1.32 → 1.69. The point the number exists to make — *peak
> does not add up, and per-content is where it fails worst* — got stronger, not weaker. Query:
>
> ```sql
> WITH expanded AS (
>   SELECT video_session_id, platform, content_id,
>          arrayJoin(range(toUInt32(toStartOfMinute(interval_start)),
>                          toUInt32(toStartOfMinute(interval_end)) + 1, 60)) AS m
>   FROM session_intervals FINAL)
> SELECT (SELECT max(c) FROM (SELECT m, uniqExact(video_session_id) AS c FROM expanded GROUP BY m)),
>        (SELECT sum(p) FROM (SELECT platform,   max(c) AS p FROM (SELECT platform,   m, uniqExact(video_session_id) AS c FROM expanded GROUP BY platform,   m) GROUP BY platform)),
>        (SELECT sum(p) FROM (SELECT content_id, max(c) AS p FROM (SELECT content_id, m, uniqExact(video_session_id) AS c FROM expanded GROUP BY content_id, m) GROUP BY content_id));
> ```

**④ Both mandated models, side by side.** `cc_minute_delta` (session-aware) reads **2,917** at the peak
minute; `cc_minute_stateless` (session-independent) reads **2,894**, unmoved by ADR 0009 — it has no
pause rule to fix. The comparison is structural, not bolted on.

> **The sign of that gap flipped, and the doc used to read it wrong.** Before ADR 0009 the peak minute
> was 2,887 aware vs 2,894 stateless, and this section described the difference as "the excluded
> background and paused time" — one-directional. It never was. Measured across the 3,820 minutes both
> models cover: **session-aware is higher on 449, stateless is higher on 498, and they agree on
> 2,873.** The two differ in *both* directions because they miss different things — stateless counts
> only minutes carrying an actual heartbeat (so it loses the `TAIL_S` lease at a session's tail),
> while session-aware credits that lease but subtracts pause explicitly. At the peak minute the fix
> moved aware from 7 *below* stateless to **23 above** it.

## C.3 · Does it handle what §B found?

| §B finding | Handled? | By what |
|---|---|---|
| Pause looks different from background | ✅ | the hybrid rule — the core design |
| Background/foreground do not pair | ✅ | we never pair them; gaps are primary |
| 4,210 duplicate rows | ✅ | **proven inert**, not patched — `evidence/dedup.txt` |
| Negative `content_id` | ✅ | `Int64` end to end + complex-key dictionary |
| Zero orphans today | ✅ | `LEFT` semantics + `'(unknown)'` default for the unseen day |
| Open sessions | ✅ | `is_open` + the truncation harness manufactures the case |
| Late arrivals | 🟡 | ADR 0006 arithmetic exact — only inside the isolated test |
| Peak not summable | ✅ | the 8-level cube, measured not asserted |
| 23.67% same-millisecond ties | ✅ | the same-second **tie in the pause rule** is fixed — [ADR 0009](adr/0009-same-second-resume-and-deterministic-attribution.md), `0c0f020`. Dimension attribution is now a deterministic dominant-value rule on all 7, so ties no longer decide labels |
| **40-second cadence** | ❌ | `TAIL_S = 60` still assumes a cadence that does not exist |
| **`resume` overloaded (9.6%)** | ❌ | still closes at the first resume |
| **Un-normalised dimensions** | ✅ | [ADR 0011](adr/0011-normalise-filter-dimensions-at-query-time.md) — query-time rule in `sql/15_normalise.sql`, `ac04975` |
| **Title collisions** | 🟡 | `v_concurrency_minute_title` still merges distinct assets; [ADR 0010](adr/0010-content-views-are-database-agnostic-and-label-their-ambiguity.md) **labels** the ambiguity (`v_content_title_collisions`, 2,773 titles over 5,729 `content_id`s) rather than resolving it |

## C.4 · Accuracy has three different answers

**Level 1 — is the arithmetic self-consistent? Exactly yes.**

```
 delta layer  vs  interval expansion    3,732 minutes   0 mismatches   ← re-run 2026-08-01
 hour tier    vs  minute tier              98 hours     0 mismatches
 incremental  vs  full rebuild          1,578 minutes   0 mismatches   ← pre-ADR-0009, not re-run
 window views vs  brute-force join       every window   0 mismatches
```

Line 1 was re-run against the current model (it read 3,725 minutes before ADR 0009 — the tie fix
changes which minutes carry active intervals, not whether the two tiers agree):

```sql
SELECT count(), countIf(ifNull(s,0) != e), max(abs(ifNull(s,0) - e)), max(e)
FROM      (SELECT minute, toInt64(concurrent) AS e FROM v_concurrency_minute_intervals) AS ex
LEFT JOIN (SELECT minute, toInt64(concurrent) AS s FROM v_cc_minute_series_total)       AS se USING (minute);
-- 3732 | 0 | 0 | 2917
```

**Level 2 — does the gate prove that? It did not. It does now (`81c0161`).**

The unseen-day rehearsal found the gate was worth far less than it looked. `sql/90_reconcile.sql`
hard-coded five `2026-07-26` timestamps, so on any other day it returned **zero rows** — and
`tools/reconcile.sh` decides the verdict with `grep -q MISMATCH`:

```
 zero rows  →  no MISMATCH string  →  exit 0  →  "reconcile PASSED"
 minutes actually compared: 0.      verdict printed: PASS.
```

It was blind a second way: truth was a `GROUP BY` over a `CROSS JOIN`, so a minute where nobody was
watching emitted no row and could not disagree — 207 of 1,364 on the holdout day. And nothing asserted
*how much* had been checked; on a one-day 07-26 file it silently returned four rows instead of five.

All three are closed and each was negative-tested:

```
 target minutes   now DERIVED from ev_raw          → 1,364 minutes on the holdout day
 idle minutes     now a DENSE SPINE, served as a running sum along it
                  → the fabricated-500 insert that used to PASS now fails with
                    25 mismatched minutes, max_abs_diff 500
 coverage         a SUMMARY row carries minutes_compared; reconcile.sh fails if
                  it is missing or zero rather than treating silence as success

 coverage on production:   5 minutes  →  17,028 minutes.   Still zero mismatches.
```

Evidence: `evidence/unseen-rehearsal.txt` for the discovery, `81c0161` for the fix.

**Level 3 — do we match the private answer key? Unknown, with a measured envelope.**

```
                                    1,978.1 h  ← what we report today
     resume semantics (doubts/02)   −189.2 h   9.6%    MEASURED
     unclosed pause  (ADR 0007)     + 99.3 h    —      SUPERSEDED, see below
     TAIL_S 60 vs 40 (doubts/01)    ≤ 170.9 h  8.6%    UPPER BOUND
```

The two `h` figures that survive are **measured numerators kept as measured**; only their ratios are
recomputed, because the denominator moved 1,949.3 h → 1,978.1 h.

**The unclosed-pause row is not simply out of date — it is unrecoverable without a re-run.** The
99.3 h was the *difference* between a conservative arm (1,949.3 h) and a permissive arm (2,048.6 h),
both measured at `cf80acc`, i.e. **both under the same-second tie bug**. ADR 0009 supersedes the
conservative arm; the permissive arm has never been re-run on the fixed derivation. Subtracting the
new conservative number from the old permissive one would invent a delta across two different
derivations, so the figure is struck rather than rescaled. Re-measuring it needs a rebuild with
`UNCLOSED_PAUSE_TO_RUN_END = 0` — filed in [TODOS.md](../TODOS.md).

These are **definitional forks**, not bugs — and the gate cannot see any of them, because it recomputes
truth using the same definition it is testing. A 9.6% error passes every test we own, silently.

A fourth, from the same adversarial pass: a **day-file answers differently from a full-context build**
(7 sessions straddle midnight on 2026-07-26; 1,140 events would be dropped by a same-shaped cut), and
both builds' gates say PASS because each recomputes truth from its own `ev_raw`. *The gate proves the
pipeline, never the input.*

## C.5 · What is broken, ranked

**Nine of the thirteen closed between `8af15cb` and `1fb6351`.** Fixed rows keep their number so the
ranking stays citable; four remain genuinely open.

| # | Fault | Why it matters | State |
|---|---|---|---|
| — | ~~Gate passes vacuously off-day~~ | zero-minute PASS on the graded input | ✅ fixed `81c0161` |
| — | ~~Gate blind to idle minutes~~ | fabricated 500 → PASS | ✅ fixed `81c0161` |
| 1 | ~~**Same-second tie bug**~~ | `toUnixTimestamp` truncates to seconds, then strict `>` skipped a resume in that second — **2,697 of 27,340 pauses (9.86%)**. `90_reconcile.sql` carried the identical expression, so the gate agreed with it | ✅ fixed **[ADR 0009](adr/0009-same-second-resume-and-deterministic-attribution.md)** `0c0f020` — `>=` in **both** files. **This is what moved the headline: PEAK 2,887 → 2,917, 1,949.3 h → 1,978.1 h** |
| 2 | ~~`interval-math` skill teaches the discarded model~~ | *"Emitted every 60s"*, no pause — agents write SQL from it | ✅ fixed `6877e87` — the skill now teaches the gap-minus-pause rule and the measured 40 s cadence |
| 3 | ~~**Un-normalised dimensions**~~ | `WHERE audio_language='hin'` misses Hindi viewers | ✅ fixed **[ADR 0011](adr/0011-normalise-filter-dimensions-at-query-time.md)** `ac04975` — query-time rule in `sql/15_normalise.sql`; re-measured peak Hindi **1,791 → 2,213** |
| 4 | **`any()` — derivation fixed, delta layer not** | ADR 0009 moved `user_id`, `content_id`, `platform`, `country` onto ADR 0008's dominant-value rule and **proved determinism end to end** (one hash at `max_threads` 1/8/32, was three). But **`sql/40_deltas.sql` still runs `any(platform)`, `any(country)`, `any(content_id)`** over `session_intervals`, re-introducing the non-determinism one layer up *and* collapsing the new per-interval attribution back to one value per session | 🟡 **partly fixed** — ADR 0009 files the remainder explicitly as out of scope. **Last `any()` in the pipeline** |
| 5 | ~~`DATA_DICTIONARY` — *"periodic, every 60s"*, *"≈78 min average session"*~~ | both disproven in §B | ✅ fixed `6877e87` — both corrected in place, with the correction dated |
| 6 | ~~`MENTOR_QUESTIONS` calls unclosed-pause the largest unresolved number~~ | `resume` is ~2× bigger on hours | ✅ fixed `6877e87` — it now ranks Q3 `resume` semantics first |
| 7 | ~~`TESTS.md` still says absorption **"FAIL as shipped"**~~ | fixed at `388a845`, test repaired at `1dee090`; evidence reads `CONVERGES` | ✅ fixed `6877e87` |
| 8 | **`TAIL_S = 60` contradicts its own justification** | the cadence exists and is 40 s | **open** — upper bound ≤ 170.9 h (8.6%) |
| 9 | ~~`45_user_concurrency.sql` stale comments~~ | `ReplacingMergeTree(interval_end)`; "297 sessions" (301) | ✅ fixed `6877e87` |
| 10 | **Peak minute ambiguous under ties** | hour tier said 16:35, answer phase said 16:59 | **open** — the serving tiers (`50_hour_agg.sql`, `85_windows.sql`) carry an earliest-wins tie-break, but `sql/90_reconcile.sql:216` still picks the peak minute with a bare `argMax(minute, truth)` |
| 11 | **`v_concurrency_minute_title` merges distinct assets** | **2,773** colliding titles spanning **5,729** `content_id`s (re-measured) | 🟡 **labelled, not resolved** — [ADR 0010](adr/0010-content-views-are-database-agnostic-and-label-their-ambiguity.md) adds `v_content_title_collisions` and documents the trap; the view still merges |
| 12 | ~~`sql/80_content.sql` hard-codes `sonyliv`~~ | its views read **production's** dictionary from any other database — exactly the shape of the unseen-day run in `sonyliv_unseen` | ✅ fixed **[ADR 0010](adr/0010-content-views-are-database-agnostic-and-label-their-ambiguity.md)** `370a74c` — views are unqualified and bake in their creating database |
| 13 | ~~A CSV reload **doubles** the data · `CH_DATABASE` silently ignored~~ | load-path defects, both recorded in [`SESSION-2026-08-01.md`](SESSION-2026-08-01.md) §6 | ✅ fixed `6355048` — loader guard (`evidence/load-guard.txt`) + `CH_DATABASE` precedence |

**The unclosed-pause rule — both of its numbers are now superseded.** It was left open on an *hours*
difference, and `cf80acc` measured the number that is actually graded, the **peak**:

```
 conservative (shipped)   2,887          permissive   3,018      ← BOTH measured at cf80acc,
                                                     ─────         BEFORE the ADR 0009 tie fix
                                          +131 viewers · +4.5%
```

**Neither figure is current and the comparison must not be patched by halves.** ADR 0009 moved the
conservative arm to **2,917**; the permissive arm has not been re-run, so the `+131 / +4.5%` spread is
stale in a way no arithmetic here can repair — writing "2,917 vs 3,018" would silently compare two
different derivations. The numbers above are therefore left exactly as `cf80acc` measured them and
labelled as historical. What survives unchanged is the *structural* result: it is one constant
(`UNCLOSED_PAUSE_TO_RUN_END`) rather than an open question, and the gate *catches* a model-only flip
(240 mismatched minutes) because it shares the **spec** but not the **code**. Default stays
conservative: under-counting is visible and explainable; over-counting invents viewers that
demonstrably were not receiving playback events. Re-measuring the permissive arm is filed in
[TODOS.md](../TODOS.md).

## C.6 · What is not built

```
 🟡 CONTINUOUS PUBLISHING   still the biggest scored gap — we batch-rebuild with `make model`,
                            and only mv_stateless and mv_user_minute are real MVs.
                            BUT the native answer is now VALIDATED, not theoretical:
                            refreshable MVs work on this service (verified independently —
                            allow_experimental_refreshable_materialized_view=1 and
                            stop_refreshable_materialized_views_on_startup=0). One created
                            in a scratch database populated itself in 8 seconds, 1,579 rows,
                            with no scheduler and no application code. See
                            docs/IMPROVEMENTS.md. It makes PUBLICATION automatic, not the
                            DERIVATION incremental — which is still the difference between
                            "rebuilt when someone remembers" and a stated freshness SLA.
 ❌ HOT TIER                BLOCKED, not unbuilt — ADR 0005 needs an operator decision.
 🟡 STRAGGLER PATH          arithmetic proven; not wired into a live path.
 ❌ /bench                  evidence/bench.txt and evidence/benchmark/ both MISSING.
 ❌ DECK · VIDEO · SUMMARY  none started.        ✅ LICENSE   ✅ README
 ❌ SUBMISSION PACKAGE      hosted demo/video/team folder/PR not yet complete.
```

**C in one sentence:** the model is arithmetically exact and the design is defensible, but the gate
that proves it **passes on zero rows** the moment the date changes, and three unanswered definitional
questions put a **±10% envelope** around the headline number that no test we own can detect.

# D · Why this approach, and what we rejected

## D.1 · The five forks

**Fork 1 · "How do we know someone stopped watching?"** Pairing `AppBackgrounded → AppForegrounded`
was rejected: 14,700 vs 14,321 → 379 never pair, and the organiser's own doc calls them "not
guaranteed." Heartbeat gaps were chosen ([ADR 0001](adr/0001-heartbeat-gaps-over-background-events.md))
— then immediately amended, because gaps catch backgrounding (silence) but **never** fire on a pause
(0.756 pings/min slips under any threshold). The answer is a **hybrid**, and it only exists because we
measured before building. A gap-only model would have shipped, passed every test, and been ~10% wrong.

**Fork 2 · "How do we store who was watching when?"**

```
 A  one row per (session, active minute)        ~185,000,000 rows   ✗
 B  an interval array per session               awkward to query    ✗
 C  +1 when a stretch opens, −1 when it closes       ~28,000 rows   ✓
```

**Fork 3 · "Does the running total carry across hours?"** Unclipped means every query scans from `t=0`
and partition pruning becomes decorative; snapshot checkpoints mean more state to get wrong.
Hour-clipping makes the carry-in problem *disappear* rather than be managed, and makes peak summable
across time ([ADR 0003](adr/0003-hour-clipped-interval-splitting.md)).

**Fork 4 · "What physical order for the raw events?"** This overturned our own earlier decision
([ADR 0002](adr/0002-order-by-time-bucket-then-platform.md)):

```
                              session-first   hour-first     hour-first is
   one-hour time slice        849,888 rows      434,176      2.0× better
   hour + platform filter     849,888 rows       49,152     17.3× better
   full interval rebuild      905,558 rows      905,558      IDENTICAL
```

The locality argument was wrong because our rebuild touches *all* sessions — it scans everything either
way, so ordering is irrelevant to it, while every dashboard query filters by time and often platform.

**Fork 5 · "What happens when data arrives late?"** `ALTER … UPDATE` is a heavy async mutation with no
read-your-writes; rebuilding the partition is literally the "recompute" answer the scoring criterion
penalises. Correction-by-diff ([ADR 0006](adr/0006-late-arrival-correction-by-diff.md)) recomputes one
session and appends the negation of its old deltas — *exactly as correct as a full rebuild, because it
is a rebuild, of one session.*

## D.2 · Measured, then rejected

**The projection — measured, rejected, then re-measured when the code changed.** ADR 0002 named the
remedy for the access pattern it gave up: add a `PROJECTION` by `video_session_id`. We built it and
measured **27.7×** on a single-session lookup. Then we measured the *actual* access path of the day —
the straggler query used `IN (subquery)`, which full-scans anyway — so the real gain was **1.00×** for
**+94% storage**, and we rejected a recommendation our own ADR had made.

**Then ADR 0013's finalizer changed the access pattern**, and the number had to be taken again rather
than inherited. On the finalizer's real query shape the same projection measures **12.8×** — it reads
0.9% of `ev_raw` instead of 11.6% — for **+91% storage**. Still not shipped: the storage cost is
unchanged and the finalizer is not deployed to `sonyliv`. The point is the discipline, not the verdict:
a measurement is only valid for the query shape it was taken on, and ours stopped being valid the
moment the finalizer landed.

**Dedup — proven unnecessary rather than bolted on.** The full derivation was run twice in one query,
raw vs `LIMIT 1 BY` the event key, with `any()` pinned to `min()` so dedup was the only variable:
identical 30,769 intervals, **0 of 3,725 minutes differ**; restricted to only the 863 duplicate-bearing
sessions so it could not wash out, 834 minutes, 0 differing. *"We proved the step unnecessary" is a
stronger answer than "we added the step."* (`evidence/dedup.txt`)

> **Counts as measured at `4a89399`, before ADR 0009** — the current model has 30,323 intervals over
> 3,732 minutes. The experiment has not been re-run, and the counts are kept rather than substituted.
> The *conclusion* is unaffected by the tie fix: both arms of that run share whatever pause rule is
> in force, so the fix moves both identically and cannot turn a 0-row difference into a non-zero one.

**`any()` — rejected after it turned out to be picking a sentinel.** Collapsing a session's dimensions
with `any()` looked like a tie-break detail; the code comment called it "accurate for 98.8%". Measured
in `8bfeeb2`, it was not: the player emits a sentinel *before* it resolves a track — `VideoSessionStart`
carries a sentinel `subtitle_language` on **10,880 of 10,880 sessions** — so `any()` picks the sentinel
more often than the truth. **44.5% of `audio_language` and 47.6% of `subtitle_language` attributions
wrong** across 139,800 session-minute cells, and **73.5% wrong at the graded peak minute**. Worse, it is
**non-deterministic**: the same data at `max_threads` 1/8/32 produced three different hashes, so two
rebuilds would serve two different filtered answers. Replaced with dominant-value-per-interval,
tie-broken by value → 3.3% and 1.8%, and identical hashes across thread counts and a full rebuild.
*(Now applied to **all 7** dimensions in the derivation — [ADR 0009](adr/0009-same-second-resume-and-deterministic-attribution.md), `5743b39`. `sql/40_deltas.sql` is the one layer still on `any()`; see §C.5 fault 4.)*

**And the extensibility claim is a hard bound, not a hopeful measurement.** `cc_minute_delta` stores at
most one open and one close per (merged run, hour), so its size is capped at **36,930 rows on this file
no matter how many dimensions exist**. Three dimensions used 24,951 (67.6% of the ceiling); seven used
28,139 (76.2%) at `8bfeeb2`, and **28,074 (76.0%) on the current model** — ADR 0009 redistributed
dimension tuples without changing the bound. A hundred could not exceed 36,930. That is what makes *"the solution should work even
if the number of dimensions increases"* true rather than aspirational — and it only holds because the
serving layer is deltas rather than a per-minute explosion, which has no such ceiling.

**Three more, each with a number:** the gap-only model (heartbeats survive a pause at 0.756/min);
`uniq` HyperLogLog (1–2% error against an *exact* private key); `SummingMergeTree` over a distinct
count (measured **9×** over-count, 45,000 vs a truth of 5,000).

## D.3 · Small choices that would have broken silently

| Choice | What the obvious alternative does |
|---|---|
| `Int64` for `content_id` | `UInt64` dies at row 1193 on the planted `-987654322` |
| `COMPLEX_KEY_HASHED` dictionary | plain `HASHED` keys on `UInt64` *regardless of declared type* → `Code: 70` |
| `SimpleAggregateFunction(sum, Int64)` | `UInt64` **wraps** a negative correction; `sum()` stays right by modular arithmetic **so the bug hides**, `max()` returns 1.8e19 |
| `ReplacingMergeTree(build_version)` | `(interval_end)` keeps the largest end — but re-derivation can **shrink** an interval, so a stale row wins forever |
| `RANGE` window frames | `ROWS` — the delta layer stores only *change* rows, so "5 rows back" is not "5 minutes back" |
| `min_bytes_for_wide_part = 0` | compact parts report per-column compression as **0** — an evidence slide of zeros |
| load over **stdin** | `file()` cannot read a bind mount *and does not exist on Cloud*, the graded target |

## D.4 · The one thing deliberately not built

The **hot tier** ([ADR 0005](adr/0005-heartbeat-lease-semantics.md)). Each heartbeat grants a 150 s
lease; concurrency is the count of live leases. Provably equivalent to the gap model in the interior —
**and the gap model is exactly what ADR 0007 discarded.** *Equivalence to a discarded model is not a
correctness argument.* Exposure: 21,068 pause windows covering 834 h against 1,949 h of counted watch
time — the same order of magnitude as the answer.

Three ways out: pause-terminated leases need the cross-block state ADR 0004 exists to avoid; negative
lease rows are impossible because `uniqExact` has no subtraction; **relabelling it honestly as the
session-independent upper bound is free** — and is one of the two models the spec mandates comparing
anyway. That is the call awaiting a human.

## D.5 · The pattern

```
 sort key        settled by  17.3× / 2.0× / identical
 gap vs hybrid   settled by  0.047 vs 0.756 vs 4.72 pings/min
 version column  settled by  316 intervals, +37 on the peak
 the projection  settled by  27.7× bench → 1.00× (old shape) → 12.8× (finalizer shape)
 dedup           settled by  0 of 3,725 minutes
 hot tier        settled by  834 hours of exposure
```

Not one was settled by argument, and four times the measurement overturned the plan — twice
overturning *our own* prior decision. The defensible story is not "we designed it well" but **"we kept
trying to disprove it, and here is the list of times we succeeded."** Which is also why §C stings: the
same discipline applied to the *gate* found it passing on zero rows.

# E · What is proven, what is only claimed, and what is missing

## E.1 · Proven — run, evidenced, reproducible

| Claim | The number | Evidence |
|---|---|---|
| Load is exact | 905,558 events = source rows · 33,464 titles | re-confirmed by the fresh reload |
| Serving layer == interval expansion | **3,732 minutes, 0 mismatches**, peak 2,917 | re-run 2026-08-01 · §C.4 |
| Hour tier == minute tier | **98 hours, 0 mismatches** | `sql/50_hour_agg.sql` |
| The 8-level cube | 26,162 rows, **0 peak + 0 integral mismatches** | `sql/50_hour_agg.sql` |
| Incremental absorption converges | **1,578 minutes, 0 mismatches** after the version fix | `evidence/truncation.txt` — pre-ADR-0009, not re-run |
| Dedup is inert | 0 of 3,725 min; **0 of 834** on duplicate-bearing sessions alone | `evidence/dedup.txt` — pre-ADR-0009 counts, see §D.2 |
| Window views | rolling + tumbling vs brute force, **0 mismatches** | commit `4a89399` |
| Peak is not summable | +2.4% (platform), **+94.7%** (content) | re-measured 2026-08-01 · §C.2 |
| Sort key choice | **17.3×** on the dashboard shape | [ADR 0002](adr/0002-order-by-time-bucket-then-platform.md) |
| Serving beats expansion | 299 KB / 23 ms vs 2.55 MB / 56 ms — **8.5×** | TODOS H3 |
| Two-signal asymmetry | **0.047 / 0.756 / 4.72** pings/min | [ADR 0007](adr/0007-gate-answers-pause-needs-explicit-handling.md) |
| Straggler tail | 239 sessions, max **2,081 s** late | ADR 0007 |
| Charts show real data | HyperDX, peak day in 1 h buckets: 3 → **2,917** → 2,873; **14 ms**, 28,074 rows | re-taken 2026-08-01 · [CLICKSTACK.md](CLICKSTACK.md) |
| Runs on a *different* day | **47 s** for 30,097 events, all 8 phases | `evidence/unseen-rehearsal.txt` |
| The gate *can* fail | bad delta row → exit 1 · fabricated 500 → MISMATCH | two negative tests |
| The 40-second cadence | p50 = p90 = **40.0 s** on three streams | §B.1 · [doubts/01](../doubts/01-heartbeat-cadence.md) |
| `resume` overload | **189.2 h · 9.6%** (measured h, ratio rebased) | §B.4 · [doubts/02](../doubts/02-resume-semantics.md) |
| Same-second tie bug — **fixed** | 2,697 of 27,340 pauses (9.86%) · **PEAK +30, hours +28.8** | [ADR 0009](adr/0009-same-second-resume-and-deterministic-attribution.md) `0c0f020` |
| Gate coverage after `81c0161` | **5 → 17,028 minutes**, zero mismatches, negative-tested | commit `81c0161` |
| Unclosed-pause cost **at the peak** | conservative 2,887 vs permissive **3,018** — **+4.5%**. ⚠️ **historical**: both arms pre-ADR-0009, spread not re-measured | commit `cf80acc` · §C.5 |
| `any()` was picking sentinels | **44.5%** audio / **47.6%** subtitle attributions wrong; **73.5%** at the graded peak minute — and non-deterministic across thread counts | commit `8bfeeb2` |
| Dimension count has a **hard row ceiling** | `cc_minute_delta` ≤ **36,930** rows *regardless of how many dimensions* — 3 dims 24,951 (67.6%), 7 dims 28,139 (76.2%) at `8bfeeb2`, **28,074 (76.0%) today**. Whole table 111 KiB | commit `8bfeeb2` · row count re-measured 2026-08-01 |
| The ADR 0008 ceiling **holds at 100×** | 4,086,387 rows against a ceiling of 4,606,268 — **88.7%**, and the headroom *widens* with scale (96.0% at 1×, 93.2% at 10×) | `evidence/scale.txt` |
| The model runs at **100× the provided file** | 89,850,838 events · 1,086,600 sessions · peak **251,668** · gate PASSES on all **6,799** minutes | `evidence/scale.txt` |
| Day-grain peak is **scale-invariant** | **176 KiB read at 1× and at 100×**, ~2 ms — the hour tier reads 8,192 rows either way | `evidence/scale.txt` |
| What breaks first: **derivation memory** | 4.48 GiB of a 5.56 GiB server at 100×; `Code: 241` at default settings. Not the parts (28 of 3,000), not the dictionary (**17.00 MiB at every scale**) | `evidence/scale.txt` |
| Thread count is a **memory multiplier** | 10 threads 4.48 GiB / 73.4 s · 2 threads **2.59 GiB / 50.5 s** — fewer threads is leaner *and* faster once the stage is memory-bound | `evidence/scale.txt` |

## E.2 · Claimed, but not proven

```
 "our answers match an unavailable answer key"
     ✗  UNPROVABLE without the key. Envelope ±10% across three definitional
        forks, none of which any test we own can detect.

 "make reconcile proves we are correct"
     ✅ WAS proven false (zero rows → PASS off-day); FIXED in 81c0161.
        Coverage 5 → 17,028 minutes, idle minutes included, minutes_compared
        asserted. Still cannot see a DEFINITIONAL error — it recomputes truth
        from the same spec it is testing.

 "the model absorbs late data incrementally"
     🟡 TRUE in an isolated database. No live path: no finalizer, no watermark
        advance, no trigger. `make model` rebuilds.

 "dashboard-grade latency from a serving layer"
     ✗  NO /bench. evidence/bench.txt and evidence/benchmark/ do not exist.

 "designed for petabyte scale"
     🟡 MEASURED at 10× and 100× — evidence/scale.txt. 89.85M events,
        1,086,600 sessions, peak concurrency 251,668, and the gate still
        PASSES on all 6,799 minutes. Serving stays cheap: day-grain peak is
        FLAT at 176 KiB / ~2 ms from 1× to 100×.
        But the interval derivation does NOT fit at default settings at 100×
        (Code: 241, 5.56 GiB budget) and needs spill + max_threads=2.
        Still a 10-core docker box, not a petabyte.

 "filter-friendly across business dimensions"
     ✅ FIXED in ADR 0011 (ac04975). hin / HIN / hin-hindi / hin-Hindi fold to
        one bucket through a query-time rule; peak Hindi 1,791 → 2,213.

 "content-level concurrency by title"
     ✗  2,773 titles merge 2–4 content_ids, 1,418 across categories. ADR 0010
        LABELS this (v_content_title_collisions); the view still merges.
```

**The defect this section used to hold has been fixed.** `sql/30_build_intervals.sql` truncated to
whole seconds (`toUnixTimestamp`) and then closed a pause with a strict
`arrayFirst(x -> x > p, resumes)`, so a resume landing in that same truncated second was **invisible**
and the pause ran on to the next resume — or became unclosed and ate the rest of the run.

```
 pauses with a resume in the same truncated second   2,697   (9.86%)
 paused time excluded, shipped   (strict >)          834.1 h
 paused time excluded, inclusive (>=)                792.6 h
                                                     ───────
 over-excluded by the tie                             41.5 h
```

`sql/90_reconcile.sql` contained the **identical expression**, so the gate reproduced the bug and
agreed with it — an independent *implementation*, but not an independent *definition*.
[ADR 0009](adr/0009-same-second-resume-and-deterministic-attribution.md) (`0c0f020`) changed both
files to `>=`. **End to end that is PEAK 2,887 → 2,917 and 1,949.3 h → 1,978.1 h** — larger than the
41.5 h raw ledger figure suggests, because much of that time was already excluded by the gap rule, and
because a segment that now ends at `run_end` earns the `TAIL_S` grace it previously did not. Note the
direction: it pushed the opposite way to the `resume`-overload fork, so the two partially masked each
other, which is why the totals had looked unremarkable.

## E.3 · Knowingly missing

```
 🔴 THE REPO IS PRIVATE     verified: gh repo view d-cryptic/clickathon → isPrivate true.
                            The rules require it PUBLIC at submission and through
                            judging. A missing/private repo is a zero on a required
                            artifact — the highest-consequence open item here.
 ❌ CONTINUOUS PUBLISHING   spec step 4 · the biggest scored gap · we batch-rebuild
 ❌ HOT TIER                blocked on one human decision (ADR 0005 option 3 is free)
 ⏸ /bench                  PARKED BY THE OPERATOR, with a reason: the benchmark query
                            set is not in hand, so the grains would be guesswork.
                            (Counter worth weighing: `.claude/commands/bench.md` already
                            anticipates this — "generate those shapes from the statement
                            and say clearly that they are our reconstruction". Bytes-read
                            on our own shapes is still evidence where we have none.)
 ❌ DECK · VIDEO · SUMMARY  none started          ✅ LICENSE  ✅ README
 ❌ SUBMISSION PACKAGE      hosted demo/video/team folder/PR not yet complete
```

The three mechanical defects recorded in [`SESSION-2026-08-01.md`](SESSION-2026-08-01.md) §6 that used
to belong here are **all fixed**: the CSV reload that doubled the data and the silently-ignored
`CH_DATABASE` at `6355048` (guard evidence in `evidence/load-guard.txt`), and
`sql/80_content.sql`'s hard-coded `sonyliv` at `370a74c`
([ADR 0010](adr/0010-content-views-are-database-agnostic-and-label-their-ambiguity.md)) — which
mattered because its views read production's dictionary from any other database, exactly the shape of
the unseen-day run (`sonyliv_unseen`).

Three more improvements not tracked elsewhere: **`session_start_epoch` is never used** by the model,
though it is the only exactly-reliable start signal (0 ms deviation across all 10,866 sessions) and is
precisely what a session truncated at the window edge needs; and `cc_minute_stateless` remains at
**3 dimensions** while `cc_minute_delta` now carries **7**, so the mandated session-aware vs
session-independent comparison can only run at the coarser grain.

**Scale evidence now exists** (`evidence/scale.txt`, `tools/scale-test.sh`) and it moved one item off
this list and put a new one on. The new one: `sql/30_build_intervals.sql` is a single
`GROUP BY video_session_id` holding a `groupArray` of every event timestamp per session, and at 100×
that is the only thing in the pipeline that does not fit — 4.48 GiB against a 5.56 GiB server, failing
outright with `Code: 241` when ingest merges are still running. It is not an algorithmic problem: time
is linear, and capping `max_threads` to 2 cuts peak memory 4.48 → 2.59 GiB **and** the runtime
73.4 → 50.5 s, because each aggregation thread keeps its own hash table. The production fix is to
derive in session-hash shards rather than in one pass; the one-line fix is the thread cap.

## E.4 · What we can honestly say today

> *"We built a foreground-only concurrency model on ClickHouse that excludes backgrounded and paused
> time. We proved the exclusion matters — 33.6% of apparent watch time, and a 21.3% over-count
> eliminated at the peak minute. The serving layer is an hour-clipped delta table, 5.3× smaller than
> per-minute expansion of the active ranges, and it reconciles exactly against raw events on every one of 17,028 minutes.
> Every design decision was settled by a measurement, and four overturned our own prior plan. We know
> of three definitional questions we cannot resolve without the answer key, we have measured what each
> is worth, and we can show the envelope."*

Every sentence there is backed. What we **cannot** say is "it is fast" (unmeasured against the real
benchmark set) or "our gate proves it" (it does not — it cannot see a definitional error).

"It scales" is no longer unmeasured, and the honest version has two halves. **Serving scales**: at 100×
the file the day-grain peak still reads 176 KiB, the gate still passes on every minute, and the
delta table sits *further* below its ceiling than at 1×. **Building does not, unattended**: the
interval derivation is the one stage whose memory is set by distinct sessions rather than by rows,
and at 100× it needs its thread count capped to fit. Both numbers are in `evidence/scale.txt`.

## E.5 · Highest grade-change per hour

```
 ✅ FIX THE GATE          DONE in 81c0161. Coverage 5 → 17,028 minutes.
 ✅ TIE BUG               DONE in 0c0f020 (ADR 0009). `>` → `>=` in BOTH
                          30_build_intervals and 90_reconcile — they share the
                          SPEC, so both moved together. PEAK 2,887 → 2,917.
 ✅ any() ON THE LAST 4   DONE in 5743b39 (ADR 0009). One hash at max_threads
                          1/8/32, was three. Peak and hours unmoved, as expected.
 ✅ NORMALISE DIMENSIONS  DONE in ac04975 (ADR 0011). Query-time rule.

 0  PACKAGE THE SUBMISSION          self-contained team folder, hosted demo,
                                   video, deck and mandatory PR. This development
                                   repository is not required to be public.
 1  RESUME RULE           ~1 h     up to 189.2h / 9.6%. Now the largest open
                                   number by some distance. Needs the mentor
                                   answer (doubts/02) or a stated, measured
                                   default.
 2  any() IN 40_deltas    ~30 min  the LAST any() in the pipeline. ADR 0009
                                   fixed the derivation and filed this; the
                                   delta layer still re-introduces it.
 3  RE-MEASURE PERMISSIVE ~20 min  the unclosed-pause spread (2,887 vs 3,018)
                                   is stale on BOTH arms — rebuild with
                                   UNCLOSED_PAUSE_TO_RUN_END=0 to restore it.
 4  DECK                  starts at H18 regardless of code state.

 ⏸ /bench                 parked by the operator — see E.3 for the reasoning
                          and the counter-argument.
```
