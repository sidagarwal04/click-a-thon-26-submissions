---
id: workflow-ci-verification
title: CI Verification Workflow
type: workflow
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
priority: high
tags: [workflow, ci, nx]
related: ["[[Workflows MOC]]", "[[Test Strategy]]", "[[Dependency Boundaries]]"]
repo_path: .github/workflows/ci.yml
code_refs: [.github/workflows/ci.yml, nx.json]
---

# CI Verification Workflow

GitHub Actions runs for main pushes and pull requests:

1. Check out full history and install Node 24, Python 3.13, uv, and Terraform.
2. Install npm/uv dependencies and Playwright browsers.
3. Start Postgres, warehouse, ClickHouse, and Cube.
4. Apply Alembic migrations to local control-plane Postgres.
5. Prove the known-bad Python architecture fixture is rejected.
6. Validate the Obsidian documentation contract through `docs:check`.
7. Format, initialize without backend, validate, and non-destructively plan
   Terraform with placeholders.
8. Run Nx lint, test, build, typecheck, and e2e targets with integration-service
   environment.
9. Request Nx self-healing diagnostics and print service logs on failure.

CI does not apply Terraform or deploy the product.

Parent: [[Workflows MOC]]
