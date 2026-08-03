---
type: metric
title: Group Completion Rate (by group size)
description: Share of started groups that are submitted (group_started → group_submitted), sliced by group_size — answers where large groups fall off. MV-served from group_family_daily.
confirmed_by_user: true
served_by_mv: group_family_daily
timestamp: 2026-08-07
tags: [metric, group, family, conversion, completion]
---

# Question

"Completion rate (`group_started → group_submitted`) **by group size** — where do large groups
fall off?" (spec 02 PM question 1)

# Formula (MV-served)

```sql
SELECT
  group_size,
  uniqMerge(groups_submitted) / nullIf(uniqMerge(groups_started), 0) AS completion_rate
FROM atlys.group_family_daily
GROUP BY group_size
ORDER BY group_size
```

- **Numerator** = distinct `group_id` that emitted `group_submitted`.
- **Denominator** = distinct `group_id` that emitted `group_started`.
- Both are `uniqMerge` over `uniqIfState(CAST(group_id,'String'), event = ...)` states.

# Observed (live)

Completion rate falls monotonically as group size grows — the PM's hypothesis holds:

| group_size | started | submitted | completion_rate |
|---|---|---|---|
| 2 | 475 | 330 | 0.695 |
| 3 | 283 | 166 | 0.587 |
| 4 | 238 | 120 | 0.504 |
| 5 | 114 | 44 | 0.386 |
| 6 | 90 | 28 | 0.311 |

# Notes

- ✅ `confirmed_by_user: true` — a confirmed PM-question metric in the manifest.
- Slice further by `destination` (also in the grain) for segment views.

# Related

- Tables: [group_family_daily](/tables/group_family_daily.md), [group_family](/tables/group_family.md)
- Entities: [group](/entities/group.md)
- Relationships: [group-started-to-submitted](/relationships/group-started-to-submitted.md)
- Source: `specs/02_group_family/spec.md`, `Atlys/schemas/02_group_family.metrics.json`
