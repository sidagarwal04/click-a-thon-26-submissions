# InsightIQ Node API

REST + in-process ClickHouse RCA (`src/engine`) + Gemini narration + in-app `/v1` chat. Traces LLM + evidence steps to **Langfuse**.

```bash
cp .env.example .env
npm install
npm run dev
```

Requires `CLICKHOUSE_*` in `.env` (see `.env.example`). No separate Go engine.

## Langfuse

```bash
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_BASE_URL=https://jp.cloud.langfuse.com
```

Each chat turn emits a trace tree:

- `handle-chat-completion` (span)
  - `retrieve-dashboard-evidence` (retriever) *or* investigation resolve
  - `narrate-with-gemini` (generation)

## Endpoints

- `GET /health` — includes `clickhouse`, `langfuse`
- `GET /api/alerts`
- `POST /api/investigate` — traced
- `GET /api/investigations/:id`
- `POST /v1/chat/completions` — in-app chat (traced)
