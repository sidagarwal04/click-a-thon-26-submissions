# Automated Root-Cause Analyst — InMobi Click-a-thon 2026

Detects when a key ad-metric (revenue, fill rate, eCPM, requests, CTR) deviates
from its expected baseline, automatically drills down to the specific
segment(s) responsible, and writes a short plain-language diagnosis where
every number is real and reproducible from ClickHouse.

ClickHouse does all the analysis (baseline comparison, revenue-identity
decomposition, per-segment ranking). An LLM (Gemini) only narrates the
already-computed numbers. Every step — every SQL query and the final LLM
call — is captured in a trace (local JSON + Langfuse), so a judge can see
exactly what was checked, in what order, and why.

## How it works

1. **Detect** (`sql` via `src/rca/baseline.py`): for each day and each metric,
   compare against a *like-for-like* baseline — the same weekday, trailing
   weeks — instead of a flat global average (which would flag every weekend
   as anomalous). A robust (median/MAD) z-score plus a minimum relative-move
   floor avoids crying wolf on noise. A linear trend fit over the trailing
   points nets out the slow growth trend the data has, so being later in the
   dataset doesn't itself look anomalous. A two-pass contamination guard
   keeps one real one-day incident from poisoning the trend baseline of a
   later, otherwise-normal day.

2. **Decompose** (`src/rca/attribution.py::decompose_revenue`): walks the
   revenue identity `revenue = requests × fill_rate × render_rate × eCPM/1000`
   using an exact logarithmic-mean (LMDI) decomposition — the factor
   contributions sum exactly to the observed revenue delta, so "which factor
   moved" is never a guess.

3. **Drill down** (`src/rca/attribution.py::drill_down`): for the responsible
   factor, ranks every segment of every dimension (ad_format, category,
   publisher_tier, vertical, campaign_type, region, country, device_model,
   os_version) by **explanatory power** (Adtributor's formula — the share of
   the movement this segment accounts for, after removing the change a pure
   volume/mix shift at the baseline rate would predict). A segment is only
   declared the localized cause if its **lift** (explanatory power ÷ its own
   volume share) clears a threshold — a segment whose EP simply equals its
   size moved in exact proportion to everything else, which is evidence of a
   *broad* effect, not a localized one, and is reported as such instead of
   being forced into a story. Recurses one level deeper into the winning
   segment (e.g. device → device × region).

4. **Narrate** (`src/rca/narrate.py`): the only LLM call. It receives nothing
   but the structured JSON of computed numbers and is instructed to cite only
   what's in that JSON, name the ruled-out segments, and say plainly when
   nothing localizes.

5. **Trace** (`src/rca/tracing.py`): every stage above runs inside a span.
   Spans are always written to `traces/*.json` locally; if Langfuse
   credentials are set they're mirrored live to Langfuse as well, nested
   exactly as they nest in code.

There are three ways to use it, all backed by the same deterministic pipeline
(`src/rca/pipeline.py`) and the same traces:

- **CLI** (`rca scan|investigate|auto`) — scripted / scriptable, JSON + trace
  output for every run.
- **Dashboard** (`rca serve`) — a small web app: live metric charts with
  anomaly markers, an incident list, and a full drill-down report per incident.
- **Chat** (LibreChat, via MCP) — ask for an investigation (or an ad-hoc SQL
  question) in natural language; the chat model calls the exact same pipeline
  as a tool, so answers are grounded in the same real numbers.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env   # fill in ClickHouse Cloud + Gemini + Langfuse creds
bash scripts/load_data.sh   # idempotent: drops + recreates + reloads everything
```

`scripts/load_data.sh` applies `sql/ddl.sql`, bulk-loads the three dimension
CSVs and `ad_events.parquet` via `clickhouse-client`, then runs
`sql/build_fact.sql` to build `fact_events` — a single denormalized table
(fact + all three dimensions pre-joined) so every drill-down query below is a
plain single-table `GROUP BY`, no joins at query time.

To point at a fresh dataset (e.g. the unseen-incident release), just replace
the files under `data/` and rerun the same script — nothing else changes.

## Usage

```bash
# Detect-only: which days, for which metrics, look anomalous (no drill-down)
rca scan
rca scan --metric revenue --metric fill_rate --lookback-weeks 4

# Full investigation of one specific window: decompose + drill-down + narrate
rca investigate --metric fill_rate --start 2026-06-23 --end 2026-06-25

# End to end: scan the whole loaded range, investigate + narrate every incident found
rca auto
```

`rca auto` (and `investigate`) write each result as JSON to `out/` and print
the local trace path (and the Langfuse trace URL, if configured). `rca auto`
with no arguments scans the full date range currently loaded in
`fact_events` — this is what to run against the unseen-incident dataset once
it's loaded, with no code changes.

## Running it all: one `docker compose up`

The dashboard, its MCP server, LibreChat, LibreChat's database, and the
official ClickHouse MCP server are all defined in one file: the repo-root
`docker-compose.yml`. From the repo root:

```bash
cp implementation/.env.example implementation/.env   # fill in CLICKHOUSE_*, GEMINI_API_KEY
cp librechat/.env.example librechat/.env             # fill in the same + generate JWT/CREDS secrets
docker compose up -d --build --wait
```

(`setup_teammate.py` at the repo root automates all of the above, including
generating the JWT/CREDS secrets and creating your personal follow-up agent —
see below.) `--wait` blocks until every service's healthcheck passes, so
there's nothing to poll for manually. This replaces what used to be three
separate consoles (`rca serve`, `rca mcp-serve`, `cd librechat && docker
compose up`).

For local development where you want fast edit/reload on just the dashboard
or MCP server without a rebuild, `rca serve` / `rca mcp-serve` still work
directly against a `pip install -e .`'d checkout — see below.

## Dashboard

```bash
rca serve   # http://127.0.0.1:8000 -- or via docker compose, see above
```

A live homepage: metric tabs (revenue/fill_rate/eCPM), a hand-rolled SVG
chart with a hover crosshair + tooltip, anomaly markers, and a dashed
baseline line (pulled live from `/api/timeseries`, which runs the same
baseline/detection code as the CLI), a "Scan for incidents" button that runs
detection + investigation live, and an incident list linking to a full
drill-down report per incident (revenue decomposition, the Q&A investigation
tree, ruled-out segments, the narrative, and the Langfuse trace link) — see
`rca/web.py` and `rca/webapp/`.

## MCP server + LibreChat (chat interface)

`rca/mcp_server.py` exposes the validated pipeline as MCP tools
(`scan_for_incidents`, `investigate_incident`, `get_metric_timeseries`,
`list_metrics_and_dimensions`, `get_investigation`, `drill_deeper`) — a chat
client calling these gets the exact same grounded, traced diagnosis as the
CLI/dashboard, not a freeform guess.

```bash
rca mcp-serve   # http://0.0.0.0:8001/mcp -- or via docker compose, see above
```

`librechat/` wires this into [LibreChat](https://www.librechat.ai/) as the
chat UI, registering **two** MCP servers so both pre-built investigations and
open-ended SQL questions are grounded in real data:

- **`rca-investigator`** — this project's own pipeline (above), its own
  container (`rca-mcp` in `docker-compose.yml`).
- **`clickhouse`** — the official [ClickHouse MCP server](https://github.com/ClickHouse/mcp-clickhouse)
  (the "starting point" the problem statement names), running as its own
  container, for ad-hoc `list_databases` / `list_tables` / `run_select_query`
  follow-ups beyond the pre-built tools.

Brought up by the single `docker compose up -d --build --wait` above (or
`cd librechat && cp .env.example .env` and fill in the same values, if you
only want the LibreChat side without the dashboard).

Then open http://localhost:3080, sign up (local auth, no email verification
in this config), pick **Google → gemini-flash-lite-latest** as the model
(*not* the "Gemini" custom endpoint — see gotcha below), enable both MCP
servers from the paperclip/tools menu, and ask something like *"why did fill
rate drop between 2026-06-23 and 2026-06-25, and what segment is
responsible?"*

**Gotcha worth knowing:** this repo also registers a "Gemini" *custom*
(OpenAI-compatible) endpoint in `librechat.yaml`, hitting Gemini's
OpenAI-compat REST shim — fine for plain chat, but **multi-turn tool calls
fail on it** with a 400 error. Gemini's function calling requires a
`thought_signature` to be echoed back on the next turn, delivered via a
Gemini-specific field the generic OpenAI-compat client doesn't know to
preserve. The native **Google** endpoint (`GOOGLE_KEY`/`GOOGLE_MODELS` in
`librechat/.env`) uses LibreChat's first-party Gemini integration instead,
which handles this correctly — that's the one to pick for any MCP/tool-using
conversation.

### "Follow up in chat" — scoped to one incident, not the dataset

Every incident detail page has a **Follow up in chat →** button. Clicking it
opens a new LibreChat conversation, pre-seeded with that incident's id and
auto-submitted, using a second, deliberately narrow agent: **RCA Follow-up**.

This exists to keep hallucination surface small. The general chat path above
(`RCA Investigator` + the raw `clickhouse` MCP server) can run arbitrary SQL
against the full 9M-row `fact_events` table — powerful, but if a user's
follow-up question is answered by the model writing its own ad-hoc query,
every number in that answer is only as trustworthy as that query. The
follow-up flow avoids that entirely:

- **`investigations` table** (`sql/ddl.sql`): every investigation the
  pipeline runs — from the CLI, the dashboard, or chat — is persisted here
  (`pipeline._persist_investigation`), not just written to `out/*.json`.
- **`get_investigation(id)`**: reads one row from that table. Not a live
  query — a read of a result a deterministic pipeline run already validated.
- **`drill_deeper(id, dimension, value)`**: goes one level deeper into a
  named segment, but reuses that investigation's own baseline/current date
  window — it cannot be pointed at a different date range or a fresh
  dataset-wide scan.
- **The `RCA Follow-up` agent has only these two tools attached** — not
  `scan_for_incidents`/`investigate_incident` (which could start a fresh,
  broader investigation) and not the `clickhouse` MCP server at all. This is
  enforced by the agent's own tool list, not a system-prompt instruction the
  model could ignore: LibreChat's Agent composer shows no MCP-server toggle
  for this agent, because none beyond its two fixed tools are attached.

**Setting it up:** the agent already exists in this deployment
(`LIBRECHAT_FOLLOWUP_AGENT_ID` in `.env`). To recreate it elsewhere,
`librechat/create_followup_agent.py` drives the LibreChat UI with Playwright
end to end (`pip install playwright && playwright install chromium`, then
`python create_followup_agent.py`) and prints the new agent id to put in
`.env`. LibreChat's agent-creation endpoint rejects a plain HTTP client even
with valid auth (an origin/CSRF guard beyond simple headers), so this drives
the real UI rather than calling the API directly. If a future LibreChat UI
update breaks its selectors, recreate it by hand in ~2 minutes instead: Agent
Builder → name it, pick model **Google → gemini-flash-lite-latest** → open
Tools → Add → click the small **Configure** (gear) icon on the
`rca-investigator` card (not the card itself, which selects all its tools) →
check only `get_investigation` and `drill_deeper` → Create → copy the new
`agent_...` id from the agent picker into `.env`.

## Project layout

```
docker-compose.yml (repo root)   the whole stack: rca-dashboard, rca-mcp, librechat, mongodb, clickhouse-mcp
implementation/Dockerfile        one image for both rca-dashboard and rca-mcp (different CMD)
sql/ddl.sql             table definitions (raw + denormalized fact_events + investigations)
sql/build_fact.sql      one-time join that builds fact_events
scripts/load_data.sh    idempotent full data load (Cloud or local)
rca/metrics.py          metric + dimension definitions (matches metrics_glossary.md exactly)
rca/baseline.py         like-for-like baseline + anomaly detection
rca/attribution.py      revenue decomposition + Adtributor-style segment ranking + drill-down
rca/narrate.py          the one LLM call (Gemini), strictly grounded in computed numbers
rca/tracing.py          local JSON trace + Langfuse mirroring
rca/pipeline.py         orchestrates detect -> decompose -> drill-down -> narrate
rca/cli.py              `rca scan|investigate|auto|serve|mcp-serve`
rca/web.py              dashboard/incident-report API (FastAPI) + static file serving
rca/webapp/             dashboard homepage + incident detail page (vanilla HTML/JS/SVG)
rca/mcp_server.py       MCP tools wrapping the pipeline (incl. the scoped get_investigation/drill_deeper)
librechat/              librechat.yaml (MCP + Gemini wiring); docker-compose.yml lives at the repo root now
librechat/create_followup_agent.py   one-time setup for the scoped "RCA Follow-up" agent
traces/                 per-investigation trace trees (local, always written)
out/                    per-investigation JSON results (diagnosis + full evidence)
```

## Design notes / what was deliberately ruled out

- **Ratio metrics are always `sum/sum`**, never an average of per-row or
  per-day ratios, per `metrics_glossary.md`'s explicit warning about rollup
  correctness.
- **`event_time` is pinned to `DateTime('UTC')`** in the DDL. Leaving it
  timezone-less lets ClickHouse silently interpret the (naive) source
  timestamps in the *server's* local timezone — on a server not already set
  to UTC this shifts every day/hour boundary and quietly corrupts every
  seasonality comparison. Caught by comparing a min/max date query against
  the documented Jun 1 – Jul 5 range before writing any analysis code.
- **Uniform/broad-based moves are reported as such, not forced into a
  segment-level story.** The Jun 21 request-volume crash in the sample data
  has explanatory-power ≈ volume-share (lift ≈ 1.0) for every segment of
  every dimension — i.e. it dropped everywhere in exact proportion to
  existing traffic. `drill_down` returns `primary = None` in that case, and
  the narration says the drop was broad-based rather than naming whichever
  segment happened to be largest.
- **`vertical`/`campaign_type` are excluded from the drill-down for
  `requests`/`fill_rate`.** They're advertiser attributes — `''` until a
  request is filled (per `metrics_glossary.md`) — so grouping the pre-fill
  population by them produces a phantom "segment" (all unfilled traffic) with
  a rate structurally fixed at 0, which briefly showed up as a fabricated
  high-lift "finding" during testing. `attribution.dimensions_for_factor`
  fixes this by construction rather than filtering it post hoc; those two
  dimensions stay in scope for render_rate/ctr/ecpm/revenue, where every row
  in view is already filled.
