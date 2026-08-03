---
type: metric
title: Traveller Add/Remove Churn
description: Travellers added vs removed per group — is there add/remove churn as travellers are managed? Ratio of removals to adds, sliceable by group_size and destination. MV-served from group_family_daily.
confirmed_by_user: true
served_by_mv: group_family_daily
timestamp: 2026-08-07
tags: [metric, group, family, churn, travellers]
---

# Question

"How many travellers are added vs removed per group; is there an add/remove churn?"
(spec 02 PM question 2)

# Formula (MV-served)

```sql
SELECT
  group_size,
  sumMerge(travellers_added_cnt)   AS added,
  sumMerge(travellers_removed_cnt) AS removed,
  sumMerge(travellers_removed_cnt) / nullIf(sumMerge(travellers_added_cnt), 0) AS churn_ratio
FROM atlys.group_family_daily
GROUP BY group_size
ORDER BY group_size
```

- **added** = count of `traveller_added` events.
- **removed** = count of `traveller_removed` events.
- **churn_ratio** = removed / added.

# Observed (live)

Churn is low overall (removals rare vs adds) but rises with group size:

| group_size | added | removed | churn_ratio |
|---|---|---|---|
| 2 | 907 | 2 | 0.002 |
| 3 | 775 | 16 | 0.021 |
| 4 | 864 | 14 | 0.016 |
| 5 | 495 | 22 | 0.044 |
| 6 | 454 | 16 | 0.035 |

# Notes

- ✅ `confirmed_by_user: true`.
- Counts are **events**, not distinct travellers — a traveller re-added after removal counts twice.

# Related

- Tables: [group_family_daily](/tables/group_family_daily.md), [group_family](/tables/group_family.md)
- Entities: [group](/entities/group.md)
- Source: `specs/02_group_family/spec.md`, `Atlys/schemas/02_group_family.metrics.json`
