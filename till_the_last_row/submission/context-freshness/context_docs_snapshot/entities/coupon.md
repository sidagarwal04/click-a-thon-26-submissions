---
type: entity
title: Coupon
description: A promo code entered at checkout, validated (valid/rejected), and — if valid — applied for a discount. Identified by coupon_code; a null/empty coupon_code marks the no-coupon baseline.
timestamp: 2026-08-07
tags: [entity, coupon, promo, checkout]
---

# Definition

A **promo code** a traveller enters on the checkout screen. It is validated: **valid** → a discount
(`discount_type` percent/flat, `discount_amount`) is computed and shown, and the user pays the
discounted `final_value`; **rejected** → a `reject_reason` is recorded and no discount applies.

# Identity

- `coupon_code` (`String`, typed path, `bloom_filter(0.01)` skip-index on the base table).
- ⚠️ **`coupon_code IS NULL` / `''` is meaningful** — it marks the **no-coupon baseline** cohort
  (users who checked out without applying a valid code), not missing data. Do not filter it out.

# Attributes

- `discount_type` — `percent` / `flat` (untyped payload path).
- `discount_amount` — discount value (untyped; CAST to `Float64`; drives margin cost M4).
- `reject_reason` — `expired` / `invalid_code` / `min_cart_not_met` / `already_used` (typed, `set(8)` index).
- `cart_value`, `final_value`, `currency` — checkout economics (untyped payload paths).

# Grain

A coupon is observed **per event row**, not as a standalone dimension table; the same code recurs
across many users/events. Per-code rollups live in
[coupon_discount_daily](/tables/coupon_discount_daily.md).

# Related

- Base table: [promo_coupon_checkout](/tables/promo_coupon_checkout.md)
- Aggregates: [coupon_funnel_daily](/tables/coupon_funnel_daily.md), [coupon_discount_daily](/tables/coupon_discount_daily.md)
- Metrics: [coupon-apply-rate](/metrics/coupon-apply-rate.md), [coupon-reject-mix](/metrics/coupon-reject-mix.md), [coupon-margin-cost](/metrics/coupon-margin-cost.md)
- Known issues: [K6](/known-issues/k6-summer20-coupon.md)
- Source: `specs/unseen_data/spec.md`, live `atlys` schema.
