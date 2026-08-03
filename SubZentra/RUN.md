# Running ZentraOS locally

Source lives in [`source/`](./source) — the full ZentraOS monorepo.

## Prerequisites

- Node.js 24 and npm
- Python 3.13 and `uv`
- Docker with Compose
- An Anthropic API key (`ANTHROPIC_API_KEY`) — required. Every other model
  provider key is optional; a provider without one is skipped in the fallback
  chain rather than failing.
- A ClickHouse Cloud connection (host, port, credentials) for the source you
  want the Cube Analyst to reason over — this is added as a Connector inside
  the running app, not via env var.

## 1. Install and bring up local infrastructure

```bash
cd source
npm ci
uv sync --frozen
docker compose up -d --wait control-postgres warehouse-postgres clickhouse cube
```

## 2. Configure environment

```bash
cp apps/api/.env.example apps/api/.env
cp apps/zentra-os/.env.example apps/zentra-os/.env.local
```

Fill in `ANTHROPIC_API_KEY` in `apps/api/.env` at minimum. Add Clerk keys to
`apps/zentra-os/.env.local` if you want a full browser sign-in flow.

## 3. Run migrations

```bash
DATABASE_OWNER_URL=postgresql+psycopg://zentra_owner:zentra_owner@localhost:5432/zentra_control \
  npm exec -- nx run postgres:migrate
```

## 4. Promote the agents

Agents are registered disabled until their pinned eval suites pass:

```bash
DATABASE_OWNER_URL=postgresql+psycopg://zentra_owner:zentra_owner@localhost:5432/zentra_control \
  npm exec -- nx run evals:promote
```

## 5. Run the API and frontend

```bash
npm exec -- nx serve api        # http://localhost:8000
npm exec -- nx serve zentra-os  # http://localhost:4200 (separate terminal)
```

## 6. Connect your ClickHouse source and ask a question

Sign in, go to **Connections → New**, add your ClickHouse Cloud source, and
let it harvest. Then go to **Chat** and ask any of the probe questions from
the [README](./README.md#try-it-against-the-probe-set) — the pipeline
resolves the connected source's live schema into a governed catalog and
answers over it end to end (Orchestrator → Cube Analyst → Evaluator →
Insight).

## Verification

```bash
uv run python tools/architecture/verify_known_bad_boundary.py
uv run lint-imports
npm exec -- nx run evals:check
npm exec -- nx run-many -t lint test build typecheck
```

`evals:check` replays pinned model responses through each agent to verify
schema compliance and confidence bounds without calling a live model.
