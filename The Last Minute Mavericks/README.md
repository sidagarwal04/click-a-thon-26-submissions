# The Last Minute Mavericks

## Track
InMobi

## Project
**RootCauseOS** — from alert to answer: an automated root-cause analyst where ClickHouse does every computation and the LLM can only narrate numbers we actually computed.

## Team Members
- Mridul ([mkvmridul](https://github.com/mkvmridul))
- Naman Goyal ([namangoyal3](https://github.com/namangoyal3))
- Deepak Kumar ([dipakkr](https://github.com/dipakkr))

## What it does
A key ad metric (revenue) moves. RootCauseOS:
1. **Detects** the deviation — robust MAD z-score (|z| > 3.5) against a same-weekday median baseline of the 3 preceding weeks, over residuals after a multiplicative detrend, with min-volume and effect-size gates so weekends and noise don't page anyone.
2. **Drills down in ClickHouse SQL** — greedy cross-cut descent across app × geo × device × advertiser dimensions to the responsible 1-D/2-D/3-D segment, with a Simpson's-exclusion check (re-run excluding the culprit; siblings that vanish are "explained by", not separate findings). `GLOBAL_UNLOCALIZED` is a first-class verdict — some incidents genuinely have no responsible segment.
3. **Decomposes** the move with LMDI (log-mean Divisia index — an exact additive split of a metric change across its multiplicative factors: requests × fill × render × eCPM), cross-checked against exact Shapley attribution; near-zero factors become the ruled-out list, with numbers.
4. **Narrates** — the LLM never sees a raw row and never does arithmetic. Every number is an evidence object `{value, sql, query_id}`; a validator rejects any draft containing a figure we did not compute, retries once, then falls back to a deterministic template. **The model cannot state a number that wasn't computed in ClickHouse.**
5. **Traces** — one public Langfuse trace per scan, one span per investigation, carrying verdict, culprit, decomposition, ruled-out list, and every evidence item with its ClickHouse `query_id`.

## Hosted Demo
- **Dashboard:** https://dash.23.101.175.68.nip.io/
- **API (deployed engine):** http://23.101.175.68:8077 — `/scan`, `/health`, `/docs`

## Demo Video
https://youtu.be/U42xK8mK8QE

## Architecture
See **[ARCHITECTURE.md](ARCHITECTURE.md)** (1–2 pager: where the analysis runs, detection & attribution method, OSS-tool integration evidence, LLM providers).

## The unseen incident bundle
See **[unseen-incident/](unseen-incident/)** — the system's diagnosis for the sealed Jul 6–10 slice, the numbers behind it (reproducible ClickHouse SQL with `query_id`s), and the public Langfuse trace that proves the pipeline generated it.

## How we built it
- **ClickHouse Cloud** is the primary datastore *and* the analysis engine — every detection, drill-down, decomposition, and verification step is a SQL query over a pre-aggregated cube (`rca.cube`, MergeTree built by `INSERT…SELECT` from 9M raw events). The LLM receives only a structured evidence bundle.
- **Langfuse (v4 SDK, pinned 4.14.2)** traces every investigation; traces are made public so judges can audit without credentials. No trace, no credit — so the trace *is* the product.
- **ClickStack** — OTel spans for every pipeline stage and every ClickHouse query (carrying the server-reported `query_id`, rows, bytes, duration) exported to HyperDX (`integrations/otel.py`, `integrations/clickstack/`).
- **LibreChat** — self-hosted (`integrations/librechat/`), wired to our OpenAI-compatible shim (`integrations/openai_shim.py`, model `rootcauseos-rca`) so follow-up questions run through the same evidence-only validation as the dashboard.
- **Engine:** single-file pipeline `run_incident.py` (detect → decompose → attribute → verify → narrate → trace), served by `api/server.py` (FastAPI), fronted by a Streamlit dashboard (`ui/`).
- **Tested:** blind-slice harness (`test-sql/`, `tests/e2e/`) — 33/33 planted incidents detected and localized across 6 blind slices, 1 false positive.
- **LLM providers:** OpenAI (gpt-4o-mini) for narration — chosen because narration is the only LLM job and needs reliability, not scale; falls back to local Ollama, then to a deterministic template. The system stays fully functional with **no** LLM at all — that's the point.

## How to run it
Prereqs: Python 3.12, a ClickHouse service, `.env` from [`.env.example`](.env.example).

```bash
pip install -r requirements.txt

# 1. Load a dataset (creates ad_events, dims, denormalized events; verifies integrity)
python scripts/load_clickhouse.py --database rca --parquet <path-to-ad_events.parquet>

# 2. Run the full investigation pipeline (build cube -> detect -> attribute -> narrate -> trace)
python run_incident.py --rebuild-cube --trace

# 3. Serve the API + dashboard
uvicorn api.server:app --port 8077
RCOS_API=http://localhost:8077 streamlit run ui/app.py

# Optional: LibreChat chat interface (needs Docker; shim on :8601)
python integrations/openai_shim.py &
docker compose -f integrations/librechat/docker-compose.yml up -d
```

To point everything at a new dataset (e.g. the unseen slice): set `CLICKHOUSE_DATABASE=<new_db>` in `.env` — CLI, API, and dashboard all resolve the database at call time. Full runbook: [`teamkit/RUNBOOK.md`](teamkit/RUNBOOK.md).
