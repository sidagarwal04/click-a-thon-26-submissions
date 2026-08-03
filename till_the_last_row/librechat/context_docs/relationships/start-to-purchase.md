---
type: relationship
title: application_started → purchase_completed (on user_id)
description: Funnel conversion join — application starters who complete a purchase. Cross-event; purchase_completed is not yet live, so this join is defined but not yet runnable.
timestamp: 2026-08-05
tags: [relationship, join, conversion, cross-event, gap]
---

# Join

```
application_started.payload.user_id = purchase_completed.<user_id>
AND purchase_completed.timestamp > application_started.timestamp
```

- Grain: dedup to distinct `user_id` per side as the question requires; a user may start several
  applications and complete at most one purchase per application window.
- Join on `user_id` (not `application_id`) for robustness, ordering by `timestamp`.

# Purpose

Serves [start-to-purchase-conversion](/metrics/start-to-purchase-conversion.md) and, sliced by
`eta_shown` band, [eta-shown-conversion-lift](/metrics/eta-shown-conversion-lift.md) — the spec-10
PM questions on start→purchase conversion.

# Notes / caveats

- ⚠️ **Not yet runnable**: `purchase_completed` has **no live table** in `atlys` (still a spec
  stub). `application_started` supplies only the **denominator**. See
  [start-to-purchase-not-live-gap](/contradictions/start-to-purchase-not-live-gap.md).
- **No MV** serves this — it is a query-time cross-event join between two base tables.

# Source

- Tables: [application_started](/tables/application_started.md), [purchase_completed](/tables/purchase_completed.md).
- Spec: `specs/10_application_started/spec.md`; metrics: `Atlys/schemas/10_application_started.metrics.json`; live `atlys` schema (no purchase_completed table).
