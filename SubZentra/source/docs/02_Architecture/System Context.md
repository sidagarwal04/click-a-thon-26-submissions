---
id: arch-system-context
title: System Context
type: architecture
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
priority: critical
tags: [architecture, system-context]
related: ["[[Architecture MOC]]", "[[Repository Overview]]", "[[Deployment Topology]]"]
repo_path: .
code_refs: [docker-compose.yml, apps/api/src/zentra_api/dependencies.py, apps/zentra-os/src/app/app.tsx]
---

# System Context

```mermaid
flowchart LR
  U["User"] --> W["zentra-os"]
  W --> C["Clerk"]
  W --> A["FastAPI service"]
  A --> P["Postgres control plane"]
  A --> Q["Cube"]
  Q --> WH["Synthetic warehouse"]
  A --> O["ClickHouse audit ledger"]
  A --> T["OTLP / Langfuse"]
  TF["Terraform operator"] --> N["Neon"]
  TF --> CC["ClickHouse Cloud"]
```

The User interacts with the Forensic Observatory. Clerk supplies identity, but
provider identifiers are resolved to internal UUIDs before product behavior.
The FastAPI service composes the application core and adapters.

Postgres owns transactional state and tenant authorization. Cube owns governed
analytical definitions over the warehouse. ClickHouse owns immutable audit
replay. Telemetry may export traces to a configured OTLP endpoint.

Local Docker services reproduce the database/semantic dependencies. Terraform
defines managed Neon and ClickHouse Cloud resources, but no application
deployment pipeline is present.

See [[Hexagonal Modular Monolith]], [[Tenancy Security]], and
[[Audit and Observability Architecture]].

Parent: [[Architecture MOC]]
