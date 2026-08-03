# Atlys ClickHouse — Single Activity Schema

Live / target fact table for Conversation analytics (owned by Instrumentation).

## Connection

| Setting | Value |
|--------|--------|
| Database | `atlys` |
| Activity table | `activity_events` (override with `CLICKHOUSE_ACTIVITY_TABLE`) |
| Data window (legacy snapshot) | `2025-12-31` → `2026-07-01` |

## Table: `atlys.activity_events`

One row per event (SAS). Fed by Instrumentation MVs from per-event tables.

| Column | Role |
|--------|------|
| `event_name` | Event discriminator |
| `ch_table` | Source per-event table |
| `timestamp` | DateTime64(3) — filters OK; `toDateTime(timestamp)` for `windowFunnel` |
| `user_id` | Journey partition |
| `application_id` | Application grain |
| `device_type` | Segment (`ios`, `android`, `web-user-b2c`, `Desktop`) |
| `os` | Segment |
| `geoip_country_code` | Segment |
| `destination` | Segment |
| `payload` | JSON — event-specific fields |

## Core funnel (`event_name`)

```
destination_card_clicked → application_started → document_uploaded → purchase_completed
```

Join on `user_id` (whole journey) and `application_id` (from `application_started` onward).

Supporting / feature events (Express, Group, …) share the same table; fields in `payload`.

## Query rules

- Aggregate in ClickHouse — never dump raw rows
- Filter on `event_name`; segment on envelope columns
- Payload metrics: `JSONExtract*(payload, '…')`
- `windowFunnel(...)(toDateTime(timestamp), ...)` — bare DateTime64 is illegal
- Prefer max(timestamp)-relative time windows for contest data
- Fully qualify: `atlys.activity_events`
