# The Instrumentation Agent & the Context Store

How a raw feature drop — a written spec plus a file of raw events — becomes a
live ClickHouse table, a validated schema, executed analytics, and an updated
semantic model of the warehouse.

This document explains the **working detail** of two things:

1. How the context (`context_versions`) table is created, versioned, and grown.
2. How the Instrumentation Agent works, pass by pass and check by check.

For layering and adapter boundaries, see [ARCHITECTURE.md](./ARCHITECTURE.md).

---

## 1. The big picture

```text
incoming_features/<feature>/
    spec.md          ← what the feature does, in prose
    events.ndjson    ← raw events, one JSON object per line
             │
             ▼
    [ deterministic profiler ]         no LLM — pure Python
             │  EventProfile
             ▼
    [ Instrumentation Agent ]          2 LLM passes + Python validation
             │  InstrumentationPlan
             ▼
    [ DDL + typed ingestion ]          real ClickHouse table
             │
             ▼
    [ Analytics Agent ]                plan → deterministic SQL → insights
             │
             ▼
    [ Context Agent (write) ]          new context version appended
             │
             ▼
    context_versions  (version N+1)
```

The central design rule: **an LLM never writes anything that reaches ClickHouse
unchecked.** Agents propose structured JSON; Python validates every field
against observed data and the live warehouse catalog before anything executes.

Orchestration lives in
[full_feature_workflow.py](backend/app/services/full_feature_workflow.py),
entered from
[feature_pipeline.py](backend/app/services/feature_pipeline.py#L79-L177).

---

## 2. Storage layout

Three internal tables are created on demand in the configured ClickHouse
database by [run_store.py](backend/app/repositories/run_store.py#L90-L142). They
sit alongside the eight preloaded baseline Atlys event tables and any tables the
pipeline generates.

### 2.1 `agent_runs` — one row per run snapshot

```sql
CREATE TABLE IF NOT EXISTS agent_runs
(
    run_id            UUID,
    version           UInt64,
    status            LowCardinality(String),
    feature           String,
    event_count       UInt64,
    table_created     String DEFAULT '',
    rows_loaded       UInt64 DEFAULT 0,
    context_version   UInt64 DEFAULT 0,
    insights_json     String DEFAULT '[]',
    langfuse_trace_id String DEFAULT '',
    error             String DEFAULT '',
    created_at        DateTime64(3, 'UTC'),
    updated_at        DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(version)
ORDER BY run_id
```

Writes are append-only. `version` is `int(now.timestamp() * 1_000_000)` — a
microsecond clock — so `ReplacingMergeTree(version)` collapses to the newest
snapshot for a `run_id`. A run is written twice: once as `profiled` right after
the ClickHouse preflight, once as `completed` at the end. Reads use `FINAL` so a
partially-merged part never returns a stale row.

### 2.2 `generated_artifacts` — the per-run payloads

```sql
CREATE TABLE IF NOT EXISTS generated_artifacts
(
    run_id        UUID,
    artifact_type LowCardinality(String),
    payload       String,          -- compact JSON
    created_at    DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(created_at)
ORDER BY (run_id, artifact_type)
```

Artifact types written over a full run, in order:

| `artifact_type` | Written by | Contents |
|---|---|---|
| `event_profile` | profiler stage | field profile, `spec_sha256`, tables seen at preflight |
| `schema` | validate/DDL stage | table name, exact DDL, column→type map |
| `instrumentation_plan` | Instrumentation Agent | the full validated plan |
| `proposed_analysis_plan` | Analytics Agent | the agent's *suggested* SQL (recorded, not executed) |
| `analysis_plan` | Python | the deterministic SQL actually run |
| `query_results` | SQL execution | aggregate rows per query |
| `insights` | Analytics Agent | evidence-backed insights |
| `context_diff` | Context Agent (write) | what this run added to the context |

Note `proposed_analysis_plan` vs `analysis_plan`: the agent's SQL is stored for
observability and comparison, but the SQL that touches ClickHouse is built in
Python by `build_deterministic_analysis_plan()`.

### 2.3 `context_versions` — the accumulated semantic model

```sql
CREATE TABLE IF NOT EXISTS context_versions
(
    version    UInt64,
    run_id     UUID,
    document   String,          -- a full ContextDocument as JSON
    created_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
ORDER BY version
```

Plain `MergeTree`, not `ReplacingMergeTree` — nothing here is ever collapsed or
updated. Every version is an immutable snapshot, so the state of the warehouse's
semantic model at any past run remains reconstructable.

---

## 3. How the context table is created and grows

### 3.1 Creation

There is no migration step. `ClickHouseRunStore.ensure_tables()` issues all three
`CREATE TABLE IF NOT EXISTS` statements and then sets an in-process
`_initialized` flag, so the DDL is attempted once per process and is a no-op
afterwards. It is called lazily from every entry point that touches storage
(`save_run_snapshot`, `next_context_version`, `get_latest_context`,
`get_run_summary`, `get_artifact`).

The database name is interpolated into the DDL, so it is checked against
`^[A-Za-z_][A-Za-z0-9_]*$` in the store's constructor; an unsafe name raises
`InvalidDatabaseNameError` before any SQL is built.

### 3.2 What a context document contains

One row's `document` column holds a full
[`ContextDocument`](backend/app/schemas/features.py#L135-L145):

```jsonc
{
  "version": 3,
  "run_id": "…uuid of the run that produced this version…",
  "entities": [
    { "name": "application", "table_name": "express_checkout_events",
      "primary_key": "application_id", "description": "...",
      "dimensions": ["device_type", "os"] }
  ],
  "relationships": [
    { "source_table": "express_checkout_events", "source_column": "application_id",
      "target_table": "applications", "target_column": "id", "reason": "..." }
  ],
  "metrics": [
    { "name": "express_conversion", "description": "...",
      "numerator": "...", "denominator": "...", "dimensions": ["device_type"] }
  ],
  "naming_conventions": ["event tables end in _events", "..."],
  "conflicts": ["..."]
}
```

Each version is the **complete** model, not a delta. The delta lives separately
as the `context_diff` artifact on the run.

### 3.3 The version lifecycle, step by step

**Read (start of run).** `get_latest_context()` runs
`SELECT document FROM context_versions ORDER BY version DESC LIMIT 1` and
validates the JSON back into a `ContextDocument`. Before the first ever write it
returns `None`, and the pipeline proceeds with an empty `ContextSelection()`.

**Narrow.** The stored document grows with every feature ever processed, so it is
not passed whole into schema design. The Context Agent runs in **read-only mode**
(`_CONTEXT_READ_PROMPT`) and selects only the entities, relationships, metrics,
and conventions relevant to this feature.

Because a model can hallucinate an entity that sounds plausible,
[`_select_context()`](backend/app/services/full_feature_workflow.py#L422-L481)
filters the selection back down to what the stored document literally contains —
matching entities and metrics by `name`, relationships by the
`(source_table, source_column, target_table, target_column)` tuple, and
conventions by exact string. **A fabricated relationship can never shape a
schema.**

**Write (end of run).** After the table exists, rows are loaded, and insights are
produced, the agent runs in **write mode** (`_CONTEXT_WRITE_PROMPT`) and is asked
to report *only what is new*. Its `ContextAgentOutput` is then:

1. **Validated** by `validate_context_output()` — every entity's `table_name` and
   `primary_key`, every entity dimension, and both sides of every relationship
   must exist in the live column catalog. A miss raises `ContextValidationError`.
2. **Retried once** with the validation error fed back as `validation_feedback`.
3. **Salvaged**, if both attempts fail, by `valid_context_subset()`: entities and
   relationships that fail validation are dropped, dimensions that don't exist
   are stripped, and the rest is kept. The rationale is explicit in the code —
   the schema, data, and insights are already durable, so a partly-invalid
   context proposal should not discard the knowledge that is sound.

**Merge.** `merge_context()` folds the additions over the previous snapshot.
Newer definitions win on key collision — `name` for entities and metrics, the
four-part tuple for relationships — and conventions/conflicts are
order-preserving deduplicated string unions. The agent only ever reports what's
new; the complete document is always reassembled in Python, so a snapshot never
depends on the model repeating itself correctly.

**Append.** `next_context_version()` reads `max(version)` and returns `+1` (or `1`
on an empty table), and `save_context_version()` inserts one new row. Older rows
are never touched. The same version number is also recorded on the run's
`agent_runs` snapshot and in the `context_diff` artifact.

> **Concurrency note.** `next_context_version()` is a read-then-insert with no
> lock. Two runs writing context concurrently can allocate the same version.
> The pipeline is designed for sequential feature processing.

### 3.4 Why it's shaped this way

- **Immutable versions** make every past state auditable and let you diff any two
  runs' worldviews.
- **Full snapshots** mean reading current context is a single
  `ORDER BY version DESC LIMIT 1` — no replay of deltas.
- **Diffs stored separately** as artifacts keep "what changed in this run" a
  cheap, run-scoped lookup (`GET /runs/{run_id}/context-diff`).
- **Agent narrows, Python verifies** keeps prompt size bounded as the warehouse
  grows without letting the model invent structure.

---

## 4. The Instrumentation Agent in detail

The Instrumentation Agent turns `spec.md` + raw events into a ClickHouse table.
It runs as **two separate LLM passes** with a deterministic profile in between
and hard validation after — implemented in
[full_feature_workflow.py](backend/app/services/full_feature_workflow.py#L122-L243)
and [generated_schema.py](backend/app/tools/generated_schema.py).

### 4.0 Before the agent: the deterministic profile

No LLM sees raw events. [`profile_events()`](backend/app/tools/event_profiler.py#L183)
streams `events.ndjson` one bounded line at a time and emits an `EventProfile`:

- **`event_count`** — total records.
- **`event_names`** — counts per event name, discovered from the first of
  `event_name`, `event`, `type`, `name` that holds a non-empty string.
- **`fields`** — per top-level field: `observed_type` (collapsed), the full
  `observed_types` set, `presence_count` / `presence` ratio, an
  `approx_cardinality` with an `is_estimate` flag, and up to 5 short scalar
  examples.

Cardinality uses a bounded **min-hash** sketch: blake2b-64 per canonical value,
keeping the 1024 smallest hashes; past that it estimates
`(sample_size - 1) × 2^64 / max_kept_hash` and flags the result as an estimate.
Memory stays bounded regardless of file size.

Everything is bounded and fails loudly: line bytes, distinct fields (512),
distinct event names (1024), name lengths, and example bytes. Non-standard JSON
numbers (`NaN`, `Infinity`) are rejected outright.

This profile — never the raw rows — is what goes into the prompt.

### 4.1 Pass 1 — understanding, before any schema exists

Prompt `_UNDERSTANDING_PROMPT`. Input: the spec and the event profile.
Output: [`FeatureUnderstanding`](backend/app/schemas/agents.py#L29-L37).

The agent is told explicitly: *do not design a schema, choose column types, or
name a table.* It states what the feature does in analytics terms —
`business_goal`, `primary_entity`, `candidate_join_keys`, `expected_analyses`,
`key_questions`.

**Grounding check.** `_understand_feature()` verifies that `primary_entity` and
every `candidate_join_key` is an actually-observed field name. If any is not, the
offending names are fed back as `validation_feedback` and the pass is retried
once. A second failure raises `GeneratedSchemaError` and the run stops — a
misunderstanding here would poison every later stage.

Splitting understanding from schema design matters: it lets the context lookup
happen against a *semantic* description of the feature rather than against a
column list that doesn't exist yet.

### 4.2 Between passes — context retrieval

The understanding drives the Context Agent read described in §3.3. The resulting
narrowed `ContextSelection` is what makes schema design *warehouse-aware*: the
prompt tells the agent that existing context describes how the warehouse already
models related data, and to reuse its naming conventions and join keys where they
apply.

### 4.3 Pass 2 — the schema and feature contract

Prompt `_INSTRUMENTATION_PROMPT`. Input: spec, event profile, the pass-1
understanding, the selected context, and — on retry — `validation_feedback`.
Output: [`InstrumentationPlan`](backend/app/schemas/agents.py#L16-L26)
(`feature_name`, `table_name`, `primary_entity`, `timestamp_field`, `columns`,
`order_by`, `order_by_reasoning`, `funnel_steps`, `dimensions`, `relationships`,
`expected_queries`). On the first run only, the agent selects the physical key
from the spec, profile, relevant relationships, metrics, and expected workload.
Each key field must carry a query role and a concrete reason.

The prompt encodes the type policy directly:

| Observed | Column type |
|---|---|
| timestamp field | `DateTime64(3)` |
| string / object / array | `String` |
| integer | `Int64` |
| float | `Float64` |
| boolean | `UInt8` |

Plus the structural rules: exactly one column per observed top-level field;
nullable whenever presence < 1 or a null was seen; table name a safe snake_case
identifier ending in `_events`; `ORDER BY` of
1–4 non-null columns; `primary_entity` and `timestamp_field` must be observed
field names.

The response is constrained server-side too — Fireworks is called with
`response_format: json_schema` built from the Pydantic model, `temperature=0.1`,
and the client itself retries up to 3 times on transport or validation failure
([fireworks.py](backend/app/agents/fireworks.py#L32-L84)).

### 4.4 The validation loop — where the guarantees live

Up to **3 attempts**. Each candidate goes through
[`validate_instrumentation_plan()`](backend/app/tools/generated_schema.py#L39-L105);
a `GeneratedSchemaError` is stringified back into the next prompt as
`validation_feedback`. If all 3 fail, the error is raised and the run stops.

Every check, in order:

1. **Identifier safety** — table name matches `^[A-Za-z_][A-Za-z0-9_]*$`. This is
   what makes backtick-quoted interpolation into DDL safe.
2. **Naming** — table name ends in `_events`.
3. **No duplicate columns.**
4. **Exact column-set match** — `set(columns) == set(profile.fields)` for
   top-level fields. Missing and extra columns are both reported by name, so the
   agent can neither drop an observed field nor invent one.
5. **Type compatibility** — per field, against `_TYPE_COMPATIBILITY`. Integers
   may widen to `Float64`; objects, arrays, mixed, and all-null fields must be
   `String`. The declared timestamp field must be exactly `DateTime64(3)`.
6. **Nullability** — a field with `presence_count < event_count`, or where a null
   was ever observed, *must* be `Nullable`.
7. **Grounding** — `timestamp_field` and `primary_entity` must be observed fields.
8. **Funnel steps** — at least 2, and every step must appear in
   `profile.event_names`.
9. **Dimensions** — every declared dimension must be an observed field.
10. **`ORDER BY`** — references known columns only, and none of them nullable
    (ClickHouse sorting keys can't be nullable here).
11. **Physical-design explanation** — `order_by_reasoning` covers every key field
    exactly once and in key order.
12. **Time access** — event-stream keys include the timestamp field.
13. **Cardinality safety** — near-unique row identifiers (`id`, `event_id`,
    `request_id`, `trace_id`) cannot occupy either of the first two positions.

Validation is then **run a second time** immediately before DDL generation, in
its own `validate_schema` trace span. Redundant by construction, and deliberately
so: the DDL builder trusts its input, so the check sits directly in front of it.

### 4.5 DDL and ingestion

`build_ddl()` emits, with every identifier re-checked through `_quoted()`:

```sql
CREATE TABLE `<database>`.`<table_name>`
(
    `col_a` String,
    `col_b` Nullable(Int64)
)
ENGINE = MergeTree
[PARTITION BY toYYYYMM(`<timestamp_field>`)]
ORDER BY (`...`)
```

The instrumentation plan explicitly chooses the partition expression, or null
for no partition, and explains the decision. Python validates the selected field
and function before compiling the bracketed clause; it does not independently
choose a partition key or granularity.

`ingest_events()` then streams the NDJSON again and inserts in batches of 1000.
Per value, `_convert()` coerces to the planned type: dicts and lists are
serialized to compact JSON when the column is `String` (and rejected for numeric
columns), booleans/ints go to `UInt8`/`Int64`, and timestamps parse from ISO-8601
with `Z` normalized to `+00:00`.

Finally, `rows_loaded` is compared to `profile.event_count`; a mismatch raises
and fails the run.

### 4.6 Materialized daily aggregate

After the raw schema is accepted and before initial ingestion, Python compiles a
bounded materialization from the same semantic contract. It uses the selected
primary entity, event field, timestamp, and at most two non-null declared
dimensions. The compiler creates an `AggregatingMergeTree` daily target with
`countState()` and `uniqState(primary_entity)`, plus a materialized view feeding
that target.

New feature data flows through the view during initial ingestion. When adopting
contracts for an existing source table, the target is explicitly backfilled once.
The materialization definition is persisted in
`feature_materialization_contracts` and tied to the source schema fingerprint;
schema drift cannot silently reuse an incompatible aggregate. A validated daily
trend/segment query reads the target using `countMerge()` and `uniqMerge()`, so
the optimization is part of the executed analysis rather than unused DDL.

### 4.7 Resumability

The first validated plan is stored in `feature_schema_contracts`, keyed by
feature. Later runs load that contract and do not ask the agent to redesign the
schema. The profile is still validated against the contract, so a new field,
type change, or nullability change is reported as schema drift.

If a table predates contracts, its actual `system.tables.sorting_key` is read and
used to bootstrap the first contract; an agent proposal is never recorded as if
it were the live key. `_validate_existing_table()` also compares the live
column→type map against the contract exactly. On a match, the existing row count
must still equal `profile.event_count`.

### 4.8 Observability

Each stage opens a Langfuse span with bounded metadata — never raw rows:
`instrumentation_pass_1`, `context_agent_read`, `instrumentation_pass_2` (records
which attempt succeeded), `validate_schema`, `execute_ddl` (records
`reused_existing`), `ingest_events`, `analytics_agent_plan`,
`execute_analytics_sql`, `analytics_agent_insights`, `context_agent_write`.

Tracing is off unless `LANGFUSE_TRACING_ENABLED=true`.

---

## 5. What happens after instrumentation

**Analytics planning.** The Analytics Agent proposes 3–5 bounded aggregate
SELECTs; that proposal is stored as an artifact. What actually executes is built
by `build_deterministic_analysis_plan()` in Python — funnel, adoption, latency,
segment, and baseline primitives derived from the validated plan's funnel steps,
entity, and dimensions.

**SQL safety.** Every query passes `validate_analysis_sql()`: must start with
`SELECT`, no `;`, no `--` or `/*`, no DDL/DML keywords, and every `FROM`/`JOIN`
target must be in the allowlist (baseline tables plus this run's new table). A
missing `LIMIT` gets `LIMIT 200` appended. Execution is further capped with
`max_execution_time=30` and `max_result_rows=200`.

**Insights.** The agent interprets *only the returned aggregate rows*. Each
insight carries observation, evidence, interpretation, context used,
recommendation, confidence, and caveats; it's instructed not to claim causality
and to lower confidence when evidence is thin.

**Context write.** As described in §3.3, producing the next context version.

---

## 6. Running it

Input goes in `incoming_features/<feature>/` with exactly `spec.md` and
`events.ndjson`. From `backend/`:

```bash
# CLI
uv run atlys-pipeline --feature 01_express_checkout

# MCP server (stdio)
uv run atlys-mcp

# REST API
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Or the whole stack — REST on `8000`, Streamable HTTP MCP on `8001`:

```bash
docker compose watch
```

### Endpoints

| REST (`/api/v1`) | MCP tool |
|---|---|
| `POST /features/upload` | — |
| `POST /features/process` | `process_feature` |
| `GET /runs/{run_id}` | `get_run_summary` |
| `GET /runs/{run_id}/schema` | `get_schema` |
| `GET /runs/{run_id}/context-diff` | `get_context_diff` |
| `GET /runs/{run_id}/insights` | `get_insights` |

Upload stores files only; processing is a separate call. Artifacts return `404`
(or an MCP tool error) until the stage that produces them has run — partial work
is never reported as a completed run.

### Configuration

Secrets go in the untracked `.env.local`, not the checked-in `.env`:

```dotenv
CLICKHOUSE_HOST=...
CLICKHOUSE_PORT=8443
CLICKHOUSE_USERNAME=default
CLICKHOUSE_PASSWORD=...
CLICKHOUSE_DATABASE=atlys
CLICKHOUSE_SECURE=true

FIREWORKS_API_KEY=...
# default model: accounts/fireworks/models/gpt-oss-120b

LANGFUSE_TRACING_ENABLED=false
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

Without `FIREWORKS_API_KEY` the agent workflow is not constructed at all, and
`process_feature` stops after profiling and persistence, returning status
`profiled`. ClickHouse credentials are resolved lazily, so importing the app or
hitting its health check needs neither.

---

## 7. Design invariants

1. Raw event rows never enter a prompt, an API response, or a trace — only
   bounded profiles and aggregates.
2. Every LLM output is a Pydantic model with `extra="forbid"`, requested via JSON
   schema and validated on arrival.
3. Every identifier interpolated into SQL is regex-checked first.
4. Agents propose; Python validates against observed data and the live catalog,
   and Python builds the SQL that executes.
5. Retries carry the specific validation error back into the prompt.
6. Storage is append-only. Nothing is mutated in place.
7. A failure late in the pipeline never discards durable work completed earlier.
