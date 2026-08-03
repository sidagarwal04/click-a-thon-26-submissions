---
id: reference-documentation-backlog
title: Documentation Backlog
type: reference
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-30
reviewed: 2026-07-30
confidence: mixed
implementation: current
priority: normal
tags: [documentation, backlog, reference]
related: ["[[References MOC]]", "[[Documentation System Specification]]", "[[Known Unknowns]]"]
repo_path: docs
---

# Documentation Backlog

These phases describe documentation-system maturity. They are unrelated to the
product roadmap in [[Phase 2 - Insight Auditor and Replay]].

## Phase 1 — critical onboarding and architecture

- [x] Root MOCs, repository overview, product boundary, system context.
- [x] Investigation trust loop, local development, first-day guide.

## Phase 2 — domain and component depth

- [x] Current domain, component, API, data, and workflow notes.
- [ ] Split individual foundation-package notes only when active product use or
  ownership demands more depth.
- [ ] Reconcile and complete the existing
  [foundation architecture review plan](../foundation-architecture-review-plan.md)
  without treating its planned findings as current behavior.

## Phase 3 — operations and runbooks

- [x] Configuration, tests, infrastructure, readiness, and five initial
  runbooks.
- [ ] Add deployment/rollback and incident response after a production runtime
  is selected.

## Phase 4 — decision history and polish

- [x] ADR frontmatter/index, source catalog, templates, quality rules.
- [ ] Add verified owners after CODEOWNERS or ownership registry exists.

## Phase 5 — continuous maintenance

- [x] Automated metadata/link/source validation in CI.
- [ ] Add release records when a release strategy is accepted.
- [ ] Review critical notes monthly and all active notes quarterly.
- [ ] Promote durable findings from GitHub issue investigations.

Parent: [[References MOC]]
