---
name: atlys-data-dictionary
description: Ground-truth schema for the Atlys ClickHouse `atlys` database — real table and column names, data quirks, metric formulas, and the planted contradictions in base_context.md to surface. Apply on every Atlys analytics query so column names and metric definitions are correct.
always-apply: true
---

# Skill: Data Dictionary & Known Contradictions

Ground truth for the `atlys` database. Use these exact names. Verify at runtime with
`DESCRIBE TABLE atlys.<table>` if unsure — schemas can evolve as new features land.

## The 8 existing tables

Funnel (in order): `destination_card_clicked` -> `application_started` ->
`document_uploaded` -> `purchase_completed`.
Supporting: `search_typed`, `landing_page_scrolled`, `auth_completed`, `pay_now_clicked`.

### Common envelope (present on every table)
`id UUID`, `timestamp DateTime`, `user_id String`,
`application_id Nullable(String)` (empty before application_started),
`app_session_id`, `device`, `device_type`, `os`, `app_version`, `client_lib`,
`geoip_country_code`, `geoip_subdivision_1_code`, `city`, `client_ip`,
`latitude`, `longitude`, `locale`, `language`, `funnel_type`, `co_travelers UInt8`,
`is_guest`, `is_referral`, `is_enterprise`, `gclid`, `fbclid`, `gad_source`,
`citizenship`, `destination`, `is_back_filled UInt8`, `duplicate_id`.
(All the above except id/timestamp/user_id are `Nullable`.)

### Event-specific columns
| Table | Extra columns |
|-------|---------------|
| `destination_card_clicked` | `visa_type`, `card_type`, `page_version`, `flow`, `is_guest_browse` |
| `application_started` | `purpose`, `eta_shown` (String), `flow` |
| `document_uploaded` | `doc_type`, `capture_mode`, `scan_mode`, `retry_count`, `failed_attempt_threshold`, `is_crossed_failed_attempt_threshold` |
| `purchase_completed` | `value` (revenue, Float64), `currency`, `coupon_applied`, `coupon_name`, `discount_amount`, `insurance_added`, `insurance_amount`, `plan_selected` |
| `search_typed` | `search_term`, `results_count`, `source` |
| `landing_page_scrolled` | `scroll_depth_pct`, `time_on_page_s`, `page_version` |
| `auth_completed` | `auth_method`, `is_new_user`, `attempts` |
| `pay_now_clicked` | `payment_method`, `amount`, `currency`, `coupon_applied`, `plan_selected` |

## Join map
- `user_id` joins all tables.
- `application_id` joins `application_started` -> `document_uploaded`,
  `pay_now_clicked`, `purchase_completed`.
- Supporting tables may precede an application, so their `application_id` is often empty.
- Funnel order is by `timestamp` ascending within `user_id` / `application_id`.

## Data quirks (deliberately messy — clean in SQL, then state what you cleaned)
- `os` can be NULL while `device_type = 'android'`.
- `device_type` values are inconsistent: `ios`, `android`, `web-user-b2c`, `Desktop`.
  Normalize with `lower(...)` and bucket web/desktop as needed.
- Empty strings vs NULLs both appear — use `empty()`/`coalesce`/`nullIf`.
- `is_back_filled = 1` marks backfilled rows; consider excluding for live-behaviour
  analysis. `duplicate_id` non-empty marks known duplicates.
- Legacy bad sort key on all tables: `ORDER BY (id, timestamp, user_id)`. Queries
  filter by time/segment, never by `id` — no impact on your SQL, but note it if asked
  about performance.

## KNOWN CONTRADICTIONS in base_context.md (surface these, don't silently pick)

1. **ETA column mismatch.** base_context §2 says `application_started` carries
   `visa_issuance_eta_days` (integer). **The real DDL has no such column** — it has
   `eta_shown Nullable(String)`. If asked about ETA, use `eta_shown` and flag the
   discrepancy.
2. **Two conversion definitions.** base_context §4 defines Conversion rate =
   purchases / **sessions** (headline), but the note in §4 says within-funnel
   conversion = `purchase_completed` users / `application_started` users. These differ.
   State which you use per question; for funnel drop-off use the latter, for the
   leadership headline use the former (and note "sessions" is not a table — approximate
   via `app_session_id` and say so).
3. **Passport pass-rate column name.** §2 references
   `is_crossed_failed_attempt_threshold` (matches DDL) — good — but wording elsewhere
   may lag; always use the DDL column.
4. **`auth_completion_rate` (M4) is NOT computable.** `09_auth_completed.metrics.json`
   defines M4 = `auth_completed / auth_started`, but **`auth_started` has no event/table**
   anywhere (spec, live schema, or sample) — M4 carries `served_by_mv: null`. Do **not**
   approximate it from `payload.attempts` (that counts retries within a *successful* auth,
   not abandoned sessions) or from `auth_completed` alone. Treat M4 as a documented gap.
5. **Legacy `ORDER BY (id, timestamp, user_id)` smell.** The 8 raw tables sort by `id`
   first though queries filter by time/segment — never filter/rely on `id` ordering. New
   JSON `payload` tables correctly drop `id` from the key (event → dims → user_id →
   timestamp); use those keys, not the legacy pattern.

> The Context Agent maintains the live, growing contradiction set under
> `/app/context_docs/contradictions/` — load it at runtime; the five above are the base set.

When you hit a contradiction: state it, choose a definition, justify the choice, and
proceed. This is explicitly rewarded.

## Metric formulas (from context — cite when you use them)
- **Funnel drop-off (stage N):** 1 - (uniq users at N+1 / uniq users at N), in time order.
- **Step-through:** users at N+1 / users at N.
- **Passport-capture pass rate:** count(is_crossed_failed_attempt_threshold = 0) /
  count(document uploads).
- **Revenue per conversion:** `value` on `purchase_completed`, in its `currency`.
- **On-time delivery:** NOT computable from these tables (post-purchase). Say so.
