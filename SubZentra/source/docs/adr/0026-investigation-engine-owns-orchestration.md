---
id: adr-0026
title: Investigation Engine owns orchestration; LangGraph is not the platform controller
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
tags: [adr, investigation, orchestration, agent-execution]
related:
  - "[[Investigation Domain]]"
  - "[[Agent Execution Domain]]"
  - "[[Investigation Trust Loop]]"
  - "[[adr/0005-agents-and-execution-participants]]"
  - "[[adr/0011-complete-phase-2-as-insight-auditor-and-replay]]"
  - "[[adr/0018-postgres-leased-execution]]"
repo_path: libs/application/investigation
code_refs:
  - libs/application/investigation/src/zentra_application_investigation/ports.py
  - apps/api/src/zentra_api/pipeline.py
  - apps/api/src/zentra_api/dependencies.py
  - apps/api/src/zentra_api/outcomes.py
  - apps/api/src/zentra_api/orchestrator_loop.py
  - libs/domain/investigation/src/zentra_domain_investigation/completion.py
  - libs/domain/investigation/src/zentra_domain_investigation/investigation_board.py
  - libs/domain/investigation/src/zentra_domain_investigation/work_item.py
---

# Investigation Engine owns orchestration; LangGraph is not the platform controller

## Status

Accepted. Amends, and does not supersede, [[adr/0011-complete-phase-2-as-insight-auditor-and-replay]]
and [[adr/0018-postgres-leased-execution]]. Publication authority, the
Evaluator-Optimizer retry ceiling, and the Postgres-leased `ExecutionJob`
model are unchanged by this decision.

## Context

`InvestigationGraph` (`libs/adapters/langgraph/.../graph.py`) is a compiled,
fixed `StateGraph`: `plan → analyze → evaluate ⟲(≤3) → insight`. The
Orchestrator node writes a `tasks` ledger into graph state
(`_plan_node`); no other node reads it — the graph's edges are Python code,
not something the ledger's content can steer. There is no durable object
where facts, hypotheses, open gaps, or conflicts accumulate across steps;
completion means "the graph reached `END`," not "the question is answered."
13 of 17 declared `AgentRole`s have no runtime because there is no mechanism
by which a dynamically-planned step could invoke one — the graph only ever
calls the four roles wired into its four nodes.

The one seam this decision exploits: `InvestigationPipeline`
(`libs/application/investigation/.../ports.py`) is a `Protocol` with a single
method, `run(investigation_id, tenant_id, question, model_tier,
data_connection_id) -> PipelineResult`, implemented by exactly one class,
`LangGraphInvestigationPipeline`, bound once in
`apps/api/src/zentra_api/dependencies.py`. `ExecutionJobWorker`,
`InvestigationService`, and the lease/outbox/Work-Feed machinery call only
this protocol — none of them import `langgraph` or know a graph is involved.

## Decision

A Postgres-backed Investigation Engine — `InvestigationBoard` (durable facts,
hypotheses, knowledge gaps, conflicts, confidence) and a `WorkItem` queue
(`pending|running|waiting|blocked|completed|rejected`) — becomes the working
memory an Investigation accumulates into. An `OrchestratorLoop` application
service implements `InvestigationPipeline` in place of
`LangGraphInvestigationPipeline`, swapped at the single binding site in
`dependencies.py`. The loop observes the Board, matches open gaps to
registered agent capabilities, assigns `WorkItem`s, merges returned
artifacts back onto the Board, and decides completion — it does not execute
a fixed sequence of nodes.

`AgentPort` (`libs/domain/agent-execution/.../contracts.py`) is unchanged:
every specialist still reads its assigned `WorkItem` and the Board, produces
typed artifacts, and never calls another agent. `OrchestratorLoop` is a
deterministic service, not an Agent — it may consult an LLM for planning
proposals, but acceptance/rejection of a proposed `WorkItem` and the
completion decision are rule-based, not model output. Publication authority
stays exactly where ADR-0011 put it: deterministic Investigation policy,
never the Orchestrator, decides whether a Draft Finding becomes a Finding.

The cutover ships in stages against the same seam rather than as one
rewrite: Phase 1 introduces the Board/WorkItem/OrchestratorLoop but still
runs the existing Analyst → Evaluator → Insight sequence serially through
it (so the ≤3-attempt Evaluator-Optimizer loop and publication behavior are
unchanged while the underlying mechanism changes). Phase 2 makes the loop
reactive — continuous observe/plan/assign/merge/replan — and deletes
`InvestigationGraph` and the `langgraph` dependency from the execution path
entirely. LangGraph itself is not prohibited; it may still be used inside a
single agent's own implementation later, but never again as the platform
controller deciding what happens next across agents.

Crash recovery moves from LangGraph's checkpointer to reloading the Board
and `WorkItem`s from Postgres — consistent with ADR-0018's existing
lease-and-resume model, not a new recovery mechanism.

## Consequences

Adding a new analytical capability becomes: implement `AgentPort` + register
it, not add a graph node and rewire edges. The `tasks` ledger the
Orchestrator agent writes stops being dead state — the Board's gaps and the
registry's capability match are what a proposed `WorkItem` is actually
built from. `graph.py`, `InvestigationGraph`, and the four `agents/*.py`
node wrappers under `zentra_adapter_langgraph` become unused once Phase 2
completes; they are deleted then, not in Phase 1, so the visible pipeline
behavior does not change mid-phase. Nothing about the Evaluator's recheck,
the confidence ceilings (`confidence_ceiling`, model independence), the
Evidence Citation contract, or the Work Feed's public-summary rule
(ADR-0019) changes as a consequence of this decision.

## Verification

Phase 1: existing publication and citation test suites pass unmodified
against the new pipeline implementation; a fixture investigation still
converges within the ≤3-attempt Evaluator loop; `docs:check` is green.
Phase 2: `grep -r langgraph libs/application libs/domain apps/api` scoped to
the investigation execution path returns nothing; cancel/retry/approval
still work end to end through chat; Replay still shows every Agent
Execution.

## Phase 1 status

Implemented. `OrchestratorLoop` (`apps/api/src/zentra_api/pipeline.py`) is
bound at `dependencies.py`'s single `InvestigationPipeline` seam in place of
`LangGraphInvestigationPipeline`. It still drives the unmodified
`SqlAnalystAgent`/`EvaluatorAgent`/`InsightAgent` serially — Analyst →
Evaluator (≤`MAX_EVALUATION_ATTEMPTS`) → Insight — but every step is now a
persisted `WorkItem` against a real `InvestigationBoard`, with Facts
recorded and the seed Knowledge Gap resolved on completion. Covered by
`apps/api/tests/test_orchestrator_loop.py` (converged run, retry-then-settle,
attempt-cap-exhausted) and verified against a live Postgres instance
(migration upgrade/downgrade, RLS tenant isolation). `graph.py` /
`InvestigationGraph` / `_build_graph_factory` remain in the tree, unused by
this wiring, exactly as planned for Phase 2's deletion — not removed here.

## Phase 2 status

Implemented as the deletion, not the reactive loop. `graph.py`,
`checkpoints.py`, `InvestigationGraph`, `PostgresCheckpointStore`,
`LangGraphInvestigationPipeline` and `_build_graph_factory` are gone;
`langgraph` and `langgraph-checkpoint-postgres` are removed from
`libs/adapters/langgraph/pyproject.toml` and from the lock, so the package
imports nothing from LangGraph and the venv no longer contains it. The
adapter keeps its name and its four Agents, which never depended on the
framework. `InsightOutcome` / `ValidatedEvidence` / `PipelineOutcome` moved
to `apps/api/src/zentra_api/outcomes.py`, beside their only consumer.

Continuous re-planning was deliberately **not** built. For a single-question
workload there is one Knowledge Gap and one sane capability order (Analyst →
Evaluator → Insight), so a generic planner would be indirection with no
behavior behind it. That payoff arrives with Phase 3's fan-out, and the
reactive loop is folded into it.

Two properties the graph enforced needed attention rather than deletion:

- **Cancellation.** `InvestigationGraph` called `cancellation_checkpoint`
  around every agent call; the Phase 1 loop did not, so a `/cancel` during a
  three-attempt run took effect only once the whole pipeline finished.
  Restored in `OrchestratorLoop._run_step` — checked before the Work Item is
  created and again once the step is durable — and wired at
  `dependencies.py`. This is what ADR-0018's "next checkpoint observes
  cancellation" refers to for analytical jobs.
- **The registry gate.** `NoEnabledAgentError` — refuse when the registry has
  not promoted a required role — lives in `OrchestratorAgent`, which the loop
  does not invoke. It is therefore **not enforced on the live chat path**.
  The agent and its tests are kept
  (`libs/adapters/langgraph/tests/test_orchestrator_agent.py`), and deciding
  whether the Engine re-imposes the gap is open work, not a settled decision.
  `NoEnabledAgentError` remains in `pipeline.py`'s and `audit_delivery.py`'s
  known-error allowlists against that.

Crash recovery is still unbuilt: `OrchestratorLoop.run()` opens a new Board
on every call and never resumes an in-flight one, so LangGraph's checkpointer
was removed without a replacement. Reconstructing an interrupted run needs
`AgentExecutionRecord.output` for the persisted Work Item's execution, which
`AgentExecutionRepository` can already read and the loop does not.

Test coverage moved rather than went away: the ~30 tests that exercised the
Agents through the graph became 21 in `apps/api/tests/test_loop_agents.py` and
`test_loop_insight.py` (the same Agents, driven by the loop, faking only the
model and semantic layer) plus 8 standalone agent tests in the adapter. The
exceptions are the two LangGraph checkpointer-resume tests and
`test_checkpoints.py`, which tested the capability this ADR removes.

## Phase 3 status

Implemented, including the reactive planning Phase 2 deferred. The loop lives
in `apps/api/src/zentra_api/orchestrator_loop.py` — split out of `pipeline.py`,
which crossed the 600-line limit — and now runs:

1. **Plan.** `OrchestratorAgent` proposes follow-up measurements. This runs
   *first*, before anything is measured, because it is also the registry's
   capability gate: a deployment that must refuse should refuse before it
   spends, not after the Analyst and its recheck have run.
2. **Measure.** The primary question, through the unchanged
   ≤`MAX_EVALUATION_ATTEMPTS` Evaluator-Optimizer loop, now extracted as
   `_measure` so it is reusable.
3. **Fan out.** Accepted follow-ups run concurrently as child Work Items whose
   `parent_work_item_id` and `depends_on` name the measurement they came from
   — the emergent graph, grown by the Board rather than drawn in advance.
   Each earns its own Evaluator recheck; evidence nobody rechecked is not
   evidence this product cites.
4. **Merge.** Facts land on the shared Board. Two measurements of the same
   metric over the same period that disagree open a `Conflict`
   (`InvestigationBoard.contradicted_by`); the same values are corroboration,
   not a conflict.
5. **Settle.** Every Conflict is *documented*, never resolved — the loop has
   no evidence to say which measurement was right, and a third query would be
   a third opinion, not an arbiter. `_require_settled_conflicts` then fails
   closed before Insight, guarding a path that does not exist yet (a Phase 4
   loop deferring a Conflict to a human).

Acceptance is rule-based, per this ADR's Decision: `_accept` takes a proposal
only if its role has a runtime that can measure, it carries an objective, and
that objective is new; the cap applies last so junk arriving first cannot
consume a slot. The registry gate Phase 2 recorded as unenforced is enforced
again — `dependencies.py` passes the registry into `build_agents_factory`.

Deliberate limits, so they are not mistaken for oversights:

- **Insight still drafts from the primary measurement alone.** Feeding it N
  analysts would change `InsightAgent`'s schema, and this phase does not
  modify agent contracts. A follow-up that disagrees therefore reaches the
  reader as a documented Conflict on the outcome's contradictions, not as
  something Insight reasoned about.
- **A failing follow-up does not fail the run.** Its Work Item is REJECTED and
  its Agent Execution recorded, so Replay shows it, and its Knowledge Gap
  stays *open* — the honest record that something here is still unanswered.
- **Fan-out is one level deep.** Children do not themselves fan out.
- **The cap is a constructor parameter** (`MAX_FANOUT_WORK_ITEMS = 3`), not a
  per-Tenant budget. There is no budget field on `tenants` to extend, and
  inventing a schema before anyone has said what a Tenant's analytical budget
  is would be guessing. This is the seam that change lands on.

`InvestigationBoardRepository` gained `open_conflict` and `settle_conflict`;
the `board_conflicts` table existed since migration 0020 and had nothing
writing to it. Crash recovery is still unbuilt.

## Phase 4 status

Implemented. `CompletionCriteria` is formalized in the domain as
`libs/domain/investigation/.../completion.py`: `assess_completion` grades a
Board against every criterion — no open HIGH-priority gap, the recheck
validated, no unsettled Conflict, confidence at or above the Tenant's
threshold — and reports *all* unmet ones, since a run blocked on three things
that reports one gets fixed three times. The question the user asked is itself
a HIGH-priority gap, so "question answered" is that criterion rather than a
second representation that could disagree with it.

`should_stop` is the point of the phase: the loop stops when the criteria are
satisfied **or** the budget is exhausted, and the two are distinguishable.
Stopping is not finishing, and a run that reports the second as the first is
the confident-wrong-answer failure this system exists to avoid.

**This is not a publication gate.** `evaluate_publication` (ADR-0011) still
decides whether a Draft Finding may become a Finding, and is untouched. The
two decisions overlap — both care about the recheck and the threshold — but
they answer different questions (*may the reader see this?* versus *is there
more work worth doing?*) and neither is derived from the other.

The loop now writes the Board it previously created and abandoned:
`set_confidence`, `set_narrative` and `InvestigationBoardRepository.save` had
zero callers, so `confidence_score`, `confidence_threshold`, `narrative` and
`updated_at` were written at insert and never again. The recorded score is
`bounded_outcome`'s, not the Evaluator's raw one — the Evaluator's is capped
at the Analyst's but not by sample size or by how independent the recheck
actually was, so recording it would leave the Board more confident than the
Finding built from it, which is precisely what ADR-0010 forbids. That required
promoting `_bounded_outcome` to `bounded_outcome` and exporting it, so the loop
and the service share one number instead of duplicating the bounding.

**Visualization brief co-evolution: verified, not built.** The brief is already
constructed exactly once at publication — `prepare_published_visualization` is
called from the auto-publish path and the approve path in `service.py`, and
nowhere else. That is the once-at-publish behaviour this phase intended to
adopt first, so there was nothing to change. Refreshing a brief as evidence
lands remains unbuilt and unneeded until a run can publish before it finishes.
