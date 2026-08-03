---
name: atlys-materialized-views
description: Turn an Atlys spec's "Questions the PM will ask" into confirmed metrics, decide whether each warrants a materialized view, and if so generate incremental AggregatingMergeTree MVs that read payload.* from the single base table and filter by payload.event for event-type-specific metrics. Confirms ambiguous metric formulas with the user before generating, and writes a metrics manifest for the Context Agent. Every AggregatingMergeTree backing table carries an agg_insert_time DateTime64 MATERIALIZED now64(3) watermark and keys its TTL on agg_insert_time (compute time), NOT on the event-day column — otherwise backfilled/recomputed historical rollups are silently TTL-deleted relative to the server clock. Invoke during onboarding after profiling. Full pattern + examples in references/materialized-views.md.
---

# Skill: Metrics & Materialized Views

The spec's **"Questions the PM will ask"** are the frequently-used queries this spec must
serve; each is a candidate **metric**. This skill: (1) turns each PM question into a concrete
metric formula, confirming with the user when ambiguous; (2) decides which metrics warrant a
materialized view; (3) generates the MVs; and (4) writes the **metrics manifest** consumed by
the Context Agent.

An MV is a **pre-aggregated rollup** over the raw JSON-column table. Create one **only** when a
metric is answered by repeated aggregate queries — not raw-row lookups. Do **not** add MVs by
default.

## Step 1 — PM questions → metric formulas (confirm ambiguous ones)

For each candidate metric from `atlys-ndjson-profiling` (one per PM question, plus any the user
named), pin down a concrete formula from the NDJSON paths:

| Metric shape | Formula skeleton |
|---|---|
| count / volume | `countState()` over the event type, grouped by dims + time |
| conversion / funnel rate | `count(numerator_event) / count(denominator_event)`, keyed by identity (usually `user_id`) |
| percentile / latency | `quantileState(0.95)(<metric_path>)` filtered to the event type carrying it |
| sum / average | `sumState()` / `avgState(<metric_path>)` grouped by dims |
| adoption / share | `count(segment) / count(total)` over a dimension |

**Ambiguity gate — ask once before generating.** If the numerator/denominator event pair, the
keying (per `user_id` vs per session/attempt), or the metric path is **not unambiguous** from
the question + paths, **propose a high-level formula and ask the user to confirm or correct
it** before building the MV. Example:

```
❓ Confirm metric formula — "Does Express lift checkout → success conversion?"
   Proposed: conversion = uniq(user_id WHERE event='express_payment_confirmed')
                        ÷ uniq(user_id WHERE event='express_checkout_shown')
   Sliced by: destination, geoip_country_code, day
   Confirm this formula, or tell me the correct numerator/denominator/keying.
```

Do **not** silently guess an ambiguous formula. Clear formulas proceed without a question.

## Step 2 — MV need-derivation (both signals must hold)

**Signal A — the confirmed PM-question metrics (+ any user-named metrics).**

| Metric / phrase (from PM questions or the user) | MV signal |
|---|---|
| "conversion rate", "funnel", "drop-off across steps" | ✅ strong — ratio/count MV |
| "p50 / p95 / p99", "percentile", "latency distribution" | ✅ strong — quantile MV |
| "per {dimension} over time", "hourly/daily trend of …" | ✅ strong — time-bucketed rollup MV |
| "top N by …", "count/sum of … grouped by …" | ✅ moderate — count/sum MV |
| "average … by …" | ✅ moderate — avg MV |
| "show the raw events", "look up a single record", "debug one session" | ❌ none — raw table is enough |

**Signal B — the NDJSON profile has the ingredients:** at least one numeric metric path (or a
countable event) AND a low-cardinality dimension path to GROUP BY AND the event timestamp path.

```
MV_NEEDED = (a confirmed PM-question/user metric that aggregates — Signal A ✅)
            AND
            (NDJSON has the metric/dimension/timestamp to satisfy it — Signal B ✅)
```

If **no** (raw-lookup feature, missing ingredients), create **no MV** for that metric — but
still record its definition in the metrics manifest so the Context Agent knows it exists.

## Output the verdict

```
🧮 MV derivation
─────────────────────────────────────────────────
Signal A (Q3 metrics + spec.md) : {user metrics + matched phrases, or "no aggregation asks"}
Signal B (NDJSON ingredients)   : metric paths={...}; dimensions={...}; timestamp={...}
Verdict                         : {MV NEEDED — list proposed MVs  |  NO MV — reason}
─────────────────────────────────────────────────
```

## Always incremental, never refreshable (for these metrics)

Generate incremental `AggregatingMergeTree` MVs that fire on insert. An incremental MV
aggregates only each newly inserted block into partial states and **never rescans the base
table** — cost scales with insert size, not table size. `toStartOfDay`/`toStartOfHour` is just
the bucket granularity, not a refresh schedule. Only fall back to a refreshable
(`REFRESH EVERY`) MV when the aggregation genuinely cannot be incremental — JOINs across
tables, dedup/`argMax` over full history, top-N/window functions. Standard
funnel-count / latency-quantile / sum metrics never need this.

## Generation

For each proposed MV, emit the **two-object pattern** — an `AggregatingMergeTree` backing table
plus a `CREATE MATERIALIZED VIEW ... TO ...` that reads dimensions/metrics through `payload.*`
paths from the **single base table**. When a metric applies to only some event types (e.g.
`payment.*` on `express_payment_confirmed`), add `WHERE payload.event = '<event_type>'`. Wrap
GROUP BY dims in `COALESCE(CAST(payload.{dim} AS String), '')` (backing-table key columns must
be NOT NULL). Append the MV objects to the **same `.sql` file**, after the base table, and note
them in the file header `-- MVs:` line.

> Exact pattern, aggregate-state mapping, casting rules, and two worked examples
> (`destination_daily_funnel_agg`, `payment_latency_daily_agg`):
> [references/materialized-views.md](references/materialized-views.md).

## Write the metrics manifest (for the Context Agent)

After metrics are confirmed and MVs (if any) generated, write **one manifest per spec** so the
Context Agent can create/update the `metric` concepts without re-deriving them:

```
$REPO_DIR/Atlys/schemas/{schema_name}.metrics.json
```

```json
{
  "spec": "01_express_checkout",
  "database": "atlys",
  "base_table": "express_checkout",
  "generated_at": "<ISO-8601>",
  "metrics": [
    {
      "name": "express_conversion_rate",
      "pm_question": "Does Express lift checkout → success conversion vs standard checkout?",
      "formula": "uniq(user_id WHERE event='express_payment_confirmed') / uniq(user_id WHERE event='express_checkout_shown')",
      "numerator": "event='express_payment_confirmed'",
      "denominator": "event='express_checkout_shown'",
      "keyed_by": "user_id",
      "dimensions": ["destination", "geoip_country_code", "day"],
      "confirmed_by_user": true,
      "served_by_mv": "destination_daily_funnel_agg",
      "notes": "conversion computed from funnel counts in the agg table"
    },
    {
      "name": "express_payment_latency_p95",
      "pm_question": "How much faster is Express (payment.latency_ms)?",
      "formula": "quantile(0.95)(payload.`payment.latency_ms`)",
      "event_filter": "event='express_payment_confirmed'",
      "dimensions": ["destination", "geoip_country_code", "day"],
      "confirmed_by_user": false,
      "served_by_mv": "payment_latency_daily_agg"
    }
  ]
}
```

Rules for the manifest:
- **One entry per confirmed metric**, whether or not an MV serves it (`served_by_mv: null` when
  the raw table answers it).
- Record `confirmed_by_user: true` for any formula the user confirmed/corrected via the
  ambiguity gate — this is the provenance the Context Agent stamps on the `metric` concept.
- Keep it in sync with the `-- MVs:` header line and the actual objects in the `.sql`.

`atlys-git-pr` includes this manifest in the PR body and passes its path to the Context Agent.
