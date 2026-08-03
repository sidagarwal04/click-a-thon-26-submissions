# Briefing: Visualizing Foreground-Only Concurrency (SonyLIV / Click-a-thon 2026)

**Purpose of this file.** Hand this to Claude Desktop as a self-contained brief. It has no access to our repo or the 232 MB dataset, so every number, event trace, and data table it needs is embedded here verbatim. All figures come from the real 905,558-event dataset unless explicitly marked as illustrative.

**What we want out of it:** a set of visuals that make a non-specialist understand *why* counting "sessions that are open" is wrong, and *how* we arrive at the true number. See [§9 Build brief](#9-build-brief).

---

## 1. The question in one sentence

> **"How many people are watching right now?"**

Sounds trivial. It is not, because *a session being open is not the same as a person watching.* People pause. People background the app. Phones lose signal. The session stays nominally open the whole time.

Our job: count only the minutes where someone was **genuinely watching** — foreground, playing, alive.

---

## 2. What the data looks like

Two CSV files.

### `ch-hackathon-raw-data.csv` — 905,558 rows, one row per event

Real rows (truncated for width):

```csv
content_id,video_session_id,user_id,event_type,event,event_timestamp,platform,country,audio_language
21311522,94D660E9F4...,7C7D3C6272...,VideoSessionStart,VideoSessionStart,1785062007336,JIO_ANDROID_TV,india,hin
21311522,94D660E9F4...,7C7D3C6272...,VideoPlay,Play,1785062009028,JIO_ANDROID_TV,india,hin
21311522,94D660E9F4...,7C7D3C6272...,VideoHeartbeat,upshift,1785062011289,JIO_ANDROID_TV,india,hin
```

| Field | Meaning |
|---|---|
| `video_session_id` | One person watching one video. The unit of concurrency. |
| `event_type` | 7 values only: `VideoSessionStart`, `VideoPlay`, `VideoHeartbeat`, `AppBackgrounded`, `AppForegrounded`, `VideoSessionEnd`, `VideoError` |
| `event` | The *specific* thing that happened. **This is where the important signals hide.** |
| `event_timestamp` | **Epoch milliseconds.** Not a date string. |
| `platform`, `country`, `audio_language`, … | Filter dimensions |

### `ch-hackathon-content-data.csv` — 33,464 rows

`content_id`, `title`, `video_type` (`vod` / `live`), `category`. Joins cleanly — all 3,357 content ids seen in events resolve.

### Dataset shape

- **905,558 events · 10,866 sessions · 3,357 videos**
- 94% of events fall on **2026-07-26**; a thin tail runs back to 2026-07-14
- Session length: median **11.9 min**, p90 33 min, max 43.6 h

---

## 3. The crux: what a "heartbeat" actually is

This is the single most misunderstood part, and the best candidate for a visual.

### What you'd expect

A heartbeat is a periodic "I'm still here" ping. The data dictionary says it fires **every 60 seconds**.

### What is actually true

**Both halves of that are wrong.**

**(a) `VideoHeartbeat` is not one signal — it is an envelope for 41 different things.**

Buffering, bitrate changes, screen resizes, seeks, ad events, downloads — all typed `VideoHeartbeat`, distinguished only by the `event` column. Critically, **`pause` and `resume` live in here too.** They are not their own `event_type`.

> ⚠️ **The classic fatal bug:** filter on `event_type` alone and you never see a pause. Every paused minute silently counts as watching.

**(b) The real cadence is 40 seconds, not 60.**

Four `event` values fire on a hard metronome. Measured across the full dataset:

| event | gaps measured | p25 | p50 | p75 | % at exactly 40s |
|---|---|---|---|---|---|
| `video-resize` | 133,459 | 40.0 | 40.0 | 40.0 | **83.2%** |
| `buffer-health` | 157,878 | 40.0 | 40.0 | 40.0 | **71.2%** |
| `network-bandwidth` | 27,379 | 40.0 | 40.0 | 40.0 | **70.8%** |
| `network-activity` | 167,855 | 32.0 | 40.0 | 40.0 | 66.6% |

Three of them have p25 = p50 = p75 = 40.0. That's not a distribution, it's a clock.

We call these four the **beacon**. Everything else under `VideoHeartbeat` is event-driven noise.

**Why it matters:** our inactivity timeout is derived as *two missed beacons* ≈ **90–100 seconds**. Anyone trusting the documented 60s picks a timeout that a single dropped beat trips, cutting live viewers off the count.

### (c) The finding that breaks the obvious approach

The natural instinct is: *"no heartbeat ⇒ not watching."* So just look for gaps.

**That does not work, and here is the measurement.** For inactive spans of ≥80 seconds (long enough that ≥2 beacons should have landed):

| Inactive because… | Spans | Went fully silent | Median span |
|---|---|---|---|
| **App backgrounded** | 5,167 | **5,071 — 98.1%** ✅ | 245s |
| **Player paused** | 5,668 | 3,153 — **only 55.6%** ❌ | 202s |

**When the app is backgrounded, the beacon stops. When the player is merely paused, it keeps ticking 44% of the time.**

So:

- Gap detection catches **backgrounding** almost perfectly.
- Gap detection is **blind to nearly half of all pauses** — the phone sits there transmitting "buffer-health, buffer-health, buffer-health" to a paused screen.

This is *the* insight of the whole problem. A visual contrasting these two timelines side by side would carry the entire explanation.

---

## 4. How we decide someone is watching

Three independent mechanisms. **None is sufficient alone.**

```
active  =  NOT backgrounded          <- gap rule catches this (98% reliable)
       AND NOT paused                <- ONLY explicit pause/resume markers catch this
       AND beacon seen within 100s   <- catches death, crash, network loss
```

| Mechanism | Detects | Signal used |
|---|---|---|
| **Gap rule** | Backgrounding, crashes, network death | Time since last event > 100s → close interval at `last_event + 30s` |
| **Pause state machine** | Paused playback | `pause` / `resume` in the `event` column |
| **Background state machine** | App backgrounding (explicit) | `AppBackgrounded` / `AppForegrounded` in `event_type` |

### One trap worth drawing

`pause` and `resume` **do not pair up.** There are 27,340 pauses and 31,780 resumes, and 34% of resumes have no open pause before them. `resume` doesn't mean "the pause ended" — it means "playback is running", and it fires after foregrounding, after buffering, after ads, and sometimes several times in a row.

**Therefore: treat them as idempotent state assignment, never as a counter or a stack.**

```
pause  → state = PAUSED     (already paused? no-op)
resume → state = PLAYING    (already playing? no-op)
```

Six consecutive resumes must be a no-op — not a counter sitting at −5, which would mark the session permanently, wrongly active.

---

## 5. Worked example — one real session, traced end to end

This is a genuine session from the dataset. **It is the best single teaching artifact we have.**

`E2C349A12096F9D3…` · platform `ANDROID_PHONE` · content `2078158754` · 25 events over 1,174.6 seconds (19.6 minutes)

Timestamps are seconds since session start. `★` marks a 40-second beacon.

| t (s) | event_type | event | | What's happening |
|---|---|---|---|---|
| 0.0 | VideoSessionStart | VideoSessionStart | | session opens |
| 0.9 | VideoPlay | Play | | ▶️ **watching starts** |
| 1.0 | VideoHeartbeat | upshift | | bitrate up |
| **7.3** | VideoHeartbeat | **pause** | | ⏸️ **user pauses — watching stops** |
| 41.0 | VideoHeartbeat | video-resize | ★ | beacon… while paused |
| 41.0 | VideoHeartbeat | buffer-health | ★ | |
| 41.0 | VideoHeartbeat | network-activity | ★ | |
| 81.0 | VideoHeartbeat | video-resize | ★ | |
| 121.0 | VideoHeartbeat | video-resize | ★ | |
| 161.0 | VideoHeartbeat | video-resize | ★ | |
| 201.0 | VideoHeartbeat | video-resize | ★ | |
| 241.1 | VideoHeartbeat | video-resize | ★ | |
| 281.1 | VideoHeartbeat | video-resize | ★ | |
| 321.1 | VideoHeartbeat | video-resize | ★ | |
| 361.1 | VideoHeartbeat | video-resize | ★ | |
| 401.1 | VideoHeartbeat | video-resize | ★ | |
| 441.1 | VideoHeartbeat | video-resize | ★ | **11 beacons, still paused** |
| 475.9 | AppBackgrounded | AppBackgrounded | | 📱 app backgrounded |
| *(670 seconds of total silence — no events at all)* |
| 1145.8 | AppForegrounded | AppForegrounded | | app returns |
| 1147.4 | VideoHeartbeat | resume | | ▶️ **watching resumes** |
| 1165.9 | VideoHeartbeat | pause | | ⏸️ pauses again |
| 1166.4 | AppBackgrounded | AppBackgrounded | | |
| 1170.1 | AppForegrounded | AppForegrounded | | |
| 1170.2 | VideoHeartbeat | resume | | ▶️ |
| 1174.6 | VideoSessionEnd | VideoSessionEnd | | session closes |

### The derived answer

| Active interval | Duration |
|---|---|
| `[0.0s → 7.3s)` | 7.3s |
| `[1147.4s → 1165.9s)` | 18.5s |
| `[1170.2s → 1174.6s)` | 4.4s |
| **Total genuinely watched** | **30.2 seconds** |

### The three ways to count it

| Method | Result | Error |
|---|---|---|
| **Naive** — session start to session end | 1,174.6s (19.6 min) | **39× too high** |
| **Gap-rule only** — ignore pause markers | 534.6s (8.9 min) | **18× too high** |
| **Correct** — all three mechanisms | **30.2s** | ✅ |

Note the middle row. Adding gap detection cuts the error by half — and still overstates by 18×, because those eleven beacons between 41s and 441s look exactly like a healthy, watching viewer. **Only the `pause` marker at 7.3s reveals the truth.**

This one session is the whole argument. A timeline visual of it — event ticks along the top, three shaded "active" bands underneath, three counting methods compared — would be the centerpiece.

---

## 6. From intervals to a concurrency curve

Once each session is a set of active intervals, concurrency is a counting problem.

### The delta trick

Don't write a row for every minute a session is active — that explodes. Instead, record only the **changes**:

```
For each active interval [start, end):
    +1  at  minute(start)
    -1  at  minute(end)
```

Concurrency at any minute = **running total of all deltas up to that minute.**

### Illustrative worked example

*(Small made-up numbers, purely to show the mechanic.)*

Three sessions:

```
Session A   active 10:01 ────────── 10:04
Session B   active 10:02 ──── 10:03
Session C   active 10:03 ────────────── 10:06
```

Deltas:

| minute | deltas | running total = **CCU** |
|---|---|---|
| 10:01 | +1 (A) | **1** |
| 10:02 | +1 (B) | **2** |
| 10:03 | −1 (B), +1 (C) | **2** |
| 10:04 | −1 (A) | **1** |
| 10:05 | — | **1** |
| 10:06 | −1 (C) | **0** |

**Peak = 2** (at 10:02 and 10:03). **Average** over 10:01–10:06 = (1+2+2+1+1+0)/6 = **1.17**.

### Why deltas, and not a row per minute

1. **Small.** A 40-minute session is 2 rows, not 40.
2. **Additive.** Deltas can be summed across time *and* across dimensions, which is what makes filtered queries correct.
3. **Updatable.** A session that's still running gets a provisional `−1` at the current watermark. When new heartbeats arrive, emit `+1` at the old watermark (cancelling it) and `−1` at the new end. Corrections just get appended — nothing is ever rewritten.

### The one thing that does NOT work

> **Peak cannot be pre-computed per filter.**

If Android peaks at 10:05 and Hindi-audio peaks at 10:41, then "Android **and** Hindi" may peak at 10:23 — a third minute entirely, not derivable from either. So we always store the **per-minute series** and take `max()` *after* filtering. Average is friendlier: it's just total watch-time ÷ minutes, which does compose.

---

## 7. Real results from the full dataset

Applying the three-mechanism rule to all 10,866 sessions:

| Metric | Naive (session open) | **Foreground-only** | Inflation |
|---|---|---|---|
| **Peak concurrent users** | 3,743 | **2,937** | **1.27×** |
| **Total watch-time** | 2,977 hours | **1,796 hours** | **1.66×** |

Two things worth showing:

- **21.5% of the naive peak isn't watching.** One in five "viewers" at the busiest moment of the day is paused or backgrounded.
- **40% of total session time isn't watching.** The watch-time error (1.66×) is much larger than the peak error (1.27×), because inactive stretches are spread across the session rather than concentrated at the peak.
- Both methods peak at the same minute here (**10:59 UTC**) — but that's luck, not a rule, and it will not hold once you filter by dimension.

---

## 8. Real curve data — ready to plot

Minute-by-minute, the peak hour of 2026-07-26. **This is real output from our pipeline.** The gap between the two lines is the story.

```csv
minute,naive_ccu,foreground_ccu
10:29,151,95
10:30,387,357
10:31,647,633
10:32,837,796
10:33,1050,962
10:34,1238,1123
10:35,1452,1323
10:36,1634,1488
10:37,1807,1612
10:38,1966,1751
10:39,2140,1882
10:40,2295,2004
10:41,2448,2138
10:42,2615,2261
10:43,2754,2353
10:44,2877,2404
10:45,2974,2441
10:46,3096,2559
10:47,3201,2630
10:48,3268,2702
10:49,3333,2693
10:50,3407,2754
10:51,3469,2752
10:52,3527,2815
10:53,3590,2803
10:54,3653,2878
10:55,3683,2901
10:56,3708,2920
10:57,3722,2899
10:58,3729,2885
10:59,3743,2937
11:00,3723,2858
11:01,3694,2888
11:02,3647,2860
11:03,3613,2788
11:04,3589,2798
11:05,3511,2667
11:06,3474,2656
11:07,3402,2655
11:08,3344,2580
11:09,3268,2505
11:10,3163,2442
11:11,3051,2361
11:12,2965,2282
11:13,2868,2211
11:14,2767,2186
11:15,2671,2096
11:16,2536,1955
11:17,2426,1894
11:18,2304,1795
11:19,2181,1706
11:20,1999,1583
11:21,1829,1424
11:22,1670,1322
11:23,1492,1142
11:24,1320,1079
11:25,1132,912
11:26,944,779
11:27,740,617
11:28,511,460
```

Note the shape: the two lines are nearly identical during the ramp-up (everyone who just opened the app is actively watching) and diverge as the event matures and people start pausing and backgrounding. That divergence widening over time is itself a finding worth drawing attention to.

---

## 9. Build brief

Please build an **interactive, self-contained HTML artifact** that teaches this. Priority order:

### Must have

1. **Session timeline (the centerpiece).** Visualize the §5 session. Events as ticks on a time axis, colour-coded by kind (session boundary / beacon / pause-resume / background-foreground). Below it, three horizontal bars showing what each counting method believes was "watch time" — naive (full width), gap-rule-only, and correct (three small slivers). Make the 39× gap visceral. Ideally let the user toggle each mechanism on and off and watch the computed watch-time number change.

2. **The two-timeline heartbeat contrast.** Side by side: a *backgrounded* span (beacon goes silent — gap detection works) versus a *paused* span (beacon keeps ticking every 40s — gap detection fails). This explains §3(c) better than any prose.

3. **The concurrency curve.** Plot both series from §8. Shade the area between them and label it "open but not watching". Annotate the 10:59 peak with both values (3,743 vs 2,937).

### Nice to have

4. **Delta-model explainer.** Animate the §6 example: three interval bars → +1/−1 markers → running-sum step chart. Show that the running total *is* the concurrency curve.

5. **Peak-is-not-additive demo.** Two filters that each peak at different minutes, and their intersection peaking at a third. Can be illustrative rather than real.

### Constraints

- **Single self-contained HTML file.** No CDN links, no external fonts or images — inline all CSS and JS. Chart libraries must be hand-rolled SVG or inlined.
- Must work in **both light and dark theme**.
- Must be **responsive**; wide charts scroll inside their own container rather than the page.
- Audience is **mixed** — hackathon judges and non-specialists. Lead with intuition, keep the numbers exact.
- **Do not invent data.** Everything needed is in this file. Anything illustrative (§6 example, §9.5) must be visibly labelled as such.

---

## 10. Quick reference

| Term | Meaning |
|---|---|
| **Session** | One person watching one video. `video_session_id`. |
| **Beacon** | The real 40-second heartbeat: `video-resize`, `buffer-health`, `network-bandwidth`, `network-activity`. |
| **Active interval** | A `[start, end)` span where someone was genuinely watching. |
| **CCU** | Concurrent users — how many sessions are active in a given minute. |
| **Naive CCU** | Counting any open session. Wrong; inflates by 1.27× at peak. |
| **Foreground-only CCU** | Counting only active intervals. What we're building. |
| **Delta** | `+1` at interval start, `−1` at interval end. Running sum = CCU. |
| **Watermark** | How far forward the served curve is trustworthy. |
| **`ACTIVITY_TIMEOUT`** | 90–100s = 2 missed beacons. Silence beyond this ⇒ not watching. |

### Numbers cheat-sheet

```
905,558 events · 10,866 sessions · 3,357 videos · 33,464 titles
Beacon cadence          40s  (documented as 60s — the docs are wrong)
ACTIVITY_TIMEOUT        90-100s (2 missed beacons)
Beacon silent when backgrounded    98.1%   -> gap detection works
Beacon silent when paused          55.6%   -> gap detection FAILS
Peak CCU        naive 3,743  ->  foreground 2,937   (21.5% not watching)
Watch-time      naive 2,977h ->  foreground 1,796h  (40% not watching)
Example session    1,174.6s wall  ->  30.2s actually watched  (39x)
```
