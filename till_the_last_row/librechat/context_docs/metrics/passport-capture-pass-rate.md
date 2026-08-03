---
type: metric
title: Passport-capture Pass Rate
description: Document uploads that did not cross the failed-capture threshold.
timestamp: 2026-08-01
tags: [metric, document]
---

# Formula

`document uploads with is_crossed_failed_attempt_threshold = 0 ÷ total document uploads`

# MV-served (now live)

Since spec 11 landed, this is computable from `document_uploaded_daily_agg` as the **complement** of
[failed-attempt-threshold-rate](/metrics/failed-attempt-threshold-rate.md) (M2):

```sql
SELECT 1 - sumMerge(threshold_crossed_state) / countMerge(uploads_state) AS pass_rate
FROM atlys.document_uploaded_daily_agg
```

> `pass_rate = 1 − threshold_cross_rate`. Not a contradiction — two names for complementary
> quantities (base_context §4 framing vs spec-11 manifest framing).

# Source

`base_context.md` §4; served by `Atlys/schemas/11_document_uploaded.sql` (`document_uploaded_daily_agg`).

# Related

- Tables: [document_uploaded](/tables/document_uploaded.md), [document_uploaded_daily](/tables/document_uploaded_daily.md)
- Entities: [document](/entities/document.md)
- Metrics: [failed-attempt-threshold-rate](/metrics/failed-attempt-threshold-rate.md) (complement)
- Known issues: [K2](/known-issues/k2-passport-scan-model-update.md), [K3](/known-issues/k3-mrz-ocr-non-latin.md)
