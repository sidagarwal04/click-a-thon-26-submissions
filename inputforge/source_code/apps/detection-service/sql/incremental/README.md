# Leftovers from the incremental (hour-tick) design

Everything detection-related that used to live here has been superseded by
`sql/mv/` (reactive + refreshable materialized views — see its README) and
deleted, including `cusum`, `ewma_fast`/`ewma_slow`, and `basic` — all
removed from the pipeline entirely, not just left dormant.

What's left here:

- `07_analyst_view.sql` — a plain `VIEW` (not materialized), one-time
  `CREATE VIEW` for `inmobi.hourly_analyst_view`, an analyst-friendly wide
  view over `metrics_hourly_v` / `metric_zr_hourly` / `anomalies`. Still run
  by `runSetup()`.

Segment-level drilldown (`../segment/`) is now also MV-driven — only
`segment/01_schema.sql` remains in `../segment/` (table + view
definitions); the detection logic itself moved to `sql/mv/08_mv_segment_detect_global.sql`.
