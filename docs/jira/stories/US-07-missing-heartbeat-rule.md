# US-07: Define active interval when heartbeat is missing

## The business ask
Heartbeats arrive every ~1 minute. If one is missing — player paused, network drop, app killed — when exactly do we declare the viewer **not watching**? Without a rule we either overcount (assume still active forever) or undercount (cut too early).

## The expectation
A **configurable timeout** defines the rule: if the gap since the last heartbeat exceeds `gap_timeout`, the active interval closes at `last_heartbeat + gap_timeout`. Gaps within the timeout keep the interval continuous. The rule is documented and defensible.

## Proof — a 210s gap vs a 45s gap

Config: `heartbeat_interval = 60s`, `gap_timeout = 90s`.

**Session 1 (gap too big):** heartbeat 10:00:00, next heartbeat 10:03:30.

| Time | 10:00:00 | 10:01:30 | 10:03:30 |
|---|---|---|---|
| event | heartbeat | — | heartbeat |
| active? | ✓ | **cut here** | ✓ (new interval) |

- Gap = 210s > 90s timeout → active **closes at 10:01:30** (last heartbeat + timeout).
- `[10:01:30 – 10:03:30]` is **not counted**.

**Session 2 (gap small):** heartbeat 10:00:00, next heartbeat 10:00:45.

- Gap = 45s ≤ 90s timeout → interval stays **continuous**; no cut.

### Data context
- **[NOW]** `SELECT event_type, count() FROM ch_hackathon_raw GROUP BY event_type` — `VideoHeartbeat` ≈ **55%** of events, so the heartbeat-gap rule drives most active-interval boundaries.
- **[BUILD]** gap-timeout logic applied during aggregation.

## Where it can go wrong
- Cutting at the **next** heartbeat instead of `last + timeout` (under-counts the last minutes of the gap).
- A timeout so long that long pauses are counted as viewing; so short that normal network jitter splits sessions.

## Acceptance Criteria
- Given a configurable gap/timeout (heartbeat every 1 min)
- When a heartbeat is missing beyond the threshold
- Then the active interval is closed at the last known active point
- And the rule is documented and defensible

## Labels
- `[NOW]` = runs on raw/content CSVs as-is
- `[BUILD]` = runs after building aggregated/serving tables
