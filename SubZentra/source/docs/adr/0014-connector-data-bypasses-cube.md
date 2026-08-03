---
id: adr-0014
title: Connector-sourced data bypasses Cube
type: adr
status: deprecated
owner: unassigned
source: repository
created: 2026-08-01
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: unknown
priority: high
tags: [adr, connector, semantic-model, cube]
related: ["[[Semantic Modeling]]", "[[Cube Semantic Model]]", "[[Connector Domain]]", "[[adr/0016-cube-is-the-single-tenant-scoped-analytical-gateway]]"]
repo_path: libs/application/connector
code_refs:
  - libs/application/connector/src/zentra_application_connector/service.py
  - infra/cube/model/cubes/Commerce.js
---

# Connector-sourced data bypasses Cube

## Status

Superseded by [[adr/0016-cube-is-the-single-tenant-scoped-analytical-gateway]].
The port this decision describes — analytical agents reaching ClickHouse
directly through a Join-Graph-gated capability — was never built; the only
data-reaching port ever implemented was Cube's. The reasoning below is kept
for the record; the Consequences section's own prediction is what proved
out.

## Context

Phase 1A's semantic layer is Cube over a hand-written model file against a
synthetic Postgres warehouse, exposing eight governed commerce metrics. The
Connector produces something structurally different: tables and fields
*discovered* per Tenant, against ClickHouse, with joins that are inferred rather
than declared and that change as a Tenant confirms or rejects them.

Those two things have to meet somewhere, and there were two places they could.

Routing connector data through Cube would give one semantic layer and one story.
It would also require generating Cube model files per Tenant, writing them to
disk where the Cube process can read them, and triggering a schema reload on
every confirmation — plus multi-datasource configuration, since the existing
Cube instance is pointed at Postgres and connector sources are ClickHouse. Each
of those is tractable alone; together they are the part of the design most
likely to consume a week and produce nothing demonstrable.

The alternative is to let the Connector serve its own Join Graph and have
analytical agents query ClickHouse through it directly.

## Decision

Connector-sourced data does not pass through Cube.

The Connector exposes confirmed Relations as a Join Graph, and the analytical
agents reach connector data through a port that refuses to emit a join the Join
Graph does not contain. Cube is untouched and continues to serve the existing
`eu_refund_spike` and `na_channel_growth` scenarios over the synthetic warehouse.

There are now two paths to governed data, and they are governed differently:
Cube's metrics are governed by a definition a human wrote, and the Join Graph is
governed by a confirmation a human gave.

## Consequences

A future reader will reasonably ask why this system has two semantic paths
instead of one, which is why this decision is written down. The honest answer is
that they solve different problems: Cube governs what a measure *means*, and the
Join Graph governs which joins are *permitted*. Merging them is possible later
and is not blocked by anything here — the Join Graph is a clean input to a Cube
model generator if one is ever built.

The costs are real. A Tenant's connector data has no governed metrics, only
governed joins, so an agent working over it composes measures itself rather than
selecting from a list. Cube's caching, pre-aggregation, and access control do not
apply to connector queries. And query construction for connector data is code
this codebase now owns rather than delegates.

The benefit is that the Connector was demonstrable end to end within the
timeline, and that a confirmation takes effect immediately rather than after a
file write and a schema reload.

Parent: [[Decisions MOC]]
