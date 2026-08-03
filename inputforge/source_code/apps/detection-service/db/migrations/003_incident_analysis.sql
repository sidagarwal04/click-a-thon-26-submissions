-- Durable output from the on-demand anomaly analyst. ClickHouse remains the
-- evidence store; Postgres owns the low-volume agent result and its audit trace.

CREATE TABLE IF NOT EXISTS incident_analysis (
  incident_id        TEXT PRIMARY KEY,
  metric             TEXT NOT NULL CHECK (metric IN (
    'requests', 'revenue', 'fill_rate', 'render_rate', 'ctr', 'ecpm', 'rpr'
  )),
  start_time         TIMESTAMPTZ NOT NULL,
  end_time           TIMESTAMPTZ NOT NULL,
  status             TEXT NOT NULL CHECK (status IN (
    'running', 'completed', 'failed'
  )),
  verdict            JSONB,
  slice_and_dice     JSONB,
  tool_calls         JSONB NOT NULL DEFAULT '[]'::jsonb,
  agent_session_id   TEXT,
  error              TEXT,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at       TIMESTAMPTZ,
  CONSTRAINT completed_analysis_has_result CHECK (
    status <> 'completed' OR (verdict IS NOT NULL AND slice_and_dice IS NOT NULL)
  )
);

CREATE INDEX IF NOT EXISTS incident_analysis_status_idx
  ON incident_analysis (status, updated_at DESC);
