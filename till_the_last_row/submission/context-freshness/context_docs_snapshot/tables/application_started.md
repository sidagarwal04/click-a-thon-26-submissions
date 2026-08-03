---
type: table
title: application_started
description: Funnel event — user starts a visa application (committed intent). New JSON-payload design, live in atlys as SharedMergeTree. Feeds mv_application_started_daily → application_started_daily rollup.
kind: funnel
source_spec: specs/10_application_started/spec.md
source_schema: Atlys/schemas/10_application_started.sql
source_metrics: Atlys/schemas/10_application_started.metrics.json
live: true
timestamp: 2026-08-05
tags: [table, funnel, live, json-payload]
---

# Purpose

Emitted when a user begins filling out a visa application form — the committed-intent event
(authenticated, destination chosen, application begun). Records visa `purpose`, the processing-time
estimate shown (`eta_shown`), and the flow variant (`flow`). Bridges top-of-funnel engagement with
document collection and payment.

# Engine & keys

- Engine: `SharedMergeTree` (Cloud). Single JSON column `payload` (plain MergeTree design).
- `ORDER BY (payload.event, payload.destination, payload.purpose, payload.user_id, payload.timestamp)`
  — event-first key matching the hot filter/segment paths, **not** the legacy `(id, timestamp, user_id)`.
- `PARTITION BY toYYYYMMDD(ch_insert_time)`.
- `TTL toDateTime(ch_insert_time) + toIntervalDay(90)` with `ttl_only_drop_parts = 1`.

# Schema

Fields live under `payload.*` and are queried via typed paths (e.g. `` payload.`eta_shown` ``).

| column / path | type | notes |
|---|---|---|
| payload | JSON(...) | single JSON column; typed hint below |
| payload.event | LowCardinality(String) | ORDER BY head; `= 'application_started'` |
| payload.destination | LowCardinality(String) | ORDER BY; typed + skip-indexed (D1) |
| payload.purpose | LowCardinality(String) | ORDER BY; typed |
| payload.user_id | String | ORDER BY; durable join key |
| payload.timestamp | DateTime64(3,'UTC') | ORDER BY tail |
| payload.flow | LowCardinality(String) | typed + skip-indexed (D1) |
| payload.eta_shown | LowCardinality(String) | string band (`instant`,`3-5 days`,`7-10 days`); typed + skip-indexed (D1) |
| payload.citizenship | LowCardinality(String) | typed + skip-indexed (D1) |
| payload.device_type | LowCardinality(String) | typed + skip-indexed (D1) |
| payload.os | LowCardinality(String) | typed + skip-indexed (D1) |
| payload.is_back_filled | Bool | typed + skip-indexed (D1) |
| ch_insert_time | DateTime64(3,'UTC') MATERIALIZED | partition + TTL anchor |

Other envelope/event fields (e.g. `co_travelers`, `app_session_id`, `duplicate_id`, geo fields)
remain in the JSON payload **untyped** — read them from `payload.*` directly at the base table.

# Deviation D1 — skip-index-typed hot-filter paths

⚠️ **D1**: the JSON typed hint promotes certain fields to typed subcolumns **only because they carry
skip indexes** on the hot-filter/segment paths — it is a performance hint, not an exhaustive schema.
Confirmed live `set` skip indexes (granularity 4): `payload.flow` (`idx_flow`),
`payload.eta_shown` (`idx_eta_shown`), `payload.citizenship` (`idx_citizenship`),
`payload.device_type` (`idx_device_type`), `payload.os` (`idx_os`),
`payload.is_back_filled` (`idx_back_filled`). Fields without a skip index (e.g. `co_travelers`) are
still queryable via `payload.*` but without index acceleration.

# Ordering note

The event-first ORDER BY here is the corrected new design; it does **not** reproduce the legacy
`(id, timestamp, user_id)` smell — see [legacy-id-order-key](/contradictions/legacy-id-order-key.md)
(this table is resolving evidence, not an instance of the smell).

# Measures

- Served by rollup: [application-started-count](/metrics/application-started-count.md),
  [back-filled-rate](/metrics/back-filled-rate.md).
- Denominator only (cross-event): [start-to-purchase-conversion](/metrics/start-to-purchase-conversion.md),
  [eta-shown-conversion-lift](/metrics/eta-shown-conversion-lift.md),
  [co-travelers-dropoff](/metrics/co-travelers-dropoff.md).

# Related

- Tables: [application_started_daily](/tables/application_started_daily.md) (rollup).
- Materialized view: `atlys.mv_application_started_daily`.
- Entities: [application](/entities/application.md)
- Contradictions: [eta-column-naming](/contradictions/eta-column-naming.md) (`eta_shown` string band vs
  entity's `visa_issuance_eta_days`), [android-os-null](/contradictions/android-os-null.md).
- Source: `Atlys/schemas/10_application_started.sql`; live `atlys` schema.
