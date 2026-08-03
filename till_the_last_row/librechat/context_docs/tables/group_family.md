---
type: table
title: group_family
description: Base event table for the Group / Family Applications flow — one traveller creates a single application for a group, adds/removes co-travellers, and submits them together. Carries four event types in a single JSON payload. Live in ClickHouse with ~5.4K rows.
kind: base
source_spec: specs/02_group_family/spec.md
source_schema: Atlys/schemas/02_group_family.sql
source_metrics: Atlys/schemas/02_group_family.metrics.json
live: true
timestamp: 2026-08-07
tags: [table, group, family, funnel, live]
---

# Purpose

Captures the **group / family application** flow: one traveller creates a single application for a
group (family or friends), adds multiple co-travellers, manages each traveller's documents, and
submits them together. Goal: make multi-traveller leisure trips convert without forcing separate
applications. **Four event types** land in this one base table (single JSON `payload` column):

| event | emitted when | key spec fields |
|---|---|---|
| `group_started` | group flow begins | `group_id`, `group_size`, `destination` |
| `traveller_added` | a co-traveller is added | `traveller_index`, `relation`, `docs_complete` |
| `traveller_removed` | a co-traveller is dropped | `traveller_index` |
| `group_submitted` | the group is submitted | `travellers_submitted` |

Live event mix (5,453 rows): `traveller_added` 3,495 · `group_started` 1,200 ·
`group_submitted` 688 · `traveller_removed` 70. Observed `group_size` ∈ [2, 6].

# Live status

✅ Live in ClickHouse `atlys`. Design = **one base table (`SharedMergeTree`) + one daily
aggregate + one incremental MV**:

- `atlys.group_family` — base table, all envelope + spec fields in `payload` (**5,453 rows**).
- `atlys.group_family_daily` — daily rollup (`SharedAggregatingMergeTree`, **754 rows**) — see [group_family_daily](/tables/group_family_daily.md).
- `atlys.group_family_daily_mv` — incremental MATERIALIZED VIEW feeding the rollup.

> Live engines report as `SharedMergeTree` / `SharedAggregatingMergeTree` — ClickHouse Cloud's
> transparent substitution for `MergeTree` / `AggregatingMergeTree`; expected, not a deviation.

# Payload fields (typed in the JSON hint)

The `JSON(...)` hint types these paths; everything else in the raw envelope stays untyped and is
read via `CAST(payload.<name>, '<T>')`.

| path | type | notes |
|---|---|---|
| event | LowCardinality(String) | One of the 4 event types; **ORDER BY col 1** |
| destination | LowCardinality(String) | ISO destination; **ORDER BY col 2**; agg dimension |
| group_size | UInt8 | Declared group size (2–6 observed); **ORDER BY col 3**; agg dimension |
| user_id | String | Joins to funnel tables; **ORDER BY col 4** |
| timestamp | DateTime64(3,'UTC') | Event time; **ORDER BY col 5 (last)** |
| application_id | LowCardinality(String) | Group application id |
| docs_complete | Bool | Per-traveller document completion (on `traveller_added`); drives docs-incomplete metric |
| os | LowCardinality(String) | Platform; skip-indexed (see D1) |

> ⚠️ **`group_id` is NOT typed** in the JSON hint — it exists in the raw envelope only and is read
> via `CAST(payload.group_id, 'String')`. It is the **metric unit** (a group = one `group_id`) but
> is deliberately kept out of the ORDER BY key; instead it carries a `bloom_filter` skip-index on
> the CAST expression (see D3). `traveller_index`, `relation`, `travellers_submitted` are untyped
> payload paths too (read via CAST).

# Ordering / partitioning / TTL (base table)

- **ORDER BY** `(payload.event, payload.destination, payload.group_size, payload.user_id, payload.timestamp)` — discriminator → analysis dims → user → timestamp last.
- ✅ Does **not** use the legacy `ORDER BY (id, timestamp, user_id)` smell — see [legacy-id-order-key](/contradictions/legacy-id-order-key.md).
- **PARTITION BY** `toYYYYMMDD(ch_insert_time)`; `ch_insert_time` = `DateTime64(3,'UTC') MATERIALIZED now64(3)` ingest-time column (`CODEC(Delta, ZSTD)`).
- **TTL** `toDateTime(ch_insert_time) + 90 day`, `ttl_only_drop_parts = 1` (base table keyed on insert watermark; contrast the agg — see D2).

# Skip-index inventory (base table)

| index | expr | type | notes |
|---|---|---|---|
| idx_os | payload.os | set(100) | typed JSON path — valid set index (D1) |
| idx_docs | payload.docs_complete | set(2) | typed Bool path — valid set index (D1) |
| idx_group_id | CAST(payload.group_id, 'String') | bloom_filter(0.01) | metric-unit filter; **CAST** because group_id is untyped (D3) |

> All GRANULARITY 4. `idx_os` and `idx_docs` are `set` indexes on **typed** JSON sub-columns — a
> plain untyped `set`/`bloom_filter` on a JSON path would error (Code 36). See D1.

# Metrics (from 02_group_family.metrics.json)

| id | metric | served by MV? |
|---|---|---|
| — | [group-completion-rate](/metrics/group-completion-rate.md) | ✅ agg |
| — | [traveller-churn](/metrics/traveller-churn.md) | ✅ agg |
| — | [docs-incomplete-share](/metrics/docs-incomplete-share.md) | ✅ agg |
| — | [group-apps-by-destination](/metrics/group-apps-by-destination.md) | ✅ agg |

# PM questions (from spec)

1. Completion rate (`group_started → group_submitted`) **by group size** — where do large groups fall off? → [group-completion-rate](/metrics/group-completion-rate.md)
2. Travellers added vs removed per group; is there add/remove churn? → [traveller-churn](/metrics/traveller-churn.md)
3. Is per-traveller `docs_complete` the bottleneck for big groups? → [docs-incomplete-share](/metrics/docs-incomplete-share.md)
4. Which destinations / segments drive group applications? → [group-apps-by-destination](/metrics/group-apps-by-destination.md)

# Deviations

- **D1 (resolved-clean)** — skip-indexed hot paths (`os`, `docs_complete`) are **typed** in the
  JSON hint, so their `set` indexes attach to the typed sub-column. An untyped `set`/`bloom_filter`
  on a JSON path errors **Code 36**; typing the path is the fix.
- **D2** — the **aggregate** table TTL is keyed on `event_date` (the derived event date), because
  the agg has **no insert watermark** column. Contrast this base table, whose TTL uses
  `ch_insert_time`. See [group_family_daily](/tables/group_family_daily.md).
- **D3** — `group_id` is the **metric unit** but is deliberately **not** in the ORDER BY key; it is
  indexed via `CAST(payload.group_id,'String')` `bloom_filter(0.01)` for point-lookup filtering.
- **D4** — the MV uses `uniqIfState(...)` (not `uniqState(...)` + WHERE) so the
  `AggregateFunction(uniq, String)` group-count states stay **non-nullable**. See [group_family_daily](/tables/group_family_daily.md).

# Related

- Entities: [user](/entities/user.md), [event](/entities/event.md), [application](/entities/application.md), [destination](/entities/destination.md)
- Tables: [group_family_daily](/tables/group_family_daily.md)
- Metrics: [group-completion-rate](/metrics/group-completion-rate.md), [traveller-churn](/metrics/traveller-churn.md), [docs-incomplete-share](/metrics/docs-incomplete-share.md), [group-apps-by-destination](/metrics/group-apps-by-destination.md)
- Relationships: [group-family-to-funnel](/relationships/group-family-to-funnel.md), [group-started-to-submitted](/relationships/group-started-to-submitted.md)
- Contradictions: [android-os-null](/contradictions/android-os-null.md), [legacy-id-order-key](/contradictions/legacy-id-order-key.md), [group-id-untyped-metric-unit](/contradictions/group-id-untyped-metric-unit.md)
- Source: `specs/02_group_family/spec.md`, `Atlys/schemas/02_group_family.sql`, `Atlys/schemas/02_group_family.metrics.json`, live `atlys` schema
