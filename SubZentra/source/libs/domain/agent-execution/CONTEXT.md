# Agent Execution

Agent Execution owns autonomous analytical workers and the constrained work they perform during an Investigation.

## Language

**Agent**:
A registered autonomous worker that performs one cognitive role through the Agent Port. Auditor and Human Reviewer are explicitly not Agents.
_Avoid_: Bot, participant, human reviewer

**Agent Execution**:
One bounded invocation of an Agent for one Investigation and Tenant.
_Avoid_: Agent run, task process

**Orchestrator Loop**:
The deterministic application service that stewards an Investigation: observes the Investigation Board, matches open Knowledge Gaps to registered Agent capabilities, assigns Work Items, merges returned artifacts, and decides Completion Criteria. Not an Agent and never owns a conclusion — it may consult the Orchestrator Agent for planning proposals, but acceptance and completion are rule-based. See [[adr/0026-investigation-engine-owns-orchestration]].
_Avoid_: Pipeline, graph, controller

**Intake Agent**:
A registered Agent, canonical role `intake`, that resolves a Thread's question against the Tenant's Analytical Scope — either creating an Investigation and its Board or asking a clarifying question grounded in the scoped catalog. See [[adr/0027-analytical-scope-replaces-scenario-whitelist]].
_Avoid_: Router, classifier

**Insight Agent**:
A registered Agent that turns validated upstream evidence into a Draft Finding without claiming causality the evidence cannot establish. Its canonical role value is `insight`; `insight_root_cause` is a read-only compatibility value that Phase 1 wrote and nothing writes again.
_Avoid_: Root-Cause Agent, Finding writer, synthesis step

**Data Visualization Agent**:
A presentation-only Agent that turns a published Visualization Brief into C1
content without analytical, repository, audit-reader, file, shell, MCP,
approval, or arbitrary-tool access.
_Avoid_: Dashboard Agent, analyst, chart query agent

**Agent Capability**:
A versioned public declaration of one bounded behavior an evaluated Agent may
perform.
_Avoid_: Tool permission, implementation detail

**Cube Analyst Agent**:
A registered Agent that answers a question by exploring the governed catalog and running Governed Query Plans through the semantic layer, without executable raw-SQL authority. Named for what it queries: Cube compiles its plan and delegates to the warehouse (ADR-0025).
_Avoid_: SQL Analyst, Query Planner Agent, SQL generator

**Tool**:
One capability an Agent may be granted, declared on its Agent Descriptor and refused if named without permission. Every registered Tool reaches data through the semantic layer; there is no Tool for raw tables because there is no port for one (ADR-0024).
_Avoid_: Function, plugin, action

**Skill**:
A named instruction pack appended to an Agent role's system prompt. Stable per role, so it stays inside the cached prefix.
_Avoid_: Prompt fragment, persona

**Governed Query Plan**:
A typed analytical intent over approved members, relationships, filters, calculations, ordering, and limits that is authoritative in Normal Mode.
_Avoid_: SQL, query JSON, execution request

**Normal Mode**:
The query interaction in which the Governed Query Plan is authoritative and editable through structured controls.
_Avoid_: Basic mode, visual SQL

**Query Version**:
One immutable, attributable version of a Governed Query Plan or Advanced SQL Override and its validation outcome.
_Avoid_: Query edit, saved SQL

**Advanced SQL Override**:
A User-authored read-only DuckDB statement that replaces the plan as authority for one Query Version and cannot be silently reverse-converted.
_Avoid_: Custom query, generated SQL edit

**Outcome Signal**:
Role-appropriate evidence about an Agent Execution: either calibrated confidence or an explicit validation result.
_Avoid_: Universal confidence score, quality score

**Auditor**:
The deterministic subscriber that records redacted investigation events as Audit Entries.
_Avoid_: Auditor agent

**Human Reviewer**:
A User acting at a Human Approval gate.
_Avoid_: Human-review agent
