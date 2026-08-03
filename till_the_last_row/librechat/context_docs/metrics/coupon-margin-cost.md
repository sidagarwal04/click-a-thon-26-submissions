---
type: metric
title: Coupon Margin Cost
description: Total discount given (SUM discount_amount) by coupon_code, separating codes that drive volume from codes that erode margin. Served by the coupon discount daily agg.
metric_id: coupon_margin_cost
served_by_mv: coupon_discount_daily_agg
computable: true
timestamp: 2026-08-07
tags: [metric, coupon, margin, discount, revenue]
---

# Formula

```
margin_cost(code)   = sumMerge(discount_amount_state)  GROUP BY coupon_code
volume(code)        = countMerge(events_state)         GROUP BY coupon_code
erosion_ratio(code) = sumMerge(discount_amount_state) / sumMerge(cart_value_state)
```

Realised revenue per code = `sumMerge(final_value_state)`.

# Notes / caveats

- ✅ Served by [coupon_discount_daily](/tables/coupon_discount_daily.md) — `coupon_code` is the
  leading grain dimension there, so per-code margin reads efficiently.
- The discount MV filters `payload.discount_amount IS NOT NULL`, so this counts **discount-bearing
  events only** (not coupon-field impressions).
- `discount_amount` / `cart_value` / `final_value` are **untyped** in the base JSON hint and are
  `CAST` to `Float64` before `sumState()` — same numeric-CAST reality as **D1**.
- Pair `discount_amount` (cost) with `events_state` (volume) to answer "which codes drive volume
  vs erode margin".
- ⚠️ Related campaign context: [K6](/known-issues/k6-summer20-coupon.md) (`SUMMER20`) → expect
  elevated apply + lower realised value.
- ⚠️ Not yet populated — agg reports `total_rows = 0`.
- Answers spec PM question: "total discount_amount; which codes drive volume vs erode margin".

# Source

- Table: [coupon_discount_daily](/tables/coupon_discount_daily.md); base [promo_coupon_checkout](/tables/promo_coupon_checkout.md).
- Spec: `specs/unseen_data/spec.md`; metrics: `Atlys/schemas/unseen_data.metrics.json` (M4).
