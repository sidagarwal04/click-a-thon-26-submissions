---
id: arch-deployment-topology
title: Deployment Topology
type: architecture
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-08-01
reviewed: 2026-08-01
confidence: mixed
implementation: current
priority: high
tags: [deployment, infrastructure, architecture]
related: ["[[Architecture MOC]]", "[[Infrastructure Topology]]", "[[Managed Service Readiness]]", "[[Phase 3 Data Execution]]"]
repo_path: infra
code_refs: [docker-compose.yml, apps/api/Dockerfile, infra/terraform/main.tf]
---

# Deployment Topology

## Local

Docker Compose starts control-plane Postgres, a separate warehouse Postgres,
ClickHouse, and Cube. The API may run on the host or through the optional
Compose `app` profile. The frontend runs through the Nx/Vite development server.

## Managed foundation

Terraform declares a Neon project in AWS US East and a ClickHouse Cloud service
in AWS US East. Managed credentials, state, and plans stay outside the
repository. Owner/migration and restricted runtime identities have different
privileges.

## Unknown production layer

No production application hosting resource, delivery pipeline, domain/routing
configuration, secret-manager integration, rollback strategy, or release
promotion workflow exists in the repository. This is an explicit unknown, not
an implied deployment design.

## Accepted Phase 3 target

Phase 3 selects only its new data plane: private Cloudflare R2 objects, a scale-
to-zero Google Cloud Run DuckDB worker, Google Secret Manager for connection
credentials, and verified shared-Cube source routing. These are planned, not
deployed. API, frontend, shared Cube, control-plane, and background-process
hosting remain operability unknowns. See [[Phase 3 Data Execution]].

Operational details: [[Infrastructure Topology]] and
[[Complete Cloud Operational Sign-off]].

Parent: [[Architecture MOC]]
