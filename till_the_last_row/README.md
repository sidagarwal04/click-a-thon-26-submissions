# till_the_last_row

## Track

Atlys

## Project

**Atlys Agentic Analytics** — from feature spec to insight: agents that instrument, analyze, and explain.
**Pitch Deck** - submission/Atlys_Pitch_till_the_last_row.pdf

## Team Members

- Abhishek Aigali ([@abhi1489](https://github.com/abhi1489))
- Deepak Kumar ([@dpkmcaanna](https://github.com/dpkmcaanna))
- Srinidhi Krishna Mundru ([@srinidhi-22](https://github.com/srinidhi-22))
- Nikhil Muddamsetty ([@Nikhil-Muddamsetty](nikhil.muddamsetty@gmail.com))

## What it does

A system of three traced agents on **ClickHouse Cloud** that collapses the manual
feature-instrumentation loop. A feature spec is dropped in and, in one traced run:

- The **Instrumentation Agent** designs production-ready ClickHouse schemas (types,
  ordering keys, partitioning, materialized views), validates + smoke-tests them, and
  pushes the DDL to GitHub.
- The **Context Agent** keeps a living business-context layer fresh — bumping a version,
  logging a changelog diff, and surfacing contradictions in the imperfect base context.
- The **Analytics Agent** reads the fresh context, pushes aggregation into ClickHouse
  (never raw rows), and writes PM-ready insights with the *why* and confidence scores.

It is built for the **unseen 6th spec** — it parses free-form specs with no hardcoding,
so a surprise feature flows through the same path: **spec → schema → context → insight**.

## Hosted Demo

**Live demo:** http://16.112.191.86:3080

The hosted demo covers everything the Atlys track submission requires: the three agents
(Instrumentation → Context → Analytics) and their handoffs, the context layer and how it
stays fresh, Langfuse tracing, the LibreChat conversational interface, and the **unseen
6th-spec run** (schema + insight + mandatory trace). Full graded-evidence index:
[`submission/README.md`](submission/README.md).

## Demo Video

**Recorded walkthrough:** https://drive.google.com/file/d/1_b74TbiKauxgJvbM7JMIJH3nBNuzKyVS/view?usp=sharing

## Architecture

See [`ARCHITECTURE.md`](ARCHITECTURE.md) — the three agents and their subagent handoffs,
where the context layer lives (and why), how Langfuse tracing is wired, the LibreChat +
MCP setup, and the LLM choice.

The pipeline in one line: a spec is dropped on the **Instrumentation Agent** (parent),
which designs + validates + applies the ClickHouse schema and pushes it, then calls the
**Context Agent** (refresh living context) and the **Analytics Agent** (PM-ready
insights) as **subagents** — one Langfuse trace end to end.

Submission evidence mapped to the track guidelines:

| Submission guideline | Where |
| --- | --- |
| **1. Code + how to run** | [`RUN.md`](RUN.md) — env vars, ClickHouse Cloud connection, one-command pipeline. |
| **2. Architecture** | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| **3a. Generated DDL** (5 known specs + 6th) | [`submission/ddl/`](submission/ddl/) |
| **3b. Analytics report over 8 existing tables** | [`submission/probe-outputs/`](submission/probe-outputs/) |
| **3c. Context layer + before/after changelog** | [`submission/context-freshness/`](submission/context-freshness/) |
| **3d. Unseen 6th-spec bundle** (schema + insight + trace) | [`submission/unseen-6th-spec/`](submission/unseen-6th-spec/) |
| **4. Langfuse trace links** (6th-spec trace mandatory) | [`submission/TRACES.md`](submission/TRACES.md) |

## How we built it

- **ClickHouse Cloud** — the primary datastore and analytical engine (`atlys` database,
  8 base tables + agent-generated tables and materialized views).
- **LibreChat** — agent runtime + conversational interface. All three agents are
  configured LibreChat Agents chained through native **Subagents**; they have no shell —
  every DB, git, and file action goes through **MCP servers** (`clickhouse_write_tools`,
  read-only `clickhouse-cloud`, `clickhouse_git_write`, `filesystem`).
- **Vector + OpenTelemetry Collector** — a containerized ingestion pipeline that
  transforms events and streams them into ClickHouse, decoupled from the agent flow.
- **Langfuse** — full LLM tracing (per-agent spans; the whole pipeline is one chain
  trace). **ClickStack / HyperDX** — system-level observability and live dashboards
  (engagement/funnel analytics, schema-changes-over-time).
- **LiteLLM** gateway serving Anthropic `opus-4.x` to all agents.

## Stack

- **ClickHouse Cloud** — primary datastore + analytical engine (`atlys` database).
- **LibreChat** — agent runtime + conversational interface; all DB/git/file I/O via MCP servers.
- **Langfuse** — full LLM tracing (per-agent spans; the chain is one trace).
- **LiteLLM** gateway serving `opus-4.x` to all agents.

## How to run it

Full instructions (env vars, ClickHouse Cloud connection, one-command pipeline) are in
[`RUN.md`](RUN.md). Quick start:

1. **Prerequisites:** Docker + Docker Compose, a ClickHouse Cloud service with the
   `atlys` database loaded, a GitHub PAT (`repo` scope), a Langfuse project, and a
   LiteLLM gateway key.

2. **Configure env:** set the Atlys-specific keys in `librechat/.env` (gitignored) —
   `CH_HOST`, `CH_USER`, `CH_PASSWORD`, `CH_DATABASE`, `GITHUB_TOKEN`, `CH_TARGET_REPO`,
   `CH_TARGET_BRANCH`, `LITELLM_API_KEY`, `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` /
   `LANGFUSE_BASE_URL`, `MONGO_URI`.

3. **Start the stack:**

   ```bash
   cd librechat
   docker compose up -d
   ```

4. **Run the pipeline:** open LibreChat (default `http://localhost:3080`) and, in a new
   conversation with the **Instrumentation Agent**, drop a spec to trigger the full
   run — schema → context → insight — traced end to end in Langfuse. See
   [`RUN.md`](RUN.md) for the exact prompt and the required one-time UI setup.
