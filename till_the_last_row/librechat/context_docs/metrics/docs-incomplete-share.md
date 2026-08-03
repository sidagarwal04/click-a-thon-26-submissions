---
type: metric
title: Per-traveller Docs-incomplete Share
description: Share of added travellers whose documents are not complete (docs_complete = false) — is per-traveller document completion the bottleneck for big groups? MV-served from group_family_daily.
confirmed_by_user: true
served_by_mv: group_family_daily
timestamp: 2026-08-07
tags: [metric, group, family, documents, bottleneck]
---

# Question

"Is per-traveller document completion (`docs_complete`) the bottleneck for big groups?"
(spec 02 PM question 3)

# Formula (MV-served)

```sql
SELECT
  group_size,
  sumMerge(docs_incomplete_cnt) / nullIf(sumMerge(docs_added_cnt), 0) AS docs_incomplete_share
FROM atlys.group_family_daily
GROUP BY group_size
ORDER BY group_size
```

- **Numerator** (`docs_incomplete_cnt`) = `traveller_added` rows with `docs_complete = false`.
- **Denominator** (`docs_added_cnt`) = all `traveller_added` rows (i.e. travellers added).

# Observed (live)

Docs-incomplete share is broadly flat (~0.18–0.22) across group sizes — per-traveller doc
completion is a steady friction, not one that worsens sharply with size (contrast the sharp
completion-rate decline, which is driven more by group coordination than per-doc completeness):

| group_size | docs_incomplete | docs_added | docs_incomplete_share |
|---|---|---|---|
| 2 | 171 | 907 | 0.189 |
| 3 | 151 | 775 | 0.195 |
| 4 | 170 | 864 | 0.197 |
| 5 | 110 | 495 | 0.222 |
| 6 | 98 | 454 | 0.216 |

# Notes

- ✅ `confirmed_by_user: true`.
- `docs_complete` is a **typed Bool** payload path with a `set(2)` skip-index (idx_docs) on the base table.

# Related

- Tables: [group_family_daily](/tables/group_family_daily.md), [group_family](/tables/group_family.md)
- Entities: [group](/entities/group.md), [document](/entities/document.md)
- Source: `specs/02_group_family/spec.md`, `Atlys/schemas/02_group_family.metrics.json`
