-- Generated schema for feature: instant_forex
-- Run: 7534cf5b2bde4111977eeb3720af7e38
-- Table: f_instant_forex_events
--
-- order_by: ORDER BY (event, timestamp, user_id). The 8 existing tables use (id, timestamp, user_id); id is unique, so the primary index prunes nothing for queries that filter by time and segment and never by id. Leading with the event discriminator (5 values) prunes hard and compresses well, timestamp second matches every time-windowed query, and user_id last keeps each entity's step sequence co-located for windowFunnel.
-- partition_by: toYYYYMM(timestamp), matching the existing tables so cross-table segment queries prune consistently. Daily partitions would create thousands of tiny parts at this volume and slow merges for no pruning benefit over a monthly part.
-- types: E=5 event types in one wide table, so an event-scoped column is ~(1 - 1/5) = 0.80 defaults -- under ClickHouse's 0.9375 sparse threshold, so it would stay dense. ratio_of_defaults_for_sparse_serialization is set to min(0.9, 1 - 1/(E+1)) = 0.8333 so those columns actually go sparse. id is a 32-char hex string with no dashes and is typed String, not UUID, which would reject the literal outright. timestamp is DateTime64(3) because the source carries milliseconds. Enums are LowCardinality(String); high-cardinality ids are plain String with ZSTD(1); currency-denominated values are Decimal(18,4) so sums are exact; genuinely approximate ratios stay Float64.
-- nullable: No Nullable columns. A null map is a second column to read and it weakens index usage on exactly the columns we filter by; absent values use DEFAULT ''/0 instead. The trap this creates is recorded, not ignored: partial-coverage identity columns are none, and every distinct-user metric on them must be uniqIf(col, col != '') because a bare uniq() would count the empty string as a real user.
-- ttl: TTL toDateTime(timestamp) + INTERVAL 18 MONTH on raw events, paired with a rollup that has no TTL. That pairing is what makes the MV worth its cost: the aggregate outlives raw expiry, so long-range trend queries keep answering.
-- mvs: One daily per-step, per-segment rollup. Dimensions are chosen under a row budget (days x event types x cardinality <= row_count/8) so the rollup is materially smaller than the source; anything that fails the 5x measured reduction gate after load is dropped with the number recorded. At sample volume the MV is unnecessary; it is justified against projected annual volume, not against these rows.
-- contrast_with_legacy: One wide table per feature instead of one table per event: every PM question here is a within-feature funnel, which is one windowFunnel on a wide table and an N-way join on the legacy shape. The existing one-table-per-event layout is an SDK artifact, not a design decision, and the id-first sorting key is a bug we do not copy.
-- generation_log: attempt 0: LLM call failed: propose_ddl:instant_forex: failed to produce a valid DDLProposal: RuntimeError: claude CLI failed (1): ; fell back to the deterministic rule-based proposal ; fallback dry run ok=True
--
-- mv mv_instant_forex_funnel_daily: 6,237 -> 640 rows (9.8x) KEPT

CREATE TABLE IF NOT EXISTS f_instant_forex_events
(
    `addon_value_inr` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=addon_value_inr; events: forex_added_to_cart,forex_purchased; coverage=0.20; distinct=1258',
    `amount` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=amount; events: amount_entered,forex_added_to_cart,forex_purchased; coverage=0.37; distinct=6',
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=3',
    `application_id` String DEFAULT '' COMMENT 'json_path=application_id; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=2900' CODEC(ZSTD(1)),
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=7',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=2',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=14',
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=4',
    `event` LowCardinality(String) DEFAULT '' COMMENT 'json_path=event; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=5',
    `from_currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=from_currency; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=1',
    `fx_rate` Float64 DEFAULT 0 COMMENT 'json_path=fx_rate; events: forex_offer_shown; coverage=0.46; distinct=2899',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=7',
    `id` String DEFAULT '' COMMENT 'json_path=id; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=6237' CODEC(ZSTD(1)),
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=0.94; distinct=4',
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=2901' CODEC(Delta, ZSTD(1)),
    `to_currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=to_currency; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=13',
    `user_id` String DEFAULT '' COMMENT 'json_path=user_id; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=2900' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, user_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.8333, index_granularity = 8192;

CREATE TABLE IF NOT EXISTS agg_instant_forex_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, city)
EMPTY AS
SELECT
    toDate(timestamp) AS day,
    event,
    city,
    countState() AS events_state,
    uniqStateIf(user_id, user_id != '') AS uniq_entities,
    sumState(addon_value_inr) AS sum_addon_value_inr
FROM f_instant_forex_events
GROUP BY day, event, city;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_instant_forex_funnel_daily
TO agg_instant_forex_funnel_daily AS
SELECT
    toDate(timestamp) AS day,
    event,
    city,
    countState() AS events_state,
    uniqStateIf(user_id, user_id != '') AS uniq_entities,
    sumState(addon_value_inr) AS sum_addon_value_inr
FROM f_instant_forex_events
GROUP BY day, event, city;
