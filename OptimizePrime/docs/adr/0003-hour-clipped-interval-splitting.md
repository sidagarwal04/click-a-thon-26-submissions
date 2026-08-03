# ADR 0003 — Clip active intervals at hour boundaries when emitting deltas

> **Summary:** When converting an active interval to minute deltas, clip it to each hour it touches:
> emit `+1` at its start within that hour, and `−1` only if it actually ends within that hour. An
> interval surviving past the hour emits no close; the next hour re-opens it with a fresh `+1`. This
> makes every hour's running sum absolute — removing the carry-in dependency that otherwise forces a
> scan from `t=0` — and makes peak pre-aggregable per hour, since `max` over an hour is now a real
> number rather than a fragment. Status: proposed, 2026-08-01. Supersedes nothing; extends the delta
> model in [ADR 0001](0001-heartbeat-gaps-over-background-events.md).

**Status** Proposed · 2026-08-01

## Context

Concurrency at minute M is the running sum of deltas **from the beginning of time** up to M. Two
consequences followed from that definition and neither was addressed in the original design:

1. **Carry-in.** A query for `[A, B]` that sums only the deltas inside the range misses every session
   that opened before `A` and is still active. The fix is either a scan from `t=0` — which defeats
   partition pruning, the main reason we partition by day — or periodic snapshot checkpoints, which is
   more state to maintain and get wrong.
2. **Peak does not roll up over time.** Peak over a day is `max()` across 1,440 minute values, so every
   day-grain peak query is forced down to minute grain. The benchmark set explicitly includes
   hour and day grain.

## Decision

For each hour `H` that an interval `[s, e]` overlaps, emit into `H`:

```
+1 at greatest(toStartOfMinute(s), H)
-1 at toStartOfMinute(e) + 1 minute   -- ONLY IF e < H + 1 hour; otherwise emit no close
```

All deltas for hour `H` therefore live inside `H`. Concurrency within the hour is
`sum(delta) OVER (PARTITION BY toStartOfHour(minute) ORDER BY minute)`.

Given that, maintain `cc_hour_agg` keyed `(dims, hour)` storing the hour's `max` of that running sum
and its `integral` (concurrency-seconds). Peak over an hour-aligned range is the max of stored maxes;
average is `sum(integrals) / range_seconds`.

## Why

- The carry-in dependency disappears rather than being managed. Each hour reconstructs absolute
  concurrency standalone, so partition pruning becomes exact instead of nominal.
- Peak becomes summable **over time** (it still is not summable over dimensions — see
  [ADR 0004](0004-two-tier-lambda-serving.md) and `docs/ARCHITECTURE.md`). A day-grain peak reads 24
  rows per dimension combination instead of 1,440 — a 60× reduction in the dominant benchmark shape.
- Time-weighted average falls out for free, including zero-concurrency minutes, because the integral is
  stored rather than derived from a mean over present rows.
- The cost is one extra delta pair per interval per crossed hour. At the measured ~78-minute average
  session that is ≈1.3 crossings, so row count moves by a small constant factor, not an order.

## Consequences

- A ragged range such as `10:17 → 14:43` decomposes into `max(` minute-scan of the leading partial
  hour, hour-maxes of the whole hours, minute-scan of the trailing partial hour `)`. Worst case is two
  partial hours regardless of range length, so the saving grows with the range.
- Hour is now a structural unit of the model, not just a query grain. Changing it (to 10 minutes, or to
  a day) is a schema change, not a setting — record it here if it ever moves.
- `/reconcile` must verify the hour-clipping specifically: an interval that spans ≥3 hours, checked at a
  minute inside the middle hour, is the case that fails if the clipping logic is wrong. Add it to
  `docs/TESTS.md`.
- The running-sum window function must partition by hour. A query that forgets the `PARTITION BY` will
  silently produce wrong numbers that look plausible — flag it in `docs/CONVENTIONS.md`.
