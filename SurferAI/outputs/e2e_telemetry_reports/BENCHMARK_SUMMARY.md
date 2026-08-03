# ClickHouse E2E Benchmark & Telemetry Validation Suite — Master Summary

**Branch:** `feat/crewai-flow-librechat`  
**Target Database:** `default`  
**Total Records Validated:** ~2.5 Million Records (2,479,858 events across 8 tables)  
**Execution Timestamp:** `2026-08-02T00:14:36.587549+00:00`  
**Total Execution Time:** `10.02 s`  
**Overall Suite Result:** `✅ 15/15 ALL TESTS PASSED`  

---

## 1. Benchmark Execution Telemetry Table

| Call ID | Tier | Query / Metric Focus | Status | Latency | Rows | Trace ID | Per-Call Report |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CALL-01-EASY** | `Easy` | Destination Card Browse Volume & Guest Ratio | ✅ OK | `1511.91 ms` | `1` | [trace-live_run-b...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/9ac7ba10cadec998daf44a8f919e668c) | [01_easy_destination_card_browse_volume_&_guest_r.md](./01_easy_destination_card_browse_volume_&_guest_r.md) |
| **CALL-02-EASY** | `Easy` | Application Starts Distribution by Device and OS | ✅ OK | `239.9 ms` | `8` | [trace-live_run-b...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/6978fec88ee738c3f267efe7beca484e) | [02_easy_application_starts_distribution_by_devic.md](./02_easy_application_starts_distribution_by_devic.md) |
| **CALL-03-EASY** | `Easy` | Total Revenue, AOV, and Discounts by Currency | ✅ OK | `240.43 ms` | `9` | [trace-live_run-b...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/07148f6e41ccd6cade2e925c138b595f) | [03_easy_total_revenue,_aov,_and_discounts_by_cur.md](./03_easy_total_revenue,_aov,_and_discounts_by_cur.md) |
| **CALL-04-EASY** | `Easy` | Top 10 Destination Search Terms and Result Counts | ✅ OK | `367.24 ms` | `10` | [trace-live_run-b...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/76ccf9e0262689bdb7d73daeb44a5b9e) | [04_easy_top_10_destination_search_terms_and_resu.md](./04_easy_top_10_destination_search_terms_and_resu.md) |
| **CALL-05-EASY** | `Easy` | Authentication Method Breakdown and Signup Success | ✅ OK | `239.89 ms` | `8` | [trace-live_run-b...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/565bfcc6c6f2e0e9ed189aafd75a4a10) | [05_easy_authentication_method_breakdown_and_sign.md](./05_easy_authentication_method_breakdown_and_sign.md) |
| **CALL-06-MEDIUM** | `Medium` | Funnel Conversion Rate by Device & Geo Cohort (HAVING >= 500 Apps) | ✅ OK | `268.01 ms` | `12` | [trace-live_run-b...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/5d9dfb2d3c669de964bd46fc7bb35575) | [06_medium_funnel_conversion_rate_by_device_&_geo_c.md](./06_medium_funnel_conversion_rate_by_device_&_geo_c.md) |
| **CALL-07-MEDIUM** | `Medium` | Weekly Funnel Stage Volumes and Step-Through Rates | ✅ OK | `256.78 ms` | `27` | [trace-live_run-b...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/01170d3578d5c81648a14c5d4152586e) | [07_medium_weekly_funnel_stage_volumes_and_step_thr.md](./07_medium_weekly_funnel_stage_volumes_and_step_thr.md) |
| **CALL-08-MEDIUM** | `Medium` | Passport-Capture Quality & Threshold Breach by Destination & Device | ✅ OK | `250.77 ms` | `12` | [trace-live_run-b...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/e354b5f50fde4b80b409dc8296b678df) | [08_medium_passport_capture_quality_&_threshold_bre.md](./08_medium_passport_capture_quality_&_threshold_bre.md) |
| **CALL-09-MEDIUM** | `Medium` | Checkout Payment Drop-off by Payment Method & Currency | ✅ OK | `240.56 ms` | `22` | [trace-live_run-b...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/3f9eb83fdc670a6469dcaf52c9c1ad0b) | [09_medium_checkout_payment_drop_off_by_payment_met.md](./09_medium_checkout_payment_drop_off_by_payment_met.md) |
| **CALL-10-MEDIUM** | `Medium` | Coupon Campaign Realized Value & Discount Share by Destination | ✅ OK | `247.04 ms` | `12` | [trace-live_run-b...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/d1b9f0ecff85d62f7bec61985325cdd9) | [10_medium_coupon_campaign_realized_value_&_discoun.md](./10_medium_coupon_campaign_realized_value_&_discoun.md) |
| **CALL-11-HARD** | `Hard` | ClickHouse windowFunnel 4-Stage Conversion Across User Journey | ✅ OK | `388.53 ms` | `8` | [trace-live_run-b...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/68c5f426fac299a34e5ce78959ab1800) | [11_hard_clickhouse_windowfunnel_4_stage_conversi.md](./11_hard_clickhouse_windowfunnel_4_stage_conversi.md) |
| **CALL-12-HARD** | `Hard` | End-to-End Funnel Latency Quantiles (P50, P90, P99) by Device & OS | ✅ OK | `256.6 ms` | `8` | [trace-live_run-b...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/d5df0091c5df634863b103a26c1e20e9) | [12_hard_end_to_end_funnel_latency_quantiles_p50,.md](./12_hard_end_to_end_funnel_latency_quantiles_p50,.md) |
| **CALL-13-HARD** | `Hard` | Known Issue K1 Diagnostic: iOS WebKit OTP Checkout Drop-off in GCC | ✅ OK | `239.79 ms` | `25` | [trace-live_run-b...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/fad7c953f5bdd48d3eaaa09e62fb418b) | [13_hard_known_issue_k1_diagnostic:_ios_webkit_ot.md](./13_hard_known_issue_k1_diagnostic:_ios_webkit_ot.md) |
| **CALL-14-HARD** | `Hard` | First-Touch Attribution and Revenue Attribution via Window Functions | ✅ OK | `560.0 ms` | `3` | [trace-live_run-b...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/81c200b592c9271ac178bf8fc2a1b08e) | [14_hard_first_touch_attribution_and_revenue_attr.md](./14_hard_first_touch_attribution_and_revenue_attr.md) |
| **CALL-15-HARD** | `Hard` | Weekly Cohort Progression Matrix & Document Retry Distribution | ✅ OK | `344.98 ms` | `27` | [trace-live_run-b...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/7042ef6cf622bc32ae0c85c3c74b3046) | [15_hard_weekly_cohort_progression_matrix_&_docum.md](./15_hard_weekly_cohort_progression_matrix_&_docum.md) |

---

## 2. Difficulty Tier Performance Breakdown

| Difficulty Tier | Tests Run | Passed | Avg Latency | Min Latency | Max Latency |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Easy** | 5 | 5 | 519.87 ms | 239.89 ms | 1511.91 ms |
| **Medium** | 5 | 5 | 252.63 ms | 240.56 ms | 268.01 ms |
| **Hard** | 5 | 5 | 357.98 ms | 239.79 ms | 560.0 ms |
| **Overall** | **15** | **15** | **376.83 ms** | **239.79 ms** | **1511.91 ms** |

---

## 3. Database & Schema Verification Highlights

1. **8 Foundation Event Tables Verified (2,479,858 Total Rows in `default`):**
   - `destination_card_clicked`: 1,000,000 rows (1,000,000 unique users)
   - `application_started`: 154,413 rows (154,413 unique application IDs)
   - `document_uploaded`: 20,446 rows (100% referential match to application_started)
   - `purchase_completed`: 7,054 rows (100% referential match to application_started)
   - `search_typed`: 599,630 rows
   - `landing_page_scrolled`: 499,786 rows
   - `auth_completed`: 183,790 rows
   - `pay_now_clicked`: 14,739 rows

2. **Core Funnel Metrics Derived:**
   - Funnel Conversion Rate (purchase ÷ application start): **4.57%** (7,054 / 154,413)
   - Visitor Conversion Rate (purchase ÷ card clicks): **0.705%** (7,054 / 1,000,000)
   - Passport Capture Pass Rate: **88.76%** (18,147 passes / 20,446 uploads)
   - Total Gross Revenue: **$19,627,982.00** (AOV: $2,782.53)

3. **Known Issues Diagnosed:**
   - **K1 (iOS WebKit OTP Autofill):** Causal evidence observed in `CALL-13-HARD` where iOS payment drop-off in GCC Gulf countries showed divergence compared to Android and non-GCC regions.
   - **K6 (SUMMER20 Coupon Campaign):** Evaluated in `CALL-10-MEDIUM`, confirming coupon discount volumes and AOV shifts across destinations.
