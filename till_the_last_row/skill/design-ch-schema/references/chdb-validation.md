# chdb Local Validation Reference (single base table, `payload` JSON column)

Validate every DDL locally using **chdb** (embedded ClickHouse in Python) before touching
the Cloud instance. This catches syntax errors, unsupported JSON hints, Nullable-in-key
problems, escaped-double-quote literals, and bad timestamp values instantly, with no external
dependencies.

> ⚠️ **No static template.** The agent generates the validation script dynamically by
> reading the input NDJSON, taking one representative raw row **per event type**, and
> inserting them all into the **single base table** (wrapped under `payload`). There is one
> table per spec, not one per event type.

---

## Install (JSON support required)

```bash
pip3 install --upgrade chdb
python3 -c "import chdb; print('chdb', chdb.__version__)"
```

> The `JSON` type is a modern ClickHouse type. If chdb errors on `JSON(...)` typed hints,
> **upgrade chdb first** — do not treat it as a DDL bug.

---

## Static lint FIRST (before chdb)

```bash
grep -nE "'\"" "Atlys/schemas/{schema_name}.sql" && echo "LINT FAIL: escaped double quotes" || echo "LINT OK"
```

Fix every escaped-double-quote literal (`'"UTC"'`, `'"express_checkout_shown"'`,
`DateTime64(3, '"UTC"')`) to single quotes before running chdb.

---

## What to keep vs omit in the chdb DDL

The DDL used for chdb is **the same DDL** that goes to ClickHouse Cloud — with only the
things chdb (single-node embedded) cannot do removed:

| Clause | chdb | Reason |
|---|---|---|
| `CREATE DATABASE IF NOT EXISTS {db}` | ✅ Keep | Needed so the qualified table name resolves |
| `JSON(...)` typed column named `payload` | ✅ Keep | Core of the design — must validate |
| `ch_insert_time ... MATERIALIZED now64(3)` | ✅ Keep | Must confirm it auto-populates |
| `MergeTree` / `AggregatingMergeTree` (MVs) | ✅ Keep | Same engines as Cloud |
| `PARTITION BY toYYYYMMDD(ch_insert_time)` | ✅ Keep | Validate partition expr |
| `ORDER BY (payload....)` | ✅ Keep | Validate typed-path key |
| `CREATE MATERIALIZED VIEW ... TO ...` | ✅ Keep | Validate MVs fire on insert |
| `TTL ...` | ✅ Keep (or omit) | Optional for correctness; keep to validate syntax |
| `CODEC(Delta, ZSTD(1))` | ✅ Keep | chdb supports it |
| `ReplicatedMergeTree` / `Distributed` / `storage_policy` | ❌ Never emitted anyway | Cloud-managed |

---

## How the agent generates the validation script dynamically

Driven entirely by the input NDJSON and the DDL designed in Step 3. No template file.

### Phase 1 — One representative row per event type

```python
from collections import defaultdict
import json

DISCRIMINATOR = "event"  # or "type"/"eventType"; None => no discriminator
best = {}                # event_type -> the row with the most non-null paths
# {ndjson_path} is $REPO_DIR/Atlys/specs/{spec_name}/events.ndjson — the managed clone,
# never a pre-existing local copy of the repo.
with open("{ndjson_path}") as f:
    for line in f:
        row = json.loads(line)
        et = row.get(DISCRIMINATOR, "__single__")
        if et not in best or sum(v is not None for v in row.values()) > sum(v is not None for v in best[et].values()):
            best[et] = row

# best.values() = one sample row per event type; ALL insert into the single base table.
```

### Phase 2 — Confirm the typed ORDER BY paths exist and are clean

For the ORDER BY paths chosen in Step 2/3, verify **from the data**:

- the discriminator path (`payload.event`) is present and non-null on every row,
- `user_id` and `application_id` are present and non-null (on every event),
- every ORDER BY path is present and non-null in each sample row (keys cannot be Nullable),
- the timestamp path holds a value parseable as `DateTime64(3)`
  (e.g. `"2026-07-27T11:34:45.123Z"` or `"2026-07-27 11:34:45.123"`).

No per-field flattening or typing is done for the rest of the payload — the `payload` column
absorbs it. Paths present only for some event types are fine.

### Phase 3 — Prepare the raw INSERT payload (WRAP under `payload`)

The whole event object goes into the `payload` JSON column via `FORMAT JSONEachRow`, **wrapped
so the column name matches** — the raw NDJSON row IS the event object, so it must be nested:

```python
# raw NDJSON row  →  { "payload": <that same row object> }
insert_obj = {"payload": best_row}
row_json = json.dumps(insert_obj)
```

Minimal transforms only when required for the **typed** paths:
- ensure `payload.{timestamp_path}` parses as DateTime64 (normalise `T`/`Z` if chdb rejects it),
- leave everything else untouched.

### Phase 4 — Emit the validation script

Write `/tmp/validate_{schema_name}.py` with **fully resolved content** — the exact
`CREATE DATABASE`, the single base `CREATE TABLE`, any MV tables/MVs, and each real wrapped
sample row. No `{placeholders}`.

```python
#!/usr/bin/env python3
"""
chdb validation — dynamically generated for: {schema_name}
Database: atlys
Base table: {spec_table}   (one table per spec; all event types insert here)
Source NDJSON: {ndjson_path}
"""
import sys, json, chdb

DB = "atlys"

# Full DDL exactly as written to the .sql file: CREATE DATABASE + base table + MV objects.
DDL_STATEMENTS = [
    'CREATE DATABASE IF NOT EXISTS `atlys`',
    """
CREATE TABLE IF NOT EXISTS `atlys`.{spec_table}
(
    payload JSON(
        event            LowCardinality(String),
        application_id   LowCardinality(String),
        {feature_dim_1}  LowCardinality(String),
        user_id          String,
        {timestamp_path} DateTime64(3, 'UTC')
    ),
    ch_insert_time DateTime64(3, 'UTC') MATERIALIZED now64(3) CODEC(Delta, ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(ch_insert_time)
ORDER BY (payload.event, payload.application_id, payload.{feature_dim_1}, payload.user_id, payload.{timestamp_path})
TTL toDateTime(ch_insert_time) + INTERVAL {ttl_days} DAY DELETE
SETTINGS index_granularity = 16384, ttl_only_drop_parts = 1
""",
    # ... any MV backing tables + CREATE MATERIALIZED VIEW statements ...
]

# One wrapped sample row per event type (all insert into the single base table)
SAMPLES = [
    {"payload": { ...real NDJSON row for event type 1... }},
    {"payload": { ...real NDJSON row for event type 2... }},
    # ...
]

# ORDER BY key paths to assert readable & non-null
ORDERBY_PATHS = ["event", "application_id", "{feature_dim_1}", "user_id", "{timestamp_path}"]

SPEC_TABLE = "{spec_table}"

# ── Runner (fixed — copy verbatim) ───────────────────────────────────────────
errors = []
fq = f"`{DB}`.{SPEC_TABLE}"
try:
    for ddl in DDL_STATEMENTS:
        chdb.query(ddl)
    print(f"  ✅ CREATE DATABASE + base table + MVs")

    for sample in SAMPLES:
        chdb.query(f"INSERT INTO {fq} (payload) FORMAT JSONEachRow {json.dumps(sample)}")
    print(f"  ✅ INSERT {len(SAMPLES)} wrapped rows (one per event type)")

    count = int(chdb.query(f"SELECT count() FROM {fq}", "CSV").bytes().strip())
    assert count >= len(SAMPLES), f"count={count} < {len(SAMPLES)}"
    print(f"  ✅ SELECT count() = {count}")

    sel = ", ".join(f"payload.{p}" for p in ORDERBY_PATHS)
    res = chdb.query(f"SELECT {sel} FROM {fq} LIMIT 1", "JSONEachRow")
    row = json.loads(res.bytes().strip().splitlines()[0])
    for p in ORDERBY_PATHS:
        assert row.get(f"payload.{p}", row.get(p)) is not None, f"ORDER BY path payload.{p} is NULL"
    print(f"  ✅ ORDER BY paths ({sel}) are not NULL")

    cit = chdb.query(f"SELECT ch_insert_time FROM {fq} LIMIT 1", "JSONEachRow").bytes().strip()
    assert cit and b"null" not in cit.lower(), "ch_insert_time is NULL"
    print(f"  ✅ ch_insert_time auto-populated")

    # If MVs exist, confirm their backing tables received rows
    # for mv_agg in MV_AGG_TABLES:
    #     n = int(chdb.query(f"SELECT count() FROM `{DB}`.{mv_agg}", "CSV").bytes().strip())
    #     print(f"  ✅ MV backing {mv_agg}: {n} aggregated group(s)")

except Exception as e:
    print(f"  ❌ FAIL: {e}")
    errors.append(str(e))

print("\n" + "="*60)
if errors:
    print(f"❌ VALIDATION FAILED — {len(errors)} error(s):")
    for err in errors:
        print(f"   {err}")
    sys.exit(1)
else:
    print("✅ BASE TABLE + MVs PASSED")
    sys.exit(0)
```

> The **runner block** is fixed — copy it verbatim. Only `DB`, `SPEC_TABLE`, the DDL
> statements, the SAMPLES, and the ORDER BY path list change per NDJSON.

---

## Run and capture output

```bash
python3 /tmp/validate_{schema_name}.py 2>&1 | tee /tmp/chdb_validation_output.txt
echo "Exit code: $?"
```

---

## Auto-fix loop

```
Run script
  │
  ├─ ✅ BASE TABLE + MVs PASSED → proceed to Step 5 (Cloud test)
  │
  └─ ❌ FAIL
        ├─ Read error message
        ├─ Identify root cause (table below)
        ├─ Fix: update the DDL in Atlys/schemas/{schema_name}.sql (and the SAMPLE if the
        │        chosen ORDER BY path was wrong) — re-derive from the NDJSON, do not guess
        └─ Re-run script  (max 5 iterations; surface to user if still failing)
```

### Error → fix decision table

| Error message | Root cause | Fix |
|---|---|---|
| `Unknown data type family JSON` / `Unexpected JSON` | chdb too old for the JSON type | `pip3 install --upgrade chdb`, re-run |
| `Syntax error ... '"'` | Escaped double-quoted literal (`'"UTC"'`) | Change to single quotes: `'UTC'`, `'express_checkout_shown'` |
| `Cannot create Nullable column … used in key expression` | A typed ORDER BY path is Nullable | Pick a path always present; type it non-nullable |
| `Cannot parse … as DateTime64` | Event timestamp value not parseable | Normalise the timestamp in SAMPLE (`T`→space, drop `Z`); confirm `{timestamp_path}` |
| `There is no subcolumn <path> in type JSON` | ORDER BY references a path not typed in the hint | Add that path to the `JSON(...)` typed hint list |
| `JSON object should start with '{'` / `Missing columns: 'payload'` | INSERT row not wrapped under `payload` | Wrap the raw row: `{"payload": <row>}` |
| `ch_insert_time is NULL` | Column not `MATERIALIZED now64(3)` | Restore exact `MATERIALIZED now64(3) CODEC(Delta, ZSTD(1))` |
| `Unknown function toYYYYMMDD` | Typo in partition expr | Use `toYYYYMMDD(ch_insert_time)` exactly |
| `Table already exists` | Leftover from a prior run | Use a fresh `chdb.session.Session()` or `DROP TABLE IF EXISTS` first |

---

## What passes = ready for Cloud

The run must show:

```
✅ CREATE DATABASE + base table + MVs
✅ INSERT {N} wrapped rows (one per event type)
✅ SELECT count() = {N}
✅ ORDER BY paths (payload.event, payload.<...>, payload.<timestamp>) are not NULL
✅ ch_insert_time auto-populated
```

Final line must be:

```
✅ BASE TABLE + MVs PASSED
```
