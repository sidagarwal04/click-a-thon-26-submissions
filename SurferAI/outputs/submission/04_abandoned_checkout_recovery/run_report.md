# CUJ 1 Ingestion Run Report — `04_abandoned_checkout_recovery`

- **Target Table:** `abandoned_checkout_recovery`
- **Execution Timestamp:** `2026-08-02T03:56:57.745458+00:00`
- **Trace URL:** https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/3159b563000be54fb75a9059211f5134
- **Run Mode:** `live_run`

---

## 1. What was decided

- **Strategy:** `EVOLVE`
- **Rationale:** 

---

## 2. Schema design rationale

- **Ordering Key:** `(timestamp, user_id)` — temporal locality allows ClickHouse to prune granules before filtering by user cohort.
- **Partitioning:** `toYYYYMM(timestamp)` — monthly partitions bound the active part count to 12 over a 1-year retention window.
- **Encodings & Types:** `LowCardinality(String)` for bounded enums (device_type, os, geoip_country_code); `UInt8` for booleans/flags; `Nullable(...)` for sparse fields.
- **Data Lifecycle Retention:** `TTL timestamp + INTERVAL 12 MONTH` for GDPR compliance and storage cost optimization.

---

## 3. Field mapping

```json
{
  "event": "event",
  "id": "id",
  "timestamp": "timestamp",
  "device_type": "device_type",
  "os": "os",
  "app_version": "app_version",
  "geoip_country_code": "geoip_country_code",
  "city": "city",
  "client_lib": "client_lib",
  "user_id": "user_id",
  "application_id": "application_id",
  "destination": "destination",
  "drop_step": "drop_step",
  "channel": "channel",
  "hours_since_drop": "hours_since_drop"
}
```

---

## 4. Materialized View

-- justification: daily segment rollup for accelerated dashboard query execution
CREATE MATERIALIZED VIEW IF NOT EXISTS abandoned_checkout_recovery_daily_mv
ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(date)
ORDER BY (device_type, os, geoip_country_code, destination, channel, date, event)
AS SELECT
    toYYYYMMDD(timestamp) AS date,
    device_type, os, geoip_country_code, destination, channel, event,
    count() AS total_events,
    uniqState(user_id) AS unique_users
FROM abandoned_checkout_recovery
GROUP BY device_type, os, geoip_country_code, destination, channel, date, event;

---

## 5. Context audit

- **Discovered Attributes (15):** abandoned_checkout_recovery.event, abandoned_checkout_recovery.id, abandoned_checkout_recovery.timestamp, abandoned_checkout_recovery.device_type, abandoned_checkout_recovery.os, abandoned_checkout_recovery.app_version, abandoned_checkout_recovery.geoip_country_code, abandoned_checkout_recovery.city, abandoned_checkout_recovery.client_lib, abandoned_checkout_recovery.user_id, abandoned_checkout_recovery.application_id, abandoned_checkout_recovery.destination, abandoned_checkout_recovery.drop_step, abandoned_checkout_recovery.channel, abandoned_checkout_recovery.hours_since_drop
- **Conflicts Detected (3):** Denominator definition conflict in 3. The eight raw event tables#1: | Table | Kind | Emitted when | Key event-specific columns |
|-------|------|--------------|----------------------------|
| `destination_card_clicked` | funnel | user taps a destination card | `destination`, `visa_type`, `card_type`, `flow` |
| `application_started` | funnel | user starts an application | `purpose`, `eta_shown`, `co_travelers`, `destination` |
| `document_uploaded` | funnel | passport image submitted | `doc_type`, `capture_mode`, `retry_count`, `is_crossed_failed_attempt_threshold` |
| `purchase_completed` | funnel | payment succeeds (**conversion**) | `value` (revenue), `currency`, `insurance_amount`, `coupon_applied` |
| `search_typed` | supporting | user types a destination search | `search_term`, `results_count`, `source` |
| `landing_page_scrolled` | supporting | user scrolls a landing page | `scroll_depth_pct`, `time_on_page_s`, `page_version` |
| `auth_completed` | supporting | user finishes login/signup | `auth_method`, `is_new_user`, `attempts` |
| `pay_now_clicked` | supporting | user taps Pay Now at checkout | `payment_method`, `amount`, `currency`, `coupon_applied` |; Denominator definition conflict in 4. Metric definitions#0: **Conversion rate** = completed purchases ÷ **sessions**. A session is a single
app-open / web visit. This is the headline number reported to leadership.; Denominator definition conflict in 4. Metric definitions#6: > Note on funnel conversion: within the funnel, we treat **conversion as
> `purchase_completed` users ÷ users who started an application**
> (`application_started`). This is the denominator used in the drop-off dashboards.
- **Documentation Gaps (5):** Undocumented column `app_version` in abandoned_checkout_recovery; Undocumented column `client_lib` in abandoned_checkout_recovery; Undocumented column `drop_step` in abandoned_checkout_recovery; Undocumented column `channel` in abandoned_checkout_recovery; Undocumented column `hours_since_drop` in abandoned_checkout_recovery

---

## 6. Table Semantics (CUJ 1 → CUJ 2 Semantic Handoff)

- **Description:** Detects travellers who drop out at a funnel step without converting and sends a
- **Concepts:** abandoned checkout recovery, event, id, device_type, os, app_version, geoip_country_code, city, client_lib
- **Embedding Dimensions:** `0`

---

## 7. Deployment & Ingestion

- **DDL Execution:** `ok`
- **Rows Loaded:** **5,919** rows from `events.ndjson`
- **Schema Registry Version:** `2`
- **Context Upserts:** `15` entries

---

## 8. Complete Reasoning Chain

1. **context_agent::refresh_chdb_from_live** (context_agent): refreshed live ClickHouse catalog (8 tables present; drift: False)
2. **context_agent::build_context_package** (context_agent): assembled existing table shapes from schema_registry and business metrics/rules from business_context
3. **context_agent::decide_strategy** (context_agent): strategy decided: EVOLVE
4. **instrumentation_agent::design_schema** (instrumentation_agent): led ordering with (timestamp, user_id) for temporal granule pruning, partitioned monthly toYYYYMM, and mapped nested event fields
5. **query_architect::design_to_ddl** (query_architect): rendered design intent into ClickHouse MergeTree DDL, SummingMergeTree MV, and JSONEachRow INSERT
6. **validator::invariant_check** (validator): verified 4 ClickHouse invariants (violations: 0)
7. **context_agent::context_diff** (context_agent): audited context: 15 additions, 3 conflicts, 5 gaps
8. **context_agent::execute_ddl** (context_agent): executed CREATE TABLE and CREATE MATERIALIZED VIEW on ClickHouse Cloud with rollback guarantee
9. **context_agent::load_events** (context_agent): loaded 5,919 events from events.ndjson into ClickHouse Cloud table abandoned_checkout_recovery
10. **context_agent::register_schema_version** (context_agent): registered table 'abandoned_checkout_recovery' version 2 in schema_registry
11. **context_agent::sync_context** (context_agent): upserted 15 attributes into business_context and context_changelog with trace attribution
12. **context_agent::write_table_semantics** (context_agent): wrote table description, concepts, and embedding (0 dims) for abandoned_checkout_recovery into chDB table_semantics (v1)
