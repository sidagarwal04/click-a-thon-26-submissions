---
type: metric
title: Coupon Segment Performance
description: Coupon funnel + margin cut by device_type, geoip_country_code and destination — which codes work where. Served by both coupon aggs.
metric_id: coupon_segment_performance
served_by_mv: coupon_funnel_daily_agg + coupon_discount_daily_agg
computable: true
timestamp: 2026-08-07
tags: [metric, coupon, segment, device, geo, destination]
---

# Formula

```
-- funnel side (apply rate / reject mix per segment)
GROUP BY device_type, geoip_country_code        [coupon_funnel_daily_agg]

-- discount / margin side (per code, per geography)
GROUP BY coupon_code, device_type, geoip_country_code, destination  [coupon_discount_daily_agg]
```

# Notes / caveats

- ✅ Served by the segment dimensions on **both** aggs — funnel-stage cuts from
  [coupon_funnel_daily](/tables/coupon_funnel_daily.md); discount/value + `destination` cuts from
  [coupon_discount_daily](/tables/coupon_discount_daily.md).
- ⚠️ **`destination` is only on the discount agg**, not the funnel agg — funnel-stage cuts by
  destination require the base table [promo_coupon_checkout](/tables/promo_coupon_checkout.md)
  (destination is untyped there, read via CAST, no index).
- ⚠️ Prefer **`device_type`** over `os` for platform slices — `os` is not a rollup dimension on
  either agg and carries the Android-null gap; see [android-os-null](/contradictions/android-os-null.md).
- All segment dims coalesce to `''` on NULL in the aggs — handle the empty-string bucket.
- Answers spec PM question: "segment cuts (device, geo, destination); which codes work where".

# Source

- Tables: [coupon_funnel_daily](/tables/coupon_funnel_daily.md), [coupon_discount_daily](/tables/coupon_discount_daily.md).
- Spec: `specs/unseen_data/spec.md`; metrics: `Atlys/schemas/unseen_data.metrics.json` (M5).
