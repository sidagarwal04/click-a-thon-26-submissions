# ZentraOS

ZentraOS is a trust-first analytics system: investigations are tenant-isolated,
results carry typed outcome evidence, governed work can stop at a human gate,
and the process can be replayed without retaining raw customer data.

The governed `eu_refund_spike` question runs through four agents: an
Orchestrator that resolves the enabled roles from the registry and delegates,
a SQL Analyst that queries Cube, an Evaluator that re-derives the number
independently on a different model, and an Insight Agent that turns the
validated result into a Draft Finding. The Orchestrator plans and arbitrates;
it does not write the conclusion.

Which model serves each agent is a per-tenant routing decision. Free tenants run
on free inference — Gemini, Cerebras, Groq, OpenRouter — falling through on rate
limits, outages, and schema violations, with Anthropic as the final backstop.
Premium tenants run Anthropic-first and never reach a provider that trains on
inference data; see
[Model Provider Sub-Processors](docs/08_Operations/Model%20Provider%20Sub-Processors.md). The Evaluator-Optimizer loop
exits hard at three attempts. A confidence below the Tenant threshold, or a
recheck that never converged, opens a Human Approval gate that blocks
completion. Every agent step is persisted with token, cost, and model
attribution and delivered to an append-only ClickHouse ledger as metadata and
`artifact://` pointers — never as result rows.

## Prerequisites

- Node.js 24 and npm
- Python 3.13
- `uv`
- Docker with Compose
- Terraform 1.9+ for managed infrastructure

## Local foundation

```bash
npm ci
uv sync --frozen
docker compose up -d --wait control-postgres warehouse-postgres clickhouse cube
DATABASE_OWNER_URL=postgresql+psycopg://zentra_owner:zentra_owner@localhost:5432/zentra_control \
  npm exec -- nx run postgres:migrate
npm exec -- nx serve api
```

In another terminal:

```bash
npm exec -- nx serve zentra-os
```

The frontend runs at `http://localhost:4200`, the API at
`http://localhost:8000`, Cube at `http://localhost:4000`, and ClickHouse HTTP at
`http://localhost:8123`.

Copy the frontend and API `.env.example` files into untracked `.env` files and
provide Clerk, Langfuse OTLP, and E2B credentials when exercising those
integrations. `ANTHROPIC_API_KEY` is required for the agents to run; every other
provider key is optional, and a provider without one is skipped in the chain.

A tenant defaults to the free tier. Put one on Anthropic-first routing with:

```sql
UPDATE tenants SET model_tier = 'premium' WHERE tenant_id = '...';
```

Agents are registered disabled. Promote them once their eval suites pass:

```bash
DATABASE_OWNER_URL=... npm exec -- nx run evals:promote
```

The authenticated API exposes:

- `POST /v1/investigations`
- `GET /v1/investigations/{investigation_id}`
- `POST /v1/investigations/{investigation_id}/approvals/{approval_id}/decision`

Only `{"scenario_key":"eu_refund_spike"}` is accepted, and the canonical
question is fixed by the server. `POST` returns immediately with status
`running`; the agents run in the background and the client polls `GET` as each
step lands.

## Verification

```bash
uv run python tools/architecture/verify_known_bad_boundary.py
uv run lint-imports
npm exec -- nx run evals:check
npm exec -- nx run-many -t lint test build typecheck
npm exec -- nx e2e zentra-os-e2e
```

`evals:check` replays pinned model responses through each agent to verify
schema compliance, governed-member enforcement, and confidence bounds. It does
not call a live model, so a pass means the agent's own logic is correct — not
that the model was right.

Managed Neon and ClickHouse Cloud resources live under `infra/terraform`.
Terraform applies are explicit operator actions; provider tokens, state, plans,
and generated connection credentials must remain outside the repository.

## Engineering knowledge

Open [`docs/`](docs/README.md) as the plugin-independent Obsidian vault and
start at the [ZentraOS Knowledge Base](docs/00_Index/ZentraOS%20Knowledge%20Base.md).
Validate its metadata, links, and source references with:

```bash
npm exec -- nx run docs:check
```
