-- Control-plane schema. Postgres, not ClickHouse — this is low-volume,
-- relational, UI-editable config; ClickHouse stays the analytical engine
-- (ad_events, metrics_hourly, segment_metrics_hourly, anomalies,
-- segment_anomalies all remain there — see sql/*.sql).
--
-- raw_measures is NOT a table here — it's hardcoded in
-- lib/registry/rawMeasures.ts. Adding a raw measure means new raw data
-- landing in ad_events/metrics_hourly, inherently an engineering task
-- (migration + rollup change), not a config row.

CREATE TABLE IF NOT EXISTS metric_definitions (
  id             TEXT PRIMARY KEY,
  label          TEXT NOT NULL,
  kind           TEXT NOT NULL CHECK (kind IN ('volume', 'ratio')),
  numerator_id   TEXT NOT NULL CHECK (numerator_id IN ('requests','fills','impressions','clicks','revenue')),
  denominator_id TEXT CHECK (denominator_id IN ('requests','fills','impressions','clicks','revenue')),
  scale          NUMERIC NOT NULL DEFAULT 1,
  requires_fill  BOOLEAN NOT NULL DEFAULT false,
  created_by     TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ratio_needs_denominator CHECK (kind = 'volume' OR denominator_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS dimension_definitions (
  id                 TEXT PRIMARY KEY,
  label              TEXT NOT NULL,
  source             TEXT NOT NULL CHECK (source IN ('event_column', 'joined_table')),
  join_table         TEXT CHECK (join_table IN ('apps','geo_device','advertisers')),
  join_key           TEXT CHECK (join_key IN ('app_id','geo_device_id','advertiser_id')),
  column_name        TEXT NOT NULL,
  requires_fill      BOOLEAN NOT NULL DEFAULT false,
  cardinality_hint   INTEGER NOT NULL,
  enabled_for_sweep  BOOLEAN NOT NULL DEFAULT true,
  CONSTRAINT joined_needs_join_info CHECK (
    source = 'event_column' OR (join_table IS NOT NULL AND join_key IS NOT NULL)
  )
);

-- Discovery cache (see lib/registry/introspect.ts). Populated by re-running
-- the introspection job against ClickHouse's system.columns; a row here is
-- a CANDIDATE, not yet usable — promoting one means inserting the
-- corresponding metric_definitions/dimension_definitions row by hand (or
-- via an admin action), a deliberate human-in-the-loop step.
CREATE TABLE IF NOT EXISTS discovered_dimensions (
  ch_table      TEXT NOT NULL,
  ch_column     TEXT NOT NULL,
  ch_type       TEXT NOT NULL,
  join_key      TEXT,
  discovered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  promoted      BOOLEAN NOT NULL DEFAULT false,
  PRIMARY KEY (ch_table, ch_column)
);

-- The only table a PM edits, via the UI.
CREATE TABLE IF NOT EXISTS monitors (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name          TEXT NOT NULL,
  metric_id     TEXT NOT NULL REFERENCES metric_definitions(id),
  dimension_id  TEXT REFERENCES dimension_definitions(id), -- null = global
  methods       JSONB NOT NULL, -- [{"method":"trend_seasonal","zThreshold":2.5,"enabled":true}, ...]
  webhook_url   TEXT,
  owner         TEXT,
  enabled       BOOLEAN NOT NULL DEFAULT true,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
