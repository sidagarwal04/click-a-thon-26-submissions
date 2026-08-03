-- Generated schema for feature: express_checkout
-- Run: c61900e783f747899ce131fea87bedf2
-- Table: f_express_checkout_events
--
-- order_by: Never lead with a unique id: the 8 legacy tables ORDER BY (id, timestamp, user_id) and base_context.md admits queries never filter by id, wasting the primary index entirely. Here entity_key=user_id was derived (100% coverage on 5/5 event types, 1,650 distinct users, 61% span >1 funnel step) vs runner-up application_id which partitions rows identically -- pick is arbitrary but harmless (confidence 0.80). event leads because E=5 is low-cardinality and every PM question (conversion, OTP failure by platform, adoption by segment) filters or groups by event first; timestamp second because all analysis is time-windowed (the observed 2026-06-08..06-28 window); user_id last co-locates each user's shown->selected->saved->otp->confirmed sequence for windowFunnel. Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, user_id) read 220,508 B / 5,509 rows; straw-man ORDER BY (timestamp, user_id) read 220,508 B / 5,509 rows. At sample volume (5,509 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.
-- partition_by: toYYYYMM(timestamp) matches all 8 existing tables so cross-table segment joins (app_version/city/client_lib, see cross_reference_hints) prune consistently on the same partition boundaries. At the observed rate (5,507 rows / 21 days ~ 262/day, projecting to well under a few hundred thousand rows/yr for this one feature against Atlys's 700K+ applications/yr run-rate) daily partitioning would produce thousands of tiny parts and slow merges for no pruning benefit monthly doesn't already give.
-- types: E=5 event types roughly balanced (1650/1007/1007/1007/836 -> the smallest two event-scoped columns still see ~15-30% coverage), so an event-scoped column's default ratio is ~(1-1/E)=0.80, just under the ClickHouse sparse threshold of 0.9375 -- it would NOT auto-sparsify. Setting ratio_of_defaults_for_sparse_serialization = min(0.9, 1-1/(E+1)) = min(0.9, 1-1/6) = min(0.9, 0.8333) = 0.8333 pulls the threshold below that 0.80 observed ratio so payment_amount/payment_latency_ms/otp_attempts/otp_success/saved_method_type/shown_amount/currency/eligible all go sparse. id is String not UUID -- the raw `id` field is a 32-char hex string with no dashes (sample f105934b4c083002827058f3) which UUID parsing rejects. payment_amount/shown_amount are Decimal(18,4) because they are summed currency amounts (PM revenue-per-conversion-style metric), not approximations. otp_attempts is UInt8 (observed max 3), payment_latency_ms is UInt32 (observed up to ~3879ms, well within range but not squeezed into UInt16 since latency can spike).
-- nullable: No Nullable columns at all, departing from the legacy tables where 30-35 of ~33-38 columns are Nullable. os has 93.1% coverage (missing 6.9%) but is a hot segment-dim used directly in the OTP/platform-failure question, so it gets DEFAULT '' rather than a null map -- same for every event-scoped column (shown_amount, saved_method_type, otp_attempts, otp_success, payment_*), which default to '' or 0 instead of NULL. Because identity/segment columns default rather than null, partial_identity_columns is empty here (user_id and application_id are 100% covered on this feature, unlike the abandoned/status_sharing features) -- but the uniqIf guard is still applied in the MV (uniqStateIf(user_id, user_id != '')) as a defensive standard, not because this feature has anonymous rows.
-- ttl: Raw table gets TTL toDateTime(timestamp) + INTERVAL 18 MONTH matching the default retention window. The paired MV (agg_express_checkout_funnel_daily) is NOT given a TTL so daily/segment aggregates survive raw expiry -- once raw rows older than 18mo drop, funnel-lift and OTP-failure trend queries over that span still run against the (much smaller) daily rollup instead of failing or needing re-derivation from data that no longer exists.
-- mvs: One MV, not several, because all four PM questions (conversion lift, OTP/payment failure by device/os/geo, latency, segment adoption) share the same grouping shape: day x event x device_type x os x geoip_country_code x destination x saved_method_type. Splitting into per-question MVs would just re-run the same GROUP BY with different SELECT lists. AggregatingMergeTree + uniqStateIf/countState/avgState/sumState is used throughout because summing pre-aggregated distinct-user counts across merged parts is wrong; every non-key output is an aggregate state per the renderer's EMPTY AS constraint. At the observed sample the raw table is 5,507 rows and the rollup collapses to roughly a few hundred grouped rows (event x device x os x geo x method combinations, most sparse) -- honestly under the 5x bar to judge purely on this sample, so the real justification is projected volume: at Atlys's 700K+ applications/yr run-rate and this feature covering a subset of returning-traveller checkouts, raw rows will reach the hundreds of thousands/yr while the daily/segment grid stays bounded by day-count x segment-cardinality, giving a durable multi-x reduction once TTL starts evicting raw rows the MV must still answer trend queries over.
-- contrast_with_legacy: The 8 legacy tables are one-table-per-event-type (per instrumentation_notes.md, an SDK template artifact, not a design choice) with ORDER BY (id, timestamp, user_id) and 30-35 Nullable columns out of ~33-38. This proposal is the opposite on all three axes: one wide table for all 5 express_checkout event types (so the shown->selected->saved_method_used->otp_entered->confirmed funnel is a single windowFunnel/sequenceMatch with zero joins, versus a 5-way join under the legacy pattern), ORDER BY led by the low-cardinality event discriminator instead of a unique id (id here isn't even in ORDER BY, matching house rule 2's explicit ban), and zero Nullable columns (versus ~85-90% Nullable in the legacy tables) because every partial-coverage field here has a semantically safe default (0/'') and the identity aggregation trap is closed with uniqStateIf guards rather than null-checking.
-- generation_log: attempt 0: lint clean, dry run OK
-- order_by_measured_chosen_bytes: 220508
-- order_by_measured_straw_bytes: 220508
-- order_by_measured_ratio: 1.00
--
-- mv mv_express_checkout_funnel_daily: 5,507 -> 4,693 rows (1.2x) DROPPED

CREATE TABLE IF NOT EXISTS f_express_checkout_events
(
    `event` LowCardinality(String) COMMENT 'json_path=event; discriminator; 5 event types, drives ORDER BY prefix',
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp; ISO-8601 ms source, no truncation' CODEC(Delta, ZSTD(1)),
    `id` String DEFAULT '' COMMENT 'json_path=id; 32-char hex, no dashes -- NOT UUID' CODEC(ZSTD(1)),
    `user_id` String DEFAULT '' COMMENT 'json_path=user_id; entity key; 100% coverage on this feature' CODEC(ZSTD(1)),
    `application_id` String DEFAULT '' COMMENT 'json_path=application_id; secondary key, 100% coverage, joins to application_started elsewhere' CODEC(ZSTD(1)),
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type; 4 distinct values, segment dim',
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; 93.1% coverage; DEFAULT '''' not Nullable, still a hot filter col per PM Q2',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code; 7 distinct, segment dim',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city; 7 distinct values',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination; 14 distinct, segment dim, always cut by destination per business_def',
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version; 3 distinct values',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib; 2 distinct values (mobile-rn/web-js)',
    `shown_amount` Decimal(18,4) DEFAULT 0 COMMENT 'json_path=shown_amount; event-scoped to express_checkout_shown only (30.0% coverage), currency amount' CODEC(ZSTD(1)),
    `currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=currency; scoped to express_checkout_shown, 7 distinct values',
    `eligible` UInt8 DEFAULT 0 COMMENT 'json_path=eligible; bool->UInt8, scoped to express_checkout_shown',
    `saved_method_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=saved_method_type; scoped to express_checkout_selected, 3 values, PM adoption-by-method question',
    `otp_attempts` UInt8 DEFAULT 0 COMMENT 'json_path=otp_attempts; scoped to otp_entered, max observed 3, UInt8 fits',
    `otp_success` UInt8 DEFAULT 0 COMMENT 'json_path=otp_success; bool->UInt8, scoped to otp_entered, PM Q2 failure-rate metric',
    `payment_amount` Decimal(18,4) DEFAULT 0 COMMENT 'json_path=payment.amount; scoped to express_payment_confirmed, summed currency value' CODEC(ZSTD(1)),
    `payment_currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=payment.currency; scoped to express_payment_confirmed, 7 distinct',
    `payment_latency_ms` UInt32 DEFAULT 0 COMMENT 'json_path=payment.latency_ms; scoped to express_payment_confirmed, PM Q3 speed metric'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, user_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.8333333333333334;

CREATE TABLE IF NOT EXISTS agg_express_checkout_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, device_type, os, geoip_country_code, destination, saved_method_type)
EMPTY AS
SELECT toDate(timestamp) AS day, event AS event, device_type AS device_type, os AS os, geoip_country_code AS geoip_country_code, destination AS destination, saved_method_type AS saved_method_type, uniqStateIf(user_id, user_id != '') AS users_state, countState() AS events_state, sumState(otp_success) AS otp_success_state, avgState(otp_attempts) AS otp_attempts_state, avgState(payment_latency_ms) AS latency_ms_state, sumState(payment_amount) AS payment_amount_state FROM f_express_checkout_events GROUP BY day, event, device_type, os, geoip_country_code, destination, saved_method_type;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_express_checkout_funnel_daily
TO agg_express_checkout_funnel_daily AS
SELECT toDate(timestamp) AS day, event AS event, device_type AS device_type, os AS os, geoip_country_code AS geoip_country_code, destination AS destination, saved_method_type AS saved_method_type, uniqStateIf(user_id, user_id != '') AS users_state, countState() AS events_state, sumState(otp_success) AS otp_success_state, avgState(otp_attempts) AS otp_attempts_state, avgState(payment_latency_ms) AS latency_ms_state, sumState(payment_amount) AS payment_amount_state FROM f_express_checkout_events GROUP BY day, event, device_type, os, geoip_country_code, destination, saved_method_type;
