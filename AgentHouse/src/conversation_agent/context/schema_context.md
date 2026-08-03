# Schema context (legacy reference)

Conversation **discover_schema** uses context catalog tools only.
This file is a static reminder of the physical SAS — not injected into the agent.

## Table

`atlys.activity_events`

| Column | Notes |
|--------|--------|
| `event_name` | Event name — funnel conditions |
| `ch_table` | Source per-event table |
| `timestamp` | DateTime64(3) — use `toDateTime(timestamp)` in `windowFunnel` |
| `user_id` | Journey partition |
| `application_id` | From `application_started` onward |
| `device_type` | Segment |
| `os` | Segment |
| `geoip_country_code` | Segment |
| `destination` | Segment |
| `payload` | JSON payload |

## Core funnel

```
destination_card_clicked → application_started → document_uploaded → purchase_completed
```
