# ClickHouse DDL

DDL exported from ClickHouse Cloud. For the full architecture (Postgres → ClickPipes CDC → agent), see the [repo README](../README.md).

Apply in order: **bronze → silver → gold → semantic → anomaly**.

## Layer folders

| Folder | Database | Objects |
|--------|----------|---------|
| `bronze/` | `default` | `clickathon_*` — ClickPipes CDC landing |
| `silver/` | `silver` | `ad_events_enriched`, `dim_*`, `dq_funnel_violations` |
| `gold/` | `gold` | `metrics_hourly_mv`, `dict_*` |
| `semantic/` | `gold` | `metrics_hourly`, `metric_hourly_by_slice` |
| `anomaly/` | `gold` | `baseline_hour_of_week`, `baseline_hour_of_week_mv`, `metric_anomaly_*`, `metric_anomalies`, `metric_anomalies_sync_mv` |

Bronze tables are usually created by the ClickPipes destination. Silver through anomaly are applied manually (SQL console or `clickhouse-client`).

## Apply order

```bash
# Bronze — created by ClickPipes; run bronze/*.sql only if bootstrapping manually

clickhouse-client < clickhouse/silver/00_database.sql
for f in clickhouse/silver/[1-9]*.sql; do clickhouse-client < "$f"; done

clickhouse-client < clickhouse/gold/00_database.sql
clickhouse-client < clickhouse/semantic/01_metrics_hourly.sql
for f in clickhouse/gold/[1-9]*.sql; do clickhouse-client < "$f"; done

clickhouse-client < clickhouse/semantic/02_metric_hourly_by_slice.sql
for f in clickhouse/anomaly/*.sql; do clickhouse-client < "$f"; done
```

Dictionary DDLs in `gold/02–04` use `{CLICKHOUSE_PASSWORD}` — substitute before running.

## RCA read targets

| Object | Folder |
|--------|--------|
| `gold.metrics_hourly` | `semantic/` |
| `gold.dict_*` | `gold/` |
| `gold.metric_hourly_by_slice` | `semantic/` |
| `gold.baseline_hour_of_week` | `anomaly/` |
| `gold.metric_anomaly_confirmed` | `anomaly/` |
| `gold.metric_anomalies` | `anomaly/` |

## Re-export DDL from cloud

```bash
CH_URL='https://gnsfz88gkd.ap-south-1.aws.clickhouse.cloud:8443'
curl -sS --user "default:$CLICKHOUSE_PASSWORD" \
  --data-binary "SHOW CREATE TABLE gold.metrics_hourly FORMAT TabSeparatedRaw" \
  "$CH_URL"
```
