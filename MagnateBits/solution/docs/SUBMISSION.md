# Atlys track — submission status

Maps our work to the four required evidence items in
[`ATLYS_SUBMISSION_GUIDELINES.md`](https://github.com/sidagarwal04/click-a-thon-26-submissions/blob/main/ATLYS_SUBMISSION_GUIDELINES.md),
with an honest status per item. Rubric weights, for prioritising what's left:
**ClickHouse & OSS 25% · Problem Fit 20% · Technical Implementation 20% ·
Innovation 20% · Scalability & Impact 10% · Presentation 5%.**

> **Read this first — the gap.** One required item remains: we run **local Docker
> ClickHouse, not ClickHouse Cloud**. It is in [§6](#6-what-is-missing) with what it
> needs. Nothing below claims evidence we do not have.

---

## Status at a glance

| # | Required evidence | Status |
|---|---|---|
| 1 | Code + `RUN.md` (env vars, ClickHouse Cloud conn, one command) | ⚠️ [`RUN.md`](../RUN.md) ✅ (local); **ClickHouse Cloud not used** |
| 2 | Architecture (agents, context layer + why, tracing, LLM providers) | ✅ [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| 3a | Generated DDL, 5 known specs **and** the 6th | ✅ all six |
| 3b | Analytics insight report **over the 8 existing tables** (autonomous) | ✅ `probe.py` → `out/probe/PROBE_RESULTS.md` |
| 3c | Context layer + before/after changelog (freshness proof) | ✅ versioned, v1→v19 |
| 3d | 6th-spec bundle: schema + insight summary + trace | ✅ run `29b74c8f` |
| 4 | Langfuse trace links, 6th-spec trace **mandatory** | ✅ working links |
| — | Standard probe set (4 prompts vs existing tables) + traces | ✅ all 4 run, 73/73 figures grounded, traced |

---

## 1. Code and how to run it

Repo: `Atlys/solution/`. One command, from a clean clone:

```bash
make init     # venv + deps, git-lfs pull, ClickHouse up, 8 tables loaded,
              # context bootstrapped, stack smoke-tested, 241 tests
```

Then the pipeline end to end:

```bash
./.venv/bin/python run_pipeline.py \
    --spec   ../specs/06_unseen/spec.md \
    --events ../specs/06_unseen/events.ndjson --rebuild
```

It **pauses for schema approval** before executing any DDL (`--yes` to skip; a
non-interactive caller polls the `pipeline_approvals` table instead). Setup detail and
the manual step-by-step equivalent are in [`../README.md`](../README.md).

**Env vars** — see [`../.env.example`](../.env.example). The ones that matter:

| Var | Purpose |
|---|---|
| `CH_HOST` / `CH_PORT` / `CH_USER` / `CH_PASSWORD` / `CH_DATABASE` / `CH_SECURE` | ClickHouse. All `os.getenv`-driven in `ch.py`; nothing hardcodes localhost, so pointing at Cloud is env-only. |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` | Tracing. Region matters — a US project 401s against the EU default. |
| `ATLYS_LLM_BACKEND` | `cli` (Claude subscription, default) · `api` (Anthropic SDK) · `mock` (offline, zero credentials) |
| `ATLYS_CONTEXT_RETRIEVAL` | `vector` (default, ranked) · `full` (dump whole layer) |

⚠️ **One gap here** — [`RUN.md`](../RUN.md) now exists and covers prerequisites, every
env var, the one command, verification and troubleshooting, but **we run local Docker
ClickHouse, not ClickHouse Cloud**. `load.sh` already targets Cloud with `--secure`, and every
connection parameter is env-driven, so the migration is configuration rather than
code — but it has not been done or tested.

## 2. Architecture

Full write-up: [`ARCHITECTURE.md`](ARCHITECTURE.md) (data-flow diagram + module map).
Summary of what the guidelines specifically ask for:

**The three agents and their handoff** — `run_pipeline.py` runs five stages in one
trace: `context.load` → `instrumentation` → `context.reconcile` → `analytics` →
`report`. Instrumentation profiles the raw events deterministically, proposes DDL
(LLM), lints and dry-runs it, waits for human approval, then executes and loads.
Context reconciles the new table and runs contradiction checks. Analytics plans
queries from a template catalog, executes them in ClickHouse, and interprets only the
aggregates. The seam between them is `FeatureSemantics` — every template is
parameterised by it and never by a feature name, which is what lets an unseen spec run
with zero new code.

**Where the context layer lives, and why — a ClickHouse table, not a vector store.**
`context_entry_log` (append-only, versioned) + a `context_current` view. Rationale
(also in `contextlayer/schema.sql`'s header): contradiction detection becomes
deterministic SQL because the context sits in the same engine as `system.columns`, so
"the docs claim column X exists" is settled by a query returning 0 rows rather than by
an LLM opinion; versioning, diffs and changelog come free from an append-only log;
and each entry carries the `run_id` that links it to its trace.

We *also* ship optional in-ClickHouse vector retrieval (`vector_rag.py`,
`cosineDistance` + an HNSW `vector_similarity` index + a text index) — now the default,
because the layer grew to ~460 entries, past what belongs in every prompt. The
embedding is a deterministic local hashing function, so *which* entries were retrieved
stays reproducible and auditable. Still no external vector DB.

**Langfuse** — `tracing.py` is the only module importing Langfuse. One trace per run;
spans mirror the pipeline stages. The mechanism that matters:
`llm.complete_json(..., context_version=...)` takes `context_version` as a **mandatory**
argument, so no traced LLM call can exist without recording which context snapshot fed
it. That makes context-freshness checkable rather than asserted.

**LibreChat + MCP** — `atlys_mcp/` exposes 8 tools (`ask`, `list_features`,
`explain_metric`, `list_contradictions`, `context_diff`, `get_context`,
`diagnose_segments`, `run_pipeline`), all tagged with native `ToolAnnotations` so a
host can distinguish reads from writes; `run_pipeline` additionally requires
`confirm=true` server-side. LibreChat is wired to it plus the `mcp-clickhouse` server
(`deploy/`).

**ClickStack — not integrated.** Optional per the guidelines.

**LLM providers** — Claude Sonnet 5 via the authenticated `claude -p` CLI
(subscription auth, no API key) for all three agent LLM calls; Anthropic SDK as an
env-flip alternative; a deterministic offline mock for eval; Ollama Cloud for the
LibreChat *chat* surface only (tool calls always go to Claude).

## 3. Graded outputs

### 3a. Generated DDL — all six specs ✅

Every run writes `artifacts/runs/<run_id>/`: `schema.sql`, `proposal.json` (DDL plus a
rationale per decision), `semantics.json`, `insight_report.md`, `context_diff.md`,
`trace_url.txt`.

| Spec | Latest run |
|---|---|
| 01 express_checkout | `95c7559c90b7` |
| 02 group_family | `e0e83851c608` |
| 03 status_sharing | `84d55343f482` |
| 04 abandoned_checkout_recovery | `59e10a11574d` |
| 05 instant_forex | `9c9e08fe4c85` |
| **06 unseen (sealed)** | **`29b74c8f`** |

Schema quality worth pointing a judge at: `id` typed `String` with a comment
explaining the 32-char-hex trap (the legacy tables' `UUID` would reject it), money as
`Decimal(18,4)` not Float, `LowCardinality` on enums, **no `Nullable` anywhere**, and
`ORDER BY (event, timestamp, <entity_key>)` — never id-first, which is the documented
anti-pattern in the legacy tables. MVs are kept or dropped on a **measured** reduction
factor; [`SCHEMA_CATALOG.md`](SCHEMA_CATALOG.md) lists every MV that was proposed, built,
measured and **rejected**, each with the ratio that killed it (all under the 5x bar).

### 3b. Insight report over the 8 existing tables ✅ + the standard probe set ✅

`python probe.py` runs the Analytics Agent with the 8 production tables as its
**subject**, and answers the four standard prompts verbatim. Output:
`out/probe/PROBE_RESULTS.md` (+ `.json`), one Langfuse trace per prompt.

**How, without a second codebase.** The 8 tables are one-table-per-event; every
template expects one table with an `event` discriminator. Rather than write parallel
templates, `probe.py` builds a `base_events` view over their **30 genuinely-shared
envelope columns** (computed at runtime, so a schema change alters the view instead of
breaking it) — 2,479,858 rows. All 22 templates, the confidence scoring, the numeric
grounding and the metric policy then apply unchanged, so these answers come from the
same machinery as the feature-spec answers.

**Result:** 4/4 answered, **73/73 asserted figures grounded** against their cited
queries, ~235M rows scanned per prompt, confidence 0.62–0.78.

| # | Prompt | Grounded | Conf |
|---|---|---|---|
| 1 | Funnel issues, with the why | 20/20 | 0.78 |
| 2 | Where are we losing conversions, by segment | 32/32 | 0.72 |
| 3 | Regressions or trends over the last quarter | 15/15 | 0.62 |
| 4 | Is the base context wrong/stale/self-contradictory | 6/6 | 0.75 |

Headline findings: the two dominant leaks are `auth_completed` (13.1% through-rate,
86.9% drop) and `document_uploaded` (12.6%, 87.4% drop), both **uniform across every
device/OS/geo cut** (12.7–14.2% and 11.7–13.9%) — structural, not segment-specific —
with the longest step gap in the funnel (median ~1.9h) sitting exactly before document
upload. Probe 4 found a genuine stale-context item: the business-overview diagram
states a 4-step funnel while the instrumented reality is 8 steps.

**Three bugs this exercise surfaced**, recorded because they are the interesting part:
- `t10_data_quality` failed outright — the legacy tables type `id` as `UUID`, but every
  template guards identity columns with `!= ''`, which ClickHouse cannot evaluate
  against a UUID. Fixed by projecting UUIDs as String in the view, which is also the
  rule our generated schemas already follow.
- **The funnel order was hardcoded from the documented product funnel, and the data
  contradicted it.** Of the 299,659 users with both, `search_typed` precedes
  `landing_page_scrolled` in 299,659 cases and follows it in **zero**. Every
  `windowFunnel` then reported 0 entities past step 1 — which reads as catastrophic
  drop-off rather than a wrong assumption. Now derived by pairwise per-entity timestamp
  precedence (Copeland), the same signal `profile.py` uses for a feature spec.
- The first probe run **correctly refused to analyse the broken funnel**, reporting it
  as "a broken step-chaining computation ... despite raw event volume being present"
  instead of inventing numbers over it. Probe 4 then independently corroborated the
  corrected 8-step order against the context layer.

### 3c. Context layer + before/after changelog ✅

`out/context/CHANGELOG.md` records every layer version with its snapshot id, entry
count, schema fingerprint and `run_id` — **v1 through v19** (the layer version in
`context_snapshot`; `context_entry_log.version` is a separate per-entry revision
counter, currently max 4). Each run's `context_diff.md` shows
added/updated/superseded entries for that run.

**The freshness proof is mechanical, not narrative.** On the sealed-spec run the trace
shows `propose_ddl` consumed context **v18** and, after reconciliation added the new
table, `analytics.plan_queries` and `analytics.interpret` consumed **v19** — recorded
on the generations themselves, visible in the Langfuse trace and in the console's *Run
flow* page.

### 3d. Sealed 6th-spec bundle ✅

Run **`29b74c8fbaa94ab6ad7a18804951835e`** — all 5 stages ok, 192.4s, **5,363/5,363
rows loaded, 0 rejected**, 12 queries 0 failed, context v18→v19, 8 contradictions.

**Trace:** https://us.cloud.langfuse.com/project/cmsa37gfi164uad0dvkq6ygqo/traces/1e202f5aab976efd00e4b8311a25be47 *(verified HTTP 200)*

The spec's own branching shape was handled without per-spec code: `coupon_applied` and
`coupon_rejected` are mutually exclusive (measured: **zero** entities have both), so
`coupon_rejected` is excluded from the ordered funnel while remaining in the schema and
queryable. Without that, `windowFunnel` forces every step after it to zero — which
reads as a catastrophic drop-off rather than a modelling error.

**Honest note on two of the five findings.** `EXPIRED5 has a 0% apply rate despite 140
users entering it` is real and is the standout. But the Desktop coupon-apply gap
(34.3% vs 54.2%) and the discount↔completion correlation (r=0.22) are **frame-specific**:
both are grounded in the `windowFunnel` frames they cite, yet on a looser scoping the
Desktop gap is not significant (60.3% vs 69.2%, p=0.12) and the correlation ranges from
−0.45 to +0.12 depending on the population. The agent hedged both ("hypothesis,
unverified", confidence 0.47 and lower), and our own Table 3 independently marks 2 of 5
findings **unverifiable** — the same two. Scope choice dominating an answer is a real
limitation, and we would rather state it than have a judge find it.

## 4. Langfuse trace links ✅

Every run writes `trace_url.txt` and a `trace_url` row in `pipeline_runs`; the console
renders the span tree natively (Langfuse sends `frame-ancestors 'none'`, so it cannot
be iframed — we pull the same data via its API and deep-link out).

⚠️ Every trace URL emitted before 2026-08-02 used a `/trace/<id>` route that **does not
exist** (307s and dead-ends). Fixed to `/project/<project_id>/traces/<id>`; the sealed
spec's artifacts were repaired and verified 200. Older committed artifacts may still
carry dead links.

## 5. Beyond the required items

- **Numeric grounding** (`grounding.py`) — every asserted number is checked against the
  query results the finding cites; failures are demoted to informational with an
  `UNVERIFIED` caveat. Built after a real incident where a fluent finding claimed a
  median of $0 while its own cited queries returned 37,536 / 29,926 / 26,127.
- **Calibrated confidence** (`confidence.py`) — a published 4-component score
  (`0.30·sample + 0.30·strength + 0.20·context + 0.20·quality`), computed in Python
  from evidence, never self-reported by the model.
- **Metric policy** (`metric_policy.py`) — while a `definition_conflict` is open on a
  metric, no unqualified number for it may be emitted. It catches the planted
  conversion-rate contradiction in `base_context.md`.
- **Eval harness** (`make eval`) — Table 1 re-verifies each spec's DDL live; Table 2
  drives 4 synthetic topologies through the no-LLM path; Table 3 re-executes each
  finding's cited SQL and re-checks its number.
- **Human-in-the-loop approval gate** before any DDL executes.
- **241 tests**, including a grep guard that fails if any source file names a known
  spec — the artifact to check if you suspect tuning to the five practice specs.
- Full methodology and every statistical formula: [`EVALUATION.md`](EVALUATION.md).

## 6. What is missing

Ordered by rubric impact, with what each actually needs.

| Gap | Why it matters | Estimate |
|---|---|---|
| **ClickHouse Cloud not used** | The guidelines ask for "your ClickHouse Cloud connection". All connection params are already env-driven and `load.sh` targets Cloud — but untested. | ~45 min |
| ClickStack not integrated | Optional. | — |

The probe-set entrypoint and `RUN.md` — previously the two open gaps — are done.
ClickHouse Cloud is the only remaining item, and was explicitly descoped.
