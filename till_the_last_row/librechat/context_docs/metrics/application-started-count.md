---
type: metric
title: Application Started Count
description: Count of application_started events (and distinct users), sliceable by destination, purpose, flow, eta_shown, citizenship, is_back_filled. Served directly by the daily rollup.
metric_id: application_started_count
served_by_mv: mv_application_started_daily
computable: true
timestamp: 2026-08-05
tags: [metric, funnel, live]
---

# Formula

```
application_started_count = countMerge(applications)   -- total starts
unique_starters           = uniqMerge(unique_users)    -- distinct user_id
```

From the rollup:

```sql
SELECT day, destination, purpose,
       countMerge(applications) AS applications,
       uniqMerge(unique_users)  AS unique_users
FROM atlys.application_started_daily
GROUP BY day, destination, purpose
ORDER BY applications DESC
```

# Notes / caveats

- **Clear + served**: single-event metric, materialized by `mv_application_started_daily`.
- Sliceable **only** by the seven rollup dims: `day, destination, purpose, flow, eta_shown,
  citizenship, is_back_filled`. Other slices (e.g. `co_travelers`, `device_type`, `os`) require the
  base table.
- Answers the PM's "which citizenship × destination pairs generate the most applications" (spec 10).
- `applications` (events) ≠ `unique_users` (distinct users) — a user can start multiple applications.

# Source

- Serving MV: `atlys.mv_application_started_daily` → `atlys.application_started_daily`.
- Table: [application_started](/tables/application_started.md), [application_started_daily](/tables/application_started_daily.md).
- Spec: `specs/10_application_started/spec.md`; metrics: `Atlys/schemas/10_application_started.metrics.json`.
