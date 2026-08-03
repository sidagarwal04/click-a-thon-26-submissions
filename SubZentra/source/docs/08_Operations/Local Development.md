---
id: reference-local-development
title: Local Development
type: reference
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
priority: critical
tags: [operations, local, development]
related: ["[[Operations MOC]]", "[[First Day]]", "[[Recover Local Foundation]]"]
repo_path: README.md
code_refs: [README.md, docker-compose.yml, apps/api/.env.example, apps/zentra-os/.env.example]
---

# Local Development

## Prerequisites

Node 24/npm, Python 3.13, uv, Docker Compose, and Terraform 1.9+.

## Bootstrap

```bash
npm ci
uv sync --frozen
docker compose up -d --wait control-postgres warehouse-postgres clickhouse cube
DATABASE_OWNER_URL=postgresql+psycopg://zentra_owner:zentra_owner@localhost:5432/zentra_control \
  npm exec -- nx run postgres:migrate
```

Copy each application `.env.example` to an untracked `.env` and replace external
provider placeholders. Local database credentials in Compose are fixtures only.

## Run

```bash
npm exec -- nx serve api
npm exec -- nx serve zentra-os
```

Frontend: `http://localhost:4200`; API: `http://localhost:8000`; Cube:
`http://localhost:4000`; ClickHouse HTTP: `http://localhost:8123`.

Without Clerk configuration, the frontend intentionally renders setup-required
rather than assuming a development identity.

## Verify

```bash
npm exec -- nx run docs:check
uv run python tools/architecture/verify_known_bad_boundary.py
npm exec -- nx run-many -t lint test build typecheck
npm exec -- nx e2e zentra-os-e2e
```

Troubleshooting: [[Recover Local Foundation]] and
[[Diagnose Degraded Readiness]].

Parent: [[Operations MOC]]
