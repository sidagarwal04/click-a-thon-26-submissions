-- spec: unseen_data (6th spec -- Promo / Coupon at Checkout, SEALED, revealed at judging)
-- table: promo_coupon_checkout_events
-- ordering_key: (event_date, destination, device_type, os, event_type, application_id, id)
-- partition_key: toYYYYMM(event_date)
-- confidence: 0.99
-- executed: 2026-08-02 04:16:38
-- trace: https://us.cloud.langfuse.com/project/cmsa4lt1l18xrad0dh1vrhjnq/traces/fb0be1756c33bf73b2028b397fe0cd7d
--
-- rationale: Trace: mapped the six supplied event types and envelope fields, analyzed the 180-event sample, and aligned the executable schema with the stated workload. The canonical base key leads with application_id, so no unsubmitted projection is claimed; this directly supports the required order-agnostic funnel joins. coupon_code uses portable Nullable(String). Each materialized_views.ddl contains both the explicit backing target CREATE TABLE and the CREATE MATERIALIZED VIEW ... TO ... statement, separated by a semicolon. Both aggregate target ORDER BY clauses include os. Exact states use uniqExactStateIf and exclude empty identifiers; readers use countMerge, uniqExactMerge, and sumMerge while grouping by every dimension column. Supporting ingestion objects are explicit deployment preconditions owned by the ingestion service: an immutable landing table containing the raw payload plus landed_at, a durable event-id ledger, and a canonical-writer interface. The writer validates non-empty id/user_id/application_id, reserves each id with a deterministic token, inserts the canonical row, and marks the reservation complete only after canonical visibility. If a crash occurs, incomplete reservations are retried from landing; reconciliation compares landing, ledger, and canonical ids and repairs incomplete reservations without inserting an id twice. Direct caller writes to canonical and aggregate tables are prohibited. Backfill/cutover is concrete: pause canonical ingestion at {cutover_utc}; create both target tables and MVs; then directly backfill the explicit targets, never the source table. Daily backfill uses INSERT INTO promo_coupon_checkout_daily_metrics (event_date,event_type,device_type,os,geoip_country_code,destination,currency,events,users,applications,discount_total,final_value_total) SELECT event_date,event_type,device_type,os,geoip_country_code,destination,currency,countState(),uniqExactStateIf(user_id,user_id!=''),uniqExactStateIf(application_id,application_id!=''),sumState(if(event_type='coupon_applied',ifNull(discount_amount,toDecimal64(0,2)),toDecimal64(0,2))),sumState(if(event_type='checkout_with_coupon',ifNull(final_value,toDecimal64(0,2)),toDecimal64(0,2))) FROM promo_coupon_checkout_events WHERE timestamp < toDateTime64('{cutover_utc}',3,'UTC') GROUP BY event_date,event_type,device_type,os,geoip_country_code,destination,currency. Code backfill uses INSERT INTO promo_coupon_checkout_code_metrics (event_date,coupon_code,event_type,device_type,os,geoip_country_code,destination,currency,events,users,applications,discount_total,final_value_total) SELECT event_date,ifNull(coupon_code,''),event_type,device_type,os,geoip_country_code,destination,currency,countState(),uniqExactStateIf(user_id,user_id!=''),uniqExactStateIf(application_id,application_id!=''),sumState(if(event_type='coupon_applied',ifNull(discount_amount,toDecimal64(0,2)),toDecimal64(0,2))),sumState(if(event_type='checkout_with_coupon',ifNull(final_value,toDecimal64(0,2)),toDecimal64(0,2))) FROM promo_coupon_checkout_events WHERE timestamp < toDateTime64('{cutover_utc}',3,'UTC') AND event_type IN ('coupon_entered','coupon_applied','coupon_rejected','checkout_with_coupon') AND coupon_code IS NOT NULL AND coupon_code != '' GROUP BY event_date,ifNull(coupon_code,''),event_type,device_type,os,geoip_country_code,destination,currency. Reconcile target totals, then resume ingestion only at or after the boundary; no event is processed by both backfill and live MV paths. The sample trace has 30 rows of each event type, 30 field-shown applications, 9 overlapping coupon_applied applications (30%), an even applied/rejected split, and rejection counts invalid_code 10, already_used 9, expired 6, and min_cart_not_met 5. It has 18 null-code baseline checkout rows and 12 non-null-code checkout rows, supporting baseline reporting but not a causal lift claim. Applied discount volume is FREESHIP 11 applies and 0 cost, WELCOME 7 and 2,100 total discount, FIRST10 5 and 2,000, ATLYS15 4 and 2,808, and SUMMER20 3 and 3,043; SUMMER20 has the highest sample cost per apply and should receive margin monitoring.

CREATE TABLE promo_coupon_checkout_events (id String,
    timestamp DateTime64(3, 'UTC'),
    event_type LowCardinality(String),
    event_date Date MATERIALIZED toDate(timestamp),
    device_type LowCardinality(String),
    os LowCardinality(String) DEFAULT '',
    app_version LowCardinality(String) DEFAULT '',
    geoip_country_code LowCardinality(String) DEFAULT '',
    city LowCardinality(String) DEFAULT '',
    client_lib LowCardinality(String) DEFAULT '',
    user_id String,
    application_id String,
    destination LowCardinality(String),
    cart_value Decimal(18, 2) DEFAULT 0,
    currency LowCardinality(String) DEFAULT '',
    coupon_code Nullable(String),
    discount_type LowCardinality(String) DEFAULT '',
    discount_amount Nullable(Decimal(18, 2)),
    final_value Nullable(Decimal(18, 2)),
    reject_reason LowCardinality(String) DEFAULT '') ENGINE = MergeTree PARTITION BY toYYYYMM(event_date) ORDER BY (event_date, destination, device_type, os, event_type, application_id, id);

CREATE TABLE promo_coupon_checkout_daily_metrics
(
    event_date Date,
    event_type LowCardinality(String),
    device_type LowCardinality(String),
    os LowCardinality(String),
    geoip_country_code LowCardinality(String),
    destination LowCardinality(String),
    currency LowCardinality(String),
    events AggregateFunction(count),
    users AggregateFunction(uniqExact, String),
    applications AggregateFunction(uniqExact, String),
    discount_total AggregateFunction(sum, Decimal(18, 2)),
    final_value_total AggregateFunction(sum, Decimal(18, 2))
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, event_type, destination, device_type, os, geoip_country_code, currency);

CREATE MATERIALIZED VIEW promo_coupon_checkout_daily_metrics_mv
TO promo_coupon_checkout_daily_metrics
AS SELECT
    event_date,
    event_type,
    device_type,
    os,
    geoip_country_code,
    destination,
    currency,
    countState() AS events,
    uniqExactStateIf(user_id, user_id != '') AS users,
    uniqExactStateIf(application_id, application_id != '') AS applications,
    sumState(if(event_type = 'coupon_applied', ifNull(discount_amount, toDecimal64(0, 2)), toDecimal64(0, 2))) AS discount_total,
    sumState(if(event_type = 'checkout_with_coupon', ifNull(final_value, toDecimal64(0, 2)), toDecimal64(0, 2))) AS final_value_total
FROM promo_coupon_checkout_events
GROUP BY event_date, event_type, device_type, os, geoip_country_code, destination, currency

CREATE TABLE promo_coupon_checkout_code_metrics
(
    event_date Date,
    coupon_code String,
    event_type LowCardinality(String),
    device_type LowCardinality(String),
    os LowCardinality(String),
    geoip_country_code LowCardinality(String),
    destination LowCardinality(String),
    currency LowCardinality(String),
    events AggregateFunction(count),
    users AggregateFunction(uniqExact, String),
    applications AggregateFunction(uniqExact, String),
    discount_total AggregateFunction(sum, Decimal(18, 2)),
    final_value_total AggregateFunction(sum, Decimal(18, 2))
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, coupon_code, event_type, destination, device_type, os, geoip_country_code, currency);

CREATE MATERIALIZED VIEW promo_coupon_checkout_code_metrics_mv
TO promo_coupon_checkout_code_metrics
AS SELECT
    event_date,
    ifNull(coupon_code, '') AS coupon_code,
    event_type,
    device_type,
    os,
    geoip_country_code,
    destination,
    currency,
    countState() AS events,
    uniqExactStateIf(user_id, user_id != '') AS users,
    uniqExactStateIf(application_id, application_id != '') AS applications,
    sumState(if(event_type = 'coupon_applied', ifNull(discount_amount, toDecimal64(0, 2)), toDecimal64(0, 2))) AS discount_total,
    sumState(if(event_type = 'checkout_with_coupon', ifNull(final_value, toDecimal64(0, 2)), toDecimal64(0, 2))) AS final_value_total
FROM promo_coupon_checkout_events
WHERE event_type IN ('coupon_entered', 'coupon_applied', 'coupon_rejected', 'checkout_with_coupon')
  AND coupon_code IS NOT NULL
  AND coupon_code != ''
GROUP BY event_date, coupon_code, event_type, device_type, os, geoip_country_code, destination, currency
