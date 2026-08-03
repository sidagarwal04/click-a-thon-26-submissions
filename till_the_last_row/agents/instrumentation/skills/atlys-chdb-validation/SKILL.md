---
name: atlys-chdb-validation
description: The hard validation gate for an Atlys ClickHouse DDL, run on the live ClickHouse Cloud service via the clickhouse_write_tools MCP (run_query) — no shell/chdb needed. Static-lint the .sql for escaped double-quoted literals, then create the DDL against a THROWAWAY validation table (spec_table + a __val suffix), INSERT one wrapped representative row per event type, assert the typed ORDER BY paths + ch_insert_time are readable and any MV backing tables received rows, then DROP the throwaway objects. Invoke after the DDL is drafted and before the production Cloud create (atlys-cloud-test) or git step. Full algorithm + error table in references/chdb-validation.md.
---

# Skill: DDL Validation Gate (on Cloud, via MCP)

**Hard gate.** You may NOT run the production create (`atlys-cloud-test`), commit, or push until
this passes. **This runs entirely over the `clickhouse_write_tools` MCP (`run_query`) — there is
NO shell, NO python, NO chdb in this runtime.** Do not stop and hand the user a script; validate
here using the write MCP against a **throwaway validation table**, then clean it up.

> Why a throwaway table? It lets you exercise the *exact* DDL on real ClickHouse (the same engine
> Cloud runs) without touching the production `{spec_table}`. The validation table name is the
> production name plus a `__val` suffix; every object created here is dropped at the end.

## Tools

| Purpose | MCP tool |
|---|---|
| Run every statement (CREATE / INSERT / SELECT / DROP) | **`clickhouse_write_tools`** → **`run_query`** (one raw SQL statement per call) |

The MCP owns the Cloud connection (host / HTTPS / cert). You pass one SQL statement per call and
read the returned rows out of the tool result. No CLI, no TLS flags.

## 1 — Static lint FIRST (catches the #1 generation bug)

Before any tool call, scan the drafted `Atlys/schemas/{schema_name}.sql` **in your own reasoning**
for escaped double-quoted literals — the top DDL-generation bug:

- `'"UTC"'`, `'"express_checkout_shown"'`, `DateTime64(3, '"UTC"')` → **wrong**.
- They must be single-quoted: `'UTC'`, `'express_checkout_shown'`, `DateTime64(3, 'UTC')`.

If you find any, fix the `.sql` before continuing. Only proceed once the DDL is free of escaped
double-quoted literals.

## 2 — Build the throwaway validation DDL

Take the exact statements from the drafted `.sql` and produce a **validation copy** in which every
object name gets a `__val` suffix so nothing collides with production:

- base table `atlys.{spec_table}` → `atlys.{spec_table}__val`
- each MV backing table `atlys.{mv_backing}` → `atlys.{mv_backing}__val`
- each `CREATE MATERIALIZED VIEW atlys.{mv_name}` → `atlys.{mv_name}__val`, and rewrite its
  `TO atlys.{mv_backing}` target and its `FROM atlys.{spec_table}` source to the `__val` names.

Do **not** otherwise edit the DDL (same JSON typed hints, `ch_insert_time`, ORDER BY, PARTITION,
TTL, engines) — the point is to validate what will actually ship. Keep `CREATE DATABASE IF NOT
EXISTS atlys` unsuffixed (the DB is shared).

## 3 — Create on Cloud (one `run_query` call per statement, in order)

Send each statement as its own `clickhouse_write_tools` → `run_query` call, in dependency order:

1. `CREATE DATABASE IF NOT EXISTS atlys`
2. `CREATE TABLE IF NOT EXISTS atlys.{spec_table}__val ( ... )`  ← the base table
3. each MV backing table `CREATE TABLE IF NOT EXISTS atlys.{mv_backing}__val ( ... )` (if any)
4. each `CREATE MATERIALIZED VIEW IF NOT EXISTS atlys.{mv_name}__val TO atlys.{mv_backing}__val AS SELECT ... FROM atlys.{spec_table}__val ...` (if any)

Stop and enter the auto-fix loop (§6) on the first call that returns `isError: true`.

## 4 — Insert one wrapped representative row per event type

From the input NDJSON, take **one representative raw row per event type** (the row with the most
non-null paths for that type). Wrap each so it lands in the `payload` JSON column — the raw NDJSON
row IS the event object, so it nests under `payload`:

```sql
INSERT INTO atlys.{spec_table}__val (payload) FORMAT JSONEachRow
{"payload": <one raw NDJSON row object>}
```

Send each as one `run_query` call (pass the whole `INSERT ... FORMAT JSONEachRow\n{...}` string
verbatim). Ensure the event's timestamp path is a value parseable as `DateTime64(3)`
(e.g. `"2026-07-27T11:34:45.123Z"`); normalise only if a call rejects it.

## 5 — Assert (read the results out of each `run_query`)

Run these as `run_query` calls and check the returned rows:

```sql
-- row count >= number of event types inserted
SELECT count() AS n FROM atlys.{spec_table}__val;

-- every typed ORDER BY path is readable & non-NULL, and ch_insert_time auto-populated
SELECT payload.event, payload.{feature_dim_1}, payload.user_id,
       payload.{timestamp_path} AS ts, ch_insert_time
FROM atlys.{spec_table}__val LIMIT 1;

-- if MVs were created, each backing table received aggregated rows
SELECT count() AS n FROM atlys.{mv_backing}__val;   -- expected >= 1 per MV

-- any boolean-typed path reads back as a real bool, not a string
SELECT payload.{bool_path} FROM atlys.{spec_table}__val LIMIT 1;   -- if any boolean paths exist

-- any skip-indexed path is actually filterable
SELECT count() FROM atlys.{spec_table}__val
WHERE payload.{indexed_path} = <sample value>;   -- if any INDEX clauses exist, must run without error
```

Pass criteria:
- CREATE succeeded, including any `INDEX` clauses and `Bool`/`UInt8` typed paths,
- `count()` ≥ number of event types inserted,
- no ORDER BY path column comes back NULL (keys cannot be Nullable),
- `ch_insert_time` is non-NULL (proves `MATERIALIZED now64(3)` fired),
- each MV backing table `n` ≥ 1 (if MVs exist),
- any boolean-typed path reads back as a real bool (not a string),
- any skip-indexed path is filterable (the `WHERE` query above runs without error).

Record these results as text — the git step embeds them as the validation evidence.

## 6 — Auto-fix loop (max 5 iterations)

```
Create + insert + assert (all via run_query on the __val table)
  ├─ ✅ pass → clean up (§7) → proceed to atlys-cloud-test (production create)
  └─ ❌ FAIL → read the run_query error → identify root cause (see reference error table) →
        fix the DDL in Atlys/schemas/{schema_name}.sql (re-derive from the NDJSON, do not guess) →
        DROP the partial __val objects (§7) → re-run from §3.
        Surface to the user if still failing after 5.
```

Common root causes: escaped double-quote literal, a Nullable typed path in the key, a bad
timestamp value, an unwrapped INSERT row, an ORDER BY path missing from the typed hint, an
`INDEX` referencing a path not typed in the `payload(...)` hint, or a boolean path whose samples
aren't actually boolean.

## 7 — Clean up the throwaway objects (always)

Drop everything you created here, MVs first, then backing tables, then the base table:

```sql
DROP TABLE IF EXISTS atlys.{mv_name}__val;      -- each MV
DROP TABLE IF EXISTS atlys.{mv_backing}__val;   -- each MV backing table
DROP TABLE IF EXISTS atlys.{spec_table}__val;   -- base table
```

Run each as a `run_query` call. The `__val` objects must not survive this step (whether it passed
or failed) — the production create is done by `atlys-cloud-test`, not here.

## Rules

- **Never** claim you cannot validate because there is no shell/chdb — validation runs on the
  `clickhouse_write_tools` MCP here. Only stop if the MCP itself is unavailable.
- **Always** validate against the `__val` throwaway table, never the production `{spec_table}`.
- **Always** send one statement per `run_query` call, in dependency order.
- **Always** use the exact DDL text from the drafted `.sql` (only the `__val` renames differ).
- **Always** clean up (§7) before proceeding — pass or fail.

> Full algorithm (per-event-type sampling, wrapped-insert prep, throwaway renaming) and the
> complete error → fix decision table: [references/chdb-validation.md](references/chdb-validation.md).
