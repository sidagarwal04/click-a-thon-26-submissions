---
id: adr-0015
title: Inferred Relations require human confirmation
type: adr
status: active
owner: unassigned
source: repository
created: 2026-08-01
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: current
priority: critical
tags: [adr, connector, relations, trust]
related:
  - "[[Connector Domain]]"
  - "[[adr/0010-confidence-bounded-by-evidence]]"
  - "[[Trust and Verification]]"
repo_path: libs/domain/connector
code_refs:
  - libs/domain/connector/src/zentra_domain_connector/relation.py
  - libs/domain/connector/src/zentra_domain_connector/confidence.py
---

# Inferred Relations require human confirmation

## Status

Accepted.

## Context

ClickHouse declares no foreign keys. MergeTree carries no referential
constraints, and its `PRIMARY KEY` / `ORDER BY` is a sparse index rather than a
uniqueness guarantee. So the joins that make a Tenant's data answerable exist
only in that Tenant's head, and `system.columns` will never reveal them.

The Connector therefore infers Relations from three deterministic signals: name
affinity, type compatibility, and value overlap measured by aggregate query at
the source. On TPC-H these signals recover documented foreign keys reliably, and
a high-confidence proposal looks convincing.

That is precisely the danger. A wrong join does not fail loudly. It returns
rows. An agent joining `orders` to `customers` on the wrong key produces a
number, cites its evidence, and publishes a Finding that is confidently,
traceably wrong — and every downstream mechanism this system has for catching
bad claims is built to check whether a claim follows from its evidence, not
whether the evidence was assembled over a relationship that exists.

Auto-accepting above a confidence threshold was the obvious alternative and
would have removed a step from the demo.

## Decision

Only a Relation a User has confirmed enters the Join Graph, and only the Join
Graph is visible to analytical agents. No confidence score, however high, admits
a Relation on its own.

Confidence is bounded by evidence rather than asserted, extending the reasoning
of [[adr/0010-confidence-bounded-by-evidence]] from Findings to Relations. A
proposal's confidence is the minimum of its raw signal score, a **sample-size
ceiling**, and a **cardinality ceiling** — the latter being what stops two
boolean columns with perfect overlap from being offered as a join, since perfect
overlap on two distinct values is what unrelated fields already do. Which ceiling
bound the score is recorded, so a reviewer can see *why* a proposal is not more
confident rather than only that it is not.

A Relation is pinned to the Field Identities it was confirmed against. When a
re-harvest changes or removes either endpoint, the Relation goes stale and leaves
the Join Graph until a human re-confirms it.

## Consequences

The Connector cannot be used without human review. A Tenant who connects a
warehouse and runs no confirmations has an empty Join Graph, and an Investigation
over that source is refused with an actionable message rather than silently
answering from a single table. This is a deliberate wall, and it is the main cost
of the decision.

Reviewer effort scales with schema width, mitigated but not removed by the
proposal floors — a pair whose values mostly do not match is not proposed at all,
because handing someone a long list of wrong guesses to reject individually is a
worse failure than proposing nothing.

In exchange, every join underpinning a published Finding traces to a named User
at a recorded time, and the system's existing promise that claims can be verified
and replayed extends to the relationships those claims were computed over.

Parent: [[Decisions MOC]]
