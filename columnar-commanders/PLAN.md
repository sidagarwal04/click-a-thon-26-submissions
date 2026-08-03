# Hackathon Plan — atlys-PrismCH

**Budget:** 12–24 hours · **Team:** 2 · **Bias:** unseen-spec readiness first

Hours below are relative (`H+0` = when you start). Adjust the drop time once it
is announced at kickoff — everything after Phase 3 anchors to it, not to H+0.

---

## The strategic bet

Spec 6 carries the most weight, and every team gets it simultaneously, so
outputs are directly comparable. That makes **generalization the product** and
everything else supporting evidence.

Two rules fall out of it, and they drive the whole schedule:

1. **Thin end-to-end before deep anywhere.** A working spec → schema → insight →
   trace loop at hour 5, however shallow, beats three excellent agents that have
   never run as a pipeline. You cannot rehearse what does not connect.
2. **No agent code may reference a specific spec.** Not a table name, not a
   branch, not a prompt example naming a known feature. Held-out rehearsal is
   how we prove it (Phase 3).

At this budget the failure mode is not "we ran out of features." It is "the
pipeline half-worked and we had no time to fix it." Sequence accordingly.

---

## Track split

Two tracks, one integration point per phase. **Agree the contract in Phase 0 and
do not renegotiate it after Phase 2.**

| | **Track A** | **Track B** |
| --- | --- | --- |
| Owns | Instrumentation Agent, schema quality, DDL execution | Context layer, Analytics Agent, insight quality |
| Scores | Schema quality | Insight quality, context freshness |
| Also owns | Integration + the freeze protocol | Visualization CLI, submission writeup |

**The contract** (write it down at H+1, in code, as types):

- `ContextSnapshot`: `version`, `tables[]`, `metrics[]`, `entities[]`, `known_issues[]`
- `SpecInput`: raw spec text + optional raw event samples, split into
  `groups[]` — one `EventGroup` per user action the spec declares
- `SchemaProposal`: `ddl[]`, `decisions[]` (each with `why`), `mv_rationale`
- Context reads `MAX(version)`; every agent step passes `context_version` into
  the trace

Both tracks already have `agent_step()` / `Step.decision()` from
[prism_ch/tracing.py](prism_ch/tracing.py) — use them from the first commit, not
as a retrofit. Traces are a scored deliverable, not instrumentation debt.

---

## Instrumentation: one table per user action

**The spec decides how many tables exist; the data is correlated onto it.**
`spec.md` lists the raw events a feature emits under "User actions". Each one
becomes its own table, named exactly as the action — mirroring the eight
provided source tables, which are one-table-per-event joined on `user_id` /
`application_id`. A single `{feature}_events` table with an `event`
discriminator column would not match the shape the Analytics Agent already
knows how to query.

The pipeline, in order:

1. **Parse** the user actions out of `spec.md`. The section heading, the bullet
   shape, and the field carrying the action name are all discovered, never
   hardcoded — the sixth spec is unseen and must parse on the first try.
2. **Correlate** every record onto a declared action by matching that field.
   A declared action with no rows is kept as an empty group and reported; an
   event in the data the spec never declared gets no table and is reported.
   Deriving tables from the data instead would hide both.
3. **Flatten** nested objects into scalar columns (`payment` →
   `payment_amount`, `payment_currency`, `payment_latency_ms`). Per
   `schema-json-when-to-use`, the `JSON` type is reserved for genuinely
   dynamic shapes; a known fixed object belongs in typed columns.
4. **Sample per group, not per file.** ~15% of *each action's own rows*. A
   pooled sample gives the rarer actions a thinner profile than the common
   ones for no reason — `express_payment_confirmed` is 836 rows against
   `express_checkout_shown`'s 1,650.
5. **Design** all tables in one LLM call, so the shared envelope is typed
   consistently across them and a join never has to cast.
6. **Load every row** of each group into its own table. Sampling bounds what
   the LLM reads; it must never bound what reaches the database.

**Existing tables are widened, never replaced.** There is no overwrite path and
no prompt: `ALTER TABLE ADD COLUMN` reconciles a table that already exists, and
`Dialect` deliberately has no `drop_table` primitive at all. `ORDER BY`,
`PARTITION BY` and `TTL` are immutable after creation and are left alone. The
only safe direction for a table holding data is wider — and an unattended run
on the unseen spec has nobody present to answer a prompt anyway.

Every statement that reaches the server is captured and surfaced, including the
`ALTER`s the agent decides on by itself — those are the ones a reviewer most
needs to see.

---

## Timeline

| Phase | Hours | Track A | Track B | Exit criterion |
| --- | --- | --- | --- | --- |
| **0. Unblock** | H+0 → H+1.5 | Fix Cloud DDL dialect; load parquet | Bootstrap context from table introspection | `make trace-check` lands a trace from Cloud |
| **1. Thin path** | H+1.5 → H+5 | Instrumentation v1: spec → DDL → validate → **execute** | Context v1: versioned tables, `get_latest()`, base context ingested | One spec runs end to end, traced |
| **2. Depth** | H+5 → H+9 | Ordering keys, codecs, types, MV decision + rationale | Analytics v1: push-down SQL, 4 cuts, insight synthesis with *why* + confidence | Insights a PM would act on |
| **3. Rehearsal** | H+9 → H+12 | **Held-out spec, unattended, timed.** Both fix what breaks. | | Clean run, no manual steps, full trace |
| **4. Cheap wins** | H+12 → H+15 | Context contradiction + gap detection | Visualization CLI (3 commands) | Both demoable |
| **5. Freeze** | drop − 2h | No merges. Second timed rehearsal only. | | Pipeline frozen |
| **6. Spec 6** | drop | Run it. Capture `run_id`, DDL, insight summary, trace. | | Artifacts saved |
| **7. Submit** | +2h | Architecture + rationale writeup (D6, D7) | | Submitted |

Phase 3 is the most important block on this schedule. Protect it. If Phase 2
overruns, cut Phase 2 — not Phase 3.

---

## Phase notes

**Phase 0 — the two things that block everything else.**
The DDL dialect gap is first because it invalidates every rehearsal until fixed:
local emits `ON CLUSTER click_agents` + `ReplicatedMergeTree`, Cloud wants plain
`MergeTree` on SharedMergeTree with no cluster clause. One target flag, both
paths tested. Second, create a limited `agent` user on Cloud
(`max_result_rows`, `max_execution_time`, `max_memory_usage`) — that enforces
"aggregate in ClickHouse, interpret in the LLM" at the database instead of by
convention, and caps the blast radius of a bad generated query.

**Phase 1 — resist depth.** The instrumentation agent may produce mediocre
ordering keys at hour 5. Fine. It must *execute* DDL and *emit a trace*.

**Phase 2 — where the craft criteria are won.** Schema quality is judged on
ordering-key choice, partitioning, types, and whether MVs earn their keep — so
the rationale must reach the trace, not just the DDL. Insight quality needs the
*why*: cross-cut by default (device, geo, funnel stage, segment), because the
single-dimension read misses the iOS-in-one-region class of finding the brief
uses as its example.

**Phase 3 — hold out one of the 5 known specs** and run the pipeline against it
with no human in the loop, on Cloud, timed. This is the only honest test of
generalization, and it is where the real bugs surface. Budget the full 3 hours;
you will use them.

**Phase 4 — the two highest-visibility-per-hour items left.** Contradiction
detection is roughly one query plus one LLM pass, and the base context is
flawed *on purpose*, so finding a seeded contradiction is a demonstrable win.
Visualization is three CLI commands reading tables you already have —
`schema-history`, `insights`, `context-diff`. Structured CLI is explicitly
acceptable; do not build a dashboard.

**Phase 5 — the freeze is a hard rule.** A pipeline edited after its last
rehearsal has not been rehearsed. Two hours before the drop: no merges, no
prompt tweaks, no "quick fixes."

**Phase 6 — capture provenance immediately.** `run_id`, generated DDL, insight
summary, trace link, saved to the repo the moment the run finishes. The insight
summary is written **for a product audience** — that is an explicit requirement,
and it is the artifact judges read first.

---

## Explicitly cut

Naming these now prevents relitigating them at hour 14.

| Cut | Why |
| --- | --- |
| Correlation analysis (A6) | Lowest insight-per-hour of the analysis types |
| Sophisticated anomaly detection | A simple threshold or z-score reads the same to a PM |
| Materialized views unless clearly warranted | An MV that does not earn its keep scores *worse* than none |
| Any web dashboard | Out of scope per the brief; CLI is accepted |
| LibreChat demo polish | Removed — its MCP client could not connect (v0.8.7 bug); was a bonus surface, not a deliverable |
| LangGraph / cognee / vector stores | Framework time is not scored; see the tracker's Open Questions |
| Episodic retrieval infrastructure | At n≈6, load all prior decisions as few-shot instead |

---

## Standing risks

| Risk | Mitigation |
| --- | --- |
| Spec-6 output has no valid trace | Trace from the first commit; `make trace-check` before the drop |
| Pipeline overfits the 5 known specs | Held-out rehearsal in Phase 3; no spec names in agent code |
| Cloud DDL dialect differs from local | Fixed in Phase 0; rehearse on Cloud, never only locally |
| Analytics pulls raw rows, burns tokens | DB-level limits on the `agent` user |
| Late edits break the frozen pipeline | Hard freeze at drop − 2h |
| Two tracks diverge on interfaces | Contract fixed at H+1, frozen after Phase 2 |

---

## Open assumption

You have parquet data for the 8 tables. If the **5 feature specs** or the
**base context layer** are not yet in hand, Phase 0's context bootstrap covers
the gap — the Context Agent derives an initial context layer from table
introspection, which is work you need regardless. When the real base context
arrives, it merges in as a new version, and the diff between the two becomes
free evidence for the context-changelog requirement.
