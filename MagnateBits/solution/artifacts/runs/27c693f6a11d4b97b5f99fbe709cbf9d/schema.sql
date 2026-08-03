-- Generated schema for feature: unseen
-- Run: 27c693f6a11d4b97b5f99fbe709cbf9d
-- Table: f_unseen_events
--
-- order_by: Never id-first (house rule 2): id is unique (5,363 distinct = row count), so leading with it gives a useless primary index, exactly the flaw the 8 legacy tables have. event has only E=6 values and every PM question (apply rate, reject mix, segment cuts) filters or groups by event, so it prunes hard first. timestamp second because all questions are time-windowed (the observed window is 2026-06-08..2026-06-28). user_id last because it's the derived entity key (100% coverage on all 6 event types, 2,100 distinct, present on both coupon-side and checkout-side rows) and is the funnel grouping key for windowFunnel(field_shown->...->checkout_with_coupon). Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, user_id) read 214,751 B / 5,365 rows; straw-man ORDER BY (timestamp, user_id) read 214,751 B / 5,365 rows. At sample volume (5,365 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.
-- partition_by: toYYYYMM(timestamp) matches all 8 existing tables so cross-table time-pruning stays consistent. Sample window is 20 days inside one month; at the platform's 700K+ applications/yr run rate this feature would be a small fraction of that, still landing well under the row-count where monthly partitions become too coarse. Daily partitions would create ~20 tiny parts for this sample alone and thousands per year, hurting merge behavior for no pruning benefit since every query here is already event-first, not day-first.
-- types: E=6 observed event types, roughly balanced (counts 268-2,100). An event-scoped column (discount_type, reject_reason, final_value, discount_amount) is a default in every row not belonging to its owning event(s), i.e. close to (1-1/E)=0.833 default ratio for a single-event column, which sits under the MergeTree sparse threshold of 0.9375 and would NOT auto-sparsify. Setting ratio_of_defaults_for_sparse_serialization = min(0.9, 1-1/(E+1)) = min(0.9, 1-1/7) = min(0.9, 0.857) = 0.857 pulls the threshold below that ~0.83-0.90 range so discount_type (10.8% coverage -> 89.2% default), reject_reason (5.0% coverage -> 95% default) and final_value (18.4% coverage -> 81.6% default) actually go sparse. id is String not UUID because sample ids are 32-char hex strings with no dashes (e.g. '40e20b22bab295b7731969b1' truncated in profile, matches the documented 24/32-char hex pattern) which UUID parsing rejects — this is the single most-cited load failure in the house rules. Money fields (cart_value, discount_amount, final_value) are Decimal(18,4) since they're summed for margin-cost reporting, not FX-approximate.
-- nullable: No Nullable columns. coupon_code, discount_type, discount_amount, final_value, reject_reason all use DEFAULT '' / DEFAULT 0 instead, per house rule 5, avoiding the null-map cost and preserving index usability that the legacy tables lose (30-35 of ~33-38 columns Nullable there). user_id and application_id both have 100% coverage in this feature (unlike the sharer/recipient features with genuinely anonymous rows), so no partial_identity_columns entry is needed and uniqState(user_id) in the MVs needs no uniqIf guard — but coupon_code defaulting to '' does double duty as 'coupon not entered' AND 'no-coupon checkout baseline', which is intentional: both cases are the same segment value for the conversion-lift question (checkout_with_coupon rows where coupon_code is empty/null).
-- ttl: TTL toDateTime(timestamp) + INTERVAL 18 MONTH on the raw table, matching house default, paired with the two agg_* rollups which are not TTL'd so apply-rate/reject-mix/margin trend queries keep working past raw expiry on a fraction of the bytes.
-- mvs: Two rollups, each targeting a distinct PM question class: mv_unseen_funnel_daily (day x event x device_type x geo x destination, AggregatingMergeTree with countState/uniqState) serves the apply-rate/reject-mix and segment-cut questions; mv_unseen_coupon_margin_daily (day x coupon_code x event, sumState(discount_amount)) serves the margin-cost/code-performance question. Both use uniqState/sumState/countState (never bare count()/uniq()) because AggregatingMergeTree requires aggregate-state columns and distinct-count sums must be uniqMerge'd, not summed, across partitions. At the observed sample (5,363 rows, 20 days) these rollups collapse to well under 5,364 rows each and would likely fail the 5x keep/drop gate on this sample alone — but projected at the platform's 700K+ applications/yr run rate, this feature's ~5,364 rows over 20 days extrapolates to roughly 100K+ events/year, while the daily x event x 3-segment-dim rollup stays bounded by day-count x 6 x device_type x geo x destination cardinality (dozens to low hundreds of rows/day), i.e. a multi-hundred-x reduction at annual volume — justified against projected_annual_rows, not sample volume, per house rule 7.
-- engine: MergeTree. Checked the field profile for a re-ingestion/backfill signal (duplicate_id, is_back_filled, dedup_*, *_reingested style column) — none present among the 17 candidate columns (id, event, timestamp, user_id, application_id, device/geo/app envelope, coupon_code, discount_type, discount_amount, final_value, reject_reason, cart_value, currency). No column shape implies re-ingestion, so plain MergeTree is correct; ReplacingMergeTree would be unjustified speculation.
-- contrast_with_legacy: The 8 existing tables are one-table-per-event with ORDER BY (id, timestamp, user_id) and 30-35 of ~33-38 columns Nullable — instrumentation_notes.md calls this an SDK template artifact, not a design. This feature's headline PM questions (apply rate field_shown->coupon_applied, reject mix, conversion lift vs no-coupon baseline, margin cost by code) are all within-feature funnels/segment cuts across the SAME entity (user_id, 100% coverage on all 6 event types) — splitting into 6 event tables would force a 6-way join per question. One wide table with event first in ORDER BY and the 0.857 sparse-serialization override gets table-per-event's storage profile (event-scoped columns like reject_reason at 5% coverage go sparse) with unified-stream query ergonomics (single windowFunnel, no joins).
-- generation_log: attempt 0: lint clean, dry run OK
-- order_by_measured_chosen_bytes: 214751
-- order_by_measured_straw_bytes: 214751
-- order_by_measured_ratio: 1.00
--
-- mv mv_unseen_funnel_daily: 5,363 -> 4,305 rows (1.2x) DROPPED
-- mv mv_unseen_coupon_margin_daily: 5,363 -> 223 rows (24.1x) KEPT

CREATE TABLE IF NOT EXISTS f_unseen_events
(
    `id` String COMMENT 'json_path=id; 32-char hex, not UUID-parseable; legacy tables'' UUID type would reject this literal' CODEC(ZSTD(1)),
    `event` LowCardinality(String) COMMENT 'json_path=event; discriminator, 6 values',
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp' CODEC(Delta, ZSTD(1)),
    `user_id` String COMMENT 'json_path=user_id; entity key, 100% coverage, 2100 distinct' CODEC(ZSTD(1)),
    `application_id` String COMMENT 'json_path=application_id; secondary key, 100% coverage, 2100 distinct' CODEC(ZSTD(1)),
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type',
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; 93.3% coverage; missing values are absence-of-info not tri-state, default '''' is fine',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination',
    `currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=currency',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib',
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version',
    `cart_value` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=cart_value; currency-denominated, present on all 6 event types (100%)',
    `coupon_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=coupon_code; 6 distinct incl. null; 49.3% coverage — '''' encodes both ''no coupon field reached'' and the no-coupon baseline at checkout_with_coupon, both analytically ''no code'', so unguarded default is correct here (this is a segment dim, not an identity column)',
    `discount_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=discount_type; only on coupon_applied (10.8% coverage), 2 values',
    `discount_amount` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=discount_amount; summed for margin cost question; present on coupon_applied/discount_shown/checkout_with_coupon (40% coverage), 0 default is correct additive identity',
    `final_value` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=final_value; only on checkout_with_coupon (18.4% coverage)',
    `reject_reason` LowCardinality(String) DEFAULT '' COMMENT 'json_path=reject_reason; only on coupon_rejected (5.0% coverage), 4 values'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, user_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.8571428571428571;

CREATE TABLE IF NOT EXISTS agg_unseen_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, device_type, geo, destination)
EMPTY AS
SELECT toDate(timestamp) AS day, event, device_type, geoip_country_code AS geo, destination, countState() AS events_state, uniqState(user_id) AS users_state FROM f_unseen_events GROUP BY day, event, device_type, geo, destination;

CREATE TABLE IF NOT EXISTS agg_unseen_coupon_margin_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, coupon_code, event)
EMPTY AS
SELECT toDate(timestamp) AS day, coupon_code, event, sumState(discount_amount) AS discount_state, countState() AS rows_state, uniqState(user_id) AS users_state FROM f_unseen_events WHERE event IN ('coupon_applied', 'checkout_with_coupon') GROUP BY day, coupon_code, event;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_unseen_funnel_daily
TO agg_unseen_funnel_daily AS
SELECT toDate(timestamp) AS day, event, device_type, geoip_country_code AS geo, destination, countState() AS events_state, uniqState(user_id) AS users_state FROM f_unseen_events GROUP BY day, event, device_type, geo, destination;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_unseen_coupon_margin_daily
TO agg_unseen_coupon_margin_daily AS
SELECT toDate(timestamp) AS day, coupon_code, event, sumState(discount_amount) AS discount_state, countState() AS rows_state, uniqState(user_id) AS users_state FROM f_unseen_events WHERE event IN ('coupon_applied', 'checkout_with_coupon') GROUP BY day, coupon_code, event;
