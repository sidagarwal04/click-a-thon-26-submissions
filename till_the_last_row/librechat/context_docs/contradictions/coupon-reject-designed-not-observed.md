---
type: contradiction
title: coupon_rejected is designed-for but unseen in the sample
description: The schema types and indexes reject_reason and the spec enumerates four reasons, but the 5,364-event sample contains no coupon_rejected rows — the reject-mix metric (M2) is schema-ready yet returns empty.
severity: low
status: open
timestamp: 2026-08-07
tags: [contradiction, coupon, data-quality, gap]
---

# Claim

The `unseen_data` spec lists **`coupon_rejected`** as one of the six raw event types with a
`reject_reason` of `expired` / `invalid_code` / `min_cart_not_met` / `already_used`, and the live
schema **types + indexes** it: `payload.reject_reason LowCardinality(String)` with a `set(8)`
skip-index, and it is a grain dimension on [coupon_funnel_daily](/tables/coupon_funnel_daily.md).
So [coupon-reject-mix](/metrics/coupon-reject-mix.md) (M2) is presented as computable.

# Conflicting claim / evidence

The 5,364-event `events.ndjson` sample for this spec contains **no `coupon_rejected` rows** (the
observed events are field-shown / entered / applied / discount-shown / checkout). Additionally the
base table is **not yet ingested** (`total_rows = 1`, no real event rows; both aggs `total_rows =
0`). So M2's reject breakdown will return **empty** against current data despite the schema being
correct.

# Why it matters

An analyst running "top reject reasons" today gets an empty result and may wrongly conclude the
instrumentation is broken, or that rejects never happen. It is neither — the event is **designed-for
but not yet observed** in the provided sample.

# Recommended resolution

- Treat M2 as **schema-ready, data-pending**: return the empty result with an explicit "no
  `coupon_rejected` events in range" note rather than an error.
- Re-check once real ingest populates the base table; the `reject_reason` typing + `set(8)` index
  are already correct.
- No schema change required.

# Affects

- [coupon-reject-mix](/metrics/coupon-reject-mix.md) (M2)
- [coupon_funnel_daily](/tables/coupon_funnel_daily.md)
- [promo_coupon_checkout](/tables/promo_coupon_checkout.md)

# Source

`specs/unseen_data/spec.md` (event list + reject_reason domain), `specs/unseen_data/events.ndjson` (no coupon_rejected rows), live `atlys` schema (typed/indexed reject_reason; `total_rows` 1/0/0).
