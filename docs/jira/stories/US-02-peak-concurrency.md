# US-02: Peak concurrency over a time range

## The business ask
Marketing wants to know the **biggest spike** of viewers: "at the moment of highest demand, how many people were watching?" Given a time range, what was the maximum concurrent audience?

## The expectation
Peak concurrency = **max** of the per-minute concurrency values inside the selected range. It respects dimension filters (each filtered segment has its own peak minute). Peak is a max, never an average.

## Proof — three minutes, two platforms

Per-minute concurrency for 10:00–10:02 (all platforms, then Android only):

| Minute | All platforms | Android only |
|---|---|---|
| 10:00 | 300,000 | 80,000 |
| 10:01 | 200,000 | **120,000** |
| 10:02 | 50,000 | 30,000 |

### Computations
- **Peak (all):** `max(300000, 200000, 50000)` = **300,000** → `[BUILD] SELECT max(concurrency) FROM serving WHERE m BETWEEN '10:00' AND '10:02'`.
- **Peak (Android):** `max(80000, 120000, 30000)` = **120,000** → `[BUILD] ... WHERE platform='android'`.

### Key insight
Android's peak (120,000 at 10:01) is **not** the Android value at the global peak minute (80,000 at 10:00). Each dimension combination peaks at its **own** minute:

| Filter | Peak value | Peak minute |
|---|---|---|
| All | 300,000 | 10:00 |
| Android | 120,000 | 10:01 |

## Where it can go wrong
- Using the **global** peak minute's value for every segment (Android would wrongly show 80,000 instead of 120,000).
- Confusing peak (max) with average — they coincide only when all minutes are equal (see US-03).

## Acceptance Criteria
- Given a time range spanning multiple minutes
- When I request peak concurrency
- Then I get the max per-minute concurrency within that range
- And it respects all applied dimension filters

## Labels
- `[NOW]` = runs on raw/content CSVs as-is
- `[BUILD]` = runs after building aggregated/serving tables
