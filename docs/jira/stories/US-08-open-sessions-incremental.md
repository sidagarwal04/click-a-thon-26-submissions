# US-08: Handle still-open sessions incrementally

## The business ask
Some sessions never end — they keep sending heartbeats. Their active range grows minute by minute. When a new heartbeat arrives, the dashboard must reflect it **without rebuilding the whole day from scratch**.

## The expectation
New events for an open session apply as a small **delta** to the aggregate: only the newly-covered minutes change. Already-published minutes must stay **bit-for-bit unchanged**, and nothing forces a full recompute of the raw stream.

## Proof — one open session, one new heartbeat

**Step 1 — current state:** an open session is active 10:00–10:05; the served minute 10:04 = **500**.

| Minute | 10:00 | 10:01 | 10:02 | 10:03 | 10:04 | 10:05 | 10:06 |
|---|---|---|---|---|---|---|---|
| served concurrency | 500 | 501 | 502 | 503 | 500 | 500 | — |

**Step 2 — new heartbeat at 10:06:** the session is now active through 10:06.

| Minute | 10:00 | 10:01 | 10:02 | 10:03 | 10:04 | 10:05 | 10:06 |
|---|---|---|---|---|---|---|---|
| served concurrency | 500 | 501 | 502 | 503 | 500 | 500 | **501** |

### What happened
- Delta = **+1 applied to minute 10:06 only**.
- Minutes 10:00–10:05 are **unchanged** — `WHERE m='10:04'` still returns **500**.
- No re-read of historical minutes, no recompute of the full session interval.

### Failure case to avoid
Re-running the full **905K-row** event stream to update a single minute. If updating minute 10:06 touches anything before it, the incremental design is broken.

## Where it can go wrong
- Re-applying a session's whole interval on every heartbeat (touches old minutes, breaks immutability).
- Publishing minute 10:06 as 500 (delta lost) instead of 501.

## Acceptance Criteria
- Given an open session receiving new heartbeats
- When new events arrive
- Then the aggregate absorbs the delta (no full recompute)
- And correctness is maintained for already-published ranges

## Labels
- `[NOW]` = runs on raw/content CSVs as-is
- `[BUILD]` = runs after building aggregated/serving tables
