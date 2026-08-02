# Instrumentation Agent Plan

## Objective

Build an evidence-driven Instrumentation Agent that turns a feature specification and raw event samples into production-ready ClickHouse DDL, event mappings, and justified materialized views.

The agent's core behavior must live in one canonical, versioned system prompt that can be improved iteratively. Deterministic validation, execution, tracing, and regression evaluation should remain outside the prompt.

## Workload Summary

- **Workload:** Product analytics event streams.
- **Data shape:** Append-heavy events, occasional duplicates and backfills, a shared event envelope, and feature-specific attributes.
- **Primary queries:** Funnels, time trends, user/application journeys, and device, geography, and application-version segmentation.
- **Main design risk:** Selecting a schema from a small sample without understanding expected queries, volume, retention, or late-arrival semantics.
- **Operating constraint:** The unseen feature must work without prompt changes or feature-specific hardcoding.

## Required Planning Inputs

## Blob-backed investigation inputs

For an investigation submitted through `deploy/ui`, the runner supplies the
investigation ID plus short-lived Azure Blob SAS URLs for `events.ndjson` and
`spec.md`. The instrumentation agent must fetch both files before beginning
discovery, must use only the supplied URLs, and must never echo a SAS URL or its
token in its hand-off. The raw input stays in Azure Blob Storage; all downstream
agents receive the structured instrumentation hand-off instead of the blobs.

The agent must discover these inputs or record explicit assumptions before finalizing DDL.

| Area | Required evidence |
| --- | --- |
| Event semantics | Trigger, grain, uniqueness, client/server source, and event version |
| Identity | Event, user, application, and session IDs, including whether each may be absent |
| Time | Event time, ingestion time, precision, timezone, and late-arrival window |
| Data quality | Duplicates, retries, backfills, malformed rows, and schema evolution |
| Scale | Events per day, peak events per second, batch size, and expected growth |
| Queries | Top 5–10 filters, groupings, joins, funnels, and time windows |
| Retention | Raw and aggregate retention plus legal/privacy deletion requirements |
| Freshness | Query latency and data-freshness targets |
| Cardinality | Approximate distinct counts for strings and candidate key columns |
| Numeric ranges | Minimum, maximum, signedness, precision, and overflow expectations |
| Execution policy | Plan-only, sandbox apply, or approved production apply |

Missing information must result in named assumptions and reduced confidence, not silent guesses.

## Required Schema Decision Pipeline

### 1. Normalize the feature specification

Produce an event catalog containing:

- Event name and version
- Grain and trigger
- Identifiers
- Event and ingestion timestamps
- Attributes and their semantics
- Example payloads
- Required invariants

### 2. Inspect the existing environment

Follow the `agent-discovery-schema` workflow:

1. List databases.
2. List tables, engines, row counts, and sizes.
3. Inspect columns, types, and comments.
4. Inspect sorting, primary, and partition keys.
5. Inspect data-skipping indexes.
6. Read bounded samples.
7. Run `EXPLAIN` for representative queries.

### 3. Profile input data

Measure:

- Null and empty-value rates
- Minimum and maximum numeric values
- Approximate cardinality
- String lengths
- Parse failures and unexpected values
- Timestamp ranges and precision
- Duplicate and backfill rates

Do not infer a narrow integer, `Enum`, or non-null constraint solely from a few sample rows.

### 4. Choose the table topology

Evaluate:

- One feature-level event table
- One table per event
- A shared event table with typed common columns and dynamic properties
- A raw landing table followed by a typed curated table

A typed feature-level table is a reasonable starting hypothesis for this challenge, but the agent must justify it against query patterns and schema variability.

### 5. Choose the engine and mutability model

- Default append-only telemetry to `MergeTree`.
- Consider `ReplacingMergeTree(version)` only when replacement semantics are real and a deterministic version exists.
- Consider collapsing engines only when explicit state transitions require them.
- Do not present `ReplacingMergeTree` as automatic or immediate deduplication.
- Prefer append-friendly late-arrival handling over frequent mutations.

### 6. Select column types

Apply these ClickHouse Agent Skills rules:

- `schema-types-native-types`
- `schema-types-minimize-bitwidth`
- `schema-types-lowcardinality`
- `schema-types-enum`
- `schema-types-avoid-nullable`
- `schema-json-when-to-use`

Decision guidelines:

- Use `UUID` for actual UUID values.
- Use `DateTime` or `DateTime64` only at the precision required.
- Use `Decimal` or integer minor units for money, never `Float64`.
- Use `Bool` for true booleans.
- Select appropriately sized signed or unsigned integers from proven ranges.
- Use `LowCardinality(String)` for stable, repeated strings with measured low cardinality.
- Use `Enum` only for genuinely closed, governed sets. Prefer `LowCardinality(String)` when values can evolve.
- Use `Nullable` only when null is semantically distinct from the type's default value.
- Use typed columns for known analytical fields and `JSON` only for genuinely variable properties.

Source: [Selecting data types](https://clickhouse.com/docs/concepts/best-practices/select-data-type)

### 7. Choose `ORDER BY` from query patterns

Apply:

- `schema-pk-plan-before-creation`
- `schema-pk-prioritize-filters`
- `schema-pk-cardinality-order`
- `schema-pk-filter-on-orderby`

The agent must:

- Rank candidate columns by filter frequency and pruning power.
- Prefer common equality filters before time-range columns.
- Generally progress from lower to higher cardinality when this does not conflict with real query patterns.
- Keep the useful key concise; four or five expressions are usually sufficient.
- Put unique event identifiers late in the key, if they belong in it at all.
- Never lead with a random UUID merely because it is unique.
- Validate representative queries with `EXPLAIN indexes = 1`.

Source: [Choosing a primary key](https://clickhouse.com/docs/concepts/best-practices/choosing-a-primary-key)

### 8. Choose partitioning for lifecycle management

Apply:

- `schema-partition-lifecycle`
- `schema-partition-low-cardinality`
- `schema-partition-query-tradeoffs`
- `schema-partition-start-without`
- `decision-partitioning-timeseries`

The agent must:

- Start without partitioning when lifecycle requirements and volume are unclear.
- Consider monthly time partitions when retention or bulk expiration warrants them.
- Use daily partitions only when retention is short, scale supports them, and projected partition count stays safe.
- Never partition by user, application, session, or event UUID.
- Project the partition count across the complete retention horizon.
- Treat partitioning primarily as lifecycle management rather than the first query accelerator.

Keep partition cardinality low, normally below roughly 100–1,000 distinct values.

Source: [Choosing a partitioning key](https://clickhouse.com/docs/concepts/best-practices/partitioning-keys)

### 9. Design TTL explicitly

TTL must be derived from a documented retention policy rather than invented by the model.

The decision must cover:

- Raw-event retention
- Aggregate retention
- Deletion versus move/recompression behavior
- Alignment between TTL boundaries and partitions
- Late arrivals and backfills
- The asynchronous merge-based nature of TTL actions
- Policy owner and business or compliance justification

Source: [Managing data with TTL](https://clickhouse.com/docs/concepts/features/operations/delete/ttl)

### 10. Define a preliminary analytics query registry

Before executing DDL, translate the product questions in the feature specification into candidate metrics and queries. This is a hypothesis registry that will be refined after ingesting and observing the data.

Every query definition must include:

- Stable query/metric ID and product-facing name
- Business question and decision it supports
- Event/entity grain
- Numerator, denominator, and deduplication rule
- Source events/tables and required join/correlation keys
- Time window and attribution window
- Filters and grouping dimensions
- Required freshness and expected query frequency
- Raw-table reference SQL
- Known correctness gaps or missing instrumentation
- Whether it is initially `raw_only`, an `mv_candidate`, or `blocked`

The registry should consider reusable metric families when supported by the spec:

- Event volume and unique-entity trends
- Funnel stage counts, completion, and step conversion
- Adoption, attach, success, failure, retry, and abandonment rates
- Time-to-step, latency, and percentile distributions
- Monetary totals, averages, and distributions with explicit units/currencies
- Segment comparisons across low-cardinality dimensions
- Data-quality and instrumentation-health metrics

Do not invent metrics merely because they are easy to aggregate. Each query must answer a stated product question or validate data quality.

### 11. Create the base schema and ingest the complete event file

The generated event table or tables are the canonical base layer. Load the supplied NDJSON/MDJSON directly into these tables through the declared mappings. Materialized views are not used to populate this base layer.

Execution depends on mode:

- `plan`: Produce base-table DDL, import SQL/configuration, mapping logic, and reconciliation queries without writes.
- `sandbox`: Create isolated base tables, ingest the complete supplied NDJSON/MDJSON file, and run all validations.
- `apply`: Create approved base tables and ingest the complete supplied event file in the target database.

The ingestion stage must:

1. Fetch the supplied event file without exposing its SAS URL or credentials.
2. Parse newline-delimited JSON as `JSONEachRow` or through an explicitly justified raw landing format.
3. Apply the declared raw-to-curated mappings and conversions.
4. Use healthy batches per `insert-batch-size`: normally 10K–100K rows, or one bounded batch when the complete fixture is smaller. Do not manufacture rows to reach a batch size.
5. Use durable async inserts only when producer shape prevents batching; keep `wait_for_async_insert = 1`.
6. Quarantine or report rejected rows with field-level reasons instead of silently dropping them.
7. Reconcile source rows, inserted rows, rejected rows, distinct event IDs, per-event counts, and any intentional deduplication.
8. Stop before analytics modeling if reconciliation does not balance exactly.

Record an ingestion manifest containing source content hash, source row count, batch count, accepted/rejected counts, duplicate policy, target table, mapping version, start/end time, and validation status. Never persist a signed source URL.

### 12. Preview and profile the ingested data

Use the ingested base tables—not only the original sample—to produce compact evidence for analytics modeling. Push computation into ClickHouse and return aggregated results to the model; do not pull the full event file into the LLM context.

The bounded preview suite should include:

- Total and per-event row counts
- Event-time minimum, maximum, and distribution by day/hour where useful
- Distinct event, entity, attempt, session, and user counts when present
- Duplicate event-ID and correlation-key multiplicity checks
- Null, empty, invalid, and unmapped-field rates
- Cardinality and top values for candidate dimensions
- Numeric min/max and approximate quantiles for counts, durations, amounts, and rates
- Funnel/path reachability and repeated-step counts at the correct journey grain
- Join-multiplicity checks before any cross-table metric is accepted
- Observed grouping cardinality for proposed aggregation dimensions

All preview queries must follow `agent-query-safety`: time/scan limits, bounded results, no unbounded `SELECT *`, and progressive exploration. Preserve query SQL, settings, compact result, rows/bytes read when available, and the conclusion drawn from it.

### 13. Refine and validate aggregation queries

Use the feature spec together with the post-ingestion preview to finalize a set of Analytics Agent-ready queries.

For every registry item:

1. Confirm that the required events, fields, correlation grain, and denominator exist.
2. Mark causal or exact-conversion questions `blocked` when assignment/attribution data is missing.
3. Write a bounded raw-table reference query.
4. Execute the query against the ingested data in sandbox/apply mode.
5. Check result cardinality, null/zero denominators, join multiplication, and semantic plausibility.
6. Record a compact preview result and confidence.
7. Classify the final serving path as `raw_only`, `incremental_mv`, `refreshable_mv`, or `blocked`.

Aggregation queries should filter source tables before joins per `query-join-filter-before`. Prefer aggregation before enrichment and avoid repeated runtime joins when a dictionary, denormalized field, or justified derived model is better per `query-join-consider-alternatives`.

The Analytics Agent must always receive a correct raw-table reference query, even when an MV-backed serving query is also provided.

### 14. Plan and create materialized views only when justified

The required data flow is:

```text
NDJSON/MDJSON
    |
    v
generated base event table(s)
    |
    +-- bounded raw aggregation previews
    |
    v
additional analytical materialized view(s)
    |
    v
dedicated aggregate target table(s)
    |
    v
Analytics Agent serving queries
```

Non-negotiable boundaries:

- Generated base event tables are populated by the ingestion stage, not by analytical MVs.
- Every analytical MV reads from one or more generated base tables.
- Every incremental analytical MV writes to a separate, dedicated target table; it must never target or write back into its source base table.
- MV target tables are additional analytics-serving objects and are not replacements for the generated base tables.
- The Analytics Agent may query an MV target when it is the preferred serving path, while retaining a raw query against the base tables as the correctness fallback.
- An incremental MV is triggered by inserts into its source table. When a metric needs complex joins across multiple generated tables, use a refreshable MV or a bounded aggregation query unless the incremental semantics are proven correct.

Apply:

- `decision-real-time-preaggregation`
- `query-mv-incremental`
- `query-mv-refreshable`

Use:

- Incremental materialized views for repeated, append-friendly aggregations.
- Refreshable materialized views for complex joins or scheduled recomputation.
- Raw tables only while important query patterns are still evolving.

An MV candidate should be promoted only when post-ingestion evidence shows:

- A named query or metric will be reused by the Analytics Agent.
- The metric grain, deduplication, attribution, and late-data semantics are correct.
- Grouping dimensions have bounded observed/projected cardinality.
- Preaggregation should materially reduce rows scanned or repeated transformation work.
- Freshness requirements match incremental or refreshable semantics.
- The additional storage, insert-time work, and operational complexity are justified.

Prefer compact, reusable rollups over one MV per PM question. Avoid high-cardinality cubes and speculative combinations of every dimension. Keep the raw path for ad hoc cuts and correctness checks.

Every proposed materialized view must name:

- Generated base source table(s)
- Separate analytical target table
- Its consumer query or metric
- Expected scan reduction or latency benefit
- Target-table engine and ordering key
- Backfill strategy
- Late-arrival and update behavior
- Correctness limitations

It must also provide:

- Target-table DDL, engine, `ORDER BY`, partitioning, and TTL
- MV DDL and dependency order
- Analytics Agent serving query using the target table
- Equivalent raw reference query
- Post-ingestion evidence used to justify materialization
- Estimated raw-to-aggregate row reduction
- Backfill SQL and cutoff/window strategy
- Reconciliation SQL and expected invariants

Because incremental materialized views process newly inserted blocks rather than existing source rows, creating one after the event-file import requires an explicit backfill:

1. Create the separate analytical target table.
2. Determine and record a source cutoff.
3. For a static fixture with paused ingestion, backfill the complete source range with `INSERT INTO target SELECT ...` using the same aggregate-state logic as the MV.
4. Create the incremental MV for subsequent inserts.
5. If ingestion is concurrent, use a monotonic ingestion watermark rather than event time: choose cutoff `T`, create the MV to accept rows at/after `T`, then backfill source rows before `T`. Account explicitly for late event times, and document the boundary so no insert is missed or counted twice.
6. Reconcile target results against the raw reference query across totals and representative dimension cuts.

Refreshable MVs must instead define refresh interval, `REPLACE`/`APPEND` semantics, dependencies, acceptable staleness, and a runtime expectation comfortably below the refresh interval.

### 15. Validate the complete base-and-analytics design

Required validations:

- DDL parses on the target ClickHouse version.
- The complete supplied event file imports successfully and ingestion reconciliation balances.
- Invalid, null, and overflow cases behave intentionally.
- Raw-to-table mapping has no unexplained dropped fields.
- Representative queries use keys according to `EXPLAIN`.
- Expected partitions and parts remain bounded.
- TTL expressions compile.
- Materialized-view results match a direct reference query.
- Every non-blocked product question has an executable aggregation query.
- Every created MV has a working Analytics Agent serving query and raw fallback.
- Incremental MV backfill plus live/cutoff rows covers the source exactly once.
- Metric previews use the correct grain and do not multiply rows through joins.
- Existing objects are diffed rather than silently accepted through `IF NOT EXISTS`.

Agent-generated inspection queries must follow `agent-query-safety`: bounded result rows, scan limits, execution timeouts, and progressive exploration.

### 16. Persist the instrumentation artifact and hand off

Support three explicit modes:

- `plan`: Generate artifacts without writes.
- `sandbox`: Create objects in an isolated database, ingest the full event file, create justified derived objects, and run validation.
- `apply`: Execute approved base/derived DDL and ingestion against the target database.

The system prompt must prohibit destructive changes to existing tables without an explicit migration plan and authorization.

After all mode-appropriate work and validation finishes, construct one complete instrumentation artifact containing the schema design, executed object names, ingestion manifest, post-ingestion profile, metric registry, aggregation queries, analytical MV definitions, backfill/reconciliation results, risks, and open items.

Persist this artifact before invoking the Analytics Agent:

1. Add dedicated `instrumentation_result String` and `instrumentation_result_sha256 FixedString(64)` fields to the append-only `default.investigations` revision schema. Keep `final_result` reserved for the final output of the complete agent chain.
2. Serialize the complete structured artifact deterministically and calculate a SHA-256 content hash.
3. Append a new `investigations` revision for the same `investigation_id` containing `instrumentation_result`, its hash, instrumentation completion status, and the existing workflow metadata.
4. Continue storing the same stage result in `investigation_agent_status.result` for per-agent operational tracing; this is not a substitute for the required investigation-level artifact.
5. Read the newly appended investigation revision back and verify the investigation ID, revision, non-empty payload, and hash.
6. Never persist source SAS URLs, tokens, credentials, or other transient secrets inside the artifact.
7. If persistence or verification fails, mark the instrumentation stage failed and do not invoke the Analytics Agent.
8. Pass the exact verified persisted artifact to the Analytics Agent. Do not regenerate or summarize a different handoff payload.

The persisted artifact stores definitions, object names, compact previews, validation results, and queries. Event rows remain in the generated base tables, and aggregate rows remain in the dedicated analytical target tables.

The handoff must identify, for each metric, the preferred source (`raw` or MV target), executable query, grain, dimensions, freshness, preview result, confidence, and fallback query. It must also include the persisted investigation revision and artifact hash so downstream traces can prove which instrumentation output they consumed.

## Schema Drift and Context Changelog Ownership

Schema history is a Context-layer concern, not an Investigation UI concern. The
UI/backend is responsible only for accepting source artifacts, running the
Instrumentation Agent, and durably storing its verified handoff. It must not
interpret DDL, infer schema changes, or write a schema-drift changelog.

On `get_and_validate_context`, the Context Agent refreshes only the relevant
objects from the current instrumentation handoff and its declared dependencies.
It invokes a dedicated Context Store schema-catalogue tool; it does not
hand-build metadata snapshots or diffs in model output.

```text
Instrumentation Agent
  -> verified object catalogue + event_tables + decision_trace
  -> persisted investigation handoff
  -> Context Agent refresh
  -> deterministic schema-catalogue tool
  -> immutable schema snapshots + physical drift
  -> Context Agent semantic review and context publication
```

### Stable comparison scope

Investigation-scoped names such as `default.inv_<investigation-id>_events` are
intentionally unique and cannot identify an evolving logical schema. Each
submission must therefore carry an explicit stable `feature_key` (for example,
`express_checkout`). The instrumentation handoff must preserve it and identify
each created object by a stable logical role, such as `events`,
`event:<event_name>`, `rollup:daily_event_counts`, or `mv:daily_event_counts`.

Never use the physical object name, an investigation ID, or a spec checksum as
the cross-run schema identity. A checksum identifies an input revision, not a
feature lineage. If a stable feature key or logical role is absent, preserve a
run-level snapshot but mark cross-run comparison as unavailable rather than
guessing a match.

### Programmatic schema-catalogue tool

Provide the Context Agent a bounded tool conceptually equivalent to:

```text
refresh_schema_catalogue(feature_key, objects, previous_context_version)
  -> schema_version_ids, schema_changes, verification_status
```

The tool must perform the following deterministically:

1. Discover live `default`-schema metadata for the scoped objects: exact DDL,
   engine, columns and ordinal positions, types, defaults, codecs, comments,
   sorting/primary/partition keys, TTL, indexes, projections, and
   materialized-view source/target/query relationships.
2. Persist an immutable physical snapshot per logical object in
   `agent.schema_versions` and column-level rows in `agent.schema_columns`.
3. Generate a normalized metadata fingerprint for comparison while retaining
   the exact ClickHouse DDL as audit evidence. Normalization may remove only
   investigation-specific physical-name prefixes and formatting; it must not
   hide a semantic expression change.
4. Compare with the most recent verified snapshot for the same
   `feature_key` and logical role, then append explicit rows to
   `agent.schema_changes`.
5. Return compact change evidence and persistent IDs to the Context Agent.

The schema history tables are append-only audit metadata. Start without a
partition key unless their actual lifecycle/volume warrants one; do not use
`ReplacingMergeTree`, mutations, or an LLM-generated diff to maintain history.

Each schema-change row must include the prior and new snapshot IDs, feature
key, logical role, operation, before/after metadata, observed time,
investigation ID, evidence query IDs, and impact classification:

- `additive`: a verified compatible addition;
- `review_required`: renamed/removed column, semantic default change, new
  index/projection, or materialized-view serving change;
- `breaking`: type, engine, `ORDER BY`, primary/partition key, TTL, grain, or
  materialized-view query change that can alter compatibility or results;
- `no_change`: identical normalized metadata, retained only when an explicit
  refresh audit is useful.

Changing `ORDER BY` is always review-required at minimum because it is
effectively immutable for an existing ClickHouse table; a physical migration is
a separate authorized workflow. This follows `schema-pk-plan-before-creation`.
The tool must obtain metadata from ClickHouse using handoff object names rather
than expecting or trusting handoff DDL,
following `agent-discovery-schema`.

### Context-layer semantic diff and publication

`agent.business_logic_versions` remains the immutable full snapshot store.
Add an append-only `agent.context_changes` table containing one semantic change
per stable context object:

```text
context_version, previous_context_version, domain, object_id, operation,
before_json, after_json, reason, evidence_refs, confidence, review_required,
schema_version_ids, created_at
```

Before a Context version is published, a deterministic Context Store operation
must canonicalize `snapshot_json` arrays by their required stable `id` and
compute `add`, `modify`, `deprecate`, `supersede`, or `no_change` operations.
It must compare semantic object fields, not Markdown formatting or array order.
The Context Agent supplies evidence, classification, and a proposed reason; the
tool validates/persists the final records and renders the concise
`change_summary`. A model-written prose summary alone is not a changelog.

The Context Agent applies publication policy to the returned physical drift:

- automatically publish verified additive live-schema metadata;
- record type/key/partition/TTL/MV-query changes as review-required context
  changes;
- deprecate context references to removed or renamed objects without erasing
  historical facts;
- leave the context version unchanged when no semantic or verified physical
  change exists.

Expose bounded read APIs/tools for schema-history and context-history views:
feature timeline, object-version detail, schema diff, context-version diff, and
links from every context change to the originating schema version and
investigation. These are read models over immutable records, never a second
source of truth.

## Single-System-Prompt Architecture

Keep one canonical prompt in `deploy/librechat/agents/instrumentation-agent/context.md` with these sections:

1. Role, objective, and non-goals
2. Input contract
3. Tool and source-precedence rules
4. Mandatory discovery and profiling workflow
5. Schema decision rules
6. Base-table ingestion and reconciliation workflow
7. Post-ingestion preview and metric-query workflow
8. Materialized-view decision, backfill, and reconciliation rules
9. Best-practice checklist
10. Validation and execution safety
11. Output contract
12. Investigation persistence and verification contract
13. Analytics Agent handoff contract
14. Failure, uncertainty, and stop conditions
15. Final self-review checklist

Do not maintain a second hand-edited copy of this prompt in `librechat.yaml`. Deployment should inject the canonical file into `promptPrefix`, or fail when the two contents do not hash identically.

## ClickHouse Agent Skills Integration

The official ClickHouse Agent Skills package provides ClickHouse-specific rules for schema design, ingestion, query performance, materialized views, and partitioning in an agent-agnostic format.

Source: [Introducing ClickHouse Agent Skills](https://clickhouse.com/blog/introducing-clickhouse-agent-skills)

The current LibreChat deployment mounts the `agents/` directory but does not expose an Agent Skills runtime. Therefore:

- Pin the skill package version used to develop and evaluate the prompt.
- Distill applicable rule names and decision gates into the single system prompt.
- Require every result to report `rules_checked`.
- Classify recommendations as `official`, `derived`, or `field`.
- Require uncertainty to be stated explicitly.
- Optionally add runtime skill loading later, but do not make the hackathon path depend on automatic skill invocation that is not deployed.
- Track the skill version rather than a hardcoded rule count. The initial article describes 28 rules, while newer versions may contain more.

Example decision record:

```yaml
decision: monthly partitioning
category: derived
confidence: medium
evidence:
  retention_days: 365
  expected_events_per_day: 12000000
rules:
  - schema-partition-lifecycle
  - schema-partition-low-cardinality
validation:
  projected_partitions: 13
  tests:
    - inspect system.parts after a representative load
```

## Agent Output Contract

Each run should return a self-contained, machine-readable payload resembling:

```yaml
schema_version: 1
run:
  prompt_version: instrumentation-agent-v0
  skill_version: clickhouse-best-practices-v0.4.0
  execution_mode: plan
request:
  normalized_feature: {}
evidence:
  source_artifacts: []
  workload_assumptions: []
  query_patterns: []
  data_profile: {}
design:
  event_catalog: []
  topology: {}
  base_tables: []
  mappings: []
  preliminary_metrics: []
  aggregation_queries: []
  mv_candidates: []
  analytical_mv_targets: []
  analytical_materialized_views: []
  retention: {}
ingestion:
  manifest: {}
  status: pending
  source_rows: 0
  inserted_rows: 0
  rejected_rows: 0
  duplicate_rows: 0
  reconciliation_checks: []
post_ingestion_preview:
  profile: {}
  queries: []
  findings: []
analytics_serving:
  metric_registry: []
  preferred_queries: []
  raw_fallback_queries: []
decisions:
  - decision: ""
    category: official
    confidence: high
    evidence: []
    rules: []
    validation: []
ddl:
  base_create: []
  import: []
  analytical_mv_targets: []
  analytical_materialized_views: []
  backfill: []
  reconciliation: []
  rollback: []
validation:
  status: pending
  checks: []
persistence:
  table: default.investigations
  investigation_id: ""
  revision: 0
  artifact_column: instrumentation_result
  hash_column: instrumentation_result_sha256
  artifact_sha256: ""
  persisted_at: ""
  readback_verified: false
rules_checked: []
risks: []
open_items: []
handoff:
  from: instrumentation-agent
  to: analytics-agent
  persisted_investigation_revision: 0
  artifact_sha256: ""
```

Unknown fields from upstream inputs should be preserved. The Analytics Agent should receive the complete payload, not a rewritten summary.

## Generalized Learnings from the Provided Specs

The provided specs are development fixtures, not a schema template. They reveal recurring classes of input and measurement problems that the agent must recognize in any future feature. Do not hardcode their feature names, event names, value sets, identifiers, cardinalities, ranges, or funnel shapes into the system prompt.

### Mandatory Prompt Rules

Add these mandatory rules to the core system prompt:

1. **Profile before narrowing.** Treat sample ranges, lengths, formats, and value sets as observations rather than contracts. Select a narrow or specialized type only when the producer contract and validation data support it.
2. **Separate absent, unknown, and false/zero.** Require a semantic-nullability decision for every optional field. Never collapse an absent property into a valid false, zero, or empty value without documenting that equivalence.
3. **Declare parsing and normalization.** Every DDL proposal must state source type, target type, parsing expression, default/null behavior, invalid-value behavior, timezone, and whether the raw field is retained.
4. **Identify the journey grain.** Before selecting `ORDER BY` or a materialized view, name the identifier that makes one attempt, exposure, visit, transaction, or stateful entity unique.
5. **Never infer attribution from a lossy join.** When repeated actions are possible, joining only on a long-lived parent entity can multiply metrics. Require the narrowest stable correlation identifier to propagate across the sequence.
6. **Distinguish product metrics from causal claims.** If the PM asks whether a treatment lifts conversion or which channel performs best, require assignment, eligibility, control/holdout, and attribution fields. Otherwise label the result observational rather than causal.
7. **Test candidate keys.** Generate an aggregate-query candidate and a journey-query candidate when both are important. Use representative `EXPLAIN indexes = 1` results to choose topology, a key, a projection, or an explicitly justified secondary structure.

### Shared Schema Patterns to Validate

These are candidate patterns, not automatic DDL defaults.

| Concern | Candidate approach | Decision gate |
| --- | --- | --- |
| Raw auditability | Preserve the original event and ingest metadata in a raw landing table or raw payload column; map it into a typed curated table. | Use when type conversion, evolving attributes, replay, or producer debugging is required. |
| Event time | Parse to `DateTime64(3, 'UTC')` only after a timezone decision; use `DateTime` if the product contract confirms second precision is sufficient. | The source format alone does not establish its timezone or required ordering precision. |
| Event type | `LowCardinality(String)` by default. | Use `Enum8` only when the event vocabulary is governed and versioned. |
| Opaque IDs | `String` by default, not a leading ordering-key component. | A fixed/binary type requires an explicit, stable producer encoding contract. |
| Common dimensions | `LowCardinality(String)` for measured low-cardinality values such as platform, country, destination, city, client library, and app version. | Re-profile cardinality per table and release. `FixedString` requires strict width and format guarantees. |
| Money and FX rate | Typed `Decimal(P,S)` with documented currency/unit/scale, or integer minor units. | The source must define denomination and precision. Do not use binary floats for financial quantities. |
| Event-specific fields | Typed columns for recurring, PM-facing dimensions; `JSON` only for unpredictable, long-tail attributes. | Avoid a wide field of unrelated `Nullable` columns when event schemas are truly divergent. |
| Data quality | Add `ingested_at`, producer/schema version, raw event ID, and a quality-status/reason where normalization can fail. | Required when events are transformed or backfilled. |

The optional raw-plus-curated base architecture is **derived** guidance. If selected, it is part of ingestion and normalization, distinct from the later analytical MV layer. Analytical MVs still read from the final generated base event tables and write only to separate aggregate targets. The raw-plus-curated choice must be justified against actual ingest cost and replay requirements. `schema-json-when-to-use` applies only to genuinely variable attributes, not as a substitute for typed analytical columns.

### General Optimization Decisions

| Decision | Recommendation | Category | Confidence | Validation |
| --- | --- | --- | --- | --- |
| Ingest shape | Prefer batched direct inserts when producers can form 10K–100K row batches; otherwise use durable async inserts. | official | high | Measure rows per insert, part count, and insert latency. |
| Raw and curated separation | Retain a replayable raw form before typed normalization when source schemas evolve or transformations can fail. | derived | medium | Re-run mapping from raw input and compare row count, event IDs, and field coverage. |
| Default engine | Use append-only `MergeTree` for raw product telemetry. | derived | high | Verify no in-place update semantics are required. |
| Late state | Derive state from append-only events; use `ReplacingMergeTree` only with genuine replacement/version semantics. | official / derived | high | Test backfills and late events without `ALTER TABLE UPDATE`. |
| Partitioning | Do not select a partition key from the samples. Choose no partitioning for small/uncertain lifecycle needs, or monthly event-time partitions when retention/TTL and production volume justify them. | official / derived | medium | Forecast active partitions and inspect `system.parts` under representative inserts. |
| Ordering key | Derive from the top query corpus and each feature's journey grain; never lead with event ID. | official | high | Compare candidate keys with `EXPLAIN indexes = 1` and bytes/granules read. |
| Materialized views | Decide after full ingestion and bounded raw-query previews; materialize only repeated, defined aggregations after correct grain and attribution are available. | official / derived | high | Backfill existing rows, reconcile to raw queries, and measure dashboard scan reduction. |
| Enrichment | Use a dictionary only for small, stable, unique-key dimensions; otherwise filter before a runtime join or use a justified precomputed view. | official | medium | Check dimension uniqueness, update frequency, and repeated join cost. |

Per `insert-batch-size`, `insert-async-small-batches`, `decision-ingestion-strategy`, `schema-pk-plan-before-creation`, `schema-pk-prioritize-filters`, `schema-partition-lifecycle`, `schema-partition-low-cardinality`, `decision-late-arriving-upserts`, `query-mv-incremental`, and `query-join-consider-alternatives`, the validation named in the final column is mandatory before promoting a recommendation from a proposal to an applied design.

### General Regression Fixtures and Acceptance Tests

Build a reusable test matrix from the patterns discovered in the provided specs, then add synthetic variations. The fixtures belong in the evaluation harness, not in the system prompt. The prompt should contain only the general decision rule each fixture tests.

| Fixture | Required agent behavior |
| --- | --- |
| Opaque identifier that resembles a UUID or integer | Do not infer semantics from appearance; report the contract and validation gate for a specialized type. |
| Timestamp without offset | Stop for or record an explicit timezone assumption before DDL. |
| Null or contradictory envelope attributes | Preserve raw values and unknown state; do not silently infer one attribute from another. |
| Event-specific boolean absent | Preserve not-applicable separately from `false`. |
| Optional numeric field where zero is valid | Do not replace absence with zero unless the two states are contractually equivalent. |
| Nested object with queried properties | Promote stable analytical paths to typed columns and retain dynamic long-tail data according to policy. |
| Repeated child actions under one parent entity | Require an attempt, visit, exposure, or transaction identifier before computing an exact funnel. |
| Monetary amount or rate | Require currency, unit, precision, and scale; reject binary floating-point storage. |
| New categorical value | Prefer an evolvable low-cardinality strategy unless a governed closed vocabulary justifies an enum. |
| Treatment-lift or best-channel question | Require assignment, eligibility, control/holdout, and attribution data before making a causal claim. |
| Late, duplicate, or backfilled event | Preserve event time and ingestion/version metadata; validate append-friendly correction semantics. |
| Aggregate and entity-journey queries on the same data | Compare separate ordering-key candidates and justify any projection or derived table with `EXPLAIN`. |

## Iterative Development Plan

### V0 — Deterministic proposal

- Parse feature specifications and raw samples.
- Produce the event catalog, DDL, mapping SQL, assumptions, and rule checklist.
- Operate in plan-only mode.
- Test against the provided specs plus generalized and synthetic adversarial fixtures.

### V1 — Evidence-driven design

- Add ClickHouse schema discovery.
- Add sample profiling and cardinality, range, and null analysis.
- Generate two candidate ordering keys when evidence is ambiguous.
- Score candidates using representative queries and `EXPLAIN`.

### V2 — Safe execution

- Add sandbox creation, full event-file ingestion, rejected-row handling, mapping validation, source/target reconciliation, and rollback artifacts.
- Introduce `plan`, `sandbox`, and `apply` modes.
- Add `investigations.instrumentation_result`, deterministic artifact hashing, append-only revision persistence, and read-back verification before handoff.
- Trace every tool call, assumption, rule, DDL revision, validation result, and final decision.

### V3 — TTL and materialized-view intelligence

- Add retention-policy modeling.
- Generate a preliminary metric registry from the feature spec.
- Profile the fully ingested tables and execute bounded raw aggregation previews.
- Add incremental versus refreshable materialized-view decisions using observed cardinality, result grain, and reuse evidence.
- Require cost/benefit evidence before creating a materialized view.
- Create target tables, backfill existing rows, attach ongoing MVs, and reconcile against raw reference queries.
- Persist the complete artifact, then hand the exact verified payload with executable preferred and fallback queries to the Analytics Agent.

### V4 — Operational feedback loop

- Capture actual query patterns, bytes read, granules selected, parts, compression, and materialized-view usage.
- Compare predictions with observed behavior.
- Revise the prompt only after running the complete regression suite.

### V5 — Unseen-spec readiness

- Test adversarial specs with missing scale, evolving enumerated values, mixed currencies, sub-second timestamps, late data, and contradictory requirements.
- Freeze and identify the prompt version before the unseen spec arrives.
- Preserve the complete trace and prompt hash proving the schema came from the pipeline.

## Evaluation Scorecard

Use a fixed regression score instead of evaluating responses by feel.

| Area | Weight |
| --- | ---: |
| DDL validity | 15% |
| Type correctness and robustness | 20% |
| Ordering-key justification and pruning | 20% |
| Partition and TTL lifecycle correctness | 15% |
| Mapping completeness and data-quality handling | 10% |
| Materialized-view necessity and correctness | 10% |
| Safety, traceability, and reproducibility | 10% |

## Core Principle

The agent must not jump directly from a feature description to DDL. It must first produce an evidence ledger, then make every schema choice traceable to a workload fact, a named ClickHouse rule, and a concrete validation.
