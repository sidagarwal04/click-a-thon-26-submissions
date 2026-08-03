# Semantic (`gold`)

Business read models on top of silver/gold pipeline output.

| File | Object | Type |
|------|--------|------|
| `01_metrics_hourly.sql` | `metrics_hourly` | Table — hourly fact at attribute grain |
| `02_metric_hourly_by_slice.sql` | `metric_hourly_by_slice` | View — six canonical slice grains for anomaly input |

Run `01` after `gold/00_database.sql` and before `gold/01_metrics_hourly_mv.sql` (the MV writes into this table).

Run `02` after `gold/` (table + MV populated). Required before `anomaly/` (detection views join `metric_hourly_by_slice`).

Attribute lookups (`dict_*`) live in [`../gold/`](../gold/).
