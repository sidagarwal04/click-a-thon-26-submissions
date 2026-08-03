# ClickStack / Langfuse / LibreChat — how each is actually wired

Per the submission guidelines, this documents the role, wiring, and evidence for
every OSS tool this project touches — not just that it's installed.

## Langfuse — the primary tracing layer, live in every run

**Role in the pipeline**: every agent turn (Instrumentation Proposer, Context
Reviewer, Context Chronicler, Analytics Agent) runs inside `tracing.traced_run()`
(`code/atlys-agents/tracing/langfuse_wrapper.py`). Every reasoning chunk and tool
call is logged to Langfuse the moment it happens — not batched at the end — via
`client.start_as_current_observation`/`run.log()`/`run.span()`. This is what every
trace link in `traces.md` points to.

**Wiring**:
- `code/atlys-agents/tracing/langfuse_wrapper.py` — the whole integration:
  `get_client()` (singleton reading `LANGFUSE_PUBLIC_KEY`/`SECRET_KEY`/`HOST` from
  env), `traced_run()` (opens one trace per agent run), `Run.log()`/`Run.span()`
  (per-event/per-phase logging).
- `code/atlys-agents/.env.example` — the required env vars, redacted.
- Also durably mirrored into `agent_meta.trace_events` in ClickHouse on the same
  write path (`Run._record()`), so the dashboard can show full history without
  depending on Langfuse being reachable — Langfuse is the source of truth for the
  live/shareable trace, ClickHouse is the durable copy the app itself reads from.

**Evidence**: every trace link in `traces.md`, one per graded run (5 known specs +
the 6th spec + all 4 standard probes + the autonomous 8-table insight run).

## ClickStack — OpenTelemetry export of every trace, for centralized observability

**Role in the pipeline**: a second, parallel export of the exact same spans Langfuse
records — the same trace IDs flow to both. This is deliberately *additive* to
Langfuse (Langfuse's own OTel `TracerProvider` gets a second `BatchSpanProcessor`
pointed at the local ClickStack collector), not a replacement, so losing ClickStack
never breaks tracing.

**Wiring**:
- `code/atlys-agents/docker-compose.yml` — runs
  `clickhouse/clickstack-otel-collector`, listening on `4317` (OTLP gRPC) /
  `4318` (OTLP HTTP), configured with this team's own ClickHouse Cloud service
  (`CLICKHOUSE_ENDPOINT`/`CLICKHOUSE_USER`/`CLICKHOUSE_PASSWORD`, secret redacted
  via env var).
- `code/atlys-agents/tracing/hyperdx_integration.py` — `init_hyperdx()` attaches
  the OTLP exporter to Langfuse's existing `TracerProvider` and instruments Python
  logging so log lines flow through too; called once from `traced_run()` in
  `langfuse_wrapper.py`, right after the Langfuse client is created. Fails silently
  and falls back to Langfuse-only tracing if the local collector isn't running —
  optional by design, never a hard dependency for the pipeline to work.

**Evidence**: `docker-compose.yml` + `hyperdx_integration.py` above are the
integration code. Bring the collector up with `docker compose up clickstack-otel`
(from `code/atlys-agents/`) before a run to see spans land in the configured
ClickHouse Cloud service alongside the `atlys`/`agent_meta` databases.

## LibreChat — the agent-hosting layer this pipeline was originally built on

**Role in the pipeline, honestly stated**: LibreChat's Agents API originally hosted
and ran the tool-calling loop for all four agents (`code/librechat/librechat.yaml`
registers the three MCP servers — `atlys_context`, `atlys_clickhouse` (registered,
not attached — see the comment in the file for why), `atlys_data` — and enables the
`skills`/`tools`/`actions` agent capabilities they need). Over the course of the
hackathon this was replaced by calling OpenAI's Responses API directly
(`code/atlys-agents/agent_runner/runner.py`), after confirming via direct testing
that LibreChat's Agents API proxy never returned real `function_call` arguments,
real reasoning summaries, or working `previous_response_id` chaining — all three
came back correctly calling OpenAI directly. `code/atlys-agents/librechat_client/`
is now a thin compatibility shim (`call_agent` → `agent_runner.run_agent`) kept only
so `orchestrator/agent_io.py`'s existing call sites didn't need to change.

**Wiring** (as it stood while LibreChat was live, kept for evidence per the
guidelines):
- `code/librechat/librechat.yaml` — MCP server registration + agent capabilities.
- `code/atlys-agents/mcp_servers/` — the actual tool servers LibreChat (and now the
  direct OpenAI path) call: `data_tools_server.py` (`atlys_data` — lean,
  size-capped ClickHouse read tools), `context_server.py` (`atlys_context` — the
  context-engine tools), a ClickHouse MCP registration (`atlys_clickhouse`).
- `code/atlys-agents/.env.example` — `LIBRECHAT_URL`/`LIBRECHAT_API_KEY` +
  per-agent IDs, from when agents were created in LibreChat's UI.

We're not claiming LibreChat as a live integration today — it's included here
because it's genuinely part of how this system was built and is real, working
config, not because it's still in the runtime path.
