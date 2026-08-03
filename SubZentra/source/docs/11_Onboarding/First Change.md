---
id: onboarding-first-change
title: First Change
type: onboarding
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
priority: high
tags: [onboarding, contribution, nx]
related: ["[[Onboarding MOC]]", "[[Documentation Maintenance Workflow]]", "[[Test Strategy]]"]
depends_on: ["[[First Day]]", "[[Dependency Boundaries]]"]
repo_path: AGENTS.md
code_refs: [AGENTS.md, nx.json, .github/workflows/ci.yml]
---

# First Change

## Before editing

1. Read `AGENTS.md`, relevant `CONTEXT.md`, and applicable ADRs.
2. Use `npm exec -- nx show project <name> --json` for resolved targets/tags.
3. Inspect the dependency graph and existing tests.
4. State assumptions and define observable success.

## Change discipline

Keep edits inside the requested behavior. Preserve domain terms and dependency
direction. Use repository ports rather than importing adapters into application
code. Never accept caller Tenant IDs or add raw customer data to audit metadata.

## Verification

Run affected targets through Nx. For a schema change, include migration-from-
previous-state and RLS tests. For API behavior, include role/privacy errors. For
frontend state, include accessibility and reduced motion. Run `docs:check` when
knowledge notes change.

## Documentation impact

Update the same PR when behavior, architecture, API, schema, operations, or
ownership changes. Prefer updating an existing canonical note over creating a
near-duplicate.

## Review handoff

Report what changed, evidence run, remaining credential-dependent checks, and
unrelated pre-existing failures separately.

Parent: [[Onboarding MOC]]
