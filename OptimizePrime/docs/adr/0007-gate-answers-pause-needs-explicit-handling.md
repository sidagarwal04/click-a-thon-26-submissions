# ADR 0007 — Heartbeat gaps detect backgrounding but NOT pause; pause needs explicit handling

> **Summary:** The three H1 gates are answered against the real file, on Cloud. GATE ① passes:
> heartbeats effectively stop while backgrounded (0.047/min vs 4.72/min active, a 100× drop), so
> ADR 0001 stands and gaps are a valid backgrounding signal. **GATE ② fails: heartbeats SURVIVE a
> pause** (0.756/min, 16% of active), so a gap-only model counts paused time as watching — which the
> statement explicitly forbids. The model must be a hybrid: gaps for backgrounding/disappearance,
> explicit `pause`/`resume` events for paused time. GATE ③: no negative clock skew at all, but 2.2%
> of sessions emit events up to 2,081s after `VideoSessionEnd`, which sets the watermark width.

**Status:** accepted · **Date:** 2026-08-01 · Measured on Cloud, `sonyliv.ev_raw`, 905,558 events

## Context

`sql/10_intervals.sql` asserts "Heartbeats are emitted every 60s, so a gap > threshold IS the
inactivity signal", with `HEARTBEAT_GAP_S = 150` justified as "~2.5 missed beats". TODOS gated H2 on
verifying that. All three gates are now measured.

## Measurement

### The cadence claim is wrong

`VideoHeartbeat` is not a periodic beat. Its `event` sub-column is discrete player telemetry —
`network-activity`, `buffer-health`, `video-resize`, `BufferStart`, `Seek`, `pause`, `resume`.
Inter-arrival within a session: **p50 = 0s, p90 = 40s, p99 = 49s**, mean 12.4s. Bursty, not periodic.
Overall rate is **4.72 beats/min**, not ~1/min.

This does not by itself invalidate a 150s threshold — 150s is still ~3× the p99 — but the stated
reason for it was not true, and the number should be re-derived from the real distribution.

### GATE ① — backgrounding: PASS, ADR 0001 stands

Heartbeats strictly inside each `AppBackgrounded → AppForegrounded` pair:

| | |
|---|---|
| closed bg→fg pairs | 13,948 |
| backgrounded time | 3,301,211 s (55,020 min) |
| heartbeats inside | 2,605 |
| **rate while backgrounded** | **0.047 /min** — 1% of the 4.72/min active rate |

Effectively zero. A gap threshold detects backgrounding. **ADR 0001 stands.**

### GATE ② — pause: FAIL

Heartbeats strictly inside each `pause → resume` pair:

| | |
|---|---|
| closed pause→resume pairs | 21,068 |
| paused time | 3,002,604 s (50,043 min) |
| heartbeats inside | 37,854 |
| **rate while paused** | **0.756 /min** — 16% of active |

0.756/min is one event every ~79s, comfortably inside a 150s gap threshold. **A gap-only model will
not close an interval during a pause, so paused time is counted as watching.** The statement excludes
paused time explicitly, so this is a correctness bug, not a tuning issue.

What those events are: mostly passive telemetry — `video-resize` (10,343), `network-activity`
(8,338), `buffer-health` (6,835) — plus scrubbing (`video_forward`, `Seek`, `video_rewind`). None of
it is playback progress. The player keeps reporting; the viewer is not watching.

### GATE ③ — ordering and lateness

There is no ingest/arrival column in the data, so true out-of-order arrival is unmeasurable from the
file. The checkable proxies:

- `event_timestamp < session_start_epoch`: **0 rows.** No negative skew anywhere.
- Events after `VideoSessionEnd`: **239 sessions (2.2%)**, max **2,081 s** after the end event.

So the watermark must be ≥ ~2,100 s to seal without losing stragglers.

## Decision

1. Keep heartbeat gaps as the backgrounding and disappearance signal (ADR 0001 unchanged).
2. **Add explicit pause handling.** Active time = gap-derived runs **minus** paused windows.
3. Re-derive `HEARTBEAT_GAP_S` from the measured p99 (49s), not from an assumed 60s cadence.
4. Set the watermark from the measured 2,081s straggler tail, not a guess.

## The unresolved part — pause pairing

`pause` and `resume` do **not** pair, in the opposite direction to bg/fg: 27,340 pauses vs 31,780
resumes, 4,440 more resumes than pauses. 6,272 pauses (23%) have no following resume.

After an unclosed pause, activity runs at **1.17 beats/min** — a quarter of the active rate, so not
obviously "still watching" and not obviously "gone". Two defensible rules:

- **Conservative** (shipped): an unclosed pause stays paused to the end of its run. Never credits time
  we cannot prove was active.
- **Permissive**: an unclosed pause ends at the next event of any kind, treating the pause as a blip.

**Measured, both rules run end to end over the real file:**

| rule | counted watch time |
|---|---|
| conservative (shipped) | **1,949.3 h** |
| permissive | **2,048.6 h** |
| difference | **+99.3 h — 5.09%** |

Note the correction: an earlier estimate put this at ~19,800 minutes (330 h), taken from the raw time
following an unclosed pause. That overstated it roughly 3×, because most of that time is *already*
excluded by the gap rule closing the run — the two exclusions overlap. The real exposure is 99.3 h.

**It moves the PEAK, which is the graded number** — measured after this ADR was first written, and
the more important figure:

| rule | counted hours | **PEAK** | peak minute |
|---|---|---|---|
| conservative (shipped) | 1,949.3 h | **2,887** | 2026-07-26 10:56 |
| permissive | 2,048.6 h | **3,018** | same minute |
| difference | +5.09% | **+131, +4.5%** | — |

**Resolved into a one-constant switch rather than left open.**
`UNCLOSED_PAUSE_TO_RUN_END` at the top of `sql/30_build_intervals.sql` — `1` conservative (default),
`0` permissive. **It must be flipped in `sql/90_reconcile.sql` too**, and that is deliberate: the gate
derives truth from `ev_raw` with a different implementation, so it shares the SPEC but not the CODE.
Verified both ways: model-only flip → gate catches it (240 mismatched minutes, max_abs_diff 156);
both flipped → gate green at peak 3,018; restored → green at 2,887.

**Default stays conservative** because under exact raw-event spot-checks, under-counting is a
visible, explainable error, while over-counting invents viewers that demonstrably were not receiving
playback events. Still worth asking (mentor Q2) — but it is now a two-line change plus a rebuild and
a gate run, not a redesign.

## Consequences

- H2 cannot be built as originally specified; the interval derivation needs a pause-subtraction step.
- `sql/10_intervals.sql`'s cadence comment is factually wrong and must be corrected.
- The bg/fg unpairing argument in ADR 0001 applies to pause/resume too: do not build a model that
  assumes clean pairing.
