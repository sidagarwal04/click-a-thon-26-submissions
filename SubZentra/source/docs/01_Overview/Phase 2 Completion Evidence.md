---
id: overview-phase-2-completion-evidence
title: Phase 2 Completion Evidence
type: overview
status: active
owner: unassigned
source: repository
created: 2026-08-01
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: current
priority: high
tags: [overview, phase-2, certification]
related: ["[[Phase 2 - Insight Auditor and Replay]]", "[[Overview MOC]]", "[[Current Implementation Status]]"]
repo_path: docs/01_Overview
---

# Phase 2 Completion Evidence

> **Issue numbers in this document refer to `openzentra/nexus`.** Phase 2 was
> built and tracked there; the code moved to `ch-nexus/ui-monorepo` on
> 2026-08-01 and GitHub resolves `#NN` against whichever repository you are
> reading in. Every `#NN` below — #12, #17, #19, #22, #24, #25, #26 and the
> rest — is a pointer into the old repository, which is retained as the `git`
> remote `openzentra` and remains the historical record.

Certification evidence for #27. Each criterion below names the primary
implementation or validation that satisfies it. No criterion is satisfied by
this document — this document only points at what is.

**Phase 2 is not certified complete.** Twelve of thirteen criteria are
evidenced; the thirteenth is blocked and is described plainly at the end rather
than deferred quietly.

## Evidenced

**1 — Every affected Nx target is green.** Re-verified 2026-08-01 against the
local stack after the move to `ch-nexus/ui-monorepo` and the history squash: `nx run-many -t lint test typecheck build` across 33 projects,
`nx run docs:check`, `nx run evals:check`, `uv run lint-imports` (3 contracts
kept, 0 broken), and `verify_known_bad_boundary.py`.

**2 — Insight is independently registered, executed, attributed and
evaluation-gated.** `agent_registry` holds `insight_v1` at `enabled = true`,
`eval_status = 'passing'`, gated by
`ck_agent_registry_enabled_requires_passing_eval`.

> **Known operational gap.** This state has now drifted back to
> `enabled = false` / `eval_status = 'pending'` twice, on a rebuilt database.
> `nx run evals:promote` is what sets it, and that target does not supply the
> `DATABASE_OWNER_URL` it requires — so it reports the corpus passing and
> silently promotes nothing. Nothing in CI runs it either. A deployment that
> migrates a fresh database therefore starts with the Insight Agent
> **disabled**, which fails closed rather than dangerously, but means the
> pipeline does not run. This needs an issue against the new tracker: either
> the target supplies the variable, or promotion becomes part of migration. The corpus is
`evals/insight/` at 17/17. The Agent is
`libs/adapters/langgraph/src/zentra_adapter_langgraph/agents/insight.py` (#12, #13).

**3 — The Orchestrator no longer synthesizes Findings.** `_synthesize` and the
`synthesize` graph node were removed in #20. Asserted against the descriptor
contract rather than execution rows in
`apps/api/tests/test_phase_2_acceptance.py`, because the contract is where a
regression reappears first. Mutation-tested: restoring `headline` and `summary`
to the Orchestrator fails two tests.

**4 — Every substantive claim is backed by a resolvable citation before
automatic publication.** `DraftFinding.__post_init__` refuses an observed claim
that cites nothing; `PostgresEvidenceCitationRepository.resolve` dereferences
through Tenant authorization (#15, #16).

**5 — Publication enforces convergence, bounded confidence, citation
resolvability and contradiction rules.**
`libs/domain/investigation/src/zentra_domain_investigation/publication.py`, with
a truth-table suite over all sixteen condition combinations (#17).

**6 — Replay composes ClickHouse process truth with authorized evidence and
preserves legacy readability.** #21. Legacy readability is asserted in the
acceptance suite: a Phase 1 Investigation loads with a null draft rather than an
invented empty one.

**7 — Deletion erases in-scope content, produces minimal Tombstones, and leaves
Audit Entries unchanged.** #19, #22. `test_erasure_integration.py` walks every
`EvidenceSurface` member and compares `audit_entries` byte for byte across the
operation.

**8 — The acceptance paths are linked as primary evidence.**
`apps/api/tests/test_phase_2_acceptance.py` — thirteen criteria, 89 tests, real
application policy, real Postgres under RLS, real transactional outbox, with
only the Agent pipeline and Semantic layer doubled (#24).

**9 — The Insight corpus and the Observatory accessibility journeys are linked.**
`evals/insight/` (17/17) and `apps/zentra-os-e2e/src/observatory-journeys.spec.ts`
— 69 journeys across Chromium, Firefox and WebKit with `wcag2a` + `wcag2aa`
scans (#25).

**11 — Governed notes distinguish current behaviour, retained compatibility and
deferred work.** [[Current Implementation Status]] and
[[Phase 2 - Insight Auditor and Replay]] were corrected on 2026-08-01; the
status note had claimed deletion and Replay were still missing after both had
shipped.

**12 — Statistician, causal proof, generalized datasets/questions and production
operability remain outside Phase 2.** None exists in the codebase.
`RootCauseState` has one member, `unresolved`, and the Insight Agent refuses a
causal claim rather than producing a weak one. Scenarios remain an allowlist of
two.

**13 — The governed documentation check passes.** `nx run docs:check` is green,
and Phase 2 is **not** marked complete, because criterion 10 is not evidenced.

## Not evidenced

**10 — The passing uncoached design-partner record is linked from the Phase 2
exit checklist.** #26 has not been run.

This cannot be delegated. The first criterion of #26 is that the reviewer did
not implement the feature and receives no developer coaching, and the agent that
built Phase 2 satisfies neither. A record written without the exercise would be
the fabricated evidence this product exists to prevent, so none has been
written and the exit-checklist box remains unticked.

**What unblocks it:** one design partner, the two governed synthetic
Investigations already seeded by `tools/e2e/fixtures.py` (one satisfying every
publication condition, one gated on an unresolved contradiction), and the rubric
in #26. When the exercise is run, its dated record is linked here and #27 can be
certified.

## Defects found by this work

Three real defects were found by the acceptance and journey suites rather than
by review, and all are fixed:

- API errors reflected caller input — posting `<script>alert(1)</script>` as a
  scenario key returned it verbatim in a client-visible error.
- Raw error messages reached the immutable ClickHouse ledger, outside the
  erasure boundary, where they would have outlived the deletion meant to erase
  them. A pre-existing violation of ADR 0006.
- Three WCAG AA contrast failures and an `aria-label` on a bare `div`, where the
  label was silently dropped by exactly the readers it was added for.

Parent: [[Overview MOC]]
