---
id: domain-identity-tenancy
title: Identity and Tenancy
type: domain
status: active
owner: unassigned
source: context-map
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
priority: critical
tags: [domain, identity, tenancy]
related: ["[[Domains MOC]]", "[[Tenancy Security]]", "[[Authenticated Tenant Resolution]]"]
repo_path: libs/domain/CONTEXT.md
code_refs:
  - libs/domain/CONTEXT.md
  - apps/api/src/zentra_api/request_context.py
  - libs/adapters/postgres/src/zentra_adapter_postgres/schema.py
---

# Identity and Tenancy

A Tenant is the isolated customer organization. A User is a global human
identity. A Membership relates one User to one Tenant with exactly one role:
owner, admin, member, or viewer.

Clerk is the current provider, but provider subject and organization IDs remain
bindings. Internal UUIDs own all product relationships. One User may hold
Memberships in multiple Tenants.

The API establishes Tenant context from a verified token and active provider
organization. Caller-supplied tenant identifiers are never authoritative.

Avoid “account,” “Clerk organization,” “tenant user,” and “guest membership”
when naming domain facts. Canonical definitions:
[ZentraOS domain context](../../libs/domain/CONTEXT.md).

Parent: [[Domains MOC]]
