# 6th spec — Promo / Coupon at Checkout

**Instrumentation job:** `20260802T034920_06_promo_coupon_checkout`
**Table:** `silver.promo_coupon_checkout_events`
**Rows loaded:** 5363
**Langfuse trace ID:** `571e24649eb2729de05f2e53f35d351b`
**Langfuse URL:** https://jp.cloud.langfuse.com/project/cmsb9811u001iad0izjcsxm8e/traces/571e24649eb2729de05f2e53f35d351b

## Product-facing summary

Feature instrumented from the sealed unseen spec. Silver table `silver.promo_coupon_checkout_events` holds coupon funnel events
(coupon_field_shown, coupon_entered, coupon_applied, coupon_rejected, discount_shown, checkout_with_coupon). Success event: `checkout_with_coupon`.

## Context diff (agent)

# Context Diff

## Added Feature

- Feature: Promo / Coupon at Checkout
- Slug: `promo_coupon_checkout`
- Table: `silver.promo_coupon_checkout_events`
- Primary entity: `application_id`
- Workflow type: `funnel`
- Events: `coupon_field_shown` -> `coupon_entered` -> `coupon_applied` -> `coupon_rejected` -> `discount_shown` -> `checkout_with_coupon`

## Product insight (Analytics Agent)

**Question:** How are promo codes affecting checkout conversion, and where do coupons get rejected?

**Answer:** Feature funnel: coupon_field_shown=2,100 → coupon_entered=848 → coupon_applied=580 → coupon_rejected=268 → discount_shown=580 → checkout_with_coupon=987. Start→end conversion: 47.00% (2,100 → 987).

**Ask job:** `20260802T035042_ask_how_are_promo_codes_affecting_checkout_conversio`
**Ask trace ID:** `2615da1310abdacee056c3ad4de7317a`
**Ask Langfuse URL:** https://jp.cloud.langfuse.com/project/cmsb9811u001iad0izjcsxm8e/traces/2615da1310abdacee056c3ad4de7317a

Full write-up: [`../analytics/05_promo_coupon_insight.md`](../analytics/05_promo_coupon_insight.md)
