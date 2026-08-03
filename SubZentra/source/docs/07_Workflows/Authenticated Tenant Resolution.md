---
id: workflow-authenticated-tenant-resolution
title: Authenticated Tenant Resolution
type: workflow
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
priority: critical
tags: [workflow, auth, tenancy]
related: ["[[Workflows MOC]]", "[[Identity and Tenancy]]", "[[Tenancy Security]]"]
repo_path: apps/api/src/zentra_api/request_context.py
code_refs:
  - apps/api/src/zentra_api/auth.py
  - apps/api/src/zentra_api/request_context.py
  - libs/adapters/postgres/src/zentra_adapter_postgres/identity.py
---

# Authenticated Tenant Resolution

1. Extract a bearer token; absence or malformed input is `401`.
2. Verify the Clerk JWT issuer/audience and required identity claims.
3. Require an active provider organization.
4. Resolve provider subject to internal User and provider organization to
   internal Tenant.
5. Resolve active Tenant Membership and role.
6. Correlate internal Tenant UUID with the current trace.
7. Produce an application `AuthenticatedActor` carrying internal IDs and
   trace/span IDs.
8. Open tenant work in a Postgres transaction and set local RLS context.

There is no tenant fallback and no request field/header that overrides the
resolved Tenant. Cross-tenant reads fail through both repository filtering and
RLS.

Parent: [[Workflows MOC]]
