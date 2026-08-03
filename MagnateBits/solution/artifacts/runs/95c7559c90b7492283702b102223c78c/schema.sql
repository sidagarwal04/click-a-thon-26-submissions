-- Generated schema for feature: express_checkout
-- Run: 95c7559c90b7492283702b102223c78c
-- Table: f_express_checkout_events
--
-- order_by: ORDER BY (event, timestamp, user_id) not (id, timestamp, user_id) as in the 8 legacy tables. id is 5,507-distinct and unique per row here, so an id-first index can't prune anything -- every query in the spec ('does Express lift conversion', 'is there a platform where OTP fails more') filters/groups by event and time first. event has only 5 distinct values (E=5) so it clusters and prunes hard; timestamp is second because every PM question is time-windowed; user_id last co-locates each traveller's 5-event sequence for the windowFunnel/sequenceMatch calls, and it was picked over the co-extensive application_id only because it's mentioned first in the spec (both partition the 1,650 entities identically, confidence 0.80 per the entity derivation, not 1.0 -- the pick is arbitrary but numerically harmless). Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, user_id) read 220,508 B / 5,509 rows; straw-man ORDER BY (timestamp, user_id) read 220,508 B / 5,509 rows. At sample volume (5,509 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.
-- partition_by: toYYYYMM(timestamp), matching all 8 existing tables so cross-table segment joins (app_version/city/client_lib, see cross_reference_hints) prune on the same partition boundaries. The observed window is only 21 days (2026-06-08..2026-06-28) with 5,507 rows; daily partitions would produce ~21 parts holding a few hundred rows each today and thousands of tiny parts once volume scales toward the 700K/year platform run-rate -- monthly keeps parts merge-friendly at both scales.
-- types: id is a 32-char hex string with no dashes (see field profile) -- declaring it UUID, as the 8 legacy tables do, would reject every load; String+ZSTD(1) is used instead. Money fields that get summed (payment_amount, shown_amount) are Decimal(18,4), not Float64, because they're currency-denominated totals, not FX-rate style approximations. payment_latency_ms is UInt32 (rule 4: latency_ms sizing) and otp_attempts is UInt8 (max observed value is 3). Enum-like columns (event, device_type, os, geoip_country_code, city, destination, app_version, client_lib, currency, saved_method_type, payment_currency) are LowCardinality(String), all with single-digit-to-low-teens distinct-value counts per the field profile. Sparse-serialization arithmetic: E=5 roughly-balanced event types means an event-scoped column (e.g. saved_method_type, otp_attempts, payment_amount) is a default in ~(1-1/5)=0.80 of rows -- under the 0.9375 sparse threshold, so it would NOT auto-sparsify. Per house rule 1, table SETTINGS sets ratio_of_defaults_for_sparse_serialization = min(0.9, 1-1/(E+1)) = min(0.9, 1-1/6) = min(0.9, 0.8333) = 0.8333, so these event-scoped columns (measured coverage 15.2%-30% in the field profile, i.e. 70-85% default ratio) do sparsify.
-- nullable: No column is Nullable. The legacy tables are 30-35 Nullable columns out of ~33-38 total (near 90%) -- exactly the anti-pattern rule 5 calls out. Here, event-scoped columns (currency, shown_amount, eligible at 30% coverage; saved_method_type, otp_attempts, otp_success at 18.3%; payment_* at 15.2%) get DEFAULT '' / DEFAULT 0 instead, keeping them usable as hot filter/group-by columns without a null-map tax. user_id and application_id are both 100%-covered per the field profile, so partial_identity_columns is empty -- but any segment-level uniq() must still guard identity columns generically per rule 5's trap; that guard is applied in the MV (uniqStateIf(user_id, user_id != '')) even though this feature happens to have no anonymous rows.
-- ttl: TTL toDateTime(timestamp) + INTERVAL 18 MONTH on the raw table, paired with the two agg_* rollups which carry no TTL (or a much longer one), so 18-month-plus trend queries ('is adoption/latency improving since launch') keep working off ~5-6K rollup rows/year instead of re-reading expired raw partitions.
-- mvs: Two MVs, each targeting a distinct PM question cluster from the spec rather than a raw copy: (1) mv_express_checkout_funnel_daily aggregates per day x event x device_type x os x geoip_country_code with countState/uniqStateIf/sumState, serving the conversion-lift and OTP/payment-failure-by-platform questions; (2) mv_express_checkout_latency_daily aggregates the express_payment_confirmed event only (15.2% of rows, 836 of 5,507 in-sample) by day x device_type x saved_method_type x destination with avgState(payment_latency_ms)/avgState(payment_amount), serving the speed and adoption-segment questions. Both use AggregatingMergeTree-style *State functions (never bare count()/avg()) so states merge correctly across partitions/time, and neither uses POPULATE or an implicit target -- each is CREATE MATERIALIZED VIEW ... TO an explicit agg_* table created EMPTY first. At the 5,507-row sample this is admittedly not required for query speed; the justification is against the 700K-application/year platform run-rate in business_def, where funnel questions over a year of raw rows dwarf a day x event x segment rollup by orders of magnitude -- kept/dropped status must be measured post-load and reported as reduction_factor per house rule 7, not assumed.
-- contrast_with_legacy: The 8 existing tables are one-table-per-event with 30-35 Nullable columns each and ORDER BY (id, timestamp, user_id); instrumentation_notes.md calls this an SDK template artifact, not a design choice. Express Checkout's 5 event types share one funnel (shown -> selected -> saved_method_used -> otp_entered -> confirmed) over the same 1,650 users, so a single wide table with event as the discriminator turns every PM question into one windowFunnel with no cross-table join, at the cost of ~70-85% defaults in event-scoped columns -- which the sparse-serialization setting (0.8333) turns back into cheap storage. Departing from id-first ORDER BY and from pervasive Nullable is intentional here, not an oversight, per house rules 2 and 5.
-- generation_log: attempt 0: lint clean, dry run OK
-- order_by_measured_chosen_bytes: 220508
-- order_by_measured_straw_bytes: 220508
-- order_by_measured_ratio: 1.00
--
-- mv mv_express_checkout_funnel_daily: 5,507 -> 2,081 rows (2.6x) DROPPED
-- mv mv_express_checkout_latency_daily: 5,507 -> 556 rows (9.9x) KEPT

CREATE TABLE IF NOT EXISTS f_express_checkout_events
(
    `event` LowCardinality(String) COMMENT 'json_path=event; discriminator; 5 values (E=5)',
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp; ISO-8601 ms source, DateTime would truncate' CODEC(Delta, ZSTD(1)),
    `id` String COMMENT 'json_path=id; 32-char hex, no dashes -- NOT UUID' CODEC(ZSTD(1)),
    `user_id` String COMMENT 'json_path=user_id; entity key; 100% coverage, 1650 distinct' CODEC(ZSTD(1)),
    `application_id` String COMMENT 'json_path=application_id; secondary key; 100% coverage, 1650 distinct' CODEC(ZSTD(1)),
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type; 4 distinct values',
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; 93.1% coverage; default '''' not Nullable per rule 5',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code; 7 distinct',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city; 7 distinct',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination; 14 distinct',
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version; 3 distinct',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib; 2 distinct',
    `currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=currency; shown-event only, 30% coverage -> long default run',
    `shown_amount` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=shown_amount; summed money field on express_checkout_shown (30% coverage)',
    `eligible` UInt8 DEFAULT 0 COMMENT 'json_path=eligible; boolean flag on shown event, 30% coverage',
    `saved_method_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=saved_method_type; 3 values, express_checkout_selected only (18.3% coverage)',
    `otp_attempts` UInt8 DEFAULT 0 COMMENT 'json_path=otp_attempts; small int count, max observed 3, otp_entered only',
    `otp_success` UInt8 DEFAULT 0 COMMENT 'json_path=otp_success; boolean -> UInt8 per rule 4, otp_entered only',
    `payment_amount` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=payment.amount; currency-denominated, summed -> Decimal not Float64; express_payment_confirmed only (15.2%)',
    `payment_currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=payment.currency; 7 values, confirmed event only',
    `payment_latency_ms` UInt32 DEFAULT 0 COMMENT 'json_path=payment.latency_ms; latency_ms -> UInt32 per rule 4'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, user_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.8333;

CREATE TABLE IF NOT EXISTS agg_express_checkout_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, device_type, os, geoip_country_code)
EMPTY AS
SELECT toDate(timestamp) AS day, event AS event, device_type AS device_type, os AS os, geoip_country_code AS geoip_country_code, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state, sumState(otp_success) AS otp_success_state, sumState(otp_attempts) AS otp_attempts_state FROM f_express_checkout_events GROUP BY day, event, device_type, os, geoip_country_code;

CREATE TABLE IF NOT EXISTS agg_express_checkout_latency_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, device_type, saved_method_type, destination)
EMPTY AS
SELECT toDate(timestamp) AS day, device_type AS device_type, saved_method_type AS saved_method_type, destination AS destination, avgState(payment_latency_ms) AS latency_avg_state, avgState(payment_amount) AS amount_avg_state, countState() AS confirmed_count_state FROM f_express_checkout_events WHERE event = 'express_payment_confirmed' GROUP BY day, device_type, saved_method_type, destination;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_express_checkout_funnel_daily
TO agg_express_checkout_funnel_daily AS
SELECT toDate(timestamp) AS day, event AS event, device_type AS device_type, os AS os, geoip_country_code AS geoip_country_code, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state, sumState(otp_success) AS otp_success_state, sumState(otp_attempts) AS otp_attempts_state FROM f_express_checkout_events GROUP BY day, event, device_type, os, geoip_country_code;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_express_checkout_latency_daily
TO agg_express_checkout_latency_daily AS
SELECT toDate(timestamp) AS day, device_type AS device_type, saved_method_type AS saved_method_type, destination AS destination, avgState(payment_latency_ms) AS latency_avg_state, avgState(payment_amount) AS amount_avg_state, countState() AS confirmed_count_state FROM f_express_checkout_events WHERE event = 'express_payment_confirmed' GROUP BY day, device_type, saved_method_type, destination;
