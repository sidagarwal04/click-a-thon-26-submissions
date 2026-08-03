---
id: overview-phase-3-governed-byod
title: Phase 3 - Governed Bring Your Own Data
type: overview
status: active
owner: unassigned
source: decision
created: 2026-08-01
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: planned
priority: critical
tags: [phase-3, data-source, csv, parquet, postgres, launch]
related: ["[[Overview MOC]]", "[[Current Implementation Status]]", "[[Data Source Domain]]", "[[Phase 3 Data Execution]]", "[[adr/0012-complete-phase-3-as-governed-bring-your-own-data]]"]
depends_on: ["[[Phase 2 - Insight Auditor and Replay]]", "[[Investigation Trust Loop]]", "[[Semantic Modeling]]"]
repo_path: .
code_refs:
  - libs/foundation/query-engine/src/types/query.ts
  - libs/foundation/query-engine/src/compiler/sql-compiler.ts
  - libs/domain/agent-execution/src/zentra_domain_agent_execution/ports.py
  - libs/adapters/cube/src/zentra_adapter_cube/semantic.py
---

# Phase 3 - Governed Bring Your Own Data

Phase 3 is **accepted and planned, not implemented**. Its durable architecture
is [[adr/0012-complete-phase-3-as-governed-bring-your-own-data]]; this note owns
mutable delivery status, launch sequence, and completion evidence.

## Product promise

A User uploads related CSV or Parquet files, confirms the meaning and joins the
AI proposes, asks a real business question, and receives an evidence-cited
Finding. “How this was calculated” exposes the visual governed plan and Replay
explains why publication was automatic or gated and whether root cause remains
unresolved.

One founder-assisted public-TLS PostgreSQL Data Connection proves the same
boundary against a live warehouse. It is beta scope and does not block the
self-service file launch.

## What ships

- Multiple CSV/Parquet Relations in one Dataset Workspace.
- Immutable Relation Versions and one Workspace Snapshot per Investigation.
- Safe parsing, local profiling, classification, and rejection reports.
- AI-proposed relationships and metrics with explicit Tenant approval.
- Natural-language questions compiled into a visual Governed Query Plan.
- Advanced DuckDB SQL as a read-only last-resort override.
- Server-side bounded DuckDB execution and evidence-safe aggregates.
- One versioned Connector Port and one PostgreSQL Connector Type.
- Read-only credentials, scope, health, revoke, drift, and Cube routing.
- Exact source/model/policy/Query Versions in citations and Replay.
- Dependency-aware deletion and Tombstones.

## Four-stage launch experience

1. **Upload** — drop related files; inspect Relations, types, and errors.
2. **Review Model** — confirm classifications, relationships, and metrics.
3. **Ask** — enter a business question; clarify only material ambiguity.
4. **Understand** — read the cited Finding and inspect the governed calculation.

The wow moment is not a connector form. It is turning the User's own related
data into a calculation they can inspect and a Finding they can trust.

## One-month solo-founder sequence

### Week 1 — source and governance foundation

- Add Data Source vocabulary and persistence contracts.
- Implement private R2 upload intake, Relation metadata, hashes, quotas, and
  deletion state.
- Ingest CSV/Parquet into a synthetic Workspace fixture.
- Produce safe profiles and Column Classification Drafts.
- Extend Query only for visual operations needed by launch.

**Gate:** two fixture files produce immutable Relations, profiles, and one
authorized Snapshot without exposing raw data to an Agent.

### Week 2 — AI plan and bounded execution

- Extend SQL Analyst to produce a Governed Query Plan.
- Implement relationship proposals, cardinality warnings, and approval.
- Add Query Version persistence and deterministic validation.
- Deploy the minimal Cloud Run DuckDB worker with AST/sandbox enforcement.
- Execute multi-table plans inside Tenant budgets.

**Gate:** a natural-language question over joined files produces a validated
aggregate; injection, side-effect, and cross-Tenant tests fail closed.

### Week 3 — complete trusted user path

- Build Upload, Review Model, Ask, and Understand states.
- Add visual editing, version comparison, and Advanced SQL Override.
- Feed aggregates through Evaluator, Insight, citations, publication, Replay,
  and deletion.
- Surface data-quality observations and provisional-semantic gates.

**Gate:** uploaded data reaches a cited Draft Finding, publication decision,
Replay, and Tombstones after deletion.

### Week 4 — PostgreSQL beta and launch proof

- Implement Connector Port and security-focused conformance tests.
- Add public-TLS PostgreSQL validation, read-only proof, vault reference, Cube
  routing, suspension/revocation, and drift checks.
- Record cost/latency/volume, leakage, rotation, and failure baselines.
- Run an uncoached Validation User session over two related files.
- Fix only launch-promise blockers; defer breadth.

**Gate:** self-service is product-validated; PostgreSQL is either conformance-
passing beta or explicitly withheld.

## Parallel boundary with Phase 2

Safe in parallel: terminology, ports, Workspace/Relation persistence, fixtures,
parsing, profiling, classification, Query Plan/Version contracts, DuckDB policy,
Connector conformance, and Upload/Review UI.

Integration must wait for stable Phase 2 Insight-owned Draft Finding, Evidence
Citation, publication reason, Replay composition, and Tombstone contracts.
Phase 3 consumes them and never creates parallel models.

## Launch defaults

| Control | Default |
| --- | --- |
| Relations per Workspace | 10 |
| Upload size | 250 MB per file |
| Source storage | 1 GB per Tenant |
| Active Workspaces | 3 per Tenant |
| Concurrent queries | 2 per Tenant; 1 per worker |
| Query timeout | 60 seconds |
| Aggregate result ceiling | 100,000 cells before reduction |
| Temporary retention | 24 hours |
| Cloud Run instances | minimum 0, maximum 1 initially |

Operator overrides are allowed and audited; billing plans are deferred.

## Completion evidence

### Engineering-complete

- [ ] Multiple Relations import and version without mutation.
- [ ] Relationship and Metric approval creates immutable model versions.
- [ ] SQL Analyst produces an attributable Query Version.
- [ ] Visual/Advanced edits create new versions and rerun.
- [ ] DuckDB accepts permitted relational SQL and rejects side effects.
- [ ] Tenant, source, model, policy, quota, and classification fail closed.
- [ ] Aggregate reaches the Phase 2 Evaluator/Insight trust path.
- [ ] Citations resolve and Replay explains source and calculation.
- [ ] Investigation, Relation, and Workspace deletion cascade correctly.
- [ ] PostgreSQL passes conformance or is withheld from beta.
- [ ] Cost, latency, leakage, rotation, revoke, timeout, and drift are measured.

### Product-validated

- [ ] One uncoached target User uploads two related files.
- [ ] The User confirms or corrects a proposed relationship.
- [ ] The User asks a real question and understands plan and Finding.
- [ ] The User follows each substantive claim to citations.
- [ ] The User explains automatic versus gated publication.
- [ ] The User recognizes unresolved root cause.
- [ ] A dated, data-safe validation record captures outcomes and failures.

Documentation alone satisfies no checkbox.

## Cost envelope

The architecture aims for near-zero launch cost, not permanently free service.
R2 Standard currently includes 10 GB-month, one million write-class operations,
ten million read-class operations, and free egress monthly. Cloud Run has
recurring CPU/memory allowances and scales the worker to zero. Secret Manager
includes six active secret versions and 10,000 accesses monthly. Billing alerts
and Tenant quotas are release requirements.

Official pricing is authoritative:
[R2](https://developers.cloudflare.com/r2/pricing/),
[Cloud Run](https://cloud.google.com/run/pricing), and
[Secret Manager](https://cloud.google.com/secret-manager/pricing).

## Deliberately deferred

- Connectors beyond PostgreSQL and self-service warehouse activation.
- Private networking and dedicated/residency deployments.
- Scheduled sync, CDC, writeback, and incremental ingestion.
- Excel, JSON, APIs, Sheets, archives, URLs, and cross-workspace joins.
- Multi-dialect SQL, ETL, notebooks, dashboards, and visual SQL IDEs.
- Automatic semantics/cleaning and raw-row model access.
- Statistician, causal proof, Root Cause promises, and more Agents.
- Billing plans, marketplace, Kubernetes, and persistent pre-aggregations.

## Source authority

The numbered roadmap establishes Phase 3 as the first real connector. ADR 0012
refines the launch path without replacing that milestone. Current code remains
implementation truth; this status note changes as evidence lands.

Parent: [[Overview MOC]]
