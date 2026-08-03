---
id: adr-0022
title: Sequence Step execution is distinct from Phase 3 query execution
type: adr
status: active
owner: unassigned
source: repository
created: 2026-08-01
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: current
priority: high
tags: [adr, sequence, chdb, lambda, data-steward, semantic-model]
related:
  - "[[Sequence Domain]]"
  - "[[adr/0012-complete-phase-3-as-governed-bring-your-own-data]]"
  - "[[adr/0016-cube-is-the-single-tenant-scoped-analytical-gateway]]"
depends_on:
  - "[[adr/0012-complete-phase-3-as-governed-bring-your-own-data]]"
repo_path: libs/adapters/sequence-execution
code_refs:
  - libs/domain/agent-execution/src/zentra_domain_agent_execution/ports.py
  - libs/domain/sequence/src/zentra_domain_sequence/sequence.py
  - libs/adapters/sequence-execution/src/zentra_adapter_sequence_execution/chdb_execution.py
  - libs/adapters/sequence-execution/src/zentra_adapter_sequence_execution/lambda_port.py
  - infra/terraform/lambda.tf
---

# Sequence Step execution is distinct from Phase 3 query execution

## Status

Accepted. Amends, and does not supersede, [[adr/0012-complete-phase-3-as-governed-bring-your-own-data]].

## Context

ADR-0012 accepts DuckDB on a scale-to-zero Google Cloud Run worker, reading
from Cloudflare R2, as Phase 3's data execution engine. That decision is
about one specific workload: SQL Analyst compiling a governed question into
a Query Version and executing it against an approved Semantic Model.

Sequence introduces a second, earlier workload with a different shape: Data
Steward applying one typed transform (`drop_nulls`, `cast_type`, `dedupe`,
`filter_rows`, `rename_column`) to a Raw Table or a prior Prepared Table,
producing a new immutable Prepared Table. This is never a governed query
against a Semantic Model — a Sequence's Final Table is what Semantic Modeler
models *afterward*; Sequence Step execution never touches the Semantic Layer
or Cube at all (see [[adr/0016-cube-is-the-single-tenant-scoped-analytical-gateway]],
which remains the single gateway for governed queries, unchanged by this
decision).

Two different Agents, two different data shapes, two different trust
boundaries — Data Steward's typed catalog is enforced at the domain layer
before any execution happens, independent of whichever engine runs it.
Nothing about picking an engine for one workload obligates the same choice
for the other.

## Decision

Sequence Step execution uses chDB (embedded ClickHouse) running inside AWS
Lambda — not DuckDB on Google Cloud Run.

chDB is chosen because a Sequence's Raw Table may be a Connector Source
Table already living in ClickHouse; chDB speaks ClickHouse's dialect
natively and reads it in place via `remote()`, with no data movement. The
same engine also reads an uploaded Data Source Dataset Table Version
directly via `file()`/`s3()`. One engine, one dialect, for both Raw Table
origins.

AWS Lambda hosts it: a scale-to-zero, per-invocation microVM, the same
isolation and cost shape ADR-0012 chose Cloud Run for, on the other cloud
this Tenant already has committed spend and infrastructure in (ClickHouse
Cloud's audit service already runs `cloud_provider = "aws"`).

## Consequences

- Two data-execution stacks now exist side by side: DuckDB/Cloud Run/R2/
  Google Secret Manager for governed queries (ADR-0012, unimplemented as of
  this writing), and chDB/Lambda for Sequence Step transforms (this ADR,
  implemented). This is accepted complexity, not an oversight — merging them
  into one engine would force one workload's constraints onto the other for
  no benefit, since they never share a boundary (a Final Table, not a raw
  execution result, is the only thing that crosses from one to the other).
- Sequence Step execution introduces the first AWS provider and first
  AWS compute resource in this repo's Terraform. Real deployment (a live
  AWS account, a scoped CI OIDC role, this Terraform's own state backend)
  is a separate, deliberately un-bundled step from writing the resource
  definitions themselves.
- `zentra_adapter_sequence_execution` depends on `zentra_adapter_postgres`
  directly (to persist Sequence Step results) — the first intentional
  adapter-to-adapter dependency in this codebase, and deliberately excluded
  from `.importlinter`'s `adapters-do-not-depend-on-each-other` contract
  rather than silently passing it.
- If Phase 3's query execution is ever built out to also use chDB (since
  chDB can serve as a DuckDB-shaped query engine too), that would be its own
  decision revisiting ADR-0012 directly — this ADR does not pre-empt it, and
  does not extend chDB's role here beyond Sequence Step execution.

## Alternatives considered

**Route Sequence Step execution through Cube.** Rejected: Cube compiles
semantic queries against an approved model to SQL; Data Steward's typed
operations run before any Semantic Model exists for this data. Stretching
Cube to also execute imperative row-level transforms has no precedent in
this codebase and no clear benefit over a dedicated, much simpler port.

**Reuse ADR-0012's DuckDB/Cloud Run worker for Sequence Steps too.** Rejected:
would require extracting Connector-sourced ClickHouse data into DuckDB's
reach before every transform, reintroducing exactly the data-movement
ADR-0014/0016 already decided against for Connector data.
