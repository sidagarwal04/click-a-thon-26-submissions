---
type: known-issue
title: K8 — group_family_daily ages out by event_date, not ingest time (D2)
description: The group_family_daily aggregate has no insert-watermark column, so its 90-day TTL is keyed on event_date. Late-arriving events for old dates can be dropped, and the agg retention window differs semantically from the base table's ch_insert_time TTL.
severity: low
timestamp: 2026-08-07
tags: [known-issue, group, family, ttl, aggregate, D2]
---

# Issue (Deviation D2)

The aggregate table [group_family_daily](/tables/group_family_daily.md) has **no insert-watermark
column** (no `ch_insert_time` equivalent), so its TTL is keyed on the derived **`event_date`**:

```
TTL event_date + 90 day, ttl_only_drop_parts = 1
```

The base table [group_family](/tables/group_family.md), by contrast, ages out on
`toDateTime(ch_insert_time) + 90 day` (ingest watermark).

# Why it matters (analytics)

- Agg rows drop when the **event** is 90 days old, regardless of when they were ingested. A
  late-ingested event for an old date may age out almost immediately in the rollup.
- Base vs agg retention windows are **semantically different** (ingest-time vs event-time); a
  base-table backfill of old dates will not be reflected in the rollup if those dates are already
  past the event-date TTL.

# Recommendation

- For long-lookback or backfill-sensitive group queries, prefer the base table over the rollup.
- Treat this as a **deliberate design deviation** (D2), not a bug — documented so the Analytics
  Agent picks the right source per question.

# Related

- Tables: [group_family_daily](/tables/group_family_daily.md), [group_family](/tables/group_family.md)
- Source: `Atlys/schemas/02_group_family.sql`, live `atlys` schema
