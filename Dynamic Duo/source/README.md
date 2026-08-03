# Automated Root-Cause Analyst

A user sees ad-exchange incidents in LibreChat, asks about one, and the system drills
down **live** — a fixed, deterministic q1–q6 ClickHouse query sequence via MCP — then
presents the guard-railed evidence. ClickHouse computes every number; the LLM narrates
and formats only; every step leaves a queryable trace.

- **[CLEAN_RUN.md](CLEAN_RUN.md)** — from nothing to a working system in one script,
  plus the Day-2 path for loading a new data slice without a wipe
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — the system, contracts, and component states
- **[librechat/README.md](librechat/README.md)** — the product surface: agent setup and
  the manual step-by-step equivalent of the script
- **[librechat/GOLDEN_QUESTIONS.md](librechat/GOLDEN_QUESTIONS.md)** — the checkpoint
  checklist with expected numbers
- **[EDGE_CASES.md](EDGE_CASES.md)** — the regression fixture: anomaly mechanisms the
  dev data never contained, the two-sided seasonality test, and the release-day
  report runner

## Layout

| path | what |
|---|---|
| `sql/00–07,99` | schema, MV cascade, read-only user, load-time validation |
| `sql/agent/` | the fixed drill-down queries q1–q6 (validated: `VALIDATED.md`) |
| `load.sh` | loader: local `clickhouse local`, local docker server, or Cloud |
| `detector/` | platform: ClickHouse access, tracing, guardrail + (parked) detection |
| `agent/` | the runner: fixed q1–q6 sequence, branching on numbers, narrator |
| `rca_mcp/` | custom MCP server: `list_incidents` / `investigate` / `investigate_window` |
| `librechat/` | the product surface: compose stack, agent instructions, checklists |

## Quickstart

```bash
cd librechat && cp .env.example .env    # set OPENAI_API_KEY
cd .. && ./clean_run.sh --yes           # wipe → load → boot   (add --unseen-dir DIR for the unseen slice)
./investigate.sh                        # detect + diagnose, when you're ready
```

One manual moment: clean_run pauses for the HyperDX connection wizard, then finishes on
its own. Full walkthrough with expected numbers at each stage, and the troubleshooting
table: **[CLEAN_RUN.md](CLEAN_RUN.md)**.
