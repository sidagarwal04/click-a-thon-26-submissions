---
type: metric
title: eta_shown Conversion Lift
description: Difference in start→purchase conversion across eta_shown bands (e.g. instant vs 7-10 days). CROSS-EVENT — depends on purchase_completed, which is not yet live; not yet computable.
metric_id: eta_shown_conversion_lift
served_by_mv: null
computable: false
timestamp: 2026-08-05
tags: [metric, funnel, conversion, cross-event, gap]
---

# Formula

```
lift(band) = start_to_purchase_conversion[eta_shown = band]
           - start_to_purchase_conversion[eta_shown = baseline]
```

e.g. `instant` vs `7-10 days`.

# Notes / caveats

- ⚠️ **Cross-event, not served by any MV** (`served_by_mv: null`). It is
  [start-to-purchase-conversion](/metrics/start-to-purchase-conversion.md) segmented by the
  `eta_shown` band, so it inherits the same dependency on the **not-yet-live** `purchase_completed`
  event → **not currently computable**. See
  [start-to-purchase-not-live-gap](/contradictions/start-to-purchase-not-live-gap.md).
- `eta_shown` is a **string** band (`instant`, `3-5 days`, `7-10 days`), not an integer — it is a
  rollup dim on the start side and a skip-index on the base table.
- Answers spec-10 PM question "does a shorter `eta_shown` materially improve conversion?".

# Source

- Denominator table: [application_started](/tables/application_started.md) (`eta_shown` band).
- Relationship: [start-to-purchase](/relationships/start-to-purchase.md).
- Spec: `specs/10_application_started/spec.md`; metrics: `Atlys/schemas/10_application_started.metrics.json`.
