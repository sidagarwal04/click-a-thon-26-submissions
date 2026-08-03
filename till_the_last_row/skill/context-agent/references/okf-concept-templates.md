# OKF Concept Templates

Every file in the bundle (except the reserved `index.md` and `log.md`) is a **concept**:
YAML frontmatter delimited by `---`, then a markdown body. `type` is **required and
non-empty**. `title`, `description`, `tags`, `timestamp` are recommended. Links use
normal markdown; a leading `/` is bundle-root-relative.

Copy a template, fill it from a real source (DDL, live schema, `base_context.md`, or an
Analytics finding), and delete any line you cannot ground in that source.

---

## `overview.md` (type: overview) — holds the version

```markdown
---
type: overview
title: Atlys Analytics — Living Context
description: Business + funnel context that feeds the Analytics Agent.
context_version: 1
timestamp: 2026-08-01
tags: [atlys, funnel, conversion]
---

# Overview
Atlys is a digital visa platform. North-star metric: **conversion**.

# Funnel
`destination_card_clicked → application_started → document_uploaded → purchase_completed`

# Related
- Entities: [user](/entities/user.md), [application](/entities/application.md)
- Metrics: [conversion-rate](/metrics/conversion-rate.md)
- Known issues: [K1-ios-otp-autofill](/known-issues/k1-ios-otp-autofill.md)
```

---

## entity (type: entity)

```markdown
---
type: entity
title: Application
description: One visa application, keyed by application_id.
timestamp: 2026-08-01
tags: [entity]
---

# Definition
Created at `application_started`; events before it carry an empty `application_id`.

# Key fields
| field | meaning |
|---|---|
| application_id | primary key |
| destination | ISO-2 target country |
| visa_issuance_eta_days | predicted turnaround shown to user |

# Related
- Tables: [application_started](/tables/application_started.md)
- Relationships: [application-to-funnel](/relationships/application-to-funnel.md)
```

---

## metric (type: metric)

```markdown
---
type: metric
title: Conversion Rate
description: Headline conversion metric.
timestamp: 2026-08-01
tags: [metric, conversion]
---

# Formula
`completed purchases ÷ sessions` (a session = one app-open / web visit).

# Notes / caveats
⚠️ A conflicting funnel definition exists — see
[dual-conversion-definition](/contradictions/dual-conversion-definition.md).

# Source
`base_context.md` §4.
```

---

## table (type: table)

```markdown
---
type: table
title: application_started
description: Funnel event — user starts an application.
source_ddl: Atlys/schemas/01_express_checkout.sql
timestamp: 2026-08-01
tags: [table, funnel]
---

# Purpose
Emitted when a user starts an application. Creates `application_id`.

# Schema
| column / path | type | notes |
|---|---|---|
| event.application_id | LowCardinality(String) | ORDER BY |
| event.timestamp | DateTime64(3,'UTC') | ORDER BY tail |
| ch_insert_time | DateTime64(3,'UTC') MATERIALIZED | partition/TTL |

- ORDER BY: `(event.application_id, event.timestamp)`
- PARTITION BY: `toYYYYMMDD(ch_insert_time)` · TTL: 90d
- Materialized views: {list or "none"}

# Measures
- [conversion-rate](/metrics/conversion-rate.md) denominator (application starts)

# Related
- Entities: [application](/entities/application.md)
```

---

## relationship (type: relationship)

```markdown
---
type: relationship
title: application → funnel tables
description: Join map for application_id.
timestamp: 2026-08-01
tags: [relationship, join]
---

# Join
`application_started.application_id` → `document_uploaded`, `pay_now_clicked`,
`purchase_completed` (on `application_id`).

# Order
By `timestamp` ascending within a `user_id` / `application_id`.
```

---

## known-issue (type: known-issue)

```markdown
---
type: known-issue
title: K1 — iOS WebKit OTP autofill regression
description: OTP field fails to autofill on recent iOS builds.
issue_id: K1
status: open
timestamp: 2026-08-01
tags: [known-issue, ios, payment]
---

# Symptom
Payment OTP field fails to autofill; some iOS users abandon at pay step.

# Exposure
Payment-heavy geos (Gulf card users). Watch `pay_now_clicked → purchase_completed` for iOS.

# Source
`base_context.md` §5.
```

---

## contradiction (type: contradiction)

```markdown
---
type: contradiction
title: Dual definition of "conversion"
description: Two conflicting conversion formulas in the base context.
severity: high
status: open
timestamp: 2026-08-01
tags: [contradiction, metric]
---

# Claim A
`base_context.md` §4 headline: conversion = purchases ÷ **sessions**.

# Claim B
`base_context.md` §4 note: conversion = purchase_completed users ÷ **application_started**.

# Why it matters
Different denominators → non-comparable numbers across dashboards.

# Recommended resolution
Name them distinctly (e.g. `session_conversion` vs `funnel_conversion`) and have the
Analytics Agent state which it uses. Needs product confirmation.

# Affects
- [conversion-rate](/metrics/conversion-rate.md)
```
