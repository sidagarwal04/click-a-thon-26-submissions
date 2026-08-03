-- User initiates a group application flow for multiple travellers.
CREATE TABLE atlys.group_started
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD(1)),
    timestamp DateTime COMMENT 'ISO-8601 timestamp of the event in UTC' CODEC(ZSTD(1)),
    user_id String COMMENT 'Unique identifier for the primary traveller/applicant, 28-char string' CODEC(ZSTD(1)),
    application_id String COMMENT 'Unique identifier for the visa application, 32-char hex string' CODEC(ZSTD(1)),
    group_id String COMMENT 'Unique identifier for a group application, 32-char hex string' CODEC(ZSTD(1)),
    destination LowCardinality(String) COMMENT 'ISO-2 country code for the visa destination' CODEC(ZSTD(1)),
    group_size Int32 COMMENT 'Total number of travellers in the group at event time' CODEC(ZSTD(1)),
    device_type Nullable(String) COMMENT 'Device platform on which the event was triggered' CODEC(ZSTD(1)),
    os Nullable(String) COMMENT 'Operating system of the device' CODEC(ZSTD(1)),
    geoip_country_code Nullable(String) COMMENT 'ISO-2 country code derived from user''s IP geolocation' CODEC(ZSTD(1)),
    city Nullable(String) COMMENT 'City derived from user''s IP geolocation' CODEC(ZSTD(1)),
    app_version Nullable(String) COMMENT 'Version of the Atlys mobile or web app at event time' CODEC(ZSTD(1)),
    client_lib Nullable(String) COMMENT 'Client library used to emit the event' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS index_granularity=8192;

-- A co-traveller is added to the group with relation and document completion status.
CREATE TABLE atlys.traveller_added
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD(1)),
    timestamp DateTime COMMENT 'ISO-8601 timestamp of the event in UTC' CODEC(ZSTD(1)),
    user_id String COMMENT 'Unique identifier for the primary traveller/applicant, 28-char string' CODEC(ZSTD(1)),
    application_id String COMMENT 'Unique identifier for the visa application, 32-char hex string' CODEC(ZSTD(1)),
    group_id String COMMENT 'Unique identifier for a group application, 32-char hex string' CODEC(ZSTD(1)),
    destination LowCardinality(String) COMMENT 'ISO-2 country code for the visa destination' CODEC(ZSTD(1)),
    group_size Int32 COMMENT 'Total number of travellers in the group at event time' CODEC(ZSTD(1)),
    traveller_index Int32 COMMENT 'Zero-based position of the traveller within the group roster' CODEC(ZSTD(1)),
    relation LowCardinality(String) COMMENT 'Family or group relation of the co-traveller to the primary applicant' CODEC(ZSTD(1)),
    docs_complete Boolean COMMENT 'Whether the traveller''s required documents (passport, etc.) are complete at event time' CODEC(ZSTD(1)),
    device_type Nullable(String) COMMENT 'Device platform on which the event was triggered' CODEC(ZSTD(1)),
    os Nullable(String) COMMENT 'Operating system of the device' CODEC(ZSTD(1)),
    geoip_country_code Nullable(String) COMMENT 'ISO-2 country code derived from user''s IP geolocation' CODEC(ZSTD(1)),
    city Nullable(String) COMMENT 'City derived from user''s IP geolocation' CODEC(ZSTD(1)),
    app_version Nullable(String) COMMENT 'Version of the Atlys mobile or web app at event time' CODEC(ZSTD(1)),
    client_lib Nullable(String) COMMENT 'Client library used to emit the event' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS index_granularity=8192;

-- A co-traveller is removed from the group application.
CREATE TABLE atlys.traveller_removed
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD(1)),
    timestamp DateTime COMMENT 'ISO-8601 timestamp of the event in UTC' CODEC(ZSTD(1)),
    user_id String COMMENT 'Unique identifier for the primary traveller/applicant, 28-char string' CODEC(ZSTD(1)),
    application_id String COMMENT 'Unique identifier for the visa application, 32-char hex string' CODEC(ZSTD(1)),
    group_id String COMMENT 'Unique identifier for a group application, 32-char hex string' CODEC(ZSTD(1)),
    destination LowCardinality(String) COMMENT 'ISO-2 country code for the visa destination' CODEC(ZSTD(1)),
    group_size Int32 COMMENT 'Total number of travellers in the group at event time' CODEC(ZSTD(1)),
    traveller_index Int32 COMMENT 'Zero-based position of the traveller within the group roster' CODEC(ZSTD(1)),
    device_type Nullable(String) COMMENT 'Device platform on which the event was triggered' CODEC(ZSTD(1)),
    os Nullable(String) COMMENT 'Operating system of the device' CODEC(ZSTD(1)),
    geoip_country_code Nullable(String) COMMENT 'ISO-2 country code derived from user''s IP geolocation' CODEC(ZSTD(1)),
    city Nullable(String) COMMENT 'City derived from user''s IP geolocation' CODEC(ZSTD(1)),
    app_version Nullable(String) COMMENT 'Version of the Atlys mobile or web app at event time' CODEC(ZSTD(1)),
    client_lib Nullable(String) COMMENT 'Client library used to emit the event' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS index_granularity=8192;

-- The group application is submitted with final traveller count.
CREATE TABLE atlys.group_submitted
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD(1)),
    timestamp DateTime COMMENT 'ISO-8601 timestamp of the event in UTC' CODEC(ZSTD(1)),
    user_id String COMMENT 'Unique identifier for the primary traveller/applicant, 28-char string' CODEC(ZSTD(1)),
    application_id String COMMENT 'Unique identifier for the visa application, 32-char hex string' CODEC(ZSTD(1)),
    group_id String COMMENT 'Unique identifier for a group application, 32-char hex string' CODEC(ZSTD(1)),
    destination LowCardinality(String) COMMENT 'ISO-2 country code for the visa destination' CODEC(ZSTD(1)),
    group_size Int32 COMMENT 'Total number of travellers in the group at event time' CODEC(ZSTD(1)),
    travellers_submitted Int32 COMMENT 'Number of travellers actually submitted in the group_submitted event' CODEC(ZSTD(1)),
    device_type Nullable(String) COMMENT 'Device platform on which the event was triggered' CODEC(ZSTD(1)),
    os Nullable(String) COMMENT 'Operating system of the device' CODEC(ZSTD(1)),
    geoip_country_code Nullable(String) COMMENT 'ISO-2 country code derived from user''s IP geolocation' CODEC(ZSTD(1)),
    city Nullable(String) COMMENT 'City derived from user''s IP geolocation' CODEC(ZSTD(1)),
    app_version Nullable(String) COMMENT 'Version of the Atlys mobile or web app at event time' CODEC(ZSTD(1)),
    client_lib Nullable(String) COMMENT 'Client library used to emit the event' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS index_granularity=8192;

-- Daily device_type, geoip_country_code rollup for group_submitted: event count + unique users, pre-aggregated so AnalyticsAgent's segment cuts don't rescan raw events.
CREATE MATERIALIZED VIEW atlys.group_submitted_daily_segment_mv
ENGINE = AggregatingMergeTree
ORDER BY (day, device_type, geoip_country_code)

SETTINGS allow_nullable_key = 1
POPULATE AS
SELECT
    toDate(timestamp) AS day,
    device_type, geoip_country_code,
    count() AS events,
    uniqState(user_id) AS unique_users_state
FROM atlys.group_submitted
GROUP BY day, device_type, geoip_country_code;