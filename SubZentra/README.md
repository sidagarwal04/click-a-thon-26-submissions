# ZentraOS — SubZentra

**Track:** Atlys — *"From feature spec to insight: agents that instrument, analyze, and explain."*

**Demo:** [hosted demo link — TODO]
**Video (2–3 min):** [Loom walkthrough](https://www.loom.com/share/eeb86c5957bd4d5ea86b71d31d3db0f7)
**Pitch deck:** [ZentraOS-SubZentra-PitchDeck.pdf](./ZentraOS-SubZentra-PitchDeck.pdf)

---

## What we built

ZentraOS is a trust-first analytics system that turns a connected ClickHouse
source into a governed, queryable semantic layer — automatically — and then
answers real business questions over it through a multi-agent investigation
pipeline that shows its work.

Point it at a ClickHouse Cloud source and it:

1. **Harvests the schema** — profiles every table, column, type, cardinality,
   and null rate, with zero manual mapping.
2. **Compiles a governed semantic layer on top of it, live** — every harvested
   table becomes a queryable cube with typed measures and dimensions, computed
   fresh per tenant and per connection. No feature spec, no config file, no
   migration: connect a source and it's immediately analyzable.
3. **Runs a governed, multi-agent investigation over it** — an Orchestrator
   plans the question, a Cube Analyst queries the governed catalog (never raw
   SQL against untrusted input), an Evaluator independently re-derives the
   same number before anyone sees it, and an Insight agent turns the validated
   result into a claim-by-claim finding — every figure traceable back to the
   query that produced it.
4. **Refuses to guess.** A claim the Evaluator can't reproduce fails closed. A
   confidence below the tenant's threshold — or a recheck that never
   converges — opens a human approval gate instead of shipping an answer
   nobody signed off on.

This is the "Analytics Agent" half of the track's brief, built for real:
governed, evidence-backed, and running against an actual ClickHouse Cloud
funnel dataset (application_started → auth_completed → purchase_completed and
five supporting event tables), not a toy demo schema.

## Why this is a strong entry

- **The catalog is discovered, not declared.** Most "agent + warehouse" demos
  hand the model a hand-written schema file. Ours compiles the semantic layer
  from whatever's actually in ClickHouse, per tenant, at query time — connect
  a different source and the agent reasons over a completely different
  catalog with no code change.
- **Every answer is auditable.** Metrics, queries, and confidence scores are
  persisted per agent execution with token/cost/model attribution, so any
  published finding can be traced back to exactly what ran and what data it
  touched.
- **The independence check is real, not cosmetic.** The Evaluator never sees
  the Analyst's query — only its reported figures — and has to rebuild the
  answer from scratch. Disagreement fails the finding rather than being
  smoothed over.
- **Multi-tenant by construction.** Postgres row-level security enforces
  tenant isolation on every governed table; a tenant's Data Connection and
  model routing are resolved per request, never hardcoded.
- **Tuned for production economics, not just a demo run.** Per-role model
  routing puts the strongest available model (Claude Sonnet 5) on planning
  and analysis — the steps that actually produce the figures — and a fast,
  cheap model on lighter classification/recheck/prose steps, with temperature
  fixed low for repeatable output. Free-tier tenants get a fully-free
  multi-provider fallback chain (Gemini → NVIDIA → Groq → Cerebras →
  OpenRouter) with Anthropic only as the paid backstop.
- **Governed, not just prompted.** The agent structurally cannot invent a
  metric that isn't in the catalog — a hallucinated field name is refused
  before a query ever runs, not caught after the fact.

## Architecture

```
                        ┌─────────────────────────┐
  ClickHouse Cloud  ──▶ │  Connector + Harvester   │  profiles tables, columns,
  (customer source)     └───────────┬─────────────┘  cardinality, null rate
                                     ▼
                        ┌─────────────────────────┐
                        │  Cube semantic layer     │  compiles a governed cube
                        │  (per tenant + source)   │  per table, live, on request
                        └───────────┬─────────────┘
                                     ▼
   ┌───────────────────────────────────────────────────────────────────┐
   │                     Investigation pipeline                        │
   │                                                                   │
   │   Orchestrator ──▶ Cube Analyst ──▶ Evaluator ──▶ Insight          │
   │   (plans the       (queries the     (independently   (drafts a    │
   │    question)         governed        re-derives it     claim-by-  │
   │                       catalog)        blind to the      claim     │
   │                                       Analyst's         finding)  │
   │                                       query)                      │
   │                                                                   │
   │   Confidence below threshold, or a recheck that never converges,  │
   │   opens a Human Approval gate — the pipeline stops rather than    │
   │   publishing a number nobody signed off on.                       │
   └───────────────────────────────────────────────────────────────────┘
```

Every step above is persisted as its own Agent Execution record — role,
model, provider, token counts, cost, latency, confidence, and the exact query
run — so a published finding has a full, queryable audit trail.

## Try it against the probe set

The pipeline is built to take exactly this kind of open-ended question and
turn it into a governed, evidence-backed answer over the connected funnel
data:

1. *"Analyze the existing funnel and surface the most important issues, with the why."*
2. *"Where are we losing conversions, and for which segments (device / geo / destination)?"*
3. *"Are there any regressions or trends over the last quarter?"*
4. *"Is anything in the base context wrong, stale, or self-contradictory?"*

See [`RUN.md`](./RUN.md) to run these yourself against a live instance.

## Stack

- **Data:** ClickHouse Cloud (connected customer source), Postgres (control
  plane, tenant isolation via RLS)
- **Semantic layer:** Cube, compiled dynamically per tenant/connection
- **Agents:** LangGraph-style tool-calling loop over a governed
  catalog-search + query tool
- **Models:** Claude Sonnet 5 (planning + analysis), Claude Haiku
  (classification/recheck/prose), with a free-tier multi-provider fallback
  chain for cost-sensitive tenants
- **API:** FastAPI, async SQLAlchemy
- **Frontend:** React + Vite, Clerk auth, Thesys C1 for generative visualization

## Team

**SubZentra**
