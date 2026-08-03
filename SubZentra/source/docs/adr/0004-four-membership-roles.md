---
id: adr-0004
title: Persist four tenant membership roles
type: adr
status: active
owner: unassigned
source: decision
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
priority: high
tags: [adr, authorization, membership]
related: ["[[Decisions MOC]]", "[[Identity and Tenancy]]", "[[Investigation API]]"]
repo_path: docs/adr/0004-four-membership-roles.md
code_refs:
  - libs/adapters/postgres/src/zentra_adapter_postgres/schema.py
  - libs/application/investigation/src/zentra_application_investigation/service.py
---

# Persist four tenant membership roles

Membership uses owner, admin, member, and viewer as the canonical role vocabulary. Guest represents an unaffiliated or denied identity rather than a persisted Membership, preventing frontend and backend authorization from assigning different meanings to the same Tenant relationship.
