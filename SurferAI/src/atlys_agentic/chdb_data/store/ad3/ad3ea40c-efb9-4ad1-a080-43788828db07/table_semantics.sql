ATTACH TABLE _ UUID '25797edd-259f-4512-94ec-aafa17dadc39'
(
    `table_name` String,
    `spec_id` String,
    `description` String,
    `concepts` String,
    `embedding` Array(Float32),
    `version` UInt16,
    `created_at` DateTime
)
ENGINE = MergeTree
ORDER BY (table_name, version)
SETTINGS index_granularity = 8192
