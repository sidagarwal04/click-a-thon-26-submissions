# US-13: Incremental compaction of finalized sessions

## The business ask
Raw per-event detail is expensive to keep forever. Once a session has safely ended, do we still need every heartbeat row? How do we keep recent detail fresh while history stays cheap?

## The expectation
Sessions that close before a **finalization watermark** are compacted into the historical tier as delta rows. Recent, still-open sessions remain as full detail in the recent tier. A query over a finalized range reads only the historical tier.

## Proof — a 30-minute session before and after compaction

Config: sessions closed before `now() - 1h` are finalized.

- **Recent tier (0–1h):** full per-event detail for open/recent sessions — small, fast to update.
- **Historical tier (>1h):** compacted **delta rows** — `minute +1` at start, `minute −1` at end.

| Tier | Storage for a 30-min session |
|---|---|
| Recent (before) | ~30 heartbeat rows (one per minute) |
| Historical (after compaction) | **2 delta rows** (`+1` at start, `−1` at end) |

### Check
| Query | Reads |
|---|---|
| Range > 1h old (finalized) | historical tier only |
| Last 5 minutes | recent tier only |

## Where it can go wrong
- Compacting a session that is **still open** (its interval keeps growing — see US-08) → wrong deltas.
- Watermark too small (compacts recent sessions) or too large (history never shrinks).

## Acceptance Criteria
- Given a session that has ended
- When it passes the finalization watermark
- Then its active intervals are compacted into the historical tier
- And recent open sessions remain in the detailed tier

## Labels
- `[NOW]` = runs on raw/content CSVs as-is
- `[BUILD]` = runs after building aggregated/serving tables
