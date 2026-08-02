---
name: clickhouse-instrumentation
description: Use this skill to choose and validate ClickHouse schemas, DDL, ingestion, materialized views, and analytical SQL for an instrumentation investigation.
source: ClickHouse Agent Skills (Apache-2.0), adapted as a deployed read-only skill pack
---

# ClickHouse instrumentation skill

This skill provides decision support, not a predetermined schema. Read the
relevant rule file before choosing SQL. The source profile and tracking spec
are the evidence; do not make a recommendation merely because an example in a
rule uses a particular column or engine.

## Rule selection

- Base-table schema: read the `schema-*` rules.
- Ingestion: read `insert-batch-size.md` and `decision-ingestion-strategy.md`.
- Materialized views: read `query-mv-incremental.md`,
  `query-mv-refreshable.md`, and `decision-real-time-preaggregation.md`.
- Querying and validation: read `agent-discovery-schema.md` and
  `agent-query-safety.md`.

For every design choice, add one `decision_trace` object with the rule name,
observed evidence, choice, and a verification query/result. Apply only rules
that fit the evidence; explicitly record when a rule leads to no partition,
no TTL, no MV, or no type coercion.

