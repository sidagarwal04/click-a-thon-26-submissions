---
type: metric
title: Auth Retry Rate
description: M2 — share of successful authentications that took more than one attempt (attempts > 1), a friction signal, sliceable by auth_method.
metric_id: M2
served_by_mv: auth_completed_metrics_mv
timestamp: 2026-08-04
tags: [metric, auth, friction, live]
---

# Formula

```
auth_retry_rate = retried_completions / completions
```

where `retried_completions` counts completions with `attempts > 1`.

```sql
SELECT auth_method,
       sumMerge(retried_completions) AS retried,
       countMerge(completions)        AS completions,
       retried / completions          AS retry_rate
FROM atlys.auth_completed_metrics_agg
GROUP BY auth_method
ORDER BY retry_rate DESC
```

# Notes / caveats

- `attempts` is an **untyped** payload path read via `CAST(payload.attempts AS UInt32)`; the
  `retried_completions` state is computed at MV time, so queries read the pre-aggregated state.
- Answers spec Q2 (which method retries most) and combines with [auth-method-mix](/metrics/auth-method-mix.md) for Q5 (geo × method × retry).

# Source

- Serving MV: `atlys.auth_completed_metrics_mv` → `auth_completed_metrics_agg` (`retried_completions`, `completions`).
- Table: [auth_completed](/tables/auth_completed.md).
- Spec: `specs/09_auth_completed/spec.md` (Q2); metrics: `Atlys/schemas/09_auth_completed.metrics.json` (M2).
