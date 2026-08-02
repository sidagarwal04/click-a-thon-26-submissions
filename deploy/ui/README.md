# Investigation UI

Copy `.env.example` to `.env`, set Azure Blob Storage, ClickHouse, and the LibreChat Agents API credentials, then run:

```bash
docker compose up --build -d
```

The service listens privately on `127.0.0.1:8090`. Place it behind the host reverse proxy.
An Nginx virtual-host template is included at
`nginx/clickathon26investigations.nannan.in.conf`; it serves
`clickathon26.nannan.in`. Set its TLS certificate with
Certbot after installing it.

The upload endpoint persists a queued investigation and returns immediately. The
separate `instrumentation-runner` service then calls LibreChat's authenticated
`/api/agents/v1/chat/completions` endpoint with a persisted `agent_<id>` and
records the result; polling `/api/investigations/{id}` reads that durable state.
The UI web process never holds an instrumentation run. It attaches no function
tools and never downloads, reads, or queries investigation data after upload.
The persisted workflow agent owns the fixed instrumentation → analytics →
aggregate analyst → evidence reviewer → context → finalizer chain and executes
its configured MCP tools inside the LibreChat runtime.
`LIBRECHAT_AGENTS_API_KEY` must be a LibreChat API key that can use that agent;
it is not the OpenAI provider key.
