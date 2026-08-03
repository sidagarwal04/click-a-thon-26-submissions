---
type: metric
title: Retry-count Distribution by doc_type × capture_mode
metric_id: M1
description: Distribution / average of retry_count across doc_type and capture_mode, to find which combination causes the most upload friction.
confirmed_by_user: false
served_by_mv: document_uploaded_daily_agg
timestamp: 2026-08-06
tags: [metric, document, friction, retries]
---

# Question

"What is the `retry_count` distribution by `doc_type` and `capture_mode`? Which combination causes
the most friction?" (spec 11 PM question 1)

# Formula (MV-served)

```sql
SELECT doc_type, capture_mode,
       avgMerge(retry_avg_state)                                  AS avg_retries,
       sumMerge(retry_sum_state)                                  AS total_retries,
       countMerge(uploads_state)                                  AS uploads
FROM atlys.document_uploaded_daily_agg
GROUP BY doc_type, capture_mode
ORDER BY avg_retries DESC
```

- "Most friction" = highest `avg_retries` (or highest `total_retries`) combination.
- A true per-value **distribution** (share of uploads at retry_count = 0,1,2,…) is **not** stored
  in the agg (only sum/avg/count states) → for the histogram, query the base
  [document_uploaded](/tables/document_uploaded.md) `GROUP BY doc_type, capture_mode, payload.retry_count`.

# Notes

- ⚠️ `confirmed_by_user: false` — derived from the spec + agg grain, not a confirmed definition.

# Related

- Tables: [document_uploaded_daily](/tables/document_uploaded_daily.md), [document_uploaded](/tables/document_uploaded.md)
- Entities: [document](/entities/document.md)
- Source: `specs/11_document_uploaded/spec.md`, `Atlys/schemas/11_document_uploaded.metrics.json`
