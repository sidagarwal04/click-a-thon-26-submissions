---
id: api-investigation
title: Investigation API
type: api
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-30
reviewed: 2026-07-30
confidence: verified
implementation: current
priority: critical
tags: [api, investigation, approval]
related: ["[[APIs MOC]]", "[[Investigation Trust Loop]]", "[[Forensic Observatory]]"]
depends_on: ["[[Authenticated Tenant Resolution]]", "[[Investigation Core]]"]
repo_path: apps/api/src/zentra_api/routes.py
code_refs:
  - apps/api/src/zentra_api/routes.py
  - apps/api/tests/test_api.py
---

# Investigation API

| Method | Path | Purpose | Authorization |
| --- | --- | --- | --- |
| GET | `/v1/scenarios` | List the governed questions this deployment answers | all Membership roles |
| POST | `/v1/investigations` | Start one of the listed scenarios | owner/admin/member |
| GET | `/v1/investigations/{investigation_id}` | Read current detail/replay | all Membership roles |
| POST | `/v1/investigations/{investigation_id}/approvals/{approval_id}/decision` | Approve or reject | owner/admin |

## Scenarios

Returns each scenario's key, canonical question, and neutral descriptive facts.
Served rather than compiled into the client so the question text has one home;
the launcher renders whatever this returns. The facts describe the data — region,
window, scale — and never a predicted outcome.

## Create

Request is exactly `{"scenario_key":"<key>"}` for a key the scenarios endpoint
lists — `eu_refund_spike` or `na_channel_growth`. Extra fields and any
unregistered scenario are rejected. The response is `201` with canonical question,
state, Finding, validation, pending approval, safe timeline, and delivery state.

## Read

Response includes internal Investigation ID, scenario, status, version,
evaluation attempts, timestamps, structured metrics, `artifact://` evidence,
typed validation, optional approval with `can_decide`, and deduplicated audit
timeline.

## Decide

Decision is `approve` or `reject`. Approval accepts no reason. Rejection requires
`insufficient_evidence`, `incorrect_interpretation`, `policy_mismatch`, or
`needs_more_analysis`. Exact decision replay is idempotent; conflicting or late
decisions return `409`.

## Error/privacy behavior

- `401`: invalid identity.
- `403`: insufficient role.
- `404`: invisible/cross-tenant Investigation or approval.
- `409`: invalid transition or conflicting decision.
- `422`: unsupported scenario or invalid request/reason.
- `503`: sanitized governed-metric dependency failure with no misleading result.

## Draft Finding — additive, current

`InvestigationDetailResponse` carries an optional `draft_finding` block beside
the existing `finding`. Additive on purpose: `finding` is unchanged, so every
Phase 1 client keeps working, and the two are served together rather than one
replacing the other.

`draft_finding` is `null` for an Investigation that ran before the Insight
Agent existed. That null is the signal a client uses to tell a legacy narrative
apart from claims that are structured and will become individually citable —
reporting the old shape as the new one would assert its sentences are
followable when nothing can resolve them.

Each claim carries `kind` (`observed` or `interpretation`), a `position`
contiguous from zero, and `citation_ids`, which stays empty until Evidence
Citations exist. `root_cause` is always `unresolved` in Phase 2.

## Evidence Citation resolution — current

`GET /v1/investigations/{investigation_id}/citations/{citation_id}` follows one
claim to the evidence behind it, returning the governed metric, filters,
period, grain, producing Agent Execution, validated aggregate, Evaluator
outcome, and the citation's state.

Nested under the Investigation deliberately: the Investigation's own visibility
is checked first, so a citation identifier cannot become a way to probe an
Investigation the caller cannot read.

**There is no Tenant parameter**, here or anywhere below. Identity comes from
the verified token through `authenticated_context`, so there is nothing for a
caller to supply or override, and the transaction's `app.tenant_id` is set from
it before any row is read.

Three ways of not being allowed to see a citation — another Tenant's, another
Investigation's, and nonexistent — return the same `404` with the same body. A
caller who could tell them apart could confirm somebody else's evidence exists
by copying an identifier. A malformed identifier is a `422` and discloses
nothing either.

`active` and `unavailable` are decided against the evidence, not stored
optimistically: `producing_execution_id` is `ON DELETE SET NULL`, so a citation
can outlive the execution that produced it, and resolution checks that the
execution is still there. **Unavailable is a fault, never a Tombstone** —
reporting loss as a deliberate erasure would reassure a reader about data that
is simply gone. Tombstones themselves arrive with evidence deletion.

Resolution records its state and duration as span attributes and nothing else;
an operator can tell slow from missing from denied without the evidence.

## Phase 2 planned contract

Tombstone results arrive with evidence deletion. Current `artifact://` strings
must not be misreported as the completed citation contract. See
[[Phase 2 - Insight Auditor and Replay]].

Parent: [[APIs MOC]]
