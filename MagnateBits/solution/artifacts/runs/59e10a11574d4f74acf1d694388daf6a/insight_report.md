# Insight report - abandoned_checkout_recovery

> ### Scanned 466,048 rows / 18.3 MB in ClickHouse; sent 217 rows to the model.
> 
> That is 466.05K rows aggregated in the database against 217 aggregate rows crossing into the prompt -- a **2,148x** reduction before a single token was spent.
> Total model tokens for the whole run: **0**.
> 
> Scan figures are `read_rows` / `read_bytes` for this run's queries, summed from `system.query_log` by `query_id` -- measured, not estimated.

| | |
| --- | --- |
| Run id | `59e10a11574d4f74acf1d694388daf6a` |
| Feature | `abandoned_checkout_recovery` (Abandoned Checkout Recovery) |
| Trace | [https://us.cloud.langfuse.com/trace/0ae0e75463b18a77650a6a8cb778d9fd](https://us.cloud.langfuse.com/trace/0ae0e75463b18a77650a6a8cb778d9fd) |
| Context version used | **v7** (diff v6 -> v7) |
| Feature table | `f_abandoned_checkout_recovery_events` |
| Rows loaded | 5,919 of 5,919 read |
| Event window | 2026-06-08 06:01:00 -> 2026-07-01 00:00:00 |
| Entity key | `user_id` |

## Stage status

| # | stage | status | detail |
| ---: | --- | --- | --- |
| 1 | `context.load` | ok | 157 entries |
| 2 | `instrumentation` | ok | 5919 rows into f_abandoned_checkout_recovery_events |
| 3 | `context.reconcile` | ok | 8 contradictions |
| 4 | `analytics` | ok | 7 findings, 0 ungrounded |
| 5 | `report` | ok | this document and its sibling artifacts |

## Executive summary

- Deterministic fallback analysis of abandoned_checkout_recovery over 5919 events (2026-06-08 to 2026-07-01).
- 7 finding(s) below, each scored by the same published confidence formula as a normal run.
- No business mechanism is attached to any of them because the interpretation model was unavailable.

_7 findings: 3 WATCH, 4 INFO._

**Read these findings with the following caveats:**
- Interpretation LLM unavailable (RuntimeError: analytics.interpret: failed to produce a valid DraftReport: RuntimeError: claude CLI failed (1): ); findings below were computed deterministically in Python from the same aggregates.
- Feature identities have no overlap with the 8 production tables, so all cross-referencing here is segment-level (shared vocabulary + calendar), never a join.
- Query plan came from the deterministic fallback, not the planner LLM (RuntimeError: analytics.plan_queries: failed to produce a valid QueryPlan: RuntimeError: claude CLI failed (1): ); coverage of the PM's questions may be narrower than requested.

## Findings

Ordered by severity, then by confidence. Every confidence score below is shown with its four components so the arithmetic can be checked without reading code.

| # | severity | headline | metric | value | confidence |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | WATCH | app_version=7.46.0 converts at 4.7% vs 7.8% for 7.44.0 | `step_through_rate` | 0.0308 | 0.85 |
| 2 | WATCH | client_lib=web-js converts at 3.5% vs 7.1% for mobile-rn | `step_through_rate` | 0.0355 | 0.83 |
| 3 | WATCH | device_type=web-user-b2c converts at 3.5% vs 11.1% for Desktop | `step_through_rate` | 0.0761 | 0.74 |
| 4 | INFO | device_type=web-user-b2c converts at 48.1% vs 51.4% for ios | `step_through_rate` | 0.0331 | 0.80 |
| 5 | INFO | app_version=7.46.0 converts at 48.7% vs 51.0% for 7.45.2 | `step_through_rate` | 0.0237 | 0.80 |
| 6 | INFO | 0.00% of 2300 user_ids reach reconverted | `funnel_completion_rate` | 0.0000 | 0.77 |
| 7 | INFO | client_lib=web-js converts at 48.1% vs 50.4% for mobile-rn | `step_through_rate` | 0.0235 | 0.77 |

### 1. [WATCH] app_version=7.46.0 converts at 4.7% vs 7.8% for 7.44.0

**Metric:** `step_through_rate` = **0.0308** (7.46.0 vs 7.44.0) | segment: app_version=7.46.0  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** app_version=7.46.0 on 3 reminder_opened converts at 4.70% (18/383) against 7.77% (29/373) for 7.44.0 -- a 3.08% absolute gap.

**Why:** Mechanism not established by this query (hypothesis, unverified).
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** If the gap is causal, lifting 7.46.0 to the 7.44.0 rate would recover about 11 entities.

**Recommended action:** Check app_version=7.46.0 against the known-issues log before assuming a product cause; if nothing matches, instrument that transition directly.

**Confidence 0.85** (method: `two_proportion_ztest`, n = 373, p = 0.0800)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.86 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.92 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.85** | |

Check the arithmetic: arithmetic mean = 0.8443, geometric mean = 0.8294, product = 0.4732. This does **not** match a standard aggregation; closest is arithmetic mean at 0.8443 (delta 0.0089) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t03_funnel_by_app_version`

**Caveats:**
- Generated without the interpretation LLM; no business mechanism attached.

### 2. [WATCH] client_lib=web-js converts at 3.5% vs 7.1% for mobile-rn

**Metric:** `step_through_rate` = **0.0355** (web-js vs mobile-rn) | segment: client_lib=web-js  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** client_lib=web-js on 3 reminder_opened converts at 3.50% (7/200) against 7.05% (67/950) for mobile-rn -- a 3.55% absolute gap.

**Why:** Mechanism not established by this query (hypothesis, unverified).
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** If the gap is causal, lifting web-js to the mobile-rn rate would recover about 7 entities.

**Recommended action:** Check client_lib=web-js against the known-issues log before assuming a product cause; if nothing matches, instrument that transition directly.

**Confidence 0.83** (method: `two_proportion_ztest`, n = 200, p = 0.0627)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.77 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.94 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.83** | |

Check the arithmetic: arithmetic mean = 0.8261, geometric mean = 0.8104, product = 0.4313. This does **not** match a standard aggregation; closest is arithmetic mean at 0.8261 (delta 0.0052) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t03_funnel_by_client_lib`

**Caveats:**
- Generated without the interpretation LLM; no business mechanism attached.

### 3. [WATCH] device_type=web-user-b2c converts at 3.5% vs 11.1% for Desktop

**Metric:** `step_through_rate` = **0.0761** (web-user-b2c vs Desktop) | segment: device_type=web-user-b2c  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** device_type=web-user-b2c on 3 reminder_opened converts at 3.50% (7/200) against 11.11% (9/81) for Desktop -- a 7.61% absolute gap.

**Why:** Mechanism not established by this query (hypothesis, unverified).
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** If the gap is causal, lifting web-user-b2c to the Desktop rate would recover about 15 entities.

**Recommended action:** Check device_type=web-user-b2c against the known-issues log before assuming a product cause; if nothing matches, instrument that transition directly.

**Confidence 0.74** (method: `two_proportion_ztest`, n = 81, p = 0.0126)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.40 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.99 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.74** | |

Check the arithmetic: arithmetic mean = 0.7469, geometric mean = 0.6977, product = 0.2370. This does **not** match a standard aggregation; closest is arithmetic mean at 0.7469 (delta 0.0107) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t03_funnel_by_device_type`

**Caveats:**
- Generated without the interpretation LLM; no business mechanism attached.

### 4. [INFO] device_type=web-user-b2c converts at 48.1% vs 51.4% for ios

**Metric:** `step_through_rate` = **0.0331** (web-user-b2c vs ios) | segment: device_type=web-user-b2c  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** device_type=web-user-b2c on 2 reminder_sent converts at 48.08% (200/416) against 51.39% (499/971) for ios -- a 3.31% absolute gap.

**Why:** Mechanism not established by this query (hypothesis, unverified).
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** If the gap is causal, lifting web-user-b2c to the ios rate would recover about 13 entities.

**Recommended action:** Check device_type=web-user-b2c against the known-issues log before assuming a product cause; if nothing matches, instrument that transition directly.

**Confidence 0.80** (method: `two_proportion_ztest`, n = 416, p = 0.2581)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.87 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.74 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.80** | |

Check the arithmetic: arithmetic mean = 0.8037, geometric mean = 0.7895, product = 0.3886. This reproduces the published score via **arithmetic mean** (delta 0.0008).

**Supporting queries:** `t03_funnel_by_device_type`

**Caveats:**
- Generated without the interpretation LLM; no business mechanism attached.

### 5. [INFO] app_version=7.46.0 converts at 48.7% vs 51.0% for 7.45.2

**Metric:** `step_through_rate` = **0.0237** (7.46.0 vs 7.45.2) | segment: app_version=7.46.0  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** app_version=7.46.0 on 2 reminder_sent converts at 48.67% (383/787) against 51.04% (394/772) for 7.45.2 -- a 2.37% absolute gap.

**Why:** Mechanism not established by this query (hypothesis, unverified).
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** If the gap is causal, lifting 7.46.0 to the 7.45.2 rate would recover about 18 entities.

**Recommended action:** Check app_version=7.46.0 against the known-issues log before assuming a product cause; if nothing matches, instrument that transition directly.

**Confidence 0.80** (method: `two_proportion_ztest`, n = 772, p = 0.3493)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.96 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.65 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.80** | |

Check the arithmetic: arithmetic mean = 0.8033, geometric mean = 0.7829, product = 0.3758. This reproduces the published score via **arithmetic mean** (delta 0.0007).

**Supporting queries:** `t03_funnel_by_app_version`

**Caveats:**
- Generated without the interpretation LLM; no business mechanism attached.

### 6. [INFO] 0.00% of 2300 user_ids reach reconverted

**Metric:** `funnel_completion_rate` = **0.0000**  
**Metric definition used:** `metric.conversion_rate@v2` (exact context entry + version)

**What:** 2300 distinct user_id values entered the funnel and 0 reached reconverted (0.00%). The single worst transition is into resumed_at_step (0.00% step-through).

**Why:** Baseline volume only; no mechanism tested (hypothesis, unverified).
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** This is the denominator every segment cut below is measured against.

**Recommended action:** Agree with the PM that reconverted is the right success event before this number becomes a target, then dig into the drop into resumed_at_step.

**Confidence 0.77** (method: `descriptive`, n = 2,300)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 1.00 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.50 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.77** | |

Check the arithmetic: arithmetic mean = 0.7750, geometric mean = 0.7401, product = 0.3000. This does **not** match a standard aggregation; closest is arithmetic mean at 0.7750 (delta 0.0050) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t02_funnel_overall`

**Caveats:**
- Generated without the interpretation LLM.

### 7. [INFO] client_lib=web-js converts at 48.1% vs 50.4% for mobile-rn

**Metric:** `step_through_rate` = **0.0235** (web-js vs mobile-rn) | segment: client_lib=web-js  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** client_lib=web-js on 2 reminder_sent converts at 48.08% (200/416) against 50.42% (950/1884) for mobile-rn -- a 2.35% absolute gap.

**Why:** Mechanism not established by this query (hypothesis, unverified).
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** If the gap is causal, lifting web-js to the mobile-rn rate would recover about 9 entities.

**Recommended action:** Check client_lib=web-js against the known-issues log before assuming a product cause; if nothing matches, instrument that transition directly.

**Confidence 0.77** (method: `two_proportion_ztest`, n = 416, p = 0.3861)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.87 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.61 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.77** | |

Check the arithmetic: arithmetic mean = 0.7717, geometric mean = 0.7530, product = 0.3216. This does **not** match a standard aggregation; closest is arithmetic mean at 0.7717 (delta 0.0056) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t03_funnel_by_client_lib`

**Caveats:**
- Generated without the interpretation LLM; no business mechanism attached.

## Schema generated for this feature

| | |
| --- | --- |
| Table | `f_abandoned_checkout_recovery_events` |
| Engine | `MergeTree` |
| ORDER BY | `(event, timestamp, user_id)` |
| PARTITION BY | `toYYYYMM(timestamp)` |
| TTL | `toDateTime(timestamp) + INTERVAL 18 MONTH` |
| Columns | 15 (10 LowCardinality, 0 Nullable, 4 with a codec) |
| Materialized views | 1 |

**Table settings:** `ratio_of_defaults_for_sparse_serialization = 0.8571`, `index_granularity = 8192`

### Columns

| column | type | source path | codec | note |
| --- | --- | --- | --- | --- |
| `app_version` | `LowCardinality(String)` | `app_version` | `-` | events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=3 |
| `application_id` | `String` | `application_id` | `(ZSTD(1))` | events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=2300 |
| `channel` | `LowCardinality(String)` | `channel` | `-` | events: reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=0.61; distinct=3 |
| `city` | `LowCardinality(String)` | `city` | `-` | events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=7 |
| `client_lib` | `LowCardinality(String)` | `client_lib` | `-` | events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=2 |
| `destination` | `LowCardinality(String)` | `destination` | `-` | events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=14 |
| `device_type` | `LowCardinality(String)` | `device_type` | `-` | events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=4 |
| `drop_step` | `LowCardinality(String)` | `drop_step` | `-` | events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=4 |
| `event` | `LowCardinality(String)` | `event` | `-` | events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=6 |
| `geoip_country_code` | `LowCardinality(String)` | `geoip_country_code` | `-` | events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=7 |
| `hours_since_drop` | `UInt16` | `hours_since_drop` | `-` | events: reminder_sent; coverage=0.39; distinct=5 |
| `id` | `String` | `id` | `(ZSTD(1))` | events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=5919 |
| `os` | `LowCardinality(String)` | `os` | `-` | events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=0.95; distinct=4 |
| `timestamp` | `DateTime64(3)` | `timestamp` | `(Delta, ZSTD(1))` | events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=4696 |
| `user_id` | `String` | `user_id` | `(ZSTD(1))` | events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=2300 |

### Rationale, decision by decision

**`order_by`** - ORDER BY (event, timestamp, user_id). The 8 existing tables use (id, timestamp, user_id); id is unique, so the primary index prunes nothing for queries that filter by time and segment and never by id. Leading with the event discriminator (6 values) prunes hard and compresses well, timestamp second matches every time-windowed query, and user_id last keeps each entity's step sequence co-located for windowFunnel.

**`partition_by`** - toYYYYMM(timestamp), matching the existing tables so cross-table segment queries prune consistently. Daily partitions would create thousands of tiny parts at this volume and slow merges for no pruning benefit over a monthly part.

**`types`** - E=6 event types in one wide table, so an event-scoped column is ~(1 - 1/6) = 0.83 defaults -- under ClickHouse's 0.9375 sparse threshold, so it would stay dense. ratio_of_defaults_for_sparse_serialization is set to min(0.9, 1 - 1/(E+1)) = 0.8571 so those columns actually go sparse. id is a 32-char hex string with no dashes and is typed String, not UUID, which would reject the literal outright. timestamp is DateTime64(3) because the source carries milliseconds. Enums are LowCardinality(String); high-cardinality ids are plain String with ZSTD(1); currency-denominated values are Decimal(18,4) so sums are exact; genuinely approximate ratios stay Float64.

**`nullable`** - No Nullable columns. A null map is a second column to read and it weakens index usage on exactly the columns we filter by; absent values use DEFAULT ''/0 instead. The trap this creates is recorded, not ignored: partial-coverage identity columns are none, and every distinct-user metric on them must be uniqIf(col, col != '') because a bare uniq() would count the empty string as a real user.

**`ttl`** - TTL toDateTime(timestamp) + INTERVAL 18 MONTH on raw events, paired with a rollup that has no TTL. That pairing is what makes the MV worth its cost: the aggregate outlives raw expiry, so long-range trend queries keep answering.

**`mvs`** - One daily per-step, per-segment rollup. Dimensions are chosen under a row budget (days x event types x cardinality <= row_count/8) so the rollup is materially smaller than the source; anything that fails the 5x measured reduction gate after load is dropped with the number recorded. At sample volume the MV is unnecessary; it is justified against projected annual volume, not against these rows.

**`contrast_with_legacy`** - One wide table per feature instead of one table per event: every PM question here is a within-feature funnel, which is one windowFunnel on a wide table and an N-way join on the legacy shape. The existing one-table-per-event layout is an SDK artifact, not a design decision, and the id-first sorting key is a bug we do not copy.

**`generation_log`** - attempt 0: LLM call failed: propose_ddl:abandoned_checkout_recovery: failed to produce a valid DDLProposal: RuntimeError: claude CLI failed (1):  ; fell back to the deterministic rule-based proposal ; fallback dry run ok=True 

### How this differs from the legacy event tables

One wide table per feature instead of one table per event: every PM question here is a within-feature funnel, which is one windowFunnel on a wide table and an N-way join on the legacy shape. The existing one-table-per-event layout is an SDK artifact, not a design decision, and the id-first sorting key is a bug we do not copy.

Structural differences a reviewer can verify directly against `SHOW CREATE TABLE` on any of the 8 pre-existing tables:

| dimension | legacy event tables | this feature table |
| --- | --- | --- |
| shape | one table per event type | one wide table per feature, `event` as the discriminator |
| ORDER BY | leads with the unique `id`, so the primary index cannot prune the time/segment filters that are actually run | `(event, timestamp, user_id)` |
| Nullable | nearly every column Nullable, costing a null map and weakening the index | 0 of 15 columns Nullable |
| enum columns | plain `String` | 10 columns as `LowCardinality(String)` |
| codecs | none declared | 4 columns carry an explicit codec |
| retention | none | `toDateTime(timestamp) + INTERVAL 18 MONTH`, paired with a rollup that outlives raw expiry |

### Generated DDL

```sql
CREATE TABLE IF NOT EXISTS f_abandoned_checkout_recovery_events
(
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=3',
    `application_id` String DEFAULT '' COMMENT 'json_path=application_id; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=2300' CODEC(ZSTD(1)),
    `channel` LowCardinality(String) DEFAULT '' COMMENT 'json_path=channel; events: reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=0.61; distinct=3',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=7',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=2',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=14',
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=4',
    `drop_step` LowCardinality(String) DEFAULT '' COMMENT 'json_path=drop_step; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=4',
    `event` LowCardinality(String) DEFAULT '' COMMENT 'json_path=event; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=6',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=7',
    `hours_since_drop` UInt16 DEFAULT 0 COMMENT 'json_path=hours_since_drop; events: reminder_sent; coverage=0.39; distinct=5',
    `id` String DEFAULT '' COMMENT 'json_path=id; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=5919' CODEC(ZSTD(1)),
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=0.95; distinct=4',
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=4696' CODEC(Delta, ZSTD(1)),
    `user_id` String DEFAULT '' COMMENT 'json_path=user_id; events: abandonment_detected,reminder_sent,reminder_opened,reminder_cta_clicked,resumed_at_step,reconverted; coverage=1.00; distinct=2300' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, user_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.8571, index_granularity = 8192;

CREATE TABLE IF NOT EXISTS agg_abandoned_checkout_recovery_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, device_type)
EMPTY AS
SELECT
    toDate(timestamp) AS day,
    event,
    device_type,
    countState() AS events_state,
    uniqStateIf(user_id, user_id != '') AS uniq_entities
FROM f_abandoned_checkout_recovery_events
GROUP BY day, event, device_type;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_abandoned_checkout_recovery_funnel_daily
TO agg_abandoned_checkout_recovery_funnel_daily AS
SELECT
    toDate(timestamp) AS day,
    event,
    device_type,
    countState() AS events_state,
    uniqStateIf(user_id, user_id != '') AS uniq_entities
FROM f_abandoned_checkout_recovery_events
GROUP BY day, event, device_type;
```

### Materialized views: measured, then kept or dropped

| materialized view | target table | source rows | target rows | reduction | verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `mv_abandoned_checkout_recovery_funnel_daily` | `agg_abandoned_checkout_recovery_funnel_daily` | 5,919 | 473 | 12.5x | **KEPT** |

The gate is a measured 5x reduction. An MV dropped **with** its measurement is a stronger result than one kept on faith.

**`mv_abandoned_checkout_recovery_funnel_daily`** - Daily per-step, per-segment funnel counters. Every PM question in this spec is 'step X -> step Y, cut by a segment, over time', which this answers by reading the rollup instead of the raw stream. It is also the retention pair for the raw TTL: raw events expire at 18 months, this survives, so long-range trend queries keep working on a fraction of the bytes. Distinct counts are stored as uniqState and must be read with uniqMerge -- summing distinct counts across parts is wrong.
- serves PM question: _Reconversion (recovery) rate by **drop_step** — which step is most recoverable?_
- serves PM question: _Which **channel** recovers best (open → click → reconvert)?_
- serves PM question: _Does timing (`hours_since_drop`) matter — send at 1h vs 24h vs 48h?_
- serves PM question: _Segment cuts (device, geo, destination). Bonus: does recovery target the same drop-offs seen in the existing funnel tables?_

## Context changes this run

Context layer moved **v6 -> v7**: 21 added, 0 updated, 0 superseded, 8 contradictions, 5 gaps.

### Added

- **`business_def.abandoned_checkout_recovery.funnel` v1** (business_def) - abandoned_checkout_recovery funnel: Ordered steps on `atlys.f_abandoned_checkout_recovery_events`: abandonment_detected -> reminder_sent -> reminder_opened -> reminder_cta_clicked -> resumed_at_step -> reconverted (step order source: spec). Segment dimensions: client_lib, app_version, device_type, drop_step, city, geoip_country_code, destination, os. Event discriminator column: `event`. _[source: instrumentation_agent, confidence 1.00, refs: app_version, city, client_lib, destination, device_type, drop_step, event, f_abandoned_checkout_recovery_events, geoip_country_code, os]_
- **`column.f_abandoned_checkout_recovery_events.app_version` v1** (column_doc) - f_abandoned_checkout_recovery_events.app_version: app_version LowCardinality(String) on f_abandoned_checkout_recovery_events. _[source: context_agent, confidence 1.00, refs: app_version, f_abandoned_checkout_recovery_events]_
- **`column.f_abandoned_checkout_recovery_events.application_id` v1** (column_doc) - f_abandoned_checkout_recovery_events.application_id: application_id String on f_abandoned_checkout_recovery_events. _[source: context_agent, confidence 1.00, refs: application_id, f_abandoned_checkout_recovery_events]_
- **`column.f_abandoned_checkout_recovery_events.channel` v1** (column_doc) - f_abandoned_checkout_recovery_events.channel: channel LowCardinality(String) on f_abandoned_checkout_recovery_events. _[source: context_agent, confidence 1.00, refs: channel, f_abandoned_checkout_recovery_events]_
- **`column.f_abandoned_checkout_recovery_events.city` v1** (column_doc) - f_abandoned_checkout_recovery_events.city: city LowCardinality(String) on f_abandoned_checkout_recovery_events. _[source: context_agent, confidence 1.00, refs: city, f_abandoned_checkout_recovery_events]_
- **`column.f_abandoned_checkout_recovery_events.client_lib` v1** (column_doc) - f_abandoned_checkout_recovery_events.client_lib: client_lib LowCardinality(String) on f_abandoned_checkout_recovery_events. _[source: context_agent, confidence 1.00, refs: client_lib, f_abandoned_checkout_recovery_events]_
- **`column.f_abandoned_checkout_recovery_events.destination` v1** (column_doc) - f_abandoned_checkout_recovery_events.destination: destination LowCardinality(String) on f_abandoned_checkout_recovery_events. _[source: context_agent, confidence 1.00, refs: destination, f_abandoned_checkout_recovery_events]_
- **`column.f_abandoned_checkout_recovery_events.device_type` v1** (column_doc) - f_abandoned_checkout_recovery_events.device_type: device_type LowCardinality(String) on f_abandoned_checkout_recovery_events. _[source: context_agent, confidence 1.00, refs: device_type, f_abandoned_checkout_recovery_events]_
- **`column.f_abandoned_checkout_recovery_events.drop_step` v1** (column_doc) - f_abandoned_checkout_recovery_events.drop_step: drop_step LowCardinality(String) on f_abandoned_checkout_recovery_events. _[source: context_agent, confidence 1.00, refs: drop_step, f_abandoned_checkout_recovery_events]_
- **`column.f_abandoned_checkout_recovery_events.event` v1** (column_doc) - f_abandoned_checkout_recovery_events.event: event LowCardinality(String) on f_abandoned_checkout_recovery_events. _[source: context_agent, confidence 1.00, refs: event, f_abandoned_checkout_recovery_events]_
- **`column.f_abandoned_checkout_recovery_events.geoip_country_code` v1** (column_doc) - f_abandoned_checkout_recovery_events.geoip_country_code: geoip_country_code LowCardinality(String) on f_abandoned_checkout_recovery_events. _[source: context_agent, confidence 1.00, refs: f_abandoned_checkout_recovery_events, geoip_country_code]_
- **`column.f_abandoned_checkout_recovery_events.hours_since_drop` v1** (column_doc) - f_abandoned_checkout_recovery_events.hours_since_drop: hours_since_drop UInt16 on f_abandoned_checkout_recovery_events. _[source: context_agent, confidence 1.00, refs: f_abandoned_checkout_recovery_events, hours_since_drop]_
- **`column.f_abandoned_checkout_recovery_events.id` v1** (column_doc) - f_abandoned_checkout_recovery_events.id: id String on f_abandoned_checkout_recovery_events. _[source: context_agent, confidence 1.00, refs: f_abandoned_checkout_recovery_events, id]_
- **`column.f_abandoned_checkout_recovery_events.os` v1** (column_doc) - f_abandoned_checkout_recovery_events.os: os LowCardinality(String) on f_abandoned_checkout_recovery_events. _[source: context_agent, confidence 1.00, refs: f_abandoned_checkout_recovery_events, os]_
- **`column.f_abandoned_checkout_recovery_events.timestamp` v1** (column_doc) - f_abandoned_checkout_recovery_events.timestamp: timestamp DateTime64(3) on f_abandoned_checkout_recovery_events. _[source: context_agent, confidence 1.00, refs: f_abandoned_checkout_recovery_events, timestamp]_
- **`column.f_abandoned_checkout_recovery_events.user_id` v1** (column_doc) - f_abandoned_checkout_recovery_events.user_id: user_id String on f_abandoned_checkout_recovery_events. _[source: context_agent, confidence 1.00, refs: f_abandoned_checkout_recovery_events, user_id]_
- **`entity.abandoned_checkout_recovery.entity_key` v1** (entity) - abandoned_checkout_recovery entity key: user_id: The grain of `atlys.f_abandoned_checkout_recovery_events` is `user_id` (confidence 0.70); secondary keys: application_id. Derived from the spec and the raw events by the instrumentation agent, not assumed. _[source: instrumentation_agent, confidence 0.70, refs: application_id, f_abandoned_checkout_recovery_events, user_id]_
- **`gap.data_quality.f_abandoned_checkout_recovery_events.application_id_join` v1** (gap) - data_quality: f_abandoned_checkout_recovery_events.application_id is not joinable to the existing tables: MEASURED, not assumed. 0.0% of `f_abandoned_checkout_recovery_events` rows have `application_id = ''` (anonymous events; empty string, not NULL). Rows joinable to the existing tables on `application_id`: destination_card_clicked=0, search_typed=0. Every identity-level metric on this table MUST use uniqIf(application_id, application_id != ''), and every cross-reference to the eight pre-existing tables MUST be segment-level (app_version, city, client_lib / day), never an identity join. Findings that compare this feature to the existing funnel must carry this as a caveat. _[source: context_agent, confidence 1.00, refs: application_id, destination_card_clicked, f_abandoned_checkout_recovery_events, search_typed]_
- **`gap.data_quality.f_abandoned_checkout_recovery_events.user_id_join` v1** (gap) - data_quality: f_abandoned_checkout_recovery_events.user_id is not joinable to the existing tables: MEASURED, not assumed. 0.0% of `f_abandoned_checkout_recovery_events` rows have `user_id = ''` (anonymous events; empty string, not NULL). Rows joinable to the existing tables on `user_id`: destination_card_clicked=0, search_typed=0. Every identity-level metric on this table MUST use uniqIf(user_id, user_id != ''), and every cross-reference to the eight pre-existing tables MUST be segment-level (app_version, city, client_lib / day), never an identity join. Findings that compare this feature to the existing funnel must carry this as a caveat. _[source: context_agent, confidence 1.00, refs: destination_card_clicked, f_abandoned_checkout_recovery_events, search_typed, user_id]_
- **`relationship.f_abandoned_checkout_recovery_events.segment_join` v1** (relationship) - f_abandoned_checkout_recovery_events -> existing tables (segment-level only): `f_abandoned_checkout_recovery_events` shares no identities with the eight pre-existing tables, but shares these segment vocabularies (measured overlap of distinct values against `destination_card_clicked`): `app_version` (3 shared values), `city` (7 shared values), `client_lib` (2 shared values). Join on those plus toDate(timestamp). This supersedes the documented user_id join map for feature tables. _[source: context_agent, confidence 1.00, refs: app_version, city, client_lib, destination_card_clicked, f_abandoned_checkout_recovery_events]_
- **`table.f_abandoned_checkout_recovery_events` v1** (table_doc) - f_abandoned_checkout_recovery_events: Auto-documented from the live schema: 15 columns; 5,919 rows at first observation; ORDER BY (event, timestamp, user_id); PARTITION BY toYYYYMM(timestamp); TTL toDateTime(timestamp) + INTERVAL 18 MONTH; order_by rationale: ORDER BY (event, timestamp, user_id). The 8 existing tables use (id, timestamp, user_id); id is unique, so the primary index prunes nothing for queries that filter by time and segment and never by id. Leading with the event discriminator (6 values) prunes hard and compresses well, timestamp second matches every time-windowed query, and user_id last keeps each entity's step sequence co-located for windowFunnel.. Columns: app_version, application_id, channel, city, client_lib, destination, device_type, drop_step, event, geoip_country_code, hours_since_drop, id, os, timestamp, user_id. _[source: context_agent, confidence 1.00, refs: f_abandoned_checkout_recovery_events]_

### Updated

_nothing updated_

### Superseded

_nothing superseded_

### Contradictions found

#### [HIGH] 'conversion (note)' and 'Conversion rate' divide by different populations

- **Kind:** `definition_conflict` (detected by rule)
- **The context claims:** The context defines the same metric subject ['conversion'] twice. [a] metric.conversion@v1 'conversion (note)': numerator='`purchase_completed` users' -> table `purchase_completed`; denominator='users who started an application (`application_started`)' -> table `application_started` | [b] metric.conversion_rate@v2 'Conversion rate': numerator='completed purchases' -> table `purchase_completed` (matched 2 word(s) in the phrase); denominator='**sessions**' -> proxy: column `app_session_id` on `destination_card_clicked` (no table is named for 'session')
- **The data says:** The two definitions have different denominators, so they cannot both be the number reported as this metric. Executed: definition [a] = 0.045546, definition [b] = 0.007065 (0.16x apart) over the same window.
- **Verified against the database:** **yes**
- **Entries affected:** `metric.conversion`, `metric.conversion_rate`
- **Proposed resolution:** Pick one denominator and version it. Recommended: keep both but rename -- 'conversion (note)' (denominator: 'users who started an application (`application_started`)') and 'Conversion rate' (denominator: '**sessions**') -- so every report states which it used via Finding.metric_definition_used.

Verification SQL:

```sql
SELECT
  (SELECT uniqIf(user_id, user_id != '') FROM atlys.purchase_completed) AS num_a,
  (SELECT uniqIf(user_id, user_id != '') FROM atlys.application_started) AS den_a,
  (SELECT uniqIf(user_id, user_id != '') FROM atlys.purchase_completed) AS num_b,
  (SELECT uniqIf(ifNull(app_session_id, ''), ifNull(app_session_id, '') != '') FROM atlys.destination_card_clicked) AS den_b,
  round(num_a / den_a, 6) AS rate_a,
  round(num_b / den_b, 6) AS rate_b,
  round(rate_b / rate_a, 2) AS ratio_b_over_a
```

Result: `[{"num_a": 7054, "den_a": 154877, "num_b": 7054, "den_b": 998469, "rate_a": 0.045546, "rate_b": 0.007065, "ratio_b_over_a": 0.16}]`

#### [HIGH] `f_abandoned_checkout_recovery_events` cannot be joined to the existing tables on `application_id`

- **Kind:** `join_assumption_violated` (detected by rule)
- **The context claims:** The documented join map asserts every table joins on `application_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.f_express_checkout_events.segment_join, relationship.f_group_family_events.segment_join).
- **The data says:** `f_abandoned_checkout_recovery_events` has 5919 rows, of which 0 (0.0%) carry `application_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 2300 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 3), ('city', 7), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.f_express_checkout_events.segment_join`, `relationship.f_group_family_events.segment_join`, `relationship.f_instant_forex_events.segment_join`, `relationship.f_status_sharing_events.segment_join`
- **Proposed resolution:** Analytics must NOT join this table to the existing tables on `application_id`. Cross-reference at segment level only (app_version, city, client_lib and day). Corroborating query: SELECT count() AS shared_values FROM (SELECT DISTINCT app_version AS v FROM atlys.f_abandoned_checkout_recovery_events WHERE app_version != '') a INNER JOIN (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.destination_card_clicked) b USING (v) -> app_version=3, city=7, client_lib=2

Verification SQL:

```sql
SELECT
  count() AS new_rows,
  countIf(application_id = '') AS anonymous_rows,
  round(countIf(application_id = '') / count(), 4) AS anonymous_frac,
  uniqIf(application_id, application_id != '') AS distinct_identities,
  countIf(application_id != '' AND application_id IN (SELECT ifNull(application_id, '') FROM atlys.destination_card_clicked)) AS rows_joinable_to_destination_card_clicked,
  countIf(application_id != '' AND application_id IN (SELECT ifNull(application_id, '') FROM atlys.search_typed)) AS rows_joinable_to_search_typed
FROM atlys.f_abandoned_checkout_recovery_events
```

Result: `[{"new_rows": 5919, "anonymous_rows": 0, "anonymous_frac": 0.0, "distinct_identities": 2300, "rows_joinable_to_destination_card_clicked": 0, "rows_joinable_to_search_typed": 0}]`

#### [HIGH] `f_abandoned_checkout_recovery_events` cannot be joined to the existing tables on `user_id`

- **Kind:** `join_assumption_violated` (detected by rule)
- **The context claims:** The documented join map asserts every table joins on `user_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.f_express_checkout_events.segment_join, relationship.f_group_family_events.segment_join).
- **The data says:** `f_abandoned_checkout_recovery_events` has 5919 rows, of which 0 (0.0%) carry `user_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 2300 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 3), ('city', 7), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.f_express_checkout_events.segment_join`, `relationship.f_group_family_events.segment_join`, `relationship.f_instant_forex_events.segment_join`, `relationship.f_status_sharing_events.segment_join`
- **Proposed resolution:** Analytics must NOT join this table to the existing tables on `user_id`. Cross-reference at segment level only (app_version, city, client_lib and day). Corroborating query: SELECT count() AS shared_values FROM (SELECT DISTINCT app_version AS v FROM atlys.f_abandoned_checkout_recovery_events WHERE app_version != '') a INNER JOIN (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.destination_card_clicked) b USING (v) -> app_version=3, city=7, client_lib=2

Verification SQL:

```sql
SELECT
  count() AS new_rows,
  countIf(user_id = '') AS anonymous_rows,
  round(countIf(user_id = '') / count(), 4) AS anonymous_frac,
  uniqIf(user_id, user_id != '') AS distinct_identities,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.destination_card_clicked)) AS rows_joinable_to_destination_card_clicked,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.search_typed)) AS rows_joinable_to_search_typed
FROM atlys.f_abandoned_checkout_recovery_events
```

Result: `[{"new_rows": 5919, "anonymous_rows": 0, "anonymous_frac": 0.0, "distinct_identities": 2300, "rows_joinable_to_destination_card_clicked": 0, "rows_joinable_to_search_typed": 0}]`

#### [HIGH] `visa_issuance_eta_days` is documented on application_started but does not exist

- **Kind:** `schema_mismatch` (detected by rule)
- **The context claims:** [entity.application@v1] 'Application' references column `visa_issuance_eta_days` on application_started.
- **The data says:** system.columns returns 0 rows for that column in scope and 0 anywhere in `atlys`. Nearest actual column(s): application_started.eta_shown Nullable(String). The context also declares it as 'integer' (Int...), but the nearest real column is Nullable(String) -- different NAME and different TYPE.
- **Verified against the database:** **yes**
- **Entries affected:** `entity.application`, `metric.on_time_delivery_rate`
- **Proposed resolution:** Rewrite the entry to use `application_started.eta_shown` (Nullable(String)) if that is the intended field, and note the type difference; otherwise mark the field as not instrumented.

Verification SQL:

```sql
SELECT
  (SELECT count() FROM system.columns WHERE database = 'atlys' AND table IN ('application_started') AND name = 'visa_issuance_eta_days') AS claimed_column_exists,
  (SELECT count() FROM system.columns WHERE database = 'atlys' AND name = 'visa_issuance_eta_days') AS claimed_column_anywhere,
  (SELECT arrayStringConcat(arraySort(groupArray(concat(table, '.', name, ' ', type))), ' | ') FROM system.columns WHERE database = 'atlys' AND ((table = 'application_started' AND name = 'eta_shown'))) AS nearest_actual_columns
```

Result: `[{"claimed_column_exists": 0, "claimed_column_anywhere": 0, "nearest_actual_columns": "application_started.eta_shown Nullable(String)"}]`

#### [HIGH] 'Conversion rate' is not computable as defined

- **Kind:** `uncomputable_metric` (detected by rule)
- **The context claims:** [metric.conversion_rate@v2] 'Conversion rate' = completed purchases ÷ **sessions**. Its DENOMINATOR is 'sessions'.
- **The data says:** 'sessions' resolves to nothing in the schema: 0 tables and 0 exactly-named columns. Only app_session_id exists, and a column cannot be counted as an occurrence without a start/end event. The headline number therefore cannot be reproduced from these tables as written.
- **Verified against the database:** **yes**
- **Entries affected:** `metric.conversion_rate`
- **Proposed resolution:** Report this metric against a denominator that exists, and state the substitution in every finding. Until then it is excluded from ContextStore.metric_catalog().

Verification SQL:

```sql
SELECT
  (SELECT count() FROM system.tables WHERE database = 'atlys' AND name ILIKE '%session%') AS tables_matching_term,
  (SELECT count() FROM system.columns WHERE database = 'atlys' AND name = 'session') AS exact_column_named_term,
  (SELECT arrayStringConcat(arraySort(groupUniqArray(name)), ', ') FROM system.columns WHERE database = 'atlys' AND name ILIKE '%session%') AS columns_containing_term
```

Result: `[{"tables_matching_term": 0, "exact_column_named_term": 0, "columns_containing_term": "app_session_id"}]`

#### [MEDIUM] Documented ORDER BY leads with `id`, a near-unique key that prunes nothing

- **Kind:** `stale_entry` (detected by rule)
- **The context claims:** [table_doc.instrumentation_note@v1] 'Instrumentation note' documents ORDER BY (id, timestamp, user_id) and simultaneously admits: "...first** (`ORDER BY (id, timestamp, user_id)`) — a legacy of the event-table template. Queries filter by time/segment..."
- **The data says:** On `destination_card_clicked`, the declared sorting key is 'id, timestamp, user_id' and the lead key `id` has selectivity 1.0 over 1000000 rows (1000000 distinct values) -- 1.0 distinct values per row -- effectively a unique key. Every granule therefore holds a distinct value, so the primary index prunes nothing for the time/segment filters the entry says queries actually use. The entry documents a design it already calls obsolete. (This check reports on measured cardinality, not on the lead column's position or name: a lead key under 0.5 selectivity and under 10000 distinct values is a genuine discriminator and is NOT reported.)
- **Verified against the database:** **yes**
- **Entries affected:** `table_doc.instrumentation_note`
- **Proposed resolution:** New tables must NOT copy this. Lead ORDER BY with a low-cardinality column the queries filter on, then `timestamp`, then the entity key -- and record the contrast in DDLProposal.rationale['order_by'].

Verification SQL:

```sql
SELECT
  'destination_card_clicked' AS table_checked,
  (SELECT sorting_key FROM system.tables WHERE database = 'atlys' AND name = 'destination_card_clicked') AS declared_sorting_key,
  count() AS rows,
  uniqExact(id) AS distinct_values_of_lead_key,
  round(uniqExact(id) / count(), 4) AS lead_key_selectivity
FROM atlys.destination_card_clicked
```

Result: `[{"table_checked": "destination_card_clicked", "declared_sorting_key": "id, timestamp, user_id", "rows": 1000000, "distinct_values_of_lead_key": 1000000, "lead_key_selectivity": 1.0}]`

#### [MEDIUM] 'On-time delivery rate' is documented as a metric but cannot be computed here

- **Kind:** `uncomputable_metric` (detected by rule)
- **The context claims:** [metric.on_time_delivery_rate@v2] 'On-time delivery rate' = applications issued on or before `visa_issuance_eta_days` ÷ applications issued. The entry itself admits: "... or before `visa_issuance_eta_days` ÷ applications issued. (Reported by the fulfilment team from post-purchase systems; not computable from the funnel tables here.)..."
- **The data says:** Confirmed against the live schema: required column(s) ['visa_issuance_eta_days'] are absent and no table matches ['issued', 'visa_issuance_eta_day']. Executed result: [{"required_column_visa_issuance_eta_days_present": 0, "source_tables_like_issued": 0, "source_tables_like_visa_issuance_eta_day": 0}]
- **Verified against the database:** **yes**
- **Entries affected:** `metric.on_time_delivery_rate`
- **Proposed resolution:** Mark the metric disputed and exclude it from the analytics metric catalog (ContextStore.metric_catalog()) so no agent reports a number for it. Re-admit it only when a post-purchase source table lands in this database.

Verification SQL:

```sql
SELECT
  (SELECT count() FROM system.columns WHERE database = 'atlys' AND name = 'visa_issuance_eta_days') AS required_column_visa_issuance_eta_days_present,
  (SELECT count() FROM system.tables WHERE database = 'atlys' AND name ILIKE '%issued%') AS source_tables_like_issued,
  (SELECT count() FROM system.tables WHERE database = 'atlys' AND name ILIKE '%visa_issuance_eta_day%') AS source_tables_like_visa_issuance_eta_day
```

Result: `[{"required_column_visa_issuance_eta_days_present": 0, "source_tables_like_issued": 0, "source_tables_like_visa_issuance_eta_day": 0}]`

#### [MEDIUM] 'sessions' is used in a metric definition but never defined

- **Kind:** `undefined_term` (detected by rule)
- **The context claims:** [metric.conversion_rate@v2] 'Conversion rate' is defined in terms of 'sessions', but no entity/glossary entry defines 'sessions'.
- **The data says:** No table is named for it (0 matches) and no column is named 'session' (0 matches). The closest thing in the schema is: app_session_id -- a column, not an event stream, so there is no boundary event that would let us count 'sessions'.
- **Verified against the database:** **yes**
- **Entries affected:** `metric.conversion_rate`
- **Proposed resolution:** Either add an entity entry defining 'sessions' operationally (e.g. as a gap between events on app_session_id), or restate the metric in terms that exist in the schema.

Verification SQL:

```sql
SELECT
  (SELECT count() FROM system.tables WHERE database = 'atlys' AND name ILIKE '%session%') AS tables_matching_term,
  (SELECT count() FROM system.columns WHERE database = 'atlys' AND name = 'session') AS exact_column_named_term,
  (SELECT arrayStringConcat(arraySort(groupUniqArray(name)), ', ') FROM system.columns WHERE database = 'atlys' AND name ILIKE '%session%') AS columns_containing_term
```

Result: `[{"tables_matching_term": 0, "exact_column_named_term": 0, "columns_containing_term": "app_session_id"}]`

### Gaps (context the layer does not yet cover)

- join_assumption_violated: `f_abandoned_checkout_recovery_events` cannot be joined to the existing tables on `application_id`
- join_assumption_violated: `f_abandoned_checkout_recovery_events` cannot be joined to the existing tables on `user_id`
- uncomputable_metric: 'Conversion rate' is not computable as defined
- uncomputable_metric: 'On-time delivery rate' is documented as a metric but cannot be computed here
- undefined_term: 'sessions' is used in a metric definition but never defined

## Unanswered questions

- Reconversion (recovery) rate by **drop_step** — which step is most recoverable?
- Which **channel** recovers best (open → click → reconvert)?
- Does timing (`hours_since_drop`) matter — send at 1h vs 24h vs 48h?
- Segment cuts (device, geo, destination). Bonus: does recovery target the same drop-offs seen in the existing funnel tables?

## How this feature was read (provenance)

- **Entity key** `user_id` - user_id: present on 6/6 event types, 100.0% of rows, 2,300 distinct values, 100% of values span >1 step. Runner-up application_id (6/6 event types, 100.0% rows); decided on first mention order in spec.md. Co-extensive alternatives application_id partition the rows identically (2,300 values, same coverage), so every funnel and ORDER BY is numerically identical whichever is chosen -- the pick is arbitrary but harmless, hence confidence is not penalised below 0.80. Row-unique id columns were excluded as entity keys (house_rules.md section 2). [confidence=0.80]
- **Funnel derived as** abandonment_detected -> reminder_sent -> reminder_opened -> reminder_cta_clicked -> resumed_at_step -> reconverted
- **Derivation method:** [source=spec] spec bullets named 6/6 observed event types. agreement spec~timestamp=0.93, spec~volume=1.00, volume~timestamp=0.93; pairwise timestamp decisiveness=0.38 over 6,021 ordered entity pairs. timestamp order inverts reminder_cta_clicked<->resumed_at_step vs the spec -- real signal, treat those two steps as concurrent. volume order=abandonment_detected > reminder_sent > reminder_opened > reminder_cta_clicked > resumed_at_step > reconverted. timestamp order=abandonment_detected > reminder_sent > reminder_opened > resumed_at_step > reminder_cta_clicked > reconverted.
- **Event types:** `abandonment_detected` (2,300), `reminder_sent` (2,300), `reminder_opened` (690), `reminder_cta_clicked` (268), `resumed_at_step` (268), `reconverted` (93)
- **Raw events profiled:** 5,919 across 15 distinct fields

---

_Generated by the Atlys agentic analytics pipeline, run `59e10a11574d4f74acf1d694388daf6a`, context layer v7._
