# MagnateBits

## Track

Atlys — *"From feature spec to insight: agents that instrument, analyze, and explain."*

## Project

**Atlys Agents** — a feature spec goes in; a production ClickHouse table, a refreshed
context layer, and PM-readable insights come out, in one traced run.

## Team Members

- Barun Acharya ([@daemon1024](https://github.com/daemon1024))
- Priyanshu Raj Shrivastava
- Shivanshu

## What it does

```bash
python run_pipeline.py --spec <spec.md> --events <events.ndjson>
```

- **Instrumentation Agent** — profiles the raw events, proposes production DDL, lints and
  dry-runs it, pauses for human approval, then executes, loads, and measures whether each
  materialized view earned its keep.
- **Context Agent** — a versioned context layer stored *in ClickHouse*, reconciled after
  every run, with contradiction checks settled by SQL.
- **Analytics Agent** — plans queries from a template catalog, executes them in
  ClickHouse, interprets only the aggregates, and scores each finding.

Nothing is written against a known spec — column types, entity key, funnel order and
segment dimensions are all derived at runtime.

## Hosted Demo

Runs locally: `make init` then one command — see [`solution/RUN.md`](solution/RUN.md).
The video below walks through the full flow.

## Demo Video

https://www.loom.com/share/7faf11555a8f495192d81a9006a0c58e

## Architecture

Full write-up: **[`ARCHITECTURE.md`](ARCHITECTURE.md)**.

**Context layer — a ClickHouse table, not a vector store.** `context_entry_log`
(append-only, versioned) plus a `context_current` view. Because the context sits in the
same engine as `system.columns`, *"the docs claim column X exists"* is settled by a query
returning zero rows rather than an LLM opinion. Versioning, diffs and changelog fall out
of the append-only log; every entry carries the `run_id` linking it to its trace.

We also ship in-ClickHouse vector retrieval (`cosineDistance` + HNSW
`vector_similarity` + a text index), default-on once the layer outgrew a prompt. The
embedding is a deterministic local hashing function, so retrieval stays reproducible.
No external vector database.

**Langfuse.** `tracing.py` is the only module importing Langfuse; one trace per run,
spans mirroring the pipeline stages. `llm.complete_json(..., context_version=...)` takes
the context version as a **mandatory** argument — no traced LLM call can exist without
recording which snapshot fed it.

**LibreChat + MCP.** `atlys_mcp/` exposes 8 tools, each tagged with native
`ToolAnnotations` so a host can tell reads from writes; `run_pipeline` requires
`confirm=true` server-side. Wiring committed:
[`librechat.yaml`](solution/deploy/librechat.yaml),
[`docker-compose.yml`](solution/deploy/docker-compose.yml),
[`.env.example`](solution/.env.example) (secrets redacted).

**LLM providers.** Claude Sonnet 5 via the authenticated `claude -p` CLI (subscription
auth, no API key); Anthropic SDK as an env-flip alternative; a deterministic offline mock
for evaluation; Ollama Cloud for the LibreChat chat surface only.

## What we did differently

**Every asserted number is verified against the queries it cites.** `grounding.py` checks
each finding's figure against the actual query results; unmatched claims are demoted with
an `UNVERIFIED` caveat. Deterministic Python — a judge can re-run it.

**Confidence is computed, not claimed.** A published four-component score
(`0.30·sample + 0.30·strength + 0.20·context + 0.20·quality`) calculated in Python from
the evidence. The model supplies raw numbers; it never rates itself.

**The system refuses when the data won't support an answer.** With a definition conflict
open on a metric, no unqualified number for it is emitted — that catches the planted
conversion-rate contradiction in `base_context.md` and answers with both definitions
instead of picking one.

**Materialized views are kept or dropped on measured evidence.** Each is built, loaded,
both sides counted, and dropped if it doesn't clear the bar.
[`SCHEMA_CATALOG.md`](solution/docs/SCHEMA_CATALOG.md) lists the ones proposed, measured
and **rejected**, each with the ratio that killed it.

**Human approval gate.** The pipeline stops after the DDL dry-runs clean — proven
runnable, nothing executed — and waits. Non-interactive callers resolve it through a
`pipeline_approvals` table.

**Context freshness is mechanical.** Because `context_version` is mandatory on every LLM
call, the trace shows it: on the sealed run `propose_ddl` read **v18**, and after
reconciliation absorbed the new table `analytics.*` read **v19**.

**One analytics engine, two data shapes.** The 8 pre-existing tables are
one-table-per-event while every template expects an `event` discriminator. Rather than a
second template set, `probe.py` presents them to the same stack as one event stream over
their 30 shared columns — so all 22 templates, the scoring, the grounding and the metric
policy apply unchanged.

**241 tests**, including a grep guard that fails the build if any source file names a
known spec.

## Graded outputs

| What | Where |
|---|---|
| Generated DDL — 5 known specs and the 6th | `solution/artifacts/runs/<run_id>/schema.sql` + `proposal.json` |
| **Sealed 6th-spec bundle** | [`sealed-spec-6th/`](sealed-spec-6th/) |
| Analytics over the 8 existing tables + 4 standard probes | [`probe-outputs/PROBE_RESULTS.md`](probe-outputs/PROBE_RESULTS.md) |
| Context layer + before/after changelog | `solution/out/context/CHANGELOG.md` |
| **Langfuse traces, exported as JSON** | [`traces/`](traces/) |

### Sealed 6th spec — run `29b74c8f`

All five stages ok · 192.4s · **5,363/5,363 rows loaded, 0 rejected** · 12 queries, 0
failed · context **v18 → v19** · 8 contradictions.

**Trace:** https://us.cloud.langfuse.com/project/cmsa37gfi164uad0dvkq6ygqo/traces/1e202f5aab976efd00e4b8311a25be47

Its branching shape needed no per-spec code: `coupon_applied` and `coupon_rejected` are
mutually exclusive — measured, **zero** entities have both — so the rejected arm is kept
out of the ordered funnel while staying queryable in the schema. Left in, `windowFunnel`
forces every later step to zero and a modelling artefact reads as a catastrophic
drop-off.

Schema highlights: `id` as `String` with a comment explaining the 32-char-hex trap that
`UUID` would reject, money as `Decimal(18,4)`, `LowCardinality` on enums, **no `Nullable`
anywhere**, and `ORDER BY (event, timestamp, user_id)` — never id-first.

### Standard probe set — 4/4, 73/73 figures grounded

| # | Prompt | Grounded | Confidence | Trace |
|---|---|---|---|---|
| 1 | Funnel issues, with the why | 20/20 | 0.78 | [json](traces/probe_1.json) |
| 2 | Losing conversions, by segment | 32/32 | 0.72 | [json](traces/probe_2.json) |
| 3 | Regressions/trends last quarter | 15/15 | 0.62 | [json](traces/probe_3.json) |
| 4 | Base context wrong/stale/contradictory | 6/6 | 0.75 | [json](traces/probe_4.json) |

The two dominant leaks are `auth_completed` (13.1% through-rate) and `document_uploaded`
(12.6%), both **uniform across every device/OS/geo cut** — structural rather than
segment-specific — with the funnel's longest step gap (~1.9h median) immediately before
document upload. Probe 4 found a stale context entry: the business-overview diagram
states a 4-step funnel where the instrumented reality is 8.

## How we built it

Python 3.12/3.13 · ClickHouse · Langfuse · MCP + LibreChat · Streamlit.

The Streamlit console is insight-first: each finding opens into its evidence chain — the
confidence decomposition, the exact SQL it rests on (re-runnable against ClickHouse from
the page), the context entries cited, and the traced LLM call that wrote it. Langfuse
traces are rendered natively from its API, since Langfuse itself cannot be embedded.

[`solution/docs/EVALUATION.md`](solution/docs/EVALUATION.md) documents the verification
stack and every statistical formula used, with a real eval run.

## How to run it

**[`solution/RUN.md`](solution/RUN.md)** — prerequisites, env vars, one command,
troubleshooting.

```bash
cd solution
make init      # venv, deps, ClickHouse, 8 tables loaded, context bootstrapped, 241 tests
./.venv/bin/python run_pipeline.py \
    --spec ../specs/06_unseen/spec.md --events ../specs/06_unseen/events.ndjson --rebuild
```

The 5 known specs and the sealed 6th live in the organisers' repo under `Atlys/specs/`;
their raw `events.ndjson` are not duplicated here.
