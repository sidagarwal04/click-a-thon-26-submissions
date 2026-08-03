---
type: metric
title: Co-travelers Drop-off (start → document upload)
description: Drop-off between application_started and document_uploaded, split by co_travelers > 0 vs = 0. CROSS-EVENT but computable — document_uploaded is live; join at query time (no MV).
metric_id: co_travelers_dropoff
served_by_mv: null
computable: true
timestamp: 2026-08-05
tags: [metric, funnel, drop-off, cross-event]
---

# Formula

```
completion(seg) = uniq(document_uploaded.user_id | co_travelers seg)
                / uniq(application_started.user_id | co_travelers seg)

dropoff(seg)    = 1 - completion(seg)
```

Segments: `co_travelers = 0` vs `co_travelers > 0`.

# Notes / caveats

- ⚠️ **Cross-event, not served by any MV** (`served_by_mv: null`) — but **computable now**: the
  numerator event `document_uploaded` **is live** in `atlys` (`atlys.document_uploaded`), unlike
  the purchase-based conversion metrics. Compute via a query-time join.
- Join on `user_id` with `document_uploaded.timestamp > application_started.timestamp`; see
  [start-to-document-upload](/relationships/start-to-document-upload.md).
- `co_travelers` is **not** a typed path or a rollup dim on `application_started` — read it from the
  base table's `payload.co_travelers`; the `application_started_daily` rollup cannot serve this.
- Answers spec-10 PM question "how does `co_travelers > 0` affect drop-off between start and
  document upload?".

# Source

- Tables: [application_started](/tables/application_started.md), [document_uploaded](/tables/document_uploaded.md).
- Relationship: [start-to-document-upload](/relationships/start-to-document-upload.md).
- Spec: `specs/10_application_started/spec.md`; metrics: `Atlys/schemas/10_application_started.metrics.json`; live `atlys` schema (`document_uploaded` present).
