---
type: relationship
title: application_started → document_uploaded (on user_id)
description: Mid-funnel transition join — application starters who upload a document. Cross-event and runnable now (document_uploaded is live). Serves the co_travelers drop-off metric.
timestamp: 2026-08-05
tags: [relationship, join, funnel, drop-off, cross-event]
---

# Join

```
application_started.payload.user_id = document_uploaded.<user_id>
AND document_uploaded.timestamp > application_started.timestamp
```

- Grain: distinct `user_id` per side per application window; a user can start several applications
  and upload several documents.

# Purpose

Serves [co-travelers-dropoff](/metrics/co-travelers-dropoff.md) — start→document-upload drop-off
split by `co_travelers` (spec-10 PM question).

# Notes / caveats

- ✅ **Runnable now**: `document_uploaded` **is live** in `atlys` (`atlys.document_uploaded`).
- **No MV** serves this — query-time cross-event join between two base tables.
- Read `co_travelers` from `application_started.payload.co_travelers` (untyped path; not a rollup
  dim).

# Source

- Tables: [application_started](/tables/application_started.md), [document_uploaded](/tables/document_uploaded.md).
- Spec: `specs/10_application_started/spec.md`; live `atlys` schema (`document_uploaded` present, 20k+ rows).
