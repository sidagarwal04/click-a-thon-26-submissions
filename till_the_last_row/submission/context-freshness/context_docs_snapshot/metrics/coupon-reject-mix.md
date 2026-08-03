---
type: metric
title: Coupon Valid/Rejected Mix + Reject-Reason Breakdown
description: Valid-vs-rejected split of entered coupons and the distribution of rejection reasons (expired / invalid_code / min_cart_not_met / already_used). Served by the coupon funnel daily agg.
metric_id: coupon_reject_mix
served_by_mv: coupon_funnel_daily_agg
computable: true
timestamp: 2026-08-07
tags: [metric, coupon, funnel, reject, mix]
---

# Formula

```
valid_share    = users[event_type='coupon_applied']  / users[event_type='coupon_entered']
rejected_share = users[event_type='coupon_rejected']  / users[event_type='coupon_entered']
reject_mix     = events_state GROUP BY reject_reason  [event_type='coupon_rejected']
```

(where `users[...] = uniqMerge(users_state)` filtered on `event_type`.)

# Notes / caveats

- ✅ Served by [coupon_funnel_daily](/tables/coupon_funnel_daily.md) — `reject_reason` is a grain
  dimension there.
- `reject_reason` domain (spec): `expired` / `invalid_code` / `min_cart_not_met` / `already_used`.
  In the agg these coalesce to `''` when absent, so filter `reject_reason != ''` for the breakdown.
- ⚠️ **Designed-for but currently unobservable** — the 5,364-event sample contains **no
  `coupon_rejected` rows**, so this metric returns empty until real rejects land. This is a data
  gap, not a schema error. See
  [coupon-reject-designed-not-observed](/contradictions/coupon-reject-designed-not-observed.md).
- Answers spec PM question: "valid vs rejected mix; top reject reasons".

# Source

- Table: [coupon_funnel_daily](/tables/coupon_funnel_daily.md); base [promo_coupon_checkout](/tables/promo_coupon_checkout.md).
- Spec: `specs/unseen_data/spec.md`; metrics: `Atlys/schemas/unseen_data.metrics.json` (M2).
