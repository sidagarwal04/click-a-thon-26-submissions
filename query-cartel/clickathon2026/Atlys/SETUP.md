# Atlys Copilot — Setup Guide (Local & Production)

How to get the full pipeline running: ClickHouse Cloud (the only datastore), the FastAPI
orchestration service (MCP server + REST API + 3 agents), the React UI (served by FastAPI),
LibreChat (chat backend / LLM routing), and Langfuse tracing. Everything below is verified
against the code in this repo.

> **TL;DR — demo on one laptop:** `cp .env.example .env` → fill keys → venv + `pip install` →
> `python data/load_python.py` (loads the 8 funnel tables) → `cd ui && npm ci && npm run build` →
> `docker compose up -d` (mongo + LibreChat + FastAPI/UI at `:8000`) → open
> `http://localhost:8000` and chat.

---

## 0. What you need (credentials)

| Service | Env vars | Required? | Where to get it |
|---|---|---|---|
| ClickHouse Cloud | `CH_HOST`, `CH_USER`, `CH_PASSWORD`, `CH_SECURE` | ✅ mandatory | ClickHouse Cloud console → service → **Connect** → "HTTPS" tab gives `https://<host>:8443` (that exact URL works as `CH_HOST`) |
| Z.ai (GLM) | `ZAI_API_KEY` | ✅ mandatory for chat | [Z.ai console](https://platform.z.ai) → API keys |
| Langfuse | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL` | optional | Langfuse Cloud project → Settings → API keys. **Absent → the pipeline runs with a `NullTracer`** (no crash, no traces) |
| LibreChat | `CREDS_KEY`, `CREDS_IV`, `JWT_SECRET`, `JWT_REFRESH_SECRET` | ✅ mandatory for chat (else LibreChat crashes) | `openssl rand -hex 32` for `CREDS_KEY`/`JWT_SECRET`/`JWT_REFRESH_SECRET`, `openssl rand -hex 16` for `CREDS_IV` |

**ClickHouse:** create the service, allowlist your IP (or `0.0.0.0/0` for a demo), and note the
**password** (not the sha256 hash) from the console. There is **nothing to provision** beyond the
service itself — the pipeline creates the `atlys` database, the `meta.*` tables, and feature
tables itself. LibreChat's MongoDB is bundled in the compose file (no external Mongo).

---

## 1. Local setup (dev machine)

### 1.1 Python environment

```bash
# repo root
python3 -m venv .venv
source .venv/bin/activate
pip install -r Atlys/service/requirements.txt
# + the data loader needs pyarrow (dev tooling only, not a service dep):
pip install pyarrow clickhouse-connect   # clickhouse-connect already in requirements
```

> **langfuse pin:** `requirements.txt` pins `langfuse>=2.30,<3`. `tracing.py` uses the **v2 SDK
> API** (`client.trace(...)` + manual `span.end()`). langfuse **v4 removed** that API — do not
> `pip install langfuse` fresh without the pin, or the CLI crashes on `start_trace`.

> **Git LFS:** `Atlys/data/*.parquet` (and `*.csv`) are LFS-tracked. Run `git lfs install` once on
> any machine before cloning/pushing, or a push will skip the blobs and fresh clones will fail with
> `[404] Object does not exist on the server`. If a clone ever fails that way, fix it from the
> machine that has the objects: `git lfs push --all origin`. For code-only checkouts, teammates can
> `GIT_LFS_SKIP_SMUDGE=1 git clone …` and `git lfs pull` later.

### 1.2 `.env`

```bash
cd Atlys
cp .env.example .env
$EDITOR .env     # fill CH_HOST, CH_PASSWORD, ZAI_API_KEY, LANGFUSE_*, LibreChat keys
```

`settings.py` auto-loads `Atlys/.env` **at import time** (dependency-free parser, never overrides
real environment variables). `CH_HOST` accepts a bare host, `host:port`, **or** a full URL like
`https://mo033….clickhouse.cloud:8443/` — the scheme sets `CH_SECURE` unless `CH_SECURE` is set
explicitly. This is why the e2e suite and CLI "just work" with a plain `python -m pytest`.

### 1.3 Load the funnel data (once)

The 8 tables (`destination_card_clicked` 1M, `purchase_completed` 7,054, … ~2.5M rows total):

```bash
PYTHONPATH=Atlys .venv/bin/python Atlys/data/load_python.py
```

This creates the `atlys` database, applies `ddl.sql` (idempotent — `IF NOT EXISTS`), and bulk-loads
each parquet with column-oriented inserts. Verify:

```bash
PYTHONPATH=Atlys .venv/bin/python -c "
from service.settings import Settings
import clickhouse_connect
s = Settings()
c = clickhouse_connect.get_client(host=s.ch_host, user=s.ch_user, password=s.ch_password, secure=s.ch_secure)
print(c.query('SELECT count() FROM atlys.destination_card_clicked').result_rows)
"
# → [(1000000,)]
```

> ⚠️ **Load-once semantics:** re-running re-inserts rows (same as `load.sh`). Don't re-run against
> a populated DB. Delete-and-reload (`DROP TABLE` or `TRUNCATE`) if you ever need a clean state.

### 1.4 Run the tests

```bash
# unit tests (no external services; run with no .env present → e2e auto-skips)
.venv/bin/python -m pytest Atlys/tests/ -q --ignore=Atlys/tests/test_e2e.py

# e2e — REQUIRES .env + live ClickHouse (auto-loaded; connects to the cloud CH)
.venv/bin/python -m pytest Atlys/tests/test_e2e.py -q
```

The e2e suite asserts the funnel counts (1M / 7,054), the full event chain
(`spec.run.requested` → … → `insight.created`), `meta.*` tables, and reconcile findings. If
`.env` is absent it **skips** with a clear message (safe for CI).

### 1.5 Run the CLI pipeline over a spec

```bash
PYTHONPATH=Atlys .venv/bin/python -m service.cli run 01_express_checkout --approve
```

`--approve` bypasses the human gate for CLI runs (the MCP flow keeps the gate). Output ends with
the insight card + `trace_id`. All 5 shipped specs run end-to-end: `01_express_checkout`,
`02_group_family`, `03_status_sharing`, `04_abandoned_checkout_recovery`, `05_instant_forex`.
Outputs land in `Atlys/generated/<feature>/` (`ddl.sql`, `schema_card.json`, `insight.md`).

### 1.6 React UI (local)

The UI is a React + Vite app in `Atlys/ui/`. FastAPI serves the production build from
`service/static/` at `/`. In Docker, Stage 1 of `Dockerfile.service` runs `npm ci && npm run build`
automatically — you only need these commands for local UI work.

```bash
cd Atlys/ui
npm ci

# Dev (HMR on :5173; Vite proxies /api/* → FastAPI on :8000)
# Keep uvicorn running in another terminal first.
npm run dev

# Production build → writes to Atlys/service/static/
npm run build

# Optional: lint / preview the built assets
npm run lint
npm run preview
```

| Mode | UI URL | API |
|---|---|---|
| `npm run dev` | `http://localhost:5173` | proxied to `http://localhost:8000` |
| `npm run build` + uvicorn | `http://localhost:8000` | same origin (StaticFiles) |
| `docker compose up` | `http://localhost:8000` | same origin inside the fastapi container |

Chat in the React UI goes through FastAPI's `POST /api/proxy/chat` → LibreChat Agents API.
You still need LibreChat up (compose or otherwise) for chat; the dashboard/API routes work
against FastAPI alone.

### 1.7 Run the HTTP service

```bash
PYTHONPATH=Atlys .venv/bin/uvicorn service.app:app --host 127.0.0.1 --port 8000
```

If `Atlys/service/static/` exists (after `npm run build` or a Docker image copy), FastAPI serves
the React SPA at `/`. If it is missing, `/healthz` and `/api/*` still work; the log notes that
the UI is not mounted.

> Concurrency: double-`approve_schema` on the same `run_id` is safe across threads and
> workers via compare-and-swap on `meta.pending_runs` (`proposed` → `running` +
> `runner_token`). Different features can run in parallel. Avoid starting two *different*
> runs that rebuild the **same** feature table at the same instant (last writer wins on
> DROP/CREATE; load is still idempotent when the schema matches).

| Endpoint | Purpose | Expected |
|---|---|---|
| `GET /` | React UI (when `service/static/` exists) | SPA `index.html` |
| `GET /healthz` | liveness + mode | `{"status":"ok","mode":"clickhouse",...}` (`dry-run` if no CH) |
| `GET /api/insights` | dashboard read | JSON list of insight cards |
| `POST /api/proxy/chat` | chat → LibreChat Agents | SSE stream |
| `GET /mcp/sse` | MCP server (SSE) | 200 + `Content-Type: text/event-stream` |
| `POST /api/specs` | drag-drop spec upload | writes `Atlys/specs/<feature>/` |

> ⚠️ Do **not** bind to `8123` — that's the local ClickHouse HTTP port and your curl results will
> silently be ClickHouse's, not the app's.

**Dry-run mode (no ClickHouse):** set `ATLYS_DRY_RUN=1` and the app runs fully in-memory — useful
to demo the event chain with zero credentials.

---

## 2. Production / demo setup (Docker + LibreChat + React UI)

### 2.1 One command for the full stack

```bash
cd Atlys
docker compose up -d          # mongo + librechat + fastapi (builds React UI in the image)
docker compose logs -f fastapi # watch for uvicorn + agent provision
```

- **React UI + API** on **`http://localhost:8000`** (primary demo surface).
- LibreChat on **`http://localhost:3080`** (chat backend; first boot: register the account that
  matches `LIBRECHAT_ADMIN_EMAIL` / `LIBRECHAT_ADMIN_PASSWORD` in `.env` so
  `provision_agent.py` can create **"Atlys PM"** automatically).
- Mongo is a **bundled compose service** — nothing to provision.
- `.env` is passed via `env_file`; the **mandatory** LibreChat vars (`CREDS_KEY`/`CREDS_IV`/`JWT_*`)
  must be filled or LibreChat crashes on boot. `MONGO_URI` is set by the compose file.
- MCP uses the Docker-internal URL `http://fastapi:8000/mcp/sse` — **no external tunnel** when
  everything runs in compose. Point `librechat.yaml` → `mcpServers.atlys-orchestrator.url`
  at that URL (already the intended D13 setup).

### 2.2 Hybrid local FastAPI + Docker LibreChat (optional tunnel)

If you run uvicorn on the host and only LibreChat/Mongo in Docker, LibreChat's MCP client still
needs a reachable SSE URL. Expose the local service:

```bash
cloudflared tunnel --url http://localhost:8000    # prints https://random-words.trycloudflare.com
# or: ngrok http 8000
```

Then edit `Atlys/librechat.yaml`:

```yaml
mcpServers:
  atlys-orchestrator:
    type: sse
    url: https://<your-tunnel-url>/mcp/sse
    headers:
      X-Atlys-Conversation-Id: "{{LIBRECHAT_BODY_CONVERSATIONID}}"
```

`docker compose restart librechat` to pick it up. **Security:** MCP has no auth header — use a
throwaway random tunnel subdomain, keep it private, and rotate between demos.

### 2.3 Wire the chat agent

With the full compose stack, FastAPI's startup hook runs `provision_agent.py` and creates
**"Atlys PM"** automatically (writes `agent_id` for the React UI proxy). Manual fallback:

1. LibreChat → **Agents** → create **"Atlys PM"** with exactly these Atlys tools enabled:
   `interrogate_spec`, `run_spec`, `approve_schema`, `reject_schema`, `get_insight`,
   `list_insights`, `get_changelog`, `get_context`, `propose_context_update`, `reconcile`,
   `db_schema`, `table_stats`, `aggregate`, `sample_rows`.
   Do **not** enable `ingest_events` (removed from the MCP tool list; paste `agents/atlys_pm.md`
   as the system prompt). Safe DB tools are read-only with timeouts/limits — no free-form SQL.
2. The **only LLM** is Z.ai GLM via `endpoints.custom` in `librechat.yaml` (LibreChat v0.8+ rejects the
   old top-level `customEndpoints` key) — the FastAPI pipeline itself makes **zero LLM calls**
   (deterministic-first).

### 2.4 Tracing

- **Pipeline layer:** FastAPI → Langfuse via the SDK (`LANGFUSE_*` in `.env`). One trace per spec
  run; `trace_id` on every `meta.*` and `atlys.event_log` row.
- **Chat layer:** LibreChat natively traces via the same env vars — no `librechat.yaml` config.
- Correlation: `session_id = run_id` on the pipeline trace; the chat reply echoes `run_id`, so
  searching Langfuse by `run_id` finds both trees.

### 2.5 The Day-2 unseen spec

The 6th sealed spec is released to all teams; it arrives as `spec.md` + `events.ndjson`. Either
drop it into `Atlys/specs/<feature>/` (or drag-drop via `POST /api/specs`), then type
`run <feature>` in LibreChat chat. The pipeline is content-driven — no per-spec code.

---

## 3. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| e2e tests "skipped" | `.env` missing or `CH_HOST` empty — create `Atlys/.env` and re-run |
| CLI crash: `AttributeError: start_trace` | langfuse v4 installed — `pip install 'langfuse>=2.30,<3'` |
| `uvicorn` answers on port 8123 look wrong | that's local ClickHouse; use any other port |
| LibreChat container exits immediately | `CREDS_KEY`/`CREDS_IV` must be **hex** of the right length (64 / 32 chars) |
| MCP tool "not found" in chat | tunnel URL in `librechat.yaml` stale → restart LibreChat after editing |
| `load_python.py` re-run duplicates rows | documented load-once semantics; `TRUNCATE TABLE` first |
| Langfuse panels empty | `LANGFUSE_*` unset → NullTracer; pipeline works but has no traces |

## 4. Also in the repo

- `ui/` — React + Vite front end (`npm run dev` / `npm run build` → `service/static/`).
- `Dockerfile.service` — multi-stage image (Node UI build + Python FastAPI).
- `data/load.sh` — the original shell loader (equivalent of `load_python.py`).
- `data/ddl.sql` — the 8 funnel table definitions.
- `data/instrumentation_notes.md` — what emits into each table.
- `generated/` — pipeline outputs per feature (DDL, schema card, insight).
- `base_context.md` — the (deliberately imperfect) business context layer the Context Agent keeps fresh.
