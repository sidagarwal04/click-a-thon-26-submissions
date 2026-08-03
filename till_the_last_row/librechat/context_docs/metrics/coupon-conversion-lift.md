---
type: metric
title: Coupon Conversion Lift
description: Do coupon users reach checkout at a higher rate than the no-coupon baseline? Cohort = users who coupon_applied then checkout_with_coupon (non-null code); baseline = users who saw the coupon field but never applied and checked out with coupon_code null.
metric_id: coupon_conversion_lift
served_by_mv: null
computable: partial
timestamp: 2026-08-07
tags: [metric, coupon, conversion, lift, cohort]
---

# Formula (user-confirmed)

```
cohort_rate   = uniq(user_id who checkout_with_coupon AND coupon_code IS NOT NULL)
              / uniq(user_id who coupon_applied)

baseline_rate = uniq(user_id who checkout_with_coupon AND coupon_code IS NULL)
              / uniq(user_id who coupon_field_shown AND never coupon_applied)

conversion_lift = cohort_rate / baseline_rate
```

Per-stage `uniq(user_id)` is captured as `uniqState(user_id)` in the funnel agg.

# Notes / caveats

- ⚠️ **Partial MV coverage** (`served_by_mv: null` for the composite). The
  [coupon_funnel_daily](/tables/coupon_funnel_daily.md) agg supplies each **stage's** distinct-user
  count (`uniqMerge(users_state)`), but it **cannot express per-user sequencing** — "applied *then*
  checked out", or "saw the field but *never* applied". Those cohort/anti-cohort definitions require
  a **query-time self-join on the base table** [promo_coupon_checkout](/tables/promo_coupon_checkout.md)
  keyed on `user_id`. See
  [coupon-conversion-lift-single-table-gap](/contradictions/coupon-conversion-lift-single-table-gap.md).
- The **no-coupon baseline** = `checkout_with_coupon` rows with `coupon_code IS NULL` (in the agg,
  `coupon_code = ''`) — do **not** filter these out; they are the denominator's numerator side.
- ⚠️ `user_id` is typed but **not in the base ORDER BY** (dropped as high-cardinality), so the
  self-join scans within date partitions rather than seeking the sort key.
- Related to the funnel-conversion family — state the denominator explicitly, see
  [dual-conversion-definition](/contradictions/dual-conversion-definition.md).
- Answers spec PM question: "do coupon users reach checkout_with_coupon at a higher rate than the
  no-coupon baseline?"

# Source

- Base table: [promo_coupon_checkout](/tables/promo_coupon_checkout.md); stage users: [coupon_funnel_daily](/tables/coupon_funnel_daily.md).
- Spec: `specs/unseen_data/spec.md`; metrics: `Atlys/schemas/unseen_data.metrics.json` (M3).
