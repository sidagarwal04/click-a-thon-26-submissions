-- Feature: express_checkout_f1
-- Generated table: express_checkout_events
-- Run ID: bf4ef2ba-ba61-4bf3-ab48-a6f2f7570063
-- Langfuse trace: afe6fc2f03c251785404f325e06ad0e3
-- Context version after run: v2
-- Rows loaded: 5507
-- Generated: 2026-08-02 05:01:33.493000 UTC
-- Produced by the Instrumentation Agent; not hand-edited.

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
