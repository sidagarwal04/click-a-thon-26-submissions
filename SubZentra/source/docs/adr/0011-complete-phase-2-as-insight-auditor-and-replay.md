---
id: adr-0011
title: Complete Phase 2 as Insight, Auditor, and Replay
type: adr
status: active
owner: unassigned
source: decision
created: 2026-07-30
updated: 2026-07-30
reviewed: 2026-07-30
confidence: verified
implementation: planned
priority: critical
tags: [adr, phase-2, insight, evidence, replay]
related: ["[[Decisions MOC]]", "[[Phase 2 - Insight Auditor and Replay]]", "[[Investigation Domain]]", "[[Trust and Verification]]"]
depends_on: ["[[adr/0005-agents-and-execution-participants]]", "[[adr/0006-metadata-only-audit-ledger]]", "[[adr/0010-confidence-bounded-by-evidence]]"]
repo_path: docs/adr/0011-complete-phase-2-as-insight-auditor-and-replay.md
code_refs:
  - libs/domain/agent-execution/src/zentra_domain_agent_execution/ports.py
  - libs/domain/investigation/src/zentra_domain_investigation/model.py
  - libs/adapters/clickhouse/src/zentra_adapter_clickhouse/audit.py
  - libs/adapters/langgraph/src/zentra_adapter_langgraph/agents/insight.py
---

# Complete Phase 2 as Insight, Auditor, and Replay

## Status

Accepted. Implementation is in progress; accepting this decision does not mark
Phase 2 complete.

## Context

The recovered product build plan names Phase 2 **Insight, Auditor, Replay**.
Later architecture documents describe the eventual Agent system but do not
replace that numbered product roadmap. The repository already implements much
of the phase under Phase 1: a deterministic Auditor, Human Approval, a
ClickHouse-backed timeline, tenant-filtered replay, and a Finding synthesized by
the Orchestrator. It does not implement a dedicated Insight Agent, resolvable
claim-level evidence, deletion Tombstones, or external Replay-comprehension
evidence.

Three ambiguities made the phase unsafe to execute without a new decision:

- “Insight/Root-Cause” promises causality the current evidence cannot establish.
- “Replay from ClickHouse alone” conflicts with the metadata-only audit ledger.
- “Human Reviewer is the only publish authority” conflicts with the product's
  confidence-gated autonomy and the implemented automatic completion path.

Production hosting, release promotion, rollback, secret management, and incident
response remain essential, but adding them would overwrite the only explicit
product roadmap and obscure a phase that is already partly implemented.

## Decision

Phase 2 completes the product's evidence-to-explanation path. It adds a
dedicated **Insight Agent**, finishes claim-level evidence and deletion
semantics, and proves that a person outside the implementation team can
understand a Finding through Investigation Replay.

### Insight is an Agent; root cause is not its promise

Insight is a separately registered `AgentPort` implementation with its own
Agent Execution, version, model attribution, evidence contract, and evaluation
suite. It receives completed SQL Analyst and Evaluator outcomes and produces a
Draft Finding. The Orchestrator delegates and arbitrates but no longer writes
the Finding.

The canonical role is **Insight Agent**, not Root-Cause Agent. Phase 2 Insight
may report observed changes, validated associations, and “root cause
unresolved.” It must not represent sample-size bounds, correlations, model
agreement, or reason codes as causal proof. A Root Cause Claim is forbidden
until a separate causal-evidence standard is accepted and satisfied.

The Statistician remains outside Phase 2.

### Every substantive claim has resolvable evidence

Every substantive Draft Finding claim carries at least one tenant-authorized,
resolvable Evidence Citation. A citation identifies:

- the governed Semantic Metric;
- filters, periods, and grain;
- the producing Agent Execution;
- the validated aggregate result; and
- the Evaluator outcome.

The user-facing contract is the Evidence Citation, not an opaque execution
pointer. Raw customer rows do not enter ClickHouse or Agent-to-Agent messages.

### Publication is conditional and deterministic

A Draft Finding publishes automatically only when evaluation converged, bounded
confidence clears the Tenant threshold, every substantive claim has a
resolvable Evidence Citation, and no unresolved contradiction remains.
Otherwise Human Approval is mandatory.

No Agent independently publishes. Publication authority belongs to the
deterministic Investigation policy. The Human Reviewer remains a User acting at
a gate, and the Auditor remains a deterministic event subscriber, as established
by [[adr/0005-agents-and-execution-participants]].

### Replay has split authority

ClickHouse is authoritative for Replay chronology, participants, lifecycle
transitions, evaluation outcomes, publication decisions, and audit integrity.
The artifact store is authoritative for evidence content resolved through
tenant-authorized Evidence Citations. Replay exposes missing or deleted evidence
explicitly rather than silently omitting it.

This refines “Replay from ClickHouse alone”: ClickHouse alone proves what
happened and why policy made its decision; cited artifacts prove what supported
each claim.

### Deletion preserves process and erases content

A Tenant evidence-deletion request erases evidence payloads, query results,
Finding narrative, and derived metric values. It preserves only Investigation
identity, lifecycle decisions, non-sensitive execution metadata, and immutable
Audit Entries.

Each affected Evidence Citation resolves to a Tombstone containing the deletion
category and timestamp, never the deleted values. Replay can prove that work
occurred and evidence was erased, but cannot reproduce the erased conclusion.

## Phase completion

Phase 2 is complete only when all of the following are evidenced:

1. Insight is registered, independently executed, attributed, and evaluation
   gated.
2. The Orchestrator no longer synthesizes Findings.
3. Every substantive claim has a tenant-isolated, resolvable Evidence Citation.
4. Publication enforces convergence, bounded confidence, complete citations,
   and contradiction checks.
5. Replay composes ClickHouse process truth with authorized evidence artifacts.
6. Evidence deletion erases content and resolves affected citations to
   Tombstones without mutating Audit Entries.
7. Automated tests cover automatic publication, Human Approval, cross-Tenant
   denial, missing evidence, and deletion.
8. At least one design-partner reviewer, without developer coaching, can use
   Replay to identify what changed, distinguish evidence from interpretation,
   follow each claim to evidence, explain automatic versus gated publication,
   and recognize unresolved root cause.

The external exercise must cover one automatically published Investigation and
one gated Investigation, with a dated, data-safe validation record.

## Alternatives considered

**Make Phase 2 production operability.** Rejected because it overwrites the
explicit product phase and hides the incomplete explanation/replay promise.
Operability remains a separate roadmap decision.

**Keep Finding synthesis in the Orchestrator.** Rejected because synthesis has
distinct failure modes and requires its own contract, attribution, and
evaluation.

**Require Human Approval for every Finding.** Rejected because it discards
confidence-gated autonomy. Deterministic policy may publish only when every
trust condition passes.

**Store complete evidence in ClickHouse.** Rejected because it violates the
metadata-only ledger, expands sensitive-data retention, and makes deletion
incompatible with immutable audit history.

**Add the Statistician to justify Root-Cause naming.** Rejected because it
widens the explicit phase and statistical significance still does not establish
causality.

## Consequences

Phase 2 is explicitly in progress rather than absent or complete. Existing
Auditor, Human Approval, and Replay work is retained instead of rebuilt.
Finding synthesis moves out of the Orchestrator, evidence becomes a
consumer-visible contract, and deletion requires coordinated artifact and
projection redaction while preserving audit metadata.

Production deployment, release operations, generalized datasets/questions,
scheduling, new warehouse connectors, the Statistician, and later Agents are
not Phase 2 completion work.

## Verification

Mutable status and evidence live in [[Phase 2 - Insight Auditor and Replay]].
The accepted boundary is enforced when implementation tests and the external
comprehension record satisfy every completion criterion above. Documentation
must continue to distinguish current behavior from the planned Phase 2 target.

Parent: [[Decisions MOC]]
