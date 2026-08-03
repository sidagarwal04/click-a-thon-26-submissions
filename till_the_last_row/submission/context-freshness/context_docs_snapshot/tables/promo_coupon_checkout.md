---
type: table
title: promo_coupon_checkout
description: Base table for the Promo / Coupon at Checkout event family (unseen 6th spec). One JSON `payload` column, one row per raw coupon event across six event types. Now live in ClickHouse.
kind: funnel
source_spec: specs/unseen_data/spec.md
source_schema: Atlys/schemas/unseen_data.sql
source_metrics: Atlys/schemas/unseen_data.metrics.json
live: true
timestamp: 2026-08-07
tags: [table, funnel, coupon, promo, checkout, live]
---

# Purpose

Base table for the **Promo / Coupon at Checkout** feature (the sealed 6th / `unseen_data` spec).
It captures the coupon micro-funnel on the checkout screen: the coupon field renders, the user
enters a code, the code is validated (**valid → discount applied** / **rejected with a reason**),
the discounted price is shown, and the user proceeds to checkout at the discounted (or baseline)
price. Product goal: **lift conversion with promos while controlling margin**.

# Live status

✅ Live in ClickHouse `atlys` as of the `unseen_data` schema push. Design = **one event family →
one base table, single JSON `payload` column** (same pattern as the other live specs). Three
objects back it:

- `atlys.promo_coupon_checkout` — base table (`SharedMergeTree`), all envelope + spec fields in `payload`.
- `atlys.coupon_funnel_daily_agg` — funnel rollup (`SharedAggregatingMergeTree`) — see [coupon_funnel_daily](/tables/coupon_funnel_daily.md).
- `atlys.coupon_discount_daily_agg` — discount/margin rollup (`SharedAggregatingMergeTree`) — see [coupon_discount_daily](/tables/coupon_discount_daily.md).
- Two MVs (`coupon_funnel_daily_mv`, `coupon_discount_daily_mv`) feed the aggs incrementally.

> Live engines report as `SharedMergeTree` / `SharedAggregatingMergeTree` — ClickHouse Cloud's
> transparent substitution for `MergeTree` / `AggregatingMergeTree`; expected, not a deviation.
> ⚠️ **Freshness caveat:** at time of writing the base table reports `total_rows = 1` and a
> `SELECT` returns no real event rows; both agg tables report `total_rows = 0`. The schema has
> landed but the 5,364-event sample is **not yet ingested / merged**. Treat coupon metrics as
> **schema-ready but not yet populated** until row counts move.

# Event types (discriminator = `payload.event`)

Six raw event types share this table (`payload.event`, `LowCardinality(String)`, ORDER BY col 1):

| event | key fields | notes |
|---|---|---|
| coupon_field_shown | cart_value, currency | coupon field renders — funnel entry |
| coupon_entered | coupon_code | user submits a code |
| coupon_applied | discount_type (percent/flat), discount_amount | code valid, discount computed |
| coupon_rejected | reject_reason | code invalid — see reasons below |
| discount_shown | — | discounted price displayed |
| checkout_with_coupon | coupon_code (**may be null** = no-coupon baseline), discount_amount, final_value | checkout proceeds |

- `reject_reason` domain (spec): `expired` / `invalid_code` / `min_cart_not_met` / `already_used`.
- ⚠️ **`coupon_rejected` and reject-reason rows are designed-for but UNSEEN** in the 5,364-event
  sample — the reject-mix metric (M2) is schema-supported but may return empty until real
  rejects land. See [coupon-reject-designed-not-observed](/contradictions/coupon-reject-designed-not-observed.md).
- ⚠️ `checkout_with_coupon` with `coupon_code IS NULL` is the **intentional no-coupon baseline**
  cohort — do NOT filter it out; it is the denominator for conversion-lift (M3).

# Payload fields (typed in the JSON hint)

Fields queried via `payload.<name>`. The JSON hint types **nine** paths — the ORDER BY columns
plus hot-filter paths carrying a skip-index. Everything else in the raw event body exists in the
JSON but is **untyped** (read via `CAST(payload.<name>, '<T>')`).

| path | type | notes |
|---|---|---|
| event | LowCardinality(String) | Discriminator; ORDER BY col 1 |
| application_id | LowCardinality(String) | ORDER BY col 2 |
| device_type | LowCardinality(String) | `ios` / `android` / `Desktop`; ORDER BY col 3 |
| geoip_country_code | LowCardinality(String) | ISO-2 geo; ORDER BY col 4 |
| timestamp | DateTime64(3,'UTC') | Event time; ORDER BY col 5 (last) |
| user_id | String | Joins all tables; ⚠️ typed but **NOT in ORDER BY** (dropped as high-cardinality) |
| coupon_code | String | Promo code; **nullable/empty = no-coupon baseline**; `bloom_filter(0.01)` idx_coupon_code |
| reject_reason | LowCardinality(String) | `expired`/`invalid_code`/`min_cart_not_met`/`already_used`; `set(8)` idx_reject_reason |
| os | LowCardinality(String) | `set(100)` idx_os; ⚠️ see android-os-null |

> ⚠️ **Untyped in the JSON hint** (present in raw payload, read via CAST): `discount_amount`,
> `cart_value`, `final_value`, `discount_type`, `currency`, `destination`, plus the standard
> envelope extras (`app_version`, `client_lib`, `city`, `id`, etc.). Of these, **`discount_amount`
> still carries a skip-index** via a `CAST(...)` index expression — see **D1**. `destination`,
> `cart_value`, `final_value`, `discount_type` are read at query time with no index.

# Ordering / partitioning / TTL (base table)

- **ORDER BY** `(payload.event, payload.application_id, payload.device_type, payload.geoip_country_code, payload.timestamp)` — discriminator → application_id → LowCard segment dims → timestamp last.
- ✅ Does **not** use the legacy `ORDER BY (id, timestamp, user_id)` smell — see [legacy-id-order-key](/contradictions/legacy-id-order-key.md). `id` absent; `user_id` deliberately **dropped from the key** as high-cardinality.
- **PARTITION BY** `toYYYYMMDD(ch_insert_time)`; `ch_insert_time` = `DateTime64(3,'UTC') MATERIALIZED now64(3)` ingest-time column.
- **TTL** `toDateTime(ch_insert_time) + 90 day`, `ttl_only_drop_parts = 1`.

# Skip-index inventory (base table)

| index | expr | type | notes |
|---|---|---|---|
| idx_os | payload.os | set(100) | OS slices; see android-os-null |
| idx_coupon_code | payload.coupon_code | bloom_filter(0.01) | high-card code → bloom, not set |
| idx_reject_reason | payload.reject_reason | set(8) | 4 reasons + headroom |
| idx_discount_amount | `CAST(payload.discount_amount, 'Float64')` | minmax | **D1** — untyped numeric path, so the index expression CASTs; no typed sub-column to attach to |

> All indexes GRANULARITY 4. `application_id` / `device_type` / `geoip_country_code` are not
> separately indexed — already in the ORDER BY prefix.

# Metrics (from unseen_data.metrics.json)

| id | metric | served by MV? |
|---|---|---|
| M1 | [coupon-apply-rate](/metrics/coupon-apply-rate.md) | ✅ funnel agg |
| M2 | [coupon-reject-mix](/metrics/coupon-reject-mix.md) | ✅ funnel agg (empty until rejects land) |
| M3 | [coupon-conversion-lift](/metrics/coupon-conversion-lift.md) | ⚠️ partial — per-stage users from funnel agg, but per-user sequencing needs base table |
| M4 | [coupon-margin-cost](/metrics/coupon-margin-cost.md) | ✅ discount agg |
| M5 | [coupon-segment-performance](/metrics/coupon-segment-performance.md) | ✅ both aggs (segment dims) |

# PM questions (from spec)

1. Coupon apply rate (`coupon_field_shown` → `coupon_applied`); valid vs rejected mix; top reject reasons. *(M1, M2)*
2. Conversion lift: do coupon users reach `checkout_with_coupon` at a higher rate than the no-coupon baseline (`coupon_code` null)? *(M3)*
3. Margin cost: total `discount_amount`; which codes drive volume vs erode margin. *(M4)*
4. Segment cuts (device, geo, destination); which codes work where. *(M5)*

# Deviations

- **D1 (CAST index pattern)** — `discount_amount` is **not typed** in the JSON hint, so its
  `minmax` skip-index attaches to a `CAST(payload.discount_amount, 'Float64')` **index expression**
  rather than to a typed sub-column (contrast `document_uploaded`, whose typed `UInt8` paths take
  `minmax` directly). The typed string/LowCard hot paths (`os`, `coupon_code`, `reject_reason`)
  index normally.
- **D2** — both agg tables carry `agg_insert_time DateTime64(3,'UTC') MATERIALIZED now64(3)` and
  TTL keyed on `agg_insert_time` (90 day), **not** on `event_day` — the compute-time-watermark
  pattern used across prior specs; keying TTL on the historical event date would drop rollups on
  merge.

# Related

- Entities: [user](/entities/user.md), [event](/entities/event.md)
- Tables: [coupon_funnel_daily](/tables/coupon_funnel_daily.md), [coupon_discount_daily](/tables/coupon_discount_daily.md)
- Metrics: [coupon-apply-rate](/metrics/coupon-apply-rate.md), [coupon-reject-mix](/metrics/coupon-reject-mix.md), [coupon-conversion-lift](/metrics/coupon-conversion-lift.md), [coupon-margin-cost](/metrics/coupon-margin-cost.md), [coupon-segment-performance](/metrics/coupon-segment-performance.md)
- Contradictions: [android-os-null](/contradictions/android-os-null.md), [legacy-id-order-key](/contradictions/legacy-id-order-key.md), [coupon-conversion-lift-single-table-gap](/contradictions/coupon-conversion-lift-single-table-gap.md), [coupon-reject-designed-not-observed](/contradictions/coupon-reject-designed-not-observed.md)
- Known issues: [K6](/known-issues/k6-summer20-coupon.md)
- Source: `specs/unseen_data/spec.md`, `Atlys/schemas/unseen_data.sql`, `Atlys/schemas/unseen_data.metrics.json`, live `atlys` schema (`system.tables`/`system.columns`/`system.data_skipping_indices` + `create_table_query`)
