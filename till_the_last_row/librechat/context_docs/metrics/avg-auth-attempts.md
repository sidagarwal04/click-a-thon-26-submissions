---
type: metric
title: Average Auth Attempts
description: M5 — mean number of attempts per successful authentication (total_attempts / completions), a friction-depth signal complementing the retry rate.
metric_id: M5
served_by_mv: auth_completed_metrics_mv
timestamp: 2026-08-04
tags: [metric, auth, friction, live]
---

# Formula

```
avg_auth_attempts = total_attempts / completions
```

```sql
SELECT auth_method,
       sumMerge(total_attempts) AS attempts,
       countMerge(completions)  AS completions,
       attempts / completions   AS avg_attempts
FROM atlys.auth_completed_metrics_agg
GROUP BY auth_method
ORDER BY avg_attempts DESC
```

# Notes / caveats

- Derived from the untyped `payload.attempts` path (`CAST(... AS UInt32)`), summed into
  `total_attempts` at MV time.
- Complements [auth-retry-rate](/metrics/auth-retry-rate.md): retry rate = *how often* users
  retry; avg attempts = *how deep* the friction goes.
- Mapping M5 → `total_attempts` state is grounded in the live agg schema; confirm the exact metric
  label against `Atlys/schemas/09_auth_completed.metrics.json` when the manifest is read directly.

# Source

- Serving MV: `atlys.auth_completed_metrics_mv` → `auth_completed_metrics_agg` (`total_attempts`, `completions`).
- Table: [auth_completed](/tables/auth_completed.md).
- Spec: `specs/09_auth_completed/spec.md` (Q2 friction); metrics: `Atlys/schemas/09_auth_completed.metrics.json` (M5).
