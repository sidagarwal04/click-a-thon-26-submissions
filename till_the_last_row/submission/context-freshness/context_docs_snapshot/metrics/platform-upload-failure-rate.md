---
type: metric
title: Platform upload-failure comparison (iOS vs Android)
metric_id: M4
description: Upload retry / threshold-crossing rates split by os / device_type to find whether a platform sees more document-upload failures.
confirmed_by_user: false
served_by_mv: document_uploaded_daily_agg
timestamp: 2026-08-06
tags: [metric, document, platform, os, device-type]
---

# Question

"Is there a platform (iOS vs Android) where document upload fails more often?" (spec 11 PM
question 4)

# Formula (MV-served)

```sql
SELECT device_type,
       avgMerge(retry_avg_state)                                   AS avg_retries,
       sumMerge(threshold_crossed_state) / countMerge(uploads_state) AS threshold_cross_rate,
       countMerge(uploads_state)                                   AS uploads
FROM atlys.document_uploaded_daily_agg
GROUP BY device_type   -- or GROUP BY os
```

- "Fails more" = higher `avg_retries` and/or higher `threshold_cross_rate`.

# ⚠️ OS segmentation caveat (D3 / android-os-null)

- `os` is a grain dim in the agg but is **NOT typed or skip-indexed** on the base
  [document_uploaded](/tables/document_uploaded.md). Android rows with `os = NULL` land in the
  `os = ''` bucket (MV coalesce), so `GROUP BY os` **undercounts Android**.
- **Prefer `GROUP BY device_type`** (`ios` / `android` / `Desktop`), which is typed + `set(32)`
  indexed and reliable, or COALESCE the empty/NULL `os` → `'Android'` when `device_type='android'`.
- See [android-os-null](/contradictions/android-os-null.md).
- ⚠️ `confirmed_by_user: false`.

# Related

- Tables: [document_uploaded_daily](/tables/document_uploaded_daily.md), [document_uploaded](/tables/document_uploaded.md)
- Contradictions: [android-os-null](/contradictions/android-os-null.md)
- Source: `specs/11_document_uploaded/spec.md`, `Atlys/schemas/11_document_uploaded.metrics.json`
