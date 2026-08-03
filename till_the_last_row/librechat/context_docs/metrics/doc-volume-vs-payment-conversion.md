---
type: metric
title: Doc volume vs payment conversion by destination
metric_id: M5
description: Which destinations require the most document types, and whether higher document volume correlates with lower payment conversion. Cross-table — not served by any MV.
confirmed_by_user: false
served_by_mv: null
timestamp: 2026-08-06
tags: [metric, document, destination, conversion, cross-table]
---

# Question

"Which destinations require the most document types, and does doc volume correlate with lower
payment conversion?" (spec 11 PM question 5)

# Two parts

1. **Doc volume by destination** (MV-friendly):

```sql
SELECT destination,
       uniqExact(doc_type)       AS distinct_doc_types,   -- base table only (agg has no uniq state)
       countMerge(uploads_state) AS uploads
FROM atlys.document_uploaded_daily_agg
GROUP BY destination
```

> ⚠️ The agg has **no `uniq`/distinct-doc_type state** — "most document *types* per destination"
> (distinct `doc_type` count) must be read from the base [document_uploaded](/tables/document_uploaded.md)
> (`GROUP BY destination` with `uniqExact(doc_type)`). Upload *volume* is MV-served.

2. **Payment conversion** (cross-table, NOT computable here):

- Correlating doc volume with payment conversion requires joining uploaders to
  `pay_now_clicked` / `purchase_completed` on `user_id` / `application_id`. `served_by_mv: null`.
- `document_uploaded` funnel joins use **`user_id`** (`application_id` is untyped/unindexed here).
- See [document-upload-to-pay-now](/relationships/document-upload-to-pay-now.md). The downstream
  `pay_now_clicked` (spec 12) and `purchase_completed` (spec 13) tables are **not yet live**, so
  the conversion half is a **gap** until they land.

# Notes

- ⚠️ `confirmed_by_user: false`; conversion definition itself is contested — see
  [dual-conversion-definition](/contradictions/dual-conversion-definition.md).

# Related

- Tables: [document_uploaded](/tables/document_uploaded.md), [document_uploaded_daily](/tables/document_uploaded_daily.md)
- Relationships: [document-upload-to-pay-now](/relationships/document-upload-to-pay-now.md)
- Contradictions: [dual-conversion-definition](/contradictions/dual-conversion-definition.md)
- Source: `specs/11_document_uploaded/spec.md`, `Atlys/schemas/11_document_uploaded.metrics.json`
