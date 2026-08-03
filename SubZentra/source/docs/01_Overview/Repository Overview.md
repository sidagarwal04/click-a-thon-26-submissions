---
id: overview-repository
title: Repository Overview
type: overview
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
priority: critical
tags: [repository, nx, overview]
related: ["[[Overview MOC]]", "[[Nx Project Catalog]]", "[[System Context]]"]
repo_path: .
code_refs: [package.json, nx.json, pyproject.toml, docker-compose.yml]
---

# Repository Overview

This npm and uv workspace combines the ZentraOS product with reusable frontend
foundation packages. Nx owns project discovery, dependency analysis, task
orchestration, and caching across both languages.

## Product surfaces

- `apps/zentra-os`: React 19 and Vite Forensic Observatory.
- `apps/api`: FastAPI composition root and HTTP boundary.
- `libs/domain`: framework-independent Investigation and Agent Execution
  contracts.
- `libs/application/investigation`: deterministic trust-loop orchestration.
- `libs/adapters`: Postgres, ClickHouse, Cube, and telemetry implementations.
- `infra`: local service initialization, analytical seed, semantic model, and
  managed-service Terraform.

## Shared engineering surfaces

`libs/foundation` contains reusable TypeScript packages for authentication,
authorization, data access, browser persistence, synchronization, metrics,
HTTP, design system, and supporting utilities. `tools` contains Nx generators.
See [[TypeScript Foundation Library Catalog]].

## Toolchain

Node 24/npm and Python 3.13/uv are the declared runtimes. Vitest, Pytest,
Playwright, ESLint, Ruff, Import Linter, Alembic, Terraform, Docker Compose, and
GitHub Actions form the verification and infrastructure toolchain.

## Wayfinding

- Product shape: [[Product Boundaries]]
- Runtime relationships: [[System Context]]
- Projects and dependencies: [[Nx Project Catalog]]
- Local execution: [[Local Development]]
- First contribution: [[First Change]]

Source of truth: [package manifest](../../package.json),
[Nx configuration](../../nx.json), and [Python workspace](../../pyproject.toml).

Parent: [[Overview MOC]]
