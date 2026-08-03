-- Same column set as sql/01_cube.sql, but standalone: the test slices ship as pre-aggregated cube
-- rows (a CSV), so there is no ad_events to build FROM. run_incident.ensure_cube() sees the table
-- already EXISTS and scans it as-is — never pass --rebuild-cube against a test-sql database.
CREATE DATABASE IF NOT EXISTS {db};
DROP TABLE IF EXISTS {db}.cube;
CREATE TABLE {db}.cube
(
    day           Date,
    region        LowCardinality(String),
    country       LowCardinality(String),
    device_model  LowCardinality(String),
    os_version    LowCardinality(String),
    category      LowCardinality(String),
    publisher_tier LowCardinality(String),
    vertical      LowCardinality(String),   -- '' on unfilled (no advertiser)
    campaign_type LowCardinality(String),   -- ''  "
    ad_format     LowCardinality(String),
    requests      UInt64,
    fills         UInt64,
    impressions   UInt64,
    clicks        UInt64,
    revenue       Float64
)
ENGINE = MergeTree
ORDER BY (day, region, os_version, category, ad_format);
