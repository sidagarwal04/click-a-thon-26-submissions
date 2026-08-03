---
name: clickhouse-best-practices
description: MUST USE when reviewing ClickHouse schemas, queries, or configurations.
  Contains 31 rules that MUST be checked before providing recommendations. Always read
  relevant rule files and cite specific rules in responses.
license: Apache-2.0
metadata:
  author: ClickHouse Inc
  version: "0.4.0"
---

# ClickHouse Best Practices

Vendored from github.com/ClickHouse/agent-skills. Re-sync with `make sync-rules`.

## How to apply

1. Check for applicable rules in this directory
2. If a rule exists: apply it and cite it as "Per `rule-name`..."
3. If no rule exists: use general ClickHouse knowledge
4. Always cite the source: rule name, or "general ClickHouse guidance"

**Why rules take priority:** ClickHouse has specific behaviours (columnar storage,
sparse indexes, merge tree mechanics) where general database intuition is
misleading. The rules encode validated, ClickHouse-specific guidance.

## Schema review order

1. `schema-pk-plan-before-creation` — ORDER BY is immutable
2. `schema-pk-cardinality-order` — column ordering in keys
3. `schema-pk-prioritize-filters` — filter column inclusion
4. `schema-types-native-types` — proper type selection
5. `schema-types-minimize-bitwidth` — numeric type sizing
6. `schema-types-lowcardinality` — LowCardinality usage
7. `schema-types-avoid-nullable` — Nullable vs DEFAULT
8. `schema-partition-low-cardinality` — partition count limits
9. `schema-partition-lifecycle` — partitioning purpose

**Schema checklist:**
- [ ] PRIMARY KEY / ORDER BY column order (low-to-high cardinality)
- [ ] Data types match actual data ranges
- [ ] LowCardinality applied to appropriate string columns
- [ ] Partition key cardinality bounded (100-1,000 values)
- [ ] ReplacingMergeTree has version column if used

## Agent query workflow

Connect → Discover → Plan → Execute → Recover.
Discovery order: databases → tables → columns + comments → sort keys →
skip indexes → sample → EXPLAIN.

## Priority by prefix

| Priority | Category | Impact | Prefix |
|---|---|---|---|
| 1 | Primary Key Selection | CRITICAL | `schema-pk-` |
| 2 | Data Type Selection | CRITICAL | `schema-types-` |
| 3 | JOIN Optimization | CRITICAL | `query-join-` |
| 4 | Insert Batching | CRITICAL | `insert-batch-` |
| 5 | Mutation Avoidance | CRITICAL | `insert-mutation-` |
| 6 | Partitioning Strategy | HIGH | `schema-partition-` |
| 7 | Skipping Indices | HIGH | `query-index-` |
| 8 | Materialized Views | HIGH | `query-mv-` |
| 9 | Async Inserts | HIGH | `insert-async-` |
| 10 | OPTIMIZE Avoidance | HIGH | `insert-optimize-` |
| 11 | JSON Usage | MEDIUM | `schema-json-` |
| 12 | Agent Schema Discovery | CRITICAL | `agent-discovery-` |
| 13 | Agent Query Safety | CRITICAL | `agent-query-` |
| 14 | Agent Connectivity | HIGH | `agent-connect-` |
