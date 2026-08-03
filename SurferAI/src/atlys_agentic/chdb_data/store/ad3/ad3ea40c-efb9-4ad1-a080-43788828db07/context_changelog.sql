ATTACH TABLE _ UUID 'e25b5678-cae9-4e40-9052-1d5586f3838c'
(
    `ts` DateTime,
    `change_type` String,
    `before` String,
    `after` String,
    `agent` String,
    `trace_id` String
)
ENGINE = MergeTree
ORDER BY ts
SETTINGS index_granularity = 8192
