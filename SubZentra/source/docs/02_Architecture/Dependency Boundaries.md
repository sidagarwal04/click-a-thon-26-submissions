---
id: arch-dependency-boundaries
title: Dependency Boundaries
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
tags: [architecture, boundaries, nx]
related: ["[[Architecture MOC]]", "[[Hexagonal Modular Monolith]]", "[[CI Verification Workflow]]"]
repo_path: .importlinter
code_refs: [.importlinter, eslint.config.mjs, tools/architecture/verify_known_bad_boundary.py]
---

# Dependency Boundaries

## Python

Import Linter forbids framework packages in both domain packages and the
Investigation application. It also enforces independence among Postgres,
ClickHouse, Cube, and telemetry adapters. Every Python project lint target runs
Ruff and Import Linter.

A controlled known-bad fixture imports FastAPI into a domain surface and must
be rejected by `tools/architecture/verify_known_bad_boundary.py`.

## TypeScript

Nx tags describe layer, platform, scope, foundation concern, visibility, and
publication. ESLint's module-boundary rule governs JavaScript/TypeScript imports.
The Nx project graph remains the authoritative resolved view.

## Invariant

The domain may not import FastAPI, SQLAlchemy, ClickHouse, Cube/http clients,
model SDKs, telemetry frameworks, or sandbox runtimes. Application code depends
on ports, not adapter implementations.

Parent: [[Architecture MOC]]
