---
id: adr-0009
title: Route model providers by tenant tier, with privacy as the paid guarantee
type: adr
status: active
owner: unassigned
source: decision
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
priority: high
tags: [adr, agent-execution, providers, privacy]
related: ["[[Decisions MOC]]", "[[Agent Execution Domain]]", "[[Trust and Verification]]"]
repo_path: docs/adr/0009-tiered-model-provider-routing.md
code_refs:
  - libs/adapters/model-providers/src/zentra_adapter_model_providers/routing.py
  - libs/adapters/model-providers/src/zentra_adapter_model_providers/router.py
---

# Route model providers by tenant tier, with privacy as the paid guarantee

Agents address a role, never a model. An ordered chain per tenant tier and agent
role decides which provider serves it, falling through on rate limits, outages,
and schema violations.

Free tenants run on free inference, including **Gemini and OpenRouter, which
train on the traffic they receive**. Premium tenants never touch a provider that
trains: that is the guarantee they are paying for, and it is asserted at import
rather than left to review.

## Selection is evidence-led

Providers were filtered on structured-output support before quality: an agent
that receives a schema violation fails hard, so a provider without constrained
decoding is unusable however capable. Mistral was rejected on that basis despite
offering the largest free quota available.

Model order within each chain follows the Artificial Analysis Intelligence
Index, not vendor-reported benchmarks, which disagreed with independent
evaluation by wide margins.

Because the Index moves, the table is expected to be revisited rather than
treated as settled. It already has been once: the first free chains shipped with
`gemini-3-flash` (38) and led the Evaluator with a model Cerebras had scheduled
for deprecation. They now lead with `gemini-3.6-flash` (50) and carry Nemotron 3
Ultra (38) as the second rung.

A provider whose strict-schema support is unverified is never placed first in a
chain, because a retry-and-fall-through would then sit on the critical path of
every investigation. Nemotron is there today; a live call proving strict
`json_schema` promotes it.

## The Evaluator's independence is checked at runtime

The free chains start the SQL Analyst and the Evaluator on different vendors and
model families, so the recheck stays independent at no cost. Fallback can still
collapse them onto the same model, so the check runs against `usage.model` on
what actually executed. When the families match, the Evaluator's confidence is
capped below the tenant threshold and the investigation cannot auto-publish.

That is honest rather than a warning label: a recheck that shares the analysis's
blind spots is worth less, so it is scored as worth less.

## Costs

Free-tier inference is materially weaker than Anthropic — roughly 72% of Claude
Sonnet 5 on the best free model, and under half on the weakest rung. The
always-gate behaviour and the Anthropic backstop at the end of every chain are
what make that acceptable.

Free-tier traffic being training-visible is a deliberate product decision, not an
oversight. It requires disclosure before any real customer data reaches the free
path; see the sub-processor list.

Parent: [[Decisions MOC]]
