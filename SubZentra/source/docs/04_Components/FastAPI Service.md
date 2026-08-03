---
id: component-api
title: FastAPI Service
type: component
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: current
priority: critical
tags: [component, api, python]
aliases: [api, zentra-api]
related: ["[[Components MOC]]", "[[Health and Context API]]", "[[Investigation API]]", "[[Workspace Organization API]]", "[[Investigation Thread API]]"]
depends_on: ["[[Investigation Core]]", "[[Postgres Adapter]]", "[[ClickHouse Adapter]]", "[[Cube Adapter]]", "[[Telemetry Adapter]]"]
repo_path: apps/api
code_refs:
  - apps/api/src/zentra_api/main.py
  - apps/api/src/zentra_api/dependencies.py
  - apps/api/src/zentra_api/routes.py
---

# FastAPI Service

The API is the backend composition root. It owns HTTP routing, request models,
authentication dependencies, CORS, lifecycle startup/shutdown, dependency
health checks, and adapter wiring.

`AppDependencies` constructs Postgres, ClickHouse, Cube, JWT verification,
Investigation service, and audit delivery from Settings. The lifespan starts the
outbox dispatcher and closes external clients.

The service exposes liveness/readiness, internal identity context, Investigation
create/read, Human Approval decisions, and tenant-scoped Group and Project
organization endpoints. It also exposes create-with-first-message, Draft
clarification, snapshot, archive/restore, and Draft-only Thread deletion
contracts. It also exposes Agent discovery, cancellation, immutable retry,
resumable SSE Work Feed, Visualization artifacts, renderer-only retry, and
reauthorized safe actions. Domain and application rules remain outside FastAPI. Organization
and Thread errors use stable codes while inaccessible resource identifiers
remain nondisclosing `404` responses.

Run with `npm exec -- nx serve api`; verify with the `api` lint/test/build
targets.

Failures: [[Diagnose Degraded Readiness]] and
[[Recover Audit Delivery Backlog]].

Parent: [[Components MOC]]
