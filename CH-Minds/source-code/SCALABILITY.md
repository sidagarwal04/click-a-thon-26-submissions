# Scaling to billions of rows

Every number in Part 1 is measured on the running stack against the loaded 9,000,000-row
dataset. Part 2 extrapolates from those measurements and is labelled as projection. Nothing
here is a vendor benchmark.

---

## Part 1 - Measured today

### Storage

| Table | Rows | Compressed | Uncompressed | Ratio | Bytes/row |
|---|---|---|---|---|---|
| `ad_events` (raw fact) | 9,000,000 | 138.8 MiB | 417.7 MiB | 3.01x | 16.17 |
| `hourly_segment_metrics` (rollup) | 7,907,017 | 78.1 MiB | 347.6 MiB | 4.45x | 10.35 |

35 day-partitions, 104 active parts.

### Query latency

Core scan query (one metric x one dimension, window-function baseline), by date filter:

| Range scanned | Time |
|---|---|
| 1 day | 0.081 s |
| 7 days | 0.081 s |
| 35 days (full) | 0.177 s |

Partition pruning is working: a 35x wider scan costs 2.2x, not 35x.

Full `/api/investigate`, end to end, warm cache:

| Stage | Time |
|---|---|
| Day-coverage check | 136 ms |
| Dynamic thresholds (cached) | 0 ms |
| Top-line deviation | 118 ms |
| Segment ranking (9 dimensions) | 695 ms |
| Multi-dimension refinement | 430 ms |
| **ClickHouse total** | **1.38 s** |
| **LLM narration** | **5.45 s** |
| **End to end** | **7.32 s** |

Cold (thresholds cache expired), `compute_thresholds` adds ~5.6 s.

**ClickHouse is 19% of the wall clock; the LLM is 74%.** That is the architecture claim -
"ClickHouse does the analysis, the LLM only narrates" - as a measurement rather than an
assertion, and it is displayed in the UI on every investigation.

### The number that actually governs scaling

| Measurement | Value |
|---|---|
| Distinct dimension combinations that ever occur | **767,984** |
| Theoretical combination space (5x7x3x8x4x5x16x8x8) | 17,203,200 |
| Combinations populated per hour (avg / max) | 9,413 / 12,991 |
| Events per hour (avg) | 10,714 |

This single ratio explains the rollup's current weak showing. Rollup rows are bounded by:

```
rollup_rows = hours x min(events_per_hour, populated_combinations_per_hour)
```

At 10,714 events/hour against 9,413 reachable combinations/hour, **the combination space is
essentially unsaturated - almost every event lands in its own bucket**, so the rollup gives
only 9.0M -> 7.9M (1.14x). `PROGRESS.md` recorded this as a "trade-off accepted" after the
`ORDER BY` corruption fix. The audit shows it is not a design flaw: it is what a 9M-row
sample looks like against a 768K-wide dimension space, and it inverts as volume grows.

---

## Part 2 - What happens at a billion rows (projection)

**Raw events grow linearly. The dimension space does not grow at all.** `ad_events` at 16.17
bytes/row compressed projects to ~16.2 GB at 1B rows and ~162 GB at 10B - unremarkable for
ClickHouse. The interesting question is what the *detection scan* has to read.

### The hourly rollup stops being enough, and the day-grain rollup fixes it permanently

Every detection query - the scan, the top-line deviation, segment ranking, combo refinement,
threshold calibration - begins with `GROUP BY toDate(hour)`. Hour grain is needed by exactly
one feature: playback (`timeline.py`). So detection is paying for a grain it immediately
discards.

Measured: rolling the current data to day grain gives **4,511,141 rows** vs 7,907,017 hourly
(1.75x today, again limited by sparsity). The projection matters more than today's ratio:

```
day_grain_rows  =  days x min(events_per_day, 767,984)
```

Once `events_per_day > 767,984` - which is true for any realistic volume - **the day-grain
rollup is capped at ~768K rows per day no matter how much traffic arrives.**

| Raw events (35 days) | Day-grain rollup rows | Reduction |
|---|---|---|
| 9,000,000 (today) | 4,511,141 | 2.0x |
| 1,000,000,000 | ~26,900,000 (capped) | **37x** |
| 10,000,000,000 | ~26,900,000 (capped) | **372x** |
| 100,000,000,000 | ~26,900,000 (capped) | **3,717x** |

This is the load-bearing property: **detection cost becomes a function of dimension
cardinality, not of traffic volume.** A 100x traffic increase costs the scan nothing. The
scan today reads 7.9M rows in 0.18 s; at 1B raw events it would read ~26.9M day-grain rows,
which is the same order of magnitude - single-digit seconds, not minutes.

Ready to apply, additive, nothing existing changes:

```sql
CREATE TABLE inmobi_rca.daily_segment_metrics
(
    day Date,
    ad_format LowCardinality(String), category LowCardinality(String),
    publisher_tier LowCardinality(String), vertical LowCardinality(String),
    campaign_type LowCardinality(String), region LowCardinality(String),
    country LowCardinality(String), device_model LowCardinality(String),
    os_version LowCardinality(String),
    requests AggregateFunction(count),
    fills AggregateFunction(sum, UInt8), impressions AggregateFunction(sum, UInt8),
    clicks AggregateFunction(sum, UInt8), revenue AggregateFunction(sum, Float64)
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
-- Every grouping column, for the reason documented at length in 01-schema.sql:
-- for AggregatingMergeTree, ORDER BY is a row's merge identity, and anything
-- omitted is silently collapsed during background merges.
ORDER BY (day, ad_format, category, publisher_tier, vertical, campaign_type,
          region, country, device_model, os_version);
```

Populated by a second materialized view off `ad_events` (not chained off the hourly rollup -
an independent view means an error in one cannot corrupt the other), and the hourly rollup
gets a TTL so it retains only the recent window playback actually needs.

**Not applied yet, deliberately.** It is a schema change with the same shape as the one that
caused this project's worst bug, and the value is entirely at a scale we cannot test today.
The measurement establishes the ceiling; applying it is the first item for a post-hackathon
pass, or a 30-minute change if a judge wants it demonstrated.

### What breaks first, in order

1. **`compute_thresholds` (~5.6 s cold).** Already the largest ClickHouse cost, and the only
   one that scales with the *number of dimensions x metrics* rather than with rows. It
   unions 9 dimension subqueries per metric across the full history. Fixes, cheapest first:
   compute it once per scan and pass it down (partly done - it is cached with a 120 s TTL);
   restrict the calibration window to a trailing 8 weeks instead of all history; materialize
   it as a nightly job rather than a request-path computation.
2. **Combo refinement.** `refine_segment` runs one query per other dimension (8 per
   investigation). Bounded and small today (430 ms), but it is O(dimensions) per
   investigation and the natural place a wider schema would hurt. Parallelising the 8 queries
   is straightforward.
3. **The LLM, unchanged.** Narration is one call on a fixed-size JSON summary, so it is
   **O(1) in data volume** - 5.45 s at 9M rows and 5.45 s at 100B. This is a direct
   consequence of never sending rows to the model, and it means the end-to-end latency
   asymptotes to the LLM call.
4. **Ingest.** The materialized view processes block-wise on insert, so bulk and streaming
   behave identically (both paths already exist and are tested). At sustained billions/day
   this becomes a Kafka/ClickPipes concern rather than a `POST` endpoint - deliberately not
   built, since adding streaming infrastructure nobody asked for would be the wrong trade in
   a 24-hour window.

### Horizontal scale

The scan is embarrassingly parallel: 5 metrics x 9 dimensions = **45 fully independent
queries** sharing no state. They are currently a sequential Python loop, which is the single
easiest large win available - a thread pool over the existing per-thread ClickHouse clients
(`db.py` already provides `threading.local()` clients precisely because of this) would cut
scan wall-clock by close to the pool size with no query changes.

Beyond one node: `ad_events` shards cleanly on `cityHash64(app_id)` or `geo_device_id`, both
high-cardinality and uncorrelated with the time filter every query starts with, so
partition pruning survives sharding. The rollup's aggregate states merge correctly across
shards by construction - that is what `AggregateFunction` columns are for - so a distributed
`sumMerge`/`countMerge` returns the same answer as the single-node one. No query in the
pipeline would need rewriting.

### What does not change

Correctness properties are volume-independent and stay true at any scale: the robust median
baseline, the partial-day hour restriction, the minimum-baseline-samples floor, the
degenerate-cut exclusions, and the guarantee that the LLM never sees a raw row. Those are
properties of the queries, not of the data size.
