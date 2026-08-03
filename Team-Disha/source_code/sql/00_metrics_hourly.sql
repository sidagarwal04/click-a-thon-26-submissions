-- Rebuild eda.metrics_hourly from ad_events (idempotent truncate+insert).
-- Run after loading a new test file into eda.ad_events (+ dims).
-- Does NOT drop the table; preserves SharedMergeTree / Cloud settings.

CREATE TABLE IF NOT EXISTS metrics_hourly
(
    event_date Date,
    event_hour UInt8,
    event_dow UInt8,
    is_weekend UInt8,
    requests UInt64,
    fills UInt64,
    impressions UInt64,
    clicks UInt64,
    revenue Float64
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date, event_hour);

TRUNCATE TABLE metrics_hourly;

INSERT INTO metrics_hourly
SELECT
    event_date,
    event_hour,
    event_dow,
    is_weekend,
    count() AS requests,
    sum(is_filled) AS fills,
    sum(is_impression) AS impressions,
    sum(is_click) AS clicks,
    sum(revenue) AS revenue
FROM ad_events
GROUP BY event_date, event_hour, event_dow, is_weekend;
