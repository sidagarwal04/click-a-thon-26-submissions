---
type: table
title: landing_page_scrolled
description: Supporting engagement event — user scrolls a landing page. Feeds page-version (A/B) and paid-vs-organic engagement analysis. Now live in ClickHouse.
kind: supporting
source_spec: specs/07_landing_page_scrolled/spec.md
source_schema: Atlys/schemas/07_landing_page_scrolled.sql
live: true
timestamp: 2026-08-03
tags: [table, supporting, engagement, ab-test, live]
---

# Purpose

Emitted when a user scrolls a landing page. It is a **supporting engagement event** (not a
funnel step): it measures *content interest* — how far a visitor scrolls (`scroll_depth_pct`)
and how long they stay (`time_on_page_s`) — and it powers the `v3`/`v4` landing-page A/B test.
It precedes the funnel spine and joins to it on `user_id` (see
[landing-scroll-to-application](/relationships/landing-scroll-to-application.md)).

# Live status

✅ Live in ClickHouse `atlys` as of the `07_landing_page_scrolled` schema push (commits
`ec49e14` SQL + `d36e589` metrics). Design = **one base table per spec, single JSON `payload`
column**. Two objects back it:

- `atlys.landing_page_scrolled` — base table (MergeTree family), all envelope + spec fields in `payload`.
- `atlys.landing_scroll_engagement_agg` — pre-aggregated rollup (AggregatingMergeTree family).
- `atlys.landing_scroll_engagement_agg_mv` — incremental MV feeding the agg table.

> Live engines report as `SharedMergeTree` / `SharedAggregatingMergeTree` — this is ClickHouse
> Cloud's transparent substitution for plain `MergeTree` / `AggregatingMergeTree`; it is expected
> and not a deviation.

# Payload fields (typed in the JSON hint)

Fields queried via `payload.<name>`. Only these are **typed** in the `JSON(...)` hint (they are
in the ORDER BY, or are string/bool hot-filter paths that carry a skip-index — see D1):

| path | type | notes |
|---|---|---|
| event | LowCardinality(String) | Always `landing_page_scrolled`; ORDER BY col 1 |
| destination | LowCardinality(String) | ISO-2 destination; ORDER BY col 2 |
| page_version | LowCardinality(String) | A/B variant `v3` / `v4`; ORDER BY col 3 |
| user_id | String | Joins all tables; ORDER BY col 4 |
| timestamp | DateTime64(3,'UTC') | Event time; ORDER BY col 5 |
| device_type | LowCardinality(String) | `ios` / `android` / `Desktop`; skip-index `set` |
| os | Nullable(String) | ⚠️ NULL on some Android rows — see [android-os-null](/contradictions/android-os-null.md). Excluded from key (Nullable); `set` skip-index only |
| geoip_country_code | LowCardinality(String) | ISO-2 geo; `set` skip-index |
| gclid | String | Google click ID; `bloom_filter` skip-index; drives `is_paid` |
| fbclid | String | Facebook click ID; `bloom_filter` skip-index; drives `is_paid` |
| is_guest | UInt8 | 1 = unauthenticated |
| is_referral | UInt8 | 1 = arrived via referral |
| is_enterprise | UInt8 | 1 = enterprise user |
| is_back_filled | UInt8 | 1 = backfilled — see [duplicate-backfill-markers](/contradictions/duplicate-backfill-markers.md) |

# Payload fields (untyped — numeric metric paths, D1)

These are the core engagement measures. They are **left untyped** in the `JSON(...)` hint and
read via `CAST(payload.<name>, '<T>')`. They are skip-indexed with `minmax` over the CAST
expression (a skip-index cannot attach to a dynamic JSON path directly → ClickHouse Code:36/47):

| path | logical type | index | range |
|---|---|---|---|
| scroll_depth_pct | UInt8 | `idx_scroll` minmax on `CAST(payload.scroll_depth_pct,'UInt8')` | 0–100 |
| time_on_page_s | UInt16 | `idx_time` minmax on `CAST(payload.time_on_page_s,'UInt16')` | seconds |

> `application_id` is **excluded** — empty on the majority of rows at this stage. Query paths
> not listed above (e.g. `payload.app_session_id`) still exist in the raw JSON but are untyped
> and unindexed.

# Ordering / partitioning / TTL

- **ORDER BY** `(payload.event, payload.destination, payload.page_version, payload.user_id, payload.timestamp)` — 5 cols, discriminator → LowCard dims → user_id → timestamp last.
- ✅ Does **not** use the legacy `ORDER BY (id, timestamp, user_id)` smell — see [legacy-id-order-key](/contradictions/legacy-id-order-key.md). This table is the reference example of the corrected pattern.
- **PARTITION BY** `toYYYYMMDD(ch_insert_time)`; `ch_insert_time` MATERIALIZED `now64(3)`.
- **TTL** `toDateTime(ch_insert_time) + INTERVAL 90 DAY DELETE`, `ttl_only_drop_parts = 1`.

# Aggregating rollup: landing_scroll_engagement_agg

Grain: `page_version × destination × device_type × is_paid × day`. Aggregate states:

| column | state | measures |
|---|---|---|
| scroll_median | `quantileState(0.5)(UInt8)` | median scroll depth |
| scroll_avg | `avgState(UInt8)` | avg scroll depth |
| time_median | `quantileState(0.5)(UInt16)` | median time on page |
| time_avg | `avgState(UInt16)` | avg time on page |
| events | `countState()` | event count |

- `is_paid` = `gclid != '' OR fbclid != ''` (derived in the MV).
- Read with `...Merge(...)` finalizers, e.g. `quantileMerge(0.5)(scroll_median)`, `avgMerge(scroll_avg)`.
- **D2**: agg TTL is keyed on `agg_insert_time DEFAULT now64(3)`, **not** the event `day` —
  the server clock (~2026-08) runs far ahead of the event span (2026-02 → 2026-06), so keying
  TTL on the historical event date would silently drop rollups on merge.
- Serves 4 of the 5 spec metrics (all except the cross-spec conversion metric).

# PM questions (from spec)

1. Median `scroll_depth_pct` / `time_on_page_s` by `page_version` — does v4 beat v3? *(MV-served)*
2. Is there a scroll-depth **threshold** above which `application_started` conversion jumps? *(cross-spec join, no MV)*
3. Do **paid** users (gclid/fbclid) engage differently from organic? *(engagement half MV-served; conversion half cross-spec)*
4. Which **destinations** have the highest avg scroll depth? *(MV-served)*
5. **Mobile vs desktop** difference in scroll/time? *(MV-served)*

# Deviations

- **D1** — skip-indexed string/bool paths typed in `payload(...)`; numeric metric paths untyped, minmax-indexed via `CAST(...)`.
- **D2** — agg TTL keyed on `agg_insert_time`, not event day.

# Related

- Entities: [user](/entities/user.md), [destination](/entities/destination.md), [event](/entities/event.md)
- Metrics: [landing-scroll-engagement](/metrics/landing-scroll-engagement.md), [scroll-depth-to-application-conversion](/metrics/scroll-depth-to-application-conversion.md)
- Relationships: [supporting-on-user](/relationships/supporting-on-user.md), [landing-scroll-to-application](/relationships/landing-scroll-to-application.md)
- Contradictions: [android-os-null](/contradictions/android-os-null.md), [legacy-id-order-key](/contradictions/legacy-id-order-key.md), [dual-conversion-definition](/contradictions/dual-conversion-definition.md), [duplicate-backfill-markers](/contradictions/duplicate-backfill-markers.md)
- Source: `specs/07_landing_page_scrolled/spec.md`, `Atlys/schemas/07_landing_page_scrolled.sql`, `Atlys/schemas/07_landing_page_scrolled.metrics.json`
