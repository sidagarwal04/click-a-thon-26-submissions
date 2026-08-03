---
id: runbook-record-replay-agent-runs
title: Record and Replay Agent Runs
type: runbook
status: active
owner: unassigned
source: repository
created: 2026-07-30
updated: 2026-07-30
reviewed: 2026-07-30
confidence: verified
implementation: current
priority: high
tags: [runbook, agents, evals, cost]
related: ["[[Runbooks MOC]]", "[[adr/0010-confidence-bounded-by-evidence]]", "[[Agent Execution Domain]]"]
repo_path: tools/evals/live_run.py
code_refs:
  - tools/evals/live_run.py
  - libs/adapters/model-providers/src/zentra_adapter_model_providers/cassette.py
  - evals/project.json
---

# Record and Replay Agent Runs

A cassette is one live run's model responses, committed under
`evals/cassettes/<name>/`, plus an `expect.json` stating what the pipeline
decided. Replaying serves those responses through the real graph, the real
confidence bounds, and the real database — without calling a provider.

One paid run becomes a permanent regression fixture. This is what makes it
possible to change calibration and re-verify against real model output for
nothing.

## Which command costs money

| Command | Providers called | Cost |
| --- | --- | --- |
| `--replay <name>` | none | **$0** |
| `--record <name>` | yes | real, and premium is Anthropic |

`--replay` reads the tier and withheld providers from the cassette, so it takes
no other flags. `--tier` defaults to `free` so premium spend is always something
you typed.

```bash
npm exec -- nx run evals:replay          # every cassette, $0
uv run python tools/evals/live_run.py --replay na_growth_premium
```

## Recording

Free recordings withhold the paid rungs, so a degraded chain fails loudly
instead of quietly falling through to Anthropic:

```bash
uv run python tools/evals/live_run.py --record free_tier \
  --without anthropic --without openai
```

This is not optional hygiene. Before the flag existed, a free-tier run reached
Opus through the fallback chain and spent $0.08 while every visible signal said
"free tier".

`--without <provider>` is repeatable and also shapes the chain deliberately:
leaving only NVIDIA reachable reproduces one model checking its own work, which
is how the `capped_independence_none` cassettes are made.

Premium requires the flag and the intent:

```bash
uv run python tools/evals/live_run.py --record premium_tier --tier premium
```

`--record` writes `expect.json` from what actually happened. Read it, add a
`note` explaining what the recording demonstrates, and commit both.

## When replay fails

**`UnrecordedRequestError`** means the prompt changed. Cassettes key on a hash of
the model, system prompt, messages, and schema, so editing `prompts.py`, the
output schemas, or anything that changes `render_catalog` invalidates every
recording. It has happened once on this branch: adding dimension values to the
catalog changed the Analyst's prompt and all five cassettes had to be re-made.

Re-record the free ones first — they cost nothing and will catch a mistake before
a premium run pays for it.

**A `MISMATCH` line** means the pipeline reached a different decision from the
same model output. That is the alarm the cassettes exist for: calibration,
gating, or independence grading changed behaviour. Read which field diverged
before assuming the expectation is stale.

**Contamination.** The cassettes contain query results, so changing the warehouse
seed can invalidate them too. New seed data must be disjoint from the slices the
existing scenarios query. `nx run evals:replay` is the check — run it after any
seed change.

## What the cassettes hold

`requested_model`, response text, token counts, cost, and the fall-through trail.
No prompts, no keys, no customer data — the runs are over synthetic seed data, so
they belong in the repository.

Replay reports **zero cost** regardless of what the recording cost, because no
provider was called. The pipeline writes that figure into `agent_executions`,
which is what cost governance reads; carrying the recorded cost through meant
verifying a change booked a premium run's spend again on every replay.

Parent: [[Runbooks MOC]]
