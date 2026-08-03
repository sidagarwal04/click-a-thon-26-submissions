# Metric Mind

**Code package:** `clickathon` — automated root-cause analyst for the [ClickHouse Click-a-thon 2026](https://github.com/sidagarwal04/click-a-thon-2026) **InMobi** track.

When a key ad-platform metric moves, this system detects the deviation, drills into the responsible segment (app, device, geo, advertiser, format), and returns a short plain-language diagnosis backed by computed numbers.

## Problem

**From alert to answer** — detect → localize → explain, with ClickHouse as the analytical engine.

## Stack

| Layer | Where |
|---|---|
| **ClickHouse Cloud** | Ad events + dims (analytical engine); OTel tables for ClickStack |
| **Langfuse Cloud** | LLM / investigation traces |
| **LibreChat** | Docker Compose chat UI + agents |
| **ClickHouse MCP** | Docker Compose → Cloud CH |
| **ClickStack** | Docker Compose (HyperDX + OTel collector) → Cloud CH |

Compose lives in [`stack/`](stack/) (trimmed from [agentic-data-stack](https://github.com/ClickHouse/agentic-data-stack) + [ClickStack](https://github.com/ClickHouse/ClickStack)).

## Python (uv)

```bash
uv sync
uv run clickathon
```

Requires Python ≥3.12. Dependencies are locked in `uv.lock`.

## Dataset

Synthetic InMobi ad-events star schema (~9M events, Jun–Jul 2026):

| Table | Role |
|---|---|
| `ad_events` | Fact: requests, fills, impressions, clicks, revenue |
| `apps` | App category & publisher tier |
| `advertisers` | Vertical & campaign type |
| `geo_device` | Region, country, device, OS |

## Metrics

Fill rate, CTR, eCPM, revenue, and RPR — computed per the hackathon
[metrics glossary](https://github.com/sidagarwal04/click-a-thon-2026/blob/main/InMobi/metrics_glossary.md).

## Docs

- Submission pack (parent): [`../README.md`](../README.md), [`../Architecture.md`](../Architecture.md)
  (run + verify instructions are in the parent README)
- [architecture.md](architecture.md) — multi-agent topology, MCP, Langfuse/OTel
- [stack/README.md](stack/README.md) — Compose URLs, RCA agents, CLI

Tracked SQL for RCA materialize: [`sql/`](sql/).

## Quick start (LibreChat agents)

```bash
uv run clickathon materialize
docker compose -f stack/docker-compose.yml --env-file .env up -d
```

Open http://localhost:3080 → pick **InMobi RCA Orchestrator** → ask:

`What are the anomalies?`

CLI:

```bash
uv run clickathon materialize --check --calibration
uv run clickathon investigate 2026-06-23
```

## Config

Copy `.env.example` → `.env` (gitignored) and fill Cloud credentials.

## License

MIT — see [LICENSE](LICENSE).
