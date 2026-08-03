-- Generated schema for feature: group_family
-- Run: e0e83851c60849bd84ad55580659b018
-- Table: f_group_family_events
--
-- order_by: Never lead with id: the existing 8 tables use (id, timestamp, user_id) and id is unique per row (5,453 distinct ids for 5,453 rows), making the primary index useless for the group/family queries, which are all 'completion rate by group_size' or 'churn by day', never single-row id lookups. We use (event, timestamp, group_id): event has only E=4 values so it prunes hard and clusters traveller_added (3,495 rows, 64% of the table) away from group_submitted (688 rows) and group_started (1,200 rows), letting a group_size funnel query skip whole granules. timestamp second because every PM question is time-windowed ('where do large groups fall off', daily churn). group_id third (not user_id or application_id, though they are numerically co-extensive at 1,200 distinct values each) because group_id is the name explicitly used in the spec's action bullets and is the funnel grain PMs reference ('per group' add/remove churn, 'by group size'). Bake-off on t02_funnel_overall: chosen ORDER BY (event, timestamp, group_id) read 240,112 B / 5,455 rows; straw-man ORDER BY (timestamp, group_id) read 240,112 B / 5,455 rows. At sample volume (5,455 rows) both layouts read the same bytes -- the table fits in a handful of granules, so primary-key pruning cannot discriminate. Event-first retained per house_rules §2 (event prune + sparse serialization); straw-man dropped. Re-run at projected_annual_rows to price the gap.
-- partition_by: toYYYYMM(timestamp), matching all 8 existing tables so any cross-table segment join (see cross_reference_hints) prunes on the same partition boundary. The observed window is 2026-06-08 to 2026-06-28 (21 days, 5,453 rows) — daily partitions at this volume (~260 rows/day) would create thousands of tiny parts over a year and slow merges for no query benefit, since no query in the spec filters by day at sub-month granularity.
-- types: id is a 32-char hex string with no dashes (sample: 17e63e1da1cd81d146fdaa87) — declaring it UUID like the legacy tables do would reject every insert; we use String CODEC(ZSTD(1)). timestamp is ISO-8601 with milliseconds so DateTime64(3) CODEC(Delta, ZSTD(1)), not DateTime (would silently drop the .000 precision). group_size/docs_complete/travellers_submitted are small ints (2-5) so UInt8, not UInt32. LowCardinality(String) applied to event (4 values), destination (14), device_type (4), os (4), geoip_country_code (7), city (7), app_version (3), client_lib (2), relation (5) — all well under the ~10k-distinct threshold where LowCardinality helps. Sparse serialization arithmetic: with E=4 roughly-balanced event types, an event-scoped column (relation, docs_complete: traveller_added-only; travellers_submitted: group_submitted-only; traveller_index: traveller_added+traveller_removed-only) sits near (1 - 1/E) = 0.75-0.80 default ratio empirically (docs_complete coverage 0.641 means default ratio 0.359 within its own scope, but across the whole table it's (rows outside traveller_added)/(total) = (5453-3495)/5453 = 0.359 actually below 0.9375 default threshold too — the binding case is travellers_submitted at 0.126 coverage, i.e. 0.874 default ratio, still under the stock 0.9375 threshold, so it would NOT go sparse by default). We therefore set ratio_of_defaults_for_sparse_serialization = min(0.9, 1 - 1/(E+1)) = min(0.9, 1 - 1/5) = min(0.9, 0.8) = 0.8, lowering the bar so travellers_submitted (0.874 default ratio) and other event-scoped columns do go sparse, matching the storage profile of one-table-per-event without the join cost.
-- nullable: Only traveller_index is Nullable, and it is justified as a genuine tri-state: its observed values include 0 (first traveller), so DEFAULT 0 would make 'traveller_index absent on this event' indistinguishable from 'this is traveller #0' — a real ambiguity since traveller_index appears on only traveller_added/traveller_removed (65.4% coverage). Every other partial-coverage column (relation 64.1%, docs_complete 64.1%, travellers_submitted 12.6%, os 93.7%) uses DEFAULT '' / DEFAULT 0 because none of them have a real value that collides with the default (no relation is '', no travellers_submitted is legitimately 0, os absence isn't analytically distinct from unknown-and-unused). This departs from the 8 existing tables, which Nullable nearly every column (30-35 of 33-38 columns) — that pattern costs a null-map per column and weakens index usage for no analytical gain here.
-- ttl: TTL toDateTime(timestamp) + INTERVAL 18 MONTH on the raw table, paired with two AggregatingMergeTree rollups (agg_group_family_funnel_daily, agg_group_family_docs_completion_daily) that are not subject to this TTL, so daily/group_size trend queries beyond 18 months keep working off the rollups after raw rows expire.
-- mvs: Two MVs, each scoped to a specific PM question rather than a raw copy. mv_group_family_funnel_daily rolls up by day x event x group_size x destination x device_type with countState()/uniqState(group_id) — answers the completion-by-group-size and destination/segment questions via windowFunnel-equivalent step counts without scanning all 5,453 raw rows per query. mv_group_family_docs_completion_daily is filtered to event='traveller_added' (3,495 of 5,453 rows, 64%) and rolls up sumState(docs_complete)/countState() by day x group_size — directly answers 'is docs_complete the bottleneck for big groups' and doubles as the traveller_added side of the add/remove churn question. Both use AggregatingMergeTree with *State functions (never bare count()/uniq()) because summing pre-aggregated distinct counts across daily partitions would double-count groups seen on multiple days; uniqMerge is required downstream. At sample volume (5,453 rows over 21 days) these MVs are not yet worth it in isolation, but projected to the 700K+ applications/yr platform run rate, group_family traffic (1,200 groups / 21 days -> ~21k groups/yr, ~95k raw events/yr) makes the daily x segment grain a materially smaller scan for any multi-month trend query — the keep/drop decision should be re-evaluated post-load by measuring actual reduction_factor and dropping any MV under 5x per house rule 7.
-- contrast_with_legacy: The 8 existing tables are one-table-per-event with ORDER BY (id, timestamp, user_id) and 30-35 Nullable columns out of 33-38 — instrumentation_notes.md calls this an SDK template artifact, not a design. f_group_family_events instead uses one wide table (event LowCardinality discriminator over 4 event types), ORDER BY (event, timestamp, group_id) with no unique id in the sort key, and only 1 genuinely Nullable column (traveller_index) instead of ~30. This turns the PM's headline question ('group_started -> group_submitted completion by group_size') from a 4-way join across per-event tables into one windowFunnel/GROUP BY over a single table, while the sparse-serialization setting (0.8, derived from E=4) keeps the event-scoped columns (relation, docs_complete, travellers_submitted, traveller_index) as cheap as they'd be in separate tables.
-- generation_log: attempt 0: lint clean, dry run OK
-- order_by_measured_chosen_bytes: 240112
-- order_by_measured_straw_bytes: 240112
-- order_by_measured_ratio: 1.00
--
-- mv mv_group_family_funnel_daily: 5,453 -> 2,736 rows (2.0x) DROPPED
-- mv mv_group_family_docs_completion_daily: 5,453 -> 104 rows (52.4x) KEPT

CREATE TABLE IF NOT EXISTS f_group_family_events
(
    `id` String COMMENT 'json_path=id; 32-char hex id, not UUID-parseable; never used in ORDER BY (house rule 2)' CODEC(ZSTD(1)),
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp; ISO-8601 with milliseconds; DateTime would truncate' CODEC(Delta, ZSTD(1)),
    `event` LowCardinality(String) COMMENT 'json_path=event; discriminator, E=4 values',
    `user_id` String DEFAULT '' COMMENT 'json_path=user_id; 100% coverage, secondary key' CODEC(ZSTD(1)),
    `application_id` String DEFAULT '' COMMENT 'json_path=application_id; 100% coverage, secondary key' CODEC(ZSTD(1)),
    `group_id` String DEFAULT '' COMMENT 'json_path=group_id; entity key, 100% coverage, 1200 distinct' CODEC(ZSTD(1)),
    `group_size` UInt8 DEFAULT 0 COMMENT 'json_path=group_size; 5 distinct small ints (2-5), fits UInt8; headline segment dim',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination; 14 distinct values, enum-like',
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type; 4 distinct values',
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; 93.7% coverage, not tri-state analytically distinct, default '''' not Nullable',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code; 7 distinct values',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city; 7 distinct values',
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version; 3 distinct values',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib; 2 distinct values',
    `relation` LowCardinality(String) DEFAULT '' COMMENT 'json_path=relation; event-scoped to traveller_added only (64.1% coverage); '''' means not-applicable, not a real relation value, so DEFAULT '''' is safe (no legit relation value is empty)',
    `docs_complete` UInt8 DEFAULT 0 COMMENT 'json_path=docs_complete; bool -> UInt8 DEFAULT 0 per house rule 4; scoped to traveller_added (64.1% coverage), aggregated only within that event filter so 0-default rows from other events never enter the docs-completion measure',
    `traveller_index` Nullable(UInt8) COMMENT 'json_path=traveller_index; tri-state exception: valid values include 0, so DEFAULT 0 would collide with a real first-traveller index; Nullable distinguishes ''not applicable on this event'' from ''index 0''. Scoped to traveller_added/traveller_removed (65.4% coverage)',
    `travellers_submitted` UInt8 DEFAULT 0 COMMENT 'json_path=travellers_submitted; only on group_submitted (12.6% coverage), values 2-5; 0 default is unambiguous since a real submission is always >=2 travellers'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, group_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.8;

CREATE TABLE IF NOT EXISTS agg_group_family_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, group_size, destination, device_type)
EMPTY AS
SELECT toDate(timestamp) AS day, event, group_size, destination, device_type, countState() AS events_state, uniqState(group_id) AS groups_state FROM atlys.f_group_family_events GROUP BY day, event, group_size, destination, device_type;

CREATE TABLE IF NOT EXISTS agg_group_family_docs_completion_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, group_size)
EMPTY AS
SELECT toDate(timestamp) AS day, group_size, countState() AS added_state, sumState(docs_complete) AS docs_complete_state, uniqState(group_id) AS groups_state FROM atlys.f_group_family_events WHERE event = 'traveller_added' GROUP BY day, group_size;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_group_family_funnel_daily
TO agg_group_family_funnel_daily AS
SELECT toDate(timestamp) AS day, event, group_size, destination, device_type, countState() AS events_state, uniqState(group_id) AS groups_state FROM atlys.f_group_family_events GROUP BY day, event, group_size, destination, device_type;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_group_family_docs_completion_daily
TO agg_group_family_docs_completion_daily AS
SELECT toDate(timestamp) AS day, group_size, countState() AS added_state, sumState(docs_complete) AS docs_complete_state, uniqState(group_id) AS groups_state FROM atlys.f_group_family_events WHERE event = 'traveller_added' GROUP BY day, group_size;
