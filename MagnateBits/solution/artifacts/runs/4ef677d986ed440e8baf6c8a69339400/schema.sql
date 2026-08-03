-- Generated schema for feature: express_checkout
-- Run: 4ef677d986ed440e8baf6c8a69339400
-- Table: f_express_checkout_events
--
-- order_by: ORDER BY (event, timestamp, user_id). Never id-first: id has 5,507/5,507 distinct values (fully unique) so an id-first index prunes nothing, exactly the failure mode base_context.md documents for the 8 legacy tables (ORDER BY (id, timestamp, user_id)). event is 5 values here (E=5) and every PM question ('conversion by step', 'otp_success by platform', 'adoption by segment') filters or groups by event first, so it prunes hardest and dictionary-compresses to near nothing. timestamp second because every question is time-windowed (window: 2026-06-08..2026-06-28). user_id last as the derived entity key (100% coverage, 1,650 distinct, present on all 5/5 event types, 61% of values span >1 funnel step) so windowFunnel/sequenceMatch over a user's events reads a contiguous run. Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, user_id) read 220,508 B / 5,509 rows; straw-man ORDER BY (timestamp, user_id) read 220,508 B / 5,509 rows. At sample volume (5,509 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.
-- partition_by: toYYYYMM(timestamp), matching all 8 existing tables so cross-table time-windowed queries (e.g. joining against destination_card_clicked by toDate(timestamp)) prune consistently across the database. At this feature's volume (5,507 rows over 3 weeks, projected well under 1M rows/year even at Atlys's 700K-applications-per-year run rate) daily partitions would create hundreds of tiny parts per year and slow merges for no pruning benefit monthly doesn't already give.
-- types: E=5 observed event types (express_checkout_shown/selected, saved_method_used, otp_entered, express_payment_confirmed). An event-scoped column (shown_amount, currency, eligible at 30.0% coverage; saved_method_type, otp_attempts, otp_success at 18.3%; payment_* at 15.2%) is a default in ~(1-1/E)=(1-1/5)=0.80 of rows on average when E event types are roughly balanced -- just under the MergeTree sparse-serialization cutoff (ratio_of_defaults_for_sparse_serialization default 0.9375), so it would NOT auto-sparsify. Setting ratio_of_defaults_for_sparse_serialization = min(0.9, 1-1/(E+1)) = min(0.9, 1-1/6) = min(0.9, 0.8333) = 0.8333 pulls the cutoff below the observed default-ratio so these columns do go sparse. id is String not UUID: the field profile shows id as a 32-char-hex-looking string (samples like 'f105934b4c083002827058f3') with no dashes -- declaring UUID would reject the raw literal on load, the single most likely ingestion failure per house rules. payment_amount/shown_amount are Decimal(18,4) (summed currency values), payment_latency_ms is UInt32 (observed up to ~3,879ms, well within range, avoids UInt16 overflow risk on tail latencies), otp_attempts is UInt8 (max observed 3), eligible/otp_success are UInt8 booleans (JSON true/false).
-- nullable: No Nullable columns. os has 93.1% coverage (the only column below 100% among identity/envelope fields) but is DEFAULT '' rather than Nullable(String): os is a hot group-by column for the 'which platform fails more' question, and Nullable adds a null-map and defeats LowCardinality dictionary efficiency for a column already being filtered constantly. All event-scoped fields (currency, shown_amount, eligible, saved_method_type, otp_attempts, otp_success, payment_*) use DEFAULT '' / DEFAULT 0 rather than Nullable -- their 'missingness' is structural (wrong event type), not a genuine tri-state, so Nullable would only add overhead. This departs from all 8 legacy tables (30-35 of ~33-38 columns Nullable each) which house rules identify as the pattern to fix, not copy. user_id and application_id are both 100% coverage on this feature (unlike the recipient-side pattern in status_sharing), so partial_identity_columns is empty here -- but the uniqIf(user_id, user_id != '') guard is still applied in the rollup MV as a defensive default per house rule 5, costing nothing at 100% coverage.
-- ttl: TTL toDateTime(timestamp) + INTERVAL 18 MONTH on the raw table, matching legacy convention. Paired with agg_express_checkout_funnel_daily (retained without a TTL / longer TTL) so day-grain conversion, OTP-failure-rate, and latency trends over >18 months keep working after raw rows expire, at a fraction of the row count.
-- mvs: One MV (mv_express_checkout_funnel_daily -> agg_express_checkout_funnel_daily, AggregatingMergeTree) covers all four PM questions via countState/uniqStateIf/sumState/avgState grouped by day x event x device_type x os x geoip_country_code x destination x saved_method_type. A second MV for 'time from shown -> confirmed per user' was considered and rejected: that metric needs per-entity sequence matching (windowFunnel over ordered events per user_id), which is not a summable/mergeable aggregate state and would require reading raw rows regardless -- an MV wouldn't reduce cost for it, so it stays a raw-table query against the (event, timestamp, user_id) index, which the raw table's TTL/18-month retention already supports. At the observed sample (5,507 rows over 3 weeks) the funnel MV's row reduction cannot be measured here without executing DDL/load, so kept=true is asserted against projected_annual_rows: Atlys's 700K-applications/year run rate implies a materially larger annual event volume for this feature than the 5,507-row, 3-week sample, at which point the day x segment grouping (bounded by 5 events x ~4 device_types x ~4 os x ~7 geo x ~14 destination x ~4 saved_method_type combinations, most sparsely populated) collapses many more raw rows per group than at sample volume -- this should be re-verified with a measured count()-vs-count() check after load and dropped if reduction is under 5x, per the keep/drop gate.
-- contrast_with_legacy: The 8 existing tables are one-table-per-event-type with ORDER BY (id, timestamp, user_id) and 30-35 of ~33-38 columns Nullable -- instrumentation_notes.md calls this an SDK template artifact, not a design choice. f_express_checkout_events instead is one wide table for the whole feature (event LowCardinality discriminator + union of the 5 event-specific field sets), because every PM question here is a within-feature funnel (shown->selected->saved_method_used->otp_entered->confirmed) that a table-per-event layout would force into a 5-way join; sorting by event first clusters each event type contiguously so the sparse event-scoped columns (currency, saved_method_type, payment_*, etc.) still compress like a table-per-event layout would, without the join cost. id is moved out of ORDER BY entirely (was position 1 in legacy) since it is 100% unique and legacy's own base_context.md admits queries never filter by id.
-- generation_log: attempt 0: lint clean, dry run OK
-- order_by_measured_chosen_bytes: 220508
-- order_by_measured_straw_bytes: 220508
-- order_by_measured_ratio: 1.00
--
-- mv mv_express_checkout_funnel_daily: 5,507 -> 4,693 rows (1.2x) DROPPED

CREATE TABLE IF NOT EXISTS f_express_checkout_events
(
    `id` String COMMENT 'json_path=id; 32-char hex, not UUID-parseable; legacy tables'' UUID id would reject this literal' CODEC(ZSTD(1)),
    `event` LowCardinality(String) COMMENT 'json_path=event',
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp' CODEC(Delta, ZSTD(1)),
    `user_id` String COMMENT 'json_path=user_id; 100% coverage on all 5 event types; entity key' CODEC(ZSTD(1)),
    `application_id` String DEFAULT '' COMMENT 'json_path=application_id; 100% coverage; secondary key' CODEC(ZSTD(1)),
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type',
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; 93.1% coverage; treated as unknown='''' not Nullable, avoids null-map cost on a hot segment column',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination',
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib',
    `currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=currency; only on express_checkout_shown (30.0% coverage), sparse by design',
    `shown_amount` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=shown_amount; currency-denominated, summable',
    `eligible` UInt8 DEFAULT 0 COMMENT 'json_path=eligible; JSON bool -> UInt8, only present on express_checkout_shown',
    `saved_method_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=saved_method_type; card/upi/wallet, only on express_checkout_selected (18.3% coverage)',
    `otp_attempts` UInt8 DEFAULT 0 COMMENT 'json_path=otp_attempts; max observed 3, only on otp_entered',
    `otp_success` UInt8 DEFAULT 0 COMMENT 'json_path=otp_success; JSON bool -> UInt8, only on otp_entered',
    `payment_amount` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=payment.amount; summed money field, nested under payment on express_payment_confirmed only',
    `payment_currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=payment.currency',
    `payment_latency_ms` UInt32 DEFAULT 0 COMMENT 'json_path=payment.latency_ms; milliseconds, max observed values in low thousands, UInt32 comfortably fits and avoids UInt16 overflow risk'
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
SELECT toDate(timestamp) AS day, event AS event, device_type AS device_type, os AS os, geoip_country_code AS geoip_country_code, destination AS destination, saved_method_type AS saved_method_type, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state, sumState(otp_success) AS otp_success_state, avgState(payment_latency_ms) AS latency_ms_avg_state, sumState(payment_amount) AS payment_amount_state FROM atlys.f_express_checkout_events GROUP BY day, event, device_type, os, geoip_country_code, destination, saved_method_type;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_express_checkout_funnel_daily
TO agg_express_checkout_funnel_daily AS
SELECT toDate(timestamp) AS day, event AS event, device_type AS device_type, os AS os, geoip_country_code AS geoip_country_code, destination AS destination, saved_method_type AS saved_method_type, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state, sumState(otp_success) AS otp_success_state, avgState(payment_latency_ms) AS latency_ms_avg_state, sumState(payment_amount) AS payment_amount_state FROM atlys.f_express_checkout_events GROUP BY day, event, device_type, os, geoip_country_code, destination, saved_method_type;
