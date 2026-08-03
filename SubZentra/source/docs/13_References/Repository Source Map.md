---
id: reference-repository-source-map
title: Repository Source Map
type: reference
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-30
reviewed: 2026-07-30
confidence: verified
implementation: current
priority: high
tags: [reference, source-map, repository]
related: ["[[References MOC]]", "[[Repository Overview]]", "[[Nx Project Catalog]]"]
repo_path: .
code_refs: [package.json, nx.json, CONTEXT-MAP.md]
---

# Repository Source Map

| Knowledge | Authoritative source |
| --- | --- |
| Product setup/status | `README.md` |
| Workspace projects/tasks | `nx.json`, resolved `nx show project` output |
| Canonical domain language | `CONTEXT-MAP.md`, `libs/domain/**/CONTEXT.md` |
| Accepted architecture | `docs/adr/` |
| Investigation behavior | domain model and application service |
| HTTP contracts | `apps/api/src/zentra_api/routes.py` |
| Authentication/tenant context | API auth/request-context modules and Postgres identity adapter |
| Transactional schema/RLS | Postgres Alembic migrations |
| Audit schema/policy | ClickHouse init SQL and adapter model validation |
| Semantic definitions | Cube `Commerce.js` |
| Deterministic facts | warehouse seed and Cube fixture |
| Frontend behavior | `apps/zentra-os/src/app` |
| Local topology | `docker-compose.yml` |
| Managed infrastructure | `infra/terraform` |
| CI behavior | `.github/workflows/ci.yml` |
| Work planning | GitHub Issues conventions in `docs/agents/issue-tracker.md` |

When a note disagrees with an executable source, treat the source as current
behavior, investigate intent through ADRs/context, and correct the note or code
in the appropriate change.

Parent: [[References MOC]]
