---
id: reference-nx-project-catalog
title: Nx Project Catalog
type: reference
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
priority: normal
tags: [reference, nx, projects]
related: ["[[References MOC]]", "[[Repository Overview]]", "[[TypeScript Foundation Library Catalog]]"]
repo_path: nx.json
code_refs: [nx.json, package.json]
---

# Nx Project Catalog

The verified pre-vault graph contained 31 software/workspace projects. Adding
the governed `docs` project makes documentation the thirty-second Nx project.

## ZentraOS product

| Project | Root | Layer |
| --- | --- | --- |
| `zentra-os` | `apps/zentra-os` | React app |
| `zentra-os-e2e` | `apps/zentra-os-e2e` | e2e |
| `api` | `apps/api` | Python service |
| `investigation` | `libs/domain/investigation` | domain |
| `agent-execution` | `libs/domain/agent-execution` | domain |
| `investigation-application` | `libs/application/investigation` | application |
| `postgres` | `libs/adapters/postgres` | adapter |
| `clickhouse` | `libs/adapters/clickhouse` | adapter |
| `cube` | `libs/adapters/cube` | adapter |
| `telemetry` | `libs/adapters/telemetry` | adapter |

## Shared frontend foundation

`foundation-adapters`, `foundation-auth`, `foundation-authz`,
`foundation-bridge`, `foundation-data-layer`, `foundation-data-model`,
`foundation-database`, `foundation-design-system`, `foundation-hooks`,
`foundation-http`, `foundation-icons`, `foundation-metrics`,
`foundation-mocks`, `foundation-query-engine`, `foundation-sync-engine`,
`foundation-trackers`, `foundation-utils`, and `foundation-shared-events`.

## Tooling and workspace

`@open-zentra/design-system-plugin`, `@open-zentra/data-layer-plugin`,
`@open-zentra/source`, and `docs`.

Always query `npm exec -- nx show projects --json` and
`npm exec -- nx show project <name> --json`; this catalog is navigation, not a
replacement for the resolved graph.

Parent: [[References MOC]]
