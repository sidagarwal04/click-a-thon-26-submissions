---
id: domain-semantic-modeling
title: Semantic Modeling
type: domain
status: active
owner: unassigned
source: context-map
created: 2026-07-29
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: current
priority: high
tags: [domain, semantic-model, cube]
related: ["[[Domains MOC]]", "[[Cube Semantic Model]]", "[[Synthetic Warehouse]]"]
repo_path: infra/cube
code_refs:
  - libs/domain/CONTEXT.md
  - infra/cube/model/cubes/Commerce.js
---

# Semantic Modeling

A Semantic Metric is a governed business measure with one agreed definition and
grain for a Tenant. It is not an ad hoc calculated field or raw-SQL metric.

Phase 1A's Cube model exposes gross revenue, net revenue, order count, average
order value, refund amount, refund rate, active customers, and repeat-purchase
rate over the synthetic commerce warehouse.

The deterministic Investigation consumes governed measures and dimensions
through Cube. The Finding retains comparisons and an `artifact://` reference,
not raw query rows.

## Phase 3 target

Uploaded Relations and live metadata may produce Column Classification,
Relationship, and Metric Drafts. Tenant approval creates an immutable Semantic
Model version. Draft-dependent Findings require Human Approval. Many-to-many
joins require a bridge or recorded row-multiplication acknowledgment. Material
schema drift blocks new Investigations until remapping and approval.

Implementation detail: [[Cube Semantic Model]]. Canonical definition:
[ZentraOS domain context](../../libs/domain/CONTEXT.md).

Phase 3 source language: [Data Source context](../../libs/domain/data-source/CONTEXT.md).

Parent: [[Domains MOC]]
