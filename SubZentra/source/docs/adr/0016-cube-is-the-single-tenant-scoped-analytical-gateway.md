---
id: adr-0016
title: Cube is the single tenant-scoped analytical gateway
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
tags: [adr, cube, connector, semantic-model, tenancy]
related:
  - "[[Semantic Modeling]]"
  - "[[Cube Semantic Model]]"
  - "[[Connector Domain]]"
  - "[[adr/0014-connector-data-bypasses-cube]]"
  - "[[adr/0012-complete-phase-3-as-governed-bring-your-own-data]]"
repo_path: infra/cube
code_refs:
  - infra/cube/cube.js
  - infra/cube/model/cubes/Connector.js
  - apps/api/src/zentra_api/cube_scope.py
  - apps/api/src/zentra_api/connector_model.py
  - apps/api/src/zentra_api/internal_cube_routes.py
  - libs/adapters/cube/src/zentra_adapter_cube/semantic.py
---

# Cube is the single tenant-scoped analytical gateway

## Status

Accepted. Supersedes [[adr/0014-connector-data-bypasses-cube]] in full.
Amends, and does not supersede, [[adr/0012-complete-phase-3-as-governed-bring-your-own-data]].

## Context

ADR-0014 decided that Connector-sourced ClickHouse data would bypass Cube:
analytical agents would reach it directly through a port that only allowed a
join the Join Graph had confirmed. Its stated reasons were that routing
through Cube would need per-tenant model generation, a schema-reload trigger
on every Relation confirmation, and multi-datasource configuration — three
things judged, on a one-month solo-founder timeline, to consume a week and
produce nothing demonstrable.

Two things changed since that decision, both discovered rather than
assumed:

1. **The bypass port was never built.** The only data-reaching port
   anywhere in this codebase is `SemanticLayerPort`
   (`libs/domain/agent-execution/src/zentra_domain_agent_execution/ports.py`),
   and its only implementation is Cube's. `SqlAnalystAgent` and
   `EvaluatorAgent` already only ever talk to Cube. Reversing ADR-0014 was
   therefore not a migration off a working path — there was no working path
   to migrate off.
2. **Cube's own documentation shows the stated blockers were effort, not a
   ceiling.** Dynamic per-tenant schema generation
   (`asyncModule`/`COMPILE_CONTEXT`) and multiple data sources in one
   deployment (`driverFactory` keyed on `dataSource`) are free, native Cube
   Core features, not gated behind Cube Cloud. ADR-0014 itself said as
   much: "the Join Graph is a clean input to a Cube model generator if one
   is ever built."

Separately, Cube's own official MCP server — considered as a way for
in-process agents to construct Cube queries — was ruled out. It is gated
behind Cube Cloud Premium/Enterprise, which conflicts with self-hosting
Cube for zero licensing cost. It also solves a problem this codebase does
not have: MCP bridges heterogeneous external AI clients to a tool surface,
but `SqlAnalystAgent`/`EvaluatorAgent` are first-class in-process Python
callers that already reach Cube through `SemanticLayerPort`. No MCP
transport is part of this system.

## Decision

Cube is the tenant-scoped analytical gateway for both the demo warehouse
and live Data Connections. It remains what it always was: an orchestrator,
never a database. It compiles a semantic query to SQL and delegates
execution to the real store — Postgres for the demo warehouse, ClickHouse
for a tenant's Data Connection — then caches and returns rows.

### What changed

- **`infra/cube/cube.js`** gained the multi-tenancy configuration it never
  had: `checkAuth` (verifies an HS256 JWT signed with `CUBEJS_API_SECRET`),
  `contextToAppId` (keys Cube's compiled-schema cache on
  `tenantId`/`dataConnectionId`/`relationFingerprint`), and `driverFactory`
  (routes to Postgres or, for `dataSource: 'connector'`, a live ClickHouse
  connection). Confirmed this HS256-JWT-rejection path returns HTTP 500 on
  self-hosted Cube Core, not 403 (403 is Cube Cloud-only) — a limitation
  documented rather than worked around, since fixing it would mean
  re-implementing Cube's own error-response shape.
- **`infra/cube/model/cubes/Connector.js`** dynamically generates one cube
  per confirmed Source Table for a tenant's Data Connection, with joins
  wired only from confirmed Relations. This reimplements ADR-0014's
  governance intent — "only permitted joins are queryable" — as compiled-
  schema absence rather than a bespoke runtime gate: an unconfirmed
  Relation cannot appear in a compiled schema that was never given it.
- **`apps/api/connector_model.py`** reads a Data Connection's confirmed
  Join Graph (via `ConnectorService.join_graph`, unchanged) and computes a
  fingerprint over confirmed-relation membership. The fingerprint, not the
  CatalogVersion id, is what actually invalidates a compiled schema on a
  Relation confirm/reject/revoke — confirming or rejecting a Relation
  mutates its state under the *same* CatalogVersion id, so keying on the
  version alone would silently serve a stale compiled schema.
- **`apps/api/cube_scope.py`** (`ScopedCubeSemanticLayers`) builds one
  `CubeSemanticLayer` per `(tenant_id, data_connection_id)`, cached with a
  TTL and the fingerprint above — replacing a single instance built once
  at boot and shared across every tenant forever, which would have
  silently served tenant A's catalog to tenant B the moment cubes were
  generated per tenant.
- **`apps/api/internal_cube_routes.py`** exposes
  `GET /internal/v1/cube/model/{tenant_id}/{data_connection_id}` for
  Cube's own Node process to call. Guarded by a static shared secret
  (`CUBE_INTERNAL_API_SECRET`, distinct from `CUBEJS_API_SECRET` so the two
  trust boundaries — tenant-facing auth vs. this deployment's own Node
  process calling back into its own API — rotate independently) rather
  than mTLS or a second signed-JWT scheme: this is a single-host
  docker-compose deployment with no certificate-issuance infrastructure,
  and the real trust boundary is "which containers share the compose
  network," where mTLS would add ceremony without adding security.

### The accepted credential-boundary exception

`ConnectorService.resolve_driver_credentials` is a new, narrow, documented
exception to "credentials never leave the application layer." Cube's
`driverFactory` runs in a Node process this application does not control
and needs a live ClickHouse connection; the internal endpoint above is the
one place decrypted credentials transit an HTTP response bound for that
process. Mitigated by: never logging that response body (in either the
FastAPI handler or Cube-side request logging), treating it as call-scoped
rather than cached beyond the `driverFactory` call that needs it, and
naming it here rather than leaving it a silent violation of the
invariant every other method in that service upholds.

### What stayed unchanged

`SemanticQuery`/`SemanticCatalog`/`SemanticLayerPort`/
`UnknownSemanticMemberError`
(`libs/domain/agent-execution/src/zentra_domain_agent_execution/ports.py`),
`CubeClient`/`CubeSemanticLayer`
(`libs/adapters/cube/src/zentra_adapter_cube/{client,semantic}.py`),
`SqlAnalystAgent`/`EvaluatorAgent`, and the Connector's entire harvest →
catalog → relation-confirmation → Join Graph pipeline
(`libs/domain/connector`, `libs/application/connector`, the harvesting
parts of `libs/adapters/clickhouse`). The governance enforcement point,
`SemanticCatalog.reject_ungoverned`, does not change either — what changes
is who populates the catalog it checks against: a human-written model file
for the demo warehouse, a Connector-generated one for live Data
Connections.

### Amendment to ADR-0012

ADR-0012 already said "Cube remains the live analytical gateway" for live
Data Connections and described a "signed internal context" carrying
Tenant, Data Connection, and Semantic Model version, with Cube choosing
the source only from verified context. That is now implemented, as the
`checkAuth`/`contextToAppId` machinery above — this decision closes that
part of ADR-0012 rather than reopening it. ADR-0012's DuckDB-for-uploads
decision is untouched: uploaded CSV/Parquet has no live warehouse behind
it, so Cube cannot serve it regardless of anything decided here. That
remains a third, separate execution path whenever it is built.

## Consequences

Two query paths remain instead of the three that would otherwise exist
(Cube for the demo warehouse, a never-built ClickHouse bypass, DuckDB for
uploads): Cube now serves both the demo warehouse and live Connector data,
and DuckDB — whenever ADR-0012's upload path is built — serves uploaded
files. "Cube runs every query" was never fully achievable regardless of
this decision, because DuckDB-for-uploads was independently already
committed as the primary launch path.

`ConnectorService` has no production wiring yet — its four repository
ports (`DataSourceRepository`, `CatalogRepository`, `RelationRepository`,
`HarvestRunRepository`) have no adapter implementation anywhere in this
repo, discovered while building this. `AppDependencies.connector` is
`None` until that gap is closed, and every function in `connector_model.py`
raises `ConnectorNotConfiguredError` rather than an `AttributeError` while
it is. Closing that gap is a separate, larger undertaking than integrating
Cube — building Postgres persistence for four aggregates — and is not
part of this decision.

A dynamically generated Connector cube emits only a `count` measure and a
per-numeric-field `sum` — a minimal, safe default rather than a governed
metric definition. An agent working over live Connector data still
composes measures itself, exactly as ADR-0014 already conceded it would
have to; this decision changes how that data reaches the agent, not
whether its metrics are pre-defined.

Rejected: Cube's official MCP server, on cost (Cube Cloud only) and fit
(no external AI client to bridge to). Recorded here so it is not reopened
without a new reason to.

## Verification

`libs/adapters/cube/tests/` (auth round-trip against a live Cube instance,
gated by `TEST_CUBE_URL`); `apps/api/tests/test_connector_model.py` (an
unconfirmed Relation never reaches the compiled model; confirming/
rejecting one changes the relation fingerprint); `apps/api/tests/test_cube_scope.py`
(two Data Connections never share a `CubeSemanticLayer` instance; a
fingerprint change invalidates the cache within the TTL window; the demo
warehouse path never triggers a Connector lookup);
`apps/api/tests/test_internal_cube_routes.py` (missing/wrong internal
secret, unconfigured `ConnectorService`, and the success path).

Parent: [[Decisions MOC]]
