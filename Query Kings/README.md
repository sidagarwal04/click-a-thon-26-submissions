# Query Kings

## Track

Atlys

## Project

**Schema Kings** — From feature spec to insight: agents that instrument ClickHouse, keep business context fresh, analyze warehouse data, and explain results for a product audience — fully traced in Langfuse.

## Team Members

- Shivam Taneja ([shivam-taneja](https://github.com/shivam-taneja))
- Divyansh Gupta ([divyanshg](https://github.com/divyanshg))

## What it does

Atlys ships product fast; every feature still needs instrumentation, schema design, and analysis, and context gets lost across handoffs.

We collapse that loop into one agentic pipeline on ClickHouse:

1. **Instrumentation Agent** — takes a feature spec (`spec.md` + `events.ndjson`) → Bronze audit → LLM schema design/critic with guardrails → Silver tables → Gold MVs
2. **Context Agent** — writes a living context layer in ClickHouse (`context.*`) only after Silver validation; surfaces contradictions and gaps
3. **Analytics Agent** — answers PM questions with warehouse-backed SQL, numbers-first insights, confidence, and an evidence critic
4. **Tracing + visualization** — every run is traced in Langfuse; a report UI (`cli serve`) shows schema over time, insights, and context changelog

Hybrid trust model: LLMs draft intent, plans, SQL, and prose; deterministic code retrieves context, blocks mutating SQL, executes ClickHouse, validates loads, and strips unsupported claims.

All dataset content is **synthetic**. No real customer data or PII.

## Hosted Demo

**[Live demo](https://schema-kings.onrender.com)** — report UI with Ask box, instrumented features, context changelog, and Langfuse deep-links.

The demo covers:

- End-to-end instrumentation of feature specs
- Analytics Agent answers (including the standard probe prompts)
- Context freshness (before/after when a new table lands)
- Langfuse traces for pipeline + ask runs (6th-spec trace mandatory)

## Demo Video

**[Demo video (2–3 min)](https://youtu.be/tt9ONsv0zG4)**

## Architecture

See [`Architecture.md`](./Architecture.md) for the full 1–2 pager.

## Pitch deck

[`pitch-deck.pdf`](./pitch-deck.pdf)

## Graded artifacts

See [`artifacts/`](./artifacts/) — DDL (specs 01–06), context changelog/diffs, analytics asks, 6th-spec bundle.

## How to run it

**Full setup + the one end-to-end command:** see [`RUN.md`](./RUN.md).

### Supported platforms

| Platform                                  | Local one-command (`./run-local.sh`) | Notes                                                |
| ----------------------------------------- | ------------------------------------ | ---------------------------------------------------- |
| **macOS**                                 | Supported                            | Primary path we develop on                           |
| **Linux**                                 | Supported                            | Same bash + Docker Compose flow                      |
| **Windows (WSL2)**                        | Supported                            | Run inside WSL + Docker Desktop with WSL integration |
| **Windows (PowerShell / CMD / Git Bash)** | **Not supported**                    | Native Windows will not work — use WSL2              |

This is **not** macOS-only. `brew …` lines below are macOS shortcuts; on Linux/WSL use the generic installers instead.

`./run-local.sh` checks prerequisites up front (Docker running, Compose, Node 22+, pnpm, `.env` keys) and exits with a clear error if something is missing.

After prerequisites and `backend/.env` are ready:

```bash
cd source_code
./run-local.sh
```

Reset local Docker anytime, then re-run:

```bash
cd source_code
./clean-local.sh
./run-local.sh
```

### Prerequisites

| Tool                                           | Why                                        | Install                                                                                                   |
| ---------------------------------------------- | ------------------------------------------ | --------------------------------------------------------------------------------------------------------- |
| **Docker Desktop** (or Docker Engine on Linux) | ClickHouse + Langfuse via `docker compose` | [Docker Desktop](https://www.docker.com/products/docker-desktop/) — open the app so the daemon is running |
| **Node.js 22+**                                | Backend CLI / report server                | [nodejs.org](https://nodejs.org/) · macOS also: `brew install node`                                       |
| **pnpm**                                       | Package manager for `source_code/backend`  | `npm install -g pnpm` · macOS also: `brew install pnpm`                                                   |
| **Groq API key**                               | LLM stages in all three agents             | [console.groq.com](https://console.groq.com/)                                                             |
| **Bash / WSL** (Windows)                       | `run-local.sh` is bash                     | [WSL](https://learn.microsoft.com/en-us/windows/wsl/install)                                              |

Verify:

```bash
docker --version
docker compose version
node --version   # v22+ recommended
pnpm --version
```

Then open [`RUN.md`](./RUN.md).
