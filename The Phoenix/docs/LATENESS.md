# Lateness policy

**2026-08-01.** How late is too late, what happens when that line is crossed, and why two of the
three numbers below are marked provisional rather than quietly published.

## The policy

| Setting | Value | State |
|---|---:|---|
| `allowed_lateness_seconds` | 90 | **provisional** |
| `finalization_delay_seconds` | 3600 | **provisional** |
| `very_late_event_action` | accept, revise, and record | decided |

Enforced in exactly one place, `sql/insights/schema/09_late_event_audit.sql`, and verified end to
end by `[V:lateness_classifier]`. A materialized view cannot take query parameters, so the two
boundaries are literals in its body. That is deliberate: the enforced policy and the documented
policy cannot drift apart when there is one place to change either, and recreating the view is a
`DROP` and a `CREATE` that rewrites no data.

## Lateness, defined

```text
lateness_seconds = arrival_timestamp - event_timestamp
```

Both are real columns on `raw_events` as of generation 2. `arrival_timestamp` is emitted by
`raw_events_mv` as `now64(3)`, so it is materialised into the part at insert time and means the
same thing every time it is read.

**Not `ingested_at`.** That column was added by `ALTER` after the July rows were loaded. ClickHouse
does not rewrite existing parts, so for those 905,558 rows the `DEFAULT now()` is evaluated at read
time and the column equals the wall clock of whichever query reads it. Filtering on it inverts the
dataset: it retains 0 of the corpus rows and all of the live ones, which is exactly backwards. The
whole reason `arrival_timestamp` defaults to a constant sentinel rather than to `now64(3)` is to
avoid reproducing that bug.

## Classes

| Class | Condition | Meaning |
|---|---|---|
| `invalid_future_event` | `lateness_seconds < 0` | The event claims to have happened after it arrived. A clock is wrong. |
| `on_time` | `0 <= lateness_seconds <= 90` | Within the gap the state machine already treats as the limit of what silence can mean. |
| `late_acceptable` | `90 < lateness_seconds <= 3600` | Late, absorbed correctly, arrived before anyone could reasonably have read the minute as final. |
| `late_after_finalization` | `lateness_seconds > 3600` | The minute it revises may already have been published and read. |

## What happens to a very late event

**Accept it, let it revise the answer, and record that the answer moved.**

The alternative, dropping or quarantining, was rejected on a measured property rather than a
preference: the pipeline already absorbs late events correctly. `session_minute_runs` is a
`CollapsingMergeTree` and a re-derived session writes `sign = -1` rows for what it had and `sign =
+1` rows for what it has now, which the delta view turns into two more additive rows. Proven at zero
diffs against batch truth in `[V:open_sessions]`. Refusing an event the pipeline can absorb would
make the answer worse in order to make the policy tidier.

What the policy adds is the record. A `late_after_finalization` row means a number somebody may have
already read has since changed, and that is a thing to be able to look up rather than infer.

## The audit table is an exception log, not a census

A row lands in `late_event_audit` only when the class is not `on_time`. Auditing every on-time event
would write one row per raw event, which at the Stage 5 volume is nine million rows restating what
`raw_events` already holds.

**So a count from this table is a numerator with no denominator.** For a rate, divide by the
`raw_events` count over the same window.

## Why two numbers are provisional

Every row currently in `phoenix_next` arrived by being copied from `phoenix`, and a copied row has
no observed arrival time. It carries the sentinel `arrival_timestamp = 0` and is excluded from every
lateness query. **The measurable lateness distribution is therefore empty: 0 observed arrivals out
of 2,188,714 rows.**

Sizing a boundary against copied rows would mean computing `arrival - event` over rows whose arrival
was manufactured by the copy, producing a tight distribution centred on nothing and a boundary that
looks measured and is not. `docs/corrections.md` is a list of eleven numbers that were plausible,
published and unchecked, and this would have been the twelfth.

The provisional values are therefore reasoned, and labelled as reasoned:

- **90 seconds** is `tolerance_s`, the gap the state machine already treats as the limit of what
  silence can mean. An event later than that could not have extended a run by simply continuing it.
- **3600 seconds** exceeds any batch derive cadence observed on this project, which makes it a
  defensible first guess at the point after which a published minute may have been read.

## The query that replaces them

Stage 5 runs our own ingest, at ten times the current volume, with arrival timing under our control.
That produces real observed arrivals, and this is the query that sizes the boundary from them:

```sql
SELECT
    count()                                                             AS observed_arrivals,
    quantiles(0.5, 0.9, 0.99, 0.999)(dateDiff('second', event_timestamp, arrival_timestamp)) AS p50_p90_p99_p999,
    max(dateDiff('second', event_timestamp, arrival_timestamp))         AS worst
FROM raw_events
WHERE arrival_timestamp > toDateTime64(0, 3);
```

The rule for reading it: set `allowed_lateness_seconds` at p99, so the common case is on time and
the tail is visible rather than hidden; set `finalization_delay_seconds` above p999, so finalization
means finalized rather than usually finalized. Publish the observed count alongside both, because a
percentile over a small sample is a number with a confidence interval nobody wrote down.

Until that runs, both values stay marked provisional here, in the DDL, and in the classifier's own
evidence artifact.

## Reproduce

```bash
./scripts/test_lateness_classifier.sh    # four events, one per class, scratch database
./scripts/init_insights.sh phoenix_next  # create or update the audit table and its view
```
