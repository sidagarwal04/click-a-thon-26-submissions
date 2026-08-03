---
type: contradiction
title: group_id is the metric unit but is untyped and absent from the ORDER BY key
description: group_id defines a "group" (the uniq unit for started/submitted metrics) yet it is not a typed JSON path and is deliberately kept out of the group_family ORDER BY key — indexed only via a CAST bloom_filter. Legitimate design choice, but a smell worth flagging.
timestamp: 2026-08-07
tags: [contradiction, group, family, group_id, schema-smell, D3]
---

# Claim

`group_id` is the **unit of measurement** for the group-family metrics: completion rate and
group-apps-by-destination both count `uniq(group_id)`, and a "group" is defined by its `group_id`.

# Conflicting evidence

On the live [group_family](/tables/group_family.md) base table, `group_id`:

- is **not typed** in the `JSON(...)` hint (only `application_id, destination, docs_complete,
  event, group_size, os, timestamp, user_id` are typed) — it is read via `CAST(payload.group_id,'String')`;
- is **not in the ORDER BY key** `(event, destination, group_size, user_id, timestamp)`;
- is reachable for point lookups only via `idx_group_id` `bloom_filter(0.01)` on the CAST expression.

So the primary metric unit has no typed sub-column and no primary-key locality.

# Provenance

- Claim: `specs/02_group_family/spec.md` (User actions — `group_id` on `group_started`) and
  `Atlys/schemas/02_group_family.metrics.json` (uniq-group formulas).
- Conflicting evidence: live `atlys` DDL for `group_family` and `system.data_skipping_indices`.

# Recommended resolution (do not silently pick a winner)

- **Design intent (D3)** appears deliberate: aggregation happens through the
  [group_family_daily](/tables/group_family_daily.md) MV (which materializes the `uniq(group_id)`
  states), so the base table is optimized for `event/destination/group_size` scans, and `group_id`
  only needs a bloom_filter for occasional single-group drill-downs. Under that intent this is
  **not** a defect.
- **However**, flag for the Instrumentation Agent: if ad-hoc single-group queries on the **base**
  table become common, the bloom_filter on a CAST expression is weaker than a typed path; consider
  typing `group_id` in the JSON hint. The Analytics Agent should prefer the rollup for group-count
  metrics and use the base table's `idx_group_id` only for targeted `group_id` filters.

# Affects

- [group_family](/tables/group_family.md)
- [group_family_daily](/tables/group_family_daily.md)
- [group](/entities/group.md)
