# RUN.md — Atlys track (team: till_the_last_row)

How to run the three-agent pipeline (Instrumentation → Context → Analytics) end to end,
fully traced in Langfuse, against our own ClickHouse Cloud service.

The agents run **inside LibreChat**. All database, git, and file I/O happen through
**MCP servers** — the agents themselves have no shell. Orchestration is via LibreChat
**Subagents** (the Instrumentation Agent is the parent and calls Context, then Analytics,
as isolated subagents, keeping conversation control and combining the result).

---

## 1. Prerequisites

- Docker + Docker Compose
- A ClickHouse Cloud service with the `atlys` database loaded (8 base tables)
- A GitHub PAT with `repo` scope (used by the git MCP to push generated schemas)
- A Langfuse project (host + public/secret keys) for tracing
- LiteLLM gateway API key (the agents run on `opus-4.x` via LiteLLM)

---

## 2. Environment variables

Set these in `librechat/.env` (already gitignored — never commit real secrets).
Only the Atlys-specific keys are listed; standard LibreChat keys are omitted.

| Var | Purpose |
| --- | --- |
| `CH_HOST` | ClickHouse Cloud host (e.g. `xxxx.azure.clickhouse.cloud`) |
| `CH_USER` | ClickHouse user (`default`) |
| `CH_PASSWORD` | ClickHouse password |
| `CH_DATABASE` | Database all tables/MVs live in (`atlys`) |
| `GITHUB_TOKEN` | GitHub PAT (`repo` scope) — git MCP pushes generated schemas |
| `CH_TARGET_REPO` | Repo the schema is committed to (`https://github.com/srinidhi-22/tillthelastrow.git`) |
| `CH_TARGET_BRANCH` | Branch pushed to directly (`master`) |
| `GIT_AUTHOR_NAME` / `GIT_AUTHOR_EMAIL` | Commit identity for the git MCP |
| `LITELLM_API_KEY` | Auth for the LiteLLM gateway serving `opus-4.x` to both agents |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_BASE_URL` | Langfuse tracing |
| `MONGO_URI` | mongodb+srv://clickathon:gbiDfrZhujlCsadL@cluster0.opmad.mongodb.net/librechat_clickathon?appName=Cluster0 |

> Note: `ANTHROPIC_API_KEY` in `.env` is the sentinel `user_provided` — we do **not** use a
> standalone Anthropic key. Both agents authenticate to Anthropic models through LiteLLM.

---

## 3. Start the stack (one command)

```bash
cd librechat
docker compose up -d
```

This brings up:

| Service | Role |
| --- | --- |
| `LibreChat` (`api`) | Agent runtime + UI. Mounts `librechat.yaml`, `./context_docs` → `/app/context_docs`, `./specs` → `/app/specs`, and the auto-loaded skills in `./skill`. |
| `clickhouse-mcp-write` | MCP `clickhouse_write_tools` — `run_query` (DDL/DML) + `list_databases` / `list_tables` against ClickHouse Cloud. Used by the Instrumentation Agent. |
| `clickhouse-git-write` | MCP `clickhouse_git_write` — `write_and_push(relative_path, content, message)`; commits + pushes generated `.sql` / `.insights.json` directly to `master`. |

Plus two hosted/streamable MCP servers referenced in `librechat.yaml`:

- `clickhouse-cloud` — hosted **read-only** ClickHouse MCP (analysis queries + introspection).
- `filesystem` — reads/writes the context bundle at `/app/context_docs` and reads specs at `/app/specs`.

Open LibreChat at the configured host (default `http://localhost:3080`).

---

## 4. One-command pipeline run (the automated flow)

The pipeline is triggered from a **single chat message** to the **Instrumentation Agent**.
In a **new conversation** with the Instrumentation Agent, send:

```
Onboard the spec at /app/specs/unseen_data (events.ndjson + spec.md).
Profile it, design + validate the schema, apply it on Cloud, push it, then refresh
context and run the analytics — the full pipeline.
```

The Instrumentation Agent then, in one traced run:

1. Profiles the NDJSON (discriminator, paths, ORDER BY candidates).
2. Designs production DDL (JSON-`payload` base table + AggregatingMergeTree rollup + MV).
3. Validates on Cloud via MCP (static lint + throwaway `__val` table), then smoke-tests.
4. Pushes `Atlys/schemas/{spec}.sql` + `.metrics.json` via `clickhouse_git_write`.
5. **Subagent call → Context Agent**: refreshes the `/app/context_docs` OKF bundle, bumps
   `context_version`, appends a `log.md` entry, returns a compact summary.
6. **Subagent call → Analytics Agent** (pipeline mode): reads the freshly-bumped context,
   analyzes the new table across segments, writes `Atlys/schemas/{spec}.insights.json`,
   returns a compact summary.
7. Combines everything into one final report (schema commit URLs + context version +
   insight summary), with the full chain visible as one Langfuse trace.

### Required UI setup (once)

- **Instrumentation Agent** — Tools: `clickhouse_write_tools`, `clickhouse_git_write`,
  `filesystem`, `clickhouse-cloud`. Subagents: **Context Agent**, then **Analytics Agent**.
- **Context Agent** — Tools: `filesystem`, `clickhouse-cloud` **only** (no git/write tools).
- **Analytics Agent** — Tools: `clickhouse-cloud`, `clickhouse_git_write`, `filesystem`.
- Each agent's **Instructions** = the matching `agents/*/SYSTEM_PROMPT.md` (pasted in the UI;
  stored in Mongo, not file-loaded).
- Model for all agents: LiteLLM `opus-4.x`.

---

## 5. Interactive mode (Analytics only)

In a new conversation with the **Analytics Agent**, ask ad-hoc questions, e.g. the four
standard probes:

1. "Analyze the existing funnel and surface the most important issues, with the why."
2. "Where are we losing conversions, and for which segments (device / geo / destination)?"
3. "Are there any regressions or trends over the last quarter?"
4. "Is anything in the base context wrong, stale, or self-contradictory?"

It reads the current context from `/app/context_docs`, pushes aggregation into ClickHouse
(never streams raw rows), and narrates PM-ready insights. Every turn is traced in Langfuse.

---

## 6. Where outputs land

| Artifact | Location |
| --- | --- |
| Generated DDL + metrics manifest | `Atlys/schemas/{spec}.sql`, `Atlys/schemas/{spec}.metrics.json` (git) |
| Insights manifest | `Atlys/schemas/{spec}.insights.json` (git) |
| Living context bundle | `librechat/context_docs/` → `/app/context_docs` (filesystem MCP) |
| Context changelog | `librechat/context_docs/log.md` + `overview.md` `context_version` |
| Traces | Langfuse project (per-agent named spans; the full chain is one trace) |

---

## 7. Reload rules (when you change things)

- Edit an existing `SKILL.md` **body** → new conversation picks it up.
- Add/remove a skill, change skill **frontmatter**, or edit `librechat.yaml` → `docker restart LibreChat`.
- New compose mount → `docker compose up -d api`.
- Edit a `SYSTEM_PROMPT.md` → **re-paste** into the agent's Instructions in the UI (Mongo-stored).

To get the visualisations run the following script - python3 Atlys/schema-timeline/server.py 
