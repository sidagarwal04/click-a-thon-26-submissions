-- BRONZE -- exactly as delivered, never edited.
-- Types mirror the CSV: event_timestamp stays epoch-ms Int64 here and is
-- converted to DateTime64(3) in silver, so bronze remains a faithful copy.
CREATE TABLE IF NOT EXISTS bronze_events
(
    content_id          String,
    video_session_id    String,
    user_id             String,
    event_type          LowCardinality(String),
    event               LowCardinality(String),
    event_timestamp     Int64,
    platform            LowCardinality(String),
    app_version         LowCardinality(String),
    country             LowCardinality(String),
    audio_language      LowCardinality(String),
    subtitle_language   LowCardinality(String),
    player_version      LowCardinality(String),
    session_start_epoch Int64
)
ENGINE = MergeTree
ORDER BY (video_session_id, event_timestamp);

CREATE TABLE IF NOT EXISTS bronze_content
(
    content_id String,
    title      String,
    video_type LowCardinality(String),
    category   LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY content_id;
