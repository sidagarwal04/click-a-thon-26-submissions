-- spec: status_sharing
-- table: visa_status_sharing_events
-- ordering_key: (event_type, status_shared, channel, event_date, destination_key, event_timestamp, share_id, application_id, user_id, event_id)
-- partition_key: toYYYYMM(event_date)
-- confidence: 0.99
-- executed: 2026-08-02 03:40:36
-- trace: https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/fa8f02506c28c1b9d4e7a7a6ada0f05d
--
-- rationale: The columns_ddl value is only a single column list, with no CREATE TABLE, semicolon, or second statement. Each materialized_view value is also a single CREATE MATERIALIZED VIEW statement with no trailing semicolon, avoiding the prior harness multi-statement and end-of-query failures. The canonical ORDER BY is event/status/channel/date/destination-leading and matches the documented workload; the share_id-leading candidate is explicitly not recommended. For production maintainability, prefer explicit AggregateFunction target tables plus CREATE MATERIALIZED VIEW ... TO statements when the migration runner supports multi-step deployment; the supplied single-statement MVs are the executable fallback. Deploy landing and canonical tables, then MV targets/views, and backfill once within a bounded watermark that does not overlap live ingestion. Reject or quarantine empty event_id values before deduplication. Deduplicate landing rows with row_number() OVER (PARTITION BY event_id ORDER BY ingest_version DESC, payload_hash DESC), where payload_hash hashes the complete canonical payload. Validate event types, channels, CTAs, and destinations upstream; require share_id, channel, and status_shared on link_generated, while destination may be a valid ISO-2 code or explicit NULL. The dimensions MV uses only link_generated rows and the earliest deterministic event_timestamp,event_id, so later recipient events cannot overwrite origin attribution. Monitor rejected IDs, duplicate rates, invalid dimensions, bounded-backfill overlap, finalized MV totals, and monthly DROP PARTITION or TTL/tiering retention. Query AggregateFunction states with matching -Merge combinators. | ordering key chosen by perf_tool: 1.0x vs legacy baseline.

CREATE TABLE visa_status_sharing_events (event_id String,
event_type LowCardinality(String),
event_timestamp DateTime64(3, 'UTC'),
event_date Date MATERIALIZED toDate(event_timestamp),
device_type LowCardinality(String) DEFAULT '',
os LowCardinality(String) DEFAULT '',
app_version LowCardinality(String) DEFAULT '',
geoip_country_code LowCardinality(String) DEFAULT '',
city String DEFAULT '',
client_lib LowCardinality(String) DEFAULT '',
user_id String DEFAULT '',
application_id String DEFAULT '',
share_id String DEFAULT '',
destination Nullable(FixedString(2)),
destination_key FixedString(2) MATERIALIZED ifNull(destination, toFixedString('', 2)),
status_shared LowCardinality(String) DEFAULT '',
channel LowCardinality(String) DEFAULT '',
recipient_is_new_user UInt8 DEFAULT 0,
cta LowCardinality(String) DEFAULT '',
ingest_version UInt64 DEFAULT 0) ENGINE = MergeTree PARTITION BY toYYYYMM(event_date) ORDER BY (event_type, status_shared, channel, event_date, destination_key, event_timestamp, share_id, application_id, user_id, event_id);

-- materialized view: visa_status_sharing_daily_event_metrics
-- answers PM question: Daily channel mix, status segmentation, new-user opens, destination spread, and distinct users, applications, and shares.
CREATE MATERIALIZED VIEW atlys.visa_status_sharing_daily_event_metrics ENGINE = AggregatingMergeTree PARTITION BY toYYYYMM(event_date) ORDER BY (event_date, event_type, status_shared, channel, destination_key) AS SELECT event_date, event_type, status_shared, channel, destination_key, countState() AS event_count, uniqExactStateIf(user_id, user_id != '') AS unique_user_count, uniqExactStateIf(application_id, application_id != '') AS unique_application_count, uniqExactStateIf(share_id, share_id != '') AS unique_share_count, countStateIf(event_type = 'link_opened' AND recipient_is_new_user = 1 AND share_id != '') AS new_user_open_event_count, uniqExactStateIf(share_id, event_type = 'link_opened' AND recipient_is_new_user = 1 AND share_id != '') AS new_user_open_share_count FROM atlys.visa_status_sharing_events GROUP BY event_date, event_type, status_shared, channel, destination_key
;

-- materialized view: visa_status_sharing_share_metrics
-- answers PM question: One-row-per-share generation, open, new-user-open, and CTA funnel metrics.
CREATE MATERIALIZED VIEW atlys.visa_status_sharing_share_metrics ENGINE = AggregatingMergeTree ORDER BY share_id AS SELECT share_id, minStateIf(event_timestamp, event_type = 'link_generated') AS first_link_generated_at, minStateIf(event_timestamp, event_type = 'link_opened') AS first_opened_at, minStateIf(event_timestamp, event_type = 'link_opened' AND recipient_is_new_user = 1) AS first_new_user_opened_at, minStateIf(event_timestamp, event_type = 'recipient_cta_clicked') AS first_cta_at, countStateIf(event_type = 'link_opened') AS open_event_count, countStateIf(event_type = 'link_opened' AND recipient_is_new_user = 1) AS new_user_open_event_count, countStateIf(event_type = 'recipient_cta_clicked') AS cta_event_count, uniqExactStateIf(event_id, event_type = 'link_opened' AND recipient_is_new_user = 1) AS new_user_open_event_id_count, uniqExactStateIf(event_id, event_type = 'recipient_cta_clicked') AS cta_event_id_count FROM atlys.visa_status_sharing_events WHERE share_id != '' GROUP BY share_id
;

-- materialized view: visa_status_sharing_share_dimensions
-- answers PM question: Authoritative origin dimensions for recipient events keyed by share_id, including valid NULL destinations.
CREATE MATERIALIZED VIEW atlys.visa_status_sharing_share_dimensions ENGINE = AggregatingMergeTree ORDER BY share_id AS SELECT share_id, argMinStateIf(destination_key, tuple(event_timestamp, event_id), event_type = 'link_generated') AS origin_destination_state, argMinStateIf(channel, tuple(event_timestamp, event_id), event_type = 'link_generated') AS origin_channel_state, argMinStateIf(status_shared, tuple(event_timestamp, event_id), event_type = 'link_generated') AS origin_status_shared_state FROM atlys.visa_status_sharing_events WHERE share_id != '' GROUP BY share_id
;