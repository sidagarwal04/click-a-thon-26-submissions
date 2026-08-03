# Prototype Validation Results

*chdb (ClickHouse 26.5.1.1), single laptop, real dataset (905,558 events / 10,866 sessions). Run 2026-08-01. Reproduce with `python3 pipeline.py && python3 validate.py && python3 replay.py` (paths inside point at the session scratchpad copy of the parquet data — adjust `DATA` in `pipeline.py` if relocated).*

## Build (pipeline.py)

| Step | Result |
|---|---|
| DDL + content dictionary | 0.03 s |
| Ingest 905,558 events (raw + Tier-1 insert-time MV) | 0.51 s |
| Tier-1 state units created | 10,962 (`(session, platform, content)` grain) |
| Compactor, full first pass, both scopes | 0.28 s |
| Global delta invariant | `sum(delta) = 0` (every +1 closed by a −1) ✓ |

## Correctness (validate.py) — vs brute-force ground truth

| Check | Result |
|---|---|
| Global per-minute series vs `reference/ground_truth_foreground_per_minute.csv` | **0 mismatched minutes / 3,872 compared, max abs diff 0** |
| Peak minutes | 2,970 @ 1785063360 (10:56 UTC), 2,965 @ 10:59, 2,940 @ 10:58 — exact match |
| ANDROID_PHONE at global peak minute | 1,818 (expected 1,818) ✓ |
| IPHONE at global peak minute | 362 (expected 362) ✓ |
| JIO_ANDROID_TV | 219 @ 10:56, **peak 230 @ 10:59** (expected: slice peak differs from global peak) ✓ |
| Idempotence: second compactor run | 0 rows emitted (1,272 = 1,272) ✓ |

## Latency (dashboard-shape queries, hot day)

| Query | Latency | Reads |
|---|---|---|
| Global peak + avg, minute grain | 3 ms | 425 delta rows |
| Platform slice peak (JIO) | 4 ms | subset of 19,674 dim rows |
| Content top-10 by peak | 4 ms | 19,674 dim rows |
| video_type = live slice peak | 4 ms | " |
| Brute-force coverage scan (cost comparison only — no bg exclusion, returns 3,530 not 2,970) | 24 ms | 905,558 raw events |

At 1x the raw scan is affordable; the point is the *reads* column — serving reads are bounded by interval edges (~2 per session-interval per scope), the raw scan grows with events. At 100x with dashboard fan-out the raw path is seconds × widgets × refreshes; the delta path stays in the tens-of-thousands of rows.

## Update handling (replay.py) — live + late events

Event-time replay in 5-minute stream batches (872 batches over the 12-day span), with **1% of events (9,036) held back 30 minutes** on top of the natural 7% within-session disorder:

- Live curve builds through the event ramp: 22 → 1,085 (10:30) → 2,913 (10:55) → 0 after stream end
- Correction deltas absorb the late arrivals incrementally — no rebuild at any point
- Compactor tick: avg 165 ms, max 1.84 s (bulk bootstrap tick)
- **Final convergence: 0 mismatched minutes / 3,872 vs ground truth, max abs diff 0**

## Known gaps at time of writing (deliberate, pending design v2)

- Dim serving key is `(platform, content_id, m)`; finalized design (D4 in `../docs/DECISIONS.md`) extends it with `app_version` + `audio_language` and adds the user-scope table — not yet implemented.
- Dictionary default is `''` → to become `'unknown'` (review fix).
- `dirty_seq` uses ingest wall-clock (fine single-writer); compactor atomicity ordering documented in review findings, prototype runs single-writer only.
- Live "right now" is the last compacted minute per decision D2 (the draft session_state overlay was removed after review).
