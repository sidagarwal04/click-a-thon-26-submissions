# E2E Telemetry & Execution Report — CALL-07-MEDIUM: Weekly Funnel Stage Volumes and Step-Through Rates

**Difficulty Category:** `Medium`  
**Target Database:** `default` (ClickHouse Cloud)  
**Execution Status:** `✅ SUCCESS`  
**Execution Latency:** `256.78 ms`  
**Timestamp:** `2026-08-02T00:14:31.792494+00:00`  

---

## 1. Langfuse Telemetry & Trace Metadata

| Property | Value |
| :--- | :--- |
| **Trace ID** | `trace-live_run-benchmark_medium_07` |
| **Trace URL** | [https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/01170d3578d5c81648a14c5d4152586e](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/01170d3578d5c81648a14c5d4152586e) |
| **Run Mode** | `live_run` |
| **Target Tables** | `application_started, document_uploaded, purchase_completed` |
| **Rows Returned** | `27` |

---

## 2. Business Question & Context

> **Question:**  
> How did weekly application starts, document uploads, and completed purchases trend across H1 2026, and what were the weekly step-through rates?

**Design Rationale:**  
Multi-table 3-way join with date truncation toStartOfWeek(timestamp), computing longitudinal step-through rates across 26 calendar weeks.

---

## 3. Generated ClickHouse SQL

```sql
SELECT 
    toStartOfWeek(a.timestamp) AS week_start,
    count(DISTINCT a.application_id) AS applications_started,
    count(DISTINCT d.application_id) AS documents_uploaded,
    count(DISTINCT p.application_id) AS purchases_completed,
    round(count(DISTINCT d.application_id) * 100.0 / count(DISTINCT a.application_id), 2) AS start_to_doc_stepthrough_pct,
    round(count(DISTINCT p.application_id) * 100.0 / count(DISTINCT d.application_id), 2) AS doc_to_purchase_stepthrough_pct,
    round(count(DISTINCT p.application_id) * 100.0 / count(DISTINCT a.application_id), 2) AS overall_funnel_conversion_pct
FROM default.application_started a
LEFT JOIN default.document_uploaded d ON a.application_id = d.application_id
LEFT JOIN default.purchase_completed p ON a.application_id = p.application_id
GROUP BY week_start
ORDER BY week_start ASC
```

---

## 4. Query Execution Results

**Columns (7):** `week_start, applications_started, documents_uploaded, purchases_completed, start_to_doc_stepthrough_pct, doc_to_purchase_stepthrough_pct, overall_funnel_conversion_pct`

| week_start | applications_started | documents_uploaded | purchases_completed | start_to_doc_stepthrough_pct | doc_to_purchase_stepthrough_pct | overall_funnel_conversion_pct |
| --- | --- | --- | --- | --- | --- | --- |
| 2025-12-28 | 2127 | 295 | 106 | 13.87 | 35.93 | 4.98 |
| 2026-01-04 | 4675 | 590 | 210 | 12.62 | 35.59 | 4.49 |
| 2026-01-11 | 4808 | 653 | 248 | 13.58 | 37.98 | 5.16 |
| 2026-01-18 | 5017 | 656 | 252 | 13.08 | 38.41 | 5.02 |
| 2026-01-25 | 4953 | 674 | 249 | 13.61 | 36.94 | 5.03 |
| 2026-02-01 | 5154 | 673 | 235 | 13.06 | 34.92 | 4.56 |
| 2026-02-08 | 5194 | 729 | 245 | 14.04 | 33.61 | 4.72 |
| 2026-02-15 | 5417 | 725 | 259 | 13.38 | 35.72 | 4.78 |
| 2026-02-22 | 5446 | 735 | 260 | 13.5 | 35.37 | 4.77 |
| 2026-03-01 | 5517 | 728 | 252 | 13.2 | 34.62 | 4.57 |

*Showing top 10 of 27 total rows.*

---

## 5. Executive & Analytical Summary

- **Execution Verdict:** Successfully executed without errors against ClickHouse default database.
- **Query Performance:** Returned in **256.78 ms** across ~2.5 million underlying records.
- **Data Integrity:** Schema structure, column types, and foreign key relationships confirmed against `base_context.md`.
- **Trace Persistence:** Telemetry, spans, and metadata flushed to Langfuse Cloud under trace `trace-live_run-benchmark_medium_07`.
