# E2E Telemetry & Execution Report — CALL-10-MEDIUM: Coupon Campaign Realized Value & Discount Share by Destination

**Difficulty Category:** `Medium`  
**Target Database:** `default` (ClickHouse Cloud)  
**Execution Status:** `✅ SUCCESS`  
**Execution Latency:** `247.04 ms`  
**Timestamp:** `2026-08-02T00:14:33.214073+00:00`  

---

## 1. Langfuse Telemetry & Trace Metadata

| Property | Value |
| :--- | :--- |
| **Trace ID** | `trace-live_run-benchmark_medium_10` |
| **Trace URL** | [https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/d1b9f0ecff85d62f7bec61985325cdd9](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/d1b9f0ecff85d62f7bec61985325cdd9) |
| **Run Mode** | `live_run` |
| **Target Tables** | `purchase_completed, application_started` |
| **Rows Returned** | `12` |

---

## 2. Business Question & Context

> **Question:**  
> How do order volume, AOV, and average discount compare between coupon-applied orders vs full-price orders across top destinations (>= 50 orders)?

**Design Rationale:**  
Multi-table JOIN evaluating promotional impact (K6 SUMMER20 campaign context) on realized revenue and AOV across visa destinations.

---

## 3. Generated ClickHouse SQL

```sql
SELECT 
    a.destination,
    pur.coupon_applied,
    if(pur.coupon_applied = 1, pur.coupon_name, 'NONE') AS coupon_code,
    count() AS order_volume,
    round(avg(pur.value), 2) AS average_order_value,
    round(sum(pur.value), 2) AS total_realized_revenue,
    round(avg(pur.discount_amount), 2) AS avg_discount_given
FROM default.purchase_completed pur
JOIN default.application_started a ON pur.application_id = a.application_id
GROUP BY a.destination, pur.coupon_applied, coupon_code
HAVING order_volume >= 50
ORDER BY order_volume DESC
LIMIT 12
```

---

## 4. Query Execution Results

**Columns (7):** `a.destination, coupon_applied, coupon_code, order_volume, average_order_value, total_realized_revenue, avg_discount_given`

| a.destination | coupon_applied | coupon_code | order_volume | average_order_value | total_realized_revenue | avg_discount_given |
| --- | --- | --- | --- | --- | --- | --- |
| AE | 0 | NONE | 916 | 2870.03 | 2628951.7 | 0.0 |
| US | 0 | NONE | 540 | 2876.68 | 1553407.2 | 0.0 |
| ID | 0 | NONE | 465 | 2702.3 | 1256570.1 | 0.0 |
| TH | 0 | NONE | 351 | 2874.96 | 1009111.8 | 0.0 |
| VN | 0 | NONE | 326 | 2721.99 | 887370.3 | 0.0 |
| EG | 0 | NONE | 313 | 2824.64 | 884111.2 | 0.0 |
| AU | 0 | NONE | 276 | 2598.87 | 717286.8 | 0.0 |
| GB | 0 | NONE | 258 | 2783.24 | 718076.7 | 0.0 |
| MA | 0 | NONE | 215 | 3384.25 | 727613.6 | 0.0 |
| HK | 0 | NONE | 183 | 2971.0 | 543693.9 | 0.0 |

*Showing top 10 of 12 total rows.*

---

## 5. Executive & Analytical Summary

- **Execution Verdict:** Successfully executed without errors against ClickHouse default database.
- **Query Performance:** Returned in **247.04 ms** across ~2.5 million underlying records.
- **Data Integrity:** Schema structure, column types, and foreign key relationships confirmed against `base_context.md`.
- **Trace Persistence:** Telemetry, spans, and metadata flushed to Langfuse Cloud under trace `trace-live_run-benchmark_medium_10`.
