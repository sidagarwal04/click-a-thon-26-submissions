---
id: adr-0012
title: Complete Phase 3 as Governed Bring Your Own Data
type: adr
status: active
owner: unassigned
source: decision
created: 2026-08-01
updated: 2026-08-01
reviewed: 2026-08-01
confidence: verified
implementation: planned
priority: critical
tags: [adr, phase-3, data-source, duckdb, cube, query-plan]
related: ["[[Decisions MOC]]", "[[Phase 3 - Governed Bring Your Own Data]]", "[[Data Source Domain]]", "[[Phase 3 Data Execution]]", "[[adr/0016-cube-is-the-single-tenant-scoped-analytical-gateway]]"]
depends_on: ["[[adr/0011-complete-phase-2-as-insight-auditor-and-replay]]", "[[Semantic Modeling]]", "[[Investigation Domain]]"]
repo_path: docs/adr/0012-complete-phase-3-as-governed-bring-your-own-data.md
code_refs:
  - libs/foundation/query-engine/src/types/query.ts
  - libs/foundation/query-engine/src/compiler/sql-compiler.ts
  - libs/domain/agent-execution/src/zentra_domain_agent_execution/ports.py
  - libs/adapters/cube/src/zentra_adapter_cube/semantic.py
---

# Complete Phase 3 as Governed Bring Your Own Data

## Status

Accepted. Implementation has not started; accepting this decision does not mark
Phase 3 complete.

## Context

The numbered roadmap defines Phase 3 as the first real customer-data phase. Its
original milestone assumed one design partner and one warehouse connector. That
remains useful beta evidence, but it cannot be the sole launch path for a solo
founder who has no design partner and intends to launch within one month.

The first public path must let a User upload related CSV or Parquet files, ask a
business question without writing SQL, inspect what the AI employee calculated,
and receive the Phase 2 cited Finding and Replay experience. The product must
also remain capable of adding many Connector Types and Tenant Data Connections
later without coupling Agents to a provider.

The repository already contains a typed JSON `Query`, join and aggregation
specifications, a DuckDB-oriented compiler, and a Semantic Layer Port through
which the SQL Analyst reaches Cube without raw-SQL authority. Phase 3 deepens
those seams rather than creating a separate query stack.

## Decision

Phase 3 delivers **Governed Bring Your Own Data**:

> Bring related data, ask a real question, see the governed calculation, and
> understand through citations and Replay why the Finding was trusted or gated.

Self-service CSV/Parquet is the primary one-month launch path. One public-TLS
PostgreSQL Connector Type is a founder-assisted beta. Both converge on one
immutable Data Source Binding and the existing Investigation trust path.

### One boundary, two source kinds

Every Investigation explicitly selects exactly one source:

1. a Workspace Snapshot containing exact uploaded Relation Versions; or
2. a live Data Connection plus its approved schema fingerprint.

The Data Source Binding also records the Tenant, Semantic Model version, Query
Governance Policy version, safe source/schema fingerprints, and authorization
provenance. The API always requires a source identifier. The UI may preselect
only when exactly one eligible source exists. No source, Relation Version,
connection, model, or policy may switch mid-run, and no silent failover exists.

### Uploaded data is immutable relational data

A Dataset Workspace contains multiple named Relations created from CSV or
Parquet files. Each upload creates an immutable Relation Version. Replacing a
file creates a new version rather than rewriting prior evidence. A Workspace
Snapshot selects the exact Relation Versions available to one Investigation;
cross-workspace joins are deferred.

CSV ingestion detects delimiter, quoting, escape rules, encoding, headers, null
markers, decimal format, dates, and candidate types. Low-confidence detection
requires review. Malformed rows are rejected with a safe report rather than
silently shifted or coerced. The original object remains unchanged. A type
override creates another Relation Version. Parquet retains its embedded schema
but receives the same profiling, classification, and semantic review.

Launch defaults are ten Relations per Workspace, 250 MB per file, 1 GB of
source storage and three active Workspaces per Tenant. These are configurable
operator limits, not billing tiers.

### Semantics are proposed, then governed

Local profiling may create:

- a Column Classification Draft with `standard`, `identifier`, `sensitive`, or
  `restricted` per column;
- a Relationship Draft with join keys, type, cardinality, confidence, and a
  plain-language rationale; and
- a Metric Draft with definition, formula, grain, filters, time behavior, units,
  and source Relations.

The AI may preview a draft, but Tenant approval is required before it enters an
immutable Semantic Model version. Suspected many-to-many joins require an
explicit bridge or a recorded row-multiplication acknowledgment. Identifier and
sensitive columns may support approved local joins and filters but are excluded
from model payloads and ordinary previews by default. Restricted columns cannot
be selected, grouped, displayed, or sent to a model.

Any Finding depending on an unapproved relationship, metric, classification
override, sample-sharing exception, or Advanced SQL Override requires Human
Approval. It cannot publish automatically even if every other Phase 2 condition
passes.

### The AI writes a governed plan, not executable authority

The existing SQL Analyst Agent is extended; Phase 3 does not register another
Query Planner Agent. From the User question and approved Semantic Model it
produces a typed, versioned Governed Query Plan. The visual UI exposes sources,
joins, fields, measures, filters, grouping, ordering, limits, assumptions, and
warnings. The plan is authoritative in Normal Mode.

A deterministic service authorizes and validates the plan, then compiles it for
the selected execution adapter. The SQL Analyst never receives raw-SQL, file,
credential, or warehouse access. The Evaluator validates results and
contradictions, the Insight Agent alone writes the Draft Finding, and the
Orchestrator only delegates and arbitrates.

Every change creates an immutable Query Version. Results and citations remain
bound to the version that produced them. A new version is revalidated and
rerun; it cannot inherit earlier results. User edits take precedence over later
Agent suggestions.

### DuckDB is the upload dialect and executor

DuckDB SQL is the only Advanced Mode dialect for uploaded Workspaces. It is not
promised as universal warehouse SQL. Normal Mode stays portable because the
Governed Query Plan is authoritative.

Advanced Mode permits one read-only relational statement: `SELECT`, or
`WITH ... SELECT`, including DuckDB-supported joins, CTEs, recursive CTEs,
subqueries, set operations, windows, grouping sets, aggregates, expressions,
ordering, and limits. It may reference only Relations in the bound Snapshot.

Policy rejects DDL, DML, multiple statements, `COPY`, `ATTACH`, `DETACH`,
`INSTALL`, `LOAD`, `PRAGMA`, secrets, macros, external scans, arbitrary paths,
network URLs, environment access, and unapproved table functions/extensions.
AST checks and a sandboxed DuckDB connection both enforce this; text matching is
not a security boundary.

If a User edits SQL, the Advanced SQL Override becomes authoritative for that
Query Version and the visual editor becomes read-only. Discarding the override
returns to the last governed plan. Arbitrary SQL is never silently reverse-
converted into the visual plan.

### Execution is bounded but autonomous

After a question, the SQL Analyst may generate, validate, and run multiple
read-only Query Versions inside a visible Investigation budget. Launch defaults
are two concurrent queries per Tenant, one query per worker container, a
60-second timeout, and at most 100,000 aggregate-result cells before a smaller
evidence-safe projection reaches an Agent. Exceeding budget requires approval.
User-edited Advanced SQL always requires an explicit Run action.

The AI asks one focused clarification when plausible interpretations materially
change the answer. Minor assumptions may proceed only when recorded. Join keys,
currency conversion, timezone, business definitions, and causal meaning are
never silently guessed.

Data Quality Observations cover missing values, duplicate candidate keys,
invalid dates, inconsistent categories, outliers, join loss, and row
multiplication. The system does not silently clean source data. A material
observation blocks automatic publication; an approved transformation creates a
new Query or Metric version.

### Server-side DuckDB is authoritative

Authoritative uploaded-data execution runs in one containerized Google Cloud Run
query worker using request billing, minimum instances zero, maximum one
initially, concurrency one, about two vCPU/four GiB memory, and a 60-second
application timeout. It may scale horizontally later without changing its port.

The worker opens only Tenant-authorized objects in the bound Snapshot. Its
filesystem is temporary; networking, extensions, external scans, and side
effects are disabled. Temporary DuckDB state, failed-query scratch, non-evidence
previews, and abandoned upload parts expire within 24 hours. Browser DuckDB may
later accelerate previews but cannot become evidence authority.

Cloudflare R2 Standard stores private uploaded files and governed evidence
behind a narrow S3-compatible port. PostgreSQL stores opaque object references,
safe metadata, and integrity hashes, not payloads. Access uses short-lived
authorization. R2 Data Catalog and R2 SQL are deferred.

### One PostgreSQL connector proves the stable port

The Connector Port owns a versioned descriptor, typed configuration, supported
authorization, metadata discovery, connection validation, safety controls,
rotation/revocation, and Cube binding. It never grants an Agent analytical query
execution. Adding another Connector Type must not change Agents or Investigation.

Phase 3 implements exactly one production Connector Type: public-TLS
PostgreSQL. It uses a dedicated read-only service identity, allowlisted schemas
or views, statement timeout, provider controls, and founder-assisted activation.
Private networking, delegated OAuth, and scheduled synchronization are deferred.

Google Cloud Secret Manager holds credentials behind a Credential Vault Port;
PostgreSQL stores only an opaque reference. Credentials remain server-side and
enter through one-time intake. Rotation is manual but versioned and audited.

Cube remains the live analytical gateway. Signed internal context contains
Tenant, Data Connection, and Semantic Model version. Cube chooses the source
only from verified context. Unknown, suspended, revoked, drifted, or cross-
Tenant bindings fail before querying. Caches are isolated by Tenant, connection,
and model version; persistent pre-aggregations are deferred.

> **Amended by [[adr/0016-cube-is-the-single-tenant-scoped-analytical-gateway]].**
> This paragraph's signed-internal-context mechanism is now implemented —
> `checkAuth`/`contextToAppId` in `infra/cube/cube.js` — and applies
> uniformly to the demo warehouse and live Connector Data Connections, not
> only to a future PostgreSQL connector. This section's intent is unchanged;
> 0016 records how it was built. The DuckDB-for-uploads decision elsewhere
> in this document is untouched.

### Connection state is explicit

A Data Connection has orthogonal state:

- Lifecycle: `provisioning -> ready -> revoked`.
- Activation Stage: authorization, validation, semantic modeling, Tenant
  approval.
- Availability: enabled or suspended.
- Health: unknown, healthy, degraded, or unavailable with typed reasons.

Eligibility is derived from those axes plus active credentials, approved model,
validation, and query policy. Tenant owner/admin initiates and approves scope,
model, and policy. An operator may validate and emergency-suspend but cannot
reactivate alone.

Safe schema fingerprints are checked before each new Investigation. Unrelated
compatible additions may proceed. Changes to referenced tables, columns, types,
keys, or permissions degrade the connection and block new work until a User
remaps and approves a new model.

### Raw data stays out of model and audit payloads

External model context contains safe metadata and locally computed profiles by
default: names, types, null rates, approximate cardinality, ranges, safe
distributions, and hashed key-overlap statistics. Raw rows, direct identifiers,
secrets, and unrestricted free text do not leave the data plane.

A Tenant admin may explicitly enable bounded samples after sensitive columns
are excluded. Consent, payload category, and content hash appear in Replay.
Only minimal validated aggregates reach Agents. ClickHouse remains metadata-
only and never stores endpoints, credentials, object names, query/results
payloads, raw rows, or evidence values.

### Retention and deletion follow dependencies

Source Relation Versions remain until Tenant deletion or account closure.
Superseded versions remain while retained Investigations cite them. Quotas, not
silent expiry, control launch cost.

Deleting an Investigation erases its derived content without deleting shared
Relations. Deleting a Relation Version or Workspace immediately blocks new work
and cascades through dependent profiles, models, results, Findings, derived
values, and evidence content. Investigation identity, lifecycle decisions, safe
execution metadata, and immutable Audit Entries remain. Every affected Evidence
Citation resolves to a Tombstone containing only deletion category and time.

## Launch experience

1. **Upload** related files and inspect Relations, types, and errors.
2. **Review Model** by confirming classifications, relationships, and metrics.
3. **Ask** a natural-language question while execution stays within budget.
4. **Understand** the cited Finding and “How this was calculated” before Replay.

Advanced SQL is an explicit switch inside the calculation view, not a separate
SQL workbench.

## Phase completion

Engineering completion requires automated evidence that:

1. multiple CSV/Parquet Relations import, version, join, query, cite, replay,
   and dependency-delete correctly;
2. SQL policy, read-only execution, quotas, timeouts, cross-Tenant isolation,
   classification, and aggregate-only model egress fail closed;
3. visual and Advanced Mode edits create attributable Query Versions without
   rewriting evidence;
4. provisional semantics and material data-quality observations force approval;
5. PostgreSQL passes Connector Port conformance for scope, suspend, revoke,
   timeout, drift, rotation, and cross-Tenant denial; and
6. one real-data Investigation traverses stable Phase 2 Finding, citation,
   publication, Replay, and Tombstone contracts.

Product validation requires one uncoached target Validation User to upload two
related files, confirm/correct a relationship, ask a real question, inspect the
plan, follow citations, explain publication, and recognize unresolved root
cause. A warehouse partner is not required.

## Parallel delivery

Vocabulary, ports, uploaded-data storage, parsing, profiling, Query Version,
policy, conformance fixtures, and Upload/Review UI may build in parallel with
Phase 2. Integration and completion depend on stable Phase 2 Draft Finding,
Evidence Citation, publication, Replay, and Tombstone contracts. Phase 3 consumes
them and must not fork them.

## Alternatives considered

**Require a warehouse design partner first.** Rejected as the sole public path
because the founder has none; a live connection remains beta evidence.

**Make arbitrary SQL the primary UI.** Rejected because it bypasses semantic
governance and excludes the target user. SQL is compiled output and a last-
resort override.

**Round-trip edited SQL to the visual plan.** Rejected because lossless handling
of CTEs, correlated subqueries, windows, lateral joins, and dialect expressions
is not a credible one-month promise.

**Use PostgreSQL SQL for uploads.** Rejected because DuckDB natively fits
CSV/Parquet analytics. Portability lives in the plan, not one dialect.

**Execute authoritatively in the browser.** Rejected because authorization,
limits, reproducibility, deletion, and artifact integrity belong server-side.

**Build many connectors or a generic private-network/OAuth platform.** Rejected
because it does not produce the first trusted real-data Finding in one month.

**Send raw samples by default or clean data automatically.** Rejected because
both weaken privacy and evidence lineage.

## Explicitly outside Phase 3

- Connectors beyond PostgreSQL and self-service live activation.
- SSH, VPN, VPC peering, PrivateLink, customer agents, or residency deployments.
- Scheduled sync, CDC, incremental ingestion, and writeback.
- Excel, JSON, APIs, Sheets, archives, URLs, and cross-workspace joins.
- Multi-dialect Advanced SQL, ETL, notebooks, dashboards, or a visual SQL IDE.
- Automatic semantic approval, automatic cleaning, or raw-row model access.
- Statistician, causal inference, guaranteed Root Cause Claims, or more Agents.
- Billing plans, connector marketplace, Kubernetes, and persistent Cube
  pre-aggregations.

## Verification

Mutable status and the one-month sequence live in
[[Phase 3 - Governed Bring Your Own Data]]. Vocabulary lives in the
[Data Source context](../../libs/domain/data-source/CONTEXT.md), [Agent Execution
context](../../libs/domain/agent-execution/CONTEXT.md), and [ZentraOS domain
context](../../libs/domain/CONTEXT.md).

Parent: [[Decisions MOC]]
