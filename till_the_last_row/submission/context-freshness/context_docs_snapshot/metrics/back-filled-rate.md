---
type: metric
title: Back-filled Application Rate
description: Share of application_started events flagged is_back_filled, sliceable by the rollup dims. Clear and served by the daily rollup.
metric_id: back_filled_rate
served_by_mv: mv_application_started_daily
computable: true
timestamp: 2026-08-05
tags: [metric, funnel, live]
---

# Formula

```
back_filled_rate = applications[is_back_filled = true] / applications[all]
```

From the rollup (`is_back_filled` is a grouping dim):

```sql
SELECT
  countMergeIf(applications, is_back_filled) AS backfilled,
  countMerge(applications)                   AS total,
  backfilled / total                         AS back_filled_rate
FROM atlys.application_started_daily
```

# Notes / caveats

- **Clear + served**: `is_back_filled` is a rollup dimension, so the rate is computed entirely from
  `application_started_daily`.
- Answers spec 10's "what is the `is_back_filled` rate". The **second half** of that PM question —
  *do back-filled applications convert differently?* — is a **cross-event** comparison against
  `purchase_completed`, which is not yet live; see
  [start-to-purchase-conversion](/metrics/start-to-purchase-conversion.md) and
  [start-to-purchase-not-live-gap](/contradictions/start-to-purchase-not-live-gap.md).

# Source

- Serving MV: `atlys.mv_application_started_daily` → `atlys.application_started_daily`.
- Table: [application_started](/tables/application_started.md).
- Spec: `specs/10_application_started/spec.md`; metrics: `Atlys/schemas/10_application_started.metrics.json`.
