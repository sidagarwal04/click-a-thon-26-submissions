---
id: adr-0003
title: Keep identity-provider subjects outside domain identifiers
type: adr
status: active
owner: unassigned
source: decision
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
priority: critical
tags: [adr, identity, tenancy]
related: ["[[Decisions MOC]]", "[[Identity and Tenancy]]", "[[Tenancy Security]]"]
repo_path: docs/adr/0003-provider-neutral-multi-tenant-identity.md
code_refs:
  - libs/adapters/postgres/src/zentra_adapter_postgres/schema.py
  - apps/api/src/zentra_api/request_context.py
---

# Keep identity-provider subjects outside domain identifiers

Users and Tenants have internal UUIDs, while Clerk user and organization IDs live in binding tables resolved at the authenticated API boundary. A User may hold Memberships in multiple Tenants, avoiding provider lock-in and matching the existing active-tenant switching behavior.
