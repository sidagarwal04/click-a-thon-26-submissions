---
id: overview-product-boundaries
title: Product Boundaries
type: overview
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: current
priority: critical
tags: [product, boundaries, phase-1a]
related: ["[[Overview MOC]]", "[[Current Implementation Status]]", "[[Investigation Trust Loop]]"]
repo_path: README.md
code_refs: [README.md, apps/api/src/zentra_api/routes.py]
---

# Product Boundaries

## Current product

ZentraOS converts a governed business question into a tenant-isolated,
evidence-backed Investigation. The current deployment exposes two fixed
scenarios: `eu_refund_spike` and `na_channel_growth`.

The workflow uses an Orchestrator, SQL Analyst, and Evaluator over governed Cube
metrics. Confidence is bounded by sample size and model independence before
publication policy applies. The EU scenario requires Human Approval; the NA
scenario can publish automatically when evaluation converges. Both expose a
safe Replay timeline without hidden reasoning or raw analytical rows.

Phase 2 is now defined but incomplete. It adds an independent Insight Agent,
resolvable Evidence Citations, deletion Tombstones, and external Replay
comprehension. See [[Phase 2 - Insight Auditor and Replay]].

Phase 3 is accepted but unimplemented. It generalizes the trust path to related
CSV/Parquet uploads and one assisted PostgreSQL Data Connection. See
[[Phase 3 - Governed Bring Your Own Data]].

## Current users

Users participate through a Tenant Membership:

- owner/admin/member can create and view an Investigation;
- viewer can view but not create;
- owner/admin can approve or reject a Human Approval.

## Deliberately outside the boundary

- Arbitrary questions, uploads, customer datasets, and generalized connectors.
- Insight, Statistician, and later analytical Agents.
- Resolvable evidence artifacts and deletion Tombstones.
- Investigation listing, streaming, full replay, or cancellation APIs.
- Production deployment automation and cloud operational sign-off.

These are current implementation exclusions, not roadmap exclusions. Phase 3
owns the planned uploaded-data and first-connector subset.

## Product promises

Tenant identity is derived from verified provider context, analytical measures
come from governed semantics, evidence uses `artifact://` references, and audit
records exclude prompts and raw customer data.

Parent: [[Overview MOC]]
