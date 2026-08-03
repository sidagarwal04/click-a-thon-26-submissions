---
type: relationship
title: auth_completed → application_started (on user_id)
description: Cross-event conversion join — successful authenticators who go on to start an application, sliceable by is_new_user. Cross-spec (auth 09 × funnel).
timestamp: 2026-08-04
tags: [relationship, join, conversion, cross-event]
---

# Join

```
auth_completed.payload.user_id = application_started.payload.user_id
```

- Grain: one user may have multiple auths and multiple application starts; dedup/first-match per
  user as the question requires.
- `payload.application_id` on `auth_completed` may be empty (auth can precede an application), so
  join on `user_id`, not `application_id`.

# Purpose

Answers spec 09 Q4: **auth → `application_started` conversion by `is_new_user`** — of users who
successfully authenticate, what share start an application, split by new vs returning.

# Notes / caveats

- **No MV serves this** — it is a cross-event join between two base tables; compute at query time.
- Distinct from [auth-completion-rate](/metrics/auth-completion-rate.md) (M4), which is
  auth_completed ÷ auth_started (a different, not-yet-instrumented denominator).
- `is_new_user` lives on `auth_completed` (`Bool`); segment there.

# Source

- Tables: [auth_completed](/tables/auth_completed.md), [application_started](/tables/application_started.md)
- Spec: `specs/09_auth_completed/spec.md` (Q4); live `atlys` schema.
