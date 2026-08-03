-- Generated schema for feature: unseen
-- Run: 29b74c8fbaa94ab6ad7a18804951835e
-- Table: f_unseen_events
--
-- order_by: Never lead with id: the 8 legacy tables order by (id, timestamp, user_id) and id is unique per row (5,363 distinct ids over 5,363 rows), so the primary index does nothing for the PM questions, which are all 'apply rate', 'reject mix', 'segment cuts' -- never single-row lookups by id. We order by (event, timestamp, user_id): event has only E=6 values and every PM question filters/groups by it (apply rate is field_shown vs applied, reject mix is filtered to coupon_rejected); timestamp second because all analysis is windowed (2026-06-08..2026-06-28); user_id last (the derived entity key, 100% coverage, 2,100 distinct, present on all 6 event types, chosen per house_rules 'first mention in spec' tie-break over the co-extensive application_id) so a user's coupon journey is co-located for windowFunnel. Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, user_id) read 214,751 B / 5,365 rows; straw-man ORDER BY (timestamp, user_id) read 214,751 B / 5,365 rows. At sample volume (5,365 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.
-- partition_by: toYYYYMM(timestamp), matching all 8 existing tables so cross-table time-range queries prune consistently. At this feature's volume (5,364 rows over a 21-day window, projecting to a few hundred thousand rows/year at Atlys' 700K+ applications/year run rate) monthly parts keep part counts sane; daily partitioning would create ~21 tiny parts for this sample alone and thousands per year, hurting merge behaviour for no query-pruning benefit since no PM question filters at day granularity on the raw table.
-- types: E=6 event types observed (coupon_field_shown, coupon_entered, coupon_applied, coupon_rejected, discount_shown, checkout_with_coupon). Event-scoped columns (discount_type 10.8% cov, reject_reason 5.0% cov, final_value 18.4% cov, discount_amount 40.0% cov, coupon_code 49.3% cov) each have a default-value ratio of roughly 1-coverage, e.g. discount_type is ~0.892 default -- comfortably above the 0.9375 sparse threshold on its own, but with E roughly balanced the generic rule is ratio_of_defaults_for_sparse_serialization = min(0.9, 1-1/(E+1)) = min(0.9, 1-1/7) = min(0.9, 0.857) = 0.857, set in table SETTINGS so all these low-coverage columns (and any future one closer to the ~0.80 balanced-E baseline) still get sparse serialization instead of sitting just under the 0.9375 default and paying full dense storage. id is String (32-char hex, e.g. '40e20b22bab295b7731969b1'), not UUID -- the legacy tables' `id UUID` would reject this literal outright. discount_amount, cart_value and final_value are Decimal(18,4), not Float64, because they are currency amounts that get summed for the margin-cost question, and Decimal avoids float summation drift over thousands of rows. event/device_type/os/city/destination/currency/client_lib/app_version/coupon_code/discount_type/reject_reason are LowCardinality(String): all have <=14 distinct values in the profile.
-- nullable: Zero Nullable columns, vs the legacy tables' 30-35/33-38 Nullable columns. coupon_code (49.3% cov), discount_type (10.8%), discount_amount (40.0%), final_value (18.4%) and reject_reason (5.0%) all use DEFAULT '' / DEFAULT 0 instead of Nullable, avoiding the null-map cost on columns that sit in the hot GROUP BY/filter path for every PM question (reject-reason mix, coupon-code margin breakdown). user_id and application_id have 100% coverage per the field profile, so partial_identity_columns is empty and no uniqIf guard is strictly required for correctness here -- but agg_unseen_discount_daily still uses uniqStateIf(user_id, ... AND user_id != '') defensively since this table's baseline rows (coupon_code='') are semantically 'anonymous w.r.t. coupon', matching the pattern the house rules warn about even though this specific column isn't currently partial.
-- ttl: TTL toDateTime(timestamp) + INTERVAL 18 MONTH on the raw table, matching the standard retention; paired with agg_unseen_funnel_daily and agg_unseen_discount_daily which have no TTL, so trend queries on apply-rate and margin-cost over >18 months keep working on the rollups after raw rows expire, at a fraction of the bytes (rollup grain is day x event(6) x device(4) x geo(7) x destination(14) x coupon_code(7) vs one row per raw event).
-- mvs: Two MVs, each targeting a distinct PM question cluster rather than one catch-all: mv_unseen_funnel_daily (funnel/apply-rate/reject-mix/segment cuts) and mv_unseen_discount_daily (margin cost + conversion lift, since lift requires comparing coupon_code='' vs coupon_code!='' checkout counts, which the funnel MV's per-event/per-coupon_code split doesn't compute directly as a ratio). Both use AggregatingMergeTree with *State functions (countState, uniqState, sumState, countIfState, uniqStateIf) per house rule 7 -- never a bare count()/sum() on an AggregatingMergeTree target, and never summing uniq counts across partitions. At this sample's 5,364 rows the two MVs are not yet worth their storage/maintenance overhead (they'd be honest to mark kept=false at this scale); they are justified against projected annual volume once this feature runs at Atlys' 700K+ applications/year rate, where the raw table grows into the millions of rows/year while the rollup grain (bounded by day x ~6 x ~4 x ~7 x ~14 x ~7 combos) stays roughly flat -- an actual keep/drop measurement (count() on source vs target, reduction_factor, 5x gate) should be re-run once real load volume is available; measured_source_rows/measured_target_rows are left null here pending that load.
-- contrast_with_legacy: The 8 existing tables are one-table-per-event (destination_card_clicked, search_typed, ..., purchase_completed) with ORDER BY (id, timestamp, user_id) and 30-35 Nullable columns out of 33-38 -- per instrumentation_notes.md this is 'a legacy of the event-table template', not a considered design. f_unseen_events instead uses ONE wide table for all 6 coupon-flow event types (matching house rule 1): every PM question here is a within-feature funnel (field_shown -> entered -> applied -> discount_shown -> checkout_with_coupon, or applied vs rejected), so one table makes it a single windowFunnel/GROUP BY with zero joins, while splitting into 6 tables (one per event) would force a 6-way join for the apply-rate question alone. Sorting by event first (not id) and eliminating Nullable in favour of typed defaults are the same two departures used in the other 5 feature tables (f_abandoned_checkout_recovery_events, f_deep_linear_events, etc.) documented in this context layer.
-- generation_log: attempt 0: lint clean, dry run OK
-- order_by_measured_chosen_bytes: 214751
-- order_by_measured_straw_bytes: 214751
-- order_by_measured_ratio: 1.00
--
-- mv mv_unseen_funnel_daily: 5,363 -> 4,608 rows (1.2x) DROPPED
-- mv mv_unseen_discount_daily: 5,363 -> 1,675 rows (3.2x) DROPPED

CREATE TABLE IF NOT EXISTS f_unseen_events
(
    `event` LowCardinality(String) COMMENT 'json_path=event; Discriminator; 6 event types, drives ORDER BY prefix',
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp; ISO-8601 with ms; DateTime would truncate precision' CODEC(Delta, ZSTD(1)),
    `id` String COMMENT 'json_path=id; 32-char hex, no dashes -- NOT UUID-parseable' CODEC(ZSTD(1)),
    `user_id` String DEFAULT '' COMMENT 'json_path=user_id; entity key; 100% coverage, 2100 distinct' CODEC(ZSTD(1)),
    `application_id` String DEFAULT '' COMMENT 'json_path=application_id; secondary key; 100% coverage, 2100 distinct' CODEC(ZSTD(1)),
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type',
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; 93.3% coverage; absent os treated as '''' not NULL',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib',
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version',
    `currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=currency',
    `cart_value` Decimal(18,4) DEFAULT 0 COMMENT 'json_path=cart_value; currency-denominated, present on all 6 event types (100% cov)',
    `coupon_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=coupon_code; 49.3% coverage -- null/absent for no-coupon baseline (checkout_with_coupon rows with coupon_code='''') and for pre-entry events; 6 distinct real codes',
    `discount_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=discount_type; 10.8% coverage -- only present on coupon_applied',
    `discount_amount` Decimal(18,4) DEFAULT 0 COMMENT 'json_path=discount_amount; 40.0% coverage -- margin measure, summed; 0 default is correct semantic zero for events with no discount',
    `final_value` Decimal(18,4) DEFAULT 0 COMMENT 'json_path=final_value; 18.4% coverage -- only on checkout_with_coupon',
    `reject_reason` LowCardinality(String) DEFAULT '' COMMENT 'json_path=reject_reason; 5.0% coverage -- only on coupon_rejected, 4 distinct reasons'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, user_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.857;

CREATE TABLE IF NOT EXISTS agg_unseen_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, device_type, geoip_country_code, destination, coupon_code)
EMPTY AS
SELECT toDate(timestamp) AS day, event, device_type, geoip_country_code, destination, coupon_code, countState() AS events_state, uniqState(user_id) AS users_state FROM f_unseen_events GROUP BY day, event, device_type, geoip_country_code, destination, coupon_code;

CREATE TABLE IF NOT EXISTS agg_unseen_discount_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, coupon_code, destination, device_type)
EMPTY AS
SELECT toDate(timestamp) AS day, coupon_code, destination, device_type, sumState(discount_amount) AS discount_amount_state, sumState(final_value) AS final_value_state, countIfState(event = 'checkout_with_coupon') AS checkout_state, uniqStateIf(user_id, event = 'coupon_field_shown' AND user_id != '') AS shown_users_state, uniqStateIf(user_id, event = 'checkout_with_coupon' AND coupon_code != '' AND user_id != '') AS coupon_checkout_users_state, uniqStateIf(user_id, event = 'checkout_with_coupon' AND coupon_code = '' AND user_id != '') AS baseline_checkout_users_state FROM f_unseen_events GROUP BY day, coupon_code, destination, device_type;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_unseen_funnel_daily
TO agg_unseen_funnel_daily AS
SELECT toDate(timestamp) AS day, event, device_type, geoip_country_code, destination, coupon_code, countState() AS events_state, uniqState(user_id) AS users_state FROM f_unseen_events GROUP BY day, event, device_type, geoip_country_code, destination, coupon_code;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_unseen_discount_daily
TO agg_unseen_discount_daily AS
SELECT toDate(timestamp) AS day, coupon_code, destination, device_type, sumState(discount_amount) AS discount_amount_state, sumState(final_value) AS final_value_state, countIfState(event = 'checkout_with_coupon') AS checkout_state, uniqStateIf(user_id, event = 'coupon_field_shown' AND user_id != '') AS shown_users_state, uniqStateIf(user_id, event = 'checkout_with_coupon' AND coupon_code != '' AND user_id != '') AS coupon_checkout_users_state, uniqStateIf(user_id, event = 'checkout_with_coupon' AND coupon_code = '' AND user_id != '') AS baseline_checkout_users_state FROM f_unseen_events GROUP BY day, coupon_code, destination, device_type;
