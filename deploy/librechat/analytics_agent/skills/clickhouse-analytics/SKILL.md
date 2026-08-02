---
name: clickhouse-analytics
description: Required ClickHouse discovery, query-safety, and join discipline for every Atlys analytics role.
---

# ClickHouse Analytics

Use the private `run_analytics` runner only. It is the enforcement boundary for
ClickHouse access; this skill tells you how to plan and review its calls.

1. Per `agent-discovery-schema`, call `discover` for every allowlisted source
   before generating analytical SQL. Inspect columns/comments, engines, sort and
   partition keys, sizes, and skipping indexes. Never assume a table, column,
   discriminator, key, unit, or relationship from its name.
2. Per `agent-query-safety`, submit only fully qualified, bounded aggregate SQL:
   one `SELECT` or `WITH ... SELECT`, an evidenced time or canonical-run boundary,
   explicit projected columns, a final `LIMIT <= 500`, and the runner's scan,
   byte, result, and execution limits. Never request `SELECT *`, raw rows,
   identities, payloads, or unbounded arrays.
3. Per `query-join-filter-before`, filter each physical source inside its own CTE
   and aggregate each event/source to the common approved grain before joining.
   A source-local inner identity may support a journey calculation only when its
   semantics are evidenced and the outer query immediately aggregates it away.
4. Treat query success as syntactic evidence, not semantic proof. Validate event
   discriminators, numerator/denominator, deduplication, grain, window, units,
   currency, and baseline comparability from the feature spec, discovered live
   schema/comments, current ClickHouse business context, and bounded aggregates.
5. Start with consolidated low-cardinality counts/rates, then add only the
   dimensions or statistics needed for the PM question and complete evaluation.
   On timeout or memory failure, narrow once before recording `query_failure`.

These are official ClickHouse rules for discovery and query limits, plus a
derived workload rule to pre-aggregate independent event tables before joins.
