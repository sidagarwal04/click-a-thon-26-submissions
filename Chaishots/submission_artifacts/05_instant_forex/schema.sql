-- Feature: instant_forex_f5
-- Generated table: instant_forex_addon_events
-- Run ID: 9d496d23-dadb-4137-b13a-8ccb49596027
-- Langfuse trace: 97e9e1246e32c240e5ce500011f49f6a
-- Context version after run: v6
-- Rows loaded: 6237
-- Generated: 2026-08-02 05:23:29.219000 UTC
-- Produced by the Instrumentation Agent; not hand-edited.

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
