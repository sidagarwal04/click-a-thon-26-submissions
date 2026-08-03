-- User drops out at a funnel step without converting; triggers recovery campaign.
CREATE TABLE atlys.abandonment_detected
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD(1)),
    timestamp DateTime COMMENT 'ISO-8601 timestamp of abandonment detection' CODEC(ZSTD(1)),
    user_id String COMMENT 'Unique identifier for the traveller (28-char string)' CODEC(ZSTD(1)),
    application_id Nullable(String) COMMENT 'Unique identifier for the visa application; null if abandoned before application_started' CODEC(ZSTD(1)),
    destination LowCardinality(String) COMMENT 'ISO-2 country code of the visa destination' CODEC(ZSTD(1)),
    drop_step LowCardinality(String) COMMENT 'Funnel step at which user abandoned: destination_card_clicked, application_started, document_uploaded, pay_now_clicked' CODEC(ZSTD(1)),
    device_type Nullable(String) COMMENT 'Device category: ios, android, web-user-b2c' CODEC(ZSTD(1)),
    os Nullable(String) COMMENT 'Operating system: iOS, Android, Windows, Mac OS X' CODEC(ZSTD(1)),
    geoip_country_code Nullable(String) COMMENT 'ISO-2 country code from user IP geolocation' CODEC(ZSTD(1)),
    app_version Nullable(String) COMMENT 'Version of the Atlys app or web client' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (user_id, timestamp)
SETTINGS index_granularity=8192;

-- Re-engagement nudge sent to abandoned user via push, email, or WhatsApp.
CREATE TABLE atlys.reminder_sent
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD(1)),
    timestamp DateTime COMMENT 'ISO-8601 timestamp of reminder send' CODEC(ZSTD(1)),
    user_id String COMMENT 'Unique identifier for the traveller (28-char string)' CODEC(ZSTD(1)),
    application_id Nullable(String) COMMENT 'Unique identifier for the visa application; null if abandoned before application_started' CODEC(ZSTD(1)),
    destination LowCardinality(String) COMMENT 'ISO-2 country code of the visa destination' CODEC(ZSTD(1)),
    drop_step LowCardinality(String) COMMENT 'Funnel step at which user abandoned' CODEC(ZSTD(1)),
    channel LowCardinality(String) COMMENT 'Reminder channel: push, email, whatsapp' CODEC(ZSTD(1)),
    hours_since_drop UInt16 COMMENT 'Hours between abandonment and reminder send' CODEC(ZSTD(1)),
    device_type Nullable(String) COMMENT 'Device category: ios, android, web-user-b2c' CODEC(ZSTD(1)),
    os Nullable(String) COMMENT 'Operating system: iOS, Android, Windows, Mac OS X' CODEC(ZSTD(1)),
    geoip_country_code Nullable(String) COMMENT 'ISO-2 country code from user IP geolocation' CODEC(ZSTD(1)),
    app_version Nullable(String) COMMENT 'Version of the Atlys app or web client' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (user_id, timestamp)
SETTINGS index_granularity=8192;

-- User opens a sent reminder (email/WhatsApp/push notification).
CREATE TABLE atlys.reminder_opened
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD(1)),
    timestamp DateTime COMMENT 'ISO-8601 timestamp of reminder open' CODEC(ZSTD(1)),
    user_id String COMMENT 'Unique identifier for the traveller (28-char string)' CODEC(ZSTD(1)),
    application_id Nullable(String) COMMENT 'Unique identifier for the visa application; null if abandoned before application_started' CODEC(ZSTD(1)),
    destination LowCardinality(String) COMMENT 'ISO-2 country code of the visa destination' CODEC(ZSTD(1)),
    drop_step LowCardinality(String) COMMENT 'Funnel step at which user abandoned' CODEC(ZSTD(1)),
    channel LowCardinality(String) COMMENT 'Reminder channel: push, email, whatsapp' CODEC(ZSTD(1)),
    device_type Nullable(String) COMMENT 'Device category: ios, android, web-user-b2c' CODEC(ZSTD(1)),
    os Nullable(String) COMMENT 'Operating system: iOS, Android, Windows, Mac OS X' CODEC(ZSTD(1)),
    geoip_country_code Nullable(String) COMMENT 'ISO-2 country code from user IP geolocation' CODEC(ZSTD(1)),
    app_version Nullable(String) COMMENT 'Version of the Atlys app or web client' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (user_id, timestamp)
SETTINGS index_granularity=8192;

-- User clicks the call-to-action link in a reminder to return to the funnel.
CREATE TABLE atlys.reminder_cta_clicked
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD(1)),
    timestamp DateTime COMMENT 'ISO-8601 timestamp of CTA click' CODEC(ZSTD(1)),
    user_id String COMMENT 'Unique identifier for the traveller (28-char string)' CODEC(ZSTD(1)),
    application_id Nullable(String) COMMENT 'Unique identifier for the visa application; null if abandoned before application_started' CODEC(ZSTD(1)),
    destination LowCardinality(String) COMMENT 'ISO-2 country code of the visa destination' CODEC(ZSTD(1)),
    drop_step LowCardinality(String) COMMENT 'Funnel step at which user abandoned' CODEC(ZSTD(1)),
    channel LowCardinality(String) COMMENT 'Reminder channel: push, email, whatsapp' CODEC(ZSTD(1)),
    device_type Nullable(String) COMMENT 'Device category: ios, android, web-user-b2c' CODEC(ZSTD(1)),
    os Nullable(String) COMMENT 'Operating system: iOS, Android, Windows, Mac OS X' CODEC(ZSTD(1)),
    geoip_country_code Nullable(String) COMMENT 'ISO-2 country code from user IP geolocation' CODEC(ZSTD(1)),
    app_version Nullable(String) COMMENT 'Version of the Atlys app or web client' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (user_id, timestamp)
SETTINGS index_granularity=8192;

-- User returns to the funnel at the step where they previously abandoned.
CREATE TABLE atlys.resumed_at_step
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD(1)),
    timestamp DateTime COMMENT 'ISO-8601 timestamp of funnel resumption' CODEC(ZSTD(1)),
    user_id String COMMENT 'Unique identifier for the traveller (28-char string)' CODEC(ZSTD(1)),
    application_id Nullable(String) COMMENT 'Unique identifier for the visa application; null if abandoned before application_started' CODEC(ZSTD(1)),
    destination LowCardinality(String) COMMENT 'ISO-2 country code of the visa destination' CODEC(ZSTD(1)),
    drop_step LowCardinality(String) COMMENT 'Funnel step at which user abandoned and is now resuming' CODEC(ZSTD(1)),
    channel Nullable(String) COMMENT 'Channel through which user resumed (push, email, whatsapp, or organic)' CODEC(ZSTD(1)),
    device_type Nullable(String) COMMENT 'Device category: ios, android, web-user-b2c' CODEC(ZSTD(1)),
    os Nullable(String) COMMENT 'Operating system: iOS, Android, Windows, Mac OS X' CODEC(ZSTD(1)),
    geoip_country_code Nullable(String) COMMENT 'ISO-2 country code from user IP geolocation' CODEC(ZSTD(1)),
    app_version Nullable(String) COMMENT 'Version of the Atlys app or web client' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (user_id, timestamp)
SETTINGS index_granularity=8192;

-- User completes payment after being nudged from an abandonment; recovery conversion event.
CREATE TABLE atlys.reconverted
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD(1)),
    timestamp DateTime COMMENT 'ISO-8601 timestamp of reconversion (payment completion)' CODEC(ZSTD(1)),
    user_id String COMMENT 'Unique identifier for the traveller (28-char string)' CODEC(ZSTD(1)),
    application_id String COMMENT 'Unique identifier for the visa application' CODEC(ZSTD(1)),
    destination LowCardinality(String) COMMENT 'ISO-2 country code of the visa destination' CODEC(ZSTD(1)),
    drop_step LowCardinality(String) COMMENT 'Funnel step at which user originally abandoned' CODEC(ZSTD(1)),
    channel LowCardinality(String) COMMENT 'Reminder channel that triggered reconversion: push, email, whatsapp' CODEC(ZSTD(1)),
    device_type Nullable(String) COMMENT 'Device category: ios, android, web-user-b2c' CODEC(ZSTD(1)),
    os Nullable(String) COMMENT 'Operating system: iOS, Android, Windows, Mac OS X' CODEC(ZSTD(1)),
    geoip_country_code Nullable(String) COMMENT 'ISO-2 country code from user IP geolocation' CODEC(ZSTD(1)),
    app_version Nullable(String) COMMENT 'Version of the Atlys app or web client' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS index_granularity=8192;

-- Daily device_type, geoip_country_code rollup for reconverted: event count + unique users, pre-aggregated so AnalyticsAgent's segment cuts don't rescan raw events.
CREATE MATERIALIZED VIEW atlys.reconverted_daily_segment_mv
ENGINE = AggregatingMergeTree
ORDER BY (day, device_type, geoip_country_code)

SETTINGS allow_nullable_key = 1
POPULATE AS
SELECT
    toDate(timestamp) AS day,
    device_type, geoip_country_code,
    count() AS events,
    uniqState(user_id) AS unique_users_state
FROM atlys.reconverted
GROUP BY day, device_type, geoip_country_code;