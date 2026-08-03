-- Express checkout button rendered for eligible user with saved payment method.
CREATE TABLE atlys.express_checkout_shown
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD(1)),
    timestamp DateTime COMMENT 'Event timestamp' CODEC(ZSTD(1)),
    user_id String COMMENT 'Unique traveller identifier' CODEC(ZSTD(1)),
    application_id Nullable(String) COMMENT 'Visa application identifier' CODEC(ZSTD(1)),
    destination Nullable(String) COMMENT 'ISO-2 destination country code' CODEC(ZSTD(1)),
    device_type Nullable(String) COMMENT 'Device platform: ios, android, Desktop, web-user-b2c' CODEC(ZSTD(1)),
    os Nullable(String) COMMENT 'Operating system name' CODEC(ZSTD(1)),
    geoip_country_code Nullable(String) COMMENT 'ISO-2 country code of user geolocation' CODEC(ZSTD(1)),
    city Nullable(String) COMMENT 'City of user geolocation' CODEC(ZSTD(1)),
    app_version Nullable(String) COMMENT 'Atlys app version' CODEC(ZSTD(1)),
    client_lib Nullable(String) COMMENT 'Client library: mobile-rn or web-js' CODEC(ZSTD(1)),
    eligible Nullable(UInt8) COMMENT 'Whether user is eligible for express checkout' CODEC(ZSTD(1)),
    shown_amount Nullable(Float64) COMMENT 'Amount displayed to user at express checkout' CODEC(ZSTD(1)),
    currency Nullable(String) COMMENT 'Currency code of transaction' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS index_granularity=8192, allow_nullable_key=1;

-- User taps Express button to initiate express checkout flow.
CREATE TABLE atlys.express_checkout_selected
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD(1)),
    timestamp DateTime COMMENT 'Event timestamp' CODEC(ZSTD(1)),
    user_id String COMMENT 'Unique traveller identifier' CODEC(ZSTD(1)),
    application_id Nullable(String) COMMENT 'Visa application identifier' CODEC(ZSTD(1)),
    destination Nullable(String) COMMENT 'ISO-2 destination country code' CODEC(ZSTD(1)),
    device_type Nullable(String) COMMENT 'Device platform: ios, android, Desktop, web-user-b2c' CODEC(ZSTD(1)),
    os Nullable(String) COMMENT 'Operating system name' CODEC(ZSTD(1)),
    geoip_country_code Nullable(String) COMMENT 'ISO-2 country code of user geolocation' CODEC(ZSTD(1)),
    city Nullable(String) COMMENT 'City of user geolocation' CODEC(ZSTD(1)),
    app_version Nullable(String) COMMENT 'Atlys app version' CODEC(ZSTD(1)),
    client_lib Nullable(String) COMMENT 'Client library: mobile-rn or web-js' CODEC(ZSTD(1)),
    saved_method_type Nullable(String) COMMENT 'Type of saved payment method: card, upi, or wallet' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS index_granularity=8192, allow_nullable_key=1;

-- Saved payment instrument loaded and ready for transaction during express checkout.
CREATE TABLE atlys.saved_method_used
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD(1)),
    timestamp DateTime COMMENT 'Event timestamp' CODEC(ZSTD(1)),
    user_id String COMMENT 'Unique traveller identifier' CODEC(ZSTD(1)),
    application_id Nullable(String) COMMENT 'Visa application identifier' CODEC(ZSTD(1)),
    destination Nullable(String) COMMENT 'ISO-2 destination country code' CODEC(ZSTD(1)),
    device_type Nullable(String) COMMENT 'Device platform: ios, android, Desktop, web-user-b2c' CODEC(ZSTD(1)),
    os Nullable(String) COMMENT 'Operating system name' CODEC(ZSTD(1)),
    geoip_country_code Nullable(String) COMMENT 'ISO-2 country code of user geolocation' CODEC(ZSTD(1)),
    city Nullable(String) COMMENT 'City of user geolocation' CODEC(ZSTD(1)),
    app_version Nullable(String) COMMENT 'Atlys app version' CODEC(ZSTD(1)),
    client_lib Nullable(String) COMMENT 'Client library: mobile-rn or web-js' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS index_granularity=8192, allow_nullable_key=1;

-- User submits OTP for payment verification during express checkout.
CREATE TABLE atlys.otp_entered
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD(1)),
    timestamp DateTime COMMENT 'Event timestamp' CODEC(ZSTD(1)),
    user_id String COMMENT 'Unique traveller identifier' CODEC(ZSTD(1)),
    application_id Nullable(String) COMMENT 'Visa application identifier' CODEC(ZSTD(1)),
    destination Nullable(String) COMMENT 'ISO-2 destination country code' CODEC(ZSTD(1)),
    device_type Nullable(String) COMMENT 'Device platform: ios, android, Desktop, web-user-b2c' CODEC(ZSTD(1)),
    os Nullable(String) COMMENT 'Operating system name' CODEC(ZSTD(1)),
    geoip_country_code Nullable(String) COMMENT 'ISO-2 country code of user geolocation' CODEC(ZSTD(1)),
    city Nullable(String) COMMENT 'City of user geolocation' CODEC(ZSTD(1)),
    app_version Nullable(String) COMMENT 'Atlys app version' CODEC(ZSTD(1)),
    client_lib Nullable(String) COMMENT 'Client library: mobile-rn or web-js' CODEC(ZSTD(1)),
    otp_attempts Nullable(UInt32) COMMENT 'Number of OTP submission attempts' CODEC(ZSTD(1)),
    otp_success Nullable(UInt8) COMMENT 'Whether OTP verification succeeded' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS index_granularity=8192, allow_nullable_key=1;

-- Payment succeeds via express checkout — conversion event for express flow.
CREATE TABLE atlys.express_payment_confirmed
(
    id UUID COMMENT 'Unique event identifier' CODEC(ZSTD(1)),
    timestamp DateTime COMMENT 'Event timestamp' CODEC(ZSTD(1)),
    user_id String COMMENT 'Unique traveller identifier' CODEC(ZSTD(1)),
    application_id Nullable(String) COMMENT 'Visa application identifier' CODEC(ZSTD(1)),
    destination Nullable(String) COMMENT 'ISO-2 destination country code' CODEC(ZSTD(1)),
    device_type Nullable(String) COMMENT 'Device platform: ios, android, Desktop, web-user-b2c' CODEC(ZSTD(1)),
    os Nullable(String) COMMENT 'Operating system name' CODEC(ZSTD(1)),
    geoip_country_code Nullable(String) COMMENT 'ISO-2 country code of user geolocation' CODEC(ZSTD(1)),
    city Nullable(String) COMMENT 'City of user geolocation' CODEC(ZSTD(1)),
    app_version Nullable(String) COMMENT 'Atlys app version' CODEC(ZSTD(1)),
    client_lib Nullable(String) COMMENT 'Client library: mobile-rn or web-js' CODEC(ZSTD(1)),
    payment_amount Nullable(Float64) COMMENT 'Final payment amount confirmed' CODEC(ZSTD(1)),
    payment_currency Nullable(String) COMMENT 'Currency of confirmed payment' CODEC(ZSTD(1)),
    payment_latency_ms Nullable(UInt32) COMMENT 'Payment processing latency in milliseconds' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (application_id, timestamp)
SETTINGS index_granularity=8192, allow_nullable_key=1;