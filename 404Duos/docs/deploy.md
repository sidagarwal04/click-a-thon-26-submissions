# Deploy a public demo (Railway + Vercel)

Target layout:

```
Browser → Vercel (web) → Railway (API + in-process RCA) → ClickHouse Cloud
                              ↘ Gemini + Langfuse Cloud (optional)
```

One Railway service runs Express **and** the ClickHouse investigation engine (ported from Go into `apps/api/src/engine`).

| Piece | Host | Public? |
|-------|------|---------|
| Web | Vercel | Yes — **demo link** |
| API (+ RCA engine) | Railway | Yes — generate a public domain |
| ClickHouse | ClickHouse Cloud | Existing |
| Langfuse | Langfuse Cloud | Existing |

Dockerfile: `apps/api/Dockerfile`.

---

## 0. Prerequisites

- [Railway](https://railway.app) account
- [Vercel](https://vercel.com) (GitHub import or CLI)
- ClickHouse Cloud credentials already working locally
- Gemini + Langfuse keys if you want narration / traces

---

## 1. Railway — single `api` service

Create one Railway **project** with **one** service from the GitHub repo.

**Do not deploy from the repo root.** If Railpack analyzes `./apps`, `./docs`, … and fails, Root Directory is still `/`.

Service **Settings**:

1. **Root Directory** → `apps/api`
2. **Builder** → **Dockerfile** (not Railpack)
3. **Dockerfile path** → `Dockerfile`
4. **Networking** → **Generate Domain**
5. Healthcheck path → `/health`

### Variables

```bash
CLICKHOUSE_HOST=your.host.clickhouse.cloud
CLICKHOUSE_PORT=8443
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=***
CLICKHOUSE_DATABASE=insightiq
CLICKHOUSE_SECURE=true
CLICKHOUSE_LOG_QUERIES=true

GEMINI_API_KEY=***
GEMINI_MODEL=gemini-flash-lite-latest
LANGFUSE_PUBLIC_KEY=pk-***
LANGFUSE_SECRET_KEY=sk-***
LANGFUSE_BASE_URL=https://jp.cloud.langfuse.com
```

Do **not** set `ENGINE_URL` — there is no separate engine service.

### Migrating from the old two-service setup

If you already deployed separate `engine` + `api` services:

1. On **api**: add all `CLICKHOUSE_*` variables (same values the old engine used)
2. On **api**: delete `ENGINE_URL` if present
3. Confirm api **Root Directory** = `apps/api`, **Builder** = Dockerfile
4. Redeploy **api**
5. Delete the old **engine** Railway service (no longer used)
6. Keep Vercel `VITE_API_URL` pointed at the **api** public domain (unchanged if the URL stayed the same)

Smoke test:

```bash
curl -s https://YOUR-API.up.railway.app/health
curl -s 'https://YOUR-API.up.railway.app/api/alerts?granularity=day' | head -c 400
```

`health.clickhouse.ok` should be `true`.

---

## 2. Vercel — web (demo link)

1. Import the repo → **Root Directory** = `apps/web`
2. Env: `VITE_API_URL` = `https://YOUR-API.up.railway.app` (no trailing slash)
3. Deploy → use the `*.vercel.app` URL as the public demo link

`VITE_*` values are **build-time**. Redeploy web when the API hostname changes.

---

## 3. Demo checklist

1. Open the Vercel URL → Dashboard loads
2. **Alerts** → Daily list non-empty
3. Open one investigation → metric tree + diagnosis + ruled-out
4. **Export** once
5. Chat follow-up (Gemini + Langfuse optional)

---

## Troubleshooting

### `Railpack could not determine how to build the app`

Root Directory must be `apps/api`, Builder = **Dockerfile**.

### `health.clickhouse.ok` is false

Check `CLICKHOUSE_*` secrets and that the Cloud service allows Railway egress.

### Alerts empty

Confirm `alerts_live` has rows in ClickHouse (`abs(zscore) > 3`).

---

## Local reference

See [setup.md](./setup.md). RCA code lives in `apps/api/src/engine/`.
