-- Feature: abandoned_checkout_recovery_f4
-- Generated table: abandoned_checkout_recovery_events
-- Run ID: 76a0e403-b1bf-4a37-9f3e-0f81840fd232
-- Langfuse trace: 209fbbbae9d7bdfa4ba539f658083ba3
-- Context version after run: v5
-- Rows loaded: 5919
-- Generated: 2026-08-02 05:19:25.929000 UTC
-- Produced by the Instrumentation Agent; not hand-edited.

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
