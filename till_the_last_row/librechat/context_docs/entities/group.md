---
type: entity
title: Group
description: A set of co-travellers (family or friends) applying for a visa together under a single application, identified by group_id. One lead traveller starts the group, adds/removes co-travellers, and submits them together.
timestamp: 2026-08-07
tags: [entity, group, family, co-traveller]
---

# Definition

A **group** is a set of co-travellers (family or friends) applying for a visa **together under a
single application**. A lead traveller starts the group (`group_started`), adds co-travellers
(`traveller_added`) — each with a `relation` and a `docs_complete` flag — may drop some
(`traveller_removed`), and submits them together (`group_submitted`). Group applications are a
large share of leisure visas.

# Identity

- `group_id` — the group's unit of identity (one group = one `group_id`).
- ⚠️ `group_id` is **not a typed JSON path** on [group_family](/tables/group_family.md); it is read
  via `CAST(payload.group_id,'String')`. It is indexed via a `bloom_filter` on that CAST expression
  and is used as the `uniq` unit in the daily rollup, but it is deliberately kept **out of the
  ORDER BY key**. See [group-id-untyped-metric-unit](/contradictions/group-id-untyped-metric-unit.md).

# Attributes

- `group_size` — declared number of travellers (2–6 observed); typed `UInt8`, an ORDER BY / rollup dimension.
- `destination` — the group's destination (typed, ORDER BY / rollup dimension).
- `travellers_submitted` — count submitted (untyped payload path on `group_submitted`).
- Per co-traveller: `traveller_index`, `relation`, `docs_complete` (on `traveller_added`).

# Grain

A group is observed **across multiple event rows** (its lifecycle: started → added/removed →
submitted), not as a standalone dimension table. Distinct-group counts are materialized as
`uniq(group_id)` states in [group_family_daily](/tables/group_family_daily.md).

# Related

- Base table: [group_family](/tables/group_family.md)
- Aggregate: [group_family_daily](/tables/group_family_daily.md)
- Entities: [user](/entities/user.md), [application](/entities/application.md), [destination](/entities/destination.md)
- Metrics: [group-completion-rate](/metrics/group-completion-rate.md), [traveller-churn](/metrics/traveller-churn.md), [docs-incomplete-share](/metrics/docs-incomplete-share.md), [group-apps-by-destination](/metrics/group-apps-by-destination.md)
- Source: `specs/02_group_family/spec.md`, live `atlys` schema
