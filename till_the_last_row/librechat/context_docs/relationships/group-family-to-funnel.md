---
type: relationship
title: group_family ↔ pre-purchase funnel (user_id / application_id)
description: How the group_family flow relates to the main pre-purchase funnel — a group application is one application_id owned by a lead user_id; group events join to funnel events on user_id and application_id.
timestamp: 2026-08-07
tags: [relationship, group, family, funnel, application, user]
---

# Shape

A group application is a **single application** created by one lead traveller. It relates to the
main pre-purchase funnel (`destination_card_clicked → application_started → document_uploaded →
purchase_completed`) through shared envelope keys.

# Join keys

- **`user_id`** — the lead traveller; joins group events to funnel events (typed `String`, ORDER BY col 4 on the base).
- **`application_id`** — the group's application; joins to funnel/application tables (typed `LowCardinality(String)`).
- **`destination`** — shared analysis dimension across group and funnel.

# Notes

- ⚠️ **Grain differs**: the funnel is per-user/per-application; the group flow is per-`group_id`
  with **many co-travellers** (only the lead traveller carries the funnel `user_id`). Co-travellers
  appear as `traveller_added` rows, not as funnel users — do **not** count co-travellers as funnel users.
- `group_id` is unique to the group flow; it does not appear in the main funnel tables.

# Related

- Tables: [group_family](/tables/group_family.md), [application_started](/tables/application_started.md), [purchase_completed](/tables/purchase_completed.md)
- Entities: [group](/entities/group.md), [user](/entities/user.md), [application](/entities/application.md)
- Relationships: [start-to-purchase](/relationships/start-to-purchase.md)
- Source: `specs/02_group_family/spec.md`, live `atlys` schema
