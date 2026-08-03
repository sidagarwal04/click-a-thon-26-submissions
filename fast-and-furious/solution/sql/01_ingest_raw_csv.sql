-- Stream the CSV through clickhouse-client; the server does not need filesystem
-- access to the source file.
--
-- clickhouse-client \
--   --param_ingest_batch_id='00000000-0000-0000-0000-000000000001' \
--   --param_ingest_version_base=1000000000 \
--   --param_insert_deduplication_token='raw-15ce6df7-v1' \
--   --query "$(cat solution/sql/01_ingest_raw_csv.sql)" \
--   < ch-hackathon-raw-data.csv
--
-- Retry with byte-identical data, the same row order, block settings, and token.
-- Production producers should use Native blocks of 10K-100K rows (50K target).
-- Source event_timestamp/session_start_epoch remain Int64 Unix epoch milliseconds.
-- Normalize that absolute instant once into DateTime64(3,'UTC'); never add a
-- local offset during ingestion. Local rendering is a query/UI concern.

INSERT INTO sonyliv.raw_events
(
    ingest_batch_id,
    ingest_version,
    source_row_hash,
    video_session_id,
    user_id,
    content_id,
    event_type,
    event,
    event_time,
    session_start_time,
    platform,
    app_version,
    country,
    audio_language,
    subtitle_language,
    player_version
)
SELECT
    {ingest_batch_id:UUID},
    {ingest_version_base:UInt64} + rowNumberInAllBlocks(),
    reinterpretAsUInt128(sipHash128(
        content_id,
        video_session_id,
        user_id,
        event_type,
        event,
        event_timestamp,
        platform,
        app_version,
        country,
        audio_language,
        subtitle_language,
        player_version,
        session_start_epoch
    )),
    video_session_id,
    user_id,
    toInt32(content_id),
    event_type,
    event,
    fromUnixTimestamp64Milli(event_timestamp, 'UTC'),
    fromUnixTimestamp64Milli(session_start_epoch, 'UTC'),
    platform,
    app_version,
    country,
    audio_language,
    subtitle_language,
    player_version
FROM input(
    'content_id Int64,
     video_session_id String,
     user_id String,
     event_type String,
     event String,
     event_timestamp Int64,
     platform String,
     app_version String,
     country String,
     audio_language String,
     subtitle_language String,
     player_version String,
     session_start_epoch Int64'
)
SETTINGS
    insert_deduplication_token = {insert_deduplication_token:String},
    async_insert = 0,
    max_threads = 1,
    input_format_parallel_parsing = 0
FORMAT CSVWithNames;
