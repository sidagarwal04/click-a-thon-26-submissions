---
id: reference-managed-service-readiness
title: Managed Service Readiness
type: reference
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: mixed
implementation: unknown
priority: high
tags: [operations, cloud, readiness]
related: ["[[Operations MOC]]", "[[Complete Cloud Operational Sign-off]]", "[[Known Unknowns]]"]
repo_path: infra/terraform
code_refs: [infra/terraform/main.tf, infra/terraform/README.md, apps/api/src/zentra_api/routes.py]
---

# Managed Service Readiness

## Defined

Neon and ClickHouse Cloud resources are expressed in Terraform, settings accept
managed connection details, the API readiness endpoint probes all mandatory
dependencies, and telemetry can export through OTLP.

## Awaiting external evidence

- Neon runtime connectivity from the API.
- ClickHouse Cloud runtime connectivity from the API.
- Managed migration execution with the owner role.
- Runtime ClickHouse inability to mutate/delete audit rows.
- One manual request visible in Langfuse with trace and internal Tenant
  correlation.
- Secret-manager, application hosting, egress, DNS/TLS, deployment, rollback,
  and release-promotion definitions.

Do not mark cloud readiness complete based only on Terraform validation or local
Docker success. Use [[Complete Cloud Operational Sign-off]] once credentials and
hosting context are available.

Parent: [[Operations MOC]]
