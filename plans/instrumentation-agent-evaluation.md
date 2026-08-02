# Instrumentation Agent Static Evaluation and Improvement Plan

## Objective

Build a deterministic evaluation harness that inspects each name-based
Instrumentation Agent output without querying production data. The harness should
reject unsafe or internally inconsistent output, score instrumentation quality,
and produce structured feedback that can improve the single canonical system
prompt through controlled regression-tested revisions. Live schema-performance
checks belong to the downstream resolver that looks up the declared object names.

The evaluator is separate from the Instrumentation Agent. It must not silently
repair object declarations, execute database changes, or rewrite the system prompt
during a production run.

## Workload and Scope

- **Workload:** Product analytics telemetry and feature-event schemas.
- **Evaluated artifact:** The complete structured Instrumentation Agent handoff,
  including evidence, assumptions, event catalog, query patterns, qualified object
  names, mappings, materialized views, retention decisions, validation plan, and
  rules checked. Exact DDL is resolved separately from live metadata.
- **Static means:** Parse and reason over supplied artifacts only. SQL AST parsing is allowed; ClickHouse execution, `EXPLAIN`, sample inserts, and benchmarking are outside the static stage.
- **Primary goal:** Catch bad schemas and weak reasoning before sandbox execution.
- **Secondary goal:** Create stable signals for improving the system prompt without overfitting it to the provided feature specs.

## Static Evaluation Boundary

Static checks can assess:

- Output-contract completeness
- Qualified-object syntax and catalogue cross-reference consistency
- Source-to-target field coverage
- Type choices against supplied profiles and contracts
- Ordering-key alignment with declared query patterns
- Projected partition cardinality and lifecycle alignment
- TTL consistency
- Engine and update-model consistency
- Materialized-view structure and justification
- Deduplication, late-data, and attribution reasoning
- Evidence, confidence, provenance, and assumption quality
- Destructive SQL and secret-leak risks

Static checks cannot prove:

- Query latency or throughput
- Actual rows, parts, granules, or bytes read
- Compression ratio
- Merge pressure under production inserts
- Materialized-view maintenance cost
- Runtime parsing behavior for every ClickHouse version
- Correct index selection by the ClickHouse optimizer

The report must label performance findings as **static proxies**. Runtime claims require the sandbox validation stage defined in the main instrumentation plan.

## Design Principles

1. **Deterministic gates before subjective scoring.** Contract, AST, lineage, safety, and rule violations run before any LLM-based review.
2. **Evidence-aware evaluation.** A choice backed by a producer contract is stronger than one inferred from samples; an explicit assumption is better than an unstated guess.
3. **No single golden DDL.** Multiple ClickHouse designs may be valid. Fixtures should encode invariants, required decisions, and prohibited anti-patterns rather than one exact table definition.
4. **Hard failures cannot be averaged away.** A high total score cannot compensate for destructive SQL, invalid lineage, unsafe money types, unbounded partitioning, or a missing version column on a replacement engine.
5. **Unknown is not failure by default.** If evidence is absent, the evaluator should request evidence, reduce confidence, or mark a check `not_evaluable`; it should not fabricate certainty.
6. **Prompt improvement happens offline.** Changes are proposed from aggregated failures, tested on development and holdout suites, reviewed, versioned, and then promoted.

## Evaluation Architecture

```text
feature spec + samples + discovered context
                    |
                    v
          instrumentation-agent output
                    |
                    v
       contract parser + SQL AST extractor
                    |
          +---------+----------+
          |                    |
          v                    v
 deterministic rules    semantic rubric checks
          |                    |
          +---------+----------+
                    |
                    v
       score + hard gates + repair feedback
                    |
          +---------+----------+
          |                    |
          v                    v
    sandbox candidate    prompt regression corpus
```

## Required Evaluation Inputs

The static evaluator needs more than table names. Require these fields in the agent output:

- Prompt version, skill version, model identifier, and run ID
- Normalized event catalog and source field inventory
- Source type/profile evidence for every proposed column
- Evidence classification: `contract`, `observed`, `discovered`, or `assumed`
- Top query patterns with filters, groupings, time ranges, relative frequency, and latency class
- Expected ingest rate, rows per insert, late-arrival window, and retention horizon, or explicit unknowns
- Table, column, engine, `ORDER BY`, `PRIMARY KEY`, partition, TTL, codec, index, and projection definitions
- Raw-to-curated mapping expressions
- Full-file ingestion manifest with source, accepted, rejected, duplicate, and reconciled row counts
- Post-ingestion preview queries, bounded results, and findings used in later decisions
- Metric registry with grain, numerator, denominator, deduplication, attribution, dimensions, and status
- Raw aggregation/reference SQL plus execution-preview evidence for every non-blocked metric
- Materialized-view generated-base source, dedicated analytical target, select, engine, key, refresh semantics, consumer query, and backfill plan
- Analytics Agent preferred serving query and raw fallback query for each materialized metric
- Investigation persistence receipt containing table, investigation ID, revision, artifact column, content hash, persisted timestamp, and read-back status
- Analytics handoff artifact hash proving it is identical to the persisted instrumentation result
- Deduplication/update semantics and version/sign column where relevant
- Decision records with rule names, provenance, confidence, evidence, alternatives, and planned validation
- Complete qualified object catalogue and rollback decision record

If required evidence is missing, the evaluator must distinguish:

- **Output omission:** The agent had the evidence but failed to include it.
- **Input gap:** The original request did not provide the evidence.
- **Discovery gap:** The agent could have obtained the evidence but did not.

These have different prompt-improvement implications and must not be collapsed into one failure.

## Canonical Evaluation Result

Every evaluator run should emit machine-readable JSON or YAML with this shape:

```yaml
evaluation_schema_version: 1
run:
  evaluation_id: ""
  source_run_id: ""
  prompt_version: ""
  skill_version: ""
  evaluator_version: ""
status: pass | conditional_pass | fail | not_evaluable
hard_gates:
  passed: []
  failed: []
scores:
  total: 0
  contract_and_safety: 0
  schema_correctness: 0
  performance_proxy: 0
  instrumentation_quality: 0
  operability: 0
  evidence_and_traceability: 0
findings:
  - check_id: CH-TYPE-001
    severity: critical | high | medium | low | info
    category: official | derived | field
    confidence: high | medium | heuristic
    status: pass | fail | warn | not_evaluable
    artifact_path: design.tables[0].columns[3]
    rule: schema-types-native-types
    evidence: []
    message: ""
    remediation: ""
    prompt_feedback: ""
coverage:
  checks_run: 0
  checks_not_evaluable: 0
  evidence_coverage_pct: 0
  source_field_coverage_pct: 0
regression:
  baseline_prompt_version: ""
  score_delta: 0
  new_failures: []
  resolved_failures: []
```

## Severity and Gate Policy

| Severity | Meaning | Effect |
| --- | --- | --- |
| Critical | Output is unsafe, invalid, materially incorrect, or cannot support the required metric | Hard fail; do not sandbox or apply |
| High | Strong likelihood of poor performance, incorrect aggregation, or operational failure | Fail unless explicitly waived with evidence |
| Medium | Important optimization, resilience, or explainability weakness | Score penalty and repair feedback |
| Low | Maintainability or minor optimization opportunity | Small score penalty |
| Info | Observation or future validation | No score penalty |

Hard gates include:

- Output cannot be parsed against the contract.
- Generated SQL cannot be parsed into the expected statement types.
- Aggregation SQL or mappings reference undeclared tables, aliases, or
  materialized-view targets.
- Raw fields needed by required metrics are dropped without explanation.
- Full-file ingestion reconciliation does not balance source, accepted, rejected, and intentionally deduplicated rows.
- A monetary amount or rate uses `Float32`/`Float64` without a documented non-financial justification.
- A timestamp is stored as `String`, or a timezone-less source is silently assigned a timezone.
- An identifier is coerced to `UUID`, integer, or fixed-width storage without contract/validation evidence.
- `ORDER BY` begins with a unique/random identifier without a documented dominant point-lookup workload.
- A high-cardinality partition expression is proposed, or projected partitions cannot be bounded for a partitioned table.
- TTL contradicts supplied retention/compliance requirements or is invented when retention is unknown.
- `ReplacingMergeTree` lacks deterministic replacement semantics or an appropriate version column.
- A materialized view references missing objects, lacks its target schema, or is incompatible with its target engine/aggregate states.
- An analytical MV writes into a generated base event table, targets its own source table, or is used as the mechanism that populates the generated base layer.
- An analytical MV does not read from the generated base table layer identified in the same output.
- An incremental materialized view is created after source ingestion without a backfill/cutoff plan and exact-once reconciliation.
- A non-blocked required product metric lacks an executable raw aggregation query.
- The complete instrumentation artifact was not persisted to `default.investigations`, read-back verification failed, or its content hash does not match the Analytics Agent handoff.
- Supplied query patterns contain unapproved destructive statements such as
  `DROP`, `TRUNCATE`, mutation-style corrections, or replacement of existing objects.
- Output contains credentials, SAS tokens, passwords, or other secret-bearing URLs.

## Static Check Catalog

Give every check a stable ID so failures can be tracked across prompt versions.

### 1. Contract and Safety

| Check ID | Check | Severity |
| --- | --- | --- |
| `OUT-001` | Required top-level sections and versions exist | Critical |
| `OUT-002` | Decision records contain evidence, provenance, confidence, and validation | High |
| `OUT-003` | Unknown/open items are explicit and do not masquerade as resolved | High |
| `OUT-004` | Complete instrumentation artifact is persisted in `default.investigations` before handoff | Critical |
| `OUT-005` | Persisted artifact passes read-back and content-hash verification | Critical |
| `OUT-006` | Analytics handoff is byte-for-byte or canonically equivalent to the verified persisted artifact | Critical |
| `SAFE-001` | No destructive SQL outside an explicitly approved migration artifact | Critical |
| `SAFE-002` | No secrets or signed URLs appear in output | Critical |
| `SAFE-003` | Plan/sandbox/apply mode is explicit and consistent with emitted statements | High |
| `SAFE-004` | Persisted artifact and handoff contain no SAS URL, token, credential, or transient secret | Critical |

### 2. SQL Structure and Lineage

| Check ID | Check | Severity |
| --- | --- | --- |
| `SQL-001` | Every SQL statement parses into an allowed ClickHouse AST type | Critical |
| `SQL-002` | Column, expression, alias, table, and target references resolve | Critical |
| `SQL-003` | Mapping outputs match target column names and compatible types | Critical |
| `SQL-004` | Materialized-view target columns and aggregate states match its `SELECT` | Critical |
| `SQL-005` | Object creation order satisfies dependencies | High |
| `SQL-006` | Rollback artifact addresses every newly created object without touching unrelated objects | High |

An offline parser may not understand every ClickHouse release. Parser failures caused by unsupported syntax must be reported as `not_evaluable`, then confirmed with version-matched ClickHouse parsing in the sandbox stage rather than treated automatically as invalid SQL.

### 3. Types and Semantics

Apply `schema-types-native-types`, `schema-types-minimize-bitwidth`, `schema-types-lowcardinality`, `schema-types-enum`, `schema-types-avoid-nullable`, and `schema-json-when-to-use`.

| Check ID | Check | Severity |
| --- | --- | --- |
| `TYPE-001` | Native numeric, date/time, boolean, UUID, decimal, and IP types are used where evidence supports them | High |
| `TYPE-002` | Numeric width covers contractual range and does not rely only on sample min/max | Critical/Medium |
| `TYPE-003` | Money/rates have unit, currency, precision, and non-binary-float representation | Critical |
| `TYPE-004` | `LowCardinality` is supported by measured/projected cardinality | Medium |
| `TYPE-005` | `Enum` has a governed, closed, evolvable contract | High |
| `TYPE-006` | Each `Nullable` or default value preserves absent/unknown/zero/false semantics | High |
| `TYPE-007` | Known analytical JSON paths are typed; dynamic paths are not unnecessarily flattened | Medium |
| `TYPE-008` | Timestamp precision and timezone match the event contract | Critical/High |
| `TYPE-009` | Specialized identifier types are supported by semantic and format evidence | Critical/High |

### 4. Ordering-Key Performance Proxy

Apply `schema-pk-plan-before-creation`, `schema-pk-prioritize-filters`, `schema-pk-cardinality-order`, and `schema-pk-filter-on-orderby`.

The evaluator should compute a query/key alignment proxy from the declared query corpus:

```text
alignment(query, key) =
  1.0  equality filters cover a useful key prefix and an optional range follows
  0.7  a useful partial prefix is covered
  0.3  only a weak or late key expression can be used
  0.0  no usable key prefix is present

weighted_key_coverage = sum(query_weight * alignment) / sum(evaluable_query_weight)
```

The exact alignment coefficients are evaluator policy, not ClickHouse guarantees. Version and calibrate them against later runtime results.

| Check ID | Check | Severity |
| --- | --- | --- |
| `KEY-001` | Top query patterns were documented before key selection | Critical |
| `KEY-002` | Frequently selective filters appear in a useful key prefix | High |
| `KEY-003` | Key expressions generally progress low-to-high cardinality after query utility is considered | High |
| `KEY-004` | Random/unique identifier is not the unjustified leading expression | Critical |
| `KEY-005` | Key remains concise or extra expressions have measured justification | Medium |
| `KEY-006` | Aggregate and entity-journey workloads were compared when they conflict | High |
| `KEY-007` | Proposed validation includes representative `EXPLAIN indexes = 1` queries | High |

Report `weighted_key_coverage` only when query weights and filter structure are present. Otherwise mark it `not_evaluable` and penalize evidence coverage, not the schema itself.

### 5. Partition and TTL Performance Proxy

Apply `schema-partition-low-cardinality`, `schema-partition-lifecycle`, `schema-partition-query-tradeoffs`, `schema-partition-start-without`, and `decision-partitioning-timeseries`.

Statically derive when inputs permit:

- Projected active partition count over the retention horizon
- Maximum partition values touched by one insert batch
- Whether inserts are likely to fan out across many partitions
- Whether common queries constrain the partition expression
- Whether TTL boundaries and partition boundaries are compatible
- Whether raw and aggregate tables have intentional, separate retention

| Check ID | Check | Severity |
| --- | --- | --- |
| `PART-001` | Partitioning has an explicit lifecycle/access-pattern justification | High |
| `PART-002` | Projected distinct partition values remain bounded; above 1,000 is critical and 100–1,000 requires explicit justification | Critical/High |
| `PART-003` | Partition key does not use a high-cardinality entity identifier | Critical |
| `PART-004` | No-partition design is considered when lifecycle evidence is absent | Medium |
| `PART-005` | Query-spanning and insert-fan-out trade-offs are acknowledged | Medium |
| `TTL-001` | TTL is sourced from a stated retention policy | Critical |
| `TTL-002` | TTL column/type/expression is structurally valid and uses the intended clock | High |
| `TTL-003` | Late-arrival/backfill window is compatible with TTL | High |

### 6. Engine, Ingestion, and Mutation Risk

Apply `decision-late-arriving-upserts`, `insert-mutation-avoid-update`, `insert-mutation-avoid-delete`, `insert-batch-size`, and `insert-async-small-batches`.

| Check ID | Check | Severity |
| --- | --- | --- |
| `ENG-001` | Engine matches append, replacement, collapsing, or aggregation semantics | Critical |
| `ENG-002` | Replacement/collapse version or sign columns exist and participate in a deterministic identity | Critical |
| `ENG-003` | Late and duplicate events have an explicit policy | High |
| `ING-001` | Insert recommendation uses known producer shape instead of a universal default | High |
| `ING-002` | Direct-insert guidance targets healthy batches; async inserts retain durability acknowledgement | High |
| `ING-003` | Proposed partitioning does not create obvious parts fan-out per batch | High |
| `MUT-001` | Event-state changes are not implemented as frequent heavy mutations | Critical |

### 7. Aggregation Queries and Metric Registry

These checks ensure the Analytics Agent receives usable queries even when no MV is justified.

| Check ID | Check | Severity |
| --- | --- | --- |
| `AGG-001` | Every non-blocked metric has an executable raw reference query against generated base tables | Critical |
| `AGG-002` | Metric grain, numerator, denominator, deduplication, time window, and dimensions are explicit | Critical |
| `AGG-003` | Query columns and filters resolve to the declared base or analytical target schema | Critical |
| `AGG-004` | Post-ingestion preview evidence supports the query and its result cardinality | High |
| `AGG-005` | Preview and serving SQL contains appropriate time, scan, result, and execution limits | High |
| `AGG-006` | Joins are filtered first and cannot multiply the intended metric grain | Critical |
| `AGG-007` | Blocked metrics state the missing instrumentation rather than emitting misleading SQL | High |
| `AGG-008` | An MV-backed metric includes both the preferred target-table query and equivalent raw fallback | High |

### 8. Materialized Views and Derived Models

Apply `decision-real-time-preaggregation`, `query-mv-incremental`, and `query-mv-refreshable`.

| Check ID | Check | Severity |
| --- | --- | --- |
| `MV-001` | Every MV has a named repeated consumer query and expected benefit | High |
| `MV-001A` | Every analytical MV reads from the generated base layer and writes to a separate dedicated analytics target | Critical |
| `MV-002` | Incremental versus refreshable semantics match freshness and transformation complexity | Critical/High |
| `MV-003` | Incremental MV accounts for insert-block semantics, late data, and separate backfill | Critical |
| `MV-004` | Target engine/key and `-State`/`-Merge` functions are consistent | Critical |
| `MV-005` | Join multiplicity cannot silently inflate aggregates | Critical |
| `MV-006` | Raw-table fallback and reconciliation query are present | High |
| `MV-007` | No speculative MV is created for an unproven query pattern | Medium |
| `MV-008` | Complex multi-base-table logic does not rely on incorrect incremental trigger semantics | Critical/High |

### 9. Instrumentation and Analytical Quality

These are mostly **derived** checks: they follow from whether the proposed schema can answer its stated product questions correctly.

| Check ID | Check | Severity |
| --- | --- | --- |
| `QUAL-001` | Every required metric maps to observable events and fields | Critical |
| `QUAL-002` | Event grain and metric denominator are explicit | Critical |
| `QUAL-003` | Repeated actions have an attempt/exposure/visit/transaction correlation key | High |
| `QUAL-004` | Attribution window and propagation fields exist where conversion crosses systems/events | High |
| `QUAL-005` | Treatment-lift claims have eligibility, assignment, control/holdout, and outcome instrumentation | Critical |
| `QUAL-006` | Failure, cancellation, and terminal-success states are distinguishable | High |
| `QUAL-007` | Source fields are mapped, deliberately retained as dynamic data, or explicitly rejected | High |
| `QUAL-008` | Schema/event version and ingestion metadata support evolution and replay | High |
| `QUAL-009` | Privacy-sensitive identifiers and payload fields have an explicit handling decision | High |

## Scoring Model

Hard gates determine eligibility; the weighted score ranks eligible outputs and detects regressions.

| Dimension | Weight |
| --- | ---: |
| Contract and safety | 10% |
| Schema correctness | 25% |
| Static performance proxy | 25% |
| Instrumentation and analytical quality | 20% |
| Operability and evolution | 10% |
| Evidence and traceability | 10% |

Suggested scoring behavior:

- Start each dimension at 100.
- Deduct 25 for each high finding, 10 for medium, and 3 for low, capped at zero.
- Critical findings fail the run instead of deducting points.
- Checks marked `not_evaluable` do not count as failures, but reduce evidence coverage.
- Cap the total score at 79 when evidence coverage is below 80%.
- Cap the total score at 69 when any dimension is below 60.
- Never compare scores across evaluator-rule versions without recording both versions.

Initial promotion thresholds:

- Zero critical findings
- Zero unwaived high safety/correctness findings
- Total score at least 85
- Every dimension at least 70
- Source-field and required-metric coverage at least 95%
- Evidence coverage at least 85%

These thresholds are **field** guidance and should be calibrated after enough outputs have both static scores and sandbox/runtime results.

## Static Performance Proxy Details

The performance score should be evidence-based and decomposable rather than a single opaque LLM judgment.

### Key alignment

- Weighted coverage of representative query filters against the key prefix
- Penalty for leading unique/random IDs without dominant point lookups
- Penalty for skipping frequently filtered/selective columns
- Penalty for key expressions unsupported by profile or query evidence
- Credit for explicitly comparing conflicting aggregate and entity-journey layouts

### Partition health

- Projected partition count over retention
- Estimated partitions created per batch
- Whether partitioning exists mainly for lifecycle management
- Expected proportion of queries that can constrain the partition key
- TTL/partition boundary compatibility

### Storage efficiency

- Native type coverage
- Width/range fit with contractual headroom
- Evidence-backed `LowCardinality` coverage
- Unnecessary `Nullable`, `String`, `DateTime64`, and JSON usage
- Financial precision correctness

### Insert and merge risk

- Expected rows per insert
- Direct versus async insert choice
- Partition fan-out per insert
- Use of append-friendly event corrections
- Obvious dependence on frequent mutations or `OPTIMIZE FINAL`

### Derived-model value

- Static estimate of repeated raw scans avoided
- Aggregate-state/target consistency
- Number and width of grouping dimensions
- Backfill and late-data correctness
- Data duplication justified by a named workload

Do not convert these proxies into claims such as “4x faster.” The report should say what risk is reduced and which sandbox metric must confirm it.

## Evaluation Corpus

### Corpus tiers

1. **Development fixtures:** The provided specs and samples. Use them to discover general failure patterns, not to encode exact DDL.
2. **Mutation fixtures:** Deterministic changes to formats, nullability, value ranges, cardinality, event ordering, repeated actions, and missing context.
3. **Synthetic adversarial fixtures:** New domains and naming with the same underlying reasoning challenges.
4. **Holdout fixtures:** Never included in prompt-writing context. Use only for promotion decisions.
5. **Runtime correlation set:** Outputs later validated in a sandbox, used to calibrate static performance proxies.

### Required metamorphic tests

The output should remain structurally equivalent, or change only in an explainable way, when:

- Feature and field names are renamed while semantics remain the same.
- Input rows and object-key order are shuffled.
- Exact duplicate samples are added.
- An irrelevant unused property is added.
- Sample volume changes without changing the producer contract.
- A new valid categorical value appears.
- A numeric outlier remains inside the contractual range.

The output should change predictably when:

- A source contract changes from opaque string to validated UUID.
- Timestamp precision or timezone requirements change.
- A value set becomes governed and closed.
- Retention changes enough to alter projected partition count.
- Dominant query filters change.
- Repeated child actions make a parent-only join ambiguous.
- An append-only event becomes genuine replacement state with a version.

### Assertions, not golden schemas

Each fixture should define:

- Required decisions
- Prohibited anti-patterns
- Required questions or assumptions
- Acceptable design families
- Fields/metrics that must be covered
- Expected severity for known gaps

Avoid storing one exact schema as the oracle. Compare declared relationships and
semantic invariants; resolve physical schema separately from live metadata.

## Optional Semantic Judge

Use an LLM judge only for qualities that deterministic rules cannot reliably assess, such as whether assumptions are clear, alternatives are genuinely compared, or a justification follows from the evidence.

Guardrails:

- Deterministic checks remain authoritative for hard gates.
- Judge receives the rubric, input evidence, and parsed output, not hidden expected prose.
- Evaluate blind to prompt-version identity.
- Prefer pairwise baseline-versus-challenger review for prompt promotion.
- Require cited artifact paths and evidence for every judgment.
- Track disagreement and do not treat one judge score as ground truth.
- Never let the judge waive a deterministic critical finding.

## Per-Run Repair Loop

Static evaluation may support a bounded repair cycle before sandboxing:

1. Preserve the original output and trace.
2. Run deterministic checks.
3. Return only structured findings and missing-evidence requests to the same agent.
4. Allow at most two repair attempts.
5. Re-run the complete suite after each repair, not only failed checks.
6. Preserve all revisions and score deltas.
7. Stop on repeated critical failure or when repair requires new user/business input.

The evaluator must not supply a replacement schema. It should state the violated invariant, evidence, and required decision so the Instrumentation Agent performs the correction.

## Prompt Improvement Loop

The production agent must not self-modify its system prompt. Prompt improvement is an offline release process:

1. **Baseline:** Run the current prompt version multiple times over the frozen development, mutation, and holdout manifests with fixed model settings.
2. **Aggregate:** Group findings by stable check ID, root cause, severity, and input-gap type.
3. **Prioritize:** Select recurring failures or critical blind spots; do not change the prompt for isolated stylistic preferences.
4. **Generalize:** Write the smallest domain-independent prompt rule that addresses the root cause. Never paste fixture-specific event names, values, or desired DDL into the prompt.
5. **Challenge:** Create or expand a fixture that exposes the general failure before editing the prompt.
6. **Revise:** Produce one versioned prompt delta with a stated hypothesis.
7. **Regress:** Run baseline and challenger across all suites, including untouched holdouts and metamorphic variants.
8. **Compare:** Review hard gates, dimension scores, evidence coverage, output stability, token cost, and latency.
9. **Promote:** Require thresholds below and a human-reviewed prompt diff.
10. **Record:** Store prompt hash, skill/evaluator versions, suite manifest, model settings, results, and rationale.

### Promotion criteria

- No new critical or high findings on any fixture.
- Targeted check IDs improve on development and at least one non-development fixture.
- No dimension regresses by more than two points suite-wide.
- Holdout total does not regress.
- Metamorphic stability stays equal or improves.
- Output-contract validity is 100% across repeated runs.
- Average output size/token use does not grow materially without justified quality gain.
- Human review confirms the prompt rule is general and does not leak fixture answers.

Reject a challenger even when its average score improves if it introduces a critical failure, hides uncertainty, or overfits the development fixtures.

## Versioning and Reproducibility

Version independently:

- System prompt
- Agent output schema
- ClickHouse Agent Skills snapshot
- Static check catalog
- Scoring weights and thresholds
- SQL parser and target ClickHouse version
- Fixture manifest and fixture content hashes
- Optional judge prompt/model

Every score must be reproducible from immutable inputs. Store the raw agent output, parsed intermediate representation, findings, score, and evaluator logs. Never store blob SAS URLs or other transient credentials in evaluation artifacts.

## Suggested Repository Layout

```text
evals/instrumentation-agent/
  README.md
  schemas/
    agent-output.schema.json
    evaluation-result.schema.json
  rules/
    checks.yaml
  fixtures/
    development/
    mutations/
    adversarial/
    holdout/
  assertions/
  reports/
  prompt-versions/
```

The fixtures and reports remain outside the single system prompt. Only generalized lessons that survive regression testing are promoted into `deploy/librechat/agents/instrumentation-agent/context.md`.

## Implementation Phases

### Phase 0 — Contract and hard gates

- Freeze the agent-output schema.
- Validate required sections and decision provenance.
- Add secret scanning and destructive-SQL checks.
- Validate investigation persistence receipts, read-back status, and persisted-versus-handoff content hashes.
- Emit stable check IDs and machine-readable results.

### Phase 1 — AST and lineage

- Parse aggregation SQL, mappings, and materialized-view object references.
- Build an object dependency graph from declared names.
- Validate mapping coverage and target references; defer physical compatibility
  to the live schema resolver.

### Phase 2 — ClickHouse best-practice rules

- Implement deterministic type, ordering-key, partition, engine, mutation, and MV checks.
- Attach official rule names and documentation links to findings.
- Add evidence coverage and `not_evaluable` handling.

### Phase 3 — Performance proxies

- Parse the structured query corpus.
- Compute weighted key coverage and partition projections.
- Score type/storage, insert/parts, and derived-model risks.
- Correlate proxies with later sandbox results before tightening thresholds.

### Phase 4 — Quality and adversarial suite

- Add metric observability, grain, attribution, causal-claim, evolution, and privacy checks.
- Generate mutation and metamorphic fixtures.
- Establish untouched holdouts.

### Phase 5 — Prompt optimization pipeline

- Produce baseline-versus-challenger reports.
- Add bounded per-run repair feedback.
- Automate promotion gates while retaining human prompt-diff approval.
- Track quality, stability, token cost, and evaluator drift over time.

## Rules and Sources

The static evaluator should cite the exact applicable rule in every finding. Core rules include:

- `schema-pk-plan-before-creation`
- `schema-pk-cardinality-order`
- `schema-pk-prioritize-filters`
- `schema-pk-filter-on-orderby`
- `schema-types-native-types`
- `schema-types-minimize-bitwidth`
- `schema-types-lowcardinality`
- `schema-types-enum`
- `schema-types-avoid-nullable`
- `schema-json-when-to-use`
- `schema-partition-low-cardinality`
- `schema-partition-lifecycle`
- `schema-partition-query-tradeoffs`
- `schema-partition-start-without`
- `insert-batch-size`
- `insert-async-small-batches`
- `insert-mutation-avoid-update`
- `insert-mutation-avoid-delete`
- `query-mv-incremental`
- `query-mv-refreshable`
- `decision-real-time-preaggregation`
- `decision-partitioning-timeseries`
- `decision-late-arriving-upserts`

Official documentation:

- [Choosing a primary key](https://clickhouse.com/docs/best-practices/choosing-a-primary-key)
- [Selecting data types](https://clickhouse.com/docs/best-practices/select-data-types)
- [Choosing a partitioning key](https://clickhouse.com/docs/best-practices/choosing-a-partitioning-key)
- [Selecting an insert strategy](https://clickhouse.com/docs/best-practices/selecting-an-insert-strategy)
- [Incremental materialized views](https://clickhouse.com/docs/materialized-view/incremental-materialized-view)
- [Refreshable materialized views](https://clickhouse.com/docs/materialized-view/refreshable-materialized-view)
- [ReplacingMergeTree](https://clickhouse.com/docs/en/guides/replacing-merge-tree)

## Success Criteria

The evaluation system is successful when it:

- Rejects unsafe or semantically invalid output before sandbox execution.
- Explains every finding with a stable check ID, evidence path, rule, and remediation.
- Distinguishes agent error from missing input and missing discovery.
- Produces performance-risk signals that correlate with later ClickHouse measurements.
- Improves holdout quality across prompt versions without fixture-specific prompt rules.
- Makes every prompt promotion reproducible from versioned artifacts and traces.
