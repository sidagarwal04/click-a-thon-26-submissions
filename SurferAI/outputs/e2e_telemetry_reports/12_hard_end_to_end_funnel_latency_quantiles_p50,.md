# E2E Telemetry & Execution Report — CALL-12-HARD: End-to-End Funnel Latency Quantiles (P50, P90, P99) by Device & OS

**Difficulty Category:** `Hard`  
**Target Database:** `default` (ClickHouse Cloud)  
**Execution Status:** `✅ SUCCESS`  
**Execution Latency:** `256.6 ms`  
**Timestamp:** `2026-08-02T00:14:34.290396+00:00`  

---

## 1. Langfuse Telemetry & Trace Metadata

| Property | Value |
| :--- | :--- |
| **Trace ID** | `trace-live_run-benchmark_hard_12` |
| **Trace URL** | [https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/d5df0091c5df634863b103a26c1e20e9](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/d5df0091c5df634863b103a26c1e20e9) |
| **Run Mode** | `live_run` |
| **Target Tables** | `application_started, document_uploaded, purchase_completed` |
| **Rows Returned** | `8` |

---

## 2. Business Question & Context

> **Question:**  
> What is the turnaround duration in seconds between application start to document upload, and document upload to purchase completion, measured at p50, p90, and p99 percentiles?

**Design Rationale:**  
3-table inner join calculating exact temporal differences across pipeline stages with ClickHouse quantilesExact(0.5, 0.9, 0.99) percentile distributions.

---

## 3. Generated ClickHouse SQL

```sql
SELECT 
    a.device_type,
    a.os,
    count() AS completed_funnel_journeys,
    round(quantilesExact(0.5, 0.9, 0.99)(dateDiff('second', a.timestamp, d.timestamp))[1], 1) AS start_to_doc_p50_seconds,
    round(quantilesExact(0.5, 0.9, 0.99)(dateDiff('second', a.timestamp, d.timestamp))[2], 1) AS start_to_doc_p90_seconds,
    round(quantilesExact(0.5, 0.9, 0.99)(dateDiff('second', a.timestamp, d.timestamp))[3], 1) AS start_to_doc_p99_seconds,
    round(quantilesExact(0.5, 0.9, 0.99)(dateDiff('second', d.timestamp, p.timestamp))[1], 1) AS doc_to_purchase_p50_seconds,
    round(quantilesExact(0.5, 0.9, 0.99)(dateDiff('second', d.timestamp, p.timestamp))[2], 1) AS doc_to_purchase_p90_seconds,
    round(quantilesExact(0.5, 0.9, 0.99)(dateDiff('second', d.timestamp, p.timestamp))[3], 1) AS doc_to_purchase_p99_seconds
FROM default.application_started a
JOIN default.document_uploaded d ON a.application_id = d.application_id
JOIN default.purchase_completed p ON a.application_id = p.application_id
WHERE d.timestamp >= a.timestamp AND p.timestamp >= d.timestamp
GROUP BY a.device_type, a.os
ORDER BY completed_funnel_journeys DESC
```

---

## 4. Query Execution Results

**Columns (9):** `a.device_type, a.os, completed_funnel_journeys, start_to_doc_p50_seconds, start_to_doc_p90_seconds, start_to_doc_p99_seconds, doc_to_purchase_p50_seconds, doc_to_purchase_p90_seconds, doc_to_purchase_p99_seconds`

| a.device_type | a.os | completed_funnel_journeys | start_to_doc_p50_seconds | start_to_doc_p90_seconds | start_to_doc_p99_seconds | doc_to_purchase_p50_seconds | doc_to_purchase_p90_seconds | doc_to_purchase_p99_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ios | iOS | 1530 | 3960 | 9180 | 12180 | 3840 | 9300 | 12540 |
| android | Android | 814 | 4080 | 9300 | 11880 | 3900 | 9480 | 12420 |
| web-user-b2c | Windows | 397 | 4320 | 9420 | 12420 | 4200 | 9360 | 12840 |
| web-user-b2c | Mac OS X | 184 | 3300 | 8100 | 11460 | 3660 | 9420 | 12720 |
| Desktop | Windows | 175 | 3960 | 9540 | 12540 | 3660 | 8820 | 12960 |
| android | None | 166 | 4140 | 9180 | 11700 | 4380 | 9060 | 11640 |
| Desktop | Mac OS X | 76 | 3420 | 9120 | 11700 | 4740 | 9600 | 11400 |
| web-user-b2c | Linux | 24 | 3780 | 10440 | 11460 | 4860 | 8580 | 11640 |

---

## 5. Executive & Analytical Summary

- **Execution Verdict:** Successfully executed without errors against ClickHouse default database.
- **Query Performance:** Returned in **256.6 ms** across ~2.5 million underlying records.
- **Data Integrity:** Schema structure, column types, and foreign key relationships confirmed against `base_context.md`.
- **Trace Persistence:** Telemetry, spans, and metadata flushed to Langfuse Cloud under trace `trace-live_run-benchmark_hard_12`.
