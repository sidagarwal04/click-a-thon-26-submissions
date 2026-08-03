---
id: api-workspace-organization
title: Workspace Organization API
type: api
status: active
owner: unassigned
source: repository
created: 2026-08-01
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: current
priority: high
tags: [api, groups, projects, tenancy]
related: ["[[APIs MOC]]", "[[Investigation API]]", "[[Postgres Control Plane]]"]
depends_on: ["[[Authenticated Tenant Resolution]]"]
repo_path: apps/api/src/zentra_api/workspace_routes.py
code_refs:
  - apps/api/src/zentra_api/workspace_routes.py
  - apps/api/src/zentra_api/workspace_schemas.py
  - apps/api/tests/test_workspace_api.py
---

# Workspace Organization API

Groups and Projects organize Investigation work without introducing nested
permissions. Every identifier is resolved under the authenticated Tenant.

| Method | Path | Purpose | Authorization |
| --- | --- | --- | --- |
| POST/GET | `/v1/groups` | Create or list Groups | create owner/admin; read all roles |
| GET/PATCH | `/v1/groups/{group_id}` | Read or rename a Group | rename owner/admin; read all roles |
| POST | `/v1/groups/{group_id}/archive` | Archive a Group | owner/admin |
| POST | `/v1/groups/{group_id}/restore` | Restore a Group | owner/admin |
| POST/GET | `/v1/groups/{group_id}/projects` | Create or list Projects | create owner/admin; read all roles |
| GET/PATCH | `/v1/projects/{project_id}` | Read or rename a Project | rename owner/admin; read all roles |
| POST | `/v1/projects/{project_id}/archive` | Archive a Project | owner/admin |
| POST | `/v1/projects/{project_id}/restore` | Restore a Project | owner/admin |

Lists use bounded keyset queries and return `next_cursor`. Groups are ordered by
their metadata activity. Projects are ordered by `latest_activity_at`, which can
be advanced independently when later Thread or Investigation work occurs. The
default page size is 50 and the maximum is 100. Archived resources are omitted
unless `include_archived=true`, but remain directly readable.

Names are NFKC-normalized, whitespace-collapsed, case-folded for uniqueness,
and limited to 100 display characters. Group uniqueness is Tenant-scoped;
Project uniqueness is Group-scoped.

Errors use `detail.code`: `permission_denied`, `workspace_not_found`,
`workspace_conflict`, or `invalid_workspace`. Nonexistent, cross-Tenant, and
otherwise inaccessible IDs all use the same not-found behavior.

Parent: [[APIs MOC]]
