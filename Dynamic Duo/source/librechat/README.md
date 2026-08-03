# librechat/ — the product surface (runbook)

The interactive flow from [ARCHITECTURE.md](../ARCHITECTURE.md): incidents, live
drill-downs, and follow-up SQL, all inside LibreChat. Stack: LibreChat + Mongo +
**rca-mcp** (custom: `list_incidents` / `investigate` / `investigate_window`) +
**mcp-clickhouse** (official, read-only user) + a local ClickHouse server.

## 1 · Configure

```bash
cd librechat
cp .env.example .env      # set OPENAI_API_KEY (chat model + narrator)
```

## 2 · ClickHouse up + data in

```bash
docker compose up -d clickhouse   # first boot creates rca db + rca_rw + librechat_ro
cd ..
CH_HOST=localhost CH_SECURE=0 CH_USER=rca_rw CH_PASSWORD=rca_rw_dev ./load.sh \
    --data-dir ../click-a-thon-2026/InMobi/data
```

`load.sh` runs the DDL (sql/00–07 stays idempotent), loads dims + 9M events through
the MV cascade, and prints the validation report — all checks must pass.

## 3 · Seed incidents + pre-fill diagnoses

The incident list comes from the detector's dev runs ("seed rows exist from dev
runs"), and every listed incident is then pre-investigated so LibreChat presents
stored diagnoses instantly — the chat's job on listed incidents is presentation;
`investigate_window` still runs live for ad-hoc questions:

```bash
export CH_HOST=localhost CH_SECURE=0 CH_TRANSPORT=http CH_USER=rca_rw CH_PASSWORD=rca_rw_dev
python3 -m detector.profiler        # measure seasonality per series (~1 min)
python3 -m detector.sweep           # score + classify + write rca.incidents
python3 -m agent.prefill            # batch-run the fixed sequence, chronologically
```

`agent.prefill` needs the narrator env too if you want LLM narratives in the
stored diagnoses (`NARRATOR_MODEL` + the matching key from `.env`, e.g.
`export NARRATOR_MODEL=gpt-5-nano OPENAI_API_KEY=...`); without a key it
stores the deterministic template narratives.

## 4 · The rest of the stack

```bash
cd librechat
docker compose up -d --build         # librechat, mongo, rca-mcp, mcp-clickhouse
docker compose logs -f rca-mcp mcp-clickhouse   # both should be serving HTTP
```

Open http://localhost:3080 and register a local account (registration is open,
local-only).

## 5 · Create the "RCA Analyst" agent (one-time, ~2 minutes)

1. In the chat UI pick the **Agents** endpoint → **Agent Builder** → new agent,
   name it **RCA Analyst**.
2. Model: OpenAI → `chat-latest` (the rolling ChatGPT-Instant alias; `gpt-5-nano`
   as the budget fallback), Anthropic → `claude-sonnet-5`, or Google →
   `gemini-3.1-flash-lite` / `gemini-2.5-flash` — whichever key you configured in `.env`.
   **The agent model MUST support function calling** — it drives the MCP tools.
   Gemma models (`gemma-4-*`) do NOT (generateContent only): they silently answer
   from thin air instead of investigating. Gemma is fine as the NARRATOR
   (`NARRATOR_MODEL` in `.env` — plain text) and for plain non-agent chats; never
   as the agent model.
3. Instructions: paste the block from [`agent/instructions.md`](agent/instructions.md)
   (everything below its `---`).
4. Tools: add the MCP tools from both servers — **rca** (`list_incidents`,
   `investigate`, `investigate_window`) and **clickhouse** (`run_query`,
   `list_tables`, `list_databases`).
5. Conversation starters:
   - `What incidents are there?`
   - `Why did fill rate drop June 23–25?`
   - `Something feels off with rewarded ads on Tuesday June 16 — check it.`
   - `Which apps were hit hardest by the June 23 incident?`
6. Save. Optionally share the agent to all users of the instance.

## 6 · Prove the flow

Walk [GOLDEN_QUESTIONS.md](GOLDEN_QUESTIONS.md) top to bottom in a fresh
conversation. That checklist **is** the checkpoint in the build order ("the
interactive flow works").

## ClickStack (HyperDX) — visualize the same ClickHouse + receive traces

Ships in this compose file; nothing extra to install. One shared ClickHouse: HyperDX
charts read `rca.*` directly, and the runner's OTLP spans land in `default.otel_traces`
via the in-stack collector.

1. `docker compose up -d hyperdx otel-collector hyperdx-seed` (or just `up -d` for all)
2. Open **http://localhost:8081** → register (first user creates the team)
3. Within ~5 s `hyperdx-seed` auto-provisions: the **Stack ClickHouse** connection,
   three sources (**Ad Metrics** = hourly rollup, **Incidents**, **Ad Events** =
   enriched rows), and the **RCA Overview** dashboard (metrics + per-dimension
   breakdowns + incident timeline/log). Set the time range to the data window
   (Jun 1 – Jul 6 2026 for the dev slice).
4. Traces: every investigation appears in HyperDX **Traces** as a tree —
   `investigate <incident_id>` root span (verdict + wall-clock) with one child per
   step carrying `rca.step_type`, `rca.decision`, `rca.metric`, `rca.scope`, and the
   exact SQL under `db.statement`. Searchable: `rca.metric:fill_rate`.
   The spans mirror the always-on `rca.investigation_steps` table — same trace id,
   stored on each diagnosis, so every verdict deep-links to its run.

## Troubleshooting

- **rca tools error "clickhouse http error 516"** — wrong `RCA_RW_PASSWORD` in
  `.env` vs what the clickhouse volume was initialized with. `docker compose down -v`
  resets everything (then reload data).
- **Loader fails with "Authentication failed … while pushing to view rca.mv_enrich"**
  — the dictionaries' loopback runs as the in-container `default` user; it must stay
  passwordless (never set `CLICKHOUSE_PASSWORD` on the clickhouse service; the
  loopback-only restriction lives in `clickhouse-users.xml`).
- **mcp-clickhouse has no tables** — data not loaded yet (step 2) or the
  `librechat_ro` user is missing (the init script only runs on first boot:
  `docker compose exec clickhouse clickhouse-client --password $CLICKHOUSE_PASSWORD
  --queries-file /docker-entrypoint-initdb.d/01-init.sh` won't work — run the SQL
  from `../sql/07_librechat_user.sql` manually instead).
- **LibreChat shows no MCP tools in the builder** — check
  `docker compose logs librechat | grep -i mcp`; both servers must initialize at
  boot. After changing `librechat.yaml`, restart the librechat service.
- **Investigations slow (>30 s)** — the runner is probably talking to
  `clickhouse local` (CH_HOST unset) or sweeps aren't hitting the rollup. Check
  rca-mcp env.
- **Reset the demo to the pre-filled state** (diagnoses feed baseline hygiene —
  q6 — so numbers depend on investigation order; the chronological pre-fill makes
  that order deterministic):
  ```bash
  for t in incidents investigation_steps diagnoses; do
    docker compose exec clickhouse clickhouse-client --user rca_rw \
      --password "$RCA_RW_PASSWORD" --query "TRUNCATE TABLE rca.$t"; done
  ( cd .. && CH_HOST=localhost CH_SECURE=0 CH_TRANSPORT=http CH_USER=rca_rw \
      CH_PASSWORD=$RCA_RW_PASSWORD python3 -m detector.sweep && \
      python3 -m agent.prefill )
  ```

## Cloud migration (the end-state env swap)

1. Run `../sql/07_librechat_user.sql` against the Cloud service with a real password.
2. Load: `CH_HOST=<cloud-host> CH_PASSWORD=... ./load.sh --data-dir ...`.
3. In compose: point `rca-mcp` (`CH_HOST`, `CH_SECURE=1`, `CH_HTTP_PORT=8443`,
   password) and `mcp-clickhouse` (`CLICKHOUSE_HOST`, `CLICKHOUSE_PORT=8443`,
   `CLICKHOUSE_SECURE=true`, new `LIBRECHAT_RO_PASSWORD`) at the Cloud host; drop the
   local `clickhouse` service. Nothing else changes.
