---
id: adr-0001
title: Enforce a hexagonal modular monolith in both workspace languages
type: adr
status: active
owner: unassigned
source: decision
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
priority: critical
tags: [adr, architecture, boundaries]
related: ["[[Decisions MOC]]", "[[Hexagonal Modular Monolith]]", "[[Dependency Boundaries]]"]
repo_path: docs/adr/0001-hexagonal-modular-monolith.md
code_refs: [.importlinter, eslint.config.mjs, nx.json]
---

# Enforce a hexagonal modular monolith in both workspace languages

ZentraOS will remain one Nx workspace and one deployable backend through the early product stages, while domain, application, adapters, and composition roots remain separate projects. TypeScript boundaries are enforced by Nx ESLint constraints and Python boundaries by Import Linter because neither code review nor one language's tooling can protect both dependency graphs.
