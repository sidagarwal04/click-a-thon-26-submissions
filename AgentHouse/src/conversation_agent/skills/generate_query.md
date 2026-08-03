---
name: clickhouse-activity-analytics
description: >-
  Build product-analytics queries against the Single Activity Schema table
  (atlys.activity_events) using event_name + envelope columns and payload JSON.
  Use for funnels (windowFunnel), conversion, drop-off, segment cuts, and
  payload-deep metrics via JSONExtract.
---

# ClickHouse Activity Schema Analytics

**Input:** `VizSpec` JSON. Map VizSpec → one `QuerySpec`.

## 1. Table — CRITICAL

**Always use `atlys.activity_events`** (or `CLICKHOUSE_ACTIVITY_TABLE`).  
Do **not** query legacy per-event tables or `funnel_events`.

### Columns (envelope)

| Column | Role |
|--------|------|
| `event_name` | Event discriminator (use in filters / funnel conditions) |
| `ch_table` | Source per-event table name (Instrumentation) |
| `timestamp` | DateTime64(3) — time filters OK as-is; **cast for `windowFunnel`** |
| `user_id` | Journey partition key |
| `application_id` | Application grain (often empty before `application_started`) |
| `device_type` | Segment |
| `os` | Segment |
| `geoip_country_code` | Segment |
| `destination` | Segment |
| `payload` | JSON string — event-specific fields |

For group/share funnels, extract `group_id` / `share_id` from `payload` when present.

## 2. windowFunnel

`timestamp` is **DateTime64(3)**. `windowFunnel` only accepts Unsigned /
Date / DateTime — always cast:

```sql
windowFunnel(window, [mode, ...])(toDateTime(timestamp), cond1, cond2, ..., condN)
```

- Window unit is **seconds** (after `toDateTime`). Comment the unit on every query.
- Conditions use **`event_name = '…'`** in funnel order.
- Per-step reach = `countIf(level >= k)`.
- Do **not** pass bare `timestamp` into `windowFunnel`.

### Base funnel (conversion by device)

```sql
-- window: 86400 seconds
WITH funnel_levels AS (
    SELECT
        user_id,
        any(device_type) AS device_type,
        windowFunnel(86400)(
            toDateTime(timestamp),
            event_name = 'destination_card_clicked',
            event_name = 'application_started',
            event_name = 'document_uploaded',
            event_name = 'purchase_completed'
        ) AS level
    FROM atlys.activity_events
    WHERE timestamp >= (SELECT max(timestamp) FROM atlys.activity_events) - INTERVAL 30 DAY
      AND timestamp <= (SELECT max(timestamp) FROM atlys.activity_events)
    GROUP BY user_id
)
SELECT
    device_type,
    countIf(level >= 1) AS entities_step_1,
    countIf(level >= 2) AS entities_step_2,
    countIf(level >= 3) AS entities_step_3,
    countIf(level >= 4) AS entities_step_4,
    countIf(level >= 4) / nullIf(countIf(level >= 1), 0) AS conversion_from_start
FROM funnel_levels
GROUP BY device_type
ORDER BY device_type
```

Prefer max(timestamp)-relative windows (contest data is historical).

## 3. Payload fields (`payload`)

For OTP, revenue, capture quality, forex, etc.:

```sql
JSONExtractString(payload, 'otp_success')
JSONExtractFloat(payload, 'value')
JSONExtractInt(payload, 'retry_count')
```

Only extract keys documented in context / `get_feature_meta` columns. Do not invent keys.

## 4. Core funnel steps

`destination_card_clicked` → `application_started` → `document_uploaded` → `purchase_completed`

## 5. Output contract

```json
{
  "sql": "…",
  "funnel": true,
  "window_seconds": 86400,
  "step_names": ["…"],
  "filters": {},
  "tables_used": ["activity_events"],
  "caveats": "…"
}
```

1. One `SELECT` / `WITH … SELECT` from **`activity_events` only**.
2. Prefer step / entities / conversion_from_start (+ segment).
3. `tables_used` = `["activity_events"]`.
