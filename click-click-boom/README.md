# TODO: Team Name

## Track
Atlys

## Project
Click Click Boom

## Team Members
- Ansh Mehta (anshmehtamm)
- Adarsh Gupta (travellerR)
- Nived Suresan (nivedsuresan)

## What it does
Three agents on ClickHouse that collapse the "new feature → instrumented → analyzed"
loop from manual and slow into automatic and traced:

- **Instrumentation Agent** turns a feature spec (markdown + raw NDJSON events) into a
  production-ready ClickHouse schema — base table DDL, materialized views, ordering/
  partition keys — benchmarked against real staged data, not guessed.
- **Context Agent** (Reviewer + Chronicler) gates every proposal against the shared
  business/data context layer before it can execute, then keeps that same layer fresh
  by writing back what's now true once a table lands — including flagging when a new
  table makes something already recorded stale.
- **Analytics Agent** explores a landed table (or, given a free-text question, decides
  which tables matter itself) entirely via its own tool calls — no pre-baked seed
  queries — and writes a PM-facing insight report with the mechanism behind each
  finding, not just a number.

All three run through the **Agents API**, fully traced end to end in
Langfuse, with a Next.js dashboard for live and historical visualization.

## Hosted Demo
Trouble hosting demo link (can add in 1 hour)

## Demo Video
https://drive.google.com/file/d/1HRMx3bEWPrwj2IUYYV8otKx7fDoLZ0Bi/view?usp=sharing

## Architecture
See `ARCHITECTURE.md` (and `architecture.html`) in this folder for the full
explanation and diagram — three agents, one shared harness, one ClickHouse service
for everything they know and produce. Summary:

- **LibreChat Agents API** hosts and runs the tool-calling loop for all three agents.
- **MCP servers** — a ClickHouse data-tools server and a context-engine server — the
  same two tool servers every agent calls.
- **Context layer**: `agent_meta.context_versions` in ClickHouse (an append-only log;
  `current_context` is a view resolving each section to its latest version) — chosen
  over a file or vector store so it's queryable, versioned, and lives next to the data
  it describes.
- **Observability**: Langfuse (one trace per run) + ClickStack (parallel OTel export
  of every trace) — see `traces.md` for every graded run's trace link, and
  `OSS_TOOLS.md` for exactly how Langfuse, ClickStack, and LibreChat are each wired.

## How we built it
- **Backend**: Python, agents driven through the LibreChat Agents API, two custom MCP
  tool servers (ClickHouse data tools; context engine), a deterministic orchestrator
  (`orchestrator/pipeline.py`) owning the propose → review → [rework, capped] →
  approve → test → execute → chronicle state machine so the LLM is only ever trusted
  for the reasoning steps, never the bookkeeping.
- **Data**: ClickHouse Cloud — `atlys` (the raw event tables + every landed feature
  table) and `agent_meta` (schema proposals/reviews, context versions, insights, full
  trace events) as two databases on the same service.
- **Tracing**: Langfuse, wired through `tracing/langfuse_wrapper.py` — every
  reasoning chunk and tool call logged live, not batched, plus a durable copy in
  `agent_meta.trace_events` so the dashboard can show history without depending on
  Langfuse being reachable.
- **Frontend**: Next.js dashboard (specs list, live trace viewer with per-agent-stage
  collapsible sections, insights feed, context browser) — polls a small file-backed
  live-run store (keyed by run id, self-healing against a dead process) to reattach to
  an in-progress run after a reload.

## How to run it
Full details in `RUN.md`