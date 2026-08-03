---
id: overview-phase-2-insight-auditor-replay
title: Phase 2 - Insight Auditor and Replay
type: overview
status: active
owner: unassigned
source: decision
created: 2026-07-30
updated: 2026-07-30
reviewed: 2026-07-30
confidence: verified
implementation: planned
priority: critical
tags: [phase-2, roadmap, insight, evidence, replay]
related: ["[[Overview MOC]]", "[[Current Implementation Status]]", "[[adr/0011-complete-phase-2-as-insight-auditor-and-replay]]", "[[Known Unknowns]]"]
depends_on: ["[[Investigation Trust Loop]]", "[[ClickHouse Audit Ledger]]", "[[Forensic Observatory]]"]
repo_path: .
code_refs:
  - libs/adapters/langgraph/src/zentra_adapter_langgraph/agents/insight.py
  - libs/application/investigation/src/zentra_application_investigation/service.py
  - libs/adapters/clickhouse/src/zentra_adapter_clickhouse/audit.py
  - apps/zentra-os/src/app/app.tsx
---

# Phase 2 - Insight Auditor and Replay

Phase 2 completes the evidence-to-explanation path for the existing governed
Investigation product. It is **in progress**. The durable boundary is accepted
in [[adr/0011-complete-phase-2-as-insight-auditor-and-replay]]; this note owns
mutable status and completion evidence.

## Completion promise

A business reader receives an evidence-grounded Finding from a dedicated Insight
Agent, can understand the workflow and publication decision through
Investigation Replay, can follow every substantive claim to authorized evidence,
and sees an explicit Tombstone when that evidence has been erased.

Insight reports observed changes and validated associations. It says “root cause
unresolved” when the available evidence cannot establish causality.

## Current status

| Capability | State | Repository evidence or gap |
| --- | --- | --- |
| Auditor | Current | Deterministic outbox subscriber writes metadata-only Audit Entries |
| Human Reviewer | Current | Owner/admin User decides at a Human Approval gate |
| Replay chronology | Current | Tenant-filtered ClickHouse timeline with pending-outbox merge |
| Finding narrative | Current | The Insight Agent is the only Agent that writes a conclusion; the Orchestrator plans, delegates and arbitrates |
| Insight Agent | Current | Registered, evaluation-gated, required, and the sole producer of a Draft Finding |
| Evidence Citation | Current | Claim-level Citations carry the full governed context and resolve through a Tenant-authorized endpoint, with active, unavailable and tombstoned decided against the evidence |
| Split-authority Replay | Current | ClickHouse process truth composed with Tenant-authorized evidence, with attribution, degradation and typed policy reasons |
| Tombstone deletion | Current | Owner/admin deletion of a terminal Investigation erases every governed surface and resolves affected citations to minimal Tombstones |
| External comprehension | Missing | No dated design-partner Replay exercise exists |

## Workstreams

### 1. Insight boundary

- Add the independently registered and evaluated Insight Agent.
- Move Draft Finding synthesis out of the Orchestrator.
- Cap Insight confidence by applicable upstream evidence.
- Evaluate unsupported causality, dropped contradictions, citation completeness,
  and safe “root cause unresolved” behavior.

### 2. Evidence Citation contract

- Define claim-to-citation cardinality and structured citation fields.
- Resolve citations through Tenant-authorized application/API boundaries.
- Connect each citation to its Semantic Metric, filters, periods, grain,
  producing Agent Execution, validated aggregate, and Evaluator outcome.
- Represent missing, denied, and deleted evidence explicitly.

### 3. Publication policy

- Require convergence, sufficient bounded confidence, complete citations, and
  no unresolved contradiction for automatic publication.
- Route every other Draft Finding to Human Approval.
- Record which policy condition produced the outcome.

### 4. Replay and deletion

- Keep ClickHouse authoritative for immutable process truth.
- Resolve evidence content from the artifact store without copying raw rows into
  the ledger.
- Erase evidence, Finding narrative, and derived values on Tenant evidence
  deletion.
- Preserve non-sensitive process metadata and return Tombstones for affected
  citations.

### 5. Completion evidence

- Test automatic and gated publication, citation authorization, cross-Tenant
  denial, missing evidence, and deletion.
- Record one uncoached design-partner exercise covering an automatically
  published and a gated Investigation.
- Require the reviewer to identify the change, separate evidence from
  interpretation, follow citations, explain the publication decision, and
  recognize unresolved causality.

## Exit checklist

- [x] Insight has its own registry entry, Agent Execution, model attribution,
  contract, and passing evaluation suite. — #12, #13; `evals/insight/`,
  `libs/adapters/langgraph/.../agents/insight.py`
- [x] The Orchestrator delegates and arbitrates but does not synthesize Findings.
  — #20; `_synthesize` and the `synthesize` node are gone
- [x] Every substantive Draft Finding claim has a resolvable Evidence Citation.
  — #15, #16; `DraftFinding.__post_init__` refuses an observed claim that cites
  nothing, and `PostgresEvidenceCitationRepository.resolve` dereferences it
- [x] Automatic publication enforces every accepted trust condition. — #17;
  `libs/domain/investigation/.../publication.py` and its 16-combination truth
  table
- [x] Replay composes ClickHouse process truth with authorized evidence content.
  — #21
- [x] Evidence deletion erases content and returns Tombstones without mutating
  Audit Entries. — #19, #22; `test_erasure_integration.py` walks every
  `EvidenceSurface` and compares `audit_entries` byte for byte
- [ ] Automated Phase 2 acceptance tests pass. — #24 in progress (9 of 13
  criteria); #25 merged 69 browser journeys
- [ ] The external Replay-comprehension exercise passes and is recorded. — #26,
  `ready-for-human`; cannot be delegated to an agent without invalidating it

No checkbox is satisfied by documentation or design alone. Link primary
implementation or validation evidence when changing a checkbox.

Per-criterion certification evidence for #27 is recorded in
[[Phase 2 Completion Evidence]]. Twelve of thirteen criteria are evidenced; the
uncoached design-partner record is the one that is not, and Phase 2 is not
certified complete until it is.

## Outside Phase 2

- Production hosting, deployment promotion, rollback, secrets, release process,
  and incident/on-call operations.
- Arbitrary datasets and questions, generalized scheduling, and additional
  warehouse connectors.
- Statistician, Demand Planner, Forecaster, Visualization, Executive Report
  Writer, and other later Agents.
- A Root Cause Claim until a separate causal-evidence standard is accepted.

## Source authority

The numbered phased build plan establishes the product phase name. Accepted
repository ADRs and current code override older role naming and implementation
sketches. The final architecture describes the eventual system but does not move
all later Agents into Phase 2. This note and ADR 0011 are now the canonical
repository definition.

Parent: [[Overview MOC]]
