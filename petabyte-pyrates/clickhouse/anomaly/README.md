# Anomaly detection & RCA queue (`gold`)

Objects live in the `gold` database but are grouped here because they form the anomaly-detection stack and RCA writeback target.

## Apply order

Run **after** `semantic/02_metric_hourly_by_slice.sql`.

| File | Object | Type |
|------|--------|------|
| `01_metric_anomalies.sql` | `gold.metric_anomalies` | Table — RCA investigation queue |
| `02_baseline_hour_of_week.sql` | `gold.baseline_hour_of_week` | Table — same-DOW/hour baselines (14-day window) |
| `03_baseline_hour_of_week_mv.sql` | `gold.baseline_hour_of_week_mv` | Refreshable MV — hourly REPLACE into baselines |
| `04_metric_anomaly_stl.sql` | `gold.metric_anomaly_stl` | View — STL + Tukey on residuals |
| `05_metric_anomaly_candidates.sql` | `gold.metric_anomaly_candidates` | View — Rule Z + Rule R candidates |
| `06_metric_anomaly_confirmed.sql` | `gold.metric_anomaly_confirmed` | View — Z + STL agreement (alerting grade) |
| `07_metric_anomalies_sync.sql` | `gold.metric_anomalies_sync_mv` | Refreshable MV — hourly append with dedup |

## Detection flow

```
gold.metric_hourly_by_slice
        │
        ├──► baseline_hour_of_week_mv ──► baseline_hour_of_week (table)
        ├──► metric_anomaly_candidates (Rule Z, Rule R)
        ├──► metric_anomaly_stl (STL + Tukey)
        │
        └──► metric_anomaly_confirmed (Z ∧ STL ∧ volume gate)
                    │
                    └──► metric_anomalies_sync_mv (hourly APPEND, deduped)
                              │
                              └──► gold.metric_anomalies (status=open)
                                        │
                                        └──► RCA agent → close_anomaly_investigation
```

## RCA queue columns

`gold.metric_anomalies` holds `anomaly_id`, detection fields, and agent writeback: `status`, `disposition`, `rca_description`, `evidence_json`, `investigated_at`.

`gold.baseline_hour_of_week_mv` refreshes every hour (`REFRESH EVERY 1 HOUR`, REPLACE). Force an immediate recompute with `SYSTEM REFRESH VIEW gold.baseline_hour_of_week_mv` after bulk loads.

`gold.metric_anomalies_sync_mv` refreshes every hour (`REFRESH EVERY 1 HOUR APPEND`) and only inserts rows whose `(metric_hour, slice_type, slice_value, metric_name)` are not already in the queue. Force an immediate backfill with `SYSTEM REFRESH VIEW gold.metric_anomalies_sync_mv`.
