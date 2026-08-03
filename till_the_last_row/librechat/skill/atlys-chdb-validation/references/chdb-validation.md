# DDL Validation Reference — on Cloud via MCP (single base table, `payload` JSON column)

Validate every DDL on the **live ClickHouse Cloud service** through the `clickhouse_write_tools`
MCP (`run_query`) before doing the production create. This catches syntax errors, unsupported JSON
hints, Nullable-in-key problems, escaped-double-quote literals, and bad timestamp values against
the *exact* engine that will run in production.

> ⚠️ **There is no shell / python / chdb in this runtime.** Do not generate a `.py` validator and
> ask the user to run it. Every statement here is a `clickhouse_write_tools` → `run_query` MCP
> call. Validation runs against a **throwaway table** whose name is the production name plus a
> `__val` suffix, which is dropped at the end.

> ⚠️ **No static template for the DDL.** The agent builds the validation DDL by taking the exact
> drafted `.sql`, renaming objects with a `__val` suffix, and inserting one representative raw row
> **per event type** into the single base table (wrapped under `payload`). There is one table per
> spec, not one per event type.

---

## Tool

| Purpose | MCP tool |
|---|---|
| Every CREATE / INSERT / SELECT / DROP | `clickhouse_write_tools` → `run_query` — one raw SQL statement per call |

`run_query` returns a JSON result (`columns` + `rows`) for SELECTs and an execution-stats row for
DDL/INSERT, with `isError: true` on failure. Read the rows out of the tool result to assert.

---

## Static lint FIRST (in reasoning, before any tool call)

Scan the drafted `Atlys/schemas/{schema_name}.sql` for escaped double-quoted literals:

- `'"UTC"'`, `'"express_checkout_shown"'`, `DateTime64(3, '"UTC"')` → **wrong**.

Fix every one to single quotes (`'UTC'`, `'express_checkout_shown'`, `DateTime64(3, 'UTC')`)
before creating anything.

---

## The `__val` throwaway rename

Take the DDL exactly as written to the `.sql`, and suffix every **object** name with `__val` so it
cannot collide with production, leaving the shared database name alone:

| Production object | Validation object |
|---|---|
| `CREATE DATABASE IF NOT EXISTS atlys` | unchanged (shared DB) |
| `atlys.{spec_table}` (base table) | `atlys.{spec_table}__val` |
| `atlys.{mv_backing}` (MV target table) | `atlys.{mv_backing}__val` |
| `atlys.{mv_name}` (materialized view) | `atlys.{mv_name}__val` |
| MV's `TO atlys.{mv_backing}` | `TO atlys.{mv_backing}__val` |
| MV's `FROM atlys.{spec_table}` | `FROM atlys.{spec_table}__val` |

Nothing else changes: same `JSON(...)` typed hints, same `ch_insert_time ... MATERIALIZED
now64(3) CODEC(Delta, ZSTD(1))`, same ORDER BY, PARTITION, TTL, engines. The point is to validate
what will actually ship.

### What to keep vs omit

The `__val` DDL is the **same DDL** that goes to production — Cloud runs the real engine, so keep
everything (JSON typed column, `ch_insert_time`, `MergeTree`/`AggregatingMergeTree`, PARTITION,
ORDER BY, MVs, TTL, CODECs). The Instrumentation design already never emits
`ReplicatedMergeTree` / `Distributed` / `storage_policy`, so there is nothing to strip.

---

## How the agent builds the validation, step by step

### Phase 1 — One representative row per event type (from the NDJSON)

Read the NDJSON via the `filesystem` MCP (`/app/specs/{spec_name}/events.ndjson` — the
read-only mount, never a shell path). Group rows by the discriminator path (`event` / `type` /
`eventType`; if none, treat all rows as one group), and for each group keep the row with the most
non-null paths. Those rows — one per event type — all insert into the single `__val` base table.

### Phase 2 — Confirm the typed ORDER BY paths are clean (from the data)

For the ORDER BY paths chosen in the design, verify from the sample rows:

- the discriminator path (`payload.event`) is present and non-null on every row,
- `user_id` / `application_id` are present and non-null on every event,
- every ORDER BY path is present and non-null in each sample row (keys cannot be Nullable),
- the timestamp path holds a value parseable as `DateTime64(3)`
  (e.g. `"2026-07-27T11:34:45.123Z"` or `"2026-07-27 11:34:45.123"`).

Only the typed paths matter; the rest of the payload is absorbed by the `JSON` column. Paths
present for only some event types are fine.

### Phase 3 — Prepare each INSERT (WRAP under `payload`)

The whole event object goes into the `payload` JSON column, **wrapped so the column name matches**
— the raw NDJSON row IS the event object, so it must be nested:

```
raw NDJSON row  →  { "payload": <that same row object> }
```

The INSERT statement passed to `run_query` is the whole string:

```sql
INSERT INTO atlys.{spec_table}__val (payload) FORMAT JSONEachRow
{"payload": <one raw NDJSON row object>}
```

Minimal transforms only when a `run_query` call rejects a value — e.g. normalise the timestamp
(`T`→space, drop `Z`) if the typed `DateTime64` path won't parse. Leave everything else untouched.

---

## The MCP call sequence (copy this order)

All calls are `clickhouse_write_tools` → `run_query`, one statement each:

1. `CREATE DATABASE IF NOT EXISTS atlys`
2. `CREATE TABLE IF NOT EXISTS atlys.{spec_table}__val ( ... )`
3. each MV backing table: `CREATE TABLE IF NOT EXISTS atlys.{mv_backing}__val ( ... )`
4. each MV: `CREATE MATERIALIZED VIEW IF NOT EXISTS atlys.{mv_name}__val TO atlys.{mv_backing}__val AS SELECT ... FROM atlys.{spec_table}__val ...`
5. one `INSERT ... FORMAT JSONEachRow {"payload": ...}` per event-type sample row
6. `SELECT count() AS n FROM atlys.{spec_table}__val`
7. `SELECT payload.event, payload.{feature_dim_1}, payload.user_id, payload.{timestamp_path} AS ts, ch_insert_time FROM atlys.{spec_table}__val LIMIT 1`
8. for each MV: `SELECT count() AS n FROM atlys.{mv_backing}__val`
9. for each `Bool`/`UInt8` typed path (if any): `SELECT payload.{bool_path} FROM atlys.{spec_table}__val LIMIT 1`
10. for each `INDEX`-covered path (if any): `SELECT count() FROM atlys.{spec_table}__val WHERE payload.{indexed_path} = <sample value>`
11. cleanup (always): `DROP TABLE IF EXISTS` each MV, then each MV backing table, then the base
    table — all `__val`.

---

## Pass criteria

From the returned rows:

```
✅ CREATE DATABASE + base table + MVs        (steps 1–4 all isError:false)
✅ INSERT {N} wrapped rows (one per event type)   (step 5, all isError:false)
✅ SELECT count() = {N}                        (step 6: n >= N)
✅ ORDER BY paths + ch_insert_time non-NULL    (step 7: no NULL in any key col; ch_insert_time set)
✅ MV backing {mv_backing}: {n} row(s)         (step 8: n >= 1 per MV, if any)
✅ boolean path {bool_path} reads as a real bool   (step 9, if any Bool/UInt8 typed paths)
✅ indexed path {indexed_path} is filterable   (step 10: query runs without error, if any INDEX clauses)
```

Final decision:

```
✅ BASE TABLE + MVs PASSED  → clean up (§11) → proceed to atlys-cloud-test
```

---

## Auto-fix loop

```
Create + insert + assert (via run_query on __val)
  │
  ├─ ✅ PASSED → DROP __val objects → proceed to atlys-cloud-test (production create)
  │
  └─ ❌ FAIL (a run_query returned isError:true, or an assert failed)
        ├─ Read the error text from the tool result
        ├─ Identify root cause (table below)
        ├─ Fix: update the DDL in Atlys/schemas/{schema_name}.sql (and the sample row if the
        │        chosen ORDER BY path was wrong) — re-derive from the NDJSON, do not guess
        ├─ DROP any partial __val objects
        └─ Re-run the sequence  (max 5 iterations; surface to user if still failing)
```

### Error → fix decision table

| `run_query` error | Root cause | Fix |
|---|---|---|
| `Unknown data type family JSON` / `Unexpected JSON` | JSON type unsupported on this tier/setting | Confirm the service supports the `JSON` type; keep the typed hint list minimal |
| `Syntax error ... '"'` | Escaped double-quoted literal (`'"UTC"'`) | Change to single quotes: `'UTC'`, `'express_checkout_shown'` |
| `Cannot create Nullable column … used in key expression` | A typed ORDER BY path is Nullable | Pick a path always present; type it non-nullable |
| `Cannot parse … as DateTime64` | Event timestamp value not parseable | Normalise the timestamp in the sample (`T`→space, drop `Z`); confirm `{timestamp_path}` |
| `There is no subcolumn <path> in type JSON` | ORDER BY references a path not typed in the hint | Add that path to the `JSON(...)` typed hint list |
| `JSON object should start with '{'` / `Missing columns: 'payload'` | INSERT row not wrapped under `payload` | Wrap the raw row: `{"payload": <row>}` |
| `ch_insert_time is NULL` (step 7) | Column not `MATERIALIZED now64(3)` | Restore exact `MATERIALIZED now64(3) CODEC(Delta, ZSTD(1))` |
| `Unknown function toYYYYMMDD` | Typo in partition expr | Use `toYYYYMMDD(ch_insert_time)` exactly |
| `Table already exists` (`...__val`) | Leftover from a prior failed run | `DROP TABLE IF EXISTS atlys.<obj>__val` first, then re-create |
| `MCP error -32001: Request timed out` | Cloud service was idle and is waking | Wait a few seconds and retry the same `run_query`; treat as transient, not a DDL bug |
| MV backing count = 0 (step 8) | MV `SELECT`/filter never matched the sample rows | Check the MV's `WHERE payload.event = ...` filter matches an inserted event type |
| Boolean path reads back as a string, not a bool (step 9) | Sample values for that path aren't actually boolean, or the path isn't typed `Bool`/`UInt8` in the `JSON(...)` hint | Fix the typed hint, or drop the boolean typing if the field isn't truly boolean |
| `There is no subcolumn <path> in type JSON` on the indexed-path query (step 10) | An `INDEX` clause references a path not present in the `JSON(...)` typed hint | Add the path to the typed hint list, or drop the `INDEX` if the path isn't worth typing |

---

## Cleanup (§11) — always, pass or fail

MVs first (they depend on the base table), then MV backing tables, then the base table:

```sql
DROP TABLE IF EXISTS atlys.{mv_name}__val;      -- each MV
DROP TABLE IF EXISTS atlys.{mv_backing}__val;   -- each MV backing table
DROP TABLE IF EXISTS atlys.{spec_table}__val;   -- base table
```

No `__val` object may survive validation. The production create (real `{spec_table}`) is performed
by `atlys-cloud-test`, never here.
