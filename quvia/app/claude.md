# AeroOps/AdOps root-cause analyst — project context

InMobi Click-a-thon 2026 submission. ClickHouse Cloud does all analysis;
a Docker-based dashboard (FastAPI backend + vanilla JS/Chart.js frontend)
visualizes results and lets a judge explore incidents interactively, with
an optional embedded LibreChat for open-ended follow-up questions.

## Database: migrated from `ganesh` to `py`

The project **pivoted mid-hackathon** from the original `ganesh` pipeline
(11 dimensions, `dim_metrics_1h`, exact-day-of-week baseline) to a richer
`py` database pipeline. **`py` is what the live dashboard actually reads
today** — treat any `ganesh.*` reference as historical/superseded unless
stated otherwise.

### `py` schema
```
py.agg_<dimension>_<freq>       SharedSummingMergeTree, plain columns
                                  (requests, fills, impressions, revenue),
                                  one physical table PER dimension x freq
                                  (no single shared "dim_metrics" table)
py.agg_overall_1h               same shape, segment = 'all' (no breakdown)
        |
py.anomaly_<dimension>_<freq>   precomputed z-scores + pct-changes for
                                  requests/revenue/fill_rate/ecpm — only
                                  rows that crossed threshold
py.anomaly_overall_1h           same, segment = 'all'
```
freq ∈ `{1m, 5m, 1h, 6h, 1d}` — the dashboard only exposes **1h and 6h**
(`db.FREQUENCIES`) so charts stay a reasonable size. The 6h tables only
have rows at hour 0/6/12/18 — `snap_bucket_to_freq()` in `db.py` snaps an
arbitrary incident timestamp down to its 6h block before querying.

### The 9 dimensions (`db.DIMENSIONS`)
`ad_format, campaign_type, category, country, device_model, os_version,
publisher_tier, region, vertical`

Unlike `ganesh`, **`py` has no `app_id` or `advertiser_id` breakdown.**
`"overall"` (single-segment `'all'` pseudo-dimension, `db.TREND_DIMENSIONS`)
is selectable in the UI but deliberately excluded from `DIMENSIONS` so it
never gets ranked alongside the real 9 in contribution/radar.

### Rolling-window baseline (replaces `ganesh`'s exact-dow baseline)
```sql
PARTITION BY segment, toDayOfWeek(bucket) IN (6, 7), toHour(bucket)
ORDER BY bucket ASC
ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
```
i.e. weekday-or-weekend + hour-of-day, **not** exact day-of-week. Every
live query in `db.py` replicates this exact partition (`_WINDOW_PARTITION`
/ `_WINDOW`) to match what `py`'s own materialized views already computed
— diverging from it would silently disagree with `py.anomaly_*`'s numbers.

### Formulas (unchanged concepts, now computed against `py`)
```
pct_dev  = (revenue_actual - revenue_expected) / revenue_expected
robust_z = abs(revenue_actual - revenue_expected) / stddev_over_window
flagged if robust_z > 3
delta = revenue_now - revenue_expected                     (per segment)
pct_of_total_delta = delta / SUM(delta) OVER (PARTITION BY dimension_name)
fill_rate = fills / requests
ecpm      = revenue / impressions * 1000
```

**Sign bug in `pct_of_total_delta` (found and fixed):** when every segment
in a dimension moves the same direction (e.g. all decline together), the
ratio `delta / sum(delta)` is negative/negative → comes out **positive**
even though the segment itself fell. Fixed with a `signed_concentration()`
helper (`narrate.py`'s `_signed_concentration`, `app.js`'s
`signedConcentration`) that re-signs the magnitude to match the segment's
own `delta` sign. Applied everywhere a concentration % is shown: diagnosis
text, drill-down table, radar chart, LibreChat prompt export.

## Architecture

```
docker-compose.yml
  dashboard        FastAPI (backend/app) + static frontend, port 8000
  clickhouse-mcp    official ClickHouse MCP server (SSE), port 8001 —
                     feeds LibreChat's MCP tool, see below
```

### Backend (`backend/app/`)
- `db.py` — all ClickHouse access. Thread-local client (`get_client()`) —
  a single cached client shared across FastAPI's thread pool throws
  "concurrent queries within the same session"; one client per thread
  fixes it. Key functions: `get_detection`, `get_day_trend`,
  `get_contribution` (per-dimension UNION ALL, snapped to freq),
  `get_dimension_series` (trend chart + anomaly points for the multi-line
  chart), `snap_bucket_to_freq`.
- `narrate.py` — deterministic diagnosis text generator (`build_diagnosis`).
  No LLM involved; every sentence reads a number already computed by
  ClickHouse. This is the "guaranteed correct" text; the AI summary
  features below are a separate, clearly-labeled addition on top.
- `llm.py` — Claude Haiku 4.5 narration, **constrained to phrase only
  numbers already present in the payload it's given, never invent one or
  speculate about causes.** Two entry points:
  - `summarize_drilldown(dimension_name, rows)` — one dimension's
    drill-down rows.
  - `summarize_incident(detection, factors, contribution)` — the full
    incident (all 9 dimensions' contribution + factors + KPIs).
- `librechat_auth.py` — server-to-server login against LibreChat's own
  `/api/auth/login` (see "LibreChat integration" below).
- `main.py` — FastAPI routes (see "API endpoints" below) + two pieces of
  request-level plumbing:
  - `no_cache_static` middleware — always revalidate the static frontend
    (this app is under active development; stale cached JS is a real risk).
  - `redirect_0000_to_localhost` middleware — `http://0.0.0.0:8000` (what
    `docker ps` prints for the port mapping) is an easy accidental
    copy-paste, but cookies are matched by exact hostname, so browsing
    there instead of `localhost` silently breaks the LibreChat auto-login
    cookie trick. Redirects `0.0.0.0` → `localhost` automatically.

### API endpoints
```
GET  /api/health
GET  /api/anomalies
GET  /api/incident/{bucket}?freq=1h|6h
GET  /api/dimension/{bucket}/{dimension_name}?freq=1h|6h
GET  /api/dimension-trend/{dimension_name}?start=&end=&freq=&metric=
GET  /api/data-range
POST /api/summarize-dimension     {dimension_name, rows}      -> {summary, available}
POST /api/summarize-incident      {detection, factors, contribution} -> {summary, available}
POST /api/librechat-auto-login    (no body)                   -> {ok}
```
`summarize-*` endpoints take the **exact rows/objects the frontend already
fetched and rendered** (not a fresh ClickHouse query) — the AI summary can
never drift from what's on screen, same traceability guarantee as every
chart.

## Frontend (`frontend/`)

Single-page vanilla JS + Chart.js, dark theme (`#0d0e10` surface,
JetBrains Mono for numbers, Inter for labels, `#4caf6e` green /
`#e2574c` red for positive/negative).

**Layout, top to bottom:**
1. **Header** — title + live "Pipeline healthy" badge (real `GET
   /api/health` check, not static).
2. **Trend panel** (`main-trend-panel`, landing view, defaults to
   "Overall") — Category dropdown (9 dimensions + Overall), Y-Axis metric
   dropdown (revenue/requests/fill_rate/ecpm), calendar date-range picker,
   1h/6h freq toggle, multi-line Chart.js chart (one line per segment).
   Anomaly points are **colored by severity, not just flagged/not**: a
   3-tier scale keyed on `|z|` (from `anomaly_<dim>_<freq>.z_<metric>`),
   anchored on the same `z=3` line used elsewhere to flag an hour —
   `|z|<1.5` yellow, `1.5≤|z|<3` orange-red, `|z|≥3` darkest red. Clicking
   a point loads that incident.
3. **Incident view** (hidden until an anomaly is clicked):
   - KPI strip, Diagnosis card (deterministic text) + **"Generate AI
     summary" button** (on-demand, not automatic — avoids a Claude call on
     every incident click) using `summarize_incident`.
   - Row: Full-day trend | Factor decomposition (compact tiles) — 80/20
     split with Diagnosis in a separate row above (`grid-diagnosis-factor`,
     `4fr 1fr`).
   - Row: (same trend chart) | **Category impact radar** — one axis per
     dimension, value = signed % of that dimension's top-segment delta,
     point color red/green by sign. **Clicking a radar point/axis drills
     into that dimension** (same `setDimension()` used by the dropdowns).
   - **Drill-down panel** (promoted to a primary section, not a popup) —
     its own Category dropdown (synced two-way with the trend panel's,
     minus "Overall" since there's nothing to drill into), bar chart
     (slim 14px bars, rounded corners, gradient fill), table, and an
     **AI summary box** below the table (`summarize_drilldown`).
4. **LibreChat panel** — slide-in iframe, see integration notes below.

**Known gotcha already fixed:** drill-down table used
`r.ecpm_now.toFixed(2)` unguarded — the catch-all "unfilled requests"
segment has `ecpm_now: null` (impressions=0 → division is null), which
threw and silently aborted the *entire* table's `innerHTML` render (not
just one row). Fixed with `!= null` guards on `ecpm_now`/`fill_rate_now`,
rendering `—` instead.

## LibreChat integration

LibreChat runs as its own separate stack at
`/Users/ganeshelango/Data/git/librechat/LibreChat/LibreChat` (own
docker-compose, own MongoDB, own auth) — not part of this project's
docker-compose. Three things wired up:

### 1. No-login iframe embed
A shared demo account (`dashboard-demo@clickathon.local`, LibreChat's own
user model) is pre-registered. Clicking "Ask LibreChat" first calls this
dashboard's `POST /api/librechat-auto-login`, which:
1. Logs into that account **server-to-server** from the backend container,
   via `http://host.docker.internal:3080` (not `localhost` — inside a
   container, `localhost` means the container itself).
2. Forwards LibreChat's `Set-Cookie` headers onto the browser's response.

This works because **cookies are scoped by hostname only, not port** —
both this dashboard (`localhost:8000`) and LibreChat (`localhost:3080`)
share the hostname `localhost` in local dev, so a cookie this backend sets
is sent by the browser to LibreChat's origin too. LibreChat's own client
bootstrap then silently exchanges that cookie for a session via its
`/api/auth/refresh`, skipping its sign-in screen. **Breaks if you browse
the dashboard via `127.0.0.1` or a LAN IP instead of `localhost`** (see the
`redirect_0000_to_localhost` middleware above for the most common case of
this).

Credentials (`LIBRECHAT_EMAIL`, `LIBRECHAT_PASSWORD`, `LIBRECHAT_INTERNAL_URL`)
live in this project's `.env`, used server-side only.

### 2. ClickHouse MCP server, always available
LibreChat's own container has **no C compiler**, so running
`uvx mcp-clickhouse` in-process via stdio fails building the `lz4` wheel
from source. Instead it runs as its **own container** in *this* project's
`docker-compose.yml` (service `clickhouse-mcp`, official
`ClickHouse/mcp-clickhouse`, `python:3.12-slim`), over SSE
(`CLICKHOUSE_MCP_SERVER_TRANSPORT=sse`, port 8001), pointed at the `py`
database. LibreChat's `librechat.yaml` (at the LibreChat repo root, bind-
mounted via `docker-compose.override.yml` — **not mounted by default**,
only `.env`/images/uploads/logs/skill are) references it:
```yaml
mcpSettings:
  allowedDomains: ['host.docker.internal']   # SSRF default-deny otherwise blocks it
interface:
  defaultPinnedTools: ['mcp']                # keeps the MCP dropdown visible by default
mcpServers:
  clickhouse:
    type: sse
    url: http://host.docker.internal:8001/sse
```
**Pinning the dropdown ≠ enabling the server for a conversation** — a user
(or the demo script) still has to toggle "clickhouse" on via the
composer's MCP Servers menu per chat. Watch for a stale "Needs Auth" stub
entry if the server failed to init once before a config fix — the working
entry shows as "clickhouse, Connected".

### 3. Claude Sonnet 5 as the hard default model
`librechat.yaml`'s `modelSpecs.list` includes one entry with `default:
true` (admin override, beats any prior user choice), `preset: {endpoint:
anthropic, model: claude-sonnet-5}`. Requires `ANTHROPIC_MODELS` in
LibreChat's own `.env` to include `claude-sonnet-5` (was commented out by
default — uncommented it) so the model id is recognized.

## What's NOT built yet
- **Orchestration loop** — drill-down/AI-summary generation is still
  triggered by a human click per incident, not an automated sweep over
  `anomaly_overall_1h` with a stopping rule.
- **Langfuse tracing** — required for the hackathon's traceability
  scoring, not wired in.
- **Two-way cross-tab** — is `campaign_type=CPM` and `country=US`/
  `region=NAM` the same effect seen twice, or independent? Still an open
  question, never actually run.

## Design rule that matters for judges
Every number on every chart (including the AI summary boxes) must trace
back to a real ClickHouse query with no client- or LLM-invented math
beyond formatting. The AI summary endpoints enforce this by construction —
they're only ever handed the JSON the dashboard already fetched and
rendered, with an explicit system-prompt instruction never to invent a
number or a root cause not present in that JSON.
