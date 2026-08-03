---
type: metric
title: Start → Purchase Conversion
description: application_started users who go on to purchase_completed, sliceable by destination, purpose, flow. CROSS-EVENT — this spec supplies only the denominator; purchase_completed is not yet live, so the metric is not yet computable.
metric_id: start_to_purchase_conversion
served_by_mv: null
computable: false
timestamp: 2026-08-05
tags: [metric, funnel, conversion, cross-event, gap]
---

# Formula

```
start_to_purchase_conversion = uniq(purchase_completed.user_id)
                             / uniq(application_started.user_id)
```

# Notes / caveats

- ⚠️ **Cross-event, not served by any MV** (`served_by_mv: null`). The `10_application_started`
  spec supplies **only the denominator** (`application_started`); the numerator event
  `purchase_completed` is a **different spec** and has **no live table** in `atlys` yet.
- **Not currently computable** — mark as a gap until `purchase_completed` is instrumented. See
  [start-to-purchase-not-live-gap](/contradictions/start-to-purchase-not-live-gap.md).
- Answers the spec-10 PM question "`application_started` → `purchase_completed` conversion by
  `destination` / `purpose` / `flow`".
- This is the `funnel_conversion` variant named in
  [dual-conversion-definition](/contradictions/dual-conversion-definition.md); state the
  denominator explicitly.
- When computable: query-time join on `user_id` with `purchase.timestamp > start.timestamp`; no MV.

# Source

- Denominator table: [application_started](/tables/application_started.md).
- Relationship: [start-to-purchase](/relationships/start-to-purchase.md).
- Spec: `specs/10_application_started/spec.md`; metrics: `Atlys/schemas/10_application_started.metrics.json`.
