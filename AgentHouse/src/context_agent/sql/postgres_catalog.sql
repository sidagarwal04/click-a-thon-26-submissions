-- Context layer only — see context_agent/TABLES.md
-- Meta tables: instrumentation_agent/sql/postgres_meta_registry.sql
-- Applied by: uv run python context_agent/scripts/init_schema.py

CREATE TABLE IF NOT EXISTS context_versions (
    context_version TEXT NOT NULL PRIMARY KEY,
    parent_version  TEXT REFERENCES context_versions (context_version),
    source          TEXT NOT NULL,
    feature_id      TEXT,
    is_current      BOOLEAN NOT NULL DEFAULT false,
    summary         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS context_versions_one_current
    ON context_versions (is_current)
    WHERE is_current = true;

CREATE TABLE IF NOT EXISTS context_items (
    context_version TEXT NOT NULL REFERENCES context_versions (context_version),
    kind            TEXT NOT NULL CHECK (
        kind IN ('entity', 'metric', 'join', 'funnel_step', 'issue', 'contradiction')
    ),
    item_key        TEXT NOT NULL,
    label           TEXT,
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (context_version, kind, item_key)
);

CREATE INDEX IF NOT EXISTS context_items_kind_idx ON context_items (context_version, kind);
