-- Reproduces the 7 metrics and 7 dimensions currently hand-swept in
-- sql/04, sql/08-09 as real registry data — same content as
-- lib/registry/seed.ts, now as the actual source of truth once Postgres is
-- wired up (lib/registry/repo.ts reads this table, not the in-memory array).

INSERT INTO metric_definitions (id, label, kind, numerator_id, denominator_id, scale, requires_fill) VALUES
  ('requests',    'Requests',            'volume', 'requests', NULL,          1,    false),
  ('revenue',     'Revenue',             'volume', 'revenue',  NULL,          1,    false),
  ('fill_rate',   'Fill Rate',           'ratio',  'fills',    'requests',    1,    false),
  ('render_rate', 'Render Rate',         'ratio',  'impressions', 'fills',    1,    false),
  ('ctr',         'CTR',                 'ratio',  'clicks',   'impressions', 1,    false),
  ('ecpm',        'eCPM',                'ratio',  'revenue',  'impressions', 1000, false),
  ('rpr',         'Revenue per Request', 'ratio',  'revenue',  'requests',    1,    false)
ON CONFLICT (id) DO NOTHING;

INSERT INTO dimension_definitions (id, label, source, join_table, join_key, column_name, requires_fill, cardinality_hint, enabled_for_sweep) VALUES
  ('ad_format',      'Ad Format',      'event_column',  NULL,           NULL,               'ad_format',      false, 5,    true),
  ('category',       'App Category',   'joined_table',  'apps',         'app_id',           'category',       false, 7,    true),
  ('publisher_tier', 'Publisher Tier', 'joined_table',  'apps',         'app_id',           'publisher_tier', false, 3,    true),
  ('region',         'Region',         'joined_table',  'geo_device',   'geo_device_id',    'region',         false, 5,    true),
  ('country',        'Country',        'joined_table',  'geo_device',   'geo_device_id',    'country',        false, 16,   true),
  ('vertical',       'Advertiser Vertical',   'joined_table', 'advertisers', 'advertiser_id', 'vertical',      true,  7,    true),
  ('campaign_type',  'Campaign Type',  'joined_table',  'advertisers',  'advertiser_id',    'campaign_type',  true,  3,    true)
ON CONFLICT (id) DO NOTHING;

-- The 2 dimensions introspection found but nobody promoted yet — inserted
-- into the discovery cache as unpromoted, exactly the state the real
-- introspection job would leave them in.
INSERT INTO discovered_dimensions (ch_table, ch_column, ch_type, join_key, promoted) VALUES
  ('geo_device', 'device_model', 'LowCardinality(String)', 'geo_device_id', false),
  ('geo_device', 'os_version',   'LowCardinality(String)', 'geo_device_id', false)
ON CONFLICT (ch_table, ch_column) DO NOTHING;
