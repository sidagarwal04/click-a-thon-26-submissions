# Data model (ClickHouse `insightiq`)

Deep dive on the native cascade: [pipeline.md](./pipeline.md).  
SQL comments: [`../infra/clickhouse/insightiq_view_layer.sql`](../infra/clickhouse/insightiq_view_layer.sql).

## Pipeline

```
ad_events_raw
      │  MATERIALIZED VIEW mv_hourly
      ▼
agg_hourly  (SummingMergeTree)
      │
      ├─► VIEW metric_hourly_snapshot  (derived rates)
      │
      ├─► baseline_hourly  (ReplacingMergeTree)
      │         │
      │         ▼
      └─► alerts_live
                │
                ├─► alert_dimension_contributors
                └─► alert_observations

alert_rules
```

## Objects

### `ad_events_raw` (MergeTree)

Landing table for raw events: `ts`, `app_id`, `geo_device_id`, `advertiser_id`, `ad_format`, `requests`, `is_filled`, `is_impression`, `is_click`, `revenue`, …

### `agg_hourly` (SummingMergeTree)

Hourly rollup with joined dimensions (`country`, `os_version`, `ad_format`, `category`, `vertical`, `publisher_tier`, `campaign_type`, …) and sums (`revenue`, `requests`, `fills`, `impressions`, `clicks`).

### `metric_hourly_snapshot` (View)

Re-aggregates `agg_hourly` and exposes derived metrics: `fill_rate`, `ctr`, `ecpm`, `rpr`. Used by dashboard and investigation math.

### `baseline_hourly` (ReplacingMergeTree)

| Column | Role |
|--------|------|
| `advertiser_id`, `metric`, `bucket` | Key |
| `expected`, `stddev`, `median`, `mad` | Seasonality model |
| `lower_bound`, `upper_bound` | Optional bounds |
| `created_at` | Version for ReplacingMergeTree |

### `alerts_live` (MergeTree)

| Column | Type |
|--------|------|
| `alert_id` | UUID |
| `advertiser_id` | String |
| `metric` | String |
| `granularity` | String (typically `hourly`) |
| `bucket` | DateTime |
| `actual` / `expected` / `zscore` | Float64 |
| `created_at` | DateTime |

Product filter: `abs(zscore) > 3` (after noise-floored stddev).

### `alert_dimension_contributors` (MergeTree)

`dimension`, `dimension_value`, `current_value`, `baseline_value`, `delta`, `contribution`.

### `alert_observations` (MergeTree)

`observation_order`, `observation_type`, `title`, `detail`, `impact`.

### `alert_rules` (MergeTree)

| Column | Notes |
|--------|-------|
| `rule_id` | UUID |
| `name` | Optional label |
| `metric` | e.g. `revenue` |
| `granularity` | e.g. `hourly` |
| `threshold` | Z-score threshold |
| `min_volume` | Minimum volume before alerting |
| `consecutive_buckets` | Persistence requirement |
| `dimensions` | Dimensions to audit |
| `created_at` | |

## Detection & attribution (summary)

| Technique | Idea |
|-----------|------|
| Seasonality baseline | Same hour / day-of-week over prior ~4 weeks |
| Noise-floored Z-score | `greatest(stddev, floor)` so tiny volumes do not explode |
| Contribution filter | e.g. `abs(delta) > 0.01` and `abs(contribution) > 0.05` |

Full SQL patterns and rationale: [pipeline.md](./pipeline.md).

## Product query patterns

- **Hourly alert wall:** top `|z|` from `alerts_live`
- **Daily alert wall:** peak `|z|` per advertiser + metric + UTC day
- **Contributors / observations:** by `alert_id`
- **Dashboard:** filter `metric_hourly_snapshot` by time and dimensions; optional compare window
- **Date bounds:** prefer `min`/`max` on `agg_hourly` (physical table)
