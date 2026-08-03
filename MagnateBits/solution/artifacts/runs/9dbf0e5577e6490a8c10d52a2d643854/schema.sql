-- Generated schema for feature: unseen
-- Run: 9dbf0e5577e6490a8c10d52a2d643854
-- Table: f_unseen_events
--
-- order_by: House rule #2 bans a unique id in lead position; the legacy tables use (id, timestamp, user_id) and the id column here is a 5,363-distinct hex string, useless for pruning. event has only E=6 values and every PM question ('apply rate', 'valid vs rejected mix', 'segment cuts') filters or groups by event first, so it leads. timestamp is second because every question is time-windowed (window observed: 2026-06-08..2026-06-28). user_id is third: it is the derived entity_key (100% coverage, 2,100 distinct, present on 6/6 event types, ties with application_id but chosen by first-mention order per house rule tie-break) and is the funnel grouping key for windowFunnel(field_shown->...->checkout_with_coupon). Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, user_id) read 214,751 B / 5,365 rows; straw-man ORDER BY (timestamp, user_id) read 214,751 B / 5,365 rows. At sample volume (5,365 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.
-- partition_by: toYYYYMM(timestamp) matches all 8 existing tables so cross-table segment-vocabulary joins (app_version/city) prune consistently on the same partition scheme. At current volume (5,363 rows over 21 days) daily partitions would produce ~21 parts averaging ~255 rows each -- far below a healthy part size and would slow merges; monthly is correct even projected to full annual run-rate.
-- types: E=6 event types here (not the generic 5 used in the house-rule example), so an event-scoped column (e.g. discount_type, present only on coupon_applied) has a default ratio of roughly 1 - 1/E = 1 - 1/6 = 0.833 in the balanced case, and the profile confirms it: discount_type coverage is 0.108 (default ratio 0.892), reject_reason coverage 0.050 (default ratio 0.950), final_value 0.184 (default ratio 0.816). These sit close to and above the stock 0.9375 sparse threshold for the highest-sparsity columns but below it for cart_value-adjacent ones, so per house rule we set ratio_of_defaults_for_sparse_serialization = min(0.9, 1 - 1/(E+1)) = min(0.9, 1 - 1/7) = min(0.9, 0.857) = 0.857, which is low enough to make discount_type/reject_reason/final_value/discount_amount/coupon_code go sparse even though they don't clear the stock 0.9375 bar. id is declared String, not UUID -- the profile shows it is a 32-char hex string (id column, e.g. '40e20b22bab295b7731969b1'), which the existing tables' UUID columns would reject. discount_amount and final_value are Decimal(18,4) because they are summed for margin-cost reporting (a money measure per house rule #4), not Float64. timestamp is DateTime64(3) since the source carries millisecond precision ('2026-06-08T06:00:00.000').
-- nullable: No Nullable columns. coupon_code (49.3% coverage), discount_type (10.8%), discount_amount (40.0%), reject_reason (5.0%) and final_value (18.4%) all get DEFAULT '' / 0 instead of Nullable, per house rule #5, avoiding a null-map per column on what are otherwise hot group-by/filter columns. However every identity column (user_id, application_id) has 100% coverage in this feature's profile -- unlike sharer/recipient features, there is no anonymous-event arm here -- so partial_identity_columns is empty and no uniqIf guard is strictly required for correctness, but the analytics layer still uses uniqIf(user_id, user_id != '') defensively since coupon_code's default '' could otherwise be miscounted as a real code in naive uniq(coupon_code) queries.
-- ttl: TTL toDateTime(timestamp) + INTERVAL 18 MONTH on the raw table, matching house-rule default and the other feature tables, paired with the two rollup MVs which are not raw-copies and can be retained longer so daily-granularity trend queries (apply rate over a quarter, margin cost year-over-year) survive raw expiry on a fraction of the bytes.
-- mvs: Two MVs, each targeting a distinct PM question cluster per house rule #7 (an MV must beat a straight raw copy). mv_unseen_funnel_daily pre-aggregates by day+event+segment (device_type/geoip/destination/coupon_code/reject_reason) with countState/uniqStateIf/sumState so the funnel-and-reject-mix and segment-cut questions run as cheap AggregatingMergeTree merges instead of scanning raw rows and running windowFunnel per query. mv_unseen_coupon_margin_daily is scoped to event='checkout_with_coupon' only, aggregated by day+coupon_code, directly serving 'total discount_amount' and 'which codes drive volume vs erode margin' plus the coupon-vs-no-coupon (coupon_code='') baseline comparison for conversion lift. At the observed sample size (5,363 rows, ~21 days) neither MV's reduction factor has been measured yet -- both should be validated post-load against the keep/drop gate (reduction_factor >= 5x) and dropped with a recorded 'kept=false' if they don't clear it; the case for keeping them rests on Atlys's 700K+ applications/year run-rate (per business_def.atlys_operates_run_rate), where the raw table would be several orders of magnitude larger than this sample and the day+event+segment grain collapses that volume hard.
-- engine: Checked the field profile for a re-ingestion/backfill signal (duplicate_id, is_back_filled, dedup_*, *_reingested-shaped column) and found none among the 17 candidate columns -- every column is either envelope, funnel-event, or money/reason data. Default MergeTree is used; no ReplacingMergeTree justified by column shape.
-- contrast_with_legacy: The 8 existing tables are one-table-per-event with ORDER BY (id, timestamp, user_id) and 30-35 Nullable columns out of ~33-38 total (per instrumentation_notes.md, an SDK-template artifact, not a design choice). This feature instead uses one wide table across all 6 event types with event leading ORDER BY (not id), because every PM question here is a within-feature funnel (field_shown -> ... -> checkout_with_coupon) that would otherwise require a 6-way join across per-event tables. Sorting by event first also clusters coupon_applied-only columns like discount_type contiguously, so their ~89% default-run gets long, aligned stretches inside each granule -- which is exactly what makes the 0.857 sparse-serialization threshold effective instead of theoretical.
-- generation_log: attempt 0: lint clean, dry run OK
-- order_by_measured_chosen_bytes: 214751
-- order_by_measured_straw_bytes: 214751
-- order_by_measured_ratio: 1.00
--
-- mv mv_unseen_funnel_daily: 5,363 -> 4,613 rows (1.2x) DROPPED
-- mv mv_unseen_coupon_margin_daily: 5,363 -> 120 rows (44.7x) KEPT

CREATE TABLE IF NOT EXISTS f_unseen_events
(
    `id` String COMMENT 'json_path=id; 32-char hex id, unique per row; row-unique so never leads ORDER BY' CODEC(ZSTD(1)),
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp; ISO-8601 with ms; DateTime64(3) preserves it, plain DateTime would truncate' CODEC(Delta, ZSTD(1)),
    `event` LowCardinality(String) COMMENT 'json_path=event; 6 event types, discriminator, leads ORDER BY',
    `user_id` String DEFAULT '' COMMENT 'json_path=user_id; entity key; 100% coverage, 2100 distinct' CODEC(ZSTD(1)),
    `application_id` String DEFAULT '' COMMENT 'json_path=application_id; secondary key; 100% coverage, 2100 distinct' CODEC(ZSTD(1)),
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type; 4 distinct values',
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; 93.3% coverage; missing not analytically tri-state, use default not Nullable',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code; 7 distinct',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city; 7 distinct',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination; 14 distinct, ISO-2',
    `currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=currency; 7 distinct',
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version; 3 distinct',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib; 2 distinct',
    `cart_value` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=cart_value; currency-denominated, present on all 6 event types at 100% coverage',
    `coupon_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=coupon_code; 49.3% coverage (null = no-coupon baseline row on checkout_with_coupon); 6 distinct codes -> enum-like',
    `discount_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=discount_type; only on coupon_applied (10.8% overall coverage), 2 values percent/flat',
    `discount_amount` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=discount_amount; money, summed for margin cost; 40% coverage across coupon_applied/discount_shown/checkout_with_coupon',
    `reject_reason` LowCardinality(String) DEFAULT '' COMMENT 'json_path=reject_reason; only on coupon_rejected (5% overall coverage), 4 values',
    `final_value` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=final_value; money, only on checkout_with_coupon (18.4% overall coverage)'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, user_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.857;

CREATE TABLE IF NOT EXISTS agg_unseen_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, device_type, geoip_country_code, destination, coupon_code, reject_reason)
EMPTY AS
SELECT toDate(timestamp) AS day, event, device_type, geoip_country_code, destination, coupon_code, reject_reason, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state, sumState(discount_amount) AS discount_amount_state FROM f_unseen_events GROUP BY day, event, device_type, geoip_country_code, destination, coupon_code, reject_reason;

CREATE TABLE IF NOT EXISTS agg_unseen_coupon_margin_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, coupon_code)
EMPTY AS
SELECT toDate(timestamp) AS day, coupon_code, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state, sumState(discount_amount) AS discount_amount_state, sumState(final_value) AS final_value_state FROM f_unseen_events WHERE event = 'checkout_with_coupon' GROUP BY day, coupon_code;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_unseen_funnel_daily
TO agg_unseen_funnel_daily AS
SELECT toDate(timestamp) AS day, event, device_type, geoip_country_code, destination, coupon_code, reject_reason, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state, sumState(discount_amount) AS discount_amount_state FROM f_unseen_events GROUP BY day, event, device_type, geoip_country_code, destination, coupon_code, reject_reason;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_unseen_coupon_margin_daily
TO agg_unseen_coupon_margin_daily AS
SELECT toDate(timestamp) AS day, coupon_code, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state, sumState(discount_amount) AS discount_amount_state, sumState(final_value) AS final_value_state FROM f_unseen_events WHERE event = 'checkout_with_coupon' GROUP BY day, coupon_code;
