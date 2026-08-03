---
id: arch-tenancy-security
title: Tenancy Security
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
tags: [security, tenancy, rls]
related: ["[[Architecture MOC]]", "[[Identity and Tenancy]]", "[[Authenticated Tenant Resolution]]"]
repo_path: libs/adapters/postgres
code_refs:
  - apps/api/src/zentra_api/request_context.py
  - libs/adapters/postgres/src/zentra_adapter_postgres/database.py
  - libs/adapters/postgres/migrations/versions/0002_phase1a_investigation.py
---

# Tenancy Security

Each authenticated request verifies a Clerk bearer token, resolves the provider
organization to an internal Tenant UUID, resolves the User and Membership, and
creates an application actor. Callers never supply a trusted tenant identifier.

Tenant-owned Postgres records carry explicit `tenant_id`. Request work runs in a
transaction with `SET LOCAL app.tenant_id`; RLS policies fail closed without
that context. Cross-tenant Investigation and Human Approval identifiers appear
as `404`, not authorization disclosures.

ClickHouse repositories require an internal tenant ID for replay reads. The
audit runtime principal can insert/select but cannot update or delete.

Provider IDs are bindings, not domain primary keys. A User can have Memberships
in multiple Tenants. The frontend's unaffiliated state is not a database role.

Decisions: [[adr/0003-provider-neutral-multi-tenant-identity]] and
[[adr/0004-four-membership-roles]].

Parent: [[Architecture MOC]]
