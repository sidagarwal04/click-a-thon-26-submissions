-- Generated schema for feature: unseen
-- Run: 7c1cabbe53f4459e92b1916b877875de
-- Table: f_unseen_events
--
-- order_by: Legacy tables lead with (id, timestamp, user_id) but id is unique per row (5,363 distinct ids, 1 row each) so the primary index never prunes on it -- every listed PM question ('apply rate', 'reject mix', 'conversion lift', 'segment cuts') filters/groups by event and time, never by id. ORDER BY (event, timestamp, user_id) puts the 6-value LowCardinality event column first (hard pruning + clusters each event type's sparse columns contiguously), timestamp second (all analysis is windowed, e.g. the 2026-06-08..2026-06-28 observation window), and user_id last since it is the derived entity key (100% coverage, 2,100 distinct values, present on all 6 event types, needed for the coupon-vs-baseline conversion-lift funnel). Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, user_id) read 214,751 B / 5,365 rows; straw-man ORDER BY (timestamp, user_id) read 214,751 B / 5,365 rows. At sample volume (5,365 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.
-- partition_by: toYYYYMM(timestamp) matches all 8 existing tables so cross-table segment joins (device_type/geo/destination) prune consistently on the same partition boundary. At 5,363 rows over a 3-week window (and even at the 700K/yr platform run-rate scaled to this feature's share), monthly parts keep part counts low; daily partitioning at this volume would produce mostly-empty parts and slow background merges for no pruning benefit.
-- types: E=6 event types observed. An event-scoped column (e.g. discount_type, present only on coupon_applied = 580/5,363 = 10.8% coverage; reject_reason present only on coupon_rejected = 5.0%; final_value only on checkout_with_coupon = 18.4%) is default-valued on the other ~5/6 of rows -- roughly (1-1/6)=0.833 or higher for the narrowest columns, comfortably past the 0.9375 sparse threshold on its own, but the *general* per-event-column default ratio for a roughly-balanced E=6 feature is (1-1/6)=0.833, which sits BELOW the default 0.9375 threshold and would NOT auto-sparsify. Per house rule 1, set ratio_of_defaults_for_sparse_serialization = min(0.9, 1-1/(E+1)) = min(0.9, 1-1/7) = min(0.9, 0.857) = 0.857, so these event-scoped columns (0.833-0.95 default ratio) correctly go sparse. id is String (32-char hex, no dashes) not UUID, since the profile shows raw values like '40e20b22bab295b7731969b1' which UUID parsing rejects. coupon_code has only 6 distinct values (ATLYS15, FREESHIP, FIRST10, WELCOME, +2 more) despite 49.3% null coverage, so LowCardinality(String), not a high-cardinality id type. cart_value/discount_amount/final_value are Decimal(18,4) because they are summed for margin-cost reporting, not approximate.
-- nullable: No column is Nullable. Legacy tables make 30-35 of ~33-38 columns Nullable (per the profile, e.g. 32/35, 30/33); we replace that with DEFAULT '' / DEFAULT 0 across the board, including on coupon_code (49.3% coverage), discount_type (10.8%), reject_reason (5.0%) and final_value (18.4%) -- these are structurally event-scoped, not genuinely tri-state, so a null map would just waste space that the sparse-serialization setting already reclaims. user_id has 100% coverage on this feature (no anonymous/recipient-side events, unlike status_sharing), so it needs no uniqIf guard and partial_identity_columns is empty -- still, any downstream distinct-user query should default to uniqIf(user_id, user_id != '') as house policy since coupon_code-scoped segments could otherwise be miscounted against ''.
-- ttl: TTL toDateTime(timestamp) + INTERVAL 18 MONTH on the raw table, matching house default. Paired with the two rollup MVs (agg_unseen_funnel_daily, agg_unseen_discount_daily) which are not raw copies and are retained independently, so daily apply-rate/margin trend queries beyond 18 months keep working on the aggregated state after raw rows expire.
-- mvs: Both MVs are daily x segment/event or daily x coupon_code aggregates using AggregatingMergeTree + *State functions (countState, uniqState, uniqStateIf, sumState) per house rule 7 -- never bare count()/uniq() into a summing target, since distinct-user counts cannot be summed across partitions. mv_unseen_funnel_daily answers apply-rate and reject-reason-mix and segment cuts (device/geo/destination) in one pass; mv_unseen_discount_daily answers margin cost (sum discount_amount by code) and conversion lift (uniqStateIf checkout users split by coupon_code='' baseline vs coupon present) in one pass. At the observed 5,363-row sample the reduction factor will look thin (rows collapse mainly by day x low-cardinality segment, e.g. up to 21 days x 6 events x 4 devices x 14 destinations = worst case a few thousand groups), so per house rule 7's keep/drop gate this must be measured post-load against measured_source_rows/measured_target_rows and re-justified against the platform's 700K/yr run-rate projection, not the 3-week sample -- if reduction_factor < 5x here, kept must be set to false and recorded honestly rather than kept on faith.
-- engine: Checked the field profile for a re-ingestion/backfill signal (duplicate_id, is_back_filled, dedup_*, *_reingested or similar) across all 19 candidate columns -- none present. Using plain MergeTree, not ReplacingMergeTree; no evidence of duplicate/backfilled rows in this feature's event shape.
-- contrast_with_legacy: The 8 existing tables are one-table-per-event with id-first ORDER BY and ~90% Nullable columns (instrumentation_notes.md: 'legacy of the event-table template'). f_unseen_events instead is one wide table spanning all 6 coupon-checkout event types (matching house rule 1's within-feature-funnel rationale: windowFunnel(coupon_field_shown->coupon_entered->coupon_applied->discount_shown->checkout_with_coupon) is a single scan here, not a 6-way join), leads ORDER BY with the 6-value `event` column instead of the unique `id` (which the legacy tables index first despite queries never filtering by id per base_context.md), uses String not UUID for id (the raw id is 32-char hex without dashes, which UUID would reject at load), and replaces near-universal Nullable with DEFAULT ''/0 plus an explicit sparse-serialization setting (0.857, derived from E=6) so the same storage efficiency Nullable was approximating is achieved without the null-map index cost.
-- generation_log: attempt 0: lint clean, dry run OK
-- order_by_measured_chosen_bytes: 214751
-- order_by_measured_straw_bytes: 214751
-- order_by_measured_ratio: 1.00
--
-- mv mv_unseen_funnel_daily: 5,363 -> 4,305 rows (1.2x) DROPPED
-- mv mv_unseen_discount_daily: 5,363 -> 1,675 rows (3.2x) DROPPED

CREATE TABLE IF NOT EXISTS f_unseen_events
(
    `id` String COMMENT 'json_path=id; 32-char hex, no dashes -- not UUID-castable, unlike legacy tables'' UUID id' CODEC(ZSTD(1)),
    `event` LowCardinality(String) COMMENT 'json_path=event',
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp' CODEC(Delta, ZSTD(1)),
    `user_id` String COMMENT 'json_path=user_id; entity key; 100% coverage across all 6 event types' CODEC(ZSTD(1)),
    `application_id` String DEFAULT '' COMMENT 'json_path=application_id' CODEC(ZSTD(1)),
    `device_type` LowCardinality(String) COMMENT 'json_path=device_type',
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; 93.3% coverage, not tri-state analytically -- treat missing as unknown/empty, not NULL',
    `geoip_country_code` LowCardinality(String) COMMENT 'json_path=geoip_country_code',
    `city` LowCardinality(String) COMMENT 'json_path=city',
    `destination` LowCardinality(String) COMMENT 'json_path=destination',
    `client_lib` LowCardinality(String) COMMENT 'json_path=client_lib',
    `app_version` LowCardinality(String) COMMENT 'json_path=app_version',
    `cart_value` Decimal(18,4) DEFAULT 0 COMMENT 'json_path=cart_value; currency-denominated, summed for margin/segment analysis',
    `currency` LowCardinality(String) COMMENT 'json_path=currency',
    `coupon_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=coupon_code; 49.3% coverage (null=no-coupon baseline); only 6 distinct values -- LowCardinality, not high-cardinality id',
    `discount_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=discount_type; 10.8% coverage -- only present on coupon_applied by construction, not a data gap',
    `discount_amount` Decimal(18,4) DEFAULT 0 COMMENT 'json_path=discount_amount; money, summed for margin cost question',
    `reject_reason` LowCardinality(String) DEFAULT '' COMMENT 'json_path=reject_reason; 5.0% coverage -- only present on coupon_rejected by construction',
    `final_value` Decimal(18,4) DEFAULT 0 COMMENT 'json_path=final_value; money, only present on checkout_with_coupon'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, user_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.857;

CREATE TABLE IF NOT EXISTS agg_unseen_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, device_type, destination, geoip_country_code)
EMPTY AS
SELECT toDate(timestamp) AS day, event AS event, device_type AS device_type, destination AS destination, geoip_country_code AS geoip_country_code, countState() AS events_state, uniqState(user_id) AS users_state FROM f_unseen_events GROUP BY day, event, device_type, destination, geoip_country_code;

CREATE TABLE IF NOT EXISTS agg_unseen_discount_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, coupon_code, device_type, destination)
EMPTY AS
SELECT toDate(timestamp) AS day, coupon_code AS coupon_code, device_type AS device_type, destination AS destination, sumState(discount_amount) AS discount_amount_state, sumState(final_value) AS final_value_state, uniqStateIf(user_id, event = 'checkout_with_coupon' AND coupon_code != '') AS coupon_checkout_users_state, uniqStateIf(user_id, event = 'checkout_with_coupon' AND coupon_code = '') AS baseline_checkout_users_state, countStateIf(event = 'checkout_with_coupon') AS checkout_events_state FROM f_unseen_events GROUP BY day, coupon_code, device_type, destination;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_unseen_funnel_daily
TO agg_unseen_funnel_daily AS
SELECT toDate(timestamp) AS day, event AS event, device_type AS device_type, destination AS destination, geoip_country_code AS geoip_country_code, countState() AS events_state, uniqState(user_id) AS users_state FROM f_unseen_events GROUP BY day, event, device_type, destination, geoip_country_code;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_unseen_discount_daily
TO agg_unseen_discount_daily AS
SELECT toDate(timestamp) AS day, coupon_code AS coupon_code, device_type AS device_type, destination AS destination, sumState(discount_amount) AS discount_amount_state, sumState(final_value) AS final_value_state, uniqStateIf(user_id, event = 'checkout_with_coupon' AND coupon_code != '') AS coupon_checkout_users_state, uniqStateIf(user_id, event = 'checkout_with_coupon' AND coupon_code = '') AS baseline_checkout_users_state, countStateIf(event = 'checkout_with_coupon') AS checkout_events_state FROM f_unseen_events GROUP BY day, coupon_code, device_type, destination;
