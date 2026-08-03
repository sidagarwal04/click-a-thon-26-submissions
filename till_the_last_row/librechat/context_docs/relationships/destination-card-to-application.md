---
type: relationship
title: destination_card_clicked → application_started
description: First funnel transition — join on user_id with timestamp ordering.
timestamp: 2026-08-02
tags: [relationship, join, funnel]
---

# Join

`destination_card_clicked.user_id` → `application_started.user_id`

# Why not application_id?

At the `destination_card_clicked` stage, `application_id` is typically empty (the application has not been created yet). The join must use `user_id` and enforce `application_started.timestamp > destination_card_clicked.timestamp`.

# Order

By `timestamp` ascending within a `user_id`. A single user may click multiple destination cards before (or without) starting an application.

# Cardinality

Many-to-many: one user can click many cards and start many applications. For funnel analysis, typically take the first card click per user/session or per application window.

# Source

`specs/08_destination_card_clicked/spec.md` — `application_id` confirmed present but usually empty.

# Related

- Tables: [destination_card_clicked](/tables/destination_card_clicked.md), [application_started](/tables/application_started.md)
- Relationships: [application-to-funnel](/relationships/application-to-funnel.md), [user-fanout](/relationships/user-fanout.md)
