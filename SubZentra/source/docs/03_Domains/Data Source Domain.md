---
id: domain-data-source
title: Data Source Domain
type: domain
status: active
owner: unassigned
source: decision
created: 2026-08-01
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: planned
priority: critical
tags: [domain, data-source, dataset-workspace, connector]
related: ["[[Domains MOC]]", "[[Semantic Modeling]]", "[[Investigation Domain]]", "[[Phase 3 Data Execution]]", "[[adr/0012-complete-phase-3-as-governed-bring-your-own-data]]"]
repo_path: libs/domain/data-source
code_refs: [libs/domain/data-source/CONTEXT.md, libs/foundation/query-engine/src/types/query.ts]
---

# Data Source Domain

Data Source owns which real Tenant data an Investigation may use and the exact
versioned binding that makes evidence reproducible. Canonical definitions live
in the [Data Source context](../../libs/domain/data-source/CONTEXT.md).

## Two source kinds

A Data Source is either a Workspace Snapshot selecting immutable CSV/Parquet
Relation Versions or a live Data Connection through a Connector Type. They
share authorization, semantic approval, policy, evidence, Replay, and deletion
boundaries. Uploaded data uses DuckDB; live data uses Cube.

## Immutable Investigation binding

Every Investigation records Tenant, source, exact Relation Versions or safe
connection fingerprint, Semantic Model version, Query Governance Policy version,
safe fingerprints, and authorization provenance. Unknown, suspended, revoked,
cross-Tenant, drifted, or otherwise ineligible sources fail before execution.

## Uploaded lifecycle

Create Workspace, upload immutable Relations, parse/profile locally, review
classification/relationship/metric drafts, approve a Semantic Model, take a
Snapshot, then retain or dependency-delete. Replacing a file never rewrites a
Snapshot, Query Version, result, citation, or Finding.

## Live state

| Axis | Values |
| --- | --- |
| Lifecycle | provisioning, ready, revoked |
| Activation Stage | authorization, validation, semantic modeling, Tenant approval |
| Availability | enabled, suspended |
| Health | unknown, healthy, degraded, unavailable |

Eligibility is derived. Referenced schema drift blocks new Investigations until
the Tenant approves a remapped model.

## Authority and deletion

Members may upload and investigate. Tenant admins approve models, sensitive
overrides, sample sharing, quotas, and Advanced Mode. Operators may validate and
emergency-suspend live connections but cannot reactivate alone.

Investigation deletion leaves shared Relations. Relation/Workspace deletion
cascades through dependent profiles, models, results, Findings, values, and
evidence. Investigation identity, safe process metadata, immutable Audit Entries,
and minimal citation Tombstones remain.

Parent: [[Domains MOC]]
