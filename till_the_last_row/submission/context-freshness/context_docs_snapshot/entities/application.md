---
type: entity
title: Application
description: One visa application, identified by application_id.
timestamp: 2026-08-01
tags: [entity, application]
---

# Definition

One visa application, identified by `application_id`. Created at the **application_started** step, so events *before* it (card clicks, searches) carry an empty `application_id`.

# Key fields

| field | meaning |
|---|---|
| application_id | primary key |
| destination | chosen destination (ISO-2 code) |
| purpose | application purpose |
| co_travelers | co-traveller count |
| visa_issuance_eta_days | predicted turnaround shown to user (integer days) |

# Note

⚠️ The field name `visa_issuance_eta_days` in the definition conflicts with `eta_shown` in the table column list — see [eta-column-naming](/contradictions/eta-column-naming.md).

# Related

- Tables: [application_started](/tables/application_started.md)
- Relationships: [application-to-funnel](/relationships/application-to-funnel.md)
