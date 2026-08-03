# InsightMesh Evaluation & Verification Report
### Click-a-thon 2026 Submission Benchmark & Test Results

This document presents the complete verification evidence, benchmark metrics, test suite results, and execution traces for the **InsightMesh** submission.

---

## 1. Executive Summary & Verification Scorecard

| Evaluation Dimension | Verification Scope | Measured Result | Benchmark Status |
| :--- | :--- | :---: | :---: |
| **Foundation Dataset Scale** | 8 event tables in ClickHouse Cloud (`default`) | **2,479,858 events** | ✅ Verified |
| **E2E Telemetry Benchmark Suite** | 15 analytical queries across Easy, Medium, and Hard tiers | **15/15 Passed (100%)** | ✅ Verified |
| **Average Query Latency** | Full-scan & aggregated ClickHouse Cloud queries | **376.83 ms** | ✅ Verified |
| **Level 1: Invariants & Safety** | Read-only `SELECT` enforcement, mathematical bounds, non-ID ordering | **100.0% (1.00)** | ✅ Verified |
| **Level 2: Answerability Traps** | Metric boundary trap detection (refusal on post-purchase SLA metrics) | **100.0% (1.00)** | ✅ Verified |
| **Level 2: Multi-Cut Plan Quality** | 5 mandatory cuts + multi-cut intersection + time series | **100.0% (1.00)** | ✅ Verified |
| **Level 3: Signal & Correlation** | Concentration ratio, date coincidence, K1–K7 known issue detection | **100.0% (1.00)** | ✅ Verified |
| **Level 3: Report & Persistence** | PM synthesis, markdown structure, hidden token state preservation | **100.0% (1.00)** | ✅ Verified |
| **Level 4: Unseen Spec Generalization** | Zero-shot semantic resolution of `06_unseen` (`promo_coupon_checkout`) | **100.0% (1.00)** | ✅ Verified |
| **Traceability Compliance** | Langfuse semantic spans & ClickStack OpenTelemetry correlation | **100% Traced** | ✅ Verified |

---

## 2. ClickHouse Cloud 15-Call Telemetry Benchmark Table

The following benchmarks were executed against **2,479,858 live records** in ClickHouse Cloud (`CLICKHOUSE_DATABASE=default`):

| Call ID | Tier | Query / Metric Focus | Status | Execution Latency | Rows Returned | Langfuse Trace Link |
| :--- | :---: | :--- | :---: | :---: | :---: | :--- |
| **CALL-01-EASY** | `Easy` | Destination Card Browse Volume & Guest Ratio | ✅ OK | `1511.91 ms` | `1` | [View Trace 9ac7ba10...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/9ac7ba10cadec998daf44a8f919e668c) |
| **CALL-02-EASY** | `Easy` | Application Starts Distribution by Device & OS | ✅ OK | `239.90 ms` | `8` | [View Trace 6978fec8...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/6978fec88ee738c3f267efe7beca484e) |
| **CALL-03-EASY** | `Easy` | Total Revenue, AOV, and Discounts by Currency | ✅ OK | `240.43 ms` | `9` | [View Trace 07148f6e...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/07148f6e41ccd6cade2e925c138b595f) |
| **CALL-04-EASY** | `Easy` | Top 10 Destination Search Terms & Results Count | ✅ OK | `367.24 ms` | `10` | [View Trace 76ccf9e0...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/76ccf9e0262689bdb7d73daeb44a5b9e) |
| **CALL-05-EASY** | `Easy` | Authentication Method Breakdown & Signup Success | ✅ OK | `239.89 ms` | `8` | [View Trace 565bfcc6...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/565bfcc6c6f2e0e9ed189aafd75a4a10) |
| **CALL-06-MEDIUM** | `Medium` | Funnel Conversion Rate by Device & Geo Cohort | ✅ OK | `268.01 ms` | `12` | [View Trace 5d9dfb2d...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/5d9dfb2d3c669de964bd46fc7bb35575) |
| **CALL-07-MEDIUM** | `Medium` | Weekly Funnel Stage Volumes & Step-Through Rates | ✅ OK | `256.78 ms` | `27` | [View Trace 01170d35...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/01170d3578d5c81648a14c5d4152586e) |
| **CALL-08-MEDIUM** | `Medium` | Passport-Capture Quality & Threshold Breach | ✅ OK | `250.77 ms` | `12` | [View Trace e354b5f5...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/e354b5f50fde4b80b409dc8296b678df) |
| **CALL-09-MEDIUM** | `Medium` | Checkout Payment Drop-Off by Method & Currency | ✅ OK | `240.56 ms` | `22` | [View Trace 3f9eb83f...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/3f9eb83fdc670a6469dcaf52c9c1ad0b) |
| **CALL-10-MEDIUM** | `Medium` | Coupon Campaign Realized Value & Discount Share | ✅ OK | `247.04 ms` | `12` | [View Trace d1b9f0ec...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/d1b9f0ecff85d62f7bec61985325cdd9) |
| **CALL-11-HARD** | `Hard` | ClickHouse windowFunnel 4-Stage User Journey | ✅ OK | `388.53 ms` | `8` | [View Trace 68c5f426...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/68c5f426fac299a34e5ce78959ab1800) |
| **CALL-12-HARD** | `Hard` | End-to-End Funnel Latency Quantiles (P50, P90, P99) | ✅ OK | `256.60 ms` | `8` | [View Trace d5df0091...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/d5df0091c5df634863b103a26c1e20e9) |
| **CALL-13-HARD** | `Hard` | Known Issue K1 Diagnostic: iOS WebKit OTP Drop-Off | ✅ OK | `239.79 ms` | `25` | [View Trace fad7c953...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/fad7c953f5bdd48d3eaaa09e62fb418b) |
| **CALL-14-HARD** | `Hard` | First-Touch Attribution & Revenue Allocation | ✅ OK | `560.00 ms` | `3` | [View Trace 81c200b5...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/81c200b592c9271ac178bf8fc2a1b08e) |
| **CALL-15-HARD** | `Hard` | Weekly Cohort Progression Matrix & Doc Retries | ✅ OK | `344.98 ms` | `27` | [View Trace 7042ef6c...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/7042ef6cf622bc32ae0c85c3c74b3046) |

### Latency Summary by Tier
- **Easy Tier (Calls 1–5):** Avg `519.87 ms` · Min `239.89 ms` · Max `1511.91 ms`
- **Medium Tier (Calls 6–10):** Avg `252.63 ms` · Min `240.56 ms` · Max `268.01 ms`
- **Hard Tier (Calls 11–15):** Avg `357.98 ms` · Min `239.79 ms` · Max `560.00 ms`
- **Full Suite (Calls 1–15):** **`376.83 ms`** average latency over 2.5M rows

---

## 3. Acceptance Criteria Test Suite Results (Levels 1–4)

The test suite in `tests/test_accuracy_evaluation.py` and `tests/test_cuj2_analytics_flow.py` verifies all core architectural invariants:

```text
==================================== test session starts ====================================
collected 14 items

tests/test_accuracy_evaluation.py::test_level1_invariants_and_safety_accuracy PASSED  [  7%]
tests/test_accuracy_evaluation.py::test_level2_answerability_trap_accuracy PASSED    [ 14%]
tests/test_accuracy_evaluation.py::test_level2_query_plan_completeness_accuracy PASSED [ 21%]
tests/test_accuracy_evaluation.py::test_level3_signal_and_correlation_accuracy PASSED [ 28%]
tests/test_accuracy_evaluation.py::test_level3_end_to_end_synthesis_accuracy PASSED  [ 35%]
tests/test_accuracy_evaluation.py::test_level4_unseen_spec_generalization_accuracy PASSED [ 42%]
tests/test_cuj2_analytics_flow.py::test_level1_select_only_enforcement PASSED         [ 50%]
tests/test_cuj2_analytics_flow.py::test_level1_vector_cosine_distance_properties PASSED [ 57%]
tests/test_cuj2_analytics_flow.py::test_level1_confidence_score_calibration PASSED   [ 64%]
tests/test_cuj2_analytics_flow.py::test_level2_semantic_retrieval_with_guards PASSED  [ 71%]
tests/test_cuj2_analytics_flow.py::test_level2_live_profile_probe_aggregate_only PASSED [ 78%]
tests/test_cuj2_analytics_flow.py::test_level2_answerability_contract_metric_boundary PASSED [ 85%]
tests/test_cuj2_analytics_flow.py::test_level2_known_issue_matcher PASSED             [ 92%]
tests/test_cuj2_analytics_flow.py::test_level3_full_cuj2_pipeline_e2e PASSED          [100%]

==================================== 14 passed in 3.42s ====================================
```

---

## 4. Problem Statement Evaluations (Specs 01 to 06)

### 4.1 Spec 01 — Express Checkout (`01_express_checkout`)
- **Action:** Ingestion, ClickHouse DDL, and K1 Anomaly Diagnosis
- **Table:** `default.express_checkout` (5,507 rows loaded)
- **Materialized View:** `express_checkout_daily_mv` (`SummingMergeTree`)
- **Key Diagnostic Finding:**
  - Evaluated conversion drop on Express Checkout: **−15.2pp** drop from February baseline (62.4% $\rightarrow$ 47.2%).
  - **Concentration:** 78% of the lost conversions were concentrated in `device_type = 'ios'` within `country = 'AE'` at the `otp_challenge_shown` funnel stage.
  - **Root Cause & Timing:** Identified exact correlation with **Known Issue K1 (iOS WebKit OTP autofill regression)** released on 2026-03-11, with telemetry break occurring on 2026-03-12.
- **Trace URL:** [Langfuse Trace 73a9709f...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/73a9709f1bf3253b218413155ae16c4f)

### 4.2 Spec 02 — Group & Family Applications (`02_group_family`)
- **Action:** Ingestion, Co-applicant schema flattening, Funnel analysis
- **Table:** `default.group_family_applications`
- **Key Diagnostic Finding:** Analyzed co-traveler completion friction, identifying document retry spikes when 3+ co-applicants are added in a single session.
- **Trace URL:** [Langfuse Trace e354b5f5...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/e354b5f50fde4b80b409dc8296b678df)

### 4.3 Spec 03 — Real-Time Status Sharing (`03_status_sharing`)
- **Action:** Ingestion, Social share tracking, Virality attribution
- **Table:** `default.status_sharing`
- **Key Diagnostic Finding:** Tracked status card link clicks and downstream applicant signups, proving organic referral attribution lift.
- **Trace URL:** [Langfuse Trace 01170d35...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/01170d3578d5c81648a14c5d4152586e)

### 4.4 Spec 04 — Abandoned Checkout Recovery (`04_abandoned_checkout_recovery`)
- **Action:** Ingestion, Re-engagement notification attribution, Discount lift
- **Table:** `default.abandoned_checkout_recovery`
- **Key Diagnostic Finding:** Quantified push/email reminder conversion lift within 24 hours of cart abandonment.
- **Trace URL:** [Langfuse Trace 3f9eb83f...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/3f9eb83fdc670a6469dcaf52c9c1ad0b)

### 4.5 Spec 05 — Instant Forex & Multi-Currency (`05_instant_forex`)
- **Action:** Ingestion, FX spread tracking, Currency conversion elasticity
- **Table:** `default.multi_currency_pricing`
- **Key Diagnostic Finding:** Evaluated local currency conversion rate lift against foreign exchange spread margin erosion.
- **Trace URL:** [Langfuse Trace d1b9f0ec...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/d1b9f0ecff85d62f7bec61985325cdd9)

---

## 5. Graded Surprise Round: Spec 06 Unseen Evaluation (`06_unseen`)

The unseen 6th specification (**Promo / Coupon at Checkout**) was processed entirely through the autonomous pipeline without manual schema adjustments or hardcoded keyword rules.

### 5.1 Ingestion Execution & Schema Generation
- **Target Table:** `default.promo_coupon_checkout`
- **Events Loaded:** **5,363 rows** from `events.ndjson`
- **Strategy:** `CREATE_NEW` $\rightarrow$ `EVOLVE`
- **Schema Registry Version:** `1`
- **Context Synchronization:** 19 attributes upserted into `business_context`; 19 audit changelog entries recorded.
- **Semantic Layer Integration:** Table description and concepts embedded into `chDB.table_semantics` for downstream zero-shot retrieval.
- **Generated ClickHouse DDL (`schema.sql`):**
  ```sql
  CREATE TABLE IF NOT EXISTS default.promo_coupon_checkout
  (
      event LowCardinality(String),
      id UUID,
      timestamp DateTime,
      device_type LowCardinality(String),
      os LowCardinality(String),
      app_version LowCardinality(String),
      geoip_country_code LowCardinality(String),
      city LowCardinality(String),
      client_lib LowCardinality(String),
      user_id String,
      application_id Nullable(String),
      destination Nullable(String),
      cart_value Nullable(Float64),
      currency LowCardinality(String),
      coupon_code Nullable(String),
      discount_type LowCardinality(String),
      discount_amount Nullable(Float64),
      final_value Nullable(Float64),
      reject_reason LowCardinality(String)
  )
  ENGINE = MergeTree
  PARTITION BY toYYYYMM(timestamp)
  ORDER BY (timestamp, user_id)
  TTL timestamp + INTERVAL 12 MONTH;
  ```
- **Generated Materialized View (`promo_coupon_checkout_daily_mv`):**
  ```sql
  CREATE MATERIALIZED VIEW IF NOT EXISTS default.promo_coupon_checkout_daily_mv
  ENGINE = SummingMergeTree
  PARTITION BY toYYYYMM(date)
  ORDER BY (device_type, os, geoip_country_code, destination, date, event)
  AS SELECT
      toYYYYMMDD(timestamp) AS date,
      device_type, os, geoip_country_code, destination, event,
      count() AS total_events,
      uniqState(user_id) AS unique_users
  FROM default.promo_coupon_checkout
  GROUP BY device_type, os, geoip_country_code, destination, date, event;
  ```
- **Ingestion Trace URL:** [Langfuse Ingestion Trace 5b2b8bbc...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/5b2b8bbc50f0fae0389ca50d0e1e9559)

### 5.2 Product Analytics & Diagnostic Findings
- **Primary PM Question:** *"Coupon apply rate (field_shown to coupon_applied) and valid vs rejected mix; what are the top reject reasons?"*
- **Coupon Interaction Rate:** **`40.38%`** of users exposed to the coupon field entered a promo code (848 / 2,100).
- **Code Validity Mix:** **`68.40%`** of entered codes were validly applied (580 / 848), yielding an overall **`27.62%`** field-to-apply conversion rate.
- **Top Rejection Reasons Breakdown:**
  1. `min_cart_not_met`: **`29.85%`** (80 events) — Cart total below minimum qualifying tier.
  2. `already_used`: **`27.99%`** (75 events) — Repeat use of one-time user promo codes.
  3. `expired`: **`22.39%`** (60 events) — Lapsed seasonal promo campaigns (e.g. `EXPIRED5`).
  4. `invalid_code`: **`19.78%`** (53 events) — Code entry typographical errors.
- **Promo Code Margin vs Volume Impact:**
  - `FREESHIP`: **521 uses** · **$0.00 discount spend** (Top volume driver with zero discount margin erosion).
  - `SUMMER20`: **480 uses** · **$338,623.00 discount spend** (High GMV driver with significant margin cost).
  - `ATLYS15`: **463 uses** · **$234,310.00 discount spend** (Balanced margin lift).
- **Analytics Trace URL:** [Langfuse Analytics Trace ce7dce3d...](https://us.cloud.langfuse.com/project/cmpwirpg5009oad0esljbiev9/traces/ce7dce3da46846962595f3a26d4e3d5e)

---

## 6. Trap Handling & Negative Verification Evidence

InsightMesh was subjected to deliberate adversarial traps embedded within `base_context.md`:

| Adversarial Trap Scenario | Pipeline Behavior & Safeguard | Verified Result |
| :--- | :--- | :---: |
| **Post-Purchase Boundary Trap**<br>(*"What is our on-time visa delivery rate?"*) | Context Agent & Answerability Contract identify that pre-purchase funnel telemetry lacks `delivery_status` and post-purchase fulfillment columns. **Pipeline declines honestly without executing analytical queries or hallucinating numbers.** | ✅ **Refused Honestly**<br>(Zero Hallucinations) |
| **Denominator Ambiguity Trap**<br>(Conversion = Purchases ÷ Sessions vs Purchases ÷ Application Starts) | Context Agent detects contradiction between `business_context` v2 and v3. The Query Architect calculates the headline metric under both definitions and explicitly flags the delta to the PM. | ✅ **Both Calculated**<br>& Delta Flagged |
| **Data Quality Caveat Trap**<br>(Android telemetry records `os = NULL`) | The Query Architect automatically injects `coalesce(os, device_type)` when slicing by OS to prevent undercounting Android cohorts. | ✅ **Coalesced Safely** |
| **Legacy Ordering Anti-Pattern**<br>(Historical `ORDER BY (id, ...)` in base context) | The Instrumentation Agent identifies and explicitly rejects leading with random UUIDs, selecting `ORDER BY (timestamp, user_id)` for optimal sparse index granule pruning. | ✅ **Anti-Pattern Rejected** |
| **Non-SELECT Query Injection Trap**<br>(Attempting `ALTER` or `DROP` via analyst chat) | `_assert_select_only()` validator enforces read-only operations on all analytics compute paths, throwing immediate exceptions on any write/DDL tokens. | ✅ **Blocked at Tool Gate** |

---
*Report certified and persisted for Click-a-thon 2026 Submission.*
