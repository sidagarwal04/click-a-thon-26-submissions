# Team Nyanners

## Track
Atlys

## Project
From feature spec to insight: agents that instrument, analyze, and explain.

## Team Members
- Karun (karun08042002)
- Kannan (kannan-ramu)
- Nannan (nanna7077)

## What it does
A multi-agent product analytics system that turns an uploaded event file and feature spec into validated ClickHouse tables, analytics metrics, durable business context, and a PM-facing report.

It uses LibreChat agents for instrumentation, analytics, context, and finalization; ClickHouse for event data, state, schema history, and context; and Langfuse plus ClickStack for tracing and operational observability.

## Hosted Demo
https://clickathon26.nannan.in/

## Demo Video
https://drive.google.com/file/d/1GDvKkGOMMH5dusdtuOhbPFED8DC2wUX2/view?usp=sharing

## PPT
https://docs.google.com/presentation/d/1UXZAI6x78ACw3GIknldwk69bnhB6nxYTm4xtCVGREoI/edit?usp=sharing

## Architecture
Please refer [ARCHITECTURE.md](ARCHITECTURE.md)

## How we built it
- **Frontend/API:** Investigation UI backed by FastAPI; accepts `events.ndjson` + `spec.md`, uploads them to private Azure Blob Storage, and polls run status.
- **Agent runtime:** LibreChat persisted agent chain using OpenAI `gpt-5.6-luna` via the Responses API.
- **Agents:** Instrumentation → Analytics → Aggregate Analyst → Evidence Reviewer → Context → Finalizer.
- **Data platform:** ClickHouse Cloud stores generated event tables, rollups/materialized views, workflow state, schema history/diffs, context versions/embeddings, and final reports.
- **Agent tools:** Private MCP services for bounded Blob inspection, ClickHouse DDL/querying, context persistence, analytical validation, and small code-based computations.
- **Ingestion:** Large NDJSON transfer is programmatic; agents inspect only profiles, peeks, and query results, then decide schema and SQL.
- **Observability:** Langfuse traces prompts, model calls, tools, and agent edges; OpenTelemetry feeds ClickStack/HyperDX for service traces, logs, metrics, latency, and failures.
- **Deployment:** Docker Compose on a VM, with private internal MCP services and Git-tracked deployment/bootstrap configuration.

Interesting implementation details: the context layer is versioned and stored in ClickHouse rather than a mutable file or standalone vector DB; schema/context changes are queryable diffs with provenance.

## How to run it
Please refer [HOW_TO_SETUP.md](HOW_TO_SETUP.md)