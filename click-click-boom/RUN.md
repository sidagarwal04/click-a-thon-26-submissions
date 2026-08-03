# RUN.md — Atlys agentic pipeline

Three agents (Instrumentation, Analytics, Context) + Langfuse tracing + a Next.js
dashboard for visualization. This doc gets you from a fresh checkout to running the
pipeline end to end. Full one-time environment bootstrap (Python venv, LibreChat with
the Agents API, MCP servers) is in `../SETUP.md` — this file assumes that's done and
focuses on "how to actually run something."

## 1. Environment

Copy `atlys-agents/.env.example` → `atlys-agents/.env` and fill in:

```
CLICKHOUSE_HOST / CLICKHOUSE_PORT / CLICKHOUSE_USER / CLICKHOUSE_PASSWORD / CLICKHOUSE_SECURE
  — your ClickHouse Cloud service (the `atlys` database with the 8 base event tables
    already loaded — see click-a-thon-2026-main/Atlys/data/load.sh)

LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_HOST
  — Langfuse Cloud project, for tracing every agent turn

LIBRECHAT_URL / LIBRECHAT_API_KEY
LIBRECHAT_AGENT_INSTRUMENTATION_PROPOSER / LIBRECHAT_AGENT_CONTEXT_REVIEWER
LIBRECHAT_AGENT_CONTEXT_CHRONICLER / LIBRECHAT_AGENT_ANALYTICS
  — a locally-running LibreChat instance (Agents API enabled) hosting the 4 agents,
    and each agent's ID once created (see ../SETUP.md section 2-3)

OPENAI_API_KEY
  — the LLM provider LibreChat's agents call (see ARCHITECTURE for why OpenAI)
```

One-time bootstrap of the agent metadata layer + context seed:

```bash
cd atlys-agents
.venv/bin/python scripts/init_db.py         # creates agent_meta DB + tables
.venv/bin/python scripts/seed_context.py    # seeds the base context layer from base_context.md
```

## 2. One command to run the pipeline end to end

### Option A — the dashboard (what we actually use day to day)

```bash
cd analytics-dashboard
npm install   # first time only
npm run dev   # http://localhost:3001
```

- **Specs** → **New Spec** → pick a folder with `spec.md` + `events.ndjson` (e.g. any
  folder under `click-a-thon-2026-main/Atlys/specs/`) → watch the live trace (every
  reasoning step + tool call, propose → review → rework loop → execute → chronicle) in
  the right panel as it happens.
- **Insights** → **Create Insight** → pick an already-executed spec (analytics scoped
  to that table's PM questions) or the **Custom question** tab (free-text, no single
  table in mind — this is what the standard probe set uses) → same live-trace panel.
- **Context** → browse the current knowledge layer by taxonomy, or the full changelog.

### Option B — CLI, one spec / one question at a time (what actually produced this submission's artifacts)

```bash
cd atlys-agents

# Ingest a known spec end to end (propose -> review -> execute -> chronicle):
.venv/bin/python scripts/run_express_checkout.py
.venv/bin/python scripts/run_group_family.py
.venv/bin/python scripts/run_status_sharing.py
.venv/bin/python scripts/run_abandoned_checkout_recovery.py
.venv/bin/python scripts/run_instant_forex.py

# Analytics on an already-executed spec:
.venv/bin/python scripts/run_analytics_express_checkout.py
.venv/bin/python scripts/run_analytics_forex.py
.venv/bin/python scripts/run_analytics_status_sharing.py

# Analytics on a free-text question, no spec in mind (the standard probe set):
.venv/bin/python scripts/run_analytics_custom.py "Analyze the existing funnel and surface the most important issues, with the why."
.venv/bin/python scripts/run_analytics_custom.py "Where are we losing conversions, and for which segments (device / geo / destination)?"
.venv/bin/python scripts/run_analytics_custom.py "Are there any regressions or trends over the last quarter?"
.venv/bin/python scripts/run_analytics_custom.py "Is anything in the base context wrong, stale, or self-contradictory?"
```

Every run prints its own Langfuse trace URL on completion. All 5 spec runs and all 4
probe runs above are the ones behind `submission/traces.md`, `submission/graded-output/ddl/`,
and `submission/graded-output/insights/` — running them again reproduces the same shape
of output (not byte-identical, LLM calls aren't deterministic) against the same live
ClickHouse data.

### For an unseen (6th) spec at judging time

```bash
cd atlys-agents
# 1. Drop the 6th spec's spec.md + events.ndjson somewhere, then either:
.venv/bin/python -c "
from orchestrator import ingest_spec
import json, pathlib
spec_dir = pathlib.Path('<path to the 6th spec folder>')
spec_markdown = (spec_dir / 'spec.md').read_text()
events = [json.loads(l) for l in (spec_dir / 'events.ndjson').read_text().splitlines() if l.strip()]
result = ingest_spec(spec_name='<spec_name>', spec_markdown=spec_markdown, sample_events=events, full_events=events)
print(result)
"
# 2. Then run analytics on it the same way as any executed spec:
.venv/bin/python -c "
from analytics.analytics_agent import run_analytics_for_spec
print(run_analytics_for_spec('<spec_name>'))
"
```

...or just use the dashboard's **New Spec** → **Create Insight** flow (Option A) — same
underlying calls, live trace visible the whole time.

## 3. Verifying the context layer is live, not a static file

```bash
cd atlys-agents
.venv/bin/python -c "
from orchestrator.pipeline import get_current_context
import json
for s in get_current_context():
    print(s['section'], '-', s['confidence'])
"
```

This queries `agent_meta.current_context` — a ClickHouse VIEW over the append-only
`agent_meta.context_versions` table (`argMax` per section, latest write wins) — the
exact same query the analytics/proposer/reviewer agents' MCP tools
(`list_context_sections`/`lookup_context`, see `mcp_servers/context_server.py`) run
live on every turn. There is no separate cache or snapshot file the agents could be
reading stale data from.
