---
type: metric
title: Auth Method Mix
description: M1 — distribution of successful authentications across auth methods (otp / google / apple / email), sliceable by device_type, os, and geo.
metric_id: M1
served_by_mv: auth_completed_metrics_mv
timestamp: 2026-08-04
tags: [metric, auth, live]
---

# Formula

Per method, share of total completions:

```
auth_method_mix(m) = completions[auth_method = m] / sum(completions)
```

From the rollup:

```sql
SELECT auth_method,
       countMerge(completions) AS completions,
       completions / sum(countMerge(completions)) OVER () AS share
FROM atlys.auth_completed_metrics_agg
GROUP BY auth_method
ORDER BY completions DESC
```

# Notes / caveats

- Slice by `device_type`, `os`, `geoip_country_code` (all agg dimensions) for spec questions 1 and 5.
- `os` can be empty/null on some Android rows — see [android-os-null](/contradictions/android-os-null.md); an `os` slice under-counts those.
- Methods observed in sample data so far: `google`, `otp`. Spec declares full set `otp/google/apple/email`.

# Source

- Serving MV: `atlys.auth_completed_metrics_mv` → `atlys.auth_completed_metrics_agg` (`completions`).
- Table: [auth_completed](/tables/auth_completed.md).
- Spec: `specs/09_auth_completed/spec.md` (Q1); metrics: `Atlys/schemas/09_auth_completed.metrics.json` (M1).
