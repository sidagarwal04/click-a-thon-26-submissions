# US-09: Session-aware vs session-independent parity

## The business ask
We have **two different ways to compute "concurrent viewers per minute"** in the codebase:

- **Session-aware** — group events by `video_session_id`, build each session's active intervals, then count how many intervals overlap each minute.
- **Session-independent** — no grouping; walk the event stream in time order with a running counter (`+1` at start, `−1` at end, `−1` at background, `+1` at foreground) and read the counter per minute.

Both must exist (US-01 says we need a concurrency number; US-09 says we need **both engines**). The business asks: **"Do these two engines give the same answer?"**

## The expectation
**For sessions that are fully observed (started AND ended), the two engines MUST produce identical per-minute concurrency.** Any difference between them on such sessions is a bug.

For sessions still open when data stops, a small, explainable difference is allowed — and we must be able to explain exactly why.

## Proof — a small, fully-observed event stream

Two sessions, both started and ended. Session A also goes backgrounded and comes back.

| Time | Session A events | Session B events |
|---|---|---|
| 10:00 | `VideoSessionStart` | `VideoSessionStart` |
| 10:01 | `VideoHeartbeat` | `VideoHeartbeat` |
| 10:02 | `VideoHeartbeat` | `VideoHeartbeat` |
| 10:03 | `AppBackgrounded` | `VideoSessionEnd` |
| 10:04 | `AppForegrounded` | — |
| 10:05 | `VideoHeartbeat` | — |
| 10:06 | `VideoSessionEnd` | — |

### Engine 1 — session-aware (overlap count)
A is active 10:00–10:02, then paused 10:03, then active again 10:04–10:05, then ends. B is active 10:00–10:02, ends 10:03.

| Minute | 10:00 | 10:01 | 10:02 | 10:03 | 10:04 | 10:05 | 10:06 |
|---|---|---|---|---|---|---|---|
| A active? | ✓ | ✓ | ✓ | ✗ bg | ✓ | ✓ | ✗ end |
| B active? | ✓ | ✓ | ✓ | ✗ end | ✗ | ✗ | ✗ |
| **count** | 2 | 2 | 2 | 0 | 1 | 1 | 0 |

### Engine 2 — session-independent (running counter)
| Time | Event | Δ | Counter |
|---|---|---|---|
| 10:00 | A starts | +1 | 1 |
| 10:00 | B starts | +1 | 2 |
| 10:03 | A backgrounded | −1 | 1 |
| 10:03 | B ends | −1 | 0 |
| 10:04 | A foregrounded | +1 | 1 |
| 10:06 | A ends | −1 | 0 |

| Minute | 10:00 | 10:01 | 10:02 | 10:03 | 10:04 | 10:05 | 10:06 |
|---|---|---|---|---|---|---|---|
| **counter** | 2 | 2 | 2 | 0 | 1 | 1 | 0 |

### Comparison
| Minute | Session-aware | Session-independent | Match? |
|---|---|---|---|
| 10:00 | 2 | 2 | ✓ |
| 10:01 | 2 | 2 | ✓ |
| 10:02 | 2 | 2 | ✓ |
| 10:03 | 0 | 0 | ✓ |
| 10:04 | 1 | 1 | ✓ |
| 10:05 | 1 | 1 | ✓ |
| 10:06 | 0 | 0 | ✓ |

**Expectation met:** both engines agree on every minute. The two approaches are interchangeable for fully-observed sessions.

## Where they CAN differ — an open session at the data boundary
Add Session C that starts at 10:06 and never ends before the data is cut at 10:10:

- **Session-aware** stops counting C once no new heartbeat is seen (missing-heartbeat rule, US-07) → C contributes only up to ~10:07.
- **Session-independent** applied `+1` at 10:06 and never saw a `−1` → the counter keeps including C at 10:08, 10:09, 10:10…

So minutes 10:08–10:10 will differ until C closes. **This is the expected, explainable discrepancy.** Once C's `VideoSessionEnd` arrives, re-run both and they match again.

## Acceptance Criteria
- Given the same event stream
- When both approaches are computed
- Then results agree on closed, fully-observed sessions
- And discrepancies between the two are explainable (e.g., only for open sessions at the data boundary)

## Labels
- `[NOW]` = runs on raw/content CSVs as-is
- `[BUILD]` = runs after building aggregated/serving tables
