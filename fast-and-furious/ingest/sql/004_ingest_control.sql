-- =============================================================================
-- 004_ingest_control.sql — pipeline evidence and rejected rows
--
-- "No pipeline evidence, no credit." These two tables are how an answer is
-- traced back to the run that produced it.
-- =============================================================================

-- One row per INSERT batch actually sent. Written by the producer AFTER the
-- data insert acknowledges, so a row here means the data is durable.
--
-- Rows are small and arrive one at a time — exactly the shape client-side
-- batching cannot fix. The producer writes this table with async_insert=1 and
-- wait_for_async_insert=1 so ClickHouse buffers server-side and still confirms
-- durability before the call returns.
-- [official: insert-async-small-batches]
CREATE TABLE IF NOT EXISTS {{db}}.ingest_batches
(
    ingest_batch_id   UUID,
    run_id            UUID     COMMENT 'Groups every batch of one pipeline invocation',
    source            LowCardinality(String) COMMENT 'e.g. csv:ch-hackathon-raw-data.csv | generator',
    source_fingerprint String  DEFAULT '' COMMENT 'SHA-256 of the source file, or the generator seed',
    batch_ordinal     UInt32   COMMENT 'Deterministic: row_number / batch_size',
    dedup_token       String   COMMENT 'insert_deduplication_token used for this batch',

    row_count         UInt32,
    rejected_count    UInt32   DEFAULT 0,
    bytes_estimate    UInt64   DEFAULT 0,
    first_event_time  DateTime64(3, 'UTC'),
    last_event_time   DateTime64(3, 'UTC'),

    started_at        DateTime64(3, 'UTC'),
    completed_at      DateTime64(3, 'UTC'),
    duration_ms       UInt32,
    attempt           UInt8    DEFAULT 1,
    -- Three states, not two. 'unknown' exists because a cancelled Send is not a
    -- failed write: clickhouse-go closes the socket on context cancel and
    -- returns ctx.Err(), discarding the server's reply, so the block may have
    -- committed. On 2026-08-01 all three batches recorded 'failed' had every
    -- one of their rows present in events_raw (3/3, 24/24, 51/51). Recording
    -- those as 'failed' made the ledger under-report by 78 rows — a silent
    -- disagreement between the audit layer and the table it describes.
    status            Enum8('ok' = 1, 'failed' = 2, 'unknown' = 3) DEFAULT 'ok',
    error             String   DEFAULT ''
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(started_at)
ORDER BY (source, run_id, batch_ordinal)
SETTINGS
    -- Missing on the live service until 2026-08-02. This is the ledger the
    -- 4.3x row-attribution audit was reconciled against, so a duplicated row
    -- here corrupts the evidence layer rather than the answer — it would make a
    -- batch look like it declared twice as many rows as it carried.
    --
    -- Control-plane rows are written one at a time through the async path
    -- (chx.Client forces async_insert for ingest_batches / ingest_rejects
    -- because single rows cannot be batched client-side). On that path
    -- insert_deduplication_token is INERT unless async_insert_deduplicate = 1,
    -- which loader.go now sets explicitly — these windows are what that setting
    -- then consults.
    non_replicated_deduplication_window = 1000,
    replicated_deduplication_window = 1000,
    replicated_deduplication_window_seconds = 2592000
COMMENT 'Ingest audit log: one row per acknowledged INSERT batch.';

-- CREATE TABLE IF NOT EXISTS above is a no-op against a database that already
-- has this table, so neither the 'unknown' state nor the settings above would
-- ever reach one. Widening an Enum8 by adding a value is metadata-only —
-- existing rows keep their encoding.
ALTER TABLE {{db}}.ingest_batches
    MODIFY COLUMN status Enum8('ok' = 1, 'failed' = 2, 'unknown' = 3) DEFAULT 'ok';

ALTER TABLE {{db}}.ingest_batches
    MODIFY SETTING
        non_replicated_deduplication_window = 1000,
        replicated_deduplication_window = 1000,
        replicated_deduplication_window_seconds = 2592000;


-- Rows the producer refused to land in events_raw.
--
-- A malformed row is quarantined, never silently dropped: on the unseen day a
-- non-zero, unexplained reject count is the difference between "our answer is
-- wrong" and "our answer excludes 12 rows, here they are, here is why".
CREATE TABLE IF NOT EXISTS {{db}}.ingest_rejects
(
    run_id       UUID,
    source       LowCardinality(String),
    source_line  UInt64   COMMENT '1-based line number in the source file, 0 for generated rows',
    reason       LowCardinality(String) COMMENT 'bad_session_id | bad_user_id | bad_content_id | bad_timestamp | bad_column_count | missing_column',
    detail       String,
    raw_row      String   COMMENT 'The offending row, verbatim',
    rejected_at  DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(rejected_at)
ORDER BY (source, reason, run_id, source_line)
TTL toDateTime(rejected_at) + INTERVAL 30 DAY
SETTINGS
    -- Missing on the live service until 2026-08-02. Same async single-row write
    -- path as ingest_batches above. A duplicated reject inflates the count that
    -- the unseen-day narrative depends on — "our answer excludes 12 rows, here
    -- they are" is only evidence if 12 is 12.
    non_replicated_deduplication_window = 1000,
    replicated_deduplication_window = 1000,
    replicated_deduplication_window_seconds = 2592000
COMMENT 'Quarantine for rows that failed validation. TTL 30d — this is a debugging aid, not a system of record.';

ALTER TABLE {{db}}.ingest_rejects
    MODIFY SETTING
        non_replicated_deduplication_window = 1000,
        replicated_deduplication_window = 1000,
        replicated_deduplication_window_seconds = 2592000;
