# API reference

Local base: `http://127.0.0.1:4000`

RCA runs **in-process** inside the Node API (`apps/api/src/engine`). There is no separate engine port.

---

## Health

### `GET /health`

```json
{
  "ok": true,
  "service": "insightiq-api",
  "gemini": true,
  "clickhouse": { "ok": true, "database": "insightiq", "alerts": 388 },
  "langfuse": true
}
```

---

## Alerts & investigations

### `GET /api/alerts?granularity=day|hour`

Default: `day`.

- `day` — peak hourly anomaly per advertiser per UTC day
- `hour` — native hourly buckets from `alerts_live`

### `GET /api/alerts/:alertId`

### `GET /api/alerts/:alertId/investigation`

### `POST /api/investigate`

```json
{ "alertId": "<uuid>" }
```

Or window fields:

```json
{
  "metric": "revenue",
  "windowStart": "2026-06-21T10:00:00Z",
  "windowEnd": "2026-06-21T10:59:59Z",
  "baselineKind": "same_hour_4w_seasonality"
}
```

### `GET /api/investigations/:id`

Cached investigation or rebuild (`inv-<alertUuid>`).

### `GET /api/investigations/:id/export`

Evidence bundle: diagnosis, trace, evidence hash, seasonality, waterfall, counterfactual, hypotheses.

---

## Dashboard

### `GET /api/dashboard/meta`

Metrics, dimensions, and `dataRange` `{ min, max, buckets }`.

### `POST /api/dashboard/query`

```json
{
  "start": "2026-06-21T00:00:00Z",
  "end": "2026-06-21T23:59:59Z",
  "granularity": "hour",
  "metrics": ["revenue", "requests", "fill_rate", "ecpm"],
  "dimensions": ["ad_format", "country"],
  "filters": { "country": ["IN"], "os_version": ["iOS 17.2"] },
  "compare": { "start": "...", "end": "..." },
  "limit": 10
}
```

### `GET /api/dashboard/filters?dimension=&start=&end=`

Distinct values for filter pickers.

---

## Chat

### `POST /v1/chat/completions`

```json
{
  "model": "insightiq-rca",
  "messages": [{ "role": "user", "content": "…" }],
  "stream": false,
  "investigationId": "optional",
  "alertId": "optional"
}
```

OpenAI-compatible; used by in-app chat.
