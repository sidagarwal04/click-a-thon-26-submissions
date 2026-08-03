---
id: overview-current-status
title: Current Implementation Status
type: overview
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: current
priority: high
tags: [status, phase-1]
related: ["[[Overview MOC]]", "[[Known Unknowns]]", "[[Managed Service Readiness]]"]
repo_path: README.md
code_refs: [README.md, libs/domain/investigation, apps/zentra-os]
---

# Current Implementation Status

## Implemented

- Phase 0 modular-monolith foundation and architectural boundary enforcement.
- Provider-neutral identity bindings and four-role Tenant Memberships.
- Postgres RLS, migrations, Investigation persistence, Human Approval locking,
  and transactional audit outbox.
- ClickHouse metadata-only audit ledger and replay deduplication.
- Eight Cube-governed commerce metrics and two deterministic seeds: the
  eight-order EU refund spike and the three-hundred-order NA channel growth.
- Phase 1A Investigation lifecycle, API, and Forensic Observatory.
- Phase 1 agent trust loop: SQL Analyst, Evaluator, and Insight as
  unmodified `AgentPort` implementations, now driven serially by an
  `OrchestratorLoop` against a durable Postgres `InvestigationBoard` and
  `WorkItem` queue instead of a compiled LangGraph graph
  ([[adr/0026-investigation-engine-owns-orchestration]]), with the
  Evaluator-Optimizer loop still exiting hard at three attempts. The graph,
  its Postgres checkpointer and the `langgraph` dependency are deleted.
  Resuming a crashed run from its Board is not yet built.
- Reactive orchestration: the Orchestrator Agent plans first (refusing the run
  outright when the registry has not promoted a required role), and the loop
  accepts its follow-up proposals *by rule* before running them concurrently
  as child Work Items that name the measurement they came from. Their Facts
  land on the shared `InvestigationBoard`, where two measurements of one metric
  over one period that disagree open a Conflict — documented rather than
  silently resolved, and carried to the reader. Fan-out is one level deep and
  capped at three; the cap is a constructor parameter, not yet a per-Tenant
  budget.
- Completion criteria in the domain (`assess_completion`): the loop stops when
  every criterion is satisfied *or* the budget is exhausted, never on "the
  queue emptied" alone, and the Board records which — with the same bounded
  confidence the Finding carries, never a higher one. Distinct from publication
  authority, which stays with `evaluate_publication`
  ([[adr/0011-complete-phase-2-as-insight-auditor-and-replay]]).
- Chat routing through an `IntakeAgent` reading a Tenant's governed catalog,
  replacing the two-scenario keyword whitelist
  ([[adr/0027-analytical-scope-replaces-scenario-whitelist]]); the two
  fixture scenarios below are no longer the only questions chat can resolve,
  though a real per-Tenant Analytical Scope is not yet configurable.
- Confidence bounded by evidence before it meets the Tenant threshold — a
  sample-size ceiling and a three-level independence ceiling, with
  `calibration_method` naming whichever bound applied
  ([[adr/0010-confidence-bounded-by-evidence]]). Both outcomes are reachable:
  the EU scenario gates, the NA scenario publishes without review.
- Agent Executions persisted per step with token, cost, and model attribution,
  and delivered to the audit ledger as metadata and `artifact://` pointers.
- Deterministic agent eval suites gating `agent_registry.eval_status`.
- Tiered model provider routing with per-role fallback chains, a per-provider
  circuit breaker, client-side schema validation, and an independence grade taken
  from what actually served each agent rather than from the routing table.
- Recorded cassettes of live runs under `evals/cassettes/`, replayed by
  `nx run evals:replay` to re-verify calibration offline at no cost.
- OpenTelemetry trace correlation and configurable OTLP export.
- Durable Postgres-leased analytical and visualization jobs with checkpoint
  resume, cooperative cancellation, linked retry, and a resumable public Work
  Feed.
- Linear Investigation follow-ups, a five-Agent public roster, strict factual
  Visualization Briefs, independently retriable Thesys C1 artifacts, safe
  server-mapped actions, and visualization-aware evidence erasure.
- A Visualization Brief that decides its own presentation: `view` is derived
  deterministically from the shape of the evidence rather than left as `auto`
  for the renderer to choose, and each governed comparison also travels as a
  two-point `series` carrying the citation that already validated both figures.
  No new query, no new evidence — the renderer can simply draw what was always
  there.
- The Chat Surface bound to the Thread API end to end: auto-provisioned
  workspace, Thread create and follow-up, a resumable SSE Work Feed read with
  `fetch` and deduplicated by `event_id`, live five-Agent progress, server-decided
  cancel/retry/approval affordances, and answers rendered as Thesys C1
  generative UI with a native fallback-brief renderer whenever the renderer is
  pending, failed, erased, or unconfigured. See [[Chat Surface]].
- The Connector context: Data Sources (connected and uploaded), immutable Catalog
  Versions, Field Profiles bounded by explicit query budgets, and Relations
  inferred from name affinity, type compatibility, and value overlap measured at
  the source. Confidence is bounded by a sample-size and a cardinality ceiling
  with the binding ceiling recorded ([[adr/0015-inferred-relations-require-human-confirmation]]).
  Only human-confirmed Relations form the Join Graph. Connector data bypasses
  Cube ([[adr/0014-connector-data-bypasses-cube]]). CSV and Parquet uploads land
  as Data Sources in a database separate from the audit ledger, which is what
  makes cross-source relation inference possible.
- Local Docker environment and managed Neon/ClickHouse Terraform definitions.

## Product phase

Phase 2 — Insight, Auditor, and Replay — is **in progress**. The current
implementation supplies the deterministic Auditor, Human Approval,
tenant-filtered ClickHouse Replay, a registered and evaluation-gated Insight
Agent that is the sole producer of a Draft Finding, claim-level Evidence
Citations that resolve through a Tenant-authorized endpoint, and a
deterministic four-condition publication policy no Agent can override.

It also supplies split-authority Replay, Tenant-initiated evidence deletion
returning minimal Tombstones, and allowlisted observability whose baselines are
read from the audit ledger rather than a second telemetry store.

Phase 2 is not complete for two reasons, and only one of them is agent-
addressable. The authenticated API acceptance suite is partial. And the external
Replay-comprehension exercise has not been recorded — it is `ready-for-human` by
design, because an uncoached exercise run by the agent that built the product
would not be uncoached. Certification is gated on it. See
[[Phase 2 - Insight Auditor and Replay]] and
[[adr/0011-complete-phase-2-as-insight-auditor-and-replay]].

Phase 3 — Governed Bring Your Own Data — is **accepted and unimplemented**. It
adds self-service related CSV/Parquet analysis and one assisted PostgreSQL Data
Connection without replacing Phase 2's Finding, citation, publication, Replay,
or deletion contracts. See [[Phase 3 - Governed Bring Your Own Data]] and
[[adr/0012-complete-phase-3-as-governed-bring-your-own-data]].

## Configured but not operationally signed off

Clerk, Neon, ClickHouse Cloud, Langfuse, E2B, and every model provider
(Anthropic, OpenAI, Gemini, NVIDIA, Groq, Cerebras, OpenRouter) require
externally supplied credentials. E2B remains configuration validation only.

The agents **have** been exercised against live models on both tiers, and the
recordings are committed. Gemini's free API tier caps at 20 requests per day —
about three investigations — after which the free chain collapses onto one
provider and its independence grade drops to `NONE`.

## Not implemented

The Statistician and later Agents, the cost-ceiling circuit breaker, a
cross-vendor Evaluator for the premium tier, recovery for a pipeline interrupted
mid-run, generalized scheduling, production application deployment, and a release
process.

Within the Connector specifically: connector Audit Entries and tracing remain
outstanding (`ch-nexus/ui-monorepo#14`). Agent Join Graph enforcement as
originally written is **superseded** — [[adr/0016-cube-is-the-single-tenant-scoped-analytical-gateway]]
made Cube the only data-reaching path, so the direct-ClickHouse port
[[adr/0014-connector-data-bypasses-cube]] described was never built and will not
be; the Join Graph now governs access through the relation fingerprint that keys
Cube's tenant scoping. See `ch-nexus/ui-monorepo#2` and its child tickets.

Relation inference accuracy is now **measured rather than asserted**. A
deterministic TPC-H subset seeds eight tables with nine documented foreign keys,
and `nx run evals:connector-accuracy` scores proposals against them, failing on
regression. Baseline: **9 of 9 recovered, recall 1.00, precision 0.69** — details
and what the four spurious proposals actually are in [[Source Catalog]].

A harvest also now reports what inference did *not* examine, grouped by reason,
and states that only single-field joins are considered. Without that an empty
proposal list reads as "your data has no relationships" when it may mean almost
nothing was eligible to be examined. Source deletion can be previewed before it
happens, including the confirmed Relations it would destroy in *other* sources.

Postgres persistence **is** now implemented (`ch-nexus/ui-monorepo#33`).
Migrations `0014_data_sources` and `0015_connector_catalog` create tenant-scoped
tables for Data Sources, Catalog Versions, Relations and Harvest Runs under the
same row-level security as the Investigation tables, and `AppDependencies`
constructs a `ConnectorService` over them. Credentials are sealed with AES-GCM
under `CONNECTOR_CREDENTIAL_KEY`; with that variable unset the service is not
constructed and the routes answer `503` naming it, rather than accepting a
password they cannot seal.

The harvest *runner* is a separate matter from harvest persistence: the tables
and repositories exist, and what still has to be proven is the discovery work
that fills them against a live warehouse — see the verification caveat below.

Phase 3's Data Source design — Dataset Workspaces, Relation Versions, Workspace
Snapshots, DuckDB execution, and the PostgreSQL Connector Type — remains
**planned and unimplemented**. It overlaps the shipped Connector context and the
two have not been reconciled; see the note in `CONTEXT-MAP.md`.

## Verification caveat

Phase 1 targeted suites, the agent eval suites, and local integrations pass
against scripted model responses.

Most of the Connector's tests run at the ConnectorService seam against in-memory
fakes. Two suites no longer do: nine integration tests exercise the four
repositories against a real Postgres — including a real AES-GCM-sealed password
that cannot be read out of the row storing it, a confirmed Relation surviving a
new connection pool, and a second Tenant reading nothing — and eleven
request-level tests drive the source routes through the router, where the
contract test only ever compared documents.

**No connector code has been executed against a live ClickHouse instance**, so
real dialect behaviour and `system.*` semantics are still unverified; a manual
pass is required before any demo. Agent behaviour against a live model is
unverified here. Existing shared foundation-package test debt is tracked
separately and must not be misreported as Phase 1 behavior.

Parent: [[Overview MOC]]
