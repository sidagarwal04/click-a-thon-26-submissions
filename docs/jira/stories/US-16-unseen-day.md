# US-16: Benchmark answers with pipeline evidence on unseen data

## The business ask
A sealed evaluation dataset (a fresh day, same schema, ~905K events) is released during the final hours. The benchmark answers count **only if they come from the pipeline** — not from hand-calculating in Excel. How do we prove the answers are pipeline-produced?

## The expectation
The unseen data is ingested **through the same pipeline** (no hand-tuning), the full pipeline runs end-to-end to the serving table, and every benchmark answer ships with query logs/traces as evidence. Answers must match ground truth within tolerance.

## Proof — the required flow

1. **Input:** fresh day of sessions, ~905K events, same schema, released at the announced hour.
2. **Ingest:** `INSERT INTO ch_hackathon_raw FORMAT CSV` → pipeline → serving table — nothing special for this dataset.
3. **Evidence bundle:**
   - Benchmark answers CSV (one answer per question).
   - Each query's `EXPLAIN` / `system.query_log` showing reads **from the serving table** (US-12).
   - Latency per query, e.g., Q1 = **48ms**.

| Evidence | Shows |
|---|---|
| Answers CSV | the numbers |
| `EXPLAIN` / `query_log` | the numbers came from ClickHouse queries, not a spreadsheet |
| Latency | queries hit the serving tier |

### Failure (no credit)
- Answers typed by hand or computed in Excel, with no query log to back them.

## Where it can go wrong
- Hand-tuning queries to the unseen day (the whole point is the same pipeline runs it).
- Losing the query log — the answer is useless without evidence.

## Acceptance Criteria
- Given the unseen dataset released at the announced time
- When I ingest it through the same pipeline (no hand-tuning)
- Then I produce answers to all benchmark queries
- And I provide query logs/traces as evidence
- And the answers match the ground truth within tolerance

## Labels
- `[NOW]` = runs on raw/content CSVs as-is
- `[BUILD]` = runs after building aggregated/serving tables
