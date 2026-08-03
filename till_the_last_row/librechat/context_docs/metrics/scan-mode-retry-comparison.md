---
type: metric
title: scan_mode auto vs manual — retry comparison (passports)
metric_id: M3
description: Average retry_count for scan_mode = auto vs manual, for passport documents, to test whether auto-scan reduces upload friction.
confirmed_by_user: false
served_by_mv: document_uploaded_daily_agg
timestamp: 2026-08-06
tags: [metric, document, scan-mode, retries]
---

# Question

"Does `scan_mode = auto` succeed (lower retries) compared to `manual` for passport documents?"
(spec 11 PM question 3)

# Formula (MV-served)

```sql
SELECT scan_mode,
       avgMerge(retry_avg_state) AS avg_retries,
       countMerge(uploads_state) AS uploads
FROM atlys.document_uploaded_daily_agg
WHERE doc_type IN ('passport_front', 'passport_back')
GROUP BY scan_mode
```

- Compare `avg_retries` for `scan_mode = 'auto'` vs `'manual'`; lower avg = less friction.
- "Passport" = `doc_type IN ('passport_front','passport_back')` (the spec lists `passport_front`,
  `passport_back`, `photo`, `supporting_doc`). ⚠️ `passport` is not a single doc_type value —
  confirm with PM whether `photo`/`supporting_doc` should be excluded.

# Notes

- ⚠️ `confirmed_by_user: false`. Both `scan_mode` and `doc_type` are ORDER BY / grain dims, so this
  slice is cheap on both base and agg.

# Related

- Tables: [document_uploaded_daily](/tables/document_uploaded_daily.md), [document_uploaded](/tables/document_uploaded.md)
- Entities: [document](/entities/document.md)
- Source: `specs/11_document_uploaded/spec.md`, `Atlys/schemas/11_document_uploaded.metrics.json`
