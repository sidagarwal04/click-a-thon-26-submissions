---
type: relationship
title: document_uploaded → pay_now_clicked (on user_id)
description: Late-funnel transition join — uploaders who reach the pay-now step. Serves the doc-friction → abandonment / payment-conversion questions. NOT runnable yet — pay_now_clicked (spec 12) is not live.
timestamp: 2026-08-06
tags: [relationship, join, funnel, drop-off, cross-event, planned]
---

# Join (planned)

```
document_uploaded.<user_id> = pay_now_clicked.<user_id>
AND pay_now_clicked.timestamp > document_uploaded.timestamp
```

- Grain: distinct `user_id` (optionally `application_id`) per application window; a user can upload
  several documents before reaching payment.
- ⚠️ On `document_uploaded`, join on **`user_id`** (typed `String`, present in JSON hint).
  `application_id` is **not typed and not indexed** on this table, so an application-scoped join
  scans the untyped `payload.application_id` sub-column.

# Purpose

Serves the cross-event halves of spec-11 questions 2 and 5:

- "Does crossing `is_crossed_failed_attempt_threshold` predict application abandonment?" — i.e.
  uploaders who did **not** reach `pay_now_clicked` (see
  [failed-attempt-threshold-rate](/metrics/failed-attempt-threshold-rate.md)).
- "Does doc volume correlate with lower payment conversion?" (see
  [doc-volume-vs-payment-conversion](/metrics/doc-volume-vs-payment-conversion.md)).

# Notes / caveats

- ❌ **NOT runnable now**: `pay_now_clicked` (spec 12) is **not yet live** in `atlys`. This
  relationship is documented ahead of instrumentation; mark results as blocked until spec 12 lands.
- **No MV** serves this — it is a query-time cross-event join between base tables.
- The definition of "conversion" is itself contested — see
  [dual-conversion-definition](/contradictions/dual-conversion-definition.md).

# Source

- Tables: [document_uploaded](/tables/document_uploaded.md), `pay_now_clicked` (planned, spec 12).
- Spec: `specs/11_document_uploaded/spec.md` (PM questions 2 & 5); `specs/12_pay_now_clicked/` (not yet instrumented).
