# US-03: Average concurrency over a time range

## The business ask
Peak shows the spike, but how do we compare it with the **typical** audience? What is the average number of concurrent viewers over a time range?

## The expectation
Average concurrency = **mean of the per-minute foreground-only counts** in the range. It must stay ≤ peak (it is an average of the same numbers), and it must be recomputed correctly when filters change.

## Proof — reuse the US-02 minutes

Per-minute concurrency for 10:00–10:02:

| Minute | 10:00 | 10:01 | 10:02 | Peak (max) | Average (mean) |
|---|---|---|---|---|---|
| concurrency | 300,000 | 200,000 | 50,000 | 300,000 | **183,333** |

- Average = `(300000 + 200000 + 50000) / 3` = **183,333** → `[BUILD] SELECT avg(concurrency) FROM serving WHERE m BETWEEN '10:00' AND '10:02'`.
- Peak = 300,000. Check: **183,333 ≤ 300,000** ✓ (average can never exceed the peak of the same numbers).

### Filtered case (platform changes peak minute)
If Android's minutes are 80,000 / 120,000 / 30,000, its average = `230000 / 3` = **76,667**, and its peak = 120,000 at a *different* minute than the global peak. Average and peak must each be computed per filter.

## Where it can go wrong
- **Sanity check that catches bugs:** if `avg > max`, then inactive time was wrongly counted (e.g., backgrounded minutes included), because including zero-value minutes would *lower* the average, not raise it above the max.
- Computing average over sessions instead of per-minute counts (inflates the number).

## Acceptance Criteria
- Given a time range with varying per-minute concurrency
- When I request average concurrency
- Then the result is computed over per-minute foreground-only counts
- And it is correct when filters change (e.g., platform changes peak minute)

## Labels
- `[NOW]` = runs on raw/content CSVs as-is
- `[BUILD]` = runs after building aggregated/serving tables
