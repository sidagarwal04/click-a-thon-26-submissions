---
id: runbook-degraded-readiness
title: Diagnose Degraded Readiness
type: runbook
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
priority: high
tags: [runbook, readiness, api]
related: ["[[Runbooks MOC]]", "[[Health and Context API]]", "[[Recover Local Foundation]]"]
repo_path: apps/api/src/zentra_api/routes.py
code_refs:
  - apps/api/src/zentra_api/routes.py
  - apps/api/src/zentra_api/settings.py
---

# Diagnose Degraded Readiness

## Use when

`GET /health/live` succeeds but `GET /health/ready` returns `503`.

## Diagnose

1. Read the sanitized dependency map to identify Postgres, ClickHouse, or Cube.
2. Confirm configuration presence booleans; never request secret values in
   tickets or chat.
3. For local use, inspect `docker compose ps` and the named service log.
4. Confirm API configuration points to the intended host/network context:
   `localhost` for host execution, Compose service names for the API container.
5. For managed use, verify network policy, TLS mode, runtime identity, and
   endpoint reachability with the platform operator.

## Recover

Restore only the failing dependency or correct its untracked environment.
Do not bypass readiness, broaden ClickHouse CIDR to the world, or substitute
owner credentials for runtime credentials.

## Verify

Readiness returns `200`, dependency status is `ready`, and one safe product read
works under a real Tenant.

Parent: [[Runbooks MOC]]
