-- Raw landing table: mirrors the feed, replayable source of truth.
-- The live-demo replay and the unseen slice both land here; the MV cascade
-- (enrichment -> rollup) fans out from this table automatically.
-- No Nullable anywhere: source uses '' as its own sentinel (advertiser_id on unfilled).

CREATE TABLE IF NOT EXISTS rca.ad_events
(
    event_time    DateTime('UTC') CODEC(Delta, ZSTD),
    app_id        LowCardinality(String),
    geo_device_id LowCardinality(String),
    advertiser_id LowCardinality(String),          -- '' = request not filled
    ad_format     LowCardinality(String),
    is_filled     UInt8,
    is_impression UInt8,
    is_click      UInt8,
    revenue       Float64,
    dataset       LowCardinality(String) DEFAULT 'main'   -- provenance: 'main' | 'unseen'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(event_time)
ORDER BY event_time;
