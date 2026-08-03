-- Event table for forex_offer_shown
CREATE TABLE atlys.forex_offer_shown
(
    id UUID COMMENT 'Event ID',
    timestamp DateTime COMMENT 'Event timestamp',
    user_id String COMMENT 'User identifier',
    application_id Nullable(String) COMMENT 'Application ID',
    device_type Nullable(String) COMMENT 'Device type',
    os Nullable(String) COMMENT 'Operating system',
    app_version Nullable(String) COMMENT 'App version',
    client_lib Nullable(String) COMMENT 'Client library',
    geoip_country_code Nullable(String) COMMENT 'Country code',
    city Nullable(String) COMMENT 'City',
    destination Nullable(String) COMMENT 'Destination country',
    from_currency Nullable(String) COMMENT 'From forex_offer_shown.from_currency',
    to_currency Nullable(String) COMMENT 'From forex_offer_shown.to_currency',
    fx_rate Nullable(Float64) COMMENT 'From forex_offer_shown.fx_rate'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS allow_nullable_key=1;

-- Event table for currency_selected
CREATE TABLE atlys.currency_selected
(
    id UUID COMMENT 'Event ID',
    timestamp DateTime COMMENT 'Event timestamp',
    user_id String COMMENT 'User identifier',
    application_id Nullable(String) COMMENT 'Application ID',
    device_type Nullable(String) COMMENT 'Device type',
    os Nullable(String) COMMENT 'Operating system',
    app_version Nullable(String) COMMENT 'App version',
    client_lib Nullable(String) COMMENT 'Client library',
    geoip_country_code Nullable(String) COMMENT 'Country code',
    city Nullable(String) COMMENT 'City',
    destination Nullable(String) COMMENT 'Destination country',
    from_currency Nullable(String) COMMENT 'From currency_selected.from_currency',
    to_currency Nullable(String) COMMENT 'From currency_selected.to_currency'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS allow_nullable_key=1;

-- Event table for amount_entered
CREATE TABLE atlys.amount_entered
(
    id UUID COMMENT 'Event ID',
    timestamp DateTime COMMENT 'Event timestamp',
    user_id String COMMENT 'User identifier',
    application_id Nullable(String) COMMENT 'Application ID',
    device_type Nullable(String) COMMENT 'Device type',
    os Nullable(String) COMMENT 'Operating system',
    app_version Nullable(String) COMMENT 'App version',
    client_lib Nullable(String) COMMENT 'Client library',
    geoip_country_code Nullable(String) COMMENT 'Country code',
    city Nullable(String) COMMENT 'City',
    destination Nullable(String) COMMENT 'Destination country',
    from_currency Nullable(String) COMMENT 'From amount_entered.from_currency',
    to_currency Nullable(String) COMMENT 'From amount_entered.to_currency',
    amount Nullable(Int64) COMMENT 'From amount_entered.amount'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS allow_nullable_key=1;

-- Event table for forex_added_to_cart
CREATE TABLE atlys.forex_added_to_cart
(
    id UUID COMMENT 'Event ID',
    timestamp DateTime COMMENT 'Event timestamp',
    user_id String COMMENT 'User identifier',
    application_id Nullable(String) COMMENT 'Application ID',
    device_type Nullable(String) COMMENT 'Device type',
    os Nullable(String) COMMENT 'Operating system',
    app_version Nullable(String) COMMENT 'App version',
    client_lib Nullable(String) COMMENT 'Client library',
    geoip_country_code Nullable(String) COMMENT 'Country code',
    city Nullable(String) COMMENT 'City',
    destination Nullable(String) COMMENT 'Destination country',
    from_currency Nullable(String) COMMENT 'From forex_added_to_cart.from_currency',
    to_currency Nullable(String) COMMENT 'From forex_added_to_cart.to_currency',
    amount Nullable(Int64) COMMENT 'From forex_added_to_cart.amount',
    addon_value_inr Nullable(Float64) COMMENT 'From forex_added_to_cart.addon_value_inr'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS allow_nullable_key=1;

-- Event table for forex_purchased
CREATE TABLE atlys.forex_purchased
(
    id UUID COMMENT 'Event ID',
    timestamp DateTime COMMENT 'Event timestamp',
    user_id String COMMENT 'User identifier',
    application_id Nullable(String) COMMENT 'Application ID',
    device_type Nullable(String) COMMENT 'Device type',
    os Nullable(String) COMMENT 'Operating system',
    app_version Nullable(String) COMMENT 'App version',
    client_lib Nullable(String) COMMENT 'Client library',
    geoip_country_code Nullable(String) COMMENT 'Country code',
    city Nullable(String) COMMENT 'City',
    destination Nullable(String) COMMENT 'Destination country',
    from_currency Nullable(String) COMMENT 'From forex_purchased.from_currency',
    to_currency Nullable(String) COMMENT 'From forex_purchased.to_currency',
    amount Nullable(Int64) COMMENT 'From forex_purchased.amount',
    addon_value_inr Nullable(Float64) COMMENT 'From forex_purchased.addon_value_inr'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS allow_nullable_key=1;

-- Daily device_type, geoip_country_code rollup for forex_purchased: event count + unique users, pre-aggregated so AnalyticsAgent's segment cuts don't rescan raw events.
CREATE MATERIALIZED VIEW atlys.forex_purchased_daily_segment_mv
ENGINE = AggregatingMergeTree
ORDER BY (day, device_type, geoip_country_code)

SETTINGS allow_nullable_key = 1
POPULATE AS
SELECT
    toDate(timestamp) AS day,
    device_type, geoip_country_code,
    count() AS events,
    uniqState(user_id) AS unique_users_state
FROM atlys.forex_purchased
GROUP BY day, device_type, geoip_country_code;