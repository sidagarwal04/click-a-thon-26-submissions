# ClickHouse Design

Two isolated databases, same schema in each, selected by the dataset registry (`engine/datasets.py`):

- **`ad_events_main`** — the primary dataset: 9,000,000 events, Jun 1 – Jul 5 2026
- **`unseen_data`** — the sealed incident drop: 1,500,000 events, Jul 6 – 10 2026. A separate database because its dimension files reuse every id with **regenerated attributes**; co-loading into the `ReplacingMergeTree` dims would silently relabel all 9M historical facts. No SQL in the repo is database-qualified, so repointing the connection repoints the entire system.

## Tables

- `ad_events` (MergeTree) — **live**: 9,000,000 rows in `ad_events_main`, 1,500,000 in `unseen_data`
- `apps` — **live**: 2,000 rows (ReplacingMergeTree)
- `advertisers` — **live**: 500 rows (ReplacingMergeTree)
- `geo_device` — **live**: 5,000 rows (ReplacingMergeTree)

## Performance

- Monthly partitions — **live** (part of schema.sql)
- Bloom filters — **live** (part of schema.sql)
- Materialized views — **live**, backfilled (rollups.sql + monitoring_rollups.sql); historical rows were backfilled with one-time manual INSERTs since `load.sql` had already run before these existed — see `PRODUCTION_PLAN.md` Phase 0 and `scripts/apply_and_backfill.py` / `scripts/apply_monitoring.py`
- Dictionaries — **live** (dictionaries.sql, 3 dictionaries)
- Projections — **live** (`proj_by_advertiser`, `proj_by_geo`, part of schema.sql)
- Aggregate rollups — **live**, backfilled and reconciled against raw `ad_events`: **19 tables** — the 12 `hourly_*` (rollups.sql) plus 7 monitoring rollups (monitoring_rollups.sql: `minute5_overall`/`minute5_by_region`/`minute5_by_format`, composite `hourly_geo_cell`/`hourly_os_family_region`/`hourly_format_region`, `reach_hourly`). What the rollups actually buy is measured, not asserted: 6×–10,714× fewer rows scanned (`scripts/bench_rollups.py`; see `../DESIGN_RATIONALE.md` §3)

## Detection-loop state (monitoring_state.sql)

- `baselines` — robust bands (median ± k·MAD) per metric × scope × grain × seasonal cell, ~1.17M rows on the primary dataset, rebuilt by `engine/baselines_job.py`
- `metric_events` — confirmed band breaches (ReplacingMergeTree, replay-safe)
- `incidents` — clustered breaches with mechanism signature, $/day impact, owner, labels
- `sweep_runs` / `sweep_coverage` — the receipt for every sweep: what was evaluated, skipped, suppressed, and why
- App state (app_state.sql): `investigations` / `scan_ticks` / `investigation_chat`

See `PRODUCTION_PLAN.md` for the full phase-wise build order and `../../PROGRESS.md` for current status.

For the rollup/materialized-view layer in depth — what each view stores, why only additive
counters are kept, how the dimension key is derived, the `''`-advertiser bucket, backfill
rules, and reconciliation queries — see `../ROLLUP_LAYER.md`.
