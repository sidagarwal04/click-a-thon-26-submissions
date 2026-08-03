---
id: reference-infrastructure-topology
title: Infrastructure Topology
type: reference
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
priority: high
tags: [operations, infrastructure, docker, terraform]
related: ["[[Operations MOC]]", "[[Deployment Topology]]", "[[Managed Service Readiness]]"]
repo_path: infra
code_refs: [docker-compose.yml, infra/terraform/main.tf, apps/api/Dockerfile]
---

# Infrastructure Topology

## Local services

| Service | Port | Role |
| --- | ---: | --- |
| control Postgres | 5432 | Product state and outbox |
| warehouse Postgres | 5433 | Synthetic commerce facts |
| ClickHouse | 8123/9000 | Audit HTTP/native endpoints |
| Cube | 4000 | Governed semantic API |
| API profile | 8000 | Optional containerized FastAPI |
| Vite host process | 4200 | Frontend |

Persistent named volumes retain local state. Initialization scripts create
runtime roles, warehouse fixtures, audit table/grants, and Cube model mounting.

## Managed services

Terraform creates `zentraos-{environment}` in Neon and
`zentraos-audit-{environment}` in ClickHouse Cloud. Defaults select Neon
`aws-us-east-2` and ClickHouse `us-east-1`. ClickHouse IP access must be a
specific API egress CIDR.

Terraform output includes sensitive Neon owner URI; operators store it in a
secret manager. Applies are explicit operator actions.

Parent: [[Operations MOC]]
