---
type: relationship
title: Supporting tables on user_id
description: Supporting events join on user_id only.
timestamp: 2026-08-01
tags: [relationship, join]
---

# Join

Supporting tables (`search_typed`, `landing_page_scrolled`, `auth_completed`) join on `user_id`.

# Note

They may precede an application, so `application_id` can be empty. For the now-live
[auth_completed](/tables/auth_completed.md), `payload.application_id` is present in the ORDER BY but
may be empty when auth happens before an application starts; the durable join key is `user_id`.

For the auth → funnel conversion (spec Q4), see [auth-to-application](/relationships/auth-to-application.md).

# Source

`base_context.md` §6; live schema `Atlys/schemas/09_auth_completed.sql`.
