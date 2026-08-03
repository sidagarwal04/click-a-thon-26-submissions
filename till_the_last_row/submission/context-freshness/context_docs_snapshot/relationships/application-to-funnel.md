---
type: relationship
title: Application → funnel tables
description: Join map for application_id across post-start funnel events.
timestamp: 2026-08-02
tags: [relationship, join]
---

# Join

`application_started.application_id` → `document_uploaded`, `pay_now_clicked`, `purchase_completed` (on `application_id`)

# Order

By `timestamp` ascending within a `user_id` / `application_id`.

# Note

Events *before* `application_started` (card clicks, searches) carry an empty `application_id`. To trace a user's journey from card click → application, join on `user_id` + timestamp order — see [destination-card-to-application](/relationships/destination-card-to-application.md).

# Source

`base_context.md` §6.
