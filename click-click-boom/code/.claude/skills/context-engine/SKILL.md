---
name: context-engine
description: Use this skill before running any EDA, funnel, or insight query against the Atlys `atlys` ClickHouse database, or before trusting a business/data claim about it. Loads the current business context from `agent_meta.current_context` and explains the two-database split, the context taxonomy, the size-capped ClickHouse tool pattern this repo's own agents use, and known gotchas baked into the context (funnel timestamp ordering, FX normalization, no session entity, etc.) so queries and insights are grounded instead of re-deriving (or contradicting) already-verified facts. Triggers on: "query atlys", "check the context", "what does the context say about X", "funnel analysis", "EDA on atlys", "is this consistent with base context".
---

# Context Engine — reading the Atlys context layer

Two databases live on the same ClickHouse Cloud service (`atlys-agents/.env` → `CLICKHOUSE_HOST`). Do not confuse them:

- **`atlys`** — the 8 raw event tables (ground truth, ~2.5M rows). This is what you run EDA/analysis against.
- **`agent_meta`** — the *context layer*: business definitions (entity/metric/table/convention/issue docs) plus this repo's own pipeline's workflow state (`schema_proposals`, `schema_reviews`, `test_cases`/`test_runs`, `insights`, `context_versions`). Schema: `atlys-agents/sql/agent_meta_ddl.sql`. Read the context layer **before** writing analysis queries so you don't re-derive (or contradict) things already checked.

This is the same live ClickHouse Cloud service used by the actual pipeline (`atlys-agents/agents/create_agents.py`, `orchestrator/pipeline.py`) — `agent_meta` isn't a snapshot or a doc dump, it's the exact table this repo's Instrumentation/Reviewer/Chronicler/Analytics agents read and write via MCP at runtime.

## Connecting

Credentials live in `atlys-agents/.env` (gitignored — copy `atlys-agents/.env.example`, never commit the real file). Vars are `CLICKHOUSE_HOST`/`CLICKHOUSE_PORT`/`CLICKHOUSE_USER`/`CLICKHOUSE_PASSWORD` (no `https://` prefix on the host).

The repo's own code (`agent_meta/db.py`) connects via the `clickhouse_connect` Python client from inside `atlys-agents/.venv`. From a bare Claude Code shell that venv's `clickhouse_connect` may hit a local CA bundle issue (`SSLCertVerificationError: unable to get local issuer certificate`) — that's this sandbox's Python cert store, not the service. The reliable path for ad-hoc queries is the plain HTTPS HTTP-interface via `curl`, which uses the system CA store and just works:

```bash
cd atlys-agents && set -a; source .env; set +a
curl -s -u "$CLICKHOUSE_USER:$CLICKHOUSE_PASSWORD" --data-binary "SELECT 1" \
  "https://$CLICKHOUSE_HOST:$CLICKHOUSE_PORT"
```

For anything beyond a one-liner, write the query to a variable/heredoc and POST it as `--data-binary` — avoids URL-encoding headaches for queries with `'`, `%`, newlines. If you're running inside `.venv` (e.g. reusing `agent_meta/db.get_client()`), it should work fine too — the cert issue is sandbox-shell-specific, not a hard blocker either way.

## Reading context: `agent_meta.current_context`

```sql
SELECT section, content, confidence, last_updated
FROM agent_meta.current_context
ORDER BY section
```

This is a **view**, not a table: `argMax(after, ts)` grouped by `section` over `agent_meta.context_versions` (the real, append-only log — see the `context-update` skill for writing to it). `content` is a JSON **string** with a consistent shape:

```json
{"title": "...", "summary": "...", "body": "...", "fields": {...}, "sources": ["..."]}
```

Parse it (don't just eyeball the raw string) — `fields` often holds the exact number/formula you need, and `sources` tells you what evidence backs the claim.

**Read `confidence` before trusting a section.** Observed calibration in this project:
- `0.9+` — directly verified against `atlys` with a specific query, cite-able.
- `0.7–0.85` — carried over from the base spec doc or documented but not independently re-verified.
- `≤0.4` — explicitly untested/unconfirmed (check `fields.status` — usually says `untested`, `contradicted`, or `directionally_confirmed`).

Don't state a `≤0.4`-confidence claim as fact in an insight — either re-verify it first or flag it as open.

## How the real pipeline agents query this (mirror this pattern for ad-hoc EDA too)

This repo already has size-capped MCP tools for exactly this purpose — read them before hand-rolling raw queries, since they encode hard-won lessons:

- **`mcp_servers/context_server.py`** — `list_context_sections()` (section + confidence + one-line summary, cheap) and `lookup_context(sections)` (full content for specific keys). Every real agent calls `list_context_sections` first, then `lookup_context` only for what it needs — never dumps the whole context layer into one call.
- **`mcp_servers/data_tools_server.py`** — `list_tables`/`describe_table` (narrow: name+type only, no comments/codecs/stats — the official `mcp-clickhouse` server's equivalent measured at ~15,500 tokens/call and blew up multi-turn agent runs to ~90-100K input tokens), `run_query` (read-only, hard-capped at 10,000 rows regardless of your own `LIMIT`, offloads anything past ~20 rows/3000 chars to an NDJSON scratch file with `grep_scratch`/`read_scratch` to page through it), and `execute_python` (pandas-only, no other imports, for post-aggregation analysis SQL can't express cleanly).

If you're querying `atlys` directly via curl instead of through these tools, apply the same discipline by hand: always aggregate (`GROUP BY`/`count`/`uniq`) rather than dumping raw rows, always add your own `LIMIT`, and describe one table at a time rather than every table's full schema at once.

## The category taxonomy (informal — no schema enforcement)

`section` is a plain `String`, not an `Enum`, and there is no catalog/taxonomy table anywhere in `agent_meta`. The categories are a pure naming convention (`category:name`) — confirm the live list rather than trusting a hardcoded count, since this pipeline actively adds tables/metrics as new specs land:

```sql
SELECT splitByChar(':', section)[1] AS category, count() AS c
FROM agent_meta.current_context GROUP BY category ORDER BY c DESC
```

As of the last check: `table` (10), `metric` (9), `issue` (7, K1–K7), `entity` (5), `convention` (2), `overview` (1), `dataquality` (1), `relationship` (1 — `join_map`). If you invent a new category prefix while writing context (via the `context-update` skill), that's a deliberate act, not an accident — make sure it's warranted.

## Gotchas already baked into the context — respect these before you write a query

- **`convention:funnel_analysis`**: `windowFunnel`/`sequenceMatch` is only safe for `destination_card_clicked→application_started→document_uploaded` (95–100% chronologically ordered). Past `document_uploaded`, ~50% of matched `application_id` pairs are out of timestamp order — `windowFunnel` there undercounts by ~6x. Use `uniqExact` joined by `application_id`, order-agnostic, for anything touching `pay_now_clicked`/`purchase_completed`.
- **`metric:revenue_per_conversion`**: `value` is in 9 different raw currencies, not FX-normalized. Never average/sum it across currencies without an explicit FX step.
- **`metric:conversion_rate`**: a "sessions" denominator is not implementable — there's no session entity in the raw tables (`app_session_id` is 1:1 with rows, a synthetic-data artifact). Use the `application_started`-denominator definition instead.
- **`entity:application`**: `eta_shown` is a `Nullable(String)` bucket (`"3-5 days"`), not an integer days column — that column doesn't exist. `on_time_delivery_rate` is not computable from these 8 tables.
- **`dataquality:envelope`**: every table in this dataset is 1:1 `user_id`:row — a synthetic-data artifact, not evidence that repeat events/applications are rare in production.

## Before treating `agent_meta` schema/proposal status as truth

`schema_proposals.status = 'executed'` does not guarantee the table exists right now — verify against `system.tables` first:
```sql
SELECT database, name FROM system.tables WHERE name = '<table_name>'
```
(`express_checkout_events` was a known example where this drifted — proposal marked `executed` multiple times across many revisions, but the table wasn't live at last check. Re-verify, don't assume it's since been reconciled.)
