-- Generated schema for feature: express_checkout
-- Run: 76b7839d2f0544dd916dd1f980ee6a0e
-- Table: f_express_checkout_events
--
-- order_by: ORDER BY (event, timestamp, user_id) not (id, timestamp, user_id). id is unique per row (5,507 distinct over 5,507 rows) so an id-first index prunes nothing; every PM question here filters/groups by event type and time window and funnels by user_id (100% coverage, 1,650 distinct values, entity key confidence 0.80 vs application_id tie). event leads because E=5 is low-cardinality and nearly every question ('cut otp_success by device/os/geo', conversion lift) filters or groups by event first; timestamp second because all four PM questions are time-windowed; user_id last to co-locate each user's 5-step sequence for windowFunnel. Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, user_id) read 220,508 B / 5,509 rows; straw-man ORDER BY (timestamp, user_id) read 220,508 B / 5,509 rows. At sample volume (5,509 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.
-- partition_by: toYYYYMM(timestamp), matching all 8 existing tables so cross-table segment joins (app_version/city/client_lib vs destination_card_clicked) prune on the same partition boundaries. At ~5,507 rows over 20 days (projected ~100k rows/year at this rate), daily partitions would produce thousands of tiny parts for a table this size and slow merges for no pruning benefit monthly doesn't already give.
-- types: Single wide table across E=5 event types. An event-scoped column (e.g. payment_latency_ms, present on only express_payment_confirmed = 836/5507 = 15.2% of rows, i.e. ~84.8% default) sits right at the edge: with E balanced event types the naive default ratio is (1-1/E) = 0.80, under the 0.9375 sparse threshold, so it would NOT auto-sparsify. We therefore set ratio_of_defaults_for_sparse_serialization = min(0.9, 1-1/(E+1)) = min(0.9, 1-1/6) = min(0.9, 0.8333) = 0.8333, below the true ~0.80-0.85 default ratios measured on otp_attempts/otp_success (18.3% coverage -> 81.7% default), shown_amount/currency/eligible (30% coverage -> 70% default), and payment_* fields (15.2% coverage -> 84.8% default), so these columns get sparse serialization at this table's actual default rates. id is String not UUID: the raw id is a 32-char hex string with no dashes ('f105934b4c083002827058f3' truncated sample is 25 chars but format is non-dashed hex), which UUID parsing rejects; the 8 legacy tables declare id UUID and would fail to load this exact field. timestamp is DateTime64(3) because the source carries millisecond precision ('2026-06-08T06:00:00.000'); DateTime would silently truncate it, breaking the latency-from-shown-to-confirmed question. Money fields (shown_amount, payment_amount) use Decimal(18,4) since they are currency-denominated and will be summed for revenue-per-conversion-style rollups; payment_latency_ms is UInt32 (ms values up to a few thousand, well under 4B); otp_attempts is UInt8 (observed max 3).
-- nullable: No Nullable columns, unlike the legacy tables (30-35 Nullable of ~33-38 columns each). Every segment/id column defaults to '' or 0: os has 93.1% coverage but 'missing OS' is not a tri-state fact worth a null-map cost on a hot group-by column used in the OTP-failure-by-platform question, so DEFAULT '' is used. Because identity/segment columns default to '' rather than NULL, uniq(user_id) would count '' as a distinct user if any partial-identity rows existed; here user_id and application_id are both 100% covered across all 5 event types (spec's 'events with a partial envelope: none'), so partial_identity_columns is empty and no uniqIf guard is strictly required for correctness -- but the funnel MV still uses uniqStateIf(user_id, user_id != '') defensively since it is the house-rule default for any AggregatingMergeTree distinct-user state.
-- ttl: TTL toDateTime(timestamp) + INTERVAL 18 MONTH on the raw table, paired with two unbounded-retention agg_ rollups (agg_express_checkout_funnel_daily, agg_express_checkout_payment_perf_daily) so segment-level conversion and latency trend queries beyond 18 months keep working on the pre-aggregated state columns after raw rows expire, at a fraction of the row count.
-- mvs: Two MVs, each targeting a distinct cluster of the 4 PM questions rather than one copy-of-raw MV. mv_express_checkout_funnel_daily (event x segment x day, countState/uniqStateIf) answers conversion-lift, adoption-by-segment, and OTP/confirmation-rate-by-platform by grouping on the same columns PMs already asked to cut by (device_type, os, geoip_country_code, destination, saved_method_type) instead of scanning 5,507+ raw rows and re-deriving per-user step sequences each time. mv_express_checkout_payment_perf_daily isolates the two genuinely sparse, expensive-to-scan measures (payment_latency_ms at 15.2% coverage, otp_success at 18.3% coverage) with -If aggregate combinators so latency and OTP-failure trends don't require re-filtering the wide table's mostly-default columns on every query. Both use AggregatingMergeTree with uniqState/avgState/sumState/countState (never plain count()/avg(), which cannot be merged correctly across partitions for an AggregatingMergeTree target). Per house rule 7, actual keep/drop must be decided post-load by comparing measured row counts on this ~5,507-row / 20-day sample projected to ~700K applications/year run-rate company-wide (this feature's own annual volume is far smaller since it's a checkout-stage feature, not every applicant), not on the sample volume itself, which is too small to show a convincing reduction factor by construction.
-- contrast_with_legacy: The 8 existing tables are one-table-per-event with ORDER BY (id, timestamp, user_id) and 30-35/33-38 Nullable columns -- instrumentation_notes.md calls this an SDK template artifact, not a design choice. This feature's headline questions ('does Express lift conversion', 'cut OTP failure by device/os/geo') are within-feature funnels across all 5 event types for the same user, which a single wide table answers with one windowFunnel/GROUP BY; five event-per-table tables would need a 5-way join on user_id per question. Naming as f_express_checkout_events / agg_express_checkout_* / mv_express_checkout_* avoids the exact collision risk called out for this context layer: other feature specs' drop_step/event values can literally match legacy table names (e.g. pay_now_clicked), so the f_/agg_/mv_ prefix is a correctness guard, not cosmetic.
-- generation_log: attempt 0: lint clean, dry run OK
-- order_by_measured_chosen_bytes: 220508
-- order_by_measured_straw_bytes: 220508
-- order_by_measured_ratio: 1.00
--
-- mv mv_express_checkout_funnel_daily: 5,507 -> 4,693 rows (1.2x) DROPPED
-- mv mv_express_checkout_payment_perf_daily: 5,507 -> 506 rows (10.9x) KEPT

CREATE TABLE IF NOT EXISTS f_express_checkout_events
(
    `id` String COMMENT 'json_path=id; 32-char hex string, not UUID-parseable; legacy tables wrongly type this UUID' CODEC(ZSTD(1)),
    `event` LowCardinality(String) COMMENT 'json_path=event; discriminator, 5 values',
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp' CODEC(Delta, ZSTD(1)),
    `user_id` String COMMENT 'json_path=user_id; entity key, 100% coverage' CODEC(ZSTD(1)),
    `application_id` String COMMENT 'json_path=application_id; secondary key, 100% coverage' CODEC(ZSTD(1)),
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type',
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; 93.1% coverage; missing = unknown OS, not analytically distinct from empty, so DEFAULT '''' not Nullable',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination',
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib',
    `currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=currency; only on express_checkout_shown (30% coverage = 1/E-ish, event-scoped)',
    `shown_amount` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=shown_amount; currency-denominated amount shown, scoped to express_checkout_shown',
    `eligible` UInt8 DEFAULT 0 COMMENT 'json_path=eligible; boolean flag on express_checkout_shown',
    `saved_method_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=saved_method_type; card/upi/wallet, scoped to express_checkout_selected',
    `otp_attempts` UInt8 DEFAULT 0 COMMENT 'json_path=otp_attempts; small int, max observed 3, scoped to otp_entered',
    `otp_success` UInt8 DEFAULT 0 COMMENT 'json_path=otp_success; boolean flag, scoped to otp_entered',
    `payment_amount` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=payment.amount; summed currency value, scoped to express_payment_confirmed',
    `payment_currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=payment.currency',
    `payment_latency_ms` UInt32 DEFAULT 0 COMMENT 'json_path=payment.latency_ms; milliseconds, fits UInt32; scoped to express_payment_confirmed'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, user_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.8333;

CREATE TABLE IF NOT EXISTS agg_express_checkout_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, device_type, os, geoip_country_code, destination, saved_method_type)
EMPTY AS
SELECT toDate(timestamp) AS day, event, device_type, os, geoip_country_code, destination, saved_method_type, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state FROM f_express_checkout_events GROUP BY day, event, device_type, os, geoip_country_code, destination, saved_method_type;

CREATE TABLE IF NOT EXISTS agg_express_checkout_payment_perf_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, device_type, os, geoip_country_code)
EMPTY AS
SELECT toDate(timestamp) AS day, device_type, os, geoip_country_code, avgStateIf(payment_latency_ms, event = 'express_payment_confirmed') AS latency_avg_state, sumStateIf(payment_amount, event = 'express_payment_confirmed') AS payment_amount_sum_state, countIfState(event = 'express_payment_confirmed') AS confirmed_count_state, avgStateIf(otp_success, event = 'otp_entered') AS otp_success_rate_state, countIfState(event = 'otp_entered') AS otp_entered_count_state FROM f_express_checkout_events GROUP BY day, device_type, os, geoip_country_code;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_express_checkout_funnel_daily
TO agg_express_checkout_funnel_daily AS
SELECT toDate(timestamp) AS day, event, device_type, os, geoip_country_code, destination, saved_method_type, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state FROM f_express_checkout_events GROUP BY day, event, device_type, os, geoip_country_code, destination, saved_method_type;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_express_checkout_payment_perf_daily
TO agg_express_checkout_payment_perf_daily AS
SELECT toDate(timestamp) AS day, device_type, os, geoip_country_code, avgStateIf(payment_latency_ms, event = 'express_payment_confirmed') AS latency_avg_state, sumStateIf(payment_amount, event = 'express_payment_confirmed') AS payment_amount_sum_state, countIfState(event = 'express_payment_confirmed') AS confirmed_count_state, avgStateIf(otp_success, event = 'otp_entered') AS otp_success_rate_state, countIfState(event = 'otp_entered') AS otp_entered_count_state FROM f_express_checkout_events GROUP BY day, device_type, os, geoip_country_code;
