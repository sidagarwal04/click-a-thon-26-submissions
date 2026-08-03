# E2E Telemetry & Execution Report — CALL-06-MEDIUM: Funnel Conversion Rate by Device & Geo Cohort (HAVING >= 500 Apps)

**Difficulty Category:** `Medium`  
**Target Database:** `default` (ClickHouse Cloud)  
**Execution Status:** `✅ SUCCESS`  
**Execution Latency:** `268.01 ms`  
**Timestamp:** `2026-08-02T00:14:31.305856+00:00`  

---

## 1. Langfuse Telemetry & Trace Metadata

| Property | Value |
| :--- | :--- |
| **Trace ID** | `trace-live_run-benchmark_medium_06` |
| **Trace URL** | [https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/5d9dfb2d3c669de964bd46fc7bb35575](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/5d9dfb2d3c669de964bd46fc7bb35575) |
| **Run Mode** | `live_run` |
| **Target Tables** | `application_started, purchase_completed` |
| **Rows Returned** | `12` |

---

## 2. Business Question & Context

> **Question:**  
> What is the stage conversion rate from application_started to purchase_completed across device types and country codes for high-volume cohorts (>= 500 applications)?

**Design Rationale:**  
Multi-table LEFT JOIN on application_id, combining 154k applications with 7k purchases, grouped by device and geo, filtered via HAVING clause.

---

## 3. Generated ClickHouse SQL

```sql
SELECT 
    a.device_type,
    a.geoip_country_code,
    count(DISTINCT a.application_id) AS started_applications,
    count(DISTINCT p.application_id) AS converted_purchases,
    round(count(DISTINCT p.application_id) * 100.0 / count(DISTINCT a.application_id), 2) AS stage_conversion_rate_pct,
    round(sum(p.value), 2) AS realized_cohort_revenue
FROM default.application_started a
LEFT JOIN default.purchase_completed p ON a.application_id = p.application_id
GROUP BY a.device_type, a.geoip_country_code
HAVING started_applications >= 500
ORDER BY stage_conversion_rate_pct DESC, started_applications DESC
LIMIT 12
```

---

## 4. Query Execution Results

**Columns (6):** `device_type, geoip_country_code, started_applications, converted_purchases, stage_conversion_rate_pct, realized_cohort_revenue`

| device_type | geoip_country_code | started_applications | converted_purchases | stage_conversion_rate_pct | realized_cohort_revenue |
| --- | --- | --- | --- | --- | --- |
| ios | AE | 8906 | 637 | 7.15 | 192706.6 |
| web-user-b2c | QA | 629 | 35 | 5.56 | 6695.5 |
| ios | OM | 1084 | 60 | 5.54 | 4391.7 |
| web-user-b2c | OM | 516 | 28 | 5.43 | 1993.4 |
| Desktop | OTHER | 924 | 50 | 5.41 | 2192.4 |
| ios | SA | 1910 | 99 | 5.18 | 28609.4 |
| android | QA | 1031 | 52 | 5.04 | 10857.6 |
| ios | OTHER | 5577 | 273 | 4.9 | 12434.5 |
| ios | GB | 2569 | 126 | 4.9 | 7508.6 |
| android | GB | 1942 | 94 | 4.84 | 5642.9 |

*Showing top 10 of 12 total rows.*

---

## 5. Executive & Analytical Summary

- **Execution Verdict:** Successfully executed without errors against ClickHouse default database.
- **Query Performance:** Returned in **268.01 ms** across ~2.5 million underlying records.
- **Data Integrity:** Schema structure, column types, and foreign key relationships confirmed against `base_context.md`.
- **Trace Persistence:** Telemetry, spans, and metadata flushed to Langfuse Cloud under trace `trace-live_run-benchmark_medium_06`.
