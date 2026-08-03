---
id: onboarding-first-day
title: First Day
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
tags: [onboarding, local-development]
related: ["[[Onboarding MOC]]", "[[Repository Overview]]", "[[Local Development]]"]
depends_on: ["[[System Context]]", "[[Investigation Trust Loop]]"]
repo_path: README.md
code_refs: [README.md, AGENTS.md, CONTEXT-MAP.md]
---

# First Day

## Outcome

Understand the product boundary, run the local foundation, and trace one
Investigation from HTTP to domain, persistence, semantic query, audit, and UI.

## Reading path

1. [[Repository Overview]] and [[Product Boundaries]].
2. [[System Context]] and [[Hexagonal Modular Monolith]].
3. Root [context map](../../CONTEXT-MAP.md), then
   [[Investigation Domain]] and [[Identity and Tenancy]].
4. [[Investigation Trust Loop]].
5. [[Tenancy Security]] and [[Audit and Observability Architecture]].

## Environment

Follow [[Local Development]]. Confirm `docs:check`, the architecture fixture,
API/frontend targets, and readiness before changing code.

## Source tour

Start at `apps/zentra-os`, cross the HTTP boundary at `apps/api`, follow
`InvestigationService`, then inspect domain, Postgres UoW, Cube scenario, and
audit coordinator. Use [[Repository Source Map]] for exact paths.

## Completion

Explain why provider organization ID is not Tenant ID, why deterministic work
has validation rather than confidence, and how an outbox crash avoids lost audit
history.

Parent: [[Onboarding MOC]]
