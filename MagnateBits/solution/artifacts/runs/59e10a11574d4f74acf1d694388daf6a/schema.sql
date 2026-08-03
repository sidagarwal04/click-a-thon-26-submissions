-- Generated schema for feature: abandoned_checkout_recovery
-- Run: 59e10a11574d4f74acf1d694388daf6a
-- Table: f_abandoned_checkout_recovery_events
--
-- order_by: ORDER BY (event, timestamp, user_id). The 8 existing tables use (id, timestamp, user_id); id is unique, so the primary index prunes nothing for queries that filter by time and segment and never by id. Leading with the event discriminator (6 values) prunes hard and compresses well, timestamp second matches every time-windowed query, and user_id last keeps each entity's step sequence co-located for windowFunnel.
-- partition_by: toYYYYMM(timestamp), matching the existing tables so cross-table segment queries prune consistently. Daily partitions would create thousands of tiny parts at this volume and slow merges for no pruning benefit over a monthly part.
-- types: E=6 event types in one wide table, so an event-scoped column is ~(1 - 1/6) = 0.83 defaults -- under ClickHouse's 0.9375 sparse threshold, so it would stay dense. ratio_of_defaults_for_sparse_serialization is set to min(0.9, 1 - 1/(E+1)) = 0.8571 so those columns actually go sparse. id is a 32-char hex string with no dashes and is typed String, not UUID, which would reject the literal outright. timestamp is DateTime64(3) because the source carries milliseconds. Enums are LowCardinality(String); high-cardinality ids are plain String with ZSTD(1); currency-denominated values are Decimal(18,4) so sums are exact; genuinely approximate ratios stay Float64.
-- nullable: No Nullable columns. A null map is a second column to read and it weakens index usage on exactly the columns we filter by; absent values use DEFAULT ''/0 instead. The trap this creates is recorded, not ignored: partial-coverage identity columns are none, and every distinct-user metric on them must be uniqIf(col, col != '') because a bare uniq() would count the empty string as a real user.
-- ttl: TTL toDateTime(timestamp) + INTERVAL 18 MONTH on raw events, paired with a rollup that has no TTL. That pairing is what makes the MV worth its cost: the aggregate outlives raw expiry, so long-range trend queries keep answering.
-- mvs: One daily per-step, per-segment rollup. Dimensions are chosen under a row budget (days x event types x cardinality <= row_count/8) so the rollup is materially smaller than the source; anything that fails the 5x measured reduction gate after load is dropped with the number recorded. At sample volume the MV is unnecessary; it is justified against projected annual volume, not against these rows.
-- contrast_with_legacy: One wide table per feature instead of one table per event: every PM question here is a within-feature funnel, which is one windowFunnel on a wide table and an N-way join on the legacy shape. The existing one-table-per-event layout is an SDK artifact, not a design decision, and the id-first sorting key is a bug we do not copy.
-- generation_log: attempt 0: LLM call failed: propose_ddl:abandoned_checkout_recovery: failed to produce a valid DDLProposal: RuntimeError: claude CLI failed (1): ; fell back to the deterministic rule-based proposal ; fallback dry run ok=True
--
-- mv mv_abandoned_checkout_recovery_funnel_daily: 5,919 -> 473 rows (12.5x) KEPT

CREATE TABLE IF NOT EXISTS f_abandoned_checkout_recovery_events
(
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=3',
    `application_id` String DEFAULT '' COMMENT 'json_path=application_id; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=2300' CODEC(ZSTD(1)),
    `channel` LowCardinality(String) DEFAULT '' COMMENT 'json_path=channel; events: reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=0.61; distinct=3',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=7',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=2',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=14',
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=4',
    `drop_step` LowCardinality(String) DEFAULT '' COMMENT 'json_path=drop_step; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=4',
    `event` LowCardinality(String) DEFAULT '' COMMENT 'json_path=event; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=6',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=7',
    `hours_since_drop` UInt16 DEFAULT 0 COMMENT 'json_path=hours_since_drop; events: reminder_sent; coverage=0.39; distinct=5',
    `id` String DEFAULT '' COMMENT 'json_path=id; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=5919' CODEC(ZSTD(1)),
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=0.95; distinct=4',
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=4696' CODEC(Delta, ZSTD(1)),
    `user_id` String DEFAULT '' COMMENT 'json_path=user_id; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=2300' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, user_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.8571, index_granularity = 8192;

CREATE TABLE IF NOT EXISTS agg_abandoned_checkout_recovery_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, device_type)
EMPTY AS
SELECT
    toDate(timestamp) AS day,
    event,
    device_type,
    countState() AS events_state,
    uniqStateIf(user_id, user_id != '') AS uniq_entities
FROM f_abandoned_checkout_recovery_events
GROUP BY day, event, device_type;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_abandoned_checkout_recovery_funnel_daily
TO agg_abandoned_checkout_recovery_funnel_daily AS
SELECT
    toDate(timestamp) AS day,
    event,
    device_type,
    countState() AS events_state,
    uniqStateIf(user_id, user_id != '') AS uniq_entities
FROM f_abandoned_checkout_recovery_events
GROUP BY day, event, device_type;
