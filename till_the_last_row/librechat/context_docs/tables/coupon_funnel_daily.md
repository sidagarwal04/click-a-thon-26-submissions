---
type: table
title: coupon_funnel_daily_agg
description: Pre-aggregated daily coupon-funnel rollup — event counts and distinct-user counts by day × event_type × device_type × geoip_country_code × coupon_code × reject_reason. Fed by coupon_funnel_daily_mv.
kind: aggregate
source_spec: specs/unseen_data/spec.md
source_schema: Atlys/schemas/unseen_data.sql
source_metrics: Atlys/schemas/unseen_data.metrics.json
live: true
timestamp: 2026-08-07
tags: [table, aggregate, rollup, coupon, funnel, live]
---

# Purpose

`SharedAggregatingMergeTree` daily funnel rollup of
[promo_coupon_checkout](/tables/promo_coupon_checkout.md). Serves the coupon-funnel metrics
(apply rate M1, reject mix M2, and the per-stage user counts for conversion-lift M3) without
scanning the base table. Fed incrementally by the `atlys.coupon_funnel_daily_mv` MATERIALIZED VIEW.

> ⚠️ Reports `total_rows = 0` at time of writing — schema landed but the base table is not yet
> ingested/merged (see freshness caveat on [promo_coupon_checkout](/tables/promo_coupon_checkout.md)).

# Grain (ORDER BY)

`event_type × device_type × geoip_country_code × coupon_code × reject_reason × event_day`

- `event_day` `Date` = `toDate(payload.timestamp)` (**event time**, not ingest time).
- `event_type` = `CAST(payload.event, 'String')` — retains **all six** event types (the MV has
  **no WHERE filter**), so apply rate M1 divides one stage's count by another's from this one table.
- Dimensions `device_type`, `geoip_country_code`, `coupon_code`, `reject_reason` are each
  `coalesce(CAST(payload.<dim>,'String'), '')` in the MV → NULLs land in the **empty-string**
  bucket, not SQL NULL. So the no-coupon baseline appears as `coupon_code = ''` and non-reject
  events as `reject_reason = ''`.
- PARTITION BY `toYYYYMM(event_day)`.

# Aggregate states

| column | state | measure | finalizer |
|---|---|---|---|
| events_state | `AggregateFunction(count)` | event count | `countMerge(events_state)` |
| users_state | `AggregateFunction(uniq, String)` | distinct users at this stage | `uniqMerge(users_state)` |

- MV source expressions: `countState()`, `uniqState(CAST(payload.user_id,'String'))`,
  grouped by the six grain columns (no row filter).
- **Apply rate** (M1) = `uniqMerge(users_state)` where `event_type='coupon_applied'` ÷ same where
  `event_type='coupon_field_shown'` (or event-count form).
- **Reject mix** (M2) = distribution of `events_state`/`users_state` over `reject_reason` where
  `event_type='coupon_rejected'`.

# Deviations

- **D2** — TTL keyed on `agg_insert_time` (`DateTime64(3,'UTC') MATERIALIZED now64(3)`),
  `toDateTime(agg_insert_time) + 90 day`, `ttl_only_drop_parts = 1`. **Not** keyed on `event_day`:
  the server clock runs ahead of the historical event span, so keying TTL on the event date would
  silently drop rollups on merge.

# Limitations

- ⚠️ This agg gives **per-stage distinct-user counts**, but it **cannot express per-user
  sequencing** (e.g. users who `coupon_applied` *and then* `checkout_with_coupon`). Conversion-lift
  M3's cohort/baseline definition needs a query-time self-join on the base table, not just this
  rollup. See [coupon-conversion-lift-single-table-gap](/contradictions/coupon-conversion-lift-single-table-gap.md).
- ⚠️ `reject_reason` rows are **unseen** in the sample — M2 will be empty until real
  `coupon_rejected` events land. See [coupon-reject-designed-not-observed](/contradictions/coupon-reject-designed-not-observed.md).
- ⚠️ `os` is **not** a dimension here (funnel rolls up on `device_type`) — prefer `device_type`
  for platform slices; see [android-os-null](/contradictions/android-os-null.md).

# Serves

- [coupon-apply-rate](/metrics/coupon-apply-rate.md) (M1)
- [coupon-reject-mix](/metrics/coupon-reject-mix.md) (M2)
- [coupon-conversion-lift](/metrics/coupon-conversion-lift.md) (M3, **partial** — per-stage users only)
- [coupon-segment-performance](/metrics/coupon-segment-performance.md) (M5, funnel-side segment dims)

# Related

- Base table: [promo_coupon_checkout](/tables/promo_coupon_checkout.md)
- Sibling agg: [coupon_discount_daily](/tables/coupon_discount_daily.md)
- Entities: [event](/entities/event.md), [user](/entities/user.md)
- Contradictions: [coupon-conversion-lift-single-table-gap](/contradictions/coupon-conversion-lift-single-table-gap.md), [coupon-reject-designed-not-observed](/contradictions/coupon-reject-designed-not-observed.md), [android-os-null](/contradictions/android-os-null.md)
- Source: `Atlys/schemas/unseen_data.sql`, live `atlys` schema (`coupon_funnel_daily_agg`, `coupon_funnel_daily_mv`)
