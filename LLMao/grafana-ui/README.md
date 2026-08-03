# [TEAM NAME]

## Track
SonyLIV

## Project
**Foreground-Only Concurrency** — counting how many people are *actually* watching, not just how many left the app open.

## Team Members
- [Name] ([GitHub handle])

## What it does
Streaming dashboards usually count a viewer as "watching" for the entire time their session is open — even if they've backgrounded the app, paused the video, or their connection went quiet. That overcounts the audience and skews decisions like ad load and capacity planning.

This project builds a pipeline in ClickHouse that looks at each session's actual signals — heartbeats, pause/play, app backgrounded/foregrounded — and keeps only the stretches of time a session was genuinely active in the foreground. Concurrency (how many sessions are active at once) is then computed from those cleaned-up stretches, sliceable by platform, country, content, and video type, at minute/hour/day grain.

It's built to stay fast and correct even as new data keeps arriving: sessions that are still open get updated in place as new heartbeats land, instead of the whole dataset being reprocessed.

On top of the numbers, we added a chat interface (LibreChat) so anyone can just ask a question like *"what was peak concurrency on Android in the last hour?"* and get an answer pulled live from the dashboards.

## Hosted Demo
[LINK]

## Demo Video
[LINK]

## Architecture

![Architecture diagram](docs/architecture.png)

Data flows through the pipeline in three stages, all inside ClickHouse:

**1. Raw layer** — Every raw event (session start/end, heartbeats, play/pause, app backgrounded/foregrounded) and all content metadata land in ClickHouse untouched, exactly as they arrive.

**2. Session state layer** — A materialized view watches the raw events for each session and works out, moment by moment, whether that session was actually active in the foreground or not (for example: a heartbeat with no "backgrounded" event since means active; an "app backgrounded" event with no matching "foregrounded" means inactive; a long gap with no heartbeat means inactive). This produces two things:
   - the **current status** of every session that's still open (so a live session's state is always queryable), and
   - a **closed active interval** — a clean start/end pair — every time a session finishes being active.

**3. Active-intervals & concurrency layer** — Closed active intervals are collected into their own table, which is the single source of truth for "when was this session really being watched." From there, two pre-computed, ready-to-query tables are built off it:
   - a **minute-by-minute concurrency table**, grouped by time and by filters like platform/country/content, so dashboards can just read a number instead of recomputing overlaps; and
   - a **delta table** (a "+1 when a session becomes active, −1 when it stops" ledger), which lets concurrency for *any* custom time range or grouping be reconstructed instantly with a running total, without rescanning raw sessions.

Dashboards (Grafana) and the chat interface (LibreChat, via a Grafana MCP connector) both read only from these pre-computed tables — never from raw events — which is what keeps queries fast regardless of how much raw data has piled up.

## How we built it
- **ClickHouse (Cloud)** — the only datastore. Raw ingestion, the active-interval logic, and both concurrency serving tables all live here, wired together with materialized views so new data pushes forward automatically instead of needing manual reprocessing.
- **Grafana** — dashboards for the concurrency curve, filters, and a side-by-side "naive count vs. corrected count" view to make the impact of excluding backgrounded time visible.
- **LibreChat + a Grafana MCP connector, behind a LiteLLM proxy** — a chat interface where a plain-English question about concurrency gets turned into a query against the same dashboards, so no one needs to write SQL to get an answer.
- Everything runs locally via Docker Compose (LibreChat + the chat connector) alongside a local Grafana instance pointed at the ClickHouse Cloud service.

## How to run it

**Prerequisites:** a ClickHouse Cloud service with the dataset loaded, Docker, and this repo.

1. **Configure ClickHouse + Grafana** — copy your ClickHouse Cloud credentials into `.env` at the repo root (host, port, user, password, database, and the two serving table names).
2. **Start Grafana:**
   ```bash
   ./start.sh
   ```
   This launches the bundled Grafana instance on `http://localhost:3000`, pre-wired to the ClickHouse datasource and the dashboards in `dashboards/`.
3. **Create a Grafana service account token** (Editor role) and add it to `.env` as `GRAFANA_SERVICE_ACCOUNT_TOKEN`, along with your LiteLLM proxy URL/key.
4. **Start the chat interface:**
   ```bash
   cd librechat
   docker compose up -d
   ```
   This brings up LibreChat and the Grafana connector container together. Once running, ask concurrency questions directly in the chat.
5. Open Grafana at `http://localhost:3000` for the dashboards, or LibreChat's URL for the chat interface.
