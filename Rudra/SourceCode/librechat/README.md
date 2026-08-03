# LibreChat — conversational layer over the concurrency data

Ask the concurrency model in natural language. The official
**[ClickHouse MCP server](https://github.com/ClickHouse/mcp-clickhouse)** runs as an
**SSE sidecar container** (`mcp/clickhouse`) and LibreChat connects to it over the compose
network — no `uv`/build inside LibreChat. The schema is injected via `serverInstructions`,
so the model queries `sonyliv.hist_minute_full` instead of guessing.

## Run
```bash
cp .env.example .env      # LLM key (GOOGLE_KEY), ClickHouse creds (CH_*), LibreChat secrets
docker compose up -d      # http://localhost:3080

# confirm the MCP sidecar connected to ClickHouse:
docker compose logs mcp-clickhouse | tail
# and that LibreChat picked up the tools:
docker compose logs api 2>&1 | grep -i 'tools' | tail
#   -> "Initialized with 1 configured server and 3 tools"  (list_databases, list_tables, run_query)
```

## Use it
1. Register the first user at **http://localhost:3080/register** (no default creds).
2. Pick the **Google / gemini-2.5-flash** model (or make an Agent and enable the **clickhouse** tools).
3. Ask — the `serverInstructions` already tell it how to model concurrency:
   - *"peak concurrency on 31 July?"* → runs SQL → **22,174**
   - *"peak concurrent viewers on ANDROID_PHONE for live content"*
   - *"average concurrency by video resolution"*

You'll see a **tool step running SQL** before the answer (not an instant guess).

## How it's wired
- `docker-compose.yml` — `mcp-clickhouse` (SSE on :8000, pointed at `CH_*`) + LibreChat + mongo + meilisearch.
- `librechat.yaml` — `interface.mcpServers.use: true`, `type: sse`, `url: http://mcp-clickhouse:8000/sse`, and the `serverInstructions` schema/rules.
- Creds go to the **sidecar's** environment (`CH_*` in `.env`); LibreChat never sees them.

## Hardening (optional)
Create a read-only ClickHouse user and point `CH_USER`/`CH_PASSWORD` at it:
```sql
CREATE USER llm_readonly IDENTIFIED BY '<strong>';
GRANT SELECT ON sonyliv.hist_minute_full TO llm_readonly;
GRANT SELECT ON sonyliv.content_raw TO llm_readonly;
ALTER USER llm_readonly SETTINGS readonly = 1, max_result_rows = 10000, max_execution_time = 30;
```
