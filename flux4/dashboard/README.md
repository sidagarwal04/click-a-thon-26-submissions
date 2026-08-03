# inMobi — Metric Forensics Dashboard

Automated root-cause analysis, made readable. The orchestrator runs continuously,
writing its investigation into ClickHouse as it goes. This app turns that live data
into a dashboard anyone can follow — no SQL required.

Built for **Click-a-thon 2026**, Data Warehousing track — team Flux4.

```
   rca_orch pipeline
   (orchestrator writes as it runs)
          │
          ▼
   ClickHouse Cloud
   rca_orch.v_narration   ── one row per incident, fully attributed
   rca_orch.v_ruleout     ── exclusion test results per candidate
   rca_orch.uniformity    ── spread of the culprit across other dimensions
   rca_orch.anomalies     ── per-day detector output
          │
          ▼
   FastAPI  /api/incidents      ── all incidents, shaped for the UI
            /api/incident/{id}  ── full detail: attribution, exclusion, lifecycle
            /api/timeseries     ── global daily metric curves
            /api/pulse          ── lightweight poll: incident count + health notes
          │                              │
          ▼                              ▼
   Dashboard UI                   Langfuse Cloud
   (live, auto-refreshing)        every ClickHouse fetch and LLM
                                  generation traced end-to-end
```

## What it does

**Reads the pipeline as it runs.** `rca_orch.v_narration` is a view that recomputes
every time the orchestrator writes. The dashboard polls `/api/pulse` every few seconds;
when the incident count changes a toast fires and the list updates without a full reload.

**Shows the full investigation.** Each incident card expands into the attribution
waterfall (which segment, how large a share of traffic, how much of the anomaly it
explains), the exclusion proof (remove it, does the global anomaly clear?), and the
orchestrator's own step-by-step lifecycle trace so you can see exactly what ran and when.

**Narrates in plain English on demand.** The detail view can ask an LLM (via OpenRouter)
to summarise the incident in three sentences for a non-technical reader. The summary is
cached in memory so the second load is instant. If the LLM is down the raw numbers show
instead — the page never breaks.

**Includes a built-in briefing assistant.** The floating chat button in the corner opens
a context-aware panel. It knows which incident you have selected, injects the full
attribution data into the system prompt, and streams the response token-by-token using
any OpenAI-compatible endpoint (OpenRouter, OpenAI, etc.). Credentials live in your
browser's `localStorage` — nothing is proxied through the server.

**Traces everything.** Langfuse v4 wraps every ClickHouse fetch (`as_type="retriever"`),
every LLM generation (`as_type="generation"`), and every incident detail request
(`as_type="span"`). One incident lookup = one trace. You can follow a slow request from
the dashboard straight to the Langfuse session that caused it.

## Setup

```bash
git clone <your-repo-url> && cd inMobi
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # fill in the values below
uvicorn app:app --reload --port 8000
```

Open `http://localhost:8000`. If the orchestrator has not run yet the dashboard shows
a "no rows" note — that is expected. It will populate as the pipeline writes.

### Environment variables

| Variable | What it is |
|---|---|
| `CH_HOST` | ClickHouse Cloud hostname (e.g. `abc.ap-south-1.aws.clickhouse.cloud`) |
| `CH_PORT` | `8443` (TLS, the default) |
| `CH_USER` | `default` or your user |
| `CH_PASSWORD` | your ClickHouse password |
| `ORCH_DB` | schema where the orchestrator writes — default `rca_orch` |
| `EVENTS_TABLE` | raw events table — default `rca.ad_events` |
| `OPENROUTER_API_KEY` | from openrouter.ai → Keys, starts `sk-or-` |
| `LLM_MODEL` | model to use for narration — default `openai/gpt-oss-20b:free` |
| `LANGFUSE_PUBLIC_KEY` | from cloud.langfuse.com → Settings |
| `LANGFUSE_SECRET_KEY` | from cloud.langfuse.com → Settings |
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` (or self-hosted URL) |

`.env` is gitignored. On Render, set the same keys under Environment.

### Setting up the briefing widget

Click the chat button in the dashboard. The first time it asks for:

- **API Base URL** — `https://openrouter.ai/api/v1` (or any OpenAI-compatible endpoint)
- **API Key** — your key, starting `sk-or-`
- **Model** — `openai/gpt-4o` or any model on OpenRouter

These are saved to `localStorage` and never leave your browser.

## API reference

| Route | What it returns |
|---|---|
| `GET /` | the dashboard |
| `GET /api/pulse` | incident count, coverage dates, revenue at risk, health notes |
| `GET /api/incidents` | all incidents from `v_narration`, shaped for the list view |
| `GET /api/incident/{id}` | full detail — attribution, exclusion, lifecycle, optional narration |
| `GET /api/timeseries` | global daily curves for requests, fill rate, eCPM, revenue |
| `GET /api/incident/{id}/timeseries` | blended + segment-level series for one incident |
| `GET /api/diag` | connectivity check — which tables are reachable and how many rows |
| `GET /api/health` | 24-hour success/failure KPIs from `rca.app_events` |
| `POST /api/chat` | server-side LLM proxy (used internally; widget calls OpenRouter directly) |

Add `?fresh=true` to any incident endpoint to bypass the 25-second view cache and
force a recompute. Add `?llm_narrate=true` to `/api/incident/{id}` to include the
plain-English summary.

## Stack

ClickHouse Cloud · FastAPI · Jinja2 · OpenRouter · Langfuse v4 · Render
