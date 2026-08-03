# Setup — from a brand-new machine to a running UI

Follow these steps in order. Each one has a copy-paste command and a "you
should see" checkpoint — if a checkpoint doesn't match, stop and read
[Troubleshooting](#troubleshooting) before moving on.

---

## 1. Install Docker Desktop

Download and install for your OS: **https://www.docker.com/products/docker-desktop/**

Open the Docker Desktop app once installed, and wait for it to say it's running.

Check it from a terminal:

```bash
docker --version && docker compose version
```

**You should see:** two version lines (e.g. `Docker version 27...` and `Docker
Compose version v2...`). If you get "command not found," Docker Desktop isn't
installed or isn't finished starting — open the app and wait.

---

## 2. Get the code

```bash
git clone https://github.com/Prem1902/atlys-prism-ch.git
cd atlys-prism-ch
```

**You should see:** a new `atlys-prism-ch` folder, and your terminal prompt now
inside it.

---

## 3. Create a ClickHouse Cloud service (free)

1. Go to **https://clickhouse.cloud/signup** and create a free account.
2. Once logged in, click **New service**, pick any name and region, and create it.
3. When the service is ready, click **Connect** → **HTTPS** (or "Connection
   details"). Note down these four values — you'll paste them in step 5:
   - **Host** (looks like `abcd1234.region.aws.clickhouse.cloud`)
   - **Port** — use **8443** (the HTTPS port, not 9440/native)
   - **User** — usually `default`
   - **Password** — shown once when the service is created; reset it from the
     console if you didn't save it

**You should see:** a ClickHouse Cloud service in "Running" state, and you have
the host/port/user/password written down somewhere.

---

## 4. Get an LLM API key

Pick **one** provider. Gemini has the easiest free tier:

- **Gemini (recommended, free tier):** https://aistudio.google.com/apikey → "Create API key"
- **Anthropic:** https://console.anthropic.com/settings/keys
- **OpenAI:** https://platform.openai.com/api-keys

**You should see:** a copied API key string (starts with `AIza...` for Gemini,
`sk-ant-...` for Anthropic, or `sk-...` for OpenAI).

---

## 5. Create your `.env` file

```bash
make env
```

**You should see:** `wrote .env` (or `.env already exists - leaving it alone`
if you've run this before).

Now open `.env` in any text editor and fill in these lines with what you
collected in steps 3 and 4:

```bash
CLICKHOUSE_HOST=your-service-id.region.aws.clickhouse.cloud
CLICKHOUSE_PORT=8443
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=your-clickhouse-password
CLICKHOUSE_DB=atlys

LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-flash-lite
GOOGLE_API_KEY=your-gemini-api-key
```

> Using Anthropic or OpenAI instead? Set `LLM_PROVIDER=anthropic` or `openai`
> and fill in `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` instead of the Google one.
> Leave `LLM_MODEL` as whichever model name you want to use from that provider.

Leave every other line in `.env` as it already is.

**You should see:** a saved `.env` file with real values (not placeholders) on
those five/six lines.

---

## 6. Start the app

```bash
make up
```

This builds the app image and starts it — the first run takes a couple of
minutes to download and build.

**You should see:** the command finish with `ClickHouse reachable` printed near
the end (not an error).

---

## 7. Open it and verify

```bash
make ui
```

This opens **http://localhost:8000** in your browser. You should see the
"Prism CH" UI with tabs across the top: Overview, Instrument, Analysis,
Context, Schema.

Double-check the backend is actually healthy:

```bash
curl http://localhost:8000/api/health
```

**You should see:** `{"ok": true, "clickhouse": "...", "database": "atlys",
"target": "cloud", "llm": "gemini-2.5-flash-lite"}` — `"ok": true` is the part
that matters.

**You're done.** Everything from here is optional.

---

## 8. (Optional) Turn on tracing

Every agent run can be traced in [Langfuse](https://langfuse.com), self-hosted
in its own containers:

```bash
make up-obs && make langfuse-ready && make langfuse
```

**You should see:** a browser tab opens to **http://localhost:3000**, logged
in automatically (dev account `dev@prism.local` / `prismdev123`). First boot
runs database migrations and can take about a minute — `langfuse-ready` waits
for that automatically.

---

## Troubleshooting

**`docker: command not found`** — Docker Desktop isn't installed or isn't
running. Revisit [step 1](#1-install-docker-desktop).

**`make up` fails with "ClickHouse unreachable"** — double check `.env`:
`CLICKHOUSE_PORT` must be **8443** (not 9440 — that's the native protocol,
wrong for this app) and `CLICKHOUSE_SECURE=true`. Also confirm the ClickHouse
Cloud service shows "Running" in its console, not "Stopped" or "Starting."

**`docker compose ps` shows the app "unhealthy"** — cosmetic only. The
container's built-in healthcheck probes a path that doesn't exist. Confirm the
app actually works with `curl http://localhost:8000/api/health` — if that
returns `"ok": true`, ignore the "unhealthy" label.

**Langfuse traces never show up, or logs say "langfuse unreachable"** — make
sure `.env` does **not** have a `LANGFUSE_BASE_URL` line. If one exists
(commented or not), delete it. That variable overrides `LANGFUSE_HOST` inside
the SDK and breaks tracing when pointed at `localhost`.

**Port already in use (`8000`, `3000`, etc.)** — something else on your machine
is using that port. Change `APP_PORT` (or `LANGFUSE_PORT`) in `.env` to a free
port and re-run `make up`.

**Starting over from scratch** — `make destroy` stops everything and deletes
all local data volumes (Langfuse traces included; your ClickHouse Cloud data is
untouched since it isn't stored locally). It asks for confirmation first.
