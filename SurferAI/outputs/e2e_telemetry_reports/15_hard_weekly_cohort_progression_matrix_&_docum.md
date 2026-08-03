# E2E Telemetry & Execution Report — CALL-15-HARD: Weekly Cohort Progression Matrix & Document Retry Distribution

**Difficulty Category:** `Hard`  
**Target Database:** `default` (ClickHouse Cloud)  
**Execution Status:** `✅ SUCCESS`  
**Execution Latency:** `344.98 ms`  
**Timestamp:** `2026-08-02T00:14:36.022349+00:00`  

---

## 1. Langfuse Telemetry & Trace Metadata

| Property | Value |
| :--- | :--- |
| **Trace ID** | `trace-live_run-benchmark_hard_15` |
| **Trace URL** | [https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/7042ef6cf622bc32ae0c85c3c74b3046](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/7042ef6cf622bc32ae0c85c3c74b3046) |
| **Run Mode** | `live_run` |
| **Target Tables** | `destination_card_clicked, application_started, document_uploaded, purchase_completed` |
| **Rows Returned** | `27` |

---

## 2. Business Question & Context

> **Question:**  
> For cohorts grouped by week of destination card click, what is the progression rate to application start, document upload, and purchase, and what are the document retry quantiles?

**Design Rationale:**  
Full 4-table cohort progression model grouping 1M users by calendar week, tracking attrition across all 4 stages with document retry quantiles.

---

## 3. Generated ClickHouse SQL

```sql
SELECT 
    toStartOfWeek(c.timestamp) AS cohort_week,
    count(DISTINCT c.user_id) AS card_clicked_cohort_size,
    count(DISTINCT a.user_id) AS started_application_users,
    count(DISTINCT d.user_id) AS document_uploaded_users,
    count(DISTINCT p.user_id) AS purchase_completed_users,
    round(count(DISTINCT a.user_id) * 100.0 / count(DISTINCT c.user_id), 2) AS click_to_start_conv_pct,
    round(count(DISTINCT p.user_id) * 100.0 / count(DISTINCT c.user_id), 2) AS end_to_end_cohort_conv_pct,
    round(quantilesExact(0.25, 0.5, 0.75, 0.95)(d.retry_count)[2], 1) AS doc_retry_p50,
    round(quantilesExact(0.25, 0.5, 0.75, 0.95)(d.retry_count)[4], 1) AS doc_retry_p95
FROM default.destination_card_clicked c
LEFT JOIN default.application_started a ON c.user_id = a.user_id
LEFT JOIN default.document_uploaded d ON a.application_id = d.application_id
LEFT JOIN default.purchase_completed p ON a.application_id = p.application_id
GROUP BY cohort_week
ORDER BY cohort_week ASC
```

---

## 4. Query Execution Results

**Columns (9):** `cohort_week, card_clicked_cohort_size, started_application_users, document_uploaded_users, purchase_completed_users, click_to_start_conv_pct, end_to_end_cohort_conv_pct, doc_retry_p50, doc_retry_p95`

| cohort_week | card_clicked_cohort_size | started_application_users | document_uploaded_users | purchase_completed_users | click_to_start_conv_pct | end_to_end_cohort_conv_pct | doc_retry_p50 | doc_retry_p95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2025-12-28 | 13650 | 2135 | 297 | 108 | 15.64 | 0.79 | 0 | 2 |
| 2026-01-04 | 30373 | 4672 | 591 | 210 | 15.38 | 0.69 | 0 | 3 |
| 2026-01-11 | 31070 | 4816 | 655 | 250 | 15.5 | 0.8 | 0 | 2 |
| 2026-01-18 | 31853 | 5014 | 656 | 252 | 15.74 | 0.79 | 0 | 3 |
| 2026-01-25 | 32602 | 4954 | 674 | 250 | 15.2 | 0.77 | 0 | 2 |
| 2026-02-01 | 33199 | 5157 | 677 | 237 | 15.53 | 0.71 | 0 | 2 |
| 2026-02-08 | 33880 | 5195 | 729 | 246 | 15.33 | 0.73 | 0 | 2 |
| 2026-02-15 | 34580 | 5418 | 725 | 259 | 15.67 | 0.75 | 0 | 2 |
| 2026-02-22 | 34934 | 5446 | 738 | 261 | 15.59 | 0.75 | 0 | 2 |
| 2026-03-01 | 35666 | 5515 | 726 | 253 | 15.46 | 0.71 | 0 | 2 |

*Showing top 10 of 27 total rows.*

---

## 5. Executive & Analytical Summary

- **Execution Verdict:** Successfully executed without errors against ClickHouse default database.
- **Query Performance:** Returned in **344.98 ms** across ~2.5 million underlying records.
- **Data Integrity:** Schema structure, column types, and foreign key relationships confirmed against `base_context.md`.
- **Trace Persistence:** Telemetry, spans, and metadata flushed to Langfuse Cloud under trace `trace-live_run-benchmark_hard_15`.
