-- Generated schema for feature: status_sharing
-- Run: 84d55343f482409b832cfa720c7f848f
-- Table: f_status_sharing_events
--
-- order_by: ORDER BY (event, timestamp, share_id). The 8 existing tables use (id, timestamp, user_id); id is unique, so the primary index prunes nothing for queries that filter by time and segment and never by id. Leading with the event discriminator (5 values) prunes hard and compresses well, timestamp second matches every time-windowed query, and share_id last keeps each entity's step sequence co-located for windowFunnel.
-- partition_by: toYYYYMM(timestamp), matching the existing tables so cross-table segment queries prune consistently. Daily partitions would create thousands of tiny parts at this volume and slow merges for no pruning benefit over a monthly part.
-- types: E=5 event types in one wide table, so an event-scoped column is ~(1 - 1/5) = 0.80 defaults -- under ClickHouse's 0.9375 sparse threshold, so it would stay dense. ratio_of_defaults_for_sparse_serialization is set to min(0.9, 1 - 1/(E+1)) = 0.8333 so those columns actually go sparse. id is a 32-char hex string with no dashes and is typed String, not UUID, which would reject the literal outright. timestamp is DateTime64(3) because the source carries milliseconds. Enums are LowCardinality(String); high-cardinality ids are plain String with ZSTD(1); currency-denominated values are Decimal(18,4) so sums are exact; genuinely approximate ratios stay Float64.
-- nullable: No Nullable columns. A null map is a second column to read and it weakens index usage on exactly the columns we filter by; absent values use DEFAULT ''/0 instead. The trap this creates is recorded, not ignored: partial-coverage identity columns are ['application_id', 'user_id'], and every distinct-user metric on them must be uniqIf(col, col != '') because a bare uniq() would count the empty string as a real user.
-- ttl: TTL toDateTime(timestamp) + INTERVAL 18 MONTH on raw events, paired with a rollup that has no TTL. That pairing is what makes the MV worth its cost: the aggregate outlives raw expiry, so long-range trend queries keep answering.
-- mvs: One daily per-step, per-segment rollup. Dimensions are chosen under a row budget (days x event types x cardinality <= row_count/8) so the rollup is materially smaller than the source; anything that fails the 5x measured reduction gate after load is dropped with the number recorded. At sample volume the MV is unnecessary; it is justified against projected annual volume, not against these rows.
-- contrast_with_legacy: One wide table per feature instead of one table per event: every PM question here is a within-feature funnel, which is one windowFunnel on a wide table and an N-way join on the legacy shape. The existing one-table-per-event layout is an SDK artifact, not a design decision, and the id-first sorting key is a bug we do not copy.
-- generation_log: attempt 0: LLM call failed: propose_ddl:status_sharing: failed to produce a valid DDLProposal: RuntimeError: claude CLI failed (1): ; fell back to the deterministic rule-based proposal ; fallback dry run ok=True
--
-- mv mv_status_sharing_funnel_daily: 6,503 -> 305 rows (21.3x) KEPT

CREATE TABLE IF NOT EXISTS f_status_sharing_events
(
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version; events: share_clicked,channel_selected,link_generated; coverage=0.60; distinct=3',
    `application_id` String DEFAULT '' COMMENT 'json_path=application_id; events: share_clicked,channel_selected,link_generated; coverage=0.60; distinct=1600' CODEC(ZSTD(1)),
    `channel` LowCardinality(String) DEFAULT '' COMMENT 'json_path=channel; events: link_opened,channel_selected,link_generated; coverage=0.71; distinct=4',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city; events: share_clicked,channel_selected,link_generated; coverage=0.60; distinct=7',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib; events: share_clicked,channel_selected,link_generated; coverage=0.60; distinct=2',
    `cta` LowCardinality(String) DEFAULT '' COMMENT 'json_path=cta; events: recipient_cta_clicked; coverage=0.05; distinct=1',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination; events: link_opened,share_clicked,channel_selected,link_generated,recipient_cta_clicked; coverage=1.00; distinct=14',
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type; events: share_clicked,channel_selected,link_generated; coverage=0.60; distinct=4',
    `event` LowCardinality(String) DEFAULT '' COMMENT 'json_path=event; events: link_opened,share_clicked,channel_selected,link_generated,recipient_cta_clicked; coverage=1.00; distinct=5',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code; events: share_clicked,channel_selected,link_generated; coverage=0.60; distinct=7',
    `id` String DEFAULT '' COMMENT 'json_path=id; events: link_opened,share_clicked,channel_selected,link_generated,recipient_cta_clicked; coverage=1.00; distinct=6503' CODEC(ZSTD(1)),
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; events: share_clicked,channel_selected,link_generated; coverage=0.57; distinct=4',
    `recipient_is_new_user` UInt8 DEFAULT 0 COMMENT 'json_path=recipient_is_new_user; events: link_opened; coverage=0.36; distinct=2',
    `share_id` String DEFAULT '' COMMENT 'json_path=share_id; events: link_opened,share_clicked,channel_selected,link_generated,recipient_cta_clicked; coverage=1.00; distinct=1600' CODEC(ZSTD(1)),
    `status_shared` LowCardinality(String) DEFAULT '' COMMENT 'json_path=status_shared; events: share_clicked,channel_selected,link_generated; coverage=0.60; distinct=3',
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp; events: link_opened,share_clicked,channel_selected,link_generated,recipient_cta_clicked; coverage=1.00; distinct=3915' CODEC(Delta, ZSTD(1)),
    `user_id` String DEFAULT '' COMMENT 'json_path=user_id; events: share_clicked,channel_selected,link_generated; coverage=0.60; distinct=1600' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, share_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.8333, index_granularity = 8192;

CREATE TABLE IF NOT EXISTS agg_status_sharing_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, channel)
EMPTY AS
SELECT
    toDate(timestamp) AS day,
    event,
    channel,
    countState() AS events_state,
    uniqStateIf(share_id, share_id != '') AS uniq_entities,
    uniqStateIf(user_id, user_id != '') AS uniq_users
FROM f_status_sharing_events
GROUP BY day, event, channel;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_status_sharing_funnel_daily
TO agg_status_sharing_funnel_daily AS
SELECT
    toDate(timestamp) AS day,
    event,
    channel,
    countState() AS events_state,
    uniqStateIf(share_id, share_id != '') AS uniq_entities,
    uniqStateIf(user_id, user_id != '') AS uniq_users
FROM f_status_sharing_events
GROUP BY day, event, channel;
