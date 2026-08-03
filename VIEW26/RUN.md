# Running FeatureLens

This runbook is the operational source of truth for judges and maintainers. The root `README.md` explains the product; this file explains how to reproduce it.

## Prerequisites

- Go 1.25+
- Node.js 22.13+
- `curl` and `jq`
- A ClickHouse service reachable over HTTPS
- The Atlys dataset folder containing `specs/01_*` through `specs/05_*`
- Langfuse Cloud keys for submission traces
- Optional: an OpenAI-compatible LLM endpoint and LibreChat/Docker Desktop

## 1. Configure environment

```bash
cp .env.example .env
```

Fill these values in `.env`:

```dotenv
# Go API
FEATURELENS_ADDR=:8080

# ClickHouse
CLICKHOUSE_HOST=your-service.region.clickhouse.cloud
CLICKHOUSE_HTTP_PORT=8443
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=replace-me
CLICKHOUSE_SECURE=true
CLICKHOUSE_SOURCE_DATABASE=atlys
CLICKHOUSE_CONTROL_DATABASE=featurelens_poc

# Langfuse — use the project region that owns the keys
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_TRACING_ENVIRONMENT=staging
LANGFUSE_RELEASE=clickathon-2026

# Governed narrative synthesis; omit key/model for deterministic fallback
LLM_PROVIDER=openrouter
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=replace-me
LLM_MODEL=openai/gpt-4.1-mini
LLM_TIMEOUT=30s
LLM_PROMPT_VERSION=analytics-insight:v2

# Frontend and MCP
NEXT_PUBLIC_FEATURELENS_API=https://clickathon-2026.view26.com
NEXT_PUBLIC_SITE_URL=https://clickathon-2026.view26.com
NEXT_PUBLIC_LIBRECHAT_URL=http://localhost:3080
FEATURELENS_MCP_URL=http://host.docker.internal:8080/mcp

# Supplied Atlys fixtures
ATLYS_DATASET_DIR=/absolute/path/to/click-a-thon-2026/Atlys
FEATURELENS_API_URL=http://localhost:8080
```

Do not commit `.env`. If a key has appeared in a screenshot, rotate it before submission.

## 2. Check ClickHouse connectivity

The API validates connectivity at startup and exits if configured ClickHouse is unreachable:

```bash
set -a && source .env && set +a
(cd backend && go run ./cmd/featurelens)
```

In another terminal:

```bash
curl --fail http://localhost:8080/health | jq
curl --fail http://localhost:8080/api/catalog | jq '.tables | length'
```

Expected: `status: "ok"`, `context_version` at least `0`, and all eight canonical `atlys` source tables present.

## 3. One-command end-to-end pipeline

```bash
./scripts/run-submission.sh
```

The command:

1. loads `.env` without printing secrets;
2. starts the Go service when one is not already healthy;
3. replays all five known feature specs sequentially;
4. preserves the human schema gate while using `auto_approve` for reproducibility;
5. verifies row counts, event-ID fingerprints, schemas, context versions, and all gates;
6. runs the autonomous Analytics Agent report across the eight source tables;
7. prints health, run, context, and Langfuse trace summaries.

Fresh databases load fixture NDJSON by default. To attach already-retained feature tables without writes:

```bash
FEATURELENS_USE_EXISTING_DATA=true ./scripts/run-submission.sh
```

## 4. Run the product UI

Terminal 1:

```bash
set -a && source .env && set +a
(cd backend && go run ./cmd/featurelens)
```

Terminal 2:

```bash
npm ci
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## 5. Run the sealed sixth feature

In the app, select **Add another release**, upload the sealed `spec.md` and `events.ndjson`, review the generated DDL, then approve the schema. The pipeline must complete without code or prompt changes.

API equivalent:

```bash
payload="$(jq -n \
  --arg name "Promo / Coupon at Checkout" \
  --arg slug "promo_coupon_at_checkout" \
  --argjson schema_version 6 \
  --rawfile spec /path/to/sixth/spec.md \
  --rawfile events /path/to/sixth/events.ndjson \
  '{name:$name,slug:$slug,schema_version:$schema_version,spec_markdown:$spec,events_ndjson:$events,role:"product_manager",auto_approve:false}')"

run_id="$(printf '%s' "$payload" | curl --fail --silent --show-error \
  -H 'Content-Type: application/json' -d @- http://localhost:8080/api/runs | jq -r '.id')"

curl --fail --silent --show-error -X POST \
  "http://localhost:8080/api/runs/${run_id}/approve" | jq
curl --fail --silent --show-error \
  "http://localhost:8080/api/runs/${run_id}" | jq
```

The submission bundle is under `submission/surprise/`.

## 6. Standard PM probes

POST each prompt to `/api/conversations` with role `product_manager`:

```bash
curl --fail --silent --show-error \
  -H 'Content-Type: application/json' \
  -d '{"role":"product_manager","question":"Analyze the existing funnel and surface the most important issues, with the why."}' \
  http://localhost:8080/api/conversations | jq
```

The four captured outputs and trace IDs are in `submission/evidence/standard-probes.md`.

## 7. Verification

```bash
(cd backend && go test ./...)
npm test
(cd backend && go run ./cmd/validate-ask)
```

The Ask validator recomputes retained-table truth independently and checks numerical evidence, dimensions, SQL allowlists, context/schema versions, provenance, prose percentages, and fail-closed boundaries.

## 8. LibreChat / MCP

```bash
./scripts/run-librechat-local.sh
```

Open [http://localhost:3080](http://localhost:3080). LibreChat receives seven governed tools from `http://host.docker.internal:8080/mcp`; the three FeatureLens agents and ClickHouse remain the system of record.

## 9. Staging deployment

Build the frontend with the final public API origin:

```bash
set -a && source .env && set +a
npm ci
npm run build
```

Run the Go service and the frontend as separate supervised processes. Route these paths at `clickathon-2026.view26.com`:

| Path | Upstream |
|---|---|
| `/api/*`, `/health`, `/mcp` | Go service on `127.0.0.1:8080` |
| all other paths | frontend on `127.0.0.1:3000` |

Before the PR, verify from an incognito window:

```bash
curl --fail https://clickathon-2026.view26.com/health | jq
curl --fail https://clickathon-2026.view26.com/api/runs | jq '.runs | length'
```

Then open the hosted app, complete one PM question, open its trace, and confirm the Langfuse observations have synced.
