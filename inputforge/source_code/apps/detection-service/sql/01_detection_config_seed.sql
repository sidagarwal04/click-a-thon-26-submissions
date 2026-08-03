-- Seed data for inmobi.detection_config (table created in 00_schema.sql).
-- Run once via setup, and again any time these values change — this table
-- IS the live-editable config (see 00_schema.sql's comment), so in
-- production you'd more likely UPDATE a row directly than re-run this file;
-- this is the reproducible starting point / reset-to-known-state path.
--
-- These were InMobi's original recall-first defaults (2.5 flat across every
-- metric for trend_seasonal), NOT independently validated numbers. We
-- attempted tuning against the external NAB benchmark and explicitly
-- disproved generalization via leave-one-out cross-validation (F1 swung
-- 0.01-0.79 across folds — see click-a-thon-2026/InMobi/detection/cv_nab.py
-- in the sibling repo this pipeline was designed in). Do not treat any
-- threshold below as validated; the honest position is cross-method
-- agreement + duration is the one defensible signal, not any single z cutoff.
--
-- trend_seasonal thresholds below are now per-metric, calibrated off each
-- metric's OWN historical noise floor rather than one flat number:
--   threshold = median(|zr|) + 3 * 1.4826 * MAD(|zr|), per metric, computed
--   over inmobi.metric_zr_hourly's full history.
-- MAD (median absolute deviation) has a ~50% breakdown point, so it isolates
-- a metric's real background noise level even with real incidents mixed
-- into the sample (this data's incidents cover at most ~14% of hours,
-- well under that) — unlike a raw percentile, which a large incident
-- visibly skews (checked: fill_rate's raw p95 comes out at 4.89, because
-- its 3-day incident alone is ~14% of all hours). This is a genuine,
-- incident-agnostic property of each metric (fill_rate/requests/revenue run
-- naturally quiet, median|zr| ~0.5-0.6; ctr/ecpm/render_rate/rpr run
-- naturally noisier, median|zr| ~0.85-0.95) — NOT reverse-engineered from
-- any one known incident's shape, and specifically NOT tuned to make the
-- 6/18-6/20 ecpm window look contiguous (the calibrated ecpm threshold
-- actually went UP, from 2.5 to 3.3 — the opposite of what would have
-- "fixed" that window; loosening ecpm specifically would have been
-- borrowing ctr/render_rate/rpr's higher noise floor, not correcting
-- anything real about ecpm).
-- All z_threshold values are clamped to a 2.5 floor — the MAD-calibrated
-- fit put revenue and fill_rate below that (2.1, 2.2), but 2.5 is the
-- recall-first baseline every other metric already sits at or above; going
-- lower than that for any metric was judged too permissive regardless of
-- what its own noise floor calibrated to.
--
-- day_level uses a 3-sigma threshold at the completed-day grain. CTR and
-- render_rate use a stricter 4-sigma threshold for both hourly methods: this
-- deployment has page-only routing, so the lower recall-first thresholds
-- create too many isolated notifications. Each hour/day still qualifies on
-- its own; this is a per-unit threshold, not a persistence rule.
--
-- cusum, ewma_fast/ewma_slow, and basic have all been removed entirely (not
-- just disabled) — see 00_schema.sql's comment near where cusum/ewma's
-- state tables used to be. `basic` (a Datadog-inspired trailing-quantile
-- band) never correlated with known incident windows in full-history
-- simulation (634 flags, 87% not caught by any other method) — dead weight,
-- not a dormant asset. No rows for any of the three below; the MV pipeline
-- no longer references any of them.

TRUNCATE TABLE inmobi.detection_config;

INSERT INTO inmobi.detection_config (metric, method, z_threshold, enabled) VALUES
  ('requests',    'trend_seasonal', 2.5, 1),
  ('revenue',     'trend_seasonal', 2.5, 1),
  ('fill_rate',   'trend_seasonal', 2.5, 1),
  ('fill_rate',   'proportion',     3.0, 1),
  ('render_rate', 'trend_seasonal', 4.0, 1),
  ('render_rate', 'proportion',     4.0, 1),
  ('ctr',         'trend_seasonal', 4.0, 1),
  ('ctr',         'proportion',     4.0, 1),
  ('ecpm',        'trend_seasonal', 3.3, 1),
  ('rpr',         'trend_seasonal', 3.4, 1),
  ('requests',    'day_level',      3.0, 1),
  ('revenue',     'day_level',      3.0, 1),
  ('fill_rate',   'day_level',      3.0, 1),
  ('render_rate', 'day_level',      3.0, 1),
  ('ctr',         'day_level',      3.0, 1),
  ('ecpm',        'day_level',      3.0, 1),
  ('rpr',         'day_level',      3.0, 1);

-- CTR and render rate have no meaningful short-lag autocorrelation after
-- seasonal adjustment in the background data. Keep their anomaly rows for
-- Stage 2 correlation and diagnosis, but do not let them open a page-only
-- incident. RPR and total revenue remain incident-enabled: their sustained
-- movements are temporally correlated and align with business-impact dips.
ALTER TABLE inmobi.detection_config
  UPDATE incident_enabled = if(metric IN ('ctr', 'render_rate'), 0, 1)
  WHERE 1
  SETTINGS mutations_sync = 2;

-- Raw binomial variance understates real-world day-to-day noise
-- (overdispersion). fill_rate retains the recall-first 3-sigma proportion
-- threshold; CTR/render_rate use 4 sigma because every reportable incident
-- pages and isolated false positives are not routable to a lower severity.
