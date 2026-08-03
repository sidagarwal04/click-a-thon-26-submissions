---
id: workflow-documentation-maintenance
title: Documentation Maintenance Workflow
type: workflow
status: active
owner: unassigned
source: governance
created: 2026-07-29
updated: 2026-07-30
reviewed: 2026-07-30
confidence: verified
implementation: current
priority: high
tags: [documentation, maintenance, workflow]
related: ["[[References MOC]]", "[[Documentation Quality Bar]]", "[[First Change]]"]
depends_on: ["[[Documentation System Specification]]"]
repo_path: docs
code_refs: [.github/workflows/ci.yml, tools/documentation/validate_vault.py]
---

# Documentation Maintenance Workflow

## Same-change updates

A PR that changes architecture, domain language, user behavior, API contracts,
schema/RLS, configuration, operations, ownership, or a runbook procedure updates
the canonical note in the same change. Reviewers ask for “documentation impact:
none” reasoning when no update is made.

## Lifecycle

- `draft`: incomplete or awaiting evidence.
- `active`: correct and navigable.
- `deprecated`: retained with replacement link.
- `archived`: moved to `99_Archive`; not an entry point.

Critical notes are reviewed monthly, high-priority notes quarterly, and normal
notes twice yearly. Any note is reviewed immediately when its source changes.

## Decisions and operations

Accepted ADR bodies are not rewritten; superseding ADRs link both directions.
Runbooks are reviewed after use and after an incident. Incident notes preserve
facts/timeline; durable learning updates tests, monitoring, runbooks, or ADRs.
Release notes describe user/operator-visible behavior, not commit lists.

## Research and work tracking

GitHub Issues are the issue and PRD workspace. Completed research becomes a
vault note only when it contains durable, reusable knowledge. Repository
conventions live in `docs/agents/issue-tracker.md`.

## Enforcement

`npm exec -- nx run docs:check` runs locally and in CI. Fix content and links;
do not weaken validation to hide stale knowledge.

Parent: [[References MOC]]
