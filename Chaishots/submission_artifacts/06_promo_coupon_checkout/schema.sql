-- SEALED SIXTH SPECIFICATION — unseen data / surprise round
-- Feature: unseen_f6
-- Generated table: promo_coupon_checkout_events
-- Run ID: 63a7c39b-a158-4acf-b92c-3f15250c9e15
-- Langfuse trace: e18e58f7f9d834c17e9b52f42f2aa851
-- Context version after run: v7
-- Rows loaded: 5363
-- Generated: 2026-08-02 06:00:11 UTC
-- Produced end to end by the Instrumentation Agent; not hand-edited.

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
