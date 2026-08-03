---
type: table
title: search_typed
description: Supporting event — user types a destination search.
kind: supporting
timestamp: 2026-08-01
tags: [table, supporting]
---

# Purpose

Emitted when user types a destination search.

# Key event-specific columns

| column | notes |
|---|---|
| search_term | query string |
| results_count | number of results |
| source | search entry point |

# Ordering

⚠️ Legacy `ORDER BY (id, timestamp, user_id)` — queries filter by time/segment, never by `id`. See [legacy-id-order-key](/contradictions/legacy-id-order-key.md).

# Related

- Entities: [user](/entities/user.md)
- Relationships: [supporting-on-user](/relationships/supporting-on-user.md)
