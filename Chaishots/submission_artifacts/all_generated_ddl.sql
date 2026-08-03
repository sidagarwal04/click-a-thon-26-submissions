-- Generated DDL for all six feature specs, Team Chaishots (Asklys).
-- Produced by the Instrumentation Agent and validated in Python before execution.
-- Source of truth: ClickHouse `generated_artifacts` where artifact_type='schema'.
-- The final table below is the sealed sixth specification.

-- express_checkout_events
CREATE TABLE `atlys`.`express_checkout_events`
(
    `event` String,
    `id` String,
    `timestamp` DateTime64(3),
    `device_type` String,
    `os` Nullable(String),
    `app_version` String,
    `geoip_country_code` String,
    `city` String,
    `client_lib` String,
    `user_id` String,
    `application_id` String,
    `destination` String,
    `eligible` Nullable(UInt8),
    `shown_amount` Nullable(Float64),
    `currency` Nullable(String),
    `saved_method_type` Nullable(String),
    `otp_attempts` Nullable(Int64),
    `otp_success` Nullable(UInt8),
    `payment` Nullable(String)
)
ENGINE = MergeTree
ORDER BY (`user_id`, `timestamp`, `event`);

-- group_application_events
CREATE TABLE `atlys`.`group_application_events`
(
    `event` String,
    `id` String,
    `timestamp` DateTime64(3),
    `device_type` String,
    `os` Nullable(String),
    `app_version` String,
    `geoip_country_code` String,
    `city` String,
    `client_lib` String,
    `user_id` String,
    `application_id` String,
    `group_id` String,
    `destination` String,
    `group_size` Int64,
    `traveller_index` Nullable(Int64),
    `relation` Nullable(String),
    `docs_complete` Nullable(UInt8),
    `travellers_submitted` Nullable(Int64)
)
ENGINE = MergeTree
ORDER BY (`group_id`, `timestamp`, `event`, `user_id`);

-- visa_status_sharing_events
CREATE TABLE `atlys`.`visa_status_sharing_events`
(
    `event` String,
    `id` String,
    `timestamp` DateTime64(3),
    `device_type` Nullable(String),
    `os` Nullable(String),
    `app_version` Nullable(String),
    `geoip_country_code` Nullable(String),
    `city` Nullable(String),
    `client_lib` Nullable(String),
    `user_id` Nullable(String),
    `application_id` Nullable(String),
    `share_id` String,
    `destination` String,
    `status_shared` Nullable(String),
    `channel` Nullable(String),
    `recipient_is_new_user` Nullable(UInt8),
    `cta` Nullable(String)
)
ENGINE = MergeTree
ORDER BY (`destination`, `event`, `timestamp`, `share_id`);

-- abandoned_checkout_recovery_events
CREATE TABLE `atlys`.`abandoned_checkout_recovery_events`
(
    `event` String,
    `id` String,
    `timestamp` DateTime64(3),
    `device_type` String,
    `os` Nullable(String),
    `app_version` String,
    `geoip_country_code` String,
    `city` String,
    `client_lib` String,
    `user_id` String,
    `application_id` String,
    `destination` String,
    `drop_step` String,
    `channel` Nullable(String),
    `hours_since_drop` Nullable(Int64)
)
ENGINE = MergeTree
ORDER BY (`user_id`, `timestamp`, `event`, `drop_step`);

-- instant_forex_addon_events
CREATE TABLE `atlys`.`instant_forex_addon_events`
(
    `event` String,
    `id` String,
    `timestamp` DateTime64(3),
    `device_type` String,
    `os` Nullable(String),
    `app_version` String,
    `geoip_country_code` String,
    `city` String,
    `client_lib` String,
    `user_id` String,
    `application_id` String,
    `destination` String,
    `from_currency` String,
    `to_currency` String,
    `fx_rate` Nullable(Float64),
    `amount` Nullable(Int64),
    `addon_value_inr` Nullable(Float64)
)
ENGINE = MergeTree
ORDER BY (`user_id`, `timestamp`, `event`, `destination`);

-- promo_coupon_checkout_events
CREATE TABLE `atlys`.`promo_coupon_checkout_events`
(
    `event` String,
    `id` String,
    `timestamp` DateTime64(3),
    `device_type` String,
    `os` Nullable(String),
    `app_version` String,
    `geoip_country_code` String,
    `city` String,
    `client_lib` String,
    `user_id` String,
    `application_id` String,
    `destination` String,
    `cart_value` Float64,
    `currency` String,
    `coupon_code` Nullable(String),
    `discount_type` Nullable(String),
    `discount_amount` Nullable(Float64),
    `final_value` Nullable(Float64),
    `reject_reason` Nullable(String)
)
ENGINE = MergeTree
ORDER BY (`user_id`, `timestamp`, `event`, `destination`);
