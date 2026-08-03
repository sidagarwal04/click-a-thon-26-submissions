---
type: entity
title: User
description: A traveller identified by user_id, present on every event.
timestamp: 2026-08-01
tags: [entity, user]
---

# Definition

A traveller. Identified by `user_id` (a 28-char string), present on every event.

# Behavior

A user may browse many destinations and start multiple applications.

# Key fields

| field | meaning |
|---|---|
| user_id | primary identifier, 28-char string |

# Related

- Tables: all event tables join on `user_id`
- Relationships: [user-fanout](/relationships/user-fanout.md)
