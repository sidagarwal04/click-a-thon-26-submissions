# atlys-PrismCH

Agentic analytics on **ClickHouse Cloud**: three cooperating agents
(Instrumentation, Context, Analytics — see [ARCHITECTURE.md](ARCHITECTURE.md))
plus a small Python service (`prism_ch`) with a browser UI, a CLI, and an MCP
server. The agents connect to your ClickHouse Cloud service directly; the app
itself runs under Docker Compose.

> **Hackathon scope:** this repo is the Click-a-thon 2026 entry. Requirement
> tracking lives in [REQUIREMENTS.md](REQUIREMENTS.md) — what is done, what is
> pending, and how each item maps to the judging criteria. The graded
> submission artifacts (generated DDL, insight reports, context changelog,
> Langfuse trace index) live under [`submission/`](submission/README.md).

## Live deployment

- [Open the Atlys Prism application](https://atlys-prism-ch-production.up.railway.app/)
- [View the Langfuse tracing project](https://cloud.langfuse.com/project/cmsbbs6ow0thvad0drb59z37m)

## Demo videos (video in artifact folder)

- [Product walkthrough](<artifacts/Screen Recording 2026-08-02 at 11.34.12 AM.mov>)
- [Agent workflow and tracing demo](<artifacts/Screen Recording 2026-08-02 at 11.41.41 AM.mov>)

**New machine? Start with [SETUP.md](SETUP.md)** — copy-paste, step by step,
from zero to a running UI. **Judge running this to verify the submission?
Start with [RUN.md](RUN.md)** — env vars, our ClickHouse Cloud connection,
and the one command that runs the pipeline end to end.

---

## Requirements

- Docker Engine 20.10+ with the Compose v2 plugin (`docker compose`)
- GNU Make
- A ClickHouse Cloud service (free trial works) — there is no local ClickHouse container
- An API key for one LLM provider (Gemini, Anthropic, or OpenAI)
- Python 3.11+ — only if you want to run the service outside a container

---

## The dataset package

The organiser's package — `base_context.md`, `data/`, `specs/` — is **provided
input, not source**, so it is never committed. Link it in once:

```bash
ln -s /path/to/Atlys inputs
```

`inputs` is gitignored. Everything that reads the package uses that path, so
`make context` and `make instrument` take no arguments on any machine:

```bash
make context                               # ingests inputs/base_context.md
make instrument SPEC=inputs/specs/01_express_checkout
```

A symlink rather than a copy on purpose: the sixth spec is released mid-event
and lands in the package directory. With a copy there would be two trees to keep
in step, and ingesting the stale one is a silent failure at the worst moment.
Set `ATLYS_PACKAGE=...` if you keep the package somewhere a link cannot reach.

---

## Quick start

**Full copy-paste, step-by-step setup (including getting ClickHouse Cloud and
an LLM key from scratch): see [SETUP.md](SETUP.md).** The short version, once
`.env` is filled in:

```bash
make env      # copy .env.example to .env — fill in CLICKHOUSE_* and an LLM key first
make up       # start the app (there is no local ClickHouse container — Cloud only)
make ui       # open http://localhost:8000
```

| URL | Purpose |
| --- | --- |
| http://localhost:8000 | The Prism CH UI (Instrument / Analysis / Context / Schema) |
| http://localhost:8000/api/health | Health check — confirms ClickHouse + the configured LLM |

### With tracing

```bash
make up-obs && make langfuse-ready && make langfuse
```

Adds the Langfuse stack (see [Tracing](#tracing) below) at
http://localhost:3000. First boot runs database migrations and takes a minute.
Do **not** set `LANGFUSE_BASE_URL` — it silently overrides `LANGFUSE_HOST` and
breaks every containerised run (see [Troubleshooting](#troubleshooting)).

---

## What is in the box

```
.
├── docker-compose.yml              app + Langfuse services (no local ClickHouse)
├── Dockerfile                      Multi-stage build for the app
├── Makefile                        Every workflow below
├── requirements.txt                Runtime dependencies
├── requirements-dev.txt            + lint / typecheck / test
├── .env.example                    All tunables, documented
├── sql/001_schema.sql              Context-layer schema
├── prism_ch/                       The application package (agents, UI, MCP server)
└── tests/                          Unit tests (no ClickHouse needed)
```

---

## Make targets

```bash
make help
```

| Target | What it does |
| --- | --- |
| `env` | Create `.env` from `.env.example` (never overwrites) |
| `up` | Start the app |
| `up-obs` | Start the app + Langfuse tracing stack |
| `down` | Stop containers, keep data volumes |
| `ps`, `logs`, `logs-app` | Status and log tailing |
| `bootstrap` | Apply the context-layer schema |
| `client`, `tables`, `query` | Interactive `clickhouse-client`, list tables, run one query |
| `instrument`, `context`, `analyze` | Run the three agents from the CLI |
| `ui` | Open the browser UI |
| `install`, `install-dev`, `lock` | Virtualenv and dependency management |
| `run` | Run the service on the host, against the ClickHouse Cloud instance in `.env` |
| `lint`, `fmt`, `typecheck`, `test`, `check` | Quality gates |
| `clean` | Remove caches and the virtualenv |
| `destroy` | Stop the stack **and delete all ClickHouse/Langfuse data** (prompts first) |

---

## Configuration

Every value lives in `.env` (see [.env.example](.env.example) and
[SETUP.md](SETUP.md) for where to get each one). The ones you must set:

| Variable | Purpose |
| --- | --- |
| `CLICKHOUSE_HOST` / `PORT` / `USER` / `PASSWORD` / `DB` | Your ClickHouse Cloud service |
| `CLICKHOUSE_TARGET` | `cloud` (default) — leave as-is unless you run your own cluster |
| `LLM_PROVIDER` / `LLM_MODEL` | `gemini` / `gemini-2.5-flash-lite` by default |
| `GOOGLE_API_KEY` (or `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`) | Whichever matches `LLM_PROVIDER` |
| `APP_PORT` | `8000` by default |

---

## Tracing

Langfuse runs self-hosted under the `langfuse` Compose **profile**, so the
default `make up` stays at two containers and tracing is opt-in per command:

```bash
make up-obs
```

Use `LANGFUSE_HOST=http://localhost:3000` for commands run on the host. Compose
services use `LANGFUSE_DOCKER_HOST=http://langfuse-web:3000` (the default), so
host and container tracing work simultaneously.

| Target | Purpose |
| --- | --- |
| `up-obs` | Start everything including Langfuse |
| `langfuse` | Open the UI |
| `langfuse-ready` | Block until the health endpoint answers |
| `langfuse-logs` | Tail web + worker logs |
| `langfuse-secrets` | Generate real secrets for `.env` |
| `langfuse-down` | Stop tracing services, leave ClickHouse running |
| `trace-check` | Emit one demo trace and verify it lands |

### The tracing layer

[prism_ch/tracing.py](prism_ch/tracing.py) is the only module that touches the
Langfuse SDK. Agents talk to `Run` and `Step` instead, which keeps SDK churn
contained to one file. Four properties it enforces:

**Tracing never breaks the pipeline.** Every SDK call goes through `_safe()`. If
the collector is down, credentials are wrong, or the SDK changes shape, you get a
debug line and the run continues. A dropped trace costs one criterion; a crashed
run on the unseen spec costs everything. With tracing off, the decision log still
prints to stdout — you keep a plain-text reasoning record either way.

**Reasoning is mandatory.** `Step.decision()` takes `why` as a required keyword,
so an agent cannot record what it chose without recording why:

```python
with agent_step("instrumentation", "design_schema") as step:
    step.decision(
        what="ORDER BY (agent_id, event_time)",
        why="agent_id appears in ~90% of predicates; event_time gives range pruning",
        alternatives=["(event_time, agent_id)"],
        confidence=0.82,
        evidence={"predicate_frequency": {"agent_id": 0.91}},
    )
```

**Context version travels with analytics.** `agent_step()` takes
`context_version`, and warns when an analytics step omits it — a conclusion whose
context version is unknown cannot be audited.

**Runs are identifiable.** `pipeline_run()` mints a `run_id` that becomes the
Langfuse session id. Print it beside any submitted artifact and a judge can match
output to the trace that produced it.

`Step.sql()` records queries pushed down to ClickHouse, which doubles as evidence
that aggregation ran server-side rather than in the LLM's context window.

Every LLM generation inside an agent step is named `agent:<agent>` and carries
`metadata.agent` plus `metadata.operation`. To chart spend by agent in Langfuse,
create an observations widget with **Total cost / Sum**, grouped by
**Observation name**, and filter observation type to **Generation**. New traces
then appear as `agent:instrumentation`, `agent:analytics`, and `agent:context`.

```bash
make trace-check
```

Emits a complete demo trace — root run, one span per agent, decisions with
reasoning, a pushed-down query, a confidence score. Exits non-zero if nothing
reached Langfuse. Worth running again right before the unseen-spec drop.

### Two ClickHouse servers, on purpose

Langfuse v3 stores traces in ClickHouse too, and this stack gives it a **separate
instance** (`langfuse-clickhouse`) rather than sharing the analytics one. Its
migrations own that database, so keeping them apart means `make tables` and any
judge poking at `system.tables` only ever sees our schema. It also matches the
topology upstream documents and tests, which matters when something breaks and
you are reading their issue tracker.

The cost is roughly 1–2 GB of RAM while the profile is up. That is the reason it
sits behind a profile instead of running always.

### Credentials

First boot runs Langfuse's headless initializer, which creates the org, project,
user, and a **fixed API key pair** from `.env`. Agents get working credentials
with no UI clicks, and wiping the volume reproduces the same setup — which keeps
a trace-producing run repeatable.

Defaults: `dev@prism.local` / `prismdev123`, keys `pk-lf-prism-dev` /
`sk-lf-prism-dev`.

> `.env.example` ships placeholder values for `LANGFUSE_SALT`,
> `LANGFUSE_NEXTAUTH_SECRET` and `LANGFUSE_ENCRYPTION_KEY`. Run
> `make langfuse-secrets` and paste real ones in before this is reachable by
> anyone but you. `ENCRYPTION_KEY` must be exactly 64 hex characters or Langfuse
> refuses to start.

### Ports

MinIO's API sits on host **9090** (console 9091) because the analytics
ClickHouse already owns 9000. Postgres and Redis are not published at all —
nothing outside the Compose network needs them.

---

## Local development

```bash
make install-dev
make run
```

Runs the app on the host, against the ClickHouse Cloud instance configured in
`.env` (no local ClickHouse container exists). Tests are pure unit tests — they
exercise config parsing, schema rendering, and the agents against fakes, and
need no running ClickHouse:

```bash
make check
```

---

## Docker image

Multi-stage build ([Dockerfile](Dockerfile)): dependencies compile into a venv in
the builder stage, and only `/opt/venv` plus the source are copied into the
`python:3.12-slim` runtime. The container runs as the non-root `prism` user
(uid 10001).

The entrypoint is `python -m prism_ch`, so the Compose command is just the
subcommand name:

```bash
docker compose run --rm app info
```

Available subcommands: `serve` (default — the UI), `bootstrap`, `info`,
`health`, `instrument`, `context`, `context-log`, `analyze`, `trace-check`, `mcp`.

---

## Troubleshooting

**Container shows "unhealthy" but the app works fine.** Known cosmetic bug: the
Dockerfile's `HEALTHCHECK` probes `/health`, which doesn't exist — the real
health endpoint is `/api/health`. Confirm with `curl http://localhost:8000/api/health`;
if that returns `{"ok": true, ...}` the app is fine regardless of what `docker
compose ps` shows.

**Langfuse traces never show up / "langfuse unreachable" in the logs.** Almost
always `LANGFUSE_BASE_URL` set in `.env`. The SDK reads it and it takes
precedence over `LANGFUSE_HOST`; pointed at `localhost` it breaks every
containerised run because `localhost` inside the `app` container isn't
`langfuse-web`. Delete the line entirely — `LANGFUSE_HOST` is enough.

**`could not connect to ClickHouse` / DDL fails immediately.** Check
`CLICKHOUSE_PORT=8443` and `CLICKHOUSE_SECURE=true` for Cloud — port `9440` is
the *native* protocol (correct for `clickhouse-client`, wrong for the agents,
which speak HTTP) and the failure looks like "Port 9000 is for clickhouse-client
program" or a TLS handshake error.

**Port already allocated.** Change `APP_PORT` in `.env`.

**Schema changes are not picked up.** `CREATE ... IF NOT EXISTS` will not alter
an existing table — the Instrumentation Agent widens an existing table with
`ALTER TABLE ADD COLUMN` instead of recreating it, by design (never drops data).
