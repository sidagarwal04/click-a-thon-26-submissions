---
type: contradiction
title: auth_completion_rate (M4) requires an uninstrumented auth_started event
description: The metrics manifest declares M4 = auth_completed ÷ auth_started, but auth_started is not part of the 09_auth_completed spec and has no table — the metric is not computable.
severity: medium
status: open
timestamp: 2026-08-04
tags: [contradiction, gap, metric, cross-event, auth]
---

# Claim

`Atlys/schemas/09_auth_completed.metrics.json` declares metric **M4 `auth_completion_rate`** =
`count(auth_completed) / count(auth_started)`.

# Conflicting claim / evidence

The `09_auth_completed` spec instruments **only** the `auth_completed` event → one base table
`atlys.auth_completed`. There is **no `auth_started` event or table** in the spec, in the live
`atlys` schema, or in the events sample. The `auth_completed_metrics_agg` rollup materializes only
the **numerator** (`completions`); the denominator has no source. Accordingly M4 carries
`served_by_mv: null`.

# Why it matters

Any attempt to compute `auth_completion_rate` from this spec alone will fail or be silently wrong.
`payload.attempts` is **not** a valid denominator — it counts retries *within* a successful auth,
not started-but-abandoned auth sessions.

# Recommended resolution

- **Do not** approximate M4 from `attempts` or from `auth_completed` alone.
- Treat M4 as a **documented gap** until an `auth_started` event is instrumented (a separate
  Instrumentation Agent task).
- The Analytics Agent should mark M4 as "not computable — requires `auth_started`" when asked,
  rather than substituting a proxy.

# Source

- Metrics: `Atlys/schemas/09_auth_completed.metrics.json` (M4, `served_by_mv: null`).
- Spec: `specs/09_auth_completed/spec.md` (no auth_started); live `atlys` schema (no auth_started table).

# Affects

- [auth-completion-rate](/metrics/auth-completion-rate.md)
- [auth_completed](/tables/auth_completed.md)
