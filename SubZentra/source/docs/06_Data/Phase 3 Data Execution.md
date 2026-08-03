---
id: data-phase-3-execution
title: Phase 3 Data Execution
type: data-model
status: active
owner: unassigned
source: decision
created: 2026-08-01
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: planned
priority: critical
tags: [data, phase-3, duckdb, r2, cube, postgres]
related: ["[[Data MOC]]", "[[Data Source Domain]]", "[[Cube Semantic Model]]", "[[Deployment Topology]]", "[[adr/0012-complete-phase-3-as-governed-bring-your-own-data]]"]
repo_path: .
code_refs: [libs/foundation/query-engine/src/types/query.ts, libs/foundation/query-engine/src/compiler/sql-compiler.ts, libs/adapters/cube/src/zentra_adapter_cube/semantic.py]
---

# Phase 3 Data Execution

Phase 3 adds two governed execution paths behind one Data Source Binding. This
is planned architecture, not current implementation.

```text
Question -> SQL Analyst plan -> authorization -> Query Version
  -> Workspace Snapshot -> DuckDB worker -> validated aggregate
  -> Data Connection    -> Cube          -> validated aggregate
  -> Evaluator -> Insight -> Citation -> publication -> Replay
```

## Uploaded path

R2 is authoritative for private source/evidence objects. PostgreSQL stores
ownership, version metadata, safe schemas, hashes, dependencies, and opaque
references. The Cloud Run worker executes one authorized read-only DuckDB query
against signed Tenant/Snapshot/Query/policy context. It cannot accept browser-
supplied paths or credentials.

The worker validates Advanced SQL AST, disables side effects/external access,
enforces resources, returns a typed outcome and minimal aggregate, and deletes
scratch state within 24 hours. Originals remain immutable.

## Live PostgreSQL path

Secret Manager holds credentials; PostgreSQL holds opaque references and state.
Cube chooses the source from verified Tenant/Data Connection/model context. The
v1 credential is a dedicated read-only PostgreSQL identity over public TLS with
allowlisted schemas/views and timeout. Persistent pre-aggregations are disabled;
transient caches isolate Tenant, connection, and model version.

## Model and audit boundary

Agents receive approved semantic members, safe profiles, assumptions, and
validated aggregates—not raw rows, credentials, object URLs, or executable
capabilities. Bounded samples require explicit admin consent. ClickHouse records
categories, hashes, participants, outcomes, and decisions, never payload values.

## Policy defaults

- one query per worker and two concurrent queries per Tenant;
- 60 seconds and 100,000 aggregate-result cells;
- ten Relations, 250 MB per file, and 1 GB per Tenant;
- no network, external table functions, extensions, or persistent local state.

Success, timeout, quota, rejection, drift, suspension, and revocation are typed
for Replay without copying query/results payloads into ClickHouse.

## Deletion

PostgreSQL owns durable erasure/dependency traversal; R2 owns payload deletion;
Phase 2 owns Finding/evidence redaction; ClickHouse remains immutable; affected
citations resolve to minimal Tombstones.

Parent: [[Data MOC]]
