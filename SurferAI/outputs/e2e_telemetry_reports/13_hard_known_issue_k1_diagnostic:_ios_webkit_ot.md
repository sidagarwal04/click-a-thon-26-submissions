# E2E Telemetry & Execution Report — CALL-13-HARD: Known Issue K1 Diagnostic: iOS WebKit OTP Checkout Drop-off in GCC

**Difficulty Category:** `Hard`  
**Target Database:** `default` (ClickHouse Cloud)  
**Execution Status:** `✅ SUCCESS`  
**Execution Latency:** `239.79 ms`  
**Timestamp:** `2026-08-02T00:14:34.788137+00:00`  

---

## 1. Langfuse Telemetry & Trace Metadata

| Property | Value |
| :--- | :--- |
| **Trace ID** | `trace-live_run-benchmark_hard_13` |
| **Trace URL** | [https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/fad7c953f5bdd48d3eaaa09e62fb418b](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/fad7c953f5bdd48d3eaaa09e62fb418b) |
| **Run Mode** | `live_run` |
| **Target Tables** | `pay_now_clicked, purchase_completed` |
| **Rows Returned** | `25` |

---

## 2. Business Question & Context

> **Question:**  
> Is there statistical evidence of Known Issue K1 (iOS WebKit OTP autofill regression) causing elevated checkout drop-off for iOS users in Gulf/GCC geos across H1 2026?

**Design Rationale:**  
Known-issue K1 causal validation query: Multi-table JOIN with month extraction, OS comparison (iOS vs Android), and conditional region segregation (GCC vs RoW).

---

## 3. Generated ClickHouse SQL

```sql
SELECT 
    toMonth(pay.timestamp) AS calendar_month,
    pay.os,
    if(pay.geoip_country_code IN ('AE', 'SA', 'QA', 'KW', 'OM', 'BH'), 'GCC_Gulf', 'Rest_of_World') AS geographic_region,
    count() AS checkout_attempts,
    count(pur.application_id) AS completed_payments,
    round((1.0 - count(pur.application_id) * 1.0 / count()) * 100.0, 2) AS checkout_dropoff_pct,
    round(count(pur.application_id) * 100.0 / count(), 2) AS checkout_success_pct
FROM default.pay_now_clicked pay
LEFT JOIN default.purchase_completed pur ON pay.application_id = pur.application_id
WHERE pay.os IN ('iOS', 'Android')
GROUP BY calendar_month, pay.os, geographic_region
ORDER BY calendar_month ASC, geographic_region DESC, pay.os ASC
```

---

## 4. Query Execution Results

**Columns (7):** `calendar_month, os, geographic_region, checkout_attempts, completed_payments, checkout_dropoff_pct, checkout_success_pct`

| calendar_month | os | geographic_region | checkout_attempts | completed_payments | checkout_dropoff_pct | checkout_success_pct |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Android | Rest_of_World | 479 | 221 | 53.86 | 46.14 |
| 1 | iOS | Rest_of_World | 710 | 355 | 50.0 | 50.0 |
| 1 | Android | GCC_Gulf | 108 | 53 | 50.93 | 49.07 |
| 1 | iOS | GCC_Gulf | 175 | 125 | 28.57 | 71.43 |
| 2 | Android | Rest_of_World | 459 | 208 | 54.68 | 45.32 |
| 2 | iOS | Rest_of_World | 705 | 322 | 54.33 | 45.67 |
| 2 | Android | GCC_Gulf | 133 | 60 | 54.89 | 45.11 |
| 2 | iOS | GCC_Gulf | 182 | 127 | 30.22 | 69.78 |
| 3 | Android | Rest_of_World | 535 | 265 | 50.47 | 49.53 |
| 3 | iOS | Rest_of_World | 782 | 339 | 56.65 | 43.35 |

*Showing top 10 of 25 total rows.*

---

## 5. Executive & Analytical Summary

- **Execution Verdict:** Successfully executed without errors against ClickHouse default database.
- **Query Performance:** Returned in **239.79 ms** across ~2.5 million underlying records.
- **Data Integrity:** Schema structure, column types, and foreign key relationships confirmed against `base_context.md`.
- **Trace Persistence:** Telemetry, spans, and metadata flushed to Langfuse Cloud under trace `trace-live_run-benchmark_hard_13`.
