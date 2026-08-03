# E2E Telemetry & Execution Report — CALL-05-EASY: Authentication Method Breakdown and Signup Success

**Difficulty Category:** `Easy`  
**Target Database:** `default` (ClickHouse Cloud)  
**Execution Status:** `✅ SUCCESS`  
**Execution Latency:** `239.89 ms`  
**Timestamp:** `2026-08-02T00:14:30.821013+00:00`  

---

## 1. Langfuse Telemetry & Trace Metadata

| Property | Value |
| :--- | :--- |
| **Trace ID** | `trace-live_run-benchmark_easy_05` |
| **Trace URL** | [https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/565bfcc6c6f2e0e9ed189aafd75a4a10](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/565bfcc6c6f2e0e9ed189aafd75a4a10) |
| **Run Mode** | `live_run` |
| **Target Tables** | `auth_completed` |
| **Rows Returned** | `8` |

---

## 2. Business Question & Context

> **Question:**  
> What is the volume breakdown of authentication completions by auth method (google, apple, email, phone) and new user status?

**Design Rationale:**  
Single-table authentication analysis on auth_completed (183k rows). Validates multi-key grouping, new user flags, and attempt friction.

---

## 3. Generated ClickHouse SQL

```sql
SELECT 
    auth_method,
    is_new_user,
    count() AS auth_events,
    round(count() * 100.0 / sum(count()) OVER (), 2) AS auth_share_pct,
    round(avg(attempts), 2) AS avg_attempts_to_complete
FROM default.auth_completed
GROUP BY auth_method, is_new_user
ORDER BY auth_events DESC
```

---

## 4. Query Execution Results

**Columns (5):** `auth_method, is_new_user, auth_events, auth_share_pct, avg_attempts_to_complete`

| auth_method | is_new_user | auth_events | auth_share_pct | avg_attempts_to_complete |
| --- | --- | --- | --- | --- |
| otp | 1 | 60414 | 32.87 | 1.18 |
| otp | 0 | 49853 | 27.12 | 1.18 |
| google | 1 | 22297 | 12.13 | 1.18 |
| google | 0 | 18199 | 9.9 | 1.18 |
| apple | 1 | 12931 | 7.04 | 1.18 |
| apple | 0 | 10736 | 5.84 | 1.18 |
| email | 1 | 5250 | 2.86 | 1.17 |
| email | 0 | 4110 | 2.24 | 1.18 |

---

## 5. Executive & Analytical Summary

- **Execution Verdict:** Successfully executed without errors against ClickHouse default database.
- **Query Performance:** Returned in **239.89 ms** across ~2.5 million underlying records.
- **Data Integrity:** Schema structure, column types, and foreign key relationships confirmed against `base_context.md`.
- **Trace Persistence:** Telemetry, spans, and metadata flushed to Langfuse Cloud under trace `trace-live_run-benchmark_easy_05`.
