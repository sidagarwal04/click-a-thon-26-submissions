---
type: table
title: document_uploaded
description: Funnel event — a document is successfully uploaded during the application form. Document friction is a major drop-off point between application_started and pay_now_clicked. Now live in ClickHouse.
kind: funnel
source_spec: specs/11_document_uploaded/spec.md
source_schema: Atlys/schemas/11_document_uploaded.sql
source_metrics: Atlys/schemas/11_document_uploaded.metrics.json
live: true
timestamp: 2026-08-06
tags: [table, funnel, document, live]
---

# Purpose

Emitted each time a user **successfully uploads a document** during the application form. It
captures the **document type** (`doc_type`), **how** it was captured (`capture_mode`), whether
auto-scan was used (`scan_mode`), and **retry / failure** information (`retry_count`,
`failed_attempt_threshold`, `is_crossed_failed_attempt_threshold`). Document friction is a **major
drop-off point** between `application_started` and `pay_now_clicked` (see
[start-to-document-upload](/relationships/start-to-document-upload.md)).

# Live status

✅ Live in ClickHouse `atlys` as of the `11_document_uploaded` schema push. Design = **one event
type → one base table, single JSON `payload` column**. Three objects back it:

- `atlys.document_uploaded` — base table (`SharedMergeTree`), all envelope + spec fields in `payload` (**20,446 rows** ingested).
- `atlys.document_uploaded_daily_agg` — pre-aggregated daily rollup (`SharedAggregatingMergeTree`) — see [document_uploaded_daily](/tables/document_uploaded_daily.md).
- `atlys.document_uploaded_daily_mv` — incremental MATERIALIZED VIEW feeding the agg table.

> Live engines report as `SharedMergeTree` / `SharedAggregatingMergeTree` — ClickHouse Cloud's
> transparent substitution for `MergeTree` / `AggregatingMergeTree`; expected, not a deviation.
> The agg table reports `total_rows = 0` (rollup not yet populated / merged; base is ingested).

# Payload fields (typed in the JSON hint)

Fields queried via `payload.<name>`. These are **typed** in the `JSON(...)` hint — either because
they are in the ORDER BY, or because they are hot-filter paths carrying a skip-index (see D1). Note
`retry_count`, `is_crossed_failed_attempt_threshold`, `failed_attempt_threshold`, `is_*` flags are
typed **`UInt8`**, so their `minmax` skip-indexes attach **directly** to the typed sub-column (no
`CAST` wrapper needed — a cleaner form than `auth_completed`'s D1 pattern).

| path | type | notes |
|---|---|---|
| event | LowCardinality(String) | Always `document_uploaded`; ORDER BY col 1 |
| doc_type | LowCardinality(String) | `passport_front` / `passport_back` / `photo` / `supporting_doc`; ORDER BY col 2 |
| capture_mode | LowCardinality(String) | `gallery` / `camera` / `qr`; ORDER BY col 3 |
| scan_mode | LowCardinality(String) | OCR/parse mode `auto` / `manual`; ORDER BY col 4 |
| timestamp | DateTime64(3,'UTC') | Event time; ORDER BY col 5 (last) |
| user_id | String | Joins all tables; ⚠️ typed but **NOT in ORDER BY** |
| retry_count | UInt8 | Failed upload attempts before this success; `minmax` idx_retry_count |
| failed_attempt_threshold | UInt8 | Max retries before fallback offered (typically 3); typed, not indexed |
| is_crossed_failed_attempt_threshold | UInt8 | 1 = user hit threshold & was offered a fallback; `minmax` idx_threshold_x |
| destination | LowCardinality(String) | ISO-2 destination; `set(256)` idx_destination |
| device_type | LowCardinality(String) | `ios` / `android` / `Desktop`; `set(32)` idx_device_type |
| citizenship | LowCardinality(String) | `set(64)` idx_citizenship |
| geoip_country_code | LowCardinality(String) | `bloom_filter(0.01)` idx_geoip_cc |
| funnel_type | LowCardinality(String) | `b2c` etc; `set(16)` idx_funnel_type |
| is_guest | UInt8 | `minmax` idx_is_guest |
| is_referral | UInt8 | `minmax` idx_is_referral |
| is_enterprise | UInt8 | `minmax` idx_is_enterprise |
| is_back_filled | UInt8 | Backfill marker; typed, not indexed |

> ⚠️ **`os` is NOT typed** in this table's JSON hint and carries **no skip-index** — unlike
> `auth_completed`. It still exists in the raw `payload` (read via `CAST(payload.os,'String')`),
> but it is a rollup dimension **only** in the agg table, not a hot-filter path on the base.
> See [android-os-null](/contradictions/android-os-null.md).
> ⚠️ **`application_id` is NOT typed** and NOT indexed (present in raw JSON only) — funnel joins
> use `user_id`.

> Standard envelope paths not listed above (e.g. `app_session_id`, `co_travelers`, `gclid`,
> `fbclid`, `gad_source`, `city`, `latitude`, `longitude`, `locale`, `language`, `duplicate_id`,
> `app_version`, `client_lib`, `os`, `application_id`) still exist in the raw JSON but are
> **untyped and unindexed**; read them via `CAST(payload.<name>, '<T>')`.

# Ordering / partitioning / TTL (base table)

- **ORDER BY** `(payload.event, payload.doc_type, payload.capture_mode, payload.scan_mode, payload.timestamp)` — discriminator → LowCard analysis dims → timestamp last.
- ✅ Does **not** use the legacy `ORDER BY (id, timestamp, user_id)` smell — see [legacy-id-order-key](/contradictions/legacy-id-order-key.md). The prior seed stub's legacy-key warning was **stale** and has been removed.
- ⚠️ Unlike `auth_completed`/`application_started`, **`user_id` is not in the sort key** — this key is optimised for `doc_type × capture_mode × scan_mode` friction slices, not for user-keyed lookups. User-level funnel joins scan on the `user_id` typed sub-column (no key prefix benefit).
- **PARTITION BY** `toYYYYMMDD(ch_insert_time)`; `ch_insert_time` = `DateTime64(3,'UTC') MATERIALIZED now64(3)` ingest-time column.
- **TTL** `toDateTime(ch_insert_time) + 90 day`, `ttl_only_drop_parts = 1`.

# Skip-index inventory (base table)

| index | expr | type | notes |
|---|---|---|---|
| idx_destination | payload.destination | set(256) | destination slices |
| idx_device_type | payload.device_type | set(32) | platform slices |
| idx_citizenship | payload.citizenship | set(64) | |
| idx_funnel_type | payload.funnel_type | set(16) | |
| idx_geoip_cc | payload.geoip_country_code | bloom_filter(0.01) | high-card geo → bloom, not set |
| idx_retry_count | payload.retry_count | minmax | typed UInt8, direct attach |
| idx_threshold_x | payload.is_crossed_failed_attempt_threshold | minmax | typed UInt8, direct attach |
| idx_is_guest | payload.is_guest | minmax | typed UInt8 |
| idx_is_referral | payload.is_referral | minmax | typed UInt8 |
| idx_is_enterprise | payload.is_enterprise | minmax | typed UInt8 |

> All indexes GRANULARITY 1. `capture_mode` / `scan_mode` are **not** separately indexed — they
> are already in the ORDER BY prefix.

# Metrics (from 11_document_uploaded.metrics.json)

| id | metric | served by MV? |
|---|---|---|
| M1 | [retry-count-distribution](/metrics/retry-count-distribution.md) | ✅ agg |
| M2 | [failed-attempt-threshold-rate](/metrics/failed-attempt-threshold-rate.md) | ✅ agg |
| M3 | [scan-mode-retry-comparison](/metrics/scan-mode-retry-comparison.md) | ✅ agg |
| M4 | [platform-upload-failure-rate](/metrics/platform-upload-failure-rate.md) | ✅ agg |
| M5 | [doc-volume-vs-payment-conversion](/metrics/doc-volume-vs-payment-conversion.md) | ❌ null — cross-table payment join |

> All 5 manifest metrics carry `confirmed_by_user: false` — the formulas below are grounded on the
> spec's PM questions + the live agg grain, not on a user confirmation.

# PM questions (from spec)

1. `retry_count` distribution by `doc_type` × `capture_mode` — which combination causes most friction? *(M1, MV-served)*
2. Share of uploads with `is_crossed_failed_attempt_threshold = 1`; does it predict abandonment? *(M2, MV-served; abandonment piece = cross-event)*
3. Does `scan_mode = auto` succeed (lower retries) vs `manual` for passports? *(M3, MV-served)*
4. Is there a platform (iOS vs Android) where upload fails more? *(M4, MV-served)*
5. Which destinations need the most doc types, and does doc volume correlate with lower payment conversion? *(M5, cross-table — no MV)*

# Deviations

- **D1 (resolved-clean)** — hot-filter paths are typed in the JSON hint so their skip-indexes are
  valid. Because the numeric/bool paths (`retry_count`, `is_crossed_failed_attempt_threshold`,
  `is_*`) are typed **`UInt8`**, their `minmax` indexes attach **directly** to the typed sub-column
  — no `CAST(...)` index expression is needed (contrast `auth_completed`, whose untyped `attempts`
  needed `minmax` on `CAST(payload.attempts AS UInt32)`). High-cardinality `geoip_country_code`
  uses `bloom_filter(0.01)` rather than `set`.
- **D2** — agg TTL keyed on `agg_insert_time` (ingest time), **NOT** the event `event_day` — same
  compute-time-watermark rationale as prior specs; keying on the historical event date would drop
  rollups on merge.
- **D3 (gap)** — `os` is a rollup **dimension** in `document_uploaded_daily_agg` but is **neither
  typed nor indexed** on the base `document_uploaded`. Base-table OS filtering scans the untyped
  `payload.os` sub-column; the agg-level `os` bucket also inherits the android-os-null gap. See
  [android-os-null](/contradictions/android-os-null.md).

# Related

- Entities: [user](/entities/user.md), [event](/entities/event.md), [document](/entities/document.md)
- Tables: [document_uploaded_daily](/tables/document_uploaded_daily.md)
- Metrics: [retry-count-distribution](/metrics/retry-count-distribution.md), [failed-attempt-threshold-rate](/metrics/failed-attempt-threshold-rate.md), [scan-mode-retry-comparison](/metrics/scan-mode-retry-comparison.md), [platform-upload-failure-rate](/metrics/platform-upload-failure-rate.md), [doc-volume-vs-payment-conversion](/metrics/doc-volume-vs-payment-conversion.md), [passport-capture-pass-rate](/metrics/passport-capture-pass-rate.md)
- Relationships: [start-to-document-upload](/relationships/start-to-document-upload.md), [document-upload-to-pay-now](/relationships/document-upload-to-pay-now.md)
- Contradictions: [android-os-null](/contradictions/android-os-null.md), [legacy-id-order-key](/contradictions/legacy-id-order-key.md)
- Known issues: [K2](/known-issues/k2-passport-scan-model-update.md), [K3](/known-issues/k3-mrz-ocr-non-latin.md)
- Source: `specs/11_document_uploaded/spec.md`, `Atlys/schemas/11_document_uploaded.sql`, `Atlys/schemas/11_document_uploaded.metrics.json`, live `atlys` schema
