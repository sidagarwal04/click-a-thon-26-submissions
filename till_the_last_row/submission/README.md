# Atlys Track — Submission (team: till_the_last_row)

*"From feature spec to insight: agents that instrument, analyze, and explain."*

This folder collects the graded evidence for the Atlys track, mapped 1:1 to
[`../SUBMISSION_GUIDELINES.md`](../SUBMISSION_GUIDELINES.md).

## Submission map

| Guideline item | Where |
| --- | --- |
| **1. Code + how to run** | [`../RUN.md`](../RUN.md) (env, CH connection, one-command pipeline). Agents in [`../agents/`](../agents/), skills in [`../librechat/skill/`](../librechat/skill/), stack in [`../librechat/`](../librechat/). |
| **2. Architecture** | [`../ARCHITECTURE.md`](../ARCHITECTURE.md) — 3 agents + Subagent handoffs, where context is stored (+ why), Langfuse wiring, LLM choice. |
| **3a. Generated DDL (5 known + 6th)** | [`ddl/`](ddl/) — `.sql` + `.metrics.json` per spec. |
| **3b. Analytics report over 8 existing tables** | [`probe-outputs/`](probe-outputs/) — the autonomous run + the 4 standard probes. |
| **3c. Context layer + before/after changelog** | [`context-freshness/`](context-freshness/) — bundle snapshot + `CONTEXT_FRESHNESS.md` proof. |
| **3d. 6th-spec bundle** | [`unseen-6th-spec/`](unseen-6th-spec/) — schema + insights + trace link. |
| **4. Langfuse trace links** | [`TRACES.md`](TRACES.md) — per-agent + the **mandatory 6th-spec** chain trace. |

## The pipeline in one line

A feature spec is dropped on the **Instrumentation Agent**, which designs + validates +
applies the ClickHouse schema, pushes it, then calls the **Context Agent** (refresh the
living context) and the **Analytics Agent** (produce PM-ready insights + `insights.json`)
as **subagents** — one traceable run: **spec → schema → context → insight**. See
[`../ARCHITECTURE.md`](../ARCHITECTURE.md).

## Status checklist

- [x] Instrumentation Agent (`agents/instrumentation/`)
- [x] Analytics Agent (`agents/analytics/`)
- [x] Context Agent (`agents/context/`)
- [x] 6th-spec schema + insights (`unseen-6th-spec/`)
- [x] Living context bundle + changelog (`context-freshness/`)
- [x] **Generated DDL for all 5 known feature specs** — the "5 known new feature specs" are
  `01_express_checkout`, `02_group_family`, `03_status_sharing`,
  `04_abandoned_checkout_recovery`, `05_instant_forex`. **Currently only `01` is done.**
  Run the pipeline on `02`–`05` to complete item 3a. (Specs 07–11 DDL is also present — bonus,
  those are existing-table event specs.)
- [x] **Langfuse trace links pasted** (`TRACES.md`) 
- [x] **8-table autonomous report + 4 probe outputs** (`probe-outputs/`) 
