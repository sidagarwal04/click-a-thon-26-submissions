# E2E Telemetry & Execution Report — CALL-14-HARD: First-Touch Attribution and Revenue Attribution via Window Functions

**Difficulty Category:** `Hard`  
**Target Database:** `default` (ClickHouse Cloud)  
**Execution Status:** `✅ SUCCESS`  
**Execution Latency:** `560.0 ms`  
**Timestamp:** `2026-08-02T00:14:35.244170+00:00`  

---

## 1. Langfuse Telemetry & Trace Metadata

| Property | Value |
| :--- | :--- |
| **Trace ID** | `trace-live_run-benchmark_hard_14` |
| **Trace URL** | [https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/81c200b592c9271ac178bf8fc2a1b08e](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/81c200b592c9271ac178bf8fc2a1b08e) |
| **Run Mode** | `live_run` |
| **Target Tables** | `purchase_completed, search_typed, destination_card_clicked, landing_page_scrolled` |
| **Rows Returned** | `3` |

---

## 2. Business Question & Context

> **Question:**  
> Using first-touch attribution (ROW_NUMBER over pre-application touchpoints), what is the revenue and conversion cycle length attributed to search vs card clicks vs landing pages?

**Design Rationale:**  
High-cardinality CTE window function ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY timestamp) across 2M touchpoints joined to purchase conversions.

---

## 3. Generated ClickHouse SQL

```sql
WITH first_touch AS (
    SELECT 
        user_id,
        touchpoint_channel,
        timestamp AS first_touch_ts,
        ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY timestamp ASC) AS rn
    FROM (
        SELECT user_id, 'destination_search' AS touchpoint_channel, timestamp FROM default.search_typed
        UNION ALL
        SELECT user_id, 'card_click' AS touchpoint_channel, timestamp FROM default.destination_card_clicked
        UNION ALL
        SELECT user_id, 'landing_page_scroll' AS touchpoint_channel, timestamp FROM default.landing_page_scrolled
    )
)
SELECT 
    ft.touchpoint_channel AS first_interaction_channel,
    count(DISTINCT p.user_id) AS converted_users,
    round(sum(p.value), 2) AS attributed_gross_revenue,
    round(avg(p.value), 2) AS attributed_aov,
    round(avg(dateDiff('minute', ft.first_touch_ts, p.timestamp)), 1) AS avg_time_to_convert_minutes
FROM default.purchase_completed p
JOIN first_touch ft ON p.user_id = ft.user_id AND ft.rn = 1
WHERE p.timestamp >= ft.first_touch_ts
GROUP BY first_interaction_channel
ORDER BY attributed_gross_revenue DESC
```

---

## 4. Query Execution Results

**Columns (5):** `first_interaction_channel, converted_users, attributed_gross_revenue, attributed_aov, avg_time_to_convert_minutes`

| first_interaction_channel | converted_users | attributed_gross_revenue | attributed_aov | avg_time_to_convert_minutes |
| --- | --- | --- | --- | --- |
| destination_search | 4247 | 11774729.2 | 2772.48 | 137.4 |
| card_click | 2590 | 7193392.5 | 2777.37 | 124.4 |
| landing_page_scroll | 217 | 659860.3 | 3040.83 | 119.5 |

---

## 5. Executive & Analytical Summary

- **Execution Verdict:** Successfully executed without errors against ClickHouse default database.
- **Query Performance:** Returned in **560.0 ms** across ~2.5 million underlying records.
- **Data Integrity:** Schema structure, column types, and foreign key relationships confirmed against `base_context.md`.
- **Trace Persistence:** Telemetry, spans, and metadata flushed to Langfuse Cloud under trace `trace-live_run-benchmark_hard_14`.
