---
id: adr-0024
title: Agents call tools through a governed registry
type: adr
status: active
owner: unassigned
source: repository
created: 2026-08-02
updated: 2026-08-02
reviewed: 2026-08-02
confidence: verified
implementation: current
tags: [adr, agent-execution, tools]
related: ["[[Agent Execution Domain]]", "[[Cube Adapter]]", "[[Investigation Trust Loop]]"]
repo_path: libs/adapters/langgraph/src/zentra_adapter_langgraph/runtime.py
---

# Agents call tools through a governed registry

## Decision

`ModelPort.complete` accepts tool definitions and may return tool calls.
`ModelMessage` carries `tool_calls` and `tool_results` so a transcript can be
replayed to a provider whole, which both wire formats require. Both provider
clients build their request blocks explicitly instead of handing
`ModelMessage.model_dump()` to the SDK.

`AgentRuntime` is the loop: offer an Agent the tools its `AgentDescriptor`
permits, run what it asks for, hand the results back, repeat until it answers
or `MAX_STEPS` trips. It is not a LangGraph node — the graph orchestrates
Agents, and this is what happens inside one Agent Execution.

`AgentDescriptor.tool_permissions` is the enforcement point, checked twice: a
tool outside an Agent's permissions is never offered, *and* is refused if named
anyway, because a model can invent a tool name it was never shown.

Every registered tool reaches data through `SemanticLayerPort` and nothing
else. The Cube Analyst holds `semantic_catalog_search` and `semantic_query`.

`ModelChoice.supports_tools` marks each routing rung, default False. When tools
are requested, a rung that cannot serve them is skipped and the skip recorded
in `fallbacks` like any other. Cerebras and `openrouter/free` are unmarked —
one answers 402 before its support can be observed, the other is an alias whose
answer changes — and both still serve the one-shot calls the Orchestrator and
Insight make.

## Consequences

The Cube Analyst gains iteration, not reach. There is no raw-table port
anywhere in the tree for a tool to wrap, so the semantic-layer-only guarantee of
[[adr/0016-cube-is-the-single-tenant-scoped-analytical-gateway]] holds unchanged: the loop lets an Agent look at a tenant's catalog, narrow, and
query again, which is the difference between one demo cube and a harvested
warehouse it has never seen.

Nothing inside the loop raises. A refused member, an unauthorized tool, a
broken tool — all three return as `is_error` results the model reads and
corrects on the next step. Failing an investigation because a model guessed one
argument wrong is a worse answer than letting it try again. `evals/cube_analyst`
asserts recovery where it previously asserted a raise.

The loop exits hard on the step cap and never returns its last partial answer,
the same discipline `MAX_EVALUATION_ATTEMPTS` applies to the Evaluator loop.

`AgentExecutionRecord.tool_calls` records name, latency and outcome per call,
and each becomes an `agent.capability_used` Work Feed event. Arguments and
results are absent by construction: they carry rows, and [[adr/0006-metadata-only-audit-ledger]] keeps the
ledger metadata-only.

Usage accumulates across every turn, not only the one that answered. The model
recorded is the answering turn's, since that is the call
`independence_of` grades.

Cassette keys include tool definitions, and omit the key entirely when none are
offered, so recordings made before tools existed stay valid. The Cube Analyst's
own recordings do not: [[adr/0025-the-sql-analyst-is-renamed-the-cube-analyst]] changed its role name and its prompt, both
of which the key covers. They need re-recording.
