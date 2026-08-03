---
type: metric
title: Coupon Apply Rate
description: Share of coupon-field impressions that result in a valid applied coupon (coupon_field_shown → coupon_applied). Served by the coupon funnel daily agg.
metric_id: coupon_apply_rate
served_by_mv: coupon_funnel_daily_agg
computable: true
timestamp: 2026-08-07
tags: [metric, coupon, funnel, apply-rate]
---

# Formula

```
coupon_apply_rate = uniqMerge(users_state) [event_type = 'coupon_applied']
                  / uniqMerge(users_state) [event_type = 'coupon_field_shown']
```

Event-count variant: `countMerge(events_state)` in place of `uniqMerge(users_state)`.

# Notes / caveats

- ✅ Single-table, served entirely by [coupon_funnel_daily](/tables/coupon_funnel_daily.md) — both
  stages are rows in the same funnel agg (MV has no WHERE filter, so all six event types survive).
- State the **basis** (distinct users vs raw events) explicitly — they differ when a user retries.
- ⚠️ Not yet populated — agg reports `total_rows = 0` (see freshness caveat on
  [promo_coupon_checkout](/tables/promo_coupon_checkout.md)).
- Answers spec PM question: "coupon apply rate (field_shown → coupon_applied)".

# Source

- Table: [coupon_funnel_daily](/tables/coupon_funnel_daily.md); base [promo_coupon_checkout](/tables/promo_coupon_checkout.md).
- Spec: `specs/unseen_data/spec.md`; metrics: `Atlys/schemas/unseen_data.metrics.json` (M1).
