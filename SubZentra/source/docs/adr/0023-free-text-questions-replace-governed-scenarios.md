---
id: adr-0023
title: Free-text questions replace governed scenarios
type: adr
status: active
owner: unassigned
source: repository
created: 2026-08-02
updated: 2026-08-02
reviewed: 2026-08-02
confidence: verified
implementation: current
tags: [adr, investigation, routing]
related: ["[[Investigation Core]]", "[[Chat Surface]]", "[[Trust and Verification]]"]
repo_path: libs/application/investigation/src/zentra_application_investigation/thread_routing.py
---

# Free-text questions replace governed scenarios

## Decision

An Investigation is started from a question, verbatim. The `SCENARIOS`
registry, its two hardcoded questions, the keyword table that matched free
text against them, `UnsupportedScenarioError` and `GET /v1/scenarios` are all
removed. `route_governed_question` survives as a seam that now resolves every
question to itself.

A question is validated by `normalize_message_content` — the same NFKC,
control-character and length rules every user-authored Thread Message already
gets — rather than by a second rule that could disagree with it.

`GET /v1/catalog` replaces `/v1/scenarios`: it serves the asking tenant's own
governed measures and dimensions, resolved through `ScopedCubeSemanticLayers`.
Clients that must offer the user a starting point build it from the tenant's
vocabulary, so a suggestion the UI makes is one the Cube Analyst can answer.

`scenario_key` becomes read-compatibility only, on `Investigation`, in
`investigations.scenario_key`, and in every API response that carried it.
Investigations that ran before this keep rendering in Replay.

## Consequences

Whether the data can answer a question is now the Cube Analyst's judgement
against the tenant's live catalog, not a router's against a keyword list. A
question the evidence cannot support yields a low-confidence *gated* Finding
rather than a pre-emptive refusal. That is the failure mode the trust loop was
built for: `independence_of`'s confidence ceilings, the Evaluator's independent
recheck and `evaluate_publication` are unchanged and still stand between a weak
answer and a published one.

A refused request must not echo what was refused. That held for free while the
only rejectable body field was a short opaque key the handler declined to
repeat; a question is attacker-controlled text, and FastAPI's default
validation handler puts the rejected value in `input`. `create_app` installs a
handler that returns the location and reason only.

Every first Thread message now queues an Investigation, so no Thread is ever a
Draft and none can be deleted — `ensure_deletable` refuses a Thread carrying
analytical work, and that guarantee is deliberately kept. Archive is the path.
The delete endpoint stays for Draft Threads created before this decision.

Mid-investigation clarification is not replaced. The router was the only place
the product asked a user to disambiguate; the right successor is a tool that
suspends a run for human input, which the leased-execution model of
[[adr/0018-postgres-leased-execution]] has no state for. Out of scope here, and
named rather than left implicit.
