CREATE TABLE default.concurrency_config (`name` String, `value` String) ENGINE = SharedMergeTree('/clickhouse/tables/{uuid}/{shard}', '{replica}')
ORDER BY
    name SETTINGS index_granularity = 8192