---
name: atlys-git-pr
description: Commit a validated Atlys ClickHouse schema and push it DIRECTLY to the target branch (default master, no feature branch, no PR) using the clickhouse_git_write MCP — no shell/git/gh needed. The MCP holds the repo clone + a GitHub PAT; you call write_and_push(relative_path, content, message). Then, only if the push succeeded, OPTIONALLY (with user confirmation) wire Vector ingestion for the new table via skill atlys-vector-ingestion, then DELEGATE the context refresh to the Context Agent AND THEN the analysis to the Analytics Agent via two sequential LibreChat Subagent calls (Context first, Analytics second), passing file pointers, and report the combined result — completing the spec→schema→(ingest)→context→insight pipeline in one traced run. Invoke only after the MCP validation gate + Cloud test pass.
---

# Skill: Git Commit, Direct Push (via MCP), Context Refresh & Analytics (Subagents)

Run only after the static lint, the MCP validation gate (`atlys-chdb-validation`), and the Cloud
test (`atlys-cloud-test`) have all passed.

> **There is no shell / git / gh in this runtime.** Committing and pushing happen through the
> **`clickhouse_git_write` MCP**, which holds the repo clone and a GitHub PAT and pushes for you.
> Do **not** try to run `git`/`gh` commands and do **not** stop and hand the user shell commands —
> use the MCP tools below.
>
> This pushes the schema **directly to the target branch** (`$CH_TARGET_BRANCH`, default `master`).
> It does **not** create a feature branch and does **not** raise a PR.

## Tools (all on `clickhouse_git_write`)

| Tool | Purpose |
|---|---|
| `repo_status()` | Refresh the clone; returns `repo`, `branch`, `head` sha, `dirty_files`. |
| `list_schemas()` | List existing files under `Atlys/schemas/` (use to check for name collisions). |
| `write_and_push(relative_path, content, message)` | Write the file in the repo, commit on the target branch, push **directly** to it, return the commit sha + URL. |

The MCP resolves the target repo/branch from its own config (`CH_TARGET_REPO`, `CH_TARGET_BRANCH`)
— you do not pass or manage credentials, hosts, branches, or clone paths.

## 1 — (Optional) sanity-check the repo and name collisions

Before writing, you may call `list_schemas()` to confirm the intended
`Atlys/schemas/{schema_name}.sql` name isn't already taken (and `repo_status()` to see the branch
+ HEAD). If the name collides with an existing, different spec, pick a non-colliding name.

## 2 — Commit the schema (+ metrics manifest) and push directly to the target branch

> **EXACT tool signature — do not guess or probe other parameter names.**
> `write_and_push(relative_path: str, content: str, message: str)` — these THREE names,
> spelled exactly: **`relative_path`**, **`content`**, **`message`**. Not `path`, not `sql`,
> not `schema`, not `files`, not `dir`/`filename`, not `commit_message`, not base64. `content`
> is the **inline file text you already hold in this conversation** — the tool does NOT read
> from `/app/context_docs` or any filesystem path; you pass the whole text as the `content`
> string. If a call is rejected, the fix is the message text, never a different parameter name.
> If you cannot make a valid call, STOP and surface the error — never fire blind schema guesses
> at a write/push tool (an accidentally-accepted wrong shape could commit garbage to `master`).

Canonical call (schema):

```
write_and_push(
  relative_path = "Atlys/schemas/{schema_name}.sql",
  content       = "<the full validated .sql text, verbatim>",
  message       = "feat(schema): generate ClickHouse DDL from {schema_name} ndjson"
)
```

Call `write_and_push` for the schema:

- `relative_path`: `Atlys/schemas/{schema_name}.sql`
- `content`: the **full, validated** `.sql` text (the exact DDL that passed the validation gate and
  the Cloud test — do not re-edit it here). This is **inline text**, not a filesystem path.
- `message`: `feat(schema): generate ClickHouse DDL from {schema_name} ndjson`

If `atlys-materialized-views` produced a metrics manifest for this spec, call `write_and_push`
**again** to commit it (a second, separate push to the same branch — you already hold its JSON
content from that step, no filesystem read needed):

- `relative_path`: `Atlys/schemas/{schema_name}.metrics.json`
- `content`: the metrics manifest JSON
- `message`: `feat(schema): metrics manifest for {schema_name}`

Each call writes the file, commits it on `$CH_TARGET_BRANCH`, and pushes **directly** to that
branch (rebasing once if the remote advanced; never force-pushing). It returns:

```json
{ "committed": true, "pushed": true, "path": "...", "branch": "master",
  "commit": "<sha>", "commit_url": "https://<host>/<owner>/<repo>/commit/<sha>", ... }
```

Report the `commit_url` (of each push, if two) to the user. If a result is `{"committed": false,
"reason": "no changes ..."}`, the identical file was already pushed — that's fine; report the
existing commit URL.

If a tool call errors (e.g. auth/PAT problem, push rejected after rebase), surface the exact
error to the user — do **not** invent a fallback or claim success.

## 2.5 — (Optional, confirm first) Wire Vector ingestion for the new table

**After** the schema push succeeded and **before** the context handoff (§3), you may enable parquet
ingestion for the newly-created table by updating `Atlys/vector-pipeline/vector.toml`. This is
**optional** and **must be confirmed** — invoke skill **`atlys-vector-ingestion`**, which:

1. **Asks the user first** — *"wire up ingestion for `{base_table}` now? yes/no"*. On **no** (or no
   answer), it changes nothing and you proceed directly to §3.
2. On **yes**, it is **idempotent**: if `{base_table}` is already wired in `vector.toml` it makes no
   change; otherwise it adds the `source + transform + sink` triple and pushes the updated
   `vector.toml` via `write_and_push` (`relative_path = "Atlys/vector-pipeline/vector.toml"`).
3. Hands the user the exact **restart command** (`cd Atlys/vector-pipeline && docker compose up -d
   --force-recreate vector`) — this runtime has no shell, so the actual ingest is a user action.

**Never let this optional step block or fail the pipeline.** Whether it wired ingestion, skipped
(user said no), or errored, **always continue to §3 (Context handoff)**.

## 3 — Delegate the context refresh to the Context Agent (LibreChat Subagents)

A new/updated table in `Atlys/schemas/` is a **schema-change trigger** for the **Context Agent**.
This is a **Subagent** call, NOT a handoff: you **keep control** of the conversation. The Context
Agent runs in an **isolated context window**, refreshes `knowledge/`, pushes its own update, and
returns a **compact result** to you — you then write the final combined report. (Subagents is used
here instead of Handoffs because the LiteLLM/Azure model route rejects a transcript that ends with
an assistant message — "does not support assistant message prefill"; a subagent starts a fresh
isolated context and avoids that 400.)

**Gate:** call **only if `write_and_push` returned commit URLs** (push succeeded). Never call
after a failed push.

**How:** LibreChat's **Subagents** feature (enabled on this agent, with the Context Agent added to
its subagents) exposes a subagent tool. Call it, passing the schema-change trigger + **file
pointers** (the Context Agent reads the pushed files itself — keep the payload small, single
source of truth):

```
trigger              : schema-change
schema_path          : Atlys/schemas/{schema_name}.sql
metrics_manifest_path: Atlys/schemas/{schema_name}.metrics.json
database             : atlys
tables               : [{base_table}, {agg_table} (MV: {mv_name})]
deviations           : [D1 skip-index-typed paths, D2 agg TTL on agg_insert_time]
```

The metrics manifest holds the confirmed PM-question metrics (formula, dimensions, serving MV,
`confirmed_by_user` provenance) the Context Agent uses to register/update `metric` concepts; it
then bumps the context version and pushes to `$CH_TARGET_BRANCH`. Include its returned summary
("context vX refreshed, N concepts") in your final report.

If the subagent tool is **not available** in this session (Context Agent not yet added as a
subagent on this agent), do **not** fabricate a call. Tell the user exactly how to continue:
`say "a new table landed — update context for {schema_name}"` to the Context Agent.

## 4 — Then delegate the analysis to the Analytics Agent (LibreChat Subagents)

**Only after the Context subagent returned its refreshed `context vX`**, make a **second** Subagent
call — this time targeting the **Analytics Agent** (added as a second subagent on this agent). This
closes the required pipeline **spec → schema → context → insight** in one continuous, traceable run
(the unseen-spec deliverable: generated schema **plus** insight summary **plus** the trace). Again a
Subagent, not a handoff — you **keep control** and wait for the compact result.

**Order matters:** Context first, Analytics second — so Analytics reasons from the freshly-bumped
context, never a stale snapshot (the "context freshness" grading criterion). The Analytics Agent
reads the now-current bundle, analyzes the new table, writes `Atlys/schemas/{spec_name}.insights.json`,
and returns a summary.

**Gate:** call **only if both the push AND the context refresh succeeded.** Skip on any prior failure.

Pass file pointers (Analytics reads the pushed files itself):

```
mode                 : pipeline
spec_name            : {spec_name}
schema_path          : Atlys/schemas/{schema_name}.sql
metrics_manifest_path: Atlys/schemas/{schema_name}.metrics.json
database             : atlys
tables               : [{base_table}, {agg_table} (MV: {mv_name})]
context_version      : {vX returned by the Context subagent}
```

Include the Analytics summary ("N insights, top confidence X, insights.json committed") in your
final combined report. If the Analytics subagent is **not available**, do **not** fabricate a call —
tell the user to run the Analytics Agent in pipeline mode on `{spec_name}`.

Never end the run at the push without either delegating (Context, then Analytics) or clearly
instructing the user which remaining step(s) to trigger. The run is complete only when schema,
context, AND insights are done.

## Rules

- **Always** commit + push via `clickhouse_git_write` → `write_and_push`. Never assume a shell,
  `git`, or `gh` is available.
- **Always** push the **exact** validated `.sql` content — this step must not introduce SQL the
  validation gate + Cloud test never saw.
- **Never** create a feature branch or a PR — the change lands on `$CH_TARGET_BRANCH` directly.
- **Never** fabricate a commit URL; only report what `write_and_push` returns.
