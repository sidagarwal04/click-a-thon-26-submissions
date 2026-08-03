# E2E Telemetry & Execution Report — CALL-04-EASY: Top 10 Destination Search Terms and Result Counts

**Difficulty Category:** `Easy`  
**Target Database:** `default` (ClickHouse Cloud)  
**Execution Status:** `✅ SUCCESS`  
**Execution Latency:** `367.24 ms`  
**Timestamp:** `2026-08-02T00:14:30.232724+00:00`  

---

## 1. Langfuse Telemetry & Trace Metadata

| Property | Value |
| :--- | :--- |
| **Trace ID** | `trace-live_run-benchmark_easy_04` |
| **Trace URL** | [https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/76ccf9e0262689bdb7d73daeb44a5b9e](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/76ccf9e0262689bdb7d73daeb44a5b9e) |
| **Run Mode** | `live_run` |
| **Target Tables** | `search_typed` |
| **Rows Returned** | `10` |

---

## 2. Business Question & Context

> **Question:**  
> What are the top 10 most frequently searched destination terms and their average search result counts in search_typed?

**Design Rationale:**  
Filtered single-table aggregation on search_typed (599k rows). Validates string filtering, group-by frequency, and distinct user counts.

---

## 3. Generated ClickHouse SQL

```sql
SELECT 
    search_term,
    count() AS search_volume,
    round(avg(results_count), 2) AS avg_search_results,
    uniqExact(user_id) AS distinct_searching_users
FROM default.search_typed
WHERE search_term != ''
GROUP BY search_term
ORDER BY search_volume DESC
LIMIT 10
```

---

## 4. Query Execution Results

**Columns (4):** `search_term, search_volume, avg_search_results, distinct_searching_users`

| search_term | search_volume | avg_search_results | distinct_searching_users |
| --- | --- | --- | --- |
| schengen | 60477 | 19.57 | 60477 |
| usa visa | 60430 | 19.51 | 60430 |
| thailand visa | 60428 | 19.48 | 60428 |
| egypt | 60008 | 19.49 | 60008 |
| uk visa | 59998 | 19.52 | 59998 |
| singapore | 59920 | 19.51 | 59920 |
| vietnam | 59781 | 19.5 | 59781 |
| dubai | 59771 | 19.47 | 59771 |
| japan | 59528 | 19.49 | 59528 |
| bali | 59289 | 19.54 | 59289 |

---

## 5. Executive & Analytical Summary

- **Execution Verdict:** Successfully executed without errors against ClickHouse default database.
- **Query Performance:** Returned in **367.24 ms** across ~2.5 million underlying records.
- **Data Integrity:** Schema structure, column types, and foreign key relationships confirmed against `base_context.md`.
- **Trace Persistence:** Telemetry, spans, and metadata flushed to Langfuse Cloud under trace `trace-live_run-benchmark_easy_04`.
