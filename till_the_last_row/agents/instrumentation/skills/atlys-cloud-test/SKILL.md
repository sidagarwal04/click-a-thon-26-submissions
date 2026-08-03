---
name: atlys-cloud-test
description: Create the PRODUCTION Atlys schema on the live ClickHouse Cloud instance via the clickhouse_write_tools MCP (HTTP, no CLI) after the MCP validation gate passes — run each DDL statement (CREATE DATABASE / CREATE TABLE / CREATE MATERIALIZED VIEW) as a run_query call, insert one real wrapped row, confirm the typed ORDER BY paths + ch_insert_time via the read MCP, then clean up the test row. Invoke after atlys-chdb-validation passes and before the git step. End-to-end walkthrough in references/test-walkthrough.md.
---

# Skill: ClickHouse Cloud Create + Test (via MCP)

After the MCP validation gate (`atlys-chdb-validation`) passes, create the **production** schema on
the real ClickHouse Cloud instance and smoke-test it.
**This runs entirely over MCP HTTP tools — no `clickhouse` CLI is required.** This is also the
step that actually creates the table/MVs on Cloud.

## Tools

| Purpose | MCP tool |
|---|---|
| Run DDL + INSERT (writes) | **`clickhouse_write_tools`** — write-capable ClickHouse MCP. Exposes exactly three tools: `list_databases`, `list_tables`, and **`run_query`**. Call **`run_query`** with your raw SQL string (one statement) for every `CREATE` / `INSERT` / `TRUNCATE` / `DROP`. |
| Read back / introspect | **`clickhouse-cloud`** — the read-only ClickHouse MCP (`SELECT`, `list_tables`) |

> No CLI, no TLS flags to manage — the MCP server holds the Cloud connection and handles the
> HTTPS/8443 + cert settings itself. Credentials live in the MCP server config
> (`librechat.yaml` / `.env`: `CH_HOST`, `CH_USER`, `CH_PASSWORD`), not in this skill.
> `run_query` executes any single raw SQL statement (DDL, `INSERT`, `SELECT`, `DROP`) — there is
> no separate insert/DDL tool; you just pass the statement text.

## 1 — Create the schema on Cloud (one statement per tool call)

MCP query tools execute **one statement at a time** — you cannot pipe a whole `.sql` file with
`--multiquery`. So split `Atlys/schemas/{schema_name}.sql` on `;` into ordered statements and
send each as a separate `clickhouse_write_tools` → `run_query` call, **in order**:

1. `CREATE DATABASE IF NOT EXISTS atlys`
2. `CREATE TABLE IF NOT EXISTS atlys.{spec_table} ( ... )`  ← the base table
3. each MV backing table `CREATE TABLE IF NOT EXISTS atlys.{mv_backing} ( ... )` (if any)
4. each `CREATE MATERIALIZED VIEW IF NOT EXISTS atlys.{mv_name} TO ... AS SELECT ...` (if any)

Order matters: database → base table → MV backing table(s) → MV(s) (an MV references its base
table and its `TO` target, so both must exist first). The statements are the **exact** text from
the validated `.sql` — do not re-edit them here. Stop and enter the auto-fix loop (§4) on the
first tool call that errors.

## 2 — Insert one real wrapped row (write tool)

The raw NDJSON row IS the event object, so wrap it under `payload` so it lands in the JSON column:

```sql
INSERT INTO atlys.{spec_table} (payload) FORMAT JSONEachRow
{"payload": <one raw NDJSON row object>}
```

Send this as a single `run_query` call — pass the whole `INSERT ... FORMAT JSONEachRow\n{...}`
as the SQL string. `run_query` runs it verbatim; there is no separate insert tool and no need to
reformat into a `VALUES` tuple.

## 3 — Smoke test (read tools)

Run these as `clickhouse-cloud` (read) tool calls and capture the results into your reasoning so
the PR body can cite them:

```sql
-- table exists with the expected engine + keys?
SELECT name, engine, partition_key, sorting_key
FROM system.tables WHERE database = 'atlys' AND name = '{spec_table}';

-- row landed?
SELECT count() FROM atlys.{spec_table};                       -- expected >= 1

-- typed ORDER BY paths + ch_insert_time accessible + populated?
SELECT payload.event, payload.{timestamp_path} AS ts, ch_insert_time
FROM atlys.{spec_table} LIMIT 1;                               -- ch_insert_time must be non-NULL

-- if MVs were created, confirm their backing tables received aggregated rows
SELECT count() FROM atlys.{mv_backing};                       -- expected >= 1 per MV
```

Then clean up the test row (write tool):

```sql
TRUNCATE TABLE atlys.{spec_table}
```

> Record the smoke-test results (table row from `system.tables`, the count, the readable typed
> paths) as text — the git/PR step embeds them in the PR body in place of the old
> `/tmp/cloud_test_output.txt` capture.

## 4 — Auto-fix loop (max 5 iterations)

```
Create + smoke test (via MCP)
  ├─ ✅ pass → proceed to atlys-git-pr
  └─ ❌ FAIL → read the MCP tool error (JSON unsupported on tier, bad path type, TTL syntax,
        Nullable-in-key, escaped double-quote literal) → fix the DDL in
        Atlys/schemas/{schema_name}.sql → re-run the MCP validation gate (atlys-chdb-validation,
        on the `__val` throwaway table) to confirm still valid → drop the partial production
        objects if needed (`DROP TABLE IF EXISTS atlys.{spec_table}` etc. via
        clickhouse_write_tools) → re-create on Cloud. Surface to user if still failing after 5.
```

Because `CREATE ... IF NOT EXISTS` is idempotent, a partial run is safe to re-apply; only drop an
object when you need to change its definition (ClickHouse won't alter a table's key/engine in
place).

## Rules

- **Always** use `clickhouse_write_tools` → `run_query` for every `CREATE` / `INSERT` /
  `TRUNCATE` / `DROP`, and the `clickhouse-cloud` read MCP for `SELECT` / `system.tables`. Never
  assume a CLI is available; never manage TLS/port flags — the MCP server owns the connection.
- **Always** send DDL **one statement per tool call**, in dependency order (database → base table
  → MV backing → MV). Do not concatenate statements.
- **Always** use the exact statement text from the MCP-validated `.sql` — this step must not
  introduce new SQL the validation gate never saw.
- **Always** clean up the inserted test row (`TRUNCATE`) after the smoke test.

> Full end-to-end walkthrough with a worked example:
> [references/test-walkthrough.md](references/test-walkthrough.md).
