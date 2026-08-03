---
id: domain-sequence
title: Sequence Domain
type: domain
status: active
owner: unassigned
source: repository
created: 2026-08-01
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: current
priority: critical
tags: [domain, sequence, data-steward, semantic-modeler, chdb]
related: ["[[Domains MOC]]", "[[Data Source Domain]]", "[[Connector Domain]]", "[[Agent Execution Domain]]", "[[Semantic Modeling]]", "[[adr/0022-sequence-step-execution-is-distinct-from-phase-3-query-execution]]"]
repo_path: libs/domain/sequence
code_refs: [libs/domain/sequence/CONTEXT.md, libs/domain/sequence/src/zentra_domain_sequence/sequence.py, libs/adapters/sequence-execution/src/zentra_adapter_sequence_execution/chdb_execution.py]
---

# Sequence Domain

Sequence owns the versioned graph of typed transform steps that turns a
Tenant's raw table into a final, model-ready table, and the two Agents —
Data Steward and Semantic Modeler — that build and hand off that graph.
Canonical definitions live in the [Sequence context](../../libs/domain/sequence/CONTEXT.md).

## One graph, one Dataset Workspace

A Sequence is owned by a Dataset Workspace, not by any single Investigation —
many Investigation Threads may reference the same Sequence's Final Tables.
It starts from one Raw Table, either a Connector Source Table or a Data
Source Dataset Table Version, and never mutates it.

## Append-only lineage

Each Sequence Step applies exactly one operation from a closed v1 typed
catalog (`drop_nulls`, `cast_type`, `dedupe`, `filter_rows`, `rename_column`)
to its input, producing a new immutable Prepared Table. A Sequence Step and
its Prepared Table are only ever recorded together, on a successful Sequence
Run — a failed run still records its typed failure reason, so nothing
attempted is silently dropped. A Sequence may branch into more than one Final
Table.

## Execution: chDB, not DuckDB

Sequence Step execution runs on chDB (embedded ClickHouse) inside AWS
Lambda — a deliberate, documented departure from [[adr/0012-complete-phase-3-as-governed-bring-your-own-data]]'s
DuckDB/Cloud Run engine for governed *queries*, since Sequence Step
execution is a different workload entirely. See
[[adr/0022-sequence-step-execution-is-distinct-from-phase-3-query-execution]]
for the full reasoning.

## Handoff to Semantic Modeling

A Final Table is the only thing the Semantic Modeler Agent may turn into a
Semantic Metric; it never models a Raw Table or an intermediate Prepared
Table directly. The resulting Metric Draft follows the same Human Approval
path as any other Semantic Model change.

Parent: [[Domains MOC]]
