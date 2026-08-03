---
id: arch-hexagonal-modular-monolith
title: Hexagonal Modular Monolith
type: architecture
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
priority: critical
tags: [architecture, hexagonal, modular-monolith]
related: ["[[Architecture MOC]]", "[[Dependency Boundaries]]", "[[adr/0001-hexagonal-modular-monolith]]"]
repo_path: .
code_refs: [.importlinter, nx.json, libs/domain, libs/application, libs/adapters, apps/api]
---

# Hexagonal Modular Monolith

The backend remains one deployable FastAPI service while its domain,
application, adapters, and composition root are separate Nx projects.

```text
domain ← application ← adapters ← FastAPI composition root
```

The Investigation domain contains lifecycle rules and framework-independent
types. The application package defines use cases and ports. Postgres, Cube,
ClickHouse, and telemetry implement external concerns. `apps/api` wires them
together and owns HTTP/lifespan behavior.

The direction prevents persistence, web, semantic, or telemetry frameworks from
becoming domain concepts. Adapters remain independent from sibling adapters.

The React frontend and reusable TypeScript foundation libraries share the Nx
workspace but do not collapse the backend hexagonal boundaries.

Decision: [[adr/0001-hexagonal-modular-monolith]]. Enforcement:
[[Dependency Boundaries]].

Parent: [[Architecture MOC]]
