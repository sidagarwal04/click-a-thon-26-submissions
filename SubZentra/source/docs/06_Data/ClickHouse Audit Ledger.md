---
id: data-clickhouse-audit-ledger
title: ClickHouse Audit Ledger
type: data-model
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: current
priority: critical
tags: [data, clickhouse, audit]
related: ["[[Data MOC]]", "[[Audit and Observability Architecture]]", "[[Audit Outbox Delivery]]"]
repo_path: infra/clickhouse/init/001_audit_entries.sql
code_refs:
  - infra/clickhouse/init/001_audit_entries.sql
  - libs/adapters/clickhouse/src/zentra_adapter_clickhouse/audit.py
  - libs/adapters/clickhouse/src/zentra_adapter_clickhouse/baselines.py
  - apps/api/src/zentra_api/audit_delivery.py
---

# ClickHouse Audit Ledger

`audit_entries` is the authoritative immutable Investigation Replay ledger. The
MergeTree order is `(tenant_id, investigation_id, created_at, entry_id)`.

The envelope includes trace/span IDs, tenant and Investigation, event type,
optional Agent/execution/step, timing, token/cost fields, input hash, typed
outcome, confidence when role-appropriate, tools/errors/model/status,
`artifact://` references, and redacted metadata.

Phase 1A deterministic events use validation outcomes and no confidence.
Application-generated event timestamps are monotonic so replay ordering
preserves causality even when transitions share a clock tick.

The runtime principal may insert/select only. Reads require internal tenant and
Investigation IDs. At-least-once delivery can create duplicate physical rows;
replay deduplicates stable `entry_id`.

Forbidden data includes prompts, raw analytical rows, uploaded values,
credentials, reviewer prose, and hidden reasoning.

## Phase 2 authority

ClickHouse remains authoritative for Replay chronology, participants, lifecycle
transitions, evaluation outcomes, publication decisions, and audit integrity.
It does not become an evidence store. Phase 2 resolves evidence content through
Tenant-authorized Evidence Citations from the artifact store; deleted evidence
resolves to a Tombstone while Audit Entries remain immutable.

## Split-authority Replay — current

Two authorities, and neither is asked to be the other.

**ClickHouse is authoritative for process truth**: chronology, participants,
Agent Execution outcomes, lifecycle transitions, evaluation results,
publication decisions, Human Approval, and audit integrity. Metadata only — no
raw row, prompt, credential or narrative reaches it, and the runtime's grants
are insert and select, so it cannot be rewritten even by mistake.

**The transactional artifact boundary is authoritative for evidence content**,
reached only through a Tenant-authorized Evidence Citation. Replay does not
copy evidence into the ledger to make it convenient; a reader follows a claim
to what backs it, and sees explicitly when that cannot be followed.

### Attribution

An Agent Execution's version was in `agent_id` all along and stripped for
readability, so Replay could not answer which build of an Agent produced a
Finding. It is shown. Safe usage — latency, spend, tokens — was written to the
ledger from the first Phase 1 execution and never read back, so Replay could
not answer "why was this slow?" at all.

### Two things the timeline used to lose

Reading only the ledger's own columns dropped a delivered event's failed
provider rungs, so an outage a fallback survived became invisible the moment
the event reached ClickHouse — the timeline showed *less* the longer you
waited. Both the delivered and the pending path now read `redacted_metadata`
through one reader, because a field that appears before delivery and vanishes
after is worse than one that never appeared.

Publication reasons travel the same way. A gate is explained at the point in
the timeline where it opened, in the policy's own vocabulary — the same words
the API and the approval panel use.

### Causal order

Delivered entries and undispatched outbox rows merge by `entry_id`, so
at-least-once delivery cannot duplicate a step, and sort by `created_at`.

The Investigation aggregate bumps `occurred_at` by a microsecond when two of
its own events share an instant, but `_investigation_from_row` rehydrates
`events=[]`, so that guard could never span requests: a denial and the approval
that followed it, written in the same microsecond by two requests, would sort
by a random identifier and Replay would show an order that never happened. The
floor is now read at the outbox — the one place every event passes through — so
each Investigation's timeline is strictly increasing regardless of how many
requests wrote it.

Parent: [[Data MOC]]

## Errors are categories, not messages

`errors` is the only free-string column on an Audit Entry, and the graph formats
each one as `Type: message`. A refusal message names the claim it refused and
the figure it could not ground, so delivering it verbatim would put Agent prose
into an immutable table that sits outside the erasure boundary — where it would
outlive the evidence deletion meant to erase it.

`error_categories` in `apps/api/src/zentra_api/audit_delivery.py` reduces each
string to its type against an allowlist before it reaches the ledger. Anything
unrecognized becomes `unexpected` rather than the raw prefix, because the
`Type: message` shape is a convention on the far side of a queue and not a
guarantee. The type is kept so Replay stays diagnosable: an operator must be
able to tell a grounding refusal from a provider outage.
