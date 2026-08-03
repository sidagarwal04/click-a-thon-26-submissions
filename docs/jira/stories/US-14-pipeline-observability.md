# US-14: Pipeline observability (integration requirement)

## The business ask
The hackathon requires integrating at least one of **ClickStack / Langfuse / LibreChat** meaningfully. "Meaningful" means it surfaces real signals about the running pipeline — not a decorative panel. How do we prove it works?

## The expectation
The integrated tool shows **real, live signals**: ingestion lag, query latency percentiles, or conversational answers backed by real queries against ClickHouse. Superficial static content does not count.

## Proof — two real integrations

**ClickStack (observability dashboard):**

| Signal | Value | SLA |
|---|---|---|
| Max ingestion lag | 42s | 60s |
| Query latency p95 | 85ms | — |

→ Live numbers drawn from `system.query_log` / pipeline metrics, not hardcoded.

**LibreChat + ClickHouse MCP (conversational):**

- User asks: *"What was peak concurrency on Android in the last hour?"*
- Answer: `412,318 at 19:45`, produced by a **real query** executed against ClickHouse, with the query log visible as evidence.

### Anti-example (fails the requirement)
- A static chart with no live query behind it.
- A chat that answers from hardcoded text instead of a real query.

## Where it can go wrong
- Picking the integration last minute and wiring only a placeholder.
- Showing dashboards that don't update or queries that never actually run.

## Acceptance Criteria
- Given the integrated tool
- When the pipeline runs
- Then it surfaces real signals (e.g., ingestion lag, query latency, or "peak concurrency on Android in the last hour")
- And the integration is functional, not superficial

## Labels
- `[NOW]` = runs on raw/content CSVs as-is
- `[BUILD]` = runs after building aggregated/serving tables
