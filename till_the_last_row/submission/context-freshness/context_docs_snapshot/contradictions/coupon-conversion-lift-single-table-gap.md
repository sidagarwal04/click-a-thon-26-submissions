---
type: contradiction
title: Conversion-lift (M3) needs per-user sequencing the funnel agg cannot express
description: The coupon funnel agg holds per-stage distinct-user counts, but M3's cohort ("applied THEN checked out") and baseline ("saw field, never applied") require per-user ordering only the base table self-join can provide.
severity: medium
status: open
timestamp: 2026-08-07
tags: [contradiction, metric, coupon, aggregate, gap]
---

# Claim

The `unseen_data` metrics manifest lists **conversion lift (M3)** among the coupon metrics, and the
schema ships [coupon_funnel_daily](/tables/coupon_funnel_daily.md) with `uniqState(user_id)` per
stage — implying M3 is served by the funnel rollup like M1/M2.

# Conflicting claim / evidence

M3's user-confirmed definition is **sequential and cohort-based**:

- cohort = distinct `user_id` who `coupon_applied` **and then** `checkout_with_coupon` with a
  **non-null** `coupon_code`;
- baseline = distinct `user_id` who saw `coupon_field_shown`, **never** `coupon_applied`, and
  `checkout_with_coupon` with `coupon_code IS NULL`.

The funnel agg's `uniqMerge(users_state)` gives **per-stage** distinct users independently — it
**cannot** express "applied *then* checked out" or "saw the field but *never* applied" for the same
user. That requires a **query-time self-join on the base table**
[promo_coupon_checkout](/tables/promo_coupon_checkout.md) keyed on `user_id` with a timestamp order,
which is **not** what the MV materializes.

# Why it matters

If the Analytics Agent computes M3 by dividing two independent stage counts from the funnel agg, it
will **overstate/understate lift** — stage-count ratios are not the same as sequenced-cohort rates,
and they cannot exclude the "never applied" users from the baseline. Worse, `user_id` is **not in
the base ORDER BY** (dropped as high-cardinality), so the correct self-join scans within date
partitions rather than seeking the sort key — a cost the agg-only path silently hides.

# Recommended resolution

- Serve **M1/M2/M5** from the aggs; compute **M3 from the base table** via a per-user self-join
  (or `sequenceMatch`/`windowFunnel`-style logic) — mark `served_by_mv: null` for M3.
- Document that the funnel agg's per-stage users are an **input** to lift, not the lift itself.
- Product confirmation on the exact baseline population ("saw field & never applied" vs "all
  no-coupon checkouts").

# Affects

- [coupon-conversion-lift](/metrics/coupon-conversion-lift.md) (M3)
- [coupon_funnel_daily](/tables/coupon_funnel_daily.md)
- [promo_coupon_checkout](/tables/promo_coupon_checkout.md)

# Source

`specs/unseen_data/spec.md` (PM conversion-lift question), `Atlys/schemas/unseen_data.metrics.json` (M3), live `atlys` schema (`coupon_funnel_daily_mv` states, base ORDER BY without `user_id`).
