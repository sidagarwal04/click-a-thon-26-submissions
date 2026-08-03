---
type: contradiction
title: os = NULL while device_type = 'android'
description: Envelope data gap — Android rows with missing OS field break OS-based segmentation.
severity: medium
status: open
timestamp: 2026-08-02
tags: [contradiction, data-quality, envelope]
---

# Claim

The standard envelope includes `os` as a segmentation dimension. Analysts expect every row to have a valid `os` value matching the `device_type`.

# Evidence

Approximately 346 rows observed where `device_type = 'android'` but `os` is NULL. This affects all event tables that share the standard envelope, including `destination_card_clicked` and the now-live `landing_page_scrolled` (where `os` is typed `Nullable(String)`, excluded from the ORDER BY, and carries only a `set` skip-index).

The now-live `auth_completed` (spec 09) sharpens the conflict: its JSON hint types `os` as
**`LowCardinality(String)` — non-Nullable** (excluded from ORDER BY, `set(0)` skip-index), yet the
`events.ndjson` sample still shows `os: null` on Android rows. A non-Nullable typed hint coerces a
null JSON value to the empty string `''` rather than SQL NULL, so on `auth_completed` the gap
surfaces as `os = ''` (empty) rather than `os IS NULL`. Segmentation/COALESCE logic must handle
**both** the empty-string and NULL forms depending on the table's hint.

# Why it matters

Any query segmenting by OS (e.g. "conversion rate by OS") will silently exclude or miscount these Android users. If a WHERE clause filters `os = 'Android'`, affected rows vanish.

# Recommended resolution

- For analysis: treat `os IS NULL AND device_type = 'android'` as `os = 'Android'` (COALESCE).
- For instrumentation: fix the client to always populate `os`.
- The Analytics Agent should note the workaround when segmenting by OS.

# Source

Tech requirements / data observation (346 rows). Confirmed that `destination_card_clicked` envelope includes both `os` and `device_type`.

# Affects

- [destination_card_clicked](/tables/destination_card_clicked.md)
- [landing_page_scrolled](/tables/landing_page_scrolled.md) — segment by `device_type` (safe) rather than `os`; the engagement agg rolls up on `device_type`
- [auth_completed](/tables/auth_completed.md) — `os` typed **non-Nullable** `LowCardinality(String)`; nulls coerce to `''`. The metrics agg rolls up on `os`, so an `os = ''` bucket will appear; prefer `device_type` slices or COALESCE `''`/NULL → `'Android'`
- [document_uploaded](/tables/document_uploaded.md) — **strongest instance**: `os` is **not even typed** in the JSON hint and carries **no skip-index**, yet it is a rollup **dimension** in `document_uploaded_daily_agg`. The MV coalesces `os` → `''`, so Android-null rows land in the `os = ''` bucket and `GROUP BY os` undercounts Android. Prefer `device_type` (typed + `set(32)` indexed) or COALESCE `''`/NULL → `'Android'`.
- All other event tables sharing the standard envelope
