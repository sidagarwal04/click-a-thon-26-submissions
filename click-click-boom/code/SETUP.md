# Setup — Atlys agentic analytics pipeline

Two pieces: `atlys-agents/` (our code — committed to this repo) and a local `LibreChat/`
instance (a clone of the upstream project, **not committed** — too large, third-party,
and config-only for us). This doc gets a fresh machine to the same state we're at.

No secrets are committed anywhere. Every `.env` file below is gitignored; use the
`.env.example` templates and fill in real values locally.

---

## 0. Prerequisites

- **Python 3.11+** — `clickhouse-connect` needs 3.9+; if your default `python3` is
  older (check with `python3 --version`), install 3.11 via `pyenv install 3.11.0`.
  `atlys-agents/.python-version` pins this automatically once you're inside the dir.
- **Docker Desktop**, running.
- A **ClickHouse Cloud** service with the `atlys` database already loaded (see
  `click-a-thon-2026-main/Atlys/data/load.sh` in the hackathon package — clone that
  repo with `git clone` if the parquet files are Git LFS pointers, not zip-download).
- A **Langfuse Cloud** project (cloud.langfuse.com or a regional host like
  us.cloud.langfuse.com) — get public/secret keys from project settings.
- An LLM provider API key with actual credit/quota (OpenAI or Anthropic). Verify it
  works with a bare `curl` against the provider's API directly before assuming
  LibreChat config is broken — see gotcha #3 below, this exact failure mode bit us.

---

## 1. `atlys-agents/` — the agent/orchestrator codebase

```bash
cd atlys-agents
python3 -m venv .venv        # use pyenv's 3.11.0 python3 if your system default is older
.venv/bin/pip install -r requirements.txt

cp .env.example .env
# fill in .env:
#   CLICKHOUSE_HOST / CLICKHOUSE_PASSWORD  — your ClickHouse Cloud service
#   LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_HOST
#   LIBRECHAT_URL / LIBRECHAT_API_KEY / LIBRECHAT_AGENT_*  — filled in during step 2
```

Bootstrap the agent metadata layer and verify each piece independently:

```bash
.venv/bin/python scripts/init_db.py             # creates agent_meta DB + 6 tables
.venv/bin/python scripts/seed_context.py        # seeds the 31-section context layer
.venv/bin/python scripts/smoke_test_tracing.py  # proves Langfuse wiring works
.venv/bin/python scripts/smoke_test_perf_tool.py  # proves perf_tool against real atlys data
```

`smoke_test_tracing.py` prints a trace URL — open it and confirm you see a root span
with a nested child span. `smoke_test_perf_tool.py` prints a full perf comparison
JSON — confirm it completes without error and reports a `winner`.

---

## 2. LibreChat — local instance, Agents API enabled

```bash
cd ..
git clone https://github.com/danny-avila/LibreChat.git
cd LibreChat
cp .env.example .env
cp librechat.example.yaml librechat.yaml
```

### 2a. Enable remote agents in `librechat.yaml`

Find the commented `remoteAgents:` block under `interface:` and uncomment/set:

```yaml
interface:
  agents:
    use: true
    create: true
  remoteAgents:
    use: true
    create: true
    share: false
    public: false
```

### 2b. Mount the config file into the container (gotcha #1 below)

`docker-compose.yml` only bind-mounts `.env` by default — `librechat.yaml` is silently
ignored unless you add an override. Create `docker-compose.override.yml`:

```yaml
services:
  api:
    volumes:
      - type: bind
        source: ./librechat.yaml
        target: /app/librechat.yaml
```

### 2c. Fill in `.env`

```
UID=<your `id -u`>
GID=<your `id -g`>
ADMIN_PANEL_SESSION_SECRET=<openssl rand -hex 32>
ANTHROPIC_API_KEY=...   # and/or
OPENAI_API_KEY=...
```

### 2d. Bring it up

```bash
docker compose up -d
```

Verify: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3080/` → `200`.
Admin panel on `:3000` needs `ADMIN_PANEL_SESSION_SECRET` set or it crash-loops.

---

## 3. Register an account, create the 4 agents, get an Agents API key

**Fast path**: register manually (one curl call below), put the admin email/password
into `atlys-agents/.env` (`LIBRECHAT_ADMIN_EMAIL`/`LIBRECHAT_ADMIN_PASSWORD`), then run
`atlys-agents/.venv/bin/python agents/create_agents.py` — it logs in, creates all 4
agents from `agents/prompts.py`, generates an Agents API key if you don't have one
yet, and writes every ID back into `.env` automatically. Re-run it any time you edit a
prompt in `agents/prompts.py` — it creates fresh agents (LibreChat doesn't have an
upsert-by-name; old ones are left in place, harmless, or delete via `DELETE /api/agents/:id`).

The manual steps below are what `create_agents.py` does under the hood — useful if
you need to debug it or create a one-off agent by hand. **Always send a real
`User-Agent` header** (gotcha #4) or you'll get auto-banned.

```bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# Register — first registered user becomes ADMIN automatically
curl -s -A "$UA" -X POST http://localhost:3080/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name":"...", "email":"...", "password":"...", "confirm_password":"..."}'

# Log in — JWT expires in ~15 min, re-run this if calls start failing
curl -s -A "$UA" -c /tmp/lc_cookies.txt -X POST http://localhost:3080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"...", "password":"..."}' -o /tmp/lc_login.json
JWT=$(python3 -c "import json; print(json.load(open('/tmp/lc_login.json'))['token'])")

# Create an agent — note: /api/agents (NOT /api/agents/v1 — gotcha #2),
# and provider is case-sensitive: "openAI" not "openai" (gotcha #5)
curl -s -A "$UA" -X POST http://localhost:3080/api/agents \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"name":"...", "provider":"openAI", "model":"gpt-4o-mini",
       "model_parameters":{"model":"gpt-4o-mini"}, "instructions":"..."}'
# -> save the returned "id" (agent_xxx) into atlys-agents/.env as one of the
#    LIBRECHAT_AGENT_* variables

# Generate a remote-agents API key — note the hyphen: /api/api-keys
curl -s -A "$UA" -X POST http://localhost:3080/api/api-keys \
  -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
  -d '{"name": "orchestrator"}'
# -> save the returned "key" into atlys-agents/.env as LIBRECHAT_API_KEY
```

Verify with the actual invocation path (`/v1/responses`, API-key auth, not JWT):

```bash
curl -s -X POST http://localhost:3080/api/agents/v1/responses \
  -H "Authorization: Bearer <LIBRECHAT_API_KEY>" -H "Content-Type: application/json" \
  -d '{"model": "<agent_id>", "input": "Reply with exactly the word: pong"}'
```

Or from Python: `atlys-agents/.venv/bin/python -c "from librechat_client import call_agent; print(call_agent('<agent_id>', 'ping').output_text)"`

---

## 4. MCP tool servers — real tool access for the agents

Two standalone MCP servers (not spawned by LibreChat — its container has no Python)
give the agents genuine tool-calling loops instead of pre-bundled context dumps:

```bash
cd atlys-agents
nohup .venv/bin/python mcp_servers/context_server.py > /tmp/context_mcp.log 2>&1 &   # :8100
nohup ./mcp_servers/run_clickhouse_mcp.sh > /tmp/ch_mcp.log 2>&1 &                     # :8101, official mcp-clickhouse, read-only, scoped to `atlys`
```

Registered in `LibreChat/librechat.yaml` as `mcpServers.atlys_context` /
`atlys_clickhouse`, pointing at `http://host.docker.internal:PORT/mcp` (Docker's
bridge to the host). Also requires `mcpSettings.allowedDomains: [host.docker.internal]`
— LibreChat's SSRF protection blocks unlisted domains by default (gotcha #8 below).

Restart LibreChat's `api` container after changing `librechat.yaml` — bind-mounted
file edits do **not** hot-reload; `docker compose up -d` won't recreate a running
container just because the mounted file changed, you need `docker compose restart api`.

Verify: `docker logs LibreChat | grep -A5 '\[MCP\]\[atlys'` should show both servers
initialized with their tool lists. Then re-run `agents/create_agents.py` — it attaches
each agent's tools from `agents/prompts.py`'s `AGENTS[...]["tools"]`.

## 5. ClickHouse Agent Skills (official, encodes exactly the bugs we kept hitting)

```bash
git clone --depth 1 https://github.com/ClickHouse/agent-skills.git /tmp/agent-skills
mkdir -p LibreChat/skill
cp -r /tmp/agent-skills/skills/clickhouse-best-practices LibreChat/skill/
```

In `librechat.yaml`, add `"skills"` to the agents capabilities list (not in the
default set):

```yaml
endpoints:
  agents:
    capabilities: ["deferred_tools", "execute_code", "file_search", "actions", "tools", "skills"]
```

`docker compose restart api`, then check `docker logs LibreChat | grep deploymentSkills`
— should show `Loaded 1 deployment skill(s) from /app/skill`. Finally, set
`skills_enabled: true` on the agents that should use it (currently
`instrumentation_proposer` and `context_reviewer` — see `agents/prompts.py`'s
`AGENTS` dict) and re-run `agents/create_agents.py`.

Verified working: asked `instrumentation_proposer` directly whether Nullable
columns belong in an ORDER BY — it called `skill` then `read_file` (×2) and cited
`schema-types-avoid-nullable` by name in its answer.

---

## 6. ClickStack Observability — traces & logs to ClickHouse Cloud (OPTIONAL)

**This step is completely optional.** Agents work normally without it - they always send traces to Langfuse. ClickStack adds a secondary destination (ClickHouse Cloud) for centralized observability and querying.

If configured, all agent traces and logs are automatically sent to ClickHouse Cloud via the ClickStack OpenTelemetry collector. This provides centralized observability with cross-references to Langfuse traces.

### Start the collector:

```bash
cd atlys-agents
docker-compose up -d
```

This starts the ClickStack OTEL collector on:
- Port 4317 (OTLP gRPC)
- Port 4318 (OTLP HTTP)

The collector automatically:
- Receives all OpenTelemetry traces from the Python agents
- Forwards them to your ClickHouse Cloud instance
- Stores traces in `otel_traces`, `otel_logs`, and `otel_metrics` tables
- Preserves Langfuse trace IDs for cross-referencing

### Verify it's working:

```bash
docker-compose ps        # check collector is running
docker-compose logs -f   # watch collector logs
```

### Query traces in ClickHouse:

```sql
SELECT
    TraceId,
    ServiceName,
    SpanName,
    Timestamp,
    SpanAttributes['langfuse_url'] as langfuse_url
FROM default.otel_traces
WHERE ServiceName = 'atlys-agents'
ORDER BY Timestamp DESC
LIMIT 100;
```

Every trace includes the Langfuse URL in its attributes, allowing you to correlate between ClickHouse and Langfuse views.

### Stop the collector:

```bash
docker-compose down
```

---

## Gotchas hit while setting this up (save yourself the debugging time)

1. **`librechat.yaml` not mounted by default.** Silent — server logs
   `ENOENT: no such file or directory, open '/app/librechat.yaml'` and just runs with
   defaults (remoteAgents stays off). Fix: step 2b above.
2. **Agent creation is `POST /api/agents`, not `/api/agents/v1`.** The `/v1` prefix is
   reserved for the remote-invocation endpoints (`/v1/responses`, `/v1/chat/completions`),
   which use API-key auth, not your JWT session. Hitting `/api/agents/v1` with a JWT
   routes into the wrong handler and returns a misleading `"Invalid API key"` error.
3. **A "provider key invalid" error from LibreChat isn't proof the key is bad.**
   Test the raw key directly against the provider's API first
   (`curl https://api.anthropic.com/v1/messages ...` / `api.openai.com/v1/chat/completions`).
   We hit this exact case: an Anthropic key that authenticated fine but had zero
   credit balance — the error only showed up as an opaque failure inside LibreChat.
4. **`curl` requests get auto-banned as `non_browser` violations.** LibreChat's
   anti-abuse middleware penalizes requests lacking browser-like headers; 20
   violations triggers a 2-hour ban. Always send a `User-Agent` header on scripted
   calls. If you do get banned (self-hosted local instance, so this is safe):
   ```bash
   docker exec chat-mongodb mongosh LibreChat --quiet --eval \
     "db.logs.deleteMany({key: {\$regex: '^(BANS|ban):'}})"
   ```
5. **Provider names are case-sensitive and not what you'd guess.** It's `openAI`
   (capital AI), not `openai`. Source of truth:
   `packages/data-provider/src/schemas.ts` → `EModelEndpoint.openAI = 'openAI'`.
6. **JWTs expire in ~15 minutes.** If a previously-working curl script starts failing
   with auth errors, re-login before debugging anything else.
7. **The Agents API key uses the endpoint `/api/api-keys`** (hyphenated) — `/api/apiKeys`
   404s.
8. **MCP servers need an explicit domain allowlist.** `mcpServers` entries pointing at
   `host.docker.internal` (or anywhere non-standard) fail with `Domain "..." is not
   allowed` unless `mcpSettings.allowedDomains` in `librechat.yaml` includes it — SSRF
   protection, off by default meaning nothing is allowed, not everything.
9. **MCP HTTP transport tool names have a specific suffix format**: `{tool}_mcp_{serverName}`
   (e.g. `run_query_mcp_atlys_clickhouse`) — this is what goes in an agent's `tools`
   array; LibreChat resolves `mcpServerNames` from it server-side automatically.
10. **`gpt-5.6` + function tools + reasoning fails on Chat Completions** unless
    `reasoning_effort` is set to an actual level (`low`/`medium`/...), not `"none"` —
    LibreChat only auto-routes gpt-5.6 through the upstream Responses API (which
    supports tools+reasoning together) when reasoning_effort is a real level. Setting
    it to `"none"` avoids the routing but also gives up reasoning depth — set a real
    level instead, don't disable reasoning to dodge this.
11. **Editing `mcp.client.streamable_http.streamable_http_client`'s context manager**:
    it can yield either `(read, write)` or `(read, write, extra)` depending on which
    server implementation you're talking to (our own MCPServer vs. FastMCP-based
    mcp-clickhouse) — unpack defensively or check the SDK version per-server.

---

## What's committed vs. not

- **Committed:** `atlys-agents/` (all code, SQL, scripts), this file, `team_plan/PLAN.md`,
  `table-analysis/`.
- **Not committed** (gitignored): `atlys-agents/.env`, `atlys-agents/.venv/`,
  `LibreChat/` in its entirety (clone fresh per step 2 — it's a large third-party repo
  and all our changes to it are config-only, fully reproducible from this doc).
