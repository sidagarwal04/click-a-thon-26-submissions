---
id: reference-model-subprocessors
title: Model Provider Sub-Processors
type: reference
status: active
owner: unassigned
source: repository
created: 2026-07-29
updated: 2026-07-29
reviewed: 2026-07-29
confidence: verified
implementation: current
priority: high
tags: [operations, providers, privacy, compliance]
related: ["[[Operations MOC]]", "[[adr/0009-tiered-model-provider-routing]]"]
repo_path: libs/adapters/model-providers
code_refs:
  - libs/adapters/model-providers/src/zentra_adapter_model_providers/providers.py
  - libs/adapters/model-providers/src/zentra_adapter_model_providers/routing.py
---

# Model Provider Sub-Processors

Every provider an Investigation may reach, and what each does with what it
receives. The SQL Analyst sends governed query **result rows** to the model, so
this list is the set of parties that can see tenant data.

Thesys is a terminal presentation sub-processor, not an analytical provider. It
receives only the strict `VisualizationBriefV1` after publication and no raw
rows, SQL, credentials, prompts, or reasoning. The adapter uses the pinned C1
model/version documented in [[adr/0020-thesys-terminal-presentation]].

## Premium tier

None of these train on inference data. This is the guarantee premium tenants
buy, and `routing.py` refuses at import to place a training provider in a paid
chain.

| Provider | Role | Data handling |
| --- | --- | --- |
| Anthropic | Primary for every role | No training on API data by default |
| OpenAI | Second rung | No training on API data by default |
| Cerebras | Later rung | Does not retain inputs or outputs |
| Groq | Later rung | Contractually barred from training; no default retention; Zero Data Retention available |

## Free tier

The first two are the same no-training providers. **The last two train on the
traffic they receive.**

| Provider | Role | Data handling |
| --- | --- | --- |
| **Gemini** | **Analyst and Orchestrator primary** | **Free-tier content is used to improve Google's products. Paid-tier API data is not** |
| **NVIDIA** | **Evaluator second; Analyst second** | **Inputs and outputs on free endpoints are recorded and used to train NVIDIA's models. NVIDIA warns against sending personal data. Only self-hosted NIM avoids this.** |
| Cerebras | Evaluator primary | Does not retain inputs or outputs |
| Groq | Later rung | Contractually barred from training |
| **OpenRouter** | Later rung | **Free model access is exchanged for traffic becoming training signal** |
| Anthropic | Final backstop | No training on API data |

⚠️ **Cerebras deprecates `zai-glm-4.7` on 2026-08-17.** It is currently the
Evaluator's primary rung. Fallback will absorb its removal silently rather than
raise, so this needs a replacement chosen before that date — either GLM-5.2 on a
paid provider, or whatever Cerebras ships next.

## What this requires

Today the only dataset is the synthetic commerce seed, so nothing a real person
would recognise reaches a training provider. That changes the moment a tenant
connects a real warehouse.

## The key class decides, and the code cannot see it

The same provider trains or does not train depending on which key a deployment
holds. This one runs a **paid** Gemini key, which Google does not train on — but
`trains_on_input` stays `True` for Gemini regardless, because nothing in the
process can tell the key classes apart and privacy takes the pessimistic
reading. `_assert_premium_never_trains()` therefore still keeps Gemini out of
every premium chain. Moving it in on the strength of a paid key is a deliberate
decision that has to revisit that flag first.

## The free tier's independence has a daily cap

Gemini's free API tier allows 20 requests a day — roughly three investigations.
Past that the chain falls through to the next rung, and because the Analyst and
Evaluator chains overlap below Gemini, both agents land on the same provider:
the recheck collapses from `FULL` independence to `NONE` and confidence is
capped at 0.50. Observed live on 2026-07-29.

The fall-through trail is recorded on every successful call and carried into the
audit ledger, so this degradation is visible in Replay rather than inferred from
a confidence score that quietly dropped.

Before the first real connector ships to a free tenant:

- State plainly, at the point of connecting data, that free-tier analysis is
  processed by providers who may train on it.
- Publish this list where a prospective tenant can read it before connecting.
- Offer the premium tier as the private path, since that is what distinguishes
  it.

A tenant subject to GDPR is the controller for the data they connect. They can
only be assumed to have instructed this processing if they were told about it.

Parent: [[Operations MOC]]
