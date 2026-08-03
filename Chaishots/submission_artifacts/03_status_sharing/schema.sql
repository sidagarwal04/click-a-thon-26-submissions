-- Feature: status_sharing_f3
-- Generated table: visa_status_sharing_events
-- Run ID: 5bef9fb7-34f1-4f5c-86a7-1afca5e4544f
-- Langfuse trace: 089db6c8c215922bc2cac20d2b5817b1
-- Context version after run: v4
-- Rows loaded: 6503
-- Generated: 2026-08-02 05:16:27.337000 UTC
-- Produced by the Instrumentation Agent; not hand-edited.

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
