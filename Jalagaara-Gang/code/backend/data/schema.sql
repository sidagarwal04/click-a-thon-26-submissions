-- Lane A: ClickHouse schema. Run top-to-bottom against your Cloud service.
-- Ids as LowCardinality(String); is_* as UInt8; revenue Float64; NAM (not NA) for North America.

CREATE TABLE IF NOT EXISTS ad_events (
    event_time     DateTime,
    app_id         LowCardinality(String),
    geo_device_id  LowCardinality(String),
    advertiser_id  LowCardinality(String),   -- empty on unfilled requests
    ad_format      LowCardinality(String),
    is_filled      UInt8,
    is_impression  UInt8,
    is_click       UInt8,
    revenue        Float64
) ENGINE = MergeTree
ORDER BY (event_time, app_id);

CREATE TABLE IF NOT EXISTS apps_dim (
    app_id         LowCardinality(String),
    category       LowCardinality(String),
    publisher_tier LowCardinality(String)
) ENGINE = MergeTree ORDER BY app_id;

CREATE TABLE IF NOT EXISTS advertisers_dim (
    advertiser_id LowCardinality(String),
    vertical      LowCardinality(String),
    campaign_type LowCardinality(String)
) ENGINE = MergeTree ORDER BY advertiser_id;

CREATE TABLE IF NOT EXISTS geo_device_dim (
    geo_device_id LowCardinality(String),
    region        LowCardinality(String),
    country       LowCardinality(String),
    device_model  LowCardinality(String),
    os_version    LowCardinality(String)
) ENGINE = MergeTree ORDER BY geo_device_id;

-- Denormalized analytical table: every drill-down is a single-table GROUP BY, no joins in recursion.
CREATE TABLE IF NOT EXISTS events_full
ENGINE = MergeTree
ORDER BY (event_time, country, os_version, app_id)
AS
SELECT
    e.event_time AS event_time, e.app_id AS app_id, e.geo_device_id AS geo_device_id,
    e.advertiser_id AS advertiser_id, e.ad_format AS ad_format,
    e.is_filled AS is_filled, e.is_impression AS is_impression, e.is_click AS is_click,
    e.revenue AS revenue,
    a.category AS category, a.publisher_tier AS publisher_tier,
    adv.vertical AS vertical, adv.campaign_type AS campaign_type,
    g.region AS region, g.country AS country, g.device_model AS device_model, g.os_version AS os_version
FROM ad_events e
LEFT JOIN apps_dim a USING (app_id)
LEFT JOIN advertisers_dim adv USING (advertiser_id)
LEFT JOIN geo_device_dim g USING (geo_device_id);

-- Hourly rollup for fast baselines/detection. Ratios stay sum/sum at read time.
CREATE TABLE IF NOT EXISTS hourly_summary
ENGINE = SummingMergeTree
ORDER BY (hour, region, country, os_version, device_model, ad_format, category, publisher_tier, vertical, campaign_type, app_id, advertiser_id)
AS
SELECT
    toStartOfHour(event_time) AS hour,
    region, country, os_version, device_model, ad_format,
    category, publisher_tier, vertical, campaign_type, app_id, advertiser_id,
    count()            AS requests,
    sum(is_filled)     AS fills,
    sum(is_impression) AS impressions,
    sum(is_click)      AS clicks,
    sum(revenue)       AS revenue
FROM events_full
GROUP BY ALL;

-- ---------------------------------------------------------------------------
-- Unseen slice (Jul 6-10): its OWN table set, because the dimension CSVs shipped with it
-- reuse the SAME ids with regenerated attributes -- app_00123 can be finance in June and
-- gaming in July. Mixing them into the dev tables would silently misattribute segments.
--
-- Structure is CLONED from the dev tables (CREATE TABLE ... AS <table> copies columns +
-- engine + sort order), so the two sets cannot drift apart. Unlike the dev derived tables
-- these start EMPTY: the stream fills them batch by batch.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ad_events_unseen        AS ad_events;
CREATE TABLE IF NOT EXISTS apps_dim_unseen         AS apps_dim;
CREATE TABLE IF NOT EXISTS advertisers_dim_unseen  AS advertisers_dim;
CREATE TABLE IF NOT EXISTS geo_device_dim_unseen   AS geo_device_dim;
CREATE TABLE IF NOT EXISTS events_full_unseen      AS events_full;
CREATE TABLE IF NOT EXISTS hourly_summary_unseen   AS hourly_summary;

-- What the streaming detector has already looked at: one row per (hour, metric) scored.
-- A separate table rather than a flag column on hourly_summary_unseen, because that rollup is
-- a SummingMergeTree -- it SUMS numeric columns on merge, so an `analyzed UInt8` would add up
-- across parts (1+1=2) instead of staying a flag, and the rollup holds one row per dimension
-- combination per hour, not one row per analysis. Keyed (hour, metric) so a resumed or
-- re-run stream can skip what it has already scored, and so "was this hour ever inferred on?"
-- is answerable in SQL rather than from job memory that dies with the process.
CREATE TABLE IF NOT EXISTS stream_analysis (
    hour        DateTime,
    metric      LowCardinality(String),
    method      LowCardinality(String),
    analyzed_at DateTime,
    detected    UInt8,
    score       Float64,
    pct_delta   Float64,
    observed    Float64,
    expected    Float64,
    investigation_id String DEFAULT ''    -- set when a hit produced a full bundle
) ENGINE = ReplacingMergeTree(analyzed_at)
ORDER BY (hour, metric);

-- ---------------------------------------------------------------------------
-- JAL-73: system-of-record tables. ClickHouse stays the single datastore, so
-- investigation history is queryable in SQL and survives restarts.
--
-- Split in two: `bundles` holds the actual evidence (everything detection +
-- decomposition + drill-down + narration produced — the dashboard reads
-- straight from here); `investigations` is a lean session/tracking record
-- (trace id, chat session, timestamps) that references its evidence by id
-- rather than duplicating it. bundle_id == investigation_id today (one
-- investigation produces exactly one bundle), kept as its own column/FK
-- rather than reused so the two tables stay conceptually independent.
-- ---------------------------------------------------------------------------

-- One row per DETECTION RUN — the traceability record. Anomalies are rare, so
-- most rows are "checked, normal" (is_anomaly=0, stats only); when a run does
-- detect (is_anomaly=1) the row carries the full drilled-down evidence. Keyed
-- ReplacingMergeTree on investigation_id so POST /narrate can rewrite the row
-- in place (latest updated_at wins). Read with FINAL — tens of rows, not
-- millions. Flattened columns (metric, observed/expected/etc, primary_factor,
-- localized_segment, ruled_out_summary) let the dashboard render a card
-- without parsing `bundle`; `bundle` itself is the full schema-valid
-- EvidenceBundle JSON, the source of truth for GET /bundle/{id}.
CREATE TABLE IF NOT EXISTS bundles (
    investigation_id  String,
    created_at        DateTime,
    updated_at        DateTime,
    window_start      DateTime,
    window_end        DateTime,
    metric            LowCardinality(String),
    direction         LowCardinality(String) DEFAULT '',   -- drop | spike
    observed          Float64 DEFAULT 0,
    expected          Float64 DEFAULT 0,
    pct_delta         Float64 DEFAULT 0,
    score             Float64 DEFAULT 0,
    is_anomaly        UInt8,                      -- 0 = checked & normal (most rows), 1 = anomaly
    primary_factor    LowCardinality(String) DEFAULT '',
    localized_segment String DEFAULT '',          -- JSON object, e.g. {"os_version":"Android 15"}
    ruled_out_count   UInt8 DEFAULT 0,
    ruled_out_summary String DEFAULT '',          -- comma-joined hypothesis names, for a quick tooltip
    narrative         String DEFAULT '',
    narrated          UInt8 DEFAULT 0,
    trace_url         String DEFAULT '',
    bundle            String                      -- full EvidenceBundle JSON
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY investigation_id;

-- One row per investigation run. References its evidence via bundle_id rather
-- than storing it — join to `bundles` for the numbers, or GET /bundle/{id}.
CREATE TABLE IF NOT EXISTS investigations (
    investigation_id  String,
    bundle_id         String,                     -- FK -> bundles.investigation_id
    trace_id          String DEFAULT '',          -- Langfuse trace, survives across HTTP calls
    session_id        String DEFAULT '',          -- chat contextId, empty for direct API calls
    created_at        DateTime,
    updated_at        DateTime
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY investigation_id;

-- Snapshot of a finished investigation's Langfuse trace, reshaped for the dashboard drawer
-- (see narrator/trace_read.py). Written the first time the trace is read, so a trace stays
-- readable forever even if Langfuse is reset or unreachable — Langfuse owns the live trace,
-- this owns the history.
CREATE TABLE IF NOT EXISTS trace_views (
    investigation_id String,
    created_at       DateTime,
    view             String                      -- JSON: {total_ms, scores, steps[]}
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY investigation_id;

-- Chat sessions (kangavault contextId pattern). Title is generated lazily.
CREATE TABLE IF NOT EXISTS chat_sessions (
    context_id String,
    title      String DEFAULT '',
    created_at DateTime,
    updated_at DateTime
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY context_id;

-- Append-only conversation history. DateTime64(3) so turns within the same
-- second keep their order.
CREATE TABLE IF NOT EXISTS chat_turns (
    context_id String,
    role       LowCardinality(String),            -- user | assistant
    message    String,
    created_at DateTime64(3)
) ENGINE = MergeTree
ORDER BY (context_id, created_at);
