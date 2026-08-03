-- spec: abandoned_checkout_recovery
-- table: abandonment_recovery_events
-- ordering_key: (recovery_id, event_date, timestamp, event_type, event_id)
-- partition_key: toYYYYMM(event_date)
-- confidence: 0.99
-- executed: 2026-08-02 03:48:48
-- trace: https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/737d5929b42820d5c68c1ffcc42a22fb
--
-- rationale: The landed table and aggregate state are untrusted because of the confirmed column-shift defect. Production writes must be restricted to validated staging; defaults are compatibility fallbacks, not valid identifiers. Staging must deduplicate by event_id, validate required fields, require the same reminder_id on resumed_at_step and reconverted, and enforce exactly one authoritative reminder_sent per recovery_id/reminder_id with valid channel and nonnegative timing. Reminders without exactly one valid sent event are quarantined. Each MV definition includes an explicit AggregatingMergeTree target, explicit target-column INSERT backfill, aliases matching every target column, and a CREATE MATERIALIZED VIEW ... TO target statement. Execute target creation and backfill before creating the live MV; the backfill SELECT and live-MV SELECT are identical. Verify system.columns AggregateFunction types and run representative inserts before migration. Use a high-watermark cutover: isolate writes, record W, validate and deduplicate through W, build/backfill v2 targets, validate counts and multi-reminder fixtures, create live MVs, replay only post-W events through the same idempotent path, reconcile continuity, atomically swap, and resume writes. Keep recovery_id first in the base ORDER BY unless benchmarks demonstrate that operational scans dominate episode retrieval. | ordering key chosen by perf_tool: 1.0x vs legacy baseline.

CREATE TABLE abandonment_recovery_events (event_id String DEFAULT '',
    event_type Enum8('abandonment_detected' = 1, 'reminder_sent' = 2, 'reminder_opened' = 3, 'reminder_cta_clicked' = 4, 'resumed_at_step' = 5, 'reconverted' = 6),
    timestamp DateTime64(3, 'UTC'),
    event_date Date MATERIALIZED toDate(timestamp),
    recovery_id String DEFAULT '',
    reminder_id String DEFAULT '',
    user_id String DEFAULT '',
    application_id String DEFAULT '',
    device_type LowCardinality(String) DEFAULT '',
    os LowCardinality(String) DEFAULT '',
    app_version LowCardinality(String) DEFAULT '',
    geoip_country_code LowCardinality(String) DEFAULT '',
    city LowCardinality(String) DEFAULT '',
    client_lib LowCardinality(String) DEFAULT '',
    destination LowCardinality(String) DEFAULT '',
    drop_step LowCardinality(String) DEFAULT '',
    resume_step LowCardinality(String) DEFAULT '',
    channel LowCardinality(String) DEFAULT '',
    hours_since_drop Nullable(Decimal(8, 2)),
    timing_bucket LowCardinality(String) MATERIALIZED multiIf(isNull(hours_since_drop), 'not_applicable', hours_since_drop < 0, 'invalid', hours_since_drop <= 2, '0-2h', hours_since_drop <= 12, '>2-12h', hours_since_drop <= 36, '>12-36h', hours_since_drop <= 60, '>36-60h', '>60h')) ENGINE = MergeTree PARTITION BY toYYYYMM(event_date) ORDER BY (recovery_id, event_date, timestamp, event_type, event_id);

-- materialized view: abandonment_recovery_daily_metrics
-- answers PM question: Daily operational counts and distinct users/recovery episodes by event type, drop step, channel, timing bucket, device, geo, and destination.
CREATE TABLE atlys.abandonment_recovery_daily_metrics
(
    event_date Date,
    event_type Enum8('abandonment_detected' = 1, 'reminder_sent' = 2, 'reminder_opened' = 3, 'reminder_cta_clicked' = 4, 'resumed_at_step' = 5, 'reconverted' = 6),
    drop_step LowCardinality(String), channel LowCardinality(String), timing_bucket LowCardinality(String), device_type LowCardinality(String), geoip_country_code LowCardinality(String), destination LowCardinality(String),
    event_count AggregateFunction(count), unique_recoveries AggregateFunction(uniqExact, String), unique_users AggregateFunction(uniqExact, String)
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, event_type, drop_step, channel, timing_bucket, device_type, geoip_country_code, destination);

INSERT INTO atlys.abandonment_recovery_daily_metrics (event_date, event_type, drop_step, channel, timing_bucket, device_type, geoip_country_code, destination, event_count, unique_recoveries, unique_users)
SELECT event_date, event_type, drop_step, channel, timing_bucket, device_type, geoip_country_code, destination, countState() AS event_count, uniqExactIfState(recovery_id, recovery_id != '') AS unique_recoveries, uniqExactIfState(user_id, user_id != '') AS unique_users
FROM atlys.abandonment_recovery_events
WHERE event_id != '' AND recovery_id != '' AND user_id != ''
GROUP BY event_date, event_type, drop_step, channel, timing_bucket, device_type, geoip_country_code, destination;

CREATE MATERIALIZED VIEW atlys.abandonment_recovery_daily_metrics_mv
TO atlys.abandonment_recovery_daily_metrics
AS SELECT event_date, event_type, drop_step, channel, timing_bucket, device_type, geoip_country_code, destination, countState() AS event_count, uniqExactIfState(recovery_id, recovery_id != '') AS unique_recoveries, uniqExactIfState(user_id, user_id != '') AS unique_users
FROM atlys.abandonment_recovery_events
WHERE event_id != '' AND recovery_id != '' AND user_id != ''
GROUP BY event_date, event_type, drop_step, channel, timing_bucket, device_type, geoip_country_code, destination
;

-- materialized view: abandonment_recovery_episode_metrics
-- answers PM question: Episode-level abandonment, sent, opened, CTA-clicked, resumed, and reconverted flags plus abandonment-time dimensions.
CREATE TABLE atlys.abandonment_recovery_episode_metrics
(
    recovery_id String,
    drop_step_state AggregateFunction(argMax, String, Tuple(UInt8, DateTime64(3, 'UTC'), String)),
    device_type_state AggregateFunction(argMax, String, Tuple(UInt8, DateTime64(3, 'UTC'), String)),
    geoip_country_code_state AggregateFunction(argMax, String, Tuple(UInt8, DateTime64(3, 'UTC'), String)),
    destination_state AggregateFunction(argMax, String, Tuple(UInt8, DateTime64(3, 'UTC'), String)),
    abandoned AggregateFunction(max, UInt8), sent AggregateFunction(max, UInt8), opened AggregateFunction(max, UInt8), cta_clicked AggregateFunction(max, UInt8), resumed AggregateFunction(max, UInt8), reconverted AggregateFunction(max, UInt8)
)
ENGINE = AggregatingMergeTree ORDER BY recovery_id;

INSERT INTO atlys.abandonment_recovery_episode_metrics (recovery_id, drop_step_state, device_type_state, geoip_country_code_state, destination_state, abandoned, sent, opened, cta_clicked, resumed, reconverted)
SELECT recovery_id, argMaxState(drop_step, tuple(toUInt8(event_type = 'abandonment_detected'), timestamp, event_id)) AS drop_step_state, argMaxState(device_type, tuple(toUInt8(event_type = 'abandonment_detected'), timestamp, event_id)) AS device_type_state, argMaxState(geoip_country_code, tuple(toUInt8(event_type = 'abandonment_detected'), timestamp, event_id)) AS geoip_country_code_state, argMaxState(destination, tuple(toUInt8(event_type = 'abandonment_detected'), timestamp, event_id)) AS destination_state, maxState(toUInt8(event_type = 'abandonment_detected')) AS abandoned, maxState(toUInt8(event_type = 'reminder_sent')) AS sent, maxState(toUInt8(event_type = 'reminder_opened')) AS opened, maxState(toUInt8(event_type = 'reminder_cta_clicked')) AS cta_clicked, maxState(toUInt8(event_type = 'resumed_at_step')) AS resumed, maxState(toUInt8(event_type = 'reconverted')) AS reconverted
FROM atlys.abandonment_recovery_events
WHERE event_id != '' AND recovery_id != '' AND user_id != ''
GROUP BY recovery_id;

CREATE MATERIALIZED VIEW atlys.abandonment_recovery_episode_metrics_mv
TO atlys.abandonment_recovery_episode_metrics
AS SELECT recovery_id, argMaxState(drop_step, tuple(toUInt8(event_type = 'abandonment_detected'), timestamp, event_id)) AS drop_step_state, argMaxState(device_type, tuple(toUInt8(event_type = 'abandonment_detected'), timestamp, event_id)) AS device_type_state, argMaxState(geoip_country_code, tuple(toUInt8(event_type = 'abandonment_detected'), timestamp, event_id)) AS geoip_country_code_state, argMaxState(destination, tuple(toUInt8(event_type = 'abandonment_detected'), timestamp, event_id)) AS destination_state, maxState(toUInt8(event_type = 'abandonment_detected')) AS abandoned, maxState(toUInt8(event_type = 'reminder_sent')) AS sent, maxState(toUInt8(event_type = 'reminder_opened')) AS opened, maxState(toUInt8(event_type = 'reminder_cta_clicked')) AS cta_clicked, maxState(toUInt8(event_type = 'resumed_at_step')) AS resumed, maxState(toUInt8(event_type = 'reconverted')) AS reconverted
FROM atlys.abandonment_recovery_events
WHERE event_id != '' AND recovery_id != '' AND user_id != ''
GROUP BY recovery_id
;

-- materialized view: abandonment_recovery_reminder_metrics
-- answers PM question: Reminder-level channel and timing rates, with outcomes attributed by the same reminder_id.
CREATE TABLE atlys.abandonment_recovery_reminder_metrics
(
    recovery_id String,
    reminder_id String,
    channel_state AggregateFunction(argMax, String, Tuple(UInt8, DateTime64(3, 'UTC'), String)),
    timing_bucket_state AggregateFunction(argMax, String, Tuple(UInt8, DateTime64(3, 'UTC'), String)),
    hours_since_drop_state AggregateFunction(argMax, Nullable(Decimal(8, 2)), Tuple(UInt8, DateTime64(3, 'UTC'), String)),
    sent AggregateFunction(max, UInt8), opened AggregateFunction(max, UInt8), cta_clicked AggregateFunction(max, UInt8), resumed AggregateFunction(max, UInt8), reconverted AggregateFunction(max, UInt8)
)
ENGINE = AggregatingMergeTree ORDER BY (recovery_id, reminder_id);

INSERT INTO atlys.abandonment_recovery_reminder_metrics (recovery_id, reminder_id, channel_state, timing_bucket_state, hours_since_drop_state, sent, opened, cta_clicked, resumed, reconverted)
SELECT recovery_id, reminder_id, argMaxState(channel, tuple(toUInt8(event_type = 'reminder_sent'), timestamp, event_id)) AS channel_state, argMaxState(timing_bucket, tuple(toUInt8(event_type = 'reminder_sent'), timestamp, event_id)) AS timing_bucket_state, argMaxState(hours_since_drop, tuple(toUInt8(event_type = 'reminder_sent'), timestamp, event_id)) AS hours_since_drop_state, maxState(toUInt8(event_type = 'reminder_sent')) AS sent, maxState(toUInt8(event_type = 'reminder_opened')) AS opened, maxState(toUInt8(event_type = 'reminder_cta_clicked')) AS cta_clicked, maxState(toUInt8(event_type = 'resumed_at_step')) AS resumed, maxState(toUInt8(event_type = 'reconverted')) AS reconverted
FROM atlys.abandonment_recovery_events
WHERE event_id != '' AND recovery_id != '' AND user_id != '' AND reminder_id != ''
GROUP BY recovery_id, reminder_id;

CREATE MATERIALIZED VIEW atlys.abandonment_recovery_reminder_metrics_mv
TO atlys.abandonment_recovery_reminder_metrics
AS SELECT recovery_id, reminder_id, argMaxState(channel, tuple(toUInt8(event_type = 'reminder_sent'), timestamp, event_id)) AS channel_state, argMaxState(timing_bucket, tuple(toUInt8(event_type = 'reminder_sent'), timestamp, event_id)) AS timing_bucket_state, argMaxState(hours_since_drop, tuple(toUInt8(event_type = 'reminder_sent'), timestamp, event_id)) AS hours_since_drop_state, maxState(toUInt8(event_type = 'reminder_sent')) AS sent, maxState(toUInt8(event_type = 'reminder_opened')) AS opened, maxState(toUInt8(event_type = 'reminder_cta_clicked')) AS cta_clicked, maxState(toUInt8(event_type = 'resumed_at_step')) AS resumed, maxState(toUInt8(event_type = 'reconverted')) AS reconverted
FROM atlys.abandonment_recovery_events
WHERE event_id != '' AND recovery_id != '' AND user_id != '' AND reminder_id != ''
GROUP BY recovery_id, reminder_id
;