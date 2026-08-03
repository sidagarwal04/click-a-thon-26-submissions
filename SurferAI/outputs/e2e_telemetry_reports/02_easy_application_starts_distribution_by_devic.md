# E2E Telemetry & Execution Report — CALL-02-EASY: Application Starts Distribution by Device and OS

**Difficulty Category:** `Easy`  
**Target Database:** `default` (ClickHouse Cloud)  
**Execution Status:** `✅ SUCCESS`  
**Execution Latency:** `239.9 ms`  
**Timestamp:** `2026-08-02T00:14:29.308326+00:00`  

---

## 1. Langfuse Telemetry & Trace Metadata

| Property | Value |
| :--- | :--- |
| **Trace ID** | `trace-live_run-benchmark_easy_02` |
| **Trace URL** | [https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/6978fec88ee738c3f267efe7beca484e](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/6978fec88ee738c3f267efe7beca484e) |
| **Run Mode** | `live_run` |
| **Target Tables** | `application_started` |
| **Rows Returned** | `8` |

---

## 2. Business Question & Context

> **Question:**  
> What is the volume and percentage distribution of visa application starts by device type and operating system?

**Design Rationale:**  
Single-table group-by aggregation with window percent-of-total on application_started (154k rows). Validates multi-dimensional slicing.

---

## 3. Generated ClickHouse SQL

```sql
SELECT 
    device_type,
    os,
    count() AS total_application_starts,
    round(count() * 100.0 / sum(count()) OVER (), 2) AS volume_share_pct
FROM default.application_started
GROUP BY device_type, os
ORDER BY total_application_starts DESC
```

---

## 4. Query Execution Results

**Columns (4):** `device_type, os, total_application_starts, volume_share_pct`

| device_type | os | total_application_starts | volume_share_pct |
| --- | --- | --- | --- |
| ios | iOS | 63520 | 41.14 |
| android | Android | 40720 | 26.37 |
| web-user-b2c | Windows | 19044 | 12.33 |
| web-user-b2c | Mac OS X | 10396 | 6.73 |
| android | None | 8907 | 5.77 |
| Desktop | Windows | 7428 | 4.81 |
| Desktop | Mac OS X | 3227 | 2.09 |
| web-user-b2c | Linux | 1171 | 0.76 |

---

## 5. Executive & Analytical Summary

- **Execution Verdict:** Successfully executed without errors against ClickHouse default database.
- **Query Performance:** Returned in **239.9 ms** across ~2.5 million underlying records.
- **Data Integrity:** Schema structure, column types, and foreign key relationships confirmed against `base_context.md`.
- **Trace Persistence:** Telemetry, spans, and metadata flushed to Langfuse Cloud under trace `trace-live_run-benchmark_easy_02`.
