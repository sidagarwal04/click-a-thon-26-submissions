---
id: runbook-recover-local-foundation
title: Recover Local Foundation
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
tags: [runbook, local, docker]
related: ["[[Runbooks MOC]]", "[[Local Development]]", "[[Diagnose Degraded Readiness]]"]
repo_path: docker-compose.yml
code_refs: [docker-compose.yml, README.md]
---

# Recover Local Foundation

## Use when

Use when a local dependency will not start or `/health/ready` reports degraded.
Do not delete volumes as a first response; they contain local state.

## Diagnose

```bash
docker compose ps
docker compose logs --no-color control-postgres warehouse-postgres clickhouse cube
```

Confirm ports 5432, 5433, 8123, and 4000 are not owned by unrelated processes.
Check `.env` against `.env.example` without printing secrets.

## Recover

```bash
docker compose up -d --wait control-postgres warehouse-postgres clickhouse cube
DATABASE_OWNER_URL=postgresql+psycopg://zentra_owner:zentra_owner@localhost:5432/zentra_control \
  npm exec -- nx run postgres:migrate
```

Restart only the failed service if its logs identify a transient start failure.
Volume deletion is destructive and requires explicit user intent.

## Verify

`docker compose ps` is healthy, API `/health/live` returns `200`, and
`/health/ready` reports all three dependencies ready.

Parent: [[Runbooks MOC]]
