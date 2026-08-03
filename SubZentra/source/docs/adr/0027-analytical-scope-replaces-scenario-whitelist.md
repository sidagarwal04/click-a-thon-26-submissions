---
id: adr-0027
title: Analytical Scope replaces the scenario whitelist
type: adr
status: active
owner: unassigned
source: repository
created: 2026-08-02
updated: 2026-08-02
reviewed: 2026-08-02
confidence: verified
implementation: current
priority: high
tags: [adr, investigation, intake, governance]
related:
  - "[[Investigation Domain]]"
  - "[[Chat Surface]]"
  - "[[adr/0016-cube-is-the-single-tenant-scoped-analytical-gateway]]"
  - "[[adr/0026-investigation-engine-owns-orchestration]]"
repo_path: libs/application/investigation
code_refs:
  - libs/application/investigation/src/zentra_application_investigation/thread_routing.py
  - libs/application/investigation/src/zentra_application_investigation/thread_service.py
  - libs/application/investigation/src/zentra_application_investigation/intake_service.py
  - libs/adapters/langgraph/src/zentra_adapter_langgraph/agents/intake.py
  - libs/domain/investigation/src/zentra_domain_investigation/model.py
  - libs/domain/investigation/src/zentra_domain_investigation/analytical_scope.py
  - libs/domain/agent-execution/src/zentra_domain_agent_execution/ports.py
---

# Analytical Scope replaces the scenario whitelist

## Status

Accepted. Amends the Investigation Domain invariant "Deterministic routing
activates a Thread only when exactly one governed scenario matches" and the
Draft-Thread rule that no analytical work is fabricated until a scenario
matches. Does not touch `SemanticCatalog.reject_ungoverned`
(`libs/domain/agent-execution/.../ports.py`), which remains the absolute
floor no Analytical Scope configuration can widen.

## Context

`thread_routing.py` matches a user's message against exactly two
hardcoded scenarios (`eu_refund_spike`, `na_channel_growth`,
`libs/application/investigation/.../dto.py`) via frozenset token-overlap
requirements. Zero matches is `UNSUPPORTED`, more than one is `AMBIGUOUS`,
and this is the entire reason chat cannot answer a question it wasn't
specifically coded for. The coupling runs deeper than the router: the
`scenario_key` a match resolves to is a required field on the `Investigation`
domain aggregate itself (`model.py`, `Investigation.create`), not just
routing metadata, and it propagates through `thread_service.py`,
`pipeline.py`, and the visualization/finding path.

## Decision

Governance moves from "does this message match one of two named scenarios"
to "is this question inside the tenant's configured Analytical Scope" — a
per-tenant allowlist of Cube cubes, with optional member-level overrides,
intersected against `SemanticCatalog` at intake time. An `IntakeAgent`
(`AgentRole.INTAKE`, registered the same way every other role is — a table,
never a code list, per ADR-0002) replaces `route_governed_question` /
`route_draft_messages`: it reads the scope-filtered catalog and either
resolves a normalized question or asks a clarifying question grounded in
what the tenant can actually be asked about. `_apply_routing`
(`thread_service.py`) keeps its two outcomes — clarify, or create an
Investigation — and keeps emitting the same `ROUTER_CLARIFICATION` /
`ROUTING_RESOLVED` Work Feed event kinds, so no frontend or wire-protocol
change is required.

`Investigation.scenario_key` keeps its field name and type but changes what
populates it: Intake's normalized-question identifier rather than a fixed
catalog key. This is a smallest-diff choice — every existing call site that
threads `scenario_key` through (follow-up creation, pipeline result
assembly, visualization) keeps working unmodified; only what supplies the
value changes.

The demo tenant's Analytical Scope defaults to the whole catalog, so local
and demo UX are unaffected by this change; scope narrowing is an explicit
tenant configuration action, not a default that would silently break
today's fixture questions.

## Consequences

Any in-scope question can now open an Investigation — the two fixture
scenarios stop being special-cased and become two of arbitrarily many
questions Intake can resolve. An out-of-scope question is refused or
clarified using the tenant's real configured catalog, and can never
reference a cube or member the tenant hasn't granted — Intake calls the same
`SemanticCatalog`-backed check every other agent is bound by, it does not
invent a parallel governance path. `SCENARIOS`
(`libs/application/investigation/.../dto.py`) and the two hardcoded
requirement tuples in `thread_routing.py` are deleted once Intake replaces
them; nothing else in the domain model changes shape as a result.

## Verification

The existing EU/NA fixture questions still resolve through Intake
(regression, not because a whitelist still exists). A novel in-scope
question creates a real Investigation with no `UNSUPPORTED` from missing
keywords. An out-of-scope question clarifies or refuses using the scoped
catalog and never fabricates a member. `Investigation.create` and its
existing test suite pass with `scenario_key` populated from Intake rather
than a dict lookup.

## Phase 1 status

Implemented with one deliberate gap and one deliberate non-change:

- **`AnalyticalScope` is not yet wired into `IntakeService`.** The domain
  type (`analytical_scope.py`) and its `narrow()` intersection with
  `SemanticCatalog` are built and unit-tested, but `dependencies.py` gives
  every Tenant the same unrestricted (whole-catalog) semantic layer Intake
  reads from — exactly the demo Tenant's intended default, so no fixture
  question or local UX regresses, but per-tenant narrowing has no
  configuration path yet. Wiring a real `AnalyticalScope` lookup per Tenant
  is follow-up work, not part of this cutover.
- **`SCENARIOS` / `dto.py` were not deleted.** They still back a separate,
  non-chat path — `InvestigationService.start()`'s explicit-scenario
  creation, used by `apps/api/routes.py` and `tools/evals/live_run.py` — that
  this change does not touch. Only `thread_routing.py`'s
  `route_governed_question` / `route_draft_messages` and their token-overlap
  helpers were deleted; `thread_routing.py` now holds only
  `deterministic_thread_title`.
