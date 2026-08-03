# US-10: Handle late / duplicate events

## The business ask
Real event streams replay, retry, and arrive late. If a duplicate heartbeat or a delayed `VideoSessionEnd` is applied twice — or at the wrong time — a viewer gets double-counted and the whole concurrency number is wrong. How do we keep the count correct?

## The expectation
Each logical state transition is applied **exactly once**, and late events land on their **original minute** (when the event happened), not when it arrived. Duplicates must never inflate the count.

## Proof — two problem events

**Duplicate heartbeat:** the identical `VideoHeartbeat` at 10:05:00 for the same session arrives twice.

| Arrival | Applied? | Result |
|---|---|---|
| 1st 10:05:00 | ✓ | session stays active |
| 2nd 10:05:00 (dup) | ✗ deduped | concurrency stays **1**, not 2 |

**Late end event:** `VideoSessionEnd` that happened at 10:12 arrives at 10:20.

| Event time | Arrival time | Applied to |
|---|---|---|
| 10:12 | 10:20 | **minute 10:12**, not 10:20 |

If it were applied to 10:20, the session would wrongly appear active from 10:12–10:20, inflating those minutes.

### Finding duplicates
- **[NOW]** `SELECT video_session_id, event_timestamp, event_type, count() FROM ch_hackathon_raw GROUP BY 1,2,3 HAVING count()>1` — find duplicate rows.
- **[BUILD]** dedup at ingestion; each transition applied once.

## Where it can go wrong
- Deduping by `video_session_id` only (a session legitimately has many distinct events — dedup key must include event type + timestamp).
- Applying late events at arrival time instead of event time.

## Acceptance Criteria
- Given duplicate heartbeats or late-arriving events
- When ingestion processes them
- Then each logical state transition is applied once
- And concurrency isn't inflated by duplicates

## Labels
- `[NOW]` = runs on raw/content CSVs as-is
- `[BUILD]` = runs after building aggregated/serving tables
