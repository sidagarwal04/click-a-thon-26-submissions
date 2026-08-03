ATTACH TABLE _ UUID 'b522b2f7-f942-4e6b-b968-e3528c292055'
(
    `table` String,
    `ddl` String,
    `columns_json` String,
    `spec_id` String,
    `version` UInt16,
    `created_at` DateTime
)
ENGINE = MergeTree
ORDER BY (`table`, version)
SETTINGS index_granularity = 8192
