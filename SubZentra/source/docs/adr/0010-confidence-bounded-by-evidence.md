---
id: adr-0010
title: Bound confidence by evidence, not by what the model asserts
type: adr
status: active
owner: unassigned
source: decision
created: 2026-07-30
updated: 2026-07-30
reviewed: 2026-07-30
confidence: verified
priority: critical
tags: [adr, agent-execution, trust, confidence, calibration]
related: ["[[Decisions MOC]]", "[[Trust and Verification]]", "[[Investigation Domain]]", "[[Agent Execution Domain]]"]
repo_path: docs/adr/0010-confidence-bounded-by-evidence.md
code_refs:
  - libs/domain/agent-execution/src/zentra_domain_agent_execution/contracts.py
  - libs/domain/investigation/src/zentra_domain_investigation/model.py
  - libs/application/investigation/src/zentra_application_investigation/service.py
  - evals/cassettes
---

# Bound confidence by evidence, not by what the model asserts

## What forced the decision

The first live run of the agent pipeline put two models on identical data — four
governed orders per month — and asked each for a confidence.

| Model | Confidence | Outcome |
|---|---|---|
| Claude Sonnet 5 | **0.55** | gated, noting the sample was not statistically robust |
| Gemini 3 Flash | **0.95** | **auto-published** |

Same evidence, same prompt, same threshold, a forty-point spread. The confidence
gate could not catch it, because the gate trusts a number the model asserts about
itself. The Evaluator did not help: it agreed at 0.95, being no better
calibrated.

That is the confidently-wrong output this product exists to stop, arriving
through the mechanism built to stop it.

## Decision

A model's confidence is treated as an upper claim, not a measurement. It may be
**lower** than the evidence supports; it may never be higher. Two bounds are
derived from the evidence in code, and the recorded confidence is the minimum of
the model's own score and both bounds. `calibration_method` names whichever bound
applied, so Investigation Replay shows *why* a number was lowered rather than
only showing a lower number.

### Sample size

Both the SQL Analyst and the Evaluator report `sample_size` as a required field
on their output schemas. Reading a count off a result is **extraction**, which
models do reliably — unlike scoring their own confidence. Counting rows in code
would be wrong: a query returning two monthly totals covers many more underlying
records than two.

| Underlying records | Ceiling |
|---|---|
| unknown, or fewer than 5 | 0.50 |
| fewer than 30 | 0.65 |
| fewer than 100 | 0.85 |
| 100 or more | 1.00 |

The two agents query independently, so their counts can legitimately differ. The
**lower** is used, and a divergence beyond 2x gates as
`ApprovalReason.CONTRADICTION_UNRESOLVED` — two agents disagreeing about how much
evidence exists have not converged, whatever they say about the figures.

### Independence is a spectrum

A second call to the *same* model varies by sampling: different wording, a
different path, sometimes a different answer. It does not vary in weights,
training, or alignment, so it shares the systematic blind spots. It is a second
pass by one expert, not a second expert.

| Level | When | Ceiling |
|---|---|---|
| `NONE` | the same model served both agents | 0.50 |
| `PARTIAL` | same family, different model | 0.85 |
| `FULL` | different model families | 1.00 |

This replaced a boolean. The boolean was wrong in both directions: it treated
Opus checking Sonnet as no independence at all — gating **every** premium run,
the tier customers pay for — while treating any family difference as complete
independence.

Independence is graded against `usage.model` on what actually executed, never
against the routing table, because fallback can collapse a chain onto one
provider without anything else noticing.

## What the live runs established

Five recordings sit in `evals/cassettes/`, replayable offline at no cost. They
are the evidence for this ADR rather than an illustration of it.

| Cassette | Outcome | Bound that applied |
|---|---|---|
| `free_tier` | gates at 0.50 | none — Gemini's own |
| `free_collapsed` | gates at 0.20 | none — after a failed recheck and one retry |
| `premium_tier` | gates at 0.55 | none — Claude's own |
| `na_growth_free` | gates at 0.95 | none — **sample divergence**, 300 against 104 |
| `na_growth_premium` | **publishes at 0.85** | `capped_independence_partial` |

### Three findings worth stating plainly

**The free tier can reach stronger independence than premium.** Its chains cross
labs by construction — Gemini analysing, Nemotron checking, `FULL` — while
premium runs Sonnet checked by Opus, one lab, `PARTIAL`. Premium buys privacy and
capability, not independence. A cross-vendor Evaluator on premium would fix it
and has not been built.

**The ceilings mostly no longer bind.** Both planning prompts now ask for a count
measure where the catalog offers one, so the agents see the sample in their own
results. Gemini reports 0.50 unaided on the eight-order question where it once
reported 0.95, and Claude 0.55. The bounds have become a backstop rather than a
daily correction, which is the outcome to want — but it means
`capped_sample_size` can no longer be demonstrated against a live model on this
data, and is proven only by unit test. Manufacturing an overconfident run to
exercise it would defeat the purpose.

**Gating is not a failure mode.** `na_growth_free` reaches the correct answer at
0.95 with `FULL` independence and still refuses to publish, because the two
agents reported 300 records against 104 from queries identical in scope. One
miscounted its own result. `na_growth_premium` on the same data has both agents
counting 300, and publishes. The gate discriminates by model quality on identical
evidence, which is precisely what it is for.

## Consequences

The bands are starting values, documented as such, and are the natural home for
tenant configuration later. They are deliberately **not** tuned to make any
particular run publish: when the eight-order scenario proved unable to clear the
threshold at all, the dataset was extended rather than the ceilings moved.

Confidence now depends on `sample_size` arriving. A provider that ignores the
required field, or a catalog with no count measure, both produce a reported zero
— which floors the ceiling at 0.50 and gates. That is the safe direction, and it
happened once already: on the first recording both agents honestly reported zero,
because their query returned totals and nothing counting the records beneath
them.

Statistical significance is out of scope. This is a sample-size bound, not a
p-value; that is the Statistician agent's work.
