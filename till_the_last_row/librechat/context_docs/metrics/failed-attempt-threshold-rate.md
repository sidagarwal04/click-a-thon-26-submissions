---
type: metric
title: Failed-attempt Threshold-crossing Rate
metric_id: M2
description: Share of document uploads where is_crossed_failed_attempt_threshold = 1 (user hit the retry threshold and was offered a fallback).
confirmed_by_user: false
served_by_mv: document_uploaded_daily_agg
timestamp: 2026-08-06
tags: [metric, document, friction, threshold]
---

# Question

"What share of uploads hit `is_crossed_failed_attempt_threshold = 1`, and does this predict
application abandonment?" (spec 11 PM question 2)

# Formula (MV-served)

```sql
SELECT sumMerge(threshold_crossed_state) / countMerge(uploads_state) AS threshold_cross_rate
FROM atlys.document_uploaded_daily_agg
-- optionally GROUP BY doc_type, capture_mode, scan_mode, device_type, destination
```

- `is_crossed_failed_attempt_threshold = 1` when the user hit `failed_attempt_threshold` (typically
  3) and was offered a fallback.

# Scope / gap

- The **rate** is MV-served. The **"predict abandonment"** half is **cross-table**: it requires
  joining upload users to the absence of a later `pay_now_clicked` / `purchase_completed` — see
  [document-upload-to-pay-now](/relationships/document-upload-to-pay-now.md). Not computable from
  this agg alone.
- ⚠️ `confirmed_by_user: false`.

# Related

- Tables: [document_uploaded_daily](/tables/document_uploaded_daily.md), [document_uploaded](/tables/document_uploaded.md)
- Metrics: [passport-capture-pass-rate](/metrics/passport-capture-pass-rate.md) (complement — pass = threshold not crossed)
- Relationships: [document-upload-to-pay-now](/relationships/document-upload-to-pay-now.md)
- Source: `specs/11_document_uploaded/spec.md`, `Atlys/schemas/11_document_uploaded.metrics.json`
