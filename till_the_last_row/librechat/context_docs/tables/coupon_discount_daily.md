---
type: table
title: coupon_discount_daily_agg
description: Pre-aggregated daily coupon discount/margin rollup — sum of discount_amount, cart_value, final_value and event count by day × coupon_code × device_type × geoip_country_code × destination. Fed by coupon_discount_daily_mv.
kind: aggregate
source_spec: specs/unseen_data/spec.md
source_schema: Atlys/schemas/unseen_data.sql
source_metrics: Atlys/schemas/unseen_data.metrics.json
live: true
timestamp: 2026-08-07
tags: [table, aggregate, rollup, coupon, discount, margin, live]
---

# Purpose

`SharedAggregatingMergeTree` daily discount/margin rollup of
[promo_coupon_checkout](/tables/promo_coupon_checkout.md). Serves the margin-cost metric (M4) and
the discount/value side of segment performance (M5) without scanning the base table. Fed
incrementally by the `atlys.coupon_discount_daily_mv` MATERIALIZED VIEW.

> ⚠️ Reports `total_rows = 0` at time of writing — schema landed but the base table is not yet
> ingested/merged (see freshness caveat on [promo_coupon_checkout](/tables/promo_coupon_checkout.md)).

# Grain (ORDER BY)

`coupon_code × device_type × geoip_country_code × destination × event_day`

- `event_day` `Date` = `toDate(payload.timestamp)` (event time).
- Dimensions `coupon_code`, `device_type`, `geoip_country_code`, `destination` are each
  `coalesce(CAST(payload.<dim>,'String'), '')` in the MV → NULL/missing lands in the **empty-string**
  bucket. `coupon_code = ''` therefore folds the no-coupon baseline into one bucket.
- ⚠️ Note the grain leads with **`coupon_code`** (not `event_type`) — this agg is code/margin-first,
  so "which codes drive volume vs erode margin" (M4) reads efficiently; it does **not** carry
  `event_type` or `reject_reason` (those live on the funnel agg).
- PARTITION BY `toYYYYMM(event_day)`.

# MV row filter

- The `coupon_discount_daily_mv` selects **only rows with `payload.discount_amount IS NOT NULL`**
  — i.e. discount-bearing events (`coupon_applied` / `checkout_with_coupon` with a discount). So
  this agg does **not** count coupon-field impressions; use the funnel agg for stage counts.

# Aggregate states

| column | state | measure | finalizer |
|---|---|---|---|
| discount_amount_state | `AggregateFunction(sum, Float64)` | total discount given | `sumMerge(discount_amount_state)` |
| cart_value_state | `AggregateFunction(sum, Float64)` | total cart value | `sumMerge(cart_value_state)` |
| final_value_state | `AggregateFunction(sum, Float64)` | total charged value | `sumMerge(final_value_state)` |
| events_state | `AggregateFunction(count)` | discount-bearing event count | `countMerge(events_state)` |

- **Margin cost** (M4) = `sumMerge(discount_amount_state)` grouped by `coupon_code`; pair with
  `events_state` (volume) to separate high-volume from high-erosion codes.
- ⚠️ `discount_amount` / `cart_value` / `final_value` are **untyped** in the base JSON hint, so the
  MV `CAST`s them to `Float64` before `sumState()` — same numeric-CAST reality as **D1**.

# Deviations

- **D2** — TTL keyed on `agg_insert_time` (`DateTime64(3,'UTC') MATERIALIZED now64(3)`),
  `toDateTime(agg_insert_time) + 90 day`, `ttl_only_drop_parts = 1` (not on `event_day`).

# Serves

- [coupon-margin-cost](/metrics/coupon-margin-cost.md) (M4)
- [coupon-segment-performance](/metrics/coupon-segment-performance.md) (M5, discount/value + `destination` dim)
- ❌ Does **not** serve funnel/reject metrics (M1/M2) — no `event_type`/`reject_reason` dims; use [coupon_funnel_daily](/tables/coupon_funnel_daily.md).

# Related

- Base table: [promo_coupon_checkout](/tables/promo_coupon_checkout.md)
- Sibling agg: [coupon_funnel_daily](/tables/coupon_funnel_daily.md)
- Entities: [event](/entities/event.md), [destination](/entities/destination.md)
- Known issues: [K6](/known-issues/k6-summer20-coupon.md)
- Source: `Atlys/schemas/unseen_data.sql`, live `atlys` schema (`coupon_discount_daily_agg`, `coupon_discount_daily_mv`)
