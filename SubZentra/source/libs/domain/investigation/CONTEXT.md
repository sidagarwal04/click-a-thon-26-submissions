# Investigation

Investigation owns one traceable attempt to answer a governed business question and the states that make its progress explicit.

Groups and Projects organize the Investigation Thread surface. They are
Tenant-owned navigation containers, not analytical authority and not nested
ACL boundaries. Archived containers remain readable and make descendants
read-only without deleting Investigation history.

An Investigation Thread is the linear conversational boundary around immutable
messages and separately governed Investigations. Draft Threads hold unresolved
user and router clarification messages without fabricating analytical work.
Intake activates a Thread only when a question resolves inside the tenant's
Analytical Scope (see [[adr/0027-analytical-scope-replaces-scenario-whitelist]]);
an out-of-scope or ambiguous question clarifies instead of fabricating work.

Once activated, an Investigation accumulates its working memory on an
Investigation Board rather than passing through a fixed sequence of steps —
see [[adr/0026-investigation-engine-owns-orchestration]].
Whether the evidence can actually answer is the Cube Analyst's judgement
against the tenant's live catalog, not a router's against a fixed list. Draft
Threads remain readable.

Follow-ups and retries create new immutable Investigations with linear parent,
retry-of, and Thread-sequence lineage. Published Findings may create a strict
Visualization Brief and independently retriable presentation artifact.

## Language

**Investigation Status**:
The current lifecycle position of an Investigation, including whether it is active, blocked for Human Approval, or terminal.
_Avoid_: Run state, workflow status

**Investigation Board**:
The durable object one Investigation accumulates its working memory onto — Facts, Hypotheses, Knowledge Gaps, Conflicts, evidence references, and bounded Confidence — read and written by Work Items rather than passed through a fixed sequence of steps.
_Avoid_: Workspace, state, scratchpad

**Work Item**:
One unit of work an Orchestrator Loop assigns to a capability-matched Agent against a gap on the Investigation Board, tracked through pending, running, waiting, blocked, completed, or rejected.
_Avoid_: Task, step, node

**Knowledge Gap**:
Something the Investigation Board does not yet know, carrying a priority an Orchestrator Loop uses to decide what to work on next.
_Avoid_: Question, todo, missing data

**Conflict**:
A contradiction between two pieces of evidence on the Investigation Board that must be resolved or explicitly documented before Insight may proceed.
_Avoid_: Discrepancy, error, mismatch

**Analytical Scope**:
The Tenant-configured allowlist of Cube cubes, and optionally members, that Intake and analytical Agents may resolve a question against; narrower than but never wider than `SemanticCatalog.reject_ungoverned`.
_Avoid_: Scenario, whitelist, permission

**Completion Criteria**:
The deterministic set of conditions — question answered, no high-priority Knowledge Gaps, evidence validated, Conflicts resolved or documented, confidence bounded above threshold, budget not exhausted — an Orchestrator Loop checks before stopping; never "no Work Items remain" alone.
_Avoid_: Done, finished, queue empty

**Finding**:
A published, evidence-backed analytical conclusion produced by an Investigation after deterministic publication policy or any required Human Approval.
_Avoid_: Answer, response, insight blob

**Draft Finding**:
An unpublished analytical conclusion proposed by the Insight Agent after evaluation and before publication policy or Human Approval decides its outcome.
_Avoid_: Finding, answer draft, Orchestrator synthesis

**Measurement**:
The governed metric, value, and period an observed claim rests on, copied from the validated aggregate rather than restated by the Agent.
_Avoid_: Figure, number, data point

**Evidence Citation**:
A Tenant-authorized reference connecting one substantive Draft Finding claim to its governed metric, query context, producing Agent Execution, validated aggregate result, and Evaluator outcome.
_Avoid_: Evidence Reference, opaque artifact pointer, raw source row

**Root Cause Claim**:
A Finding claim asserting that evidence establishes why an observed change occurred, admissible only under an accepted causal-evidence standard.
_Avoid_: Driver, association, reason code

**Tombstone**:
A non-sensitive record that cited evidence and its derived content were erased, retaining only the deletion category and timestamp needed to explain their absence.
_Avoid_: Deleted evidence, placeholder, missing artifact

**Erasure Operation**:
One durable, retryable request to erase a terminal Investigation's evidence, which reports success only when every governed surface is clear.
_Avoid_: Delete job, purge, hard delete

**Evaluation Attempt**:
One bounded validation pass that either permits completion, requests retry, or opens a Human Approval gate.
_Avoid_: Evaluator run, confidence check

**Validation Result**:
Deterministic evidence stating which declared checks passed and which issues remain; it never invents confidence.
_Avoid_: Fake confidence, quality score

**Visualization Artifact**:
One independently metered terminal presentation of a Visualization Brief,
including renderer status, retry lineage, and erasure state.
_Avoid_: Finding, analytical result, dashboard
