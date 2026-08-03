# Detection pipeline (materialized views)

Two execution models, deliberately:

- **Reactive** — fires on `INSERT` into `inmobi.ad_events` directly. Used
  only for the single-hop rollups: `01_mv_metrics_hourly.sql` and
  `07_mv_segment_metrics_hourly.sql`. Proven reliable in production, even
  under a large bulk load.
- **Refreshable** — reschedules itself inside ClickHouse
  (`REFRESH EVERY ...`), recomputes full history, and atomically REPLACEs
  its target table on every cycle. Used for everything downstream of the
  rollups: `02_mv_zr_hourly.sql`, `03_mv_detect_global.sql`,
  `06_mv_noise_baseline_daily.sql`, `08_mv_segment_detect_global.sql`,
  `09_mv_segment_zr_hourly.sql`, `10_mv_segment_incident_evidence.sql`,
  `12_mv_incidents.sql`.

## Why not reactive all the way down

It was, originally. Found in production: a **cascaded** reactive MV — one
sourced from another MV's target table, not from `ad_events` directly —
does not reliably fire on a large bulk `INSERT`. A real incident: after a
multi-day backfill into `ad_events`, `mv_metrics_hourly` (single hop, direct
off `ad_events`) had correctly processed the whole range, but
`mv_zr_hourly` (which cascaded off `metrics_hourly`, not `ad_events`) had
silently stopped days earlier — no error, no partial output, just nothing
past a certain point. The query itself was correct (verified by running it
manually); the trigger simply never propagated through the second hop for
that block.

Refreshable MVs don't have this failure mode because they don't depend on
trigger propagation at all — they run on their own timer and read whatever
is currently in their source tables. That's why every cascaded stage is
refreshable now, and why the two rollups that stayed reactive are
specifically the ones that are *not* cascaded (a single hop off `ad_events`
itself, empirically reliable).

## The chain

1. `01_mv_metrics_hourly.sql` — reactive, `ad_events` → `metrics_hourly`.
2. `02_mv_zr_hourly.sql` — refreshable (`REFRESH EVERY 10 MINUTE`), full
   recompute of the seasonal z-residual → `metric_zr_hourly`. No `touched`
   scoping anymore — a refreshable MV has no concept of "just this block,"
   it always recomputes the whole series. Reads `metric_noise_baseline` via
   `argMax`, so needs (6) to have refreshed at least once first.
3. `03_mv_detect_global.sql` — refreshable, `DEPENDS ON mv_zr_hourly`,
   consolidates `trend_seasonal` + `proportion` + `day_level` into one query
   → `anomalies`. One MV, not three: a refreshable MV without `APPEND` does
   a full atomic REPLACE of its target, so multiple independent refreshable
   MVs writing to the same table would each wipe out what the others wrote.
   Every method that writes to `anomalies` has to live in this single
   query. `DEPENDS ON` means this only runs after `mv_zr_hourly`'s own
   refresh has actually completed, not on an independent same-cadence timer
   that could race it.
6. `06_mv_noise_baseline_daily.sql` — refreshable (`REFRESH EVERY 1 DAY`),
   the pooled residual-noise baseline `trend_seasonal` shrinks toward.
7. `07_mv_segment_metrics_hourly.sql` — reactive, `ad_events` (joined
   against `apps`/`geo_device`/`advertisers`) → `segment_metrics_hourly`.
8. `08_mv_segment_detect_global.sql` — refreshable, consolidates segment
   `trend_seasonal` (volume + ratios) + `proportion` into one query →
   `segment_anomalies`. No `DEPENDS ON` — segment detection reads
   `segment_metrics_hourly_v` directly (not through a zr-style intermediate
   table), and (7) is reactive-and-reliable being a single hop, so this just
   runs on its own schedule.
9. `09_mv_segment_zr_hourly.sql` — refreshable, stores a seasonal z-score
   for every eligible segment/hour, including quiet rows. This is separate
   from threshold-filtered `segment_anomalies`: a missing anomaly row alone
   is not evidence that a segment was measured and ruled out.
10. `10_mv_segment_incident_evidence.sql` — refreshable, depends on the
    all-score layer and canonical incidents, and stores the compact heatmap
    matrix: peak/mean z-score, incident and prior-28-day correlations,
    direction agreement, and quiet hours. Correlations use standardized
    residuals, not raw seasonal values, and are co-movement evidence—not
    proof of cause.
12. `12_mv_incidents.sql` — refreshable, `DEPENDS ON mv_detect_global`,
    collapses adverse, incident-enabled anomaly rows into spans →
    `incidents`. Incident formation needs gaps across full anomaly history,
    which an INSERT-triggered MV can't see even in principle — this was
    the first stage built refreshable, before the cascading-bulk-load bug
    above was even found.

Every active method (`trend_seasonal`, `proportion`, `day_level`, and both
segment-level ones) handles full-history recompute safely — each hour (or
each `(dimension, segment, hour)` triple) looks up its own trailing baseline
independently, no cross-hour ordering dependency. That's also why
`anomalies`/`segment_anomalies`/`metric_zr_hourly` are now **plain
`MergeTree`**, not `ReplacingMergeTree` — each has exactly one writer (its
refreshable MV), which fully replaces the table's content every cycle, so
there's nothing to dedupe. Don't query any of them with `FINAL` — ClickHouse
Cloud's `SharedMergeTree` rejects `FINAL` outright on a non-Replacing table
(`ILLEGAL_FINAL`), it does not silently no-op.

One real consequence of full-recompute-and-replace: `anomalies` always
reflects what qualifies under the **current** `detection_config`, not
whatever config was active when an hour first got scored. That's an
intentional property, not a side effect — it's exactly what
`scripts/recompute-detections-local.ts` used to do manually before this
migration ("makes stored anomaly rows match the current MV SQL"); now it
happens automatically every refresh.

## Removed, not dormant

`cusum`, `ewma_fast`/`ewma_slow`, `basic`, and `forecast_regression` have
all been removed from the pipeline entirely — no config rows, no state
tables, no SQL files. `cusum`/`ewma` were architecturally incompatible with
the reactive-MV design (a true sequential recurrence can't fold correctly
under a block-triggered MV — though note this concern doesn't even apply to
the *refreshable* design used here, since a refreshable MV always
recomputes from scratch; nobody has revisited whether that changes the
calculus). `basic` never correlated with known incident windows in
full-history simulation. `forecast_regression` (a `stochasticLinearRegressionState`
experiment) was dropped as a direction — linear regression is no longer
part of this project's approach. Active global ensemble: `trend_seasonal` +
`proportion` + `day_level`. Active segment ensemble: `trend_seasonal` +
`proportion` only (`day_level` was never built per-segment).

`detection_config` also has `incident_enabled` (separate from `enabled`) —
CTR/render_rate are detected and kept in `anomalies` as evidence, but
excluded from opening a paged incident in `mv_incidents`. See
`sql/01_detection_config_seed.sql`'s comment.

## No app-level schedule

Detection is now fully MV-driven, global and segment-level alike — there is
no daily segment-sweep batch job and no daily noise-baseline cron job (the
noise baseline is `06_mv_noise_baseline_daily.sql`, a refreshable MV).
`mv_incidents` materializes canonical incidents directly in ClickHouse;
there is no Node poller or outbound webhook delivery — the dashboard and
incident-detail page read `inmobi.incidents` directly.

## Setup

Run once via `npm run setup:local` (`lib/incremental/tick.ts`'s
`runSetup()`), which runs `00_schema.sql`, `01_detection_config_seed.sql`,
`segment/01_schema.sql`, then the MV chain in dependency order.
`CREATE MATERIALIZED VIEW IF NOT EXISTS` makes re-running setup idempotent
for MVs that already exist unchanged, but **does not** pick up a changed
query body — dropping and recreating is required to actually update an
existing MV's definition (`DROP VIEW inmobi.<name>`, then re-run its file).

A refreshable MV's first run happens on ClickHouse's own schedule, which can
be up to its full `REFRESH EVERY` interval after creation. On a fresh
environment, force the first pass through the whole chain rather than
waiting:

```bash
npm run recompute:local
```

This runs `SYSTEM REFRESH VIEW` + `SYSTEM WAIT VIEW` for every refreshable
MV in dependency order (noise baseline → zr → global detect → segment
detect → incidents) and prints row counts.

Existing rows already in `ad_events` at MV-creation time are backfilled
automatically for the *refreshable* stages (they always recompute full
history), but **not** for the *reactive* rollups (`mv_metrics_hourly`,
`mv_segment_metrics_hourly`) — those only fire on inserts that happen after
they're created. A fresh environment needs its historical `ad_events`
loaded after the reactive MVs exist, or `metrics_hourly`/
`segment_metrics_hourly` (and everything downstream) will be empty.

If an existing environment has only some segment dimensions populated (for
example, `ad_format` was loaded before the dimension lookup joins existed),
run `npm run backfill:segments:local`. It inserts only dimensions that are
completely absent, then `npm run recompute:local` refreshes the downstream
z-score and incident-evidence tables. It deliberately refuses to infer a
repair for a partially populated dimension.
