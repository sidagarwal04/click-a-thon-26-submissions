# US-15: Scalability framing (100x)

## The business ask
The demo data is ~905K events. The judges will ask: **what happens at 100x?** Do the design choices hold up, or were they hacks that only work on a small dataset?

## The expectation
At 100x, no pattern requires a full rescan of raw history per query, and no pattern explodes the data into unmanageable per-minute rows. Every trade-off is documented with numbers.

## Proof — serving table vs per-minute explosion at 100x

**Acceptable at 100x — serving table `(minute, dims) → count`:**

| Metric | Today | At 100x |
|---|---|---|
| Raw events | 905K | 90M |
| Serving rows `(minute × dims)` | 14K | **~1.4M** |

→ 1.4M pre-aggregated rows still answers in ms.

**Rejected at 100x:**

- Exploding every session into per-minute rows: 905K events → ~90M rows at 100x — storage and scans blow up.
- Recomputing overlap from raw history on every dashboard query (US-12 exists to prevent exactly this).

### The scaling story (document it)
`interval → delta rows → serving tier` scales because:
1. Delta rows are O(sessions), not O(minutes).
2. Serving rows are O(minutes × dims), not O(events).
3. Queries read only the serving tier.

## Where it can go wrong
- A solution tuned to "905K rows" that breaks the moment data grows (e.g., per-query full scans).
- No written rationale — the design is only as defensible as its documentation.

## Acceptance Criteria
- Given design choices made in the solution
- When judges probe scale behavior
- Then no full-rescan or per-minute-explosion-of-all-history patterns are required at production scale
- And the reasoning behind each trade-off is documented

## Labels
- `[NOW]` = runs on raw/content CSVs as-is
- `[BUILD]` = runs after building aggregated/serving tables
