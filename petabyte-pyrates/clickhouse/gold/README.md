# Gold (`gold` database)

Materialized views and attribute dictionaries. The `metrics_hourly` table DDL lives in [`../semantic/`](../semantic/) because it is the semantic fact target for analyst and anomaly workloads.

| File | Object | Type |
|------|--------|------|
| `00_database.sql` | `gold` | Database |
| `01_metrics_hourly_mv.sql` | `metrics_hourly_mv` | Materialized view — silver → `gold.metrics_hourly` |
| `02_dict_apps.sql` | `dict_apps` | Dictionary — app_id → category, publisher_tier |
| `03_dict_advertisers.sql` | `dict_advertisers` | Dictionary — advertiser_id → vertical, campaign_type |
| `04_dict_geo_device.sql` | `dict_geo_device` | Dictionary — geo_device_id → region, country, device, OS |

Dictionary DDLs use `{CLICKHOUSE_PASSWORD}` — substitute before running.

Apply order: `gold/00` → `semantic/01_metrics_hourly.sql` → remaining `gold/*.sql` → `semantic/02` → `anomaly/`.
