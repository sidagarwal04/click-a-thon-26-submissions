---
id: domain-agent-execution
title: Agent Execution Domain
type: domain
status: active
owner: unassigned
source: context-map
created: 2026-07-29
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: current
priority: high
tags: [domain, agent-execution]
aliases: [agent-execution, Agent Port]
related: ["[[Domains MOC]]", "[[Investigation Domain]]", "[[adr/0005-agents-and-execution-participants]]"]
repo_path: libs/domain/agent-execution
code_refs:
  - libs/domain/agent-execution/CONTEXT.md
  - libs/domain/agent-execution/src/zentra_domain_agent_execution/contracts.py
  - libs/adapters/postgres/migrations/versions/0005_canonical_insight_role.py
---

# Agent Execution Domain

This context owns the contract for future autonomous analytical workers and one
bounded Agent Execution within an Investigation and Tenant.

The Agent Port declares structured input/output schemas, evidence, role-specific
Outcome Signal, tools, context budget, fallback, and evaluation-suite reference.
An outcome is either calibrated confidence or explicit validation; deterministic
work must not fabricate confidence.

Fourteen autonomous roles may eventually be registered. Auditor is a
deterministic event subscriber and Human Reviewer is a User at a Human Approval
gate; neither is an Agent.

## Current boundary

Five public roles are exposed — Orchestrator, SQL Analyst, Evaluator, Insight,
and Data Visualization. The first four participate in governed analytical work;
the fifth is presentation-only after publication. Each is a registry row that
the Orchestrator resolves at investigation start; a role with no enabled,
eval-passing Agent causes the Investigation to refuse rather than proceed.

Both the SQL Analyst and the Evaluator report `sample_size` alongside their
confidence — how many underlying records the figures rest on, read from a count
measure in their own result. Reading a count is extraction; scoring one's own
confidence is not, which is why the application bounds the latter by the former.

`IndependenceLevel` grades a recheck by what actually served each agent, not by
the routing table: `NONE` when one model served both, `PARTIAL` within a model
family, `FULL` across families. Fallback can collapse a chain onto one provider,
so the grade is taken from `usage.model` on what executed.

The governed catalog carries the permitted **values** of low-cardinality string
dimensions, not only member names. Without them an agent filtering
`North America` against data storing `NA` receives zero rows and no error.

The Semantic Layer Port is the only capability in the tree that reaches data.
No raw-SQL port exists for an Agent to be granted, which is what makes the SQL
Analyst's inability to see raw tables structural rather than instructed.

The Data Visualization Agent is registered with a versioned presentation
capability and receives only `VisualizationBriefV1`. It has no semantic-layer,
repository, audit-reader, file, shell, MCP, approval, or arbitrary-tool access.
Its served model, API version, tokens, cost, latency, and safe failure category
are recorded separately from analytical usage. See
[[adr/0020-thesys-terminal-presentation]].

## Phase 2 boundary

Phase 2 adds the Insight Agent as the fourth implemented autonomous role. It is
separately registered and evaluated, produces a Draft Finding from validated
upstream evidence, and never guarantees a Root Cause Claim. The Orchestrator
continues to delegate and arbitrate but stops synthesizing Findings. The
Statistician remains deferred. See
[[adr/0011-complete-phase-2-as-insight-auditor-and-replay]].

## Phase 3 target boundary

Phase 3 extends SQL Analyst instead of adding a Query Planner Agent. It proposes
a Governed Query Plan from a question and approved Semantic Model. Deterministic
policy authorizes, versions, compiles, and executes it against one Data Source
Binding. The Agent receives no raw SQL execution, file access, credentials, or
raw rows. Advanced SQL is a User-owned Query Version. Evaluator validates,
Insight writes the Draft Finding, and Orchestrator delegates/arbitrates. See
[[adr/0012-complete-phase-3-as-governed-bring-your-own-data]].

### Write vocabulary and read compatibility

The canonical role value is `insight`. Phase 1 shipped `insight_root_cause`
before any implementation existed, and the name promised causality the evidence
cannot establish, so the two now sit on opposite sides of a read/write split:

- **Written** — three seams refuse the legacy value outright.
  `ck_agent_registry_role` rejects it on insert into `agent_registry`;
  `reject_legacy_role` rejects it in `PostgresExecutionRecorder.record`, before
  the transaction opens, because the role reaches the immutable Audit Entry
  from there; and `chain_for` has no provider chain under it, so nothing can be
  routed to run as it.
- **Not advertised** — `PostgresAgentRegistry.enabled_agents` filters legacy
  rows out. A surviving row is readable but must never be planned against: the
  Orchestrator persists the roles it is offered into the task ledger, which is
  a write the recorder's guard never sees.
- **Read** — `insight_root_cause` stays a deserializable `AgentRole`, so
  Investigations that recorded it remain readable and displayable in Replay.
  Migration `0005_canonical_insight_role` re-adds the constraint `NOT VALID`
  precisely so an existing legacy row survives the tightening.

This is the expand step. Removing the legacy read path is a separate decision
and is not part of Phase 2 completion.

### Registration gating

`agent_registry` decides which Agents may reach a Tenant, and
`ck_agent_registry_enabled_requires_passing_eval` means a row cannot be
`enabled` without `eval_status = 'passing'`. `nx run evals:promote` is the only
thing that sets it, so an Agent existing in the table is not the same as an
Agent being allowed to run.

Insight is registered by `0007_register_insight_agent` disabled and `pending`,
exactly as the Phase 1 agents were. Promotion refuses it in three distinct
situations, each of which demotes it to `failing` and `enabled = false`:

- **Absent** — no suite under `evals/insight`.
- **Incomplete** — the suite is missing a case named in `REQUIRED_CASES`. A
  suite stays green while someone deletes the case that hurt, so passing every
  case it happens to contain is a weaker claim than having been tested for what
  matters. Insight is the only Agent that declares required coverage; the
  Phase 1 agents predate the requirement.
- **Failing** — any case in the suite fails.

Insight's descriptor grants **no** tool permissions. It is the one Agent that
reaches no capability at all — it works only on state the SQL Analyst and
Evaluator already validated — which is what makes "did it invent this?" a
question with a decidable answer. Its fallback policy is the role-keyed
provider chain, attributed through `AgentOutput.fallbacks` and proved by the
suite's fallback-attribution case.

`nx run evals:check` runs the gate in CI. Before Phase 2 nothing did, so a
deleted suite or an unregistered Agent left the build green.

### One Agent owns the conclusion

The pipeline is `plan → analyze → evaluate → insight`. There is no synthesis
node, and the Orchestrator has no phase that writes prose. It planned and then
wrote the Finding, which meant one Agent Execution both chose the work and drew
the conclusion, with no independent evaluation of the second job.

Insight sits outside the evaluation loop and reads the **terminal** Evaluator
outcome — drafting on an attempt about to be retried would conclude from
evidence the recheck is about to reject. Three failed rechecks still produce
exactly one Insight execution.

Insight is a required role, not a flag. Nothing else can write a Finding, so a
deployment whose registry has not promoted it refuses at plan time rather than
reaching the last node with nothing to run. The Orchestrator's declared
`output_fields` are `{"tasks"}` and nothing more, so a regression that put
prose back would be refused by the allowlist rather than published.

Insight receives the same row-free projection every agent does — `rows` never
travels in graph state — so it gets validated aggregates and the `artifact://`
pointers that lead to everything else. It records its own Agent Execution with
its own id, model, provider fallbacks, tokens, cost, latency and status, and
the Draft Finding names that execution.

**Compatibility is unchanged.** Historical executions recorded under the
legacy role, and Findings the Orchestrator wrote before the contraction, remain
readable — `insight_root_cause` is still a deserializable `AgentRole` and the
Phase 1 narrative in `investigations.state` is untouched. Removing that read
path is a separate decision.

Canonical language:
[Agent Execution context](../../libs/domain/agent-execution/CONTEXT.md).

Parent: [[Domains MOC]]
