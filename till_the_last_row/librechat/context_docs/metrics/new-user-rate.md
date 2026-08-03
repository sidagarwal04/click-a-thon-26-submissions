---
type: metric
title: New-User Rate (by acquisition channel)
description: M3 — share of successful authentications that are a user's first-ever (is_new_user = 1), broken down by derived acquisition_channel (paid_google / paid_meta / organic).
metric_id: M3
served_by_mv: auth_completed_metrics_mv
timestamp: 2026-08-04
tags: [metric, auth, acquisition, live]
---

# Formula

```
new_user_rate = new_user_completions / completions
```

sliced by `acquisition_channel`, a **user-confirmed derived dimension** (`confirmed_by_user: true`):

```
acquisition_channel = gclid != '' ? 'paid_google'
                    : fbclid != '' ? 'paid_meta'
                    : 'organic'
```

```sql
SELECT acquisition_channel,
       sumMerge(new_user_completions) AS new_users,
       countMerge(completions)        AS completions,
       new_users / completions        AS new_user_rate
FROM atlys.auth_completed_metrics_agg
GROUP BY acquisition_channel
ORDER BY new_user_rate DESC
```

# Notes / caveats

- `acquisition_channel` is derived in the MV from `gclid` / `fbclid` (both untyped envelope paths);
  the base table stores the raw ids, the agg stores only the derived channel.
- Order matters: `gclid` wins over `fbclid` when both are present (paid_google precedence).
- Answers spec Q3 (new-user rate by acquisition source).

# Source

- Serving MV: `atlys.auth_completed_metrics_mv` → `auth_completed_metrics_agg` (`new_user_completions`, `completions`, dim `acquisition_channel`).
- Table: [auth_completed](/tables/auth_completed.md).
- Spec: `specs/09_auth_completed/spec.md` (Q3); metrics: `Atlys/schemas/09_auth_completed.metrics.json` (M3).
