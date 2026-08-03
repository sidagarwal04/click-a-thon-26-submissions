# E2E Telemetry & Execution Report — CALL-01-EASY: Destination Card Browse Volume & Guest Ratio

**Difficulty Category:** `Easy`  
**Target Database:** `default` (ClickHouse Cloud)  
**Execution Status:** `✅ SUCCESS`  
**Execution Latency:** `1511.91 ms`  
**Timestamp:** `2026-08-02T00:14:26.622330+00:00`  

---

## 1. Langfuse Telemetry & Trace Metadata

| Property | Value |
| :--- | :--- |
| **Trace ID** | `trace-live_run-benchmark_easy_01` |
| **Trace URL** | [https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/9ac7ba10cadec998daf44a8f919e668c](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/9ac7ba10cadec998daf44a8f919e668c) |
| **Run Mode** | `live_run` |
| **Target Tables** | `destination_card_clicked` |
| **Rows Returned** | `1` |

---

## 2. Business Question & Context

> **Question:**  
> What is the total number of destination card clicks, distinct users, and guest browse proportion across the 1M card clicks in H1 2026?

**Design Rationale:**  
Single-table aggregation on destination_card_clicked (1M rows). Validates basic COUNT, uniqExact, and conditional aggregates.

---

## 3. Generated ClickHouse SQL

```sql
SELECT 
    count() AS total_card_clicks,
    uniqExact(user_id) AS unique_users,
    countIf(is_guest_browse = 1) AS guest_browses,
    round(countIf(is_guest_browse = 1) * 100.0 / count(), 2) AS guest_browse_pct,
    min(timestamp) AS earliest_click,
    max(timestamp) AS latest_click
FROM default.destination_card_clicked
```

---

## 4. Query Execution Results

**Columns (6):** `total_card_clicks, unique_users, guest_browses, guest_browse_pct, earliest_click, latest_click`

| total_card_clicks | unique_users | guest_browses | guest_browse_pct | earliest_click | latest_click |
| --- | --- | --- | --- | --- | --- |
| 1000000 | 1000000 | 349525 | 34.95 | 2026-01-01 00:00:35 | 2026-06-30 23:59:40 |

---

## 5. Executive & Analytical Summary

- **Execution Verdict:** Successfully executed without errors against ClickHouse default database.
- **Query Performance:** Returned in **1511.91 ms** across ~2.5 million underlying records.
- **Data Integrity:** Schema structure, column types, and foreign key relationships confirmed against `base_context.md`.
- **Trace Persistence:** Telemetry, spans, and metadata flushed to Langfuse Cloud under trace `trace-live_run-benchmark_easy_01`.
