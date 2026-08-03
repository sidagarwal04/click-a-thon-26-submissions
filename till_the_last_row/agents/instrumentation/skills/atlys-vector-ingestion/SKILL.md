---
name: atlys-vector-ingestion
description: OPTIONAL, confirm-gated step that runs AFTER the schema (+ metrics manifest) has been committed and pushed, but BEFORE the Context Agent handoff. It updates the Vector pipeline config (Atlys/vector-pipeline/vector.toml) so the newly-created ClickHouse table starts ingesting its parquet file. Idempotent — if the table is already wired in vector.toml, it changes nothing. Always ask the user "wire up ingestion for {table}?" first; on NO, skip straight to the context handoff. Pushes the edited vector.toml via the clickhouse_git_write MCP (write_and_push), then tells the user the exact command to (re)start the pipeline — it does NOT run shell/docker itself.
---

# Skill: Enable Vector Ingestion for a New Table (optional, confirm-gated)

After a new table is created + pushed (`atlys-git-pr` §2), its parquet data is **not ingested**
until the **Vector pipeline** (`Atlys/vector-pipeline/vector.toml`) knows about it. This skill
adds the wiring for the new base table. It is **optional** and runs **only with user confirmation**;
on a NO, the flow proceeds straight to the Context Agent handoff with **no** config change.

> **No shell / git / docker in this runtime.** The config file is edited in memory and pushed via
> the **`clickhouse_git_write` MCP** (`write_and_push`) — the same MCP that pushed the schema. This
> skill does **not** run `vector`, `docker`, or `docker compose`; after pushing it **tells the user
> the exact restart command** so ingestion actually starts.

## When to run (position in the pipeline)

```
schema (+ metrics) pushed  ──►  [ THIS SKILL — optional, confirmed ]  ──►  Context handoff  ──►  Analytics handoff
        (atlys-git-pr §2)          (atlys-vector-ingestion)               (atlys-git-pr §3)      (atlys-git-pr §4)
```

Run **only after** `write_and_push` returned commit URLs for the schema (push succeeded). Never run
before the schema is on the branch.

## 0 — Ask first (the confirmation gate)

Before touching anything, ask **one** concise question and wait for an answer:

> "The `{base_table}` table is created and pushed. Do you want me to **wire up parquet ingestion**
> for it now (update `Atlys/vector-pipeline/vector.toml`) before I refresh the context?
> **yes / no**"

- **NO / no answer / "skip"** → do **nothing** here. State "Skipping ingestion wiring — proceeding
  to the context handoff", then continue with `atlys-git-pr` §3 (Context). This must never block the
  pipeline.
- **YES** → continue with the steps below.

Derive `{base_table}` from the schema you just pushed (the `CREATE TABLE atlys.{base_table}` name).
The parquet file is conventionally `{base_table}.parquet` and the event name is `{base_table}`
(one base table per event type — see `atlys-schema-design`). If the spec's parquet/event name
differs from the table name, ask the user to confirm the parquet filename.

## 1 — Read the current config and check if it is already wired (idempotent)

Read `Atlys/vector-pipeline/vector.toml` (it is in the repo the git MCP already clones — you can get
its current text via `list_schemas`-style familiarity, or the user pastes it; if you do not already
hold it, ask the user for the current `vector.toml`). **Check whether `{base_table}` is already
present** (i.e. a `src_{base_table}` source already exists).

- **Already present** → report "ingestion already wired for `{base_table}` — no config change
  needed" and go to Step 4 (restart instruction only). Do **not** push a no-op.
- **Not present** → go to Step 2.

## 2 — Add the source + transform + sink triple

`vector.toml` wires each table with **three** blocks. Add all three for the new table, matching the
existing style exactly (same interval, same remap, same sink options). Replace `{base_table}`
throughout, and `{PARQUET_FILE}` with the parquet path (default `/app/data/{base_table}.parquet`).

**Source** (exec → parquet reader):

```toml
[sources.src_{base_table}]
type = "exec"
mode = "scheduled"
scheduled.exec_interval_secs = 86400
command = ["python3", "/app/parquet_reader.py"]
environment = { PARQUET_FILE = "/app/data/{base_table}.parquet", EVENT_NAME = "{base_table}" }
```

**Transform** (parse NDJSON line, lift `.payload`):

```toml
[transforms.remap_{base_table}]
type = "remap"
inputs = ["src_{base_table}"]
drop_on_error = true
source = '''
  parsed, err = parse_json(.message)
  if err != null {
    abort
  }
  .payload = parsed.payload
  del(.message)
  del(.source_type)
  del(.timestamp)
  del(.host)
'''
```

**Sink** (HTTP → ClickHouse Cloud `INSERT ... FORMAT JSONEachRow`):

```toml
[sinks.sink_{base_table}]
type = "http"
inputs = ["remap_{base_table}"]
uri = "https://<CH_HOST>:8443/?database=atlys&user=<CH_USER>&password=<CH_PASSWORD>&query=INSERT%20INTO%20{base_table}%20FORMAT%20JSONEachRow"
method = "post"
[sinks.sink_{base_table}.encoding]
codec = "json"
[sinks.sink_{base_table}.framing]
method = "newline_delimited"
[sinks.sink_{base_table}.request]
retry_attempts = 2
```

Rules:
- **Reuse the exact host/credentials + TLS/framing/encoding shape already in the file** — copy an
  existing `sink_*` block and swap only the table name in the `query=INSERT INTO ... ` part and the
  `[sinks.sink_*]`/`inputs`/keys. Do not invent a new host or change the DB.
- Insert the three blocks into their **respective sections** (sources with sources, transforms with
  transforms, sinks with sinks) so the file stays readable — but Vector does not require ordering.
- The row shape the sink sends is `{"payload": {...}}`, matching the base table's single `payload`
  JSON column. Do **not** flatten it.
- Leave the observability section (`internal_logs` → OTel) untouched.

## 3 — Push the updated vector.toml via the git MCP

Commit the **full edited file** with `clickhouse_git_write` → `write_and_push`, exactly as for the
schema (three params, verbatim: `relative_path`, `content`, `message`; `content` is the whole file
text inline, not a filesystem path):

```
write_and_push(
  relative_path = "Atlys/vector-pipeline/vector.toml",
  content       = "<the full edited vector.toml text, verbatim>",
  message       = "chore(ingest): wire vector.toml to ingest {base_table} parquet"
)
```

Report the returned `commit_url`. If the result is `{"committed": false, "reason": "no changes ..."}`
the config already matched (idempotent) — that is fine, report it. If the call **errors**, surface the
exact error and STOP this optional step; do **not** block the pipeline — tell the user ingestion
wiring failed and continue to the context handoff.

## 4 — Tell the user how to (re)start ingestion

You cannot run shell/docker here, so the actual ingest is a **user action**. After the push, give the
exact command:

```
cd Atlys/vector-pipeline && docker compose up -d --force-recreate vector
# (the scheduled exec source runs once on start, then every 24h)
```

Then briefly note how to verify: `SELECT count() FROM atlys.{base_table}` on Cloud should become
non-zero after Vector's first run.

## 5 — Continue the pipeline

Whether ingestion was wired (YES) or skipped (NO/error), **proceed to the Context Agent handoff**
(`atlys-git-pr` §3) and then Analytics (§4). This step never terminates the run and never gates the
context refresh — it only precedes it.

## Rules

- **Always ask first.** No confirmation → no config change. This is an optional convenience step.
- **Idempotent.** If `src_{base_table}` already exists in `vector.toml`, change nothing (Step 1).
- **Never** invent a new ClickHouse host/credentials — copy the pattern from an existing sink.
- **Never** run `vector`/`docker`/`git` yourself; push via the MCP and hand the restart command to
  the user.
- **Never** block or fail the pipeline because of this step — on any problem, report it and continue
  to the context handoff.
- Push the **whole** `vector.toml`, not a fragment — `write_and_push` overwrites the file.
