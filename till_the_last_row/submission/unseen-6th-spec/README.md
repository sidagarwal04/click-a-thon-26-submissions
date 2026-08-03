# 6th Spec (Unseen / Surprise Round) — `unseen_data`

Feature: **Promo / Coupon at Checkout.** This is the sealed spec; everything here was
produced by our pipeline, evidenced by the trace.

## Artifacts

| File | What |
| --- | --- |
| `unseen_data.sql` | Generated DDL — base `promo_coupon_checkout` (JSON-`payload` SharedMergeTree, 6 event types) + 2 SharedAggregatingMergeTree rollups (`coupon_funnel_daily_agg`, `coupon_discount_daily_agg`) + their MVs. |
| `unseen_data.metrics.json` | Confirmed PM metrics M1–M5 (formula, dimensions, serving MV). |
| `unseen_data.insights.json` | Analytics Agent's machine-readable insights (confidence scores, related K-issues/metrics, trace URL). |

## Insight summary (product audience)

<!-- Paste the Analytics Agent's PM-ready prose summary for the 6th spec here (the human
half that pairs with insights.json). Keep it product-facing, not DB-facing. -->

```
<PASTE 6TH-SPEC PM INSIGHT SUMMARY>
```

## Trace (MANDATORY)

Full `spec → schema → context → insight` chain for `unseen_data`:

**`<PASTE LANGFUSE CHAIN TRACE LINK>`** — also listed in [`../TRACES.md`](../TRACES.md).

## Notes from the run

- Context updated to **v7** when these tables landed (see
  [`../context-freshness/CONTEXT_FRESHNESS.md`](../context-freshness/CONTEXT_FRESHNESS.md)) —
  the Analytics Agent reasoned from v7, not a stale snapshot.
- The schema follows both baked-in deviations: **D1** (numeric JSON paths indexed via
  `CAST(...) minmax` since untyped; string/bool paths typed in the `payload(...)` hint) and
  **D2** (agg tables carry `agg_insert_time` and TTL on ingestion time, not event day).
