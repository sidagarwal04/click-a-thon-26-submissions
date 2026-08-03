
CREATE TABLE IF NOT EXISTS meta_features (
  feature_id TEXT PRIMARY KEY,
  -- [{"event_name","journey_order","ch_table"}, ...]
  journey JSONB NOT NULL DEFAULT '[]',
  spec_path TEXT NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS meta_events (
  event_name TEXT PRIMARY KEY,
  -- Comma-separated feature ids that use this event (no FK — multi-feature).
  feature_id TEXT NOT NULL,
  ch_table TEXT NOT NULL,
  columns JSONB NOT NULL DEFAULT '{}',
  -- updated = freshly registered / feature appended; done = already linked
  status TEXT NOT NULL DEFAULT 'done',
  registered_at TIMESTAMPTZ DEFAULT now()
);

-- Drop legacy columns / indexes / FK if an older registry already exists.
ALTER TABLE meta_features DROP COLUMN IF EXISTS status;
ALTER TABLE meta_features DROP COLUMN IF EXISTS events_path;
ALTER TABLE meta_features DROP COLUMN IF EXISTS run_id;
ALTER TABLE meta_features DROP COLUMN IF EXISTS event_count;
ALTER TABLE meta_features DROP COLUMN IF EXISTS error;

DROP INDEX IF EXISTS idx_meta_events_feature_journey;
ALTER TABLE meta_events DROP COLUMN IF EXISTS journey_order;
ALTER TABLE meta_events DROP COLUMN IF EXISTS row_count;
ALTER TABLE meta_events DROP COLUMN IF EXISTS run_id;

ALTER TABLE meta_events ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'done';

-- feature_id is a CSV of feature ids; drop single-feature FK if present.
ALTER TABLE meta_events DROP CONSTRAINT IF EXISTS meta_events_feature_id_fkey;

CREATE INDEX IF NOT EXISTS idx_meta_events_feature
  ON meta_events (feature_id);
