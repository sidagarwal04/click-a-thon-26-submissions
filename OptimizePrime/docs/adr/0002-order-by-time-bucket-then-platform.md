# ADR 0002 — Lead the raw sort key with a truncated hour, not the session id

> **Summary:** `ev_raw` is `ORDER BY (toStartOfHour(event_timestamp), platform, video_session_id,
> event_timestamp)`. An earlier version led with `video_session_id` for session locality. Measured on
> the real 905K-event file that was **17.3× worse** on the dashboard access shape and **2× worse** on a
> plain time slice, while being **identical** on the full interval rebuild. Status: accepted, 2026-08-01.

**Status** Accepted · 2026-08-01 · supersedes the key in the initial scaffold

## Context
Two candidate orderings for the raw event table:
- **A** `(video_session_id, event_timestamp)` — a session's events contiguous, one range read per
  session when reconstructing intervals.
- **B** `(toStartOfHour(event_timestamp), platform, video_session_id, event_timestamp)` — low
  cardinality first, per the official ClickHouse rule `schema-pk-cardinality-order` (impact: CRITICAL).

A leads with a near-unique 64-char hash, which that rule names as the anti-pattern: every granule holds
different values, so the sparse index can skip nothing.

## Decision
**B.** Measured, not argued.

| Access pattern | A: rows / bytes | B: rows / bytes | B is |
|---|---|---|---|
| one-hour time slice | 849,888 / 6.80 MB | 434,176 / 3.47 MB | **2.0× better** |
| one-hour slice + `platform` filter | 849,888 / 7.65 MB | 49,152 / 0.44 MB | **17.3× better** |
| full interval rebuild (`GROUP BY` session) | 905,558 | 905,558 | identical |

## Why the locality argument was wrong
The benefit A was protecting — contiguous session reads — only pays off when a query touches *some*
sessions. Our interval rebuild touches *all* of them, so it scans the whole table either way and the
ordering is irrelevant to it. Meanwhile every incremental, late-arrival and dashboard query filters by
**time**, and often by **platform**, which is exactly B's prefix.

## Consequences
- Day-grain pruning still comes from `PARTITION BY toYYYYMMDD`; the hour bucket prunes within a day.
- A session spanning an hour boundary is split across granules. This costs nothing measurable here
  because interval reconstruction is a full scan anyway.
- If a "single session lookup" access pattern ever becomes hot, add a `PROJECTION` ordered by
  `video_session_id` rather than reverting the key — measured elsewhere to recover the alternative
  ordering's performance exactly.
