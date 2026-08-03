---
type: relationship
title: group_started → group_submitted (within-group funnel)
description: The intra-group lifecycle — a group_id progresses group_started → traveller_added/removed (n) → group_submitted, all within the group_family table. Completion is the ratio of distinct submitted groups to distinct started groups.
timestamp: 2026-08-07
tags: [relationship, group, family, funnel]
---

# Shape

All four group events share a single `group_id` and live in one base table
[group_family](/tables/group_family.md). A group's lifecycle:

```
group_started ── traveller_added × n ── (traveller_removed × m) ── group_submitted
```

# Join / progression key

- **`group_id`** ties the events of one group together (read via `CAST(payload.group_id,'String')`).
- Ordering within a group is by `payload.timestamp`.
- `group_size` and `destination` are stable per group and are the analysis dimensions.

# Metrics built on this progression

- **Completion**: distinct groups with `group_submitted` ÷ distinct groups with `group_started`,
  by `group_size` — see [group-completion-rate](/metrics/group-completion-rate.md).
- **Churn** between add and remove — see [traveller-churn](/metrics/traveller-churn.md).

# Notes

- This is an **intra-table** progression (one table, discriminated by `payload.event`), not a
  cross-table join. The daily rollup [group_family_daily](/tables/group_family_daily.md)
  materializes the started/submitted `uniq(group_id)` states directly.

# Related

- Tables: [group_family](/tables/group_family.md), [group_family_daily](/tables/group_family_daily.md)
- Entities: [group](/entities/group.md)
- Metrics: [group-completion-rate](/metrics/group-completion-rate.md), [traveller-churn](/metrics/traveller-churn.md)
- Source: `specs/02_group_family/spec.md`, live `atlys` schema
