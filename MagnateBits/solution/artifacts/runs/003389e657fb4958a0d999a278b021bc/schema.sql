-- Generated schema for feature: deep_linear
-- Run: 003389e657fb4958a0d999a278b021bc
-- Table: f_deep_linear_events
--
-- order_by: Never lead with `id` (3165 distinct, useless for pruning) or `booking_id` alone (560 distinct but only meaningful once event is fixed). ORDER BY (event, timestamp, booking_id): event has only 8 values and every PM question ('step-through rate', 'largest drop', 'does network predict auth success') filters or groups by event first, so it prunes hard; timestamp is second because all questions are time-windowed (the observed window is a single day, but production queries run over months); booking_id last co-locates each booking's 8-step sequence within an event+time slice, which is what windowFunnel-style step analysis over the funnel needs. Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, booking_id) read 139,552 B / 3,167 rows; straw-man ORDER BY (timestamp, booking_id) read 139,552 B / 3,167 rows. At sample volume (3,167 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.
-- partition_by: toYYYYMM(timestamp), matching all 8 existing tables so cross-feature segment joins (see cross_reference_hints) prune on the same partition boundary. At this feature's projected scale (~3-4M rows/year) monthly partitions stay in the tens-of-thousands-of-rows-per-partition range per event type; daily partitions would produce ~2900 tiny parts/8-years and slow merges for no pruning benefit since queries are month/quarter windows, not single days.
-- types: E=8 event types are roughly balanced (560..266, no type below 8% of total), so an event-scoped column (slot_window, document_kind/scan fields, insurance_tier, payment_* fields) is a default in ~1-1/8=87.5% of rows on average, worse for the rarest-scoped columns -- comfortably above the sparse threshold. Setting ratio_of_defaults_for_sparse_serialization = min(0.9, 1-1/(E+1)) = min(0.9, 1-1/9) = min(0.9, 0.8889) = 0.8889 (below the ClickHouse default of 0.9375) ensures these columns actually switch to sparse serialization instead of silently staying dense at ~87.5% defaults, which is under the stock 0.9375 default and would NOT go sparse without this override. `id` is String not UUID because the raw id is a 32-char hex string with no dashes -- the existing tables' `id UUID` declaration would reject this literal on load. `document.scan.*` and `payment.*` are flattened out of their nested JSON objects into flat typed columns (document_scan_quality_score, payment_card_network, etc.) because ClickHouse aggregates/filters on flat columns, not nested structs, and PM question 2 ('does payment.card.network predict authorisation success') requires network as a first-class segment dim. payment_amount_minor is Decimal(18,4) (money, will be summed) not Float64; auth_latency_ms is UInt32 (ms-scale, fits); document_scan_page_count is UInt8 (small count).
-- nullable: Every column is DEFAULT '' / DEFAULT 0 except document_scan_quality_score, which is the one genuinely tri-state field: a real score of e.g. 0.02 (low quality, still a scan) must be distinguishable from 'no scan happened because this row isn't a document_uploaded event' -- coalescing both to 0 would corrupt the abandonment-prediction question (low quality_score predicting the next-step drop) by making 'no scan' look like 'worst possible scan'. user_id and booking_id both have 100% coverage in this feature's profile (unlike status_sharing or abandoned_checkout_recovery), so no partial_identity_columns / uniqIf guard is structurally required for those two -- but downstream aggregation on booking_id/user_id should still prefer uniqIf(x, x!='') defensively since default-string rows are indistinguishable from empty values in principle.
-- ttl: TTL toDateTime(timestamp) + INTERVAL 18 MONTH on the raw table, paired with the two rollup MVs (agg_deep_linear_funnel_daily, agg_deep_linear_auth_latency_daily) which are not subject to the same TTL, so month/quarter/year-over-year step-through-rate and auth-latency trend queries keep working on the aggregated fraction of bytes after raw rows expire.
-- mvs: Two MVs, both AggregatingMergeTree with uniqState/avgState/countState (never a bare count()/uniq() which the server rejects on AggregatingMergeTree, and never summing distinct counts across partitions). mv_deep_linear_funnel_daily serves the headline step-through/drop-off question at day x event x device_type x destination grain; mv_deep_linear_auth_latency_daily serves the auth-latency-by-device/destination and network-predicts-success questions pre-filtered to payment_authorized. At sample volume (3165 rows) both rollups look unnecessary, so projected annual volume (~3-4M raw rows/year at the observed events/booking ratio) is used to justify keeping them (>5x reduction each); actual keep/drop should be confirmed post-load via count() on source vs target as required by the keep/drop gate.
-- contrast_with_legacy: The 8 existing tables are one-table-per-event with ORDER BY (id, timestamp, user_id) and 30-35/33-38 Nullable columns -- instrumentation_notes.md calls this an SDK template artifact, not a design, and base_context.md confirms queries never filter by id. This proposal departs on all three axes for deep_linear: one wide table (all 8 booking steps, since every PM question is a within-feature funnel requiring shared-table windowFunnel, not a 5+-way join), event-first ordering (not id-first), and defaults instead of Nullable everywhere except the one column where absence is analytically distinct from zero.
-- generation_log: attempt 0: lint clean, dry run OK
-- order_by_measured_chosen_bytes: 139552
-- order_by_measured_straw_bytes: 139552
-- order_by_measured_ratio: 1.00
--
-- mv mv_deep_linear_funnel_daily: 3,165 -> 120 rows (26.4x) KEPT
-- mv mv_deep_linear_auth_latency_daily: 3,165 -> 15 rows (211.0x) KEPT

CREATE TABLE IF NOT EXISTS f_deep_linear_events
(
    `id` String COMMENT 'json_path=id; 32-char hex id, no dashes -- NOT UUID (existing tables'' UUID type would reject this literal)' CODEC(ZSTD(1)),
    `event` LowCardinality(String) COMMENT 'json_path=event; discriminator, 8 values',
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp' CODEC(Delta, ZSTD(1)),
    `booking_id` String COMMENT 'json_path=booking_id; entity key: 100% coverage, 560 distinct, present on 8/8 event types' CODEC(ZSTD(1)),
    `user_id` String COMMENT 'json_path=user_id; 100% coverage, 340 distinct; secondary key' CODEC(ZSTD(1)),
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib',
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type',
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination; 100% coverage, 5 distinct; carried on every step, not just itinerary_viewed',
    `slot_window` LowCardinality(String) DEFAULT '' COMMENT 'json_path=slot_window; slot_selected only, 15.7% coverage -- event-scoped, becomes a long default run under event-first ordering',
    `document_kind` LowCardinality(String) DEFAULT '' COMMENT 'json_path=document.kind; document_uploaded only, 12.8% coverage',
    `document_scan_quality_score` Nullable(Float64) COMMENT 'json_path=document.scan.quality_score; genuinely tri-state: a real low score (e.g. 0.02) is analytically distinct from ''no scan attempted''; coalescing to 0 would conflate them for the abandonment-prediction question. Only 12.8% coverage (document_uploaded rows) -- listed in partial_identity_columns is not needed since this isn''t an identity col, but flagged as a data-quality caveat.',
    `document_scan_page_count` UInt8 DEFAULT 0 COMMENT 'json_path=document.scan.page_count; count-like, small int fits UInt8',
    `insurance_tier` LowCardinality(String) DEFAULT '' COMMENT 'json_path=insurance_tier; insurance_offered only, 12.1% coverage, 3 values',
    `payment_method` LowCardinality(String) DEFAULT '' COMMENT 'json_path=payment.method; payment_initiated only, 10.3% coverage',
    `payment_card_network` LowCardinality(String) DEFAULT '' COMMENT 'json_path=payment.card.network; flattened from nested payment.card object; PM question 2 needs this as a segment dim, not buried in a struct',
    `payment_card_issuer_country` LowCardinality(String) DEFAULT '' COMMENT 'json_path=payment.card.issuer_country',
    `payment_amount_minor` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=payment.amount_minor; currency-denominated, will be summed -- Decimal not Float64',
    `auth_latency_ms` UInt32 DEFAULT 0 COMMENT 'json_path=auth_latency_ms; payment_authorized only, 8.9% coverage; ms-scale latency fits UInt32'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, booking_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.8889;

CREATE TABLE IF NOT EXISTS agg_deep_linear_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, device_type, destination)
EMPTY AS
SELECT toDate(timestamp) AS day, event, device_type, destination, countState() AS events_state, uniqStateIf(booking_id, booking_id != '') AS bookings_state, uniqStateIf(user_id, user_id != '') AS users_state FROM f_deep_linear_events GROUP BY day, event, device_type, destination;

CREATE TABLE IF NOT EXISTS agg_deep_linear_auth_latency_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, device_type, destination, card_network)
EMPTY AS
SELECT toDate(timestamp) AS day, device_type, destination, payment_card_network AS card_network, avgState(auth_latency_ms) AS latency_avg_state, countState() AS auth_count_state FROM f_deep_linear_events WHERE event = 'payment_authorized' GROUP BY day, device_type, destination, card_network;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_deep_linear_funnel_daily
TO agg_deep_linear_funnel_daily AS
SELECT toDate(timestamp) AS day, event, device_type, destination, countState() AS events_state, uniqStateIf(booking_id, booking_id != '') AS bookings_state, uniqStateIf(user_id, user_id != '') AS users_state FROM f_deep_linear_events GROUP BY day, event, device_type, destination;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_deep_linear_auth_latency_daily
TO agg_deep_linear_auth_latency_daily AS
SELECT toDate(timestamp) AS day, device_type, destination, payment_card_network AS card_network, avgState(auth_latency_ms) AS latency_avg_state, countState() AS auth_count_state FROM f_deep_linear_events WHERE event = 'payment_authorized' GROUP BY day, device_type, destination, card_network;
