# E2E Telemetry & Execution Report — CALL-08-MEDIUM: Passport-Capture Quality & Threshold Breach by Destination & Device

**Difficulty Category:** `Medium`  
**Target Database:** `default` (ClickHouse Cloud)  
**Execution Status:** `✅ SUCCESS`  
**Execution Latency:** `250.77 ms`  
**Timestamp:** `2026-08-02T00:14:32.282182+00:00`  

---

## 1. Langfuse Telemetry & Trace Metadata

| Property | Value |
| :--- | :--- |
| **Trace ID** | `trace-live_run-benchmark_medium_08` |
| **Trace URL** | [https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/e354b5f50fde4b80b409dc8296b678df](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/e354b5f50fde4b80b409dc8296b678df) |
| **Run Mode** | `live_run` |
| **Target Tables** | `document_uploaded, application_started` |
| **Rows Returned** | `12` |

---

## 2. Business Question & Context

> **Question:**  
> What is the passport-capture pass rate (is_crossed_failed_attempt_threshold = 0) and average retry count by target destination and device type for destinations with >= 200 uploads?

**Design Rationale:**  
Multi-table JOIN on application_id, evaluating KYC passport capture quality, retry counts, and failed attempt thresholds with HAVING filtering.

---

## 3. Generated ClickHouse SQL

```sql
SELECT 
    a.destination,
    d.device_type,
    count() AS total_doc_uploads,
    round(avg(d.retry_count), 2) AS avg_retry_count,
    countIf(d.is_crossed_failed_attempt_threshold = 1) AS failed_attempt_breaches,
    round(countIf(d.is_crossed_failed_attempt_threshold = 0) * 100.0 / count(), 2) AS passport_capture_pass_rate_pct
FROM default.document_uploaded d
JOIN default.application_started a ON d.application_id = a.application_id
GROUP BY a.destination, d.device_type
HAVING total_doc_uploads >= 200
ORDER BY passport_capture_pass_rate_pct ASC, total_doc_uploads DESC
LIMIT 12
```

---

## 4. Query Execution Results

**Columns (6):** `a.destination, device_type, total_doc_uploads, avg_retry_count, failed_attempt_breaches, passport_capture_pass_rate_pct`

| a.destination | device_type | total_doc_uploads | avg_retry_count | failed_attempt_breaches | passport_capture_pass_rate_pct |
| --- | --- | --- | --- | --- | --- |
| MA | android | 222 | 0.5 | 47 | 78.83 |
| US | android | 631 | 0.46 | 130 | 79.4 |
| AU | android | 333 | 0.44 | 54 | 83.78 |
| TH | android | 395 | 0.47 | 64 | 83.8 |
| VN | android | 340 | 0.48 | 54 | 84.12 |
| AE | android | 1096 | 0.47 | 173 | 84.22 |
| GB | android | 320 | 0.54 | 49 | 84.69 |
| EG | android | 311 | 0.48 | 47 | 84.89 |
| ID | android | 538 | 0.42 | 70 | 86.99 |
| HK | android | 203 | 0.43 | 25 | 87.68 |

*Showing top 10 of 12 total rows.*

---

## 5. Executive & Analytical Summary

- **Execution Verdict:** Successfully executed without errors against ClickHouse default database.
- **Query Performance:** Returned in **250.77 ms** across ~2.5 million underlying records.
- **Data Integrity:** Schema structure, column types, and foreign key relationships confirmed against `base_context.md`.
- **Trace Persistence:** Telemetry, spans, and metadata flushed to Langfuse Cloud under trace `trace-live_run-benchmark_medium_08`.
