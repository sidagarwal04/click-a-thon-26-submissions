-- Generated schema for feature: unseen
-- Run: 769dc10533d94f7d8eebf03270037342
-- Table: f_unseen_events
--
-- order_by: Never lead with id (5,363 distinct, one row each -- useless for pruning). event first: E=6 event types, and every PM question (apply rate, reject mix, conversion lift, margin, segment cuts) filters or groups by event, so it prunes hard and each event type's specific columns (discount_type, reject_reason, final_value) cluster into contiguous runs. timestamp second: all questions are window-scoped ('did coupon users convert higher... over the observed window'). user_id last: it is the derived entity key (100% coverage on all 6 event types, 2,100 distinct, chosen over the co-extensive application_id by spec-mention order per house rule 2) and is the funnel grouping key for windowFunnel(coupon_field_shown->...->checkout_with_coupon). Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, user_id) read 214,751 B / 5,365 rows; straw-man ORDER BY (timestamp, user_id) read 214,751 B / 5,365 rows. At sample volume (5,365 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.
-- partition_by: toYYYYMM(timestamp) matches all 8 existing tables and the other 5 feature tables so cross-table/cross-feature time-window queries prune consistently. The window here is only 2026-06-08..06-28 (3 weeks, 5,364 rows) -- daily partitions would produce ~20 near-empty parts for a table this small and would only get worse at Atlys run-rate; monthly keeps merges cheap without sacrificing prune granularity for month-scale PM questions.
-- types: E=6 observed event types (coupon_field_shown, coupon_entered, coupon_applied, coupon_rejected, discount_shown, checkout_with_coupon), roughly balanced (2100/848/580/268/580/987). An event-scoped column (e.g. discount_type, present only on coupon_applied) is a default on ~(1-1/6)=0.833 of rows -- under the 0.9375 sparse threshold, so it would NOT auto-sparsify. Setting ratio_of_defaults_for_sparse_serialization = min(0.9, 1-1/(E+1)) = min(0.9, 1-1/7) = min(0.9, 0.857) = 0.857 forces sparse serialization for these event-scoped columns (discount_type 10.8% coverage, reject_reason 5.0%, final_value 18.4%, discount_amount/coupon_code ~40-49%), all comfortably above the 0.857 default-ratio bar once event-clustered by the sort key. id kept as String (32-char hex, no dashes) not UUID -- UUID parsing would reject the raw literal, the single most likely load failure per house rules. cart_value/discount_amount/final_value are Decimal(18,4) since they are summed currency amounts feeding the margin-cost question, not approximate FX-style floats.
-- nullable: No Nullable columns. coupon_code, discount_type, discount_amount, final_value, reject_reason, os all have <100% coverage (49.3%, 10.8%, 40%, 18.4%, 5.0%, 93.3% respectively) but each is DEFAULT ''/0 instead of Nullable per house rule 5 -- these are hot group-by/filter columns (coupon_code segments the margin-cost question, reject_reason segments the reject-mix question) and Nullable would add a null-map and weaken index usage. Critically, coupon_code='' is not noise here: it is the explicit no-coupon-baseline marker the PM's conversion-lift question needs (rows where coupon_code is null in the spec). Because user_id and application_id are both 100% covered on all 6 event types, there is no anonymous-event trap for this feature -- partial_identity_columns is empty -- but any identity aggregation should still use uniqIf(user_id, user_id != '') defensively rather than bare uniq(), which the funnel MV does via uniqStateIf.
-- ttl: TTL toDateTime(timestamp) + INTERVAL 18 MONTH on the raw table, paired with agg_unseen_funnel_daily which has no TTL (or a much longer one) so day-level apply-rate/margin/segment trend queries keep working past raw expiry on a fraction of the bytes -- this pairing is what justifies keeping the MV rather than treating it as a throwaway copy.
-- mvs: One rollup, mv_unseen_funnel_daily -> agg_unseen_funnel_daily (AggregatingMergeTree), grouped by day/event/device_type/geoip_country_code/destination/coupon_code with countState/uniqStateIf/sumState. It directly answers 3 of the 4 PM questions (apply rate & reject mix, margin cost by code, segment cuts) at day-grain instead of scanning raw rows. At the observed sample (5,363 rows over 3 weeks) the reduction factor will look modest -- keep/drop must be measured post-load per house rule 7 (report as mv_status_unseen_funnel_daily: X -> Y rows (Zx) KEPT/DROPPED) -- but the MV is justified against projected_annual_rows: at Atlys's 700K+ applications/yr run-rate, a comparably-shaped checkout-adjacent feature implies low-millions of raw rows/yr, where a day x event x 4-segment rollup is easily >5x smaller. A second MV (e.g. per-code performance) was considered but coupon_code is already a GROUP BY dimension in this one rollup, so a separate table would be a near-duplicate with no new pruning benefit -- not proposed, per house rule 7's guidance against reflexive MVs.
-- engine: Checked all 19 field-profile columns for a re-ingestion/backfill signal (duplicate_id, is_back_filled, dedup_*, *_reingested, or similar) -- none present in the observed events (id is a plain per-event hex string, no versioning/backfill column). Using plain MergeTree; no ReplacingMergeTree needed.
-- contrast_with_legacy: The 8 existing tables are one-table-per-event with ORDER BY (id, timestamp, user_id) and 30-35/33-38 Nullable columns -- instrumentation_notes.md calls this an SDK template artifact, not a design. This feature's 6 event types share one envelope (device_type, os, geoip_country_code, city, destination, client_lib, app_version, user_id, application_id all at 100% coverage across all 6 types) and every PM question is a within-feature funnel (field_shown->entered->applied->discount_shown->checkout_with_coupon, plus the mutually-exclusive coupon_rejected branch confirmed by 0% entity overlap with checkout_with_coupon/coupon_applied/discount_shown). Splitting into 6 tables would turn every apply-rate or conversion-lift question into a 5-6-way join; one wide table with event-first sort and sparse-serialization tuned for E=6 gets table-per-event storage economics (0.857 default-ratio columns go sparse) with single-windowFunnel query economics.
-- generation_log: attempt 0: lint clean, dry run OK
-- order_by_measured_chosen_bytes: 214751
-- order_by_measured_straw_bytes: 214751
-- order_by_measured_ratio: 1.00
--
-- mv mv_unseen_funnel_daily: 5,363 -> 4,608 rows (1.2x) DROPPED

CREATE TABLE IF NOT EXISTS f_unseen_events
(
    `id` String COMMENT 'json_path=id; 32-char hex string, not UUID-parseable; existing tables'' UUID type would reject this literal' CODEC(ZSTD(1)),
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp' CODEC(Delta, ZSTD(1)),
    `event` LowCardinality(String) COMMENT 'json_path=event',
    `user_id` String COMMENT 'json_path=user_id; entity key; 100% coverage, 2100 distinct' CODEC(ZSTD(1)),
    `application_id` String DEFAULT '' COMMENT 'json_path=application_id; secondary key; 100% coverage' CODEC(ZSTD(1)),
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type',
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; 93.3% coverage; missing collapsed to '''' rather than Nullable per house rule 5',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib',
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version; only 3 distinct values',
    `currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=currency',
    `cart_value` Decimal(18,4) DEFAULT 0 COMMENT 'json_path=cart_value; currency-denominated, summed for cart totals',
    `coupon_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=coupon_code; only 6 distinct codes incl. null->'''' for no-coupon baseline rows (coupon_code coverage 0.493); '''' is the explicit baseline marker used in conversion-lift queries, so keep as default not Nullable',
    `discount_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=discount_type; percent/flat, only present on coupon_applied (10.8% coverage)',
    `discount_amount` Decimal(18,4) DEFAULT 0 COMMENT 'json_path=discount_amount; margin-cost measure, summed; present on checkout_with_coupon/coupon_applied/discount_shown (40% coverage), 0 default is correct additive identity',
    `final_value` Decimal(18,4) DEFAULT 0 COMMENT 'json_path=final_value; post-discount price, only on checkout_with_coupon (18.4% coverage)',
    `reject_reason` LowCardinality(String) DEFAULT '' COMMENT 'json_path=reject_reason; 4 enum values, only on coupon_rejected (5% coverage)'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, user_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.857143;

CREATE TABLE IF NOT EXISTS agg_unseen_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, device_type, geoip_country_code, destination, coupon_code)
EMPTY AS
SELECT toDate(timestamp) AS day, event, device_type, geoip_country_code, destination, coupon_code, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state, sumState(discount_amount) AS discount_amount_state, sumState(cart_value) AS cart_value_state, sumState(final_value) AS final_value_state FROM atlys.f_unseen_events GROUP BY day, event, device_type, geoip_country_code, destination, coupon_code;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_unseen_funnel_daily
TO agg_unseen_funnel_daily AS
SELECT toDate(timestamp) AS day, event, device_type, geoip_country_code, destination, coupon_code, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state, sumState(discount_amount) AS discount_amount_state, sumState(cart_value) AS cart_value_state, sumState(final_value) AS final_value_state FROM atlys.f_unseen_events GROUP BY day, event, device_type, geoip_country_code, destination, coupon_code;
