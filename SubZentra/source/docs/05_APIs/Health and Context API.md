---
id: api-health-context
title: Health and Context API
type: api
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
priority: high
tags: [api, health, identity]
related: ["[[APIs MOC]]", "[[FastAPI Service]]", "[[Authenticated Tenant Resolution]]"]
repo_path: apps/api/src/zentra_api/routes.py
code_refs:
  - apps/api/src/zentra_api/routes.py
  - apps/api/src/zentra_api/request_context.py
  - apps/api/tests/test_api.py
---

# Health and Context API

| Method | Path | Purpose | Success | Authentication |
| --- | --- | --- | --- | --- |
| GET | `/health/live` | Process liveness only | `200` | none |
| GET | `/health/ready` | Postgres, ClickHouse, Cube readiness | `200` or `503` | none |
| GET | `/v1/context` | Internal User/Tenant/Membership context | `200` | Clerk bearer token |

`/health/live` never contacts dependencies. `/health/ready` returns sanitized
per-dependency `ready`/`unavailable` status and boolean configuration presence;
it does not expose credentials or connection strings.

`/v1/context` verifies identity and resolves provider bindings to internal UUIDs,
tenant name, email, and one role. Missing/invalid identity returns `401`;
unbound provider identity or organization is denied without trusting request
tenant data.

Authorization and correlation are implemented by a reusable request dependency.
See [[Authenticated Tenant Resolution]].

Parent: [[APIs MOC]]
