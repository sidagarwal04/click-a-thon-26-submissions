# CUJ 1 Ingestion Run Report — `03_status_sharing`

- **Target Table:** `status_sharing_events`
- **Execution Timestamp:** `2026-08-02T03:56:11.415777+00:00`
- **Trace URL:** https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/e5a553e2d8e50d4e63c6de8bcaa990c7
- **Run Mode:** `live_run`

---

## 1. What was decided

- **Strategy:** `CREATE`
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
  "share_id": "share_id",
  "destination": "destination",
  "status_shared": "status_shared",
  "channel": "channel",
  "recipient_is_new_user": "recipient_is_new_user",
  "cta": "cta"
}
```

---

## 4. Materialized View

-- justification: daily segment rollup for accelerated dashboard query execution
CREATE MATERIALIZED VIEW IF NOT EXISTS status_sharing_events_daily_mv
ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(date)
ORDER BY (device_type, os, geoip_country_code, destination, channel, date, event)
AS SELECT
    toYYYYMMDD(timestamp) AS date,
    device_type, os, geoip_country_code, destination, channel, event,
    count() AS total_events,
    uniqState(user_id) AS unique_users
FROM status_sharing_events
GROUP BY device_type, os, geoip_country_code, destination, channel, date, event;

---

## 5. Context audit

- **Discovered Attributes (17):** status_sharing_events.event, status_sharing_events.id, status_sharing_events.timestamp, status_sharing_events.device_type, status_sharing_events.os, status_sharing_events.app_version, status_sharing_events.geoip_country_code, status_sharing_events.city, status_sharing_events.client_lib, status_sharing_events.user_id, status_sharing_events.application_id, status_sharing_events.share_id, status_sharing_events.destination, status_sharing_events.status_shared, status_sharing_events.channel, status_sharing_events.recipient_is_new_user, status_sharing_events.cta
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
- **Documentation Gaps (7):** Undocumented column `app_version` in status_sharing_events; Undocumented column `client_lib` in status_sharing_events; Undocumented column `share_id` in status_sharing_events; Undocumented column `status_shared` in status_sharing_events; Undocumented column `channel` in status_sharing_events; Undocumented column `recipient_is_new_user` in status_sharing_events; Undocumented column `cta` in status_sharing_events

---

## 6. Table Semantics (CUJ 1 → CUJ 2 Semantic Handoff)

- **Description:** Lets a traveller share their live application status via a link (WhatsApp, copy,
- **Concepts:** status sharing events, event, id, device_type, os, app_version, geoip_country_code, city, client_lib
- **Embedding Dimensions:** `0`

---

## 7. Deployment & Ingestion

- **DDL Execution:** `rolled_back`
- **Rows Loaded:** **0** rows from `events.ndjson`
- **Schema Registry Version:** `0`
- **Context Upserts:** `17` entries

---

## 8. Complete Reasoning Chain

1. **context_agent::refresh_chdb_from_live** (context_agent): refreshed live ClickHouse catalog (8 tables present; drift: False)
2. **context_agent::build_context_package** (context_agent): assembled existing table shapes from schema_registry and business metrics/rules from business_context
3. **context_agent::decide_strategy** (context_agent): strategy decided: CREATE
4. **instrumentation_agent::design_schema** (instrumentation_agent): led ordering with (timestamp, user_id) for temporal granule pruning, partitioned monthly toYYYYMM, and mapped nested event fields
5. **query_architect::design_to_ddl** (query_architect): rendered design intent into ClickHouse MergeTree DDL, SummingMergeTree MV, and JSONEachRow INSERT
6. **validator::invariant_check** (validator): verified 4 ClickHouse invariants (violations: 0)
7. **context_agent::context_diff** (context_agent): audited context: 17 additions, 3 conflicts, 7 gaps
8. **context_agent::execute_ddl** (context_agent): executed CREATE TABLE and CREATE MATERIALIZED VIEW on ClickHouse Cloud with rollback guarantee
9. **context_agent::load_events** (context_agent): loaded 0 events from events.ndjson into ClickHouse Cloud table status_sharing_events
10. **context_agent::register_schema_version** (context_agent): registered table 'status_sharing_events' version 0 in schema_registry
11. **context_agent::sync_context** (context_agent): upserted 17 attributes into business_context and context_changelog with trace attribution
12. **context_agent::write_table_semantics** (context_agent): wrote table description, concepts, and embedding (0 dims) for status_sharing_events into chDB table_semantics (v1)
