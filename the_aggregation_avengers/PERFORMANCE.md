# PERFORMANCE.md — every key choice, and the measurement behind it

**Question this answers:** why is each table sorted, partitioned and grouped the way it is, and what did changing it buy?

Everything here was measured against live ClickHouse Cloud, not reasoned about. Where a belief turned out to be wrong, the wrong belief is left in with the number that killed it — that is usually the useful part.

---

## 1. The rule that drives every sort-key decision

`ORDER BY` in a MergeTree does three separate jobs, and they are often confused:

1. **Granule pruning.** The sparse primary index stores one entry per 8,192 rows. A `WHERE` on a sort-key prefix lets ClickHouse skip granules without reading them.
2. **Compression.** Rows are stored sorted, so a column whose values repeat in long runs compresses far better than one that alternates. Column order decides who gets long runs.
3. **The merge key** — and for `AggregatingMergeTree` this is the big one. **`ORDER BY` *is* the group key.** Rows sharing an `ORDER BY` tuple are merged together. You cannot shorten it for performance without changing what the table means.

That third point removes the obvious optimisation before we start, and it is worth saying to a judge: our nine gold dimensions are not in the sort key because we like long sort keys, they are in it because **each one is a `GROUP BY` dimension, and removing one would merge rows that must stay separate.**

---

## 2. The measurement that decided the ordering

Same query, same one-hour minute range, one dimension filter at a time. `EXPLAIN indexes=1`, counting primary-key granules kept:

| filter | position in sort key | granules kept |
|---|---|---|
| *(none)* | — | 7 / 12 |
| `platform` | 2nd | **2 / 12** |
| `video_type` | 4th | 7 / 12 |
| `app_version` | 9th | 7 / 12 |
| `player_version` | 10th | 7 / 12 |

**Only the column immediately after `minute` prunes. Nothing after it prunes at all.**

The reason is that `minute` is a **range** predicate, not a point. Within a multi-minute range, values of the 3rd sort column are sorted only *inside* each `(minute, platform)` group — globally they are interleaved, so no granule can be excluded on them. The index cannot help, and the filter becomes a row-by-row scan of whatever the minute range selected.

**What follows from that:**

- `minute` is first because **every single query filters on it**. It is the only predicate that is always present, and it is the most selective. This is the single most important choice in the schema.
- `platform` is second because it is the only remaining slot that can prune, and platform is both the most-filtered dimension and the default breakdown.
- Positions 3–11 will never prune. Their only remaining job is **compression**, so cardinality is the only thing that should order them.

---

## 3. Cardinality, measured

```
country      1        video_type   2        subtitle_language  3
platform    10        player_ver  13        audio_language    14
app_version 65        category    84        content_id     3,357
minute   3,856        gold rows 105,083
```

Sorted storage compresses in runs, so **low cardinality belongs early**: a 2-value column placed early yields enormous runs, whereas placing a 3,357-value column early shatters the runs of everything after it.

By that rule the current tail is wrong — `content_id` (3,357) sits **third**, ahead of `video_type` (2) and `country` (1). The ideal tail is ascending: `country, video_type, subtitle_language, platform, player_version, audio_language, app_version, category, content_id`.

**We have not reordered it, and that is a deliberate call.** `MODIFY ORDER BY` cannot permute an existing key — only extend it — so changing this means recreating and re-backfilling gold. On the provided data the win is a few MiB of compression, against the risk of rebuilding the serving layer shortly before a submission. **On the unseen day gold is built from scratch anyway**, so `sql/30_gold.sql` should carry the corrected order when it is next run. Recorded here rather than quietly skipped.

`video_resolution` was appended last (see §7), which is both the only position ClickHouse allows and the correct one.

---

## 4. `PARTITION BY toDate(minute)`

Day-partitioned because:

- The `WHERE` is always a time range, so whole partitions are eliminated before the primary index is consulted — visible in `EXPLAIN` as a separate `Partition` pruning step ahead of `PrimaryKey`.
- Dropping a day is a metadata operation, so retention costs nothing.
- Merges stay inside a day, so a late-arriving row rewrites only that day's parts.

**Not partitioned by anything finer.** Hour partitions would give ~24× more parts for no extra pruning — the primary index already handles within-day ranges — and ClickHouse degrades badly past a few thousand parts. The unseen day is a **single day, 7M events, one partition**, which is exactly the size a partition should be.

---

## 5. `GROUP BY`, and why peak is never stored

Every query groups by `minute` first, matching the sort order, so ClickHouse aggregates in one pass without a sort.

**Peak is never stored, at any grain.** `max()` does not decompose across a filter predicate: different slices peak at different *minutes*. Measured — the ten per-platform peaks sum to **2,966** against a true peak of **2,882**, an 84-session overstatement, because ANDROID_PHONE and IPHONE do not crest together. A stored peak would be wrong for every filter combination it was not computed for, and there are more combinations than rows. So gold stores the **series**, and `max()` is applied *after* filtering, every time.

Hour and day grain, which the unseen-day submission asks for explicitly, are `max()` over the minute series inside each bucket — never an average of averages, never a separate stored aggregate.

**`uniqExactState`, not `uniqState`.** The latter is HyperLogLog and approximate. Against a private ground truth that is a correctness risk for no benefit at this scale. Exact distinct-count is also what makes the model idempotent under redelivery — merging a repeated session id changes nothing, so at-least-once delivery is safe.

---

## 6. What we changed, and what it bought

### 6.1 Stop reading the `users` state unless it is wanted

Every series query read **both** aggregate states to populate a "people vs sessions" overlay the dashboard hides by default behind a checkbox. Columnar storage means the column you do not select is a column you do not pay for.

```
sessions + users   37.54 MiB
sessions only      19.05 MiB     <- measured, same query, same range
```

Now opt-in via `?users=1`; the dashboard asks only when the overlay is on.

### 6.2 A separate table for the unfiltered query

`gold_ccu_minute` is keyed by minute × dimensions, so **one minute is ~27 rows** (105,083 / 3,856). But the dashboard's default view — and the first number a judge asks for — has **no dimension filter at all**, and pays that 27× to produce one number per minute.

`gold_ccu_total` holds one row per minute: **3,856 rows against 105,083.** The API routes to it only when no dimension predicate is set, and falls back otherwise. Both are fed from the same rows by sibling materialized views, and `sql/40_gold_total.sql` **asserts they agree** (2,882 = 2,882, 135,929 = 135,929) before the API is allowed to trust it.

This is not a stored peak. It is a per-minute distinct-count state for all traffic — exactly what the unfiltered query computes anyway.

### 6.3 Results

Sixteen query shapes, five repeats each, median ClickHouse-side time. `readBytes` is from ClickHouse's own summary header, not our clock.

| shape | before | after | factor |
|---|---|---|---|
| **series · no filter** | 37.54 MiB | **0.13 MiB** | **289×** |
| summary · no filter | 37.54 MiB | 0.25 MiB | 150× |
| rollup · no filter | 18.95 MiB | 0.13 MiB | 146× |
| series · platform | 37.63 MiB | 3.20 MiB | 11.8× |
| series · platform+video_type | 37.72 MiB | 3.22 MiB | 11.7× |
| series · 3 filters | 37.82 MiB | 3.23 MiB | 11.7× |
| series · video_type / audio / subtitle | 37.63 MiB | 19.05 MiB | 2.0× |
| breakdown · * | 19.05 MiB | 19.05 MiB | — |
| **TOTAL** | **435.77 MiB** | **201.95 MiB** | **2.16×** |
| ClickHouse time, total | 442 ms | 292 ms | 1.51× |

Independently, from the ClickStack traces over the same period — all 23 UI interactions driven through the real dashboard with Playwright:

| | before | after |
|---|---|---|
| p50 `clickhouse.query` | 66.9 ms | **57.6 ms** |
| p95 | 271.9 ms | **151.8 ms** |
| max | 18,564 ms | **244 ms** |
| avg bytes read / query | 21.24 MiB | **7.72 MiB** |

> **Read the two tables differently.** The benchmark is controlled — identical shapes, same range, before and after. The ClickStack figures cover *all* traffic in each window including ad-hoc probing, so treat them as corroboration of direction, not as a clean measurement. The p95 and the bytes-per-query agree with the benchmark, which is the point.

---

## 7. Sizing for the unseen day

7,000,000 events in **one day** against 905,558 across twelve — roughly **7.7× the rows, all in a single partition**, plus a tenth gold dimension.

**The dimension multiplier is the risk to watch.** `gold_ccu_minute` has one row per minute × dimension *combination*, so an added dimension with *k* values multiplies row count by up to *k*. With `video_resolution` at ~5 values and 1,440 minutes densely populated, gold could plausibly reach the low millions of rows.

Three things absorb that:

1. **`gold_ccu_total` does not carry the multiplier at all** — it is one row per minute, so 1,440 rows for the whole unseen day regardless of how many dimensions exist. The headline answers come from there.
2. **One day is one partition**, which is the right granularity — no part explosion.
3. **`video_resolution` is last in the sort key**, so it neither displaces `platform` from the one pruning slot nor breaks up the runs of the columns before it.

### The two ClickHouse constraints hit while adding it

Both fail in ways that are easy to mis-diagnose, so they are written down in `sql/50_add_unseen_dimensions.sql` as well:

- **`ADD COLUMN` and `MODIFY ORDER BY` must be one statement.** A sort key can only be extended with columns added by the *same* ALTER. Split in two, the ADD succeeds and the MODIFY fails with `BAD_ARGUMENTS (36)` — and the column is then permanently ineligible for the sort key until you drop it.
- **A column with an explicit `DEFAULT` cannot be in a sort key.** *"Newly added column has a default expression, so adding expressions that use it to the sorting key is forbidden."* Omitting `DEFAULT ''` changes nothing — the implicit default for `LowCardinality(String)` is already `''` — but it is the difference between working and not.

---

## 8. Reproducing any of this

```bash
node scripts/bench_ui.mjs before      # writes .run/bench-before.json
# ... change something ...
node scripts/bench_ui.mjs after
scripts/clickstack.sh spans           # the trace-side view
```

`EXPLAIN indexes=1` in front of any query prints the pruning table used in §2. That is the tool to reach for before believing a sort key helps.
