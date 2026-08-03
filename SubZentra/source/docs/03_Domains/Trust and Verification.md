---
id: domain-trust-verification
title: Trust and Verification
type: domain
status: active
owner: unassigned
source: context-map
created: 2026-07-29
updated: 2026-07-30
reviewed: 2026-07-30
confidence: verified
implementation: current
priority: critical
tags: [domain, trust, approval, audit]
related: ["[[Domains MOC]]", "[[Investigation Domain]]", "[[ClickHouse Audit Ledger]]"]
repo_path: libs/domain/CONTEXT.md
code_refs:
  - libs/domain/CONTEXT.md
  - libs/domain/investigation/src/zentra_domain_investigation/model.py
  - libs/adapters/clickhouse/src/zentra_adapter_clickhouse/audit.py
---

# Trust and Verification

Trust is expressed through typed validation, Evidence References, explicit
Human Approval, immutable Audit Entries, and Investigation Replay.

A Human Approval blocks work that cannot proceed autonomously. Whether it opens
is decided by evidence, not by dataset size or a blanket policy: a model's
confidence is capped by how many underlying records it read and by how
independent the recheck actually was, and the investigation gates when the
result falls below the tenant threshold. See
[[adr/0010-confidence-bounded-by-evidence]].

Both outcomes are reachable. The eight-order refund scenario gates; the
three-hundred-order channel scenario publishes without review when the two
agents agree and the recheck is independent. Owner/admin Users decide; approval
completes the Finding and rejection records one structured reason.

An Audit Entry is a tenant-scoped fact about process, not a log line or reasoning
dump. Replay is the ordered record connecting question, evidence, validation,
and judgment.

The UI displays structured rationale and audit facts. It never exposes hidden
chain-of-thought or invents confidence.

## Phase 2 trust conditions

Phase 2 permits automatic publication only when evaluation converged, bounded
confidence clears the Tenant threshold, every substantive claim has a
resolvable Evidence Citation, and no unresolved contradiction remains.
Otherwise Human Approval is mandatory.

ClickHouse remains authoritative for immutable process truth; authorized
artifacts supply evidence content. Evidence deletion erases content while
Tombstones explain its absence. These conditions are accepted targets and are
not all implemented. See
[[adr/0011-complete-phase-2-as-insight-auditor-and-replay]].

## Evidence-informed approval — current

A reviewer at the gate is not shown a status and asked to trust it. Beside the
decision they see what the decision turns on: the bounded confidence and which
ceiling produced it, how many claims are measured rather than interpreted, how
many citations resolve and how many cannot be followed, every open
contradiction, and that root cause is unresolved.

Those come from the payload the page already holds rather than being fetched
when a disclosure is opened, so a reviewer cannot reach the buttons before the
evidence has answered.

The consequences are stated **before** the controls, not after: approving
publishes to the whole Tenant, rejecting records a structured reason and closes
without publishing, and either way the evidence, the decision and who made it
stay in Replay.

Members and viewers see all of it and can decide none of it — read-only is not
blind.

### A denied attempt is an event

Attempting a decision a membership may not make used to raise and leave no
trace, which meant the one thing worth noticing — repeated attempts by someone
who cannot approve — was the one thing Replay could not show.
`human_approval.denied` records the role and the internal user id — enough to
count repeated attempts by one person, which counting per role could never
answer — and nothing about the evidence, no email and no name.

It is silent in two cases. When the Investigation is invisible to the actor,
because recording against one they cannot see would confirm it exists. And when
there is no pending approval matching the identifier, because a denial against
a gate that never existed is noise, and writing one per request would let anyone
who can read an Investigation generate unbounded audit rows by posting
decisions at it.

Requested, denied and granted appear in causal order; a timeline that reordered
them would tell a different story about what happened. Ordering rests on
`occurred_at` with a per-aggregate microsecond bump, which holds within one
request but not across two written in the same microsecond — a limitation
Replay chronology owns rather than the approval gate.

Parent: [[Domains MOC]]
