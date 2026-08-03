---
type: metric
title: Group Applications by Destination
description: Which destinations / segments drive group applications — distinct groups started per destination (optionally per group_size). MV-served from group_family_daily.
confirmed_by_user: true
served_by_mv: group_family_daily
timestamp: 2026-08-07
tags: [metric, group, family, destination, segment]
---

# Question

"Which destinations / segments drive group applications?" (spec 02 PM question 4)

# Formula (MV-served)

```sql
SELECT
  destination,
  uniqMerge(groups_started)   AS groups_started,
  uniqMerge(groups_submitted) AS groups_submitted
FROM atlys.group_family_daily
GROUP BY destination
ORDER BY groups_started DESC
```

- **groups_started** = distinct `group_id` that emitted `group_started`, per `destination`.
- `group_size` is also in the grain, so segment views can split by destination × size.

# Notes

- ✅ `confirmed_by_user: true`.
- `destination` is a typed `LowCardinality(String)` path and ORDER BY col 2 on the base table, so
  destination slices are cheap on both base and rollup.

# Related

- Tables: [group_family_daily](/tables/group_family_daily.md), [group_family](/tables/group_family.md)
- Entities: [group](/entities/group.md), [destination](/entities/destination.md)
- Source: `specs/02_group_family/spec.md`, `Atlys/schemas/02_group_family.metrics.json`
