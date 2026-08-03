# Team-Disha

## Track

InMobi

## Project

**Metric Mind** — From alert to answer: ClickHouse-native detect → drill-down → plain-language diagnosis, with LibreChat, Langfuse, and ClickStack.

## Team Members

- Ashiq Abdulkhader ([AshiqAbdulkhader](https://github.com/AshiqAbdulkhader))
- Poushali Chattopadhyay ([poushalic34](https://github.com/poushalic34))

## What it does

When a key ad-platform metric moves (revenue / fill / eCPM / requests), the system:

1. **Detects** same-weekday (−7) anomalies with seasonality gates and optional ML residual baselines  
2. **Attributes** the move to requests vs fill vs eCPM (contribution shares in ClickHouse)  
3. **Localizes** to segments/combos (`os_version`, region, format, category, …)  
4. **Narrates** a plain-language diagnosis (LLM only narrates numbers already computed in ClickHouse)  
5. **Traces** the run in Langfuse; ops telemetry via ClickStack (HyperDX + OTel)

All investigation numbers come from precomputed `eda.rca_*` tables (or live CLI fallback). The LLM does not invent anomalies or metrics.

## Hosted Demo

**[Live demo](https://metric-mind.ashiqabdulkhader.dev/login)** — Metric Mind (LibreChat) via Cloudflare Tunnel → this laptop’s stack.

| | |
|---|---|
| **URL** | https://metric-mind.ashiqabdulkhader.dev/login |
| **Email** | `admin@clickathon.local` |
| **Password** | `clickathon-admin` |

After login, open **InMobi RCA Orchestrator**. Suggested prompts:

- `What are the anomalies?` → catalog from `rca_incidents`
- Deep explain for one incident (factor, segment, counterfactual)
- Optional chart via `plot_anomaly`
- Langfuse: `Give me the trace for this`

Local fallback after `docker compose` + seed: `http://localhost:3080` (same credentials from `.env` / `LIBRECHAT_USER_*`).

## Demo Video

[`demo-video.mov`](./demo-video.mov) — LibreChat Day-2 RCA + Langfuse trace + ClickStack / HyperDX (~2–3 min).

Mirror: [Google Drive](https://drive.google.com/file/d/18foP3ku3cDEzAKG5TdvZaDZ-kytKUTIH/view?usp=drive_link)

## OSS stack evidence

| Tool | Role in pipeline | Proof for judges |
|---|---|---|
| **LibreChat** | Multi-agent chat UI over RCA MCP | [Hosted demo](https://metric-mind.ashiqabdulkhader.dev/login) + local run (`stack/librechat.yaml`, seeded agents) |
| **Langfuse Cloud** | Investigation + LLM traces | Public Day-2 links in [`unseen_incident/trace.md`](./unseen_incident/trace.md); offline JSON in [`unseen_incident/langfuse/`](./unseen_incident/langfuse/) |
| **ClickStack** | HyperDX + OTel → Cloud `otel` | [`evidence/clickstack/`](./evidence/clickstack/) — HyperDX data-source screenshots + `otel_tables_summary.json` |

## Architecture

See [`Architecture.md`](./Architecture.md) — full design write-up (Mermaid + data model + `rca_*` catalog + Compose + tools + research decisions). Same file mirrored at [`source_code/architecture.md`](./source_code/architecture.md). Algorithms considered/rejected: [`design-notes/RESEARCH.md`](./design-notes/RESEARCH.md).

## Pitch deck

**`pitch-deck.pdf`** in this folder (add before the submission PR if not already present).

## Unseen incident (Day-2)

Evidence pack: [`unseen_incident/`](./unseen_incident/) (`diagnosis.md`, `numbers.md`, `trace.md`).

**Reproduce the numbers yourself** (after load + materialize — see below):

```bash
cd source_code
uv run python stack/scripts/verify_unseen_rca.py
```

That script queries `eda.rca_incidents`, `rca_daily_wow`, `rca_counterfactual`, and top segment/combo rows, and writes `stack/scripts/verify_unseen_rca_last.json`. Compare the printed figures to [`unseen_incident/diagnosis.md`](./unseen_incident/diagnosis.md) and [`unseen_incident/numbers.md`](./unseen_incident/numbers.md).

## How we built it

| Piece | Role |
|---|---|
| **ClickHouse Cloud** | Primary datastore + analytical engine (`eda.rca_*` materialize) |
| **Python / uv** | Thin CLI + RCA MCP; NL enrichment only |
| **LibreChat** | Multi-agent chat demo (Orchestrator / Detector / Factor / Localizer) |
| **Langfuse Cloud** | Investigation + LLM traces judges open |
| **ClickStack** | HyperDX + OTel → Cloud `otel` for runtime observability |
| **Azure OpenAI** | Narration LLM (`gpt-5.6-sol` via OpenAI-compatible API) |

Trust model: **ClickHouse computes → findings JSON → LLM narrates.**

## How to run it

Supported: macOS, Linux, Windows (PowerShell or WSL) with Docker Desktop, Python ≥3.12, and [uv](https://github.com/astral-sh/uv).

You need a **ClickHouse Cloud** service with the original InMobi star schema in `default` (Jun 1 – Jul 5). RCA uses database `eda`.

### 1. Configure

```bash
cd source_code
cp .env.example .env
uv sync
```

Fill at least: `CLICKHOUSE_*` (`CLICKHOUSE_RCA_DATABASE=eda`), `LANGFUSE_*`, `OPENAI_*` / `AZURE_OPENAI_*`, LibreChat JWT/`LIBRECHAT_USER_*`, optional `HYPERDX_API_KEY`.

### 2. Demo path (original build dataset)

```bash
# if eda needs a clean copy of default:
#   uv run python stack/scripts/restore_eda_from_default.py
uv run clickathon materialize --rollup
docker compose -f stack/docker-compose.yml --env-file .env up -d
uv run python stack/scripts/seed_librechat_agents.py
```

| Service | URL |
|---|---|
| LibreChat | http://localhost:3080 |
| Admin Panel | http://localhost:3081 |
| HyperDX | http://localhost:8080 |
| RCA MCP | http://localhost:8001/mcp |

Open LibreChat → **InMobi RCA Orchestrator** → `What are the anomalies?`

CLI:

```bash
uv run clickathon scan
uv run clickathon investigate 2026-06-23
```

### 3. Day-2 unseen dataset (separate `eda`, no append)

Point `UNSEEN` at the hackathon release folder that contains `ad_events.parquet` + dim CSVs (e.g. `InMobi/unseen_data`).

```bash
# Replace eda with Jul 6–10 only; dims from unseen CSVs.
# T−7 baselines are read from default.ad_events (history is not copied into eda).
uv run python stack/scripts/upload_unseen.py /path/to/InMobi/unseen_data

uv run clickathon materialize --rollup

# Re-run the ClickHouse checks that back our diagnosis:
uv run python stack/scripts/verify_unseen_rca.py
```

Then in LibreChat: `What are the anomalies?` → explain each id → `Give me the trace for this`.

Restore the original `eda` later:

```bash
uv run python stack/scripts/restore_eda_from_default.py
uv run clickathon materialize --rollup
```

### 4. Stop

```bash
docker compose -f stack/docker-compose.yml --env-file .env down
```

More stack notes: [`source_code/stack/README.md`](./source_code/stack/README.md).

## Source code

All project code is under [`source_code/`](./source_code/).

## License

MIT — see [`source_code/LICENSE`](./source_code/LICENSE).
