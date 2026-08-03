# SonyLIV serving layer — how to read viewing trends

You are querying a **pre-aggregated concurrency serving layer**. There is no per-user or
per-event data here and no way to reach it: every row is a count for one dimension
combination in one time bucket. Answer questions about *viewing trends* — how many people
were watching, when it peaked, what they watched, which slice is falling.

Everything below is a rule that has already been got wrong once on this data. Read it
before composing SQL.

---

## 1. The additivity rule — the single most important thing here

| Measure | Additive across… | Use it for |
|---|---|---|
| `active_ms` | **everything** — dimensions and time both | averages, viewer-hours, totals |
| `ending_concurrency` | dimensions, at one instant only | "how many right now" |
| `minute_peak` / `bucket_peak` | **nothing** | exact peak of one slice, read directly |

**Never `SUM` a peak, and never average one.** Different titles peak at different
instants, so summing per-title peaks invents viewers who were never simultaneously
present. To combine peaks across time use `max()` — that composes, so an hourly peak is
the max of its minute peaks. To combine across *dimensions* you cannot combine at all;
read the pre-computed row for the grouping you want.

**Average concurrency is never `avg(minute_peak)`.** It is time-weighted:

```sql
sum(active_ms) / <window duration in ms>
```

Viewer-hours is the same quantity in different units: `sum(active_ms) / 3600000`.

## 2. Always filter on `grouping`

`serving_minute_current` stores **eleven overlapping aggregations of the same traffic**,
one per `grouping` value. They all describe the same viewers at different resolutions, so
a query that does not pin `grouping` sums every slice and overstates reality several
times over. Measured: blending all eleven reports average concurrency of **9,411.64**
where the truth is **855.58**.

> Every query against `serving_minute_current` or `serving_concurrency_minute` must
> contain either `grouping = '<one value>'` or `GROUP BY grouping`.

Available groupings, and what each costs to read for one hot hour:

| `grouping` | rows/hour | use when the question is… |
|---|---|---|
| `total` | 60 | overall concurrency, peak, average |
| `video type` | 140 | live vs vod vs preview |
| `platform` | 407 | per-device / per-client |
| `app version` | ~700 | rollout health |
| `category` | 3,870 | genre mix |
| `country` | 60 | per-location (single value `india` in this data) |
| `platform + country` | ~1,700 | location × device |
| `platform + video type` | ~1,000 | is live broken on one device |
| `content` | 31,537 | per-title |
| `platform + content` | ~90,000 | title × device |
| `all dimensions` | 41,845 | last resort |

**Pick the narrowest grouping that answers the question.** Read volume is a judged
criterion on this project; `total` is 60 rows where `all dimensions` is 41,845 for the
same answer.

Ignore the `dim_mask` column. It is the bit field `grouping` is derived from, kept for
the rollup's use. Never show it to a person and never filter on it — use `grouping`.

### When a filter is enough, and when it is not

For **averages, viewer-hours and instantaneous counts**, one grouping plus a `WHERE` on
the dimension is exact, because those measures are additive. For a **peak** it is not: a
peak must come from a row that was aggregated at that combination. `ANDROID_PHONE` reads
a peak of **1,461** at `grouping = 'platform'` and **223** at `grouping = 'all
dimensions'`, and both are correct — they are peaks of different things.

## 3. Which layer to read

| Object | Grain | Lag | Use |
|---|---|---|---|
| `serving_live_total`, `serving_live_content` | 10 s | ~7 s | "what is happening right now" |
| `serving_minute_current` | 1 min | ~6 min | **everything analytical** |
| `serving_drop_signal(...)` | 1 min | ~6 min | detecting a slice falling |

Default to `serving_minute_current`. The live layer is best-effort: it is rebuilt on a
trailing window, so buckets that age out keep an optimistic reading (each session's
interval ends at `last_signal + 120s`). Measured over-report: **0.053%** — small, but the
minute layer is the corrected one and is what reference figures are quoted against.

## 4. Check freshness before calling anything a drop

The minute layer publishes on a deliberate ~5-minute lag so late events can arrive. The
most recent minutes are therefore **absent, not empty**, and reading them as zero viewers
is the most common wrong answer this data produces.

```sql
SELECT layer, watermark_ts, dateDiff('second', watermark_ts, now()) AS lag_s
FROM sonyliv_prod.serving_watermark FINAL WHERE layer = 'minute'
```

Never report a decline whose last minute is at or after `watermark_ts`. Use the
`data_freshness` tool first when a question is about *now*.

## 5. Time

All timestamps are **UTC**. Windows are half-open — `$from <= t < $to`. Both edges must be
explicit; an inclusive right edge silently adds one bucket, which on an hour-long window
overstated the average by **4.3%**.

## 6. Reference figures — a sanity check on any new query

Hot hour `2026-07-26 10:00:00Z` to `11:00:00Z`, `grouping = 'total'`:

- exact peak concurrency **2,305**
- time-weighted average **855.578199**
- viewer-hours **855.578**
- peaked at **10:55:00Z**, reading **60 rows**

There is only one number now, which was not true before 2026-08-02. This server used to
report **855.603469** while the graded extract averaged **855.578199**, and the guide told
you to quote the former. The gap was a single synthetic session written during API testing
that carried a July timestamp and so landed inside the extract window — 90,972 ms of active
time, and 90,972 / 3,600,000 = 0.025270, exactly the difference. It has been removed, so the
serving layer now reproduces the graded figure to the digit. Quote **855.578199**.

If a rewrite of an existing query disagrees with these, the rewrite is wrong.

The extract spans `2026-07-14` to `2026-07-26`, with 93.9% of events inside a 2.5-hour
window on 2026-07-26. Data after that date is synthetic load, not the graded extract.

## 7. Recipes

**Concurrency trend over a window** — the shape of the audience.

```sql
SELECT minute_start AS ts, sum(active_ms) / 60000.0 AS avg_concurrent, max(minute_peak) AS peak
FROM sonyliv_prod.serving_minute_current
WHERE grouping = 'total' AND minute_start >= {from} AND minute_start < {to}
GROUP BY ts ORDER BY ts
```

**Peak and average for a window** — the two headline numbers.

```sql
SELECT max(minute_peak) AS exact_peak,
       sum(active_ms) / dateDiff('millisecond', {from}, {to}) AS avg_concurrency,
       sum(active_ms) / 3600000.0 AS viewer_hours
FROM sonyliv_prod.serving_minute_current
WHERE grouping = 'total' AND minute_start >= {from} AND minute_start < {to}
```

**Rank slices within a dimension** — who is biggest, and when did each peak.

```sql
SELECT dim_values, max(minute_peak) AS exact_peak,
       argMax(minute_start, minute_peak) AS peaked_at,
       sum(active_ms) / 3600000.0 AS viewer_hours
FROM sonyliv_prod.serving_minute_current
WHERE grouping = 'platform' AND minute_start >= {from} AND minute_start < {to}
GROUP BY dim_values ORDER BY exact_peak DESC
```

`dim_values` is the readable label for the row's dimension combination — a platform name,
a title, `IPHONE · live`. For `grouping = 'total'` it reads `all`.

**Hour-of-day shape across days** — when do people watch.

```sql
SELECT toHour(minute_start) AS hour_utc, sum(active_ms) / 3600000.0 AS viewer_hours
FROM sonyliv_prod.serving_minute_current
WHERE grouping = 'total' AND minute_start >= {from} AND minute_start < {to}
GROUP BY hour_utc ORDER BY hour_utc
```

**Is a slice falling** — retention against that slice's own trailing median. Prefer the
`detect_drops` tool; it sets the parameters correctly.

```sql
SELECT minute_start, dim_values, observed, baseline, retention
FROM sonyliv_prod.serving_drop_signal(
    win_from = {from}, win_to = {to}, grouping_key = 'platform',
    baseline_minutes = 15, min_baseline = 25, persist_minutes = 1)
WHERE has_opinion AND is_settled AND retention < 0.7
```

## 8. Framing an answer

Concurrency is not viewers-per-hour and not sessions. State which measure you used —
*peak concurrent*, *average concurrent*, or *viewer-hours* — because they answer different
questions and differ by orders of magnitude. Give the grouping you read and the window in
UTC, so the number can be reproduced.
