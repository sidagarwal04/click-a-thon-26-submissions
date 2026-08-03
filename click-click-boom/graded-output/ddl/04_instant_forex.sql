-- spec: instant_forex
-- table: forex_addon_events
-- ordering_key: (application_id, event_type, event_timestamp, event_id)
-- partition_key: (none)
-- confidence: 0.99
-- executed: 2026-08-02 02:51:10
-- trace: https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/764f66e6fa153486ad49a1ee19a7eeb3
--
-- rationale: All statements intentionally use unqualified object names and must be deployed after explicitly selecting the atlys database with `USE atlys`; therefore the base table and both materialized views resolve to the same database without mixed qualification. Empty application_id rows are excluded only from the application funnel MV; the daily MV retains total event_count while conditionally counting only nonempty users and applications. Destination and currency are intentionally offer-time dimensions: nonblank values from forex_offer_shown are preferred, with deterministic fallback to later nonblank events. Device and geo use the earliest nonblank observed values. event_id deduplication is a mandatory deployment prerequisite via an idempotency ledger or deduplicated staging pipeline before insertion. Retries and backfills must load only deduplicated rows, or rebuild/backfill both incremental MVs because aggregate states cannot retract duplicates. State query contract: finalize the application MV first, then regroup. Canonical destination query: SELECT destination, sum(purchased) / nullIf(sum(offer_shown), 0) AS attach_rate FROM (SELECT application_id, argMinMerge(destination) AS destination, maxMerge(purchased) AS purchased, maxMerge(offer_shown) AS offer_shown FROM forex_addon_application_funnel GROUP BY application_id) GROUP BY destination. Overall attach rate uses the same finalized subquery without the outer GROUP BY. Daily query: SELECT event_date, event_type, countMerge(event_count) AS events, uniqExactMerge(unique_users) AS users, uniqExactMerge(unique_applications) AS applications FROM forex_addon_daily_event_metrics GROUP BY event_date, event_type. Users and applications exclude empty identifiers, while events includes anonymous rows. Use sumMerge(purchased_addon_value_inr) for total purchased addon value. | ordering key chosen by perf_tool: 1.0x vs legacy baseline.

CREATE TABLE forex_addon_events (`event_type` LowCardinality(String),
`event_id` String,
`event_timestamp` DateTime64(3, 'UTC'),
`event_date` Date MATERIALIZED toDate(event_timestamp),
`device_type` LowCardinality(String) DEFAULT '',
`os` LowCardinality(String) DEFAULT '',
`app_version` LowCardinality(String) DEFAULT '',
`geoip_country_code` LowCardinality(String) DEFAULT '',
`city` LowCardinality(String) DEFAULT '',
`client_lib` LowCardinality(String) DEFAULT '',
`user_id` String,
`application_id` String,
`destination` FixedString(2),
`from_currency` FixedString(3) DEFAULT '   ',
`to_currency` FixedString(3) DEFAULT '   ',
`fx_rate` Decimal(18, 8) DEFAULT 0,
`amount` Decimal(18, 2) DEFAULT 0,
`addon_value_inr` Decimal(18, 2) DEFAULT 0) ENGINE = MergeTree ORDER BY (application_id, event_type, event_timestamp, event_id);

-- materialized view: forex_addon_application_funnel
-- answers PM question: Application-level attach rates, stage drop-offs, destination/currency comparisons, and deterministic device/geo segment cuts.
CREATE MATERIALIZED VIEW forex_addon_application_funnel
ENGINE = AggregatingMergeTree
ORDER BY (application_id)
AS
SELECT
    application_id,
    argMinIfState(user_id, tuple(event_timestamp, event_id), user_id != '') AS user_id,
    argMinIfState(destination, tuple(if(event_type = 'forex_offer_shown', 0, 1), event_timestamp, event_id), destination != '') AS destination,
    argMinIfState(to_currency, tuple(if(event_type = 'forex_offer_shown', 0, 1), event_timestamp, event_id), to_currency != '   ') AS to_currency,
    argMinIfState(from_currency, tuple(if(event_type = 'forex_offer_shown', 0, 1), event_timestamp, event_id), from_currency != '   ') AS from_currency,
    argMinIfState(device_type, tuple(event_timestamp, event_id), device_type != '') AS device_type,
    argMinIfState(geoip_country_code, tuple(event_timestamp, event_id), geoip_country_code != '') AS geoip_country_code,
    minState(event_timestamp) AS first_event_timestamp,
    maxState(toUInt8(event_type = 'forex_offer_shown')) AS offer_shown,
    maxState(toUInt8(event_type = 'currency_selected')) AS currency_selected,
    maxState(toUInt8(event_type = 'amount_entered')) AS amount_entered,
    maxState(toUInt8(event_type = 'forex_added_to_cart')) AS added_to_cart,
    maxState(toUInt8(event_type = 'forex_purchased')) AS purchased,
    sumState(if(event_type = 'forex_purchased', addon_value_inr, toDecimal64(0, 2))) AS purchased_addon_value_inr
FROM forex_addon_events
WHERE application_id != ''
GROUP BY application_id
;

-- materialized view: forex_addon_daily_event_metrics
-- answers PM question: All daily forex event volume, plus distinct nonempty users and applications, by event type and reporting dimensions.
CREATE MATERIALIZED VIEW forex_addon_daily_event_metrics
ENGINE = AggregatingMergeTree
ORDER BY (event_date, event_type, destination, to_currency, device_type, geoip_country_code)
AS
SELECT
    event_date,
    event_type,
    destination,
    to_currency,
    device_type,
    geoip_country_code,
    countState() AS event_count,
    uniqExactIfState(user_id, user_id != '') AS unique_users,
    uniqExactIfState(application_id, application_id != '') AS unique_applications
FROM forex_addon_events
GROUP BY event_date, event_type, destination, to_currency, device_type, geoip_country_code
;