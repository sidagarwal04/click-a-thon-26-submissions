---
type: table
title: auth_completed
description: Supporting event — user successfully authenticates (sign-up or login). Sits between destination card selection and application start; a drop here means the auth wall is blocking conversion. Now live in ClickHouse.
kind: supporting
source_spec: specs/09_auth_completed/spec.md
source_schema: Atlys/schemas/09_auth_completed.sql
source_metrics: Atlys/schemas/09_auth_completed.metrics.json
live: true
timestamp: 2026-08-04
tags: [table, supporting, auth, live]
---

# Purpose

Emitted immediately after a user successfully authenticates (sign-up or login). It is a
**supporting event** on the pre-funnel path: it sits between `destination_card_clicked` and
`application_started`, so a drop here means the **authentication wall** is blocking conversion.
It captures the auth **method**, whether this is a **new user**, and how many **attempts** it
took. It joins to the funnel on `user_id` (see
[auth-to-application](/relationships/auth-to-application.md)).

# Live status

✅ Live in ClickHouse `atlys` as of the `09_auth_completed` schema push. Design = **one event
type → one base table, single JSON `payload` column**. Three objects back it:

- `atlys.auth_completed` — base table (`SharedMergeTree`), all envelope + spec fields in `payload`.
- `atlys.auth_completed_metrics_agg` — pre-aggregated rollup (`SharedAggregatingMergeTree`).
- `atlys.auth_completed_metrics_mv` — incremental MATERIALIZED VIEW feeding the agg table.

> Live engines report as `SharedMergeTree` / `SharedAggregatingMergeTree` — ClickHouse Cloud's
> transparent substitution for `MergeTree` / `AggregatingMergeTree`; expected, not a deviation.
> Base and agg tables currently report `total_rows = 0` (schema landed; backfill/ingest pending).

# Payload fields (typed in the JSON hint)

Fields queried via `payload.<name>`. Only these are **typed** in the `JSON(...)` hint (they are
in the ORDER BY, or are string/bool hot-filter paths that carry a skip-index — see D1):

| path | type | notes |
|---|---|---|
| event | LowCardinality(String) | Always `auth_completed`; ORDER BY col 1 |
| application_id | LowCardinality(String) | ORDER BY col 2; may be empty (auth can precede an application) |
| auth_method | LowCardinality(String) | `otp` / `google` / `apple` / `email`; ORDER BY col 3; `set(0)` — see below |
| user_id | String | Joins all tables; ORDER BY col 4 |
| timestamp | DateTime64(3,'UTC') | Event time; ORDER BY col 5 (last) |
| device_type | LowCardinality(String) | `ios` / `android` / `Desktop`; skip-index `set(0)` |
| os | LowCardinality(String) | ⚠️ typed **non-Nullable** here, but arrives `null` on some Android rows — see [android-os-null](/contradictions/android-os-null.md); skip-index `set(0)` |
| geoip_country_code | LowCardinality(String) | ISO-2 geo; skip-index `set(0)` |
| is_new_user | Bool | 1 = user's first-ever successful auth; skip-index `set(2)` |

# Payload fields (untyped — numeric metric path, D1)

Left **untyped** in the `JSON(...)` hint and read via `CAST(payload.<name>, '<T>')`. Skip-indexed
with `minmax` over the CAST expression (a skip-index cannot attach to a dynamic JSON path
directly → ClickHouse Code:36/47):

| path | logical type | index | notes |
|---|---|---|---|
| attempts | UInt32 | `minmax` on `CAST(payload.attempts AS UInt32)` | auth attempts before success; `attempts > 1` = friction |

> Standard envelope paths not listed above (e.g. `gclid`, `fbclid`, `city`, `citizenship`,
> `destination`, `is_back_filled`, `duplicate_id`, `app_session_id`) still exist in the raw JSON
> but are **untyped and unindexed**. `gclid` / `fbclid` are read at MV time to derive
> `acquisition_channel` (see below).

# Ordering / partitioning / TTL (base table)

- **ORDER BY** `(payload.event, payload.application_id, payload.auth_method, payload.user_id, payload.timestamp)` — 5 cols: discriminator → LowCard dims → user_id → timestamp last.
- ✅ Does **not** use the legacy `ORDER BY (id, timestamp, user_id)` smell — see [legacy-id-order-key](/contradictions/legacy-id-order-key.md).
- **PARTITION BY** `toYYYYMMDD(ch_insert_time)`; `ch_insert_time` = `DateTime64(3,'UTC')` ingest-time column.
- **TTL** 90 days, `ttl_only_drop_parts = 1`.
- **os excluded from ORDER BY** (D1): it is null on some rows, so it is typed + `set`-indexed for skip-filtering rather than placed in the sort key.

# Aggregating rollup: auth_completed_metrics_agg

`SharedAggregatingMergeTree`. **Grain** (ORDER BY): `day × auth_method × device_type × os ×
geoip_country_code × acquisition_channel × is_new_user`. PARTITION BY `toYYYYMM(day)`.
Aggregate states:

| column | state | measures |
|---|---|---|
| completions | `AggregateFunction(count)` | auth completion count (M1 base) |
| new_user_completions | `AggregateFunction(sum, UInt64)` | new-user completions (M3) |
| retried_completions | `AggregateFunction(sum, UInt64)` | completions with `attempts > 1` (M2) |
| total_attempts | `AggregateFunction(sum, UInt64)` | sum of `attempts` (M5 — avg attempts) |

- Read with `...Merge(...)` finalizers, e.g. `countMerge(completions)`, `sumMerge(retried_completions)`.
- **`acquisition_channel`** is a **user-confirmed derived dimension** (`confirmed_by_user: true`):
  `gclid != '' → paid_google`, else `fbclid != '' → paid_meta`, else `organic`. Derived in the MV.
- **D2**: agg TTL is keyed on `agg_insert_time` (ingest time), **NOT** the event `day` — the
  server clock (~2026-08) runs far ahead of the event span (2026-02 → 2026-06), so keying TTL on
  the historical event date would silently drop rollups on merge.
- Serves **M1, M2, M3, M5**. **M4 (auth_completion_rate) is cross-event** (needs `auth_started`,
  not in this spec) → `served_by_mv: null` — see
  [auth-completion-rate-cross-event-gap](/contradictions/auth-completion-rate-cross-event-gap.md).

# Metrics (from 09_auth_completed.metrics.json)

| id | metric | served by MV? |
|---|---|---|
| M1 | [auth-method-mix](/metrics/auth-method-mix.md) | ✅ agg |
| M2 | [auth-retry-rate](/metrics/auth-retry-rate.md) | ✅ agg |
| M3 | [new-user-rate](/metrics/new-user-rate.md) (by acquisition_channel) | ✅ agg |
| M4 | [auth-completion-rate](/metrics/auth-completion-rate.md) | ❌ null — cross-event |
| M5 | [avg-auth-attempts](/metrics/avg-auth-attempts.md) | ✅ agg |

# PM questions (from spec)

1. Auth **method mix** (`otp`/`google`/`apple`/`email`) by `device_type`/`os`? *(M1, MV-served)*
2. Share of events with `attempts > 1` (friction) and which method retries most? *(M2, MV-served)*
3. **New-user rate** by acquisition source (`gclid`/`fbclid`)? *(M3 via `acquisition_channel`, MV-served)*
4. Auth → `application_started` conversion by `is_new_user`? *(cross-spec join, no MV)*
5. Geo markets where a method dominates + its retry rate? *(M1×M2, MV-served)*

# Deviations

- **D1** — hot-filter/bool paths (`device_type`, `os`, `geoip_country_code`, `is_new_user`) typed
  only for skip-indexing (`set`); `os` is **excluded from ORDER BY** (null on some rows). Numeric
  `attempts` stays **untyped** in payload, indexed via `minmax` on `CAST(payload.attempts AS UInt32)`.
- **D2** — agg TTL keyed on `agg_insert_time` (ingest time), not the event `day`.

# Related

- Entities: [user](/entities/user.md), [event](/entities/event.md), [application](/entities/application.md)
- Metrics: [auth-method-mix](/metrics/auth-method-mix.md), [auth-retry-rate](/metrics/auth-retry-rate.md), [new-user-rate](/metrics/new-user-rate.md), [auth-completion-rate](/metrics/auth-completion-rate.md), [avg-auth-attempts](/metrics/avg-auth-attempts.md)
- Relationships: [supporting-on-user](/relationships/supporting-on-user.md), [auth-to-application](/relationships/auth-to-application.md)
- Contradictions: [android-os-null](/contradictions/android-os-null.md), [legacy-id-order-key](/contradictions/legacy-id-order-key.md), [auth-completion-rate-cross-event-gap](/contradictions/auth-completion-rate-cross-event-gap.md)
- Source: `specs/09_auth_completed/spec.md`, `Atlys/schemas/09_auth_completed.sql`, `Atlys/schemas/09_auth_completed.metrics.json`, live `atlys` schema
