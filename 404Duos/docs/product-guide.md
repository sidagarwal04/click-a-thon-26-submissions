# Product guide

## Dashboard (`/`)

- Metrics from `metric_hourly_snapshot` via `/api/dashboard/query`
- Date range and prior-period compare
- Dimension filters and breakdown tables

## Alerts (`/alerts`)

### Granularity

| Mode | Behavior |
|------|----------|
| **Daily** (default) | One card per advertiser per day (peak hourly anomaly) |
| **Hourly** | Native hour buckets from `alerts_live` |

Daily opens investigations with `?view=day` so the header shows the calendar day and peak hour. RCA still runs on that peak hour bucket.

### Category tabs

Count alerts that have contributors in that dimension family (geo, OS, campaign, format, publisher, content). Alerts without attribution appear under **All** only.

### Baselines

| Label | Meaning |
|-------|---------|
| vs same hour, prior 4 weeks | Same hour-of-day over prior weeks |
| daily peak hour | Daily card rollup; peak hour used the seasonal baseline |

## Investigation (`/investigations/:id`)

- Metric tree and contribution waterfall
- Seasonality, diagnosis, citations
- Segments, ruled-out factors, hypotheses, counterfactual
- Trace timeline
- Export evidence bundle
- Ask-in-chat deep link

## Chat (`/chat`)

Natural language → `POST /v1/chat/completions`.

- Filter questions (region, country, OS, dates) → dashboard query
- RCA questions → investigation evidence

Markdown tables render if the model emits them. Charts live on the Dashboard.
