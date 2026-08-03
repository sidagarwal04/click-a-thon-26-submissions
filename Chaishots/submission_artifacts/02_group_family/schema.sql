-- Feature: group_family_f2
-- Generated table: group_application_events
-- Run ID: c8f1a7b2-585c-4c1f-a8ca-7a5b1c5932ab
-- Langfuse trace: adb389ca213bd869be811ad0d2d0305b
-- Context version after run: v3
-- Rows loaded: 5453
-- Generated: 2026-08-02 05:13:00.351000 UTC
-- Produced by the Instrumentation Agent; not hand-edited.

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
