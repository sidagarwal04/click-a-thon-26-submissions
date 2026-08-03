CREATE TABLE gold.metric_anomalies
(
    `anomaly_id` UUID DEFAULT generateUUIDv4(),
    `detected_at` DateTime64(3, 'UTC') DEFAULT now64(3),
    `metric_hour` DateTime('UTC'),
    `segment_key` String,
    `region` LowCardinality(String),
    `ad_format` LowCardinality(String),
    `slice_type` LowCardinality(String) DEFAULT 'region_x_ad_format',
    `slice_value` String,
    `metric_name` LowCardinality(String),
    `current_value` Float64,
    `baseline_value` Float64,
    `delta_pct` Float64,
    `z_score` Nullable(Float64),
    `volume_requests` UInt64 DEFAULT 0,
    `direction` LowCardinality(String) DEFAULT '',
    `severity` LowCardinality(String),
    `detection_tier` LowCardinality(String),
    `confidence_tier` LowCardinality(String),
    `detection_methods` Array(String) DEFAULT [],
    `status` LowCardinality(String) DEFAULT 'open',
    `incident_id` Nullable(UUID),
    `last_error` String DEFAULT '',
    `investigated_at` Nullable(DateTime64(3, 'UTC')),
    `alert_payload` String DEFAULT '',
    `rca_description` String DEFAULT '',
    `evidence_json` String DEFAULT '',
    `disposition` LowCardinality(String) DEFAULT 'pending'
)
ENGINE = SharedMergeTree('/clickhouse/tables/{uuid}/{shard}', '{replica}')
PARTITION BY toYYYYMM(metric_hour)
ORDER BY (metric_hour, severity, segment_key, metric_name)
SETTINGS index_granularity = 8192
