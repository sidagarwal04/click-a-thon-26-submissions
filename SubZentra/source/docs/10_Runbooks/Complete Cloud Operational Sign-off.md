---
id: runbook-cloud-operational-signoff
title: Complete Cloud Operational Sign-off
type: runbook
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: mixed
implementation: unknown
priority: high
tags: [runbook, cloud, signoff]
related: ["[[Runbooks MOC]]", "[[Managed Service Readiness]]", "[[Deployment Topology]]"]
repo_path: infra/terraform
code_refs:
  - infra/terraform/README.md
  - infra/terraform/main.tf
  - apps/api/src/zentra_api/settings.py
---

# Complete Cloud Operational Sign-off

## Use when

Clerk, Neon, ClickHouse Cloud, and Langfuse credentials plus an API runtime with
known egress are available.

## Preconditions

- Credentials are supplied through approved secret storage, never files or
  command output captured in tickets.
- Terraform remote backend, state access, egress CIDR, environment, and rollback
  owner are known.
- Owner/migration and runtime identities are distinct.

## Procedure

1. Run Terraform format, backend-free validation, and reviewed plan.
2. Apply only with explicit operator authorization.
3. Apply Postgres migrations using the Neon owner role.
4. Configure the API with restricted Neon and ClickHouse runtime credentials.
5. Verify `/health/ready` from the deployed API.
6. Create/read the deterministic Investigation through a bound Clerk Tenant.
7. Confirm audit delivery and tenant-filtered replay in ClickHouse Cloud.
8. Prove the runtime ClickHouse principal cannot update or delete rows.
9. Confirm the request trace appears in Langfuse with trace and internal Tenant
   correlation and no forbidden payload data.

## Sign-off evidence

Record environment, UTC time, resource IDs, checks performed, and pass/fail
without credentials, connection strings, customer data, or raw payloads.

Parent: [[Runbooks MOC]]
