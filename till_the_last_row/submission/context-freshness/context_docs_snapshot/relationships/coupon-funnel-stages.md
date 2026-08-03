---
type: relationship
title: Coupon micro-funnel (coupon_field_shown → checkout_with_coupon, on user_id)
description: Within-table stage transitions of the coupon checkout funnel — same base table, six event types keyed by payload.event, sequenced per user_id/application_id.
timestamp: 2026-08-07
tags: [relationship, funnel, coupon, within-table, cohort]
---

# Join

All stages are rows in the **same** base table [promo_coupon_checkout](/tables/promo_coupon_checkout.md),
discriminated by `payload.event`. Cross-stage cohorts sequence on `user_id` (+ `application_id`):

```
same table, self-join on payload.user_id (and payload.application_id)
AND later.payload.timestamp >= earlier.payload.timestamp
```

# Stage order

```
coupon_field_shown → coupon_entered → coupon_applied  → discount_shown → checkout_with_coupon
                                    ↘ coupon_rejected (reject_reason)
```

- `checkout_with_coupon` with `coupon_code IS NULL` = the **no-coupon baseline** branch (users who
  saw the field but did not apply a valid code).

# Purpose

- Stage counts (apply rate M1, reject mix M2) are pre-aggregated in
  [coupon_funnel_daily](/tables/coupon_funnel_daily.md).
- Per-user sequencing (conversion-lift M3 cohort vs baseline) is a **query-time self-join on the
  base table** — the funnel agg holds per-stage distinct users but not who-did-A-then-B. See
  [coupon-conversion-lift-single-table-gap](/contradictions/coupon-conversion-lift-single-table-gap.md).

# Notes / caveats

- ✅ **Within-table**, no cross-spec join needed — all six event types share one base table.
- ⚠️ `user_id` is typed but **not in the ORDER BY** (dropped as high-cardinality), so the
  self-join scans within `toYYYYMMDD(ch_insert_time)` partitions.
- ⚠️ Not yet populated — base table reports `total_rows = 1` / no real event rows.

# Source

- Table: [promo_coupon_checkout](/tables/promo_coupon_checkout.md); agg [coupon_funnel_daily](/tables/coupon_funnel_daily.md).
- Spec: `specs/unseen_data/spec.md`; live `atlys` schema.
