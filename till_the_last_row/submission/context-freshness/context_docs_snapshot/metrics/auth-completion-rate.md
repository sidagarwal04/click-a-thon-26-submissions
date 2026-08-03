---
type: metric
title: Auth Completion Rate
description: M4 — successful auths ÷ auth attempts started (auth_completed / auth_started). CROSS-EVENT — not computable from the 09_auth_completed spec alone because auth_started is not yet instrumented.
metric_id: M4
served_by_mv: null
computable: false
timestamp: 2026-08-04
tags: [metric, auth, cross-event, gap]
---

# Formula

```
auth_completion_rate = count(auth_completed) / count(auth_started)
```

# Notes / caveats

- ⚠️ **Not served by any MV** (`served_by_mv: null`) and **not currently computable**: it requires
  an `auth_started` event/table that is **not part of the `09_auth_completed` spec** and is not yet
  instrumented in `atlys`.
- The `auth_completed_metrics_agg` rollup provides only the numerator (`completions`); the
  denominator has no source.
- Tracked as a gap — see [auth-completion-rate-cross-event-gap](/contradictions/auth-completion-rate-cross-event-gap.md).
- Do **not** approximate the denominator from `attempts`: `attempts` counts retries within a
  *successful* auth, not started-but-abandoned auth sessions.

# Source

- Table: [auth_completed](/tables/auth_completed.md) (numerator only).
- Spec: `specs/09_auth_completed/spec.md`; metrics: `Atlys/schemas/09_auth_completed.metrics.json` (M4).
