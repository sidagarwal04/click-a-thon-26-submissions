# US-12: Serving layer for dashboards

## The business ask
Every dashboard query answers from raw session history — that's a ~905K-row scan each time. How do we make dashboard queries answer in milliseconds instead of seconds?

## The expectation
A dedicated **concurrency-optimized serving table** holds pre-aggregated `(minute, platform, country, content_id, video_type) → concurrency`. Dashboard queries read **only** this table, never rescan raw history, and answer at dashboard-grade latency.

## Proof — same answer, two orders of magnitude apart

**Serving table:** pre-aggregated rows, one per (minute × dimension combo).

- **[BUILD]** `SELECT m, concurrency FROM serving WHERE m BETWEEN '19:00' AND '20:00' AND platform='android'` → reads **60 pre-aggregated rows** → **~30–80ms**.

| Query path | Rows touched | Latency |
|---|---|---|
| Serving table | 60 | **~30–80ms** |
| Raw table scan | ~905K events | **~2s** |

### Comparison proof
Run the **same** query both ways and capture both latencies as evidence — same answer, but raw scan is ~25–60× slower.

## Where it can go wrong
- Serving queries that still touch the raw table (e.g., fallback joins or missing pre-aggregation).
- Serving stale data — the serving layer must be refreshed incrementally (US-08) or the numbers drift from raw.

## Acceptance Criteria
- Given a dashboard query (minute grain, with filters)
- When executed
- Then it reads only the serving table
- And answers at dashboard-grade latency

## Labels
- `[NOW]` = runs on raw/content CSVs as-is
- `[BUILD]` = runs after building aggregated/serving tables
