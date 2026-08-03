# US-01: Foreground-only concurrency per minute

## The business ask
A viewer who puts the app in the background or stops sending heartbeats is **not watching**. How many concurrent viewers per minute do we count if we exclude backgrounded and silent periods — instead of counting everyone who ever opened the app?

## The expectation
Per-minute concurrency counts **only active playback**. Backgrounded and heartbeat-missing periods contribute **0** to the count, and the per-minute values must match the ground-truth answer key.

## Proof — two sessions, one goes backgrounded

Session A: start 10:00, heartbeats 10:01–10:05, `AppBackgrounded` 10:06, `AppForegrounded` 10:09, heartbeats 10:10–10:12, end 10:12.
Session B: start 10:00, end 10:11 (plain, no backgrounding).

Per-minute active status:

| Minute | 10:00 | 10:01 | 10:02 | 10:03 | 10:04 | 10:05 | 10:06 | 10:07 | 10:08 | 10:09 | 10:10 | 10:11 | 10:12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A active? | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ bg | ✗ bg | ✗ bg | ✓ | ✓ | ✓ | ✗ end |
| B active? | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ end | ✗ |
| **correct count** | 2 | 2 | 2 | 2 | 2 | 2 | 1 | 1 | 1 | 2 | 2 | 1 | 0 |

### What each approach returns
- **[NOW]** `SELECT toStartOfMinute(event_timestamp) AS m, count(DISTINCT video_session_id) FROM ch_hackathon_raw GROUP BY m` — treats the whole session as active; **includes backgrounded time** → minute 10:07 = **2**.
- **[BUILD]** same query but only where `active = 1` (flag computed from `AppBackgrounded`/`AppForegrounded`/heartbeat gaps) → minute 10:07 = **1**.

### Comparison at the key minute
| Minute | [NOW] | [BUILD] | Correct? |
|---|---|---|---|
| 10:07 | 2 | 1 | [BUILD] = 1 ✓ |

The `[NOW]` answer is inflated: A was backgrounded at 10:06 and only returned at 10:09, so it should not be counted at 10:07.

## Where it can differ
The naive count overcounts every minute that falls inside a backgrounded window. The fix is the `active` flag (US-06, US-07) that cuts inactive segments out of each session's interval.

## Acceptance Criteria
- Given a set of sessions with start/end, heartbeats, and background/foreground markers
- When I query concurrency at minute grain for a time range
- Then backgrounded and heartbeat-missing periods are excluded from the count
- And the count matches the ground-truth answer key

## Labels
- `[NOW]` = runs on raw/content CSVs as-is
- `[BUILD]` = runs after building aggregated/serving tables
