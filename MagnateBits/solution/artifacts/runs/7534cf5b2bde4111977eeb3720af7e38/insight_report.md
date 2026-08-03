# Insight report - instant_forex

> ### Scanned 255,717 rows / 6.7 MB in ClickHouse; sent 155 rows to the model.
> 
> That is 255.72K rows aggregated in the database against 155 aggregate rows crossing into the prompt -- a **1,650x** reduction before a single token was spent.
> Total model tokens for the whole run: **0**.
> 
> Scan figures are `read_rows` / `read_bytes` for this run's queries, summed from `system.query_log` by `query_id` -- measured, not estimated.

| | |
| --- | --- |
| Run id | `7534cf5b2bde4111977eeb3720af7e38` |
| Feature | `instant_forex` (Instant Forex Add-on) |
| Trace | [https://us.cloud.langfuse.com/trace/c6883df2143dbd5d207cff1639a2ea55](https://us.cloud.langfuse.com/trace/c6883df2143dbd5d207cff1639a2ea55) |
| Context version used | **v8** (diff v7 -> v8) |
| Feature table | `f_instant_forex_events` |
| Rows loaded | 6,237 of 6,237 read |
| Event window | 2026-06-08 06:00:00 -> 2026-06-28 23:12:00 |
| Entity key | `user_id` |

## Stage status

| # | stage | status | detail |
| ---: | --- | --- | --- |
| 1 | `context.load` | ok | 178 entries |
| 2 | `instrumentation` | ok | 6237 rows into f_instant_forex_events |
| 3 | `context.reconcile` | ok | 8 contradictions |
| 4 | `analytics` | ok | 8 findings, 1 ungrounded |
| 5 | `report` | ok | this document and its sibling artifacts |

## Executive summary

- Deterministic fallback analysis of instant_forex over 6237 events (2026-06-08 to 2026-06-28).
- 8 finding(s) below, each scored by the same published confidence formula as a normal run.
- No business mechanism is attached to any of them because the interpretation model was unavailable.

_8 findings: 2 WATCH, 6 INFO._

**Read these findings with the following caveats:**
- 1 finding(s) failed numeric grounding and were demoted to informational; their numbers do not appear in the queries they cite.
- Interpretation LLM unavailable (RuntimeError: analytics.interpret: failed to produce a valid DraftReport: RuntimeError: claude CLI failed (1): ); findings below were computed deterministically in Python from the same aggregates.
- Feature identities have no overlap with the 8 production tables, so all cross-referencing here is segment-level (shared vocabulary + calendar), never a join.
- Query plan came from the deterministic fallback, not the planner LLM (RuntimeError: analytics.plan_queries: failed to produce a valid QueryPlan: RuntimeError: claude CLI failed (1): ); coverage of the PM's questions may be narrower than requested.

## Findings

Ordered by severity, then by confidence. Every confidence score below is shown with its four components so the arithmetic can be checked without reading code.

| # | severity | headline | metric | value | confidence |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | WATCH | app_version=7.46.0 converts at 33.0% vs 37.8% for 7.44.0 | `step_through_rate` | 0.0487 | 0.91 |
| 2 | WATCH | device_type=android converts at 89.4% vs 93.8% for web-user-b2c | `step_through_rate` | 0.0442 | 0.82 |
| 3 | INFO | app_version=7.46.0 converts at 14.4% vs 16.0% for everyone else | `step_through_rate` | 0.0164 | 0.85 |
| 4 | INFO | app_version=7.45.2 converts at 60.4% vs 65.9% for 7.46.0 | `step_through_rate` | 0.0552 | 0.82 |
| 5 | INFO | device_type=web-user-b2c converts at 33.6% vs 36.6% for android | `step_through_rate` | 0.0301 | 0.82 |
| 6 | INFO | client_lib=web-js converts at 33.6% vs 36.1% for mobile-rn | `step_through_rate` | 0.0249 | 0.81 |
| 7 | INFO | client_lib=mobile-rn converts at 90.4% vs 93.8% for web-js | `step_through_rate` | 0.0336 | 0.80 |
| 8 | INFO | bucket_label=4187 .. 16761 converts at 54.5% vs 68.3% for 46111 .. 75814 | `step_through_rate` | 0.1379 | 0.25 |

### 1. [WATCH] app_version=7.46.0 converts at 33.0% vs 37.8% for 7.44.0

**Metric:** `step_through_rate` = **0.0487** (7.46.0 vs 7.44.0) | segment: app_version=7.46.0  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** app_version=7.46.0 on 2 currency_selected converts at 32.97% (337/1022) against 37.85% (355/938) for 7.44.0 -- a 4.87% absolute gap.

**Why:** Mechanism not established by this query (hypothesis, unverified).
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** If the gap is causal, lifting 7.46.0 to the 7.44.0 rate would recover about 49 entities.

**Recommended action:** Check app_version=7.46.0 against the known-issues log before assuming a product cause; if nothing matches, instrument that transition directly.

**Confidence 0.91** (method: `two_proportion_ztest`, n = 938, p = 0.0242)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.99 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.98 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.91** | |

Check the arithmetic: arithmetic mean = 0.8916, geometric mean = 0.8727, product = 0.5800. This does **not** match a standard aggregation; closest is arithmetic mean at 0.8916 (delta 0.0184) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t03_funnel_by_app_version`

**Caveats:**
- Generated without the interpretation LLM; no business mechanism attached.

### 2. [WATCH] device_type=android converts at 89.4% vs 93.8% for web-user-b2c

**Metric:** `step_through_rate` = **0.0442** (android vs web-user-b2c) | segment: device_type=android  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** device_type=android on 3 amount_entered converts at 89.37% (311/348) against 93.79% (166/177) for web-user-b2c -- a 4.42% absolute gap.

**Why:** Mechanism not established by this query (hypothesis, unverified).
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** If the gap is causal, lifting android to the web-user-b2c rate would recover about 15 entities.

**Recommended action:** Check device_type=android against the known-issues log before assuming a product cause; if nothing matches, instrument that transition directly.

**Confidence 0.82** (method: `two_proportion_ztest`, n = 177, p = 0.0969)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.75 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.90 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.82** | |

Check the arithmetic: arithmetic mean = 0.8131, geometric mean = 0.7982, product = 0.4060. This reproduces the published score via **arithmetic mean** (delta 0.0026).

**Supporting queries:** `t03_funnel_by_device_type`

**Caveats:**
- Generated without the interpretation LLM; no business mechanism attached.

### 3. [INFO] app_version=7.46.0 converts at 14.4% vs 16.0% for everyone else

**Metric:** `step_through_rate` = **0.0164** (7.46.0 vs everyone else) | segment: app_version=7.46.0  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** app_version=7.46.0 on forex_offer_shown -> forex_purchased converts at 14.38% (147/1022) against 16.03% (301/1878) for everyone else -- a 1.64% absolute gap.

**Why:** Mechanism not established by this query (hypothesis, unverified).
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** If the gap is causal, lifting 7.46.0 to the everyone else rate would recover about 16 entities.

**Recommended action:** Check app_version=7.46.0 against the known-issues log before assuming a product cause; if nothing matches, instrument that transition directly.

**Confidence 0.85** (method: `two_proportion_ztest`, n = 1,022, p = 0.2419)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 1.00 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.76 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.85** | |

Check the arithmetic: arithmetic mean = 0.8395, geometric mean = 0.8212, product = 0.4549. This does **not** match a standard aggregation; closest is arithmetic mean at 0.8395 (delta 0.0079) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t04_segment_vs_baseline_app_version`

**Caveats:**
- Generated without the interpretation LLM; no business mechanism attached.

### 4. [INFO] app_version=7.45.2 converts at 60.4% vs 65.9% for 7.46.0

**Metric:** `step_through_rate` = **0.0552** (7.45.2 vs 7.46.0) | segment: app_version=7.45.2  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** app_version=7.45.2 on 4 forex_added_to_cart converts at 60.39% (186/308) against 65.91% (203/308) for 7.46.0 -- a 5.52% absolute gap.

**Why:** Mechanism not established by this query (hypothesis, unverified).
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** If the gap is causal, lifting 7.45.2 to the 7.46.0 rate would recover about 16 entities.

**Recommended action:** Check app_version=7.45.2 against the known-issues log before assuming a product cause; if nothing matches, instrument that transition directly.

**Confidence 0.82** (method: `two_proportion_ztest`, n = 308, p = 0.1556)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.83 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.84 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.82** | |

Check the arithmetic: arithmetic mean = 0.8185, geometric mean = 0.8052, product = 0.4203. This reproduces the published score via **arithmetic mean** (delta 0.0037).

**Supporting queries:** `t03_funnel_by_app_version`

**Caveats:**
- Generated without the interpretation LLM; no business mechanism attached.

### 5. [INFO] device_type=web-user-b2c converts at 33.6% vs 36.6% for android

**Metric:** `step_through_rate` = **0.0301** (web-user-b2c vs android) | segment: device_type=web-user-b2c  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** device_type=web-user-b2c on 2 currency_selected converts at 33.59% (177/527) against 36.59% (348/951) for android -- a 3.01% absolute gap.

**Why:** Mechanism not established by this query (hypothesis, unverified).
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** If the gap is causal, lifting web-user-b2c to the android rate would recover about 15 entities.

**Recommended action:** Check device_type=web-user-b2c against the known-issues log before assuming a product cause; if nothing matches, instrument that transition directly.

**Confidence 0.82** (method: `two_proportion_ztest`, n = 527, p = 0.2473)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.91 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.75 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.82** | |

Check the arithmetic: arithmetic mean = 0.8150, geometric mean = 0.8001, product = 0.4098. This reproduces the published score via **arithmetic mean** (delta 0.0030).

**Supporting queries:** `t03_funnel_by_device_type`

**Caveats:**
- Generated without the interpretation LLM; no business mechanism attached.

### 6. [INFO] client_lib=web-js converts at 33.6% vs 36.1% for mobile-rn

**Metric:** `step_through_rate` = **0.0249** (web-js vs mobile-rn) | segment: client_lib=web-js  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** client_lib=web-js on 2 currency_selected converts at 33.59% (177/527) against 36.07% (856/2373) for mobile-rn -- a 2.49% absolute gap.

**Why:** Mechanism not established by this query (hypothesis, unverified).
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** If the gap is causal, lifting web-js to the mobile-rn rate would recover about 13 entities.

**Recommended action:** Check client_lib=web-js against the known-issues log before assuming a product cause; if nothing matches, instrument that transition directly.

**Confidence 0.81** (method: `two_proportion_ztest`, n = 527, p = 0.2810)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.91 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.72 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.81** | |

Check the arithmetic: arithmetic mean = 0.8066, geometric mean = 0.7910, product = 0.3914. This reproduces the published score via **arithmetic mean** (delta 0.0013).

**Supporting queries:** `t03_funnel_by_client_lib`

**Caveats:**
- Generated without the interpretation LLM; no business mechanism attached.

### 7. [INFO] client_lib=mobile-rn converts at 90.4% vs 93.8% for web-js

**Metric:** `step_through_rate` = **0.0336** (mobile-rn vs web-js) | segment: client_lib=mobile-rn  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** client_lib=mobile-rn on 3 amount_entered converts at 90.42% (774/856) against 93.79% (166/177) for web-js -- a 3.36% absolute gap.

**Why:** Mechanism not established by this query (hypothesis, unverified).
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** If the gap is causal, lifting mobile-rn to the web-js rate would recover about 28 entities.

**Recommended action:** Check client_lib=mobile-rn against the known-issues log before assuming a product cause; if nothing matches, instrument that transition directly.

**Confidence 0.80** (method: `two_proportion_ztest`, n = 177, p = 0.1545)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.75 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.85 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.80** | |

Check the arithmetic: arithmetic mean = 0.7987, geometric mean = 0.7852, product = 0.3801. This reproduces the published score via **arithmetic mean** (delta 0.0003).

**Supporting queries:** `t03_funnel_by_client_lib`

**Caveats:**
- Generated without the interpretation LLM; no business mechanism attached.

### 8. [INFO] bucket_label=4187 .. 16761 converts at 54.5% vs 68.3% for 46111 .. 75814

**Metric:** `step_through_rate` = **0.1379** (4187 .. 16761 vs 46111 .. 75814) | segment: bucket_label=4187 .. 16761  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** bucket_label=4187 .. 16761 on forex_purchased addon_value_inr converts at 54.48% (79/145) against 68.28% (99/145) for 46111 .. 75814 -- a 13.79% absolute gap.

**Why:** Mechanism not established by this query (hypothesis, unverified).
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** If the gap is causal, lifting 4187 .. 16761 to the 46111 .. 75814 rate would recover about 20 entities.

**Recommended action:** Check bucket_label=4187 .. 16761 against the known-issues log before assuming a product cause; if nothing matches, instrument that transition directly.

**Confidence 0.25** (method: `two_proportion_ztest`, n = 145, p = 0.0159)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.72 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.98 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.25** | |

Check the arithmetic: arithmetic mean = 0.8261, geometric mean = 0.8076, product = 0.4254. This does **not** match a standard aggregation; closest is product at 0.4254 (delta 0.1754) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t08_numeric_driver_addon_value_inr`

**Caveats:**
- UNVERIFIED: this finding's headline number could not be matched to its own cited query results (asserts step_through_rate=0.137931, which does not appear in t08_numeric_driver_addon_value_inr). Treat as a lead, not a fact.
- Generated without the interpretation LLM; no business mechanism attached.

## Schema generated for this feature

| | |
| --- | --- |
| Table | `f_instant_forex_events` |
| Engine | `MergeTree` |
| ORDER BY | `(event, timestamp, user_id)` |
| PARTITION BY | `toYYYYMM(timestamp)` |
| TTL | `toDateTime(timestamp) + INTERVAL 18 MONTH` |
| Columns | 17 (10 LowCardinality, 0 Nullable, 4 with a codec) |
| Materialized views | 1 |

**Table settings:** `ratio_of_defaults_for_sparse_serialization = 0.8333`, `index_granularity = 8192`

### Columns

| column | type | source path | codec | note |
| --- | --- | --- | --- | --- |
| `addon_value_inr` | `Decimal(18, 4)` | `addon_value_inr` | `-` | events: forex_added_to_cart,forex_purchased; coverage=0.20; distinct=1258 |
| `amount` | `Decimal(18, 4)` | `amount` | `-` | events: amount_entered,forex_added_to_cart,forex_purchased; coverage=0.37; distinct=6 |
| `app_version` | `LowCardinality(String)` | `app_version` | `-` | events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=3 |
| `application_id` | `String` | `application_id` | `(ZSTD(1))` | events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=2900 |
| `city` | `LowCardinality(String)` | `city` | `-` | events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=7 |
| `client_lib` | `LowCardinality(String)` | `client_lib` | `-` | events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=2 |
| `destination` | `LowCardinality(String)` | `destination` | `-` | events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=14 |
| `device_type` | `LowCardinality(String)` | `device_type` | `-` | events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=4 |
| `event` | `LowCardinality(String)` | `event` | `-` | events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=5 |
| `from_currency` | `LowCardinality(String)` | `from_currency` | `-` | events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=1 |
| `fx_rate` | `Float64` | `fx_rate` | `-` | events: forex_offer_shown; coverage=0.46; distinct=2899 |
| `geoip_country_code` | `LowCardinality(String)` | `geoip_country_code` | `-` | events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=7 |
| `id` | `String` | `id` | `(ZSTD(1))` | events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=6237 |
| `os` | `LowCardinality(String)` | `os` | `-` | events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=0.94; distinct=4 |
| `timestamp` | `DateTime64(3)` | `timestamp` | `(Delta, ZSTD(1))` | events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=2901 |
| `to_currency` | `LowCardinality(String)` | `to_currency` | `-` | events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=13 |
| `user_id` | `String` | `user_id` | `(ZSTD(1))` | events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=2900 |

### Rationale, decision by decision

**`order_by`** - ORDER BY (event, timestamp, user_id). The 8 existing tables use (id, timestamp, user_id); id is unique, so the primary index prunes nothing for queries that filter by time and segment and never by id. Leading with the event discriminator (5 values) prunes hard and compresses well, timestamp second matches every time-windowed query, and user_id last keeps each entity's step sequence co-located for windowFunnel.

**`partition_by`** - toYYYYMM(timestamp), matching the existing tables so cross-table segment queries prune consistently. Daily partitions would create thousands of tiny parts at this volume and slow merges for no pruning benefit over a monthly part.

**`types`** - E=5 event types in one wide table, so an event-scoped column is ~(1 - 1/5) = 0.80 defaults -- under ClickHouse's 0.9375 sparse threshold, so it would stay dense. ratio_of_defaults_for_sparse_serialization is set to min(0.9, 1 - 1/(E+1)) = 0.8333 so those columns actually go sparse. id is a 32-char hex string with no dashes and is typed String, not UUID, which would reject the literal outright. timestamp is DateTime64(3) because the source carries milliseconds. Enums are LowCardinality(String); high-cardinality ids are plain String with ZSTD(1); currency-denominated values are Decimal(18,4) so sums are exact; genuinely approximate ratios stay Float64.

**`nullable`** - No Nullable columns. A null map is a second column to read and it weakens index usage on exactly the columns we filter by; absent values use DEFAULT ''/0 instead. The trap this creates is recorded, not ignored: partial-coverage identity columns are none, and every distinct-user metric on them must be uniqIf(col, col != '') because a bare uniq() would count the empty string as a real user.

**`ttl`** - TTL toDateTime(timestamp) + INTERVAL 18 MONTH on raw events, paired with a rollup that has no TTL. That pairing is what makes the MV worth its cost: the aggregate outlives raw expiry, so long-range trend queries keep answering.

**`mvs`** - One daily per-step, per-segment rollup. Dimensions are chosen under a row budget (days x event types x cardinality <= row_count/8) so the rollup is materially smaller than the source; anything that fails the 5x measured reduction gate after load is dropped with the number recorded. At sample volume the MV is unnecessary; it is justified against projected annual volume, not against these rows.

**`contrast_with_legacy`** - One wide table per feature instead of one table per event: every PM question here is a within-feature funnel, which is one windowFunnel on a wide table and an N-way join on the legacy shape. The existing one-table-per-event layout is an SDK artifact, not a design decision, and the id-first sorting key is a bug we do not copy.

**`generation_log`** - attempt 0: LLM call failed: propose_ddl:instant_forex: failed to produce a valid DDLProposal: RuntimeError: claude CLI failed (1):  ; fell back to the deterministic rule-based proposal ; fallback dry run ok=True 

### How this differs from the legacy event tables

One wide table per feature instead of one table per event: every PM question here is a within-feature funnel, which is one windowFunnel on a wide table and an N-way join on the legacy shape. The existing one-table-per-event layout is an SDK artifact, not a design decision, and the id-first sorting key is a bug we do not copy.

Structural differences a reviewer can verify directly against `SHOW CREATE TABLE` on any of the 8 pre-existing tables:

| dimension | legacy event tables | this feature table |
| --- | --- | --- |
| shape | one table per event type | one wide table per feature, `event` as the discriminator |
| ORDER BY | leads with the unique `id`, so the primary index cannot prune the time/segment filters that are actually run | `(event, timestamp, user_id)` |
| Nullable | nearly every column Nullable, costing a null map and weakening the index | 0 of 17 columns Nullable |
| enum columns | plain `String` | 10 columns as `LowCardinality(String)` |
| codecs | none declared | 4 columns carry an explicit codec |
| retention | none | `toDateTime(timestamp) + INTERVAL 18 MONTH`, paired with a rollup that outlives raw expiry |

### Generated DDL

```sql
CREATE TABLE IF NOT EXISTS f_instant_forex_events
(
    `addon_value_inr` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=addon_value_inr; events: forex_added_to_cart,forex_purchased; coverage=0.20; distinct=1258',
    `amount` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=amount; events: amount_entered,forex_added_to_cart,forex_purchased; coverage=0.37; distinct=6',
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=3',
    `application_id` String DEFAULT '' COMMENT 'json_path=application_id; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=2900' CODEC(ZSTD(1)),
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=7',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=2',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=14',
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=4',
    `event` LowCardinality(String) DEFAULT '' COMMENT 'json_path=event; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=5',
    `from_currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=from_currency; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=1',
    `fx_rate` Float64 DEFAULT 0 COMMENT 'json_path=fx_rate; events: forex_offer_shown; coverage=0.46; distinct=2899',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=7',
    `id` String DEFAULT '' COMMENT 'json_path=id; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=6237' CODEC(ZSTD(1)),
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=0.94; distinct=4',
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=2901' CODEC(Delta, ZSTD(1)),
    `to_currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=to_currency; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=13',
    `user_id` String DEFAULT '' COMMENT 'json_path=user_id; events: forex_offer_shown,currency_selected,amount_entered,forex_added_to_cart,forex_purchased; coverage=1.00; distinct=2900' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, user_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.8333, index_granularity = 8192;

CREATE TABLE IF NOT EXISTS agg_instant_forex_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, city)
EMPTY AS
SELECT
    toDate(timestamp) AS day,
    event,
    city,
    countState() AS events_state,
    uniqStateIf(user_id, user_id != '') AS uniq_entities,
    sumState(addon_value_inr) AS sum_addon_value_inr
FROM f_instant_forex_events
GROUP BY day, event, city;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_instant_forex_funnel_daily
TO agg_instant_forex_funnel_daily AS
SELECT
    toDate(timestamp) AS day,
    event,
    city,
    countState() AS events_state,
    uniqStateIf(user_id, user_id != '') AS uniq_entities,
    sumState(addon_value_inr) AS sum_addon_value_inr
FROM f_instant_forex_events
GROUP BY day, event, city;
```

### Materialized views: measured, then kept or dropped

| materialized view | target table | source rows | target rows | reduction | verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `mv_instant_forex_funnel_daily` | `agg_instant_forex_funnel_daily` | 6,237 | 640 | 9.8x | **KEPT** |

The gate is a measured 5x reduction. An MV dropped **with** its measurement is a stronger result than one kept on faith.

**`mv_instant_forex_funnel_daily`** - Daily per-step, per-segment funnel counters. Every PM question in this spec is 'step X -> step Y, cut by a segment, over time', which this answers by reading the rollup instead of the raw stream. It is also the retention pair for the raw TTL: raw events expire at 18 months, this survives, so long-range trend queries keep working on a fraction of the bytes. Distinct counts are stored as uniqState and must be read with uniqMerge -- summing distinct counts across parts is wrong.
- serves PM question: _Attach rate: offer_shown → forex_purchased, overall and by `destination`._
- serves PM question: _AOV uplift: distribution of `addon_value_inr` among attachers._
- serves PM question: _Where is the drop — offer → amount_entered, or added_to_cart → purchased?_
- serves PM question: _Which destinations / currencies attach best; any segment (device/geo) skew?_

## Context changes this run

Context layer moved **v7 -> v8**: 14 added, 3 updated, 0 superseded, 8 contradictions, 5 gaps.

### Added

- **`column.agg_instant_forex_funnel_daily.city` v1** (column_doc) - agg_instant_forex_funnel_daily.city: city LowCardinality(String) on agg_instant_forex_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_instant_forex_funnel_daily, city]_
- **`column.agg_instant_forex_funnel_daily.day` v1** (column_doc) - agg_instant_forex_funnel_daily.day: day Date on agg_instant_forex_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_instant_forex_funnel_daily, day]_
- **`column.agg_instant_forex_funnel_daily.event` v1** (column_doc) - agg_instant_forex_funnel_daily.event: event LowCardinality(String) on agg_instant_forex_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_instant_forex_funnel_daily, event]_
- **`column.agg_instant_forex_funnel_daily.events_state` v1** (column_doc) - agg_instant_forex_funnel_daily.events_state: events_state AggregateFunction(count) on agg_instant_forex_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_instant_forex_funnel_daily, events_state]_
- **`column.agg_instant_forex_funnel_daily.sum_addon_value_inr` v1** (column_doc) - agg_instant_forex_funnel_daily.sum_addon_value_inr: sum_addon_value_inr AggregateFunction(sum, Decimal(18, 4)) on agg_instant_forex_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_instant_forex_funnel_daily, sum_addon_value_inr]_
- **`column.agg_instant_forex_funnel_daily.uniq_entities` v1** (column_doc) - agg_instant_forex_funnel_daily.uniq_entities: uniq_entities AggregateFunction(uniq, String) on agg_instant_forex_funnel_daily. _[source: context_agent, confidence 1.00, refs: agg_instant_forex_funnel_daily, uniq_entities]_
- **`column.mv_instant_forex_funnel_daily.city` v1** (column_doc) - mv_instant_forex_funnel_daily.city: city LowCardinality(String) on mv_instant_forex_funnel_daily. _[source: context_agent, confidence 1.00, refs: city, mv_instant_forex_funnel_daily]_
- **`column.mv_instant_forex_funnel_daily.day` v1** (column_doc) - mv_instant_forex_funnel_daily.day: day Date on mv_instant_forex_funnel_daily. _[source: context_agent, confidence 1.00, refs: day, mv_instant_forex_funnel_daily]_
- **`column.mv_instant_forex_funnel_daily.event` v1** (column_doc) - mv_instant_forex_funnel_daily.event: event LowCardinality(String) on mv_instant_forex_funnel_daily. _[source: context_agent, confidence 1.00, refs: event, mv_instant_forex_funnel_daily]_
- **`column.mv_instant_forex_funnel_daily.events_state` v1** (column_doc) - mv_instant_forex_funnel_daily.events_state: events_state AggregateFunction(count) on mv_instant_forex_funnel_daily. _[source: context_agent, confidence 1.00, refs: events_state, mv_instant_forex_funnel_daily]_
- **`column.mv_instant_forex_funnel_daily.sum_addon_value_inr` v1** (column_doc) - mv_instant_forex_funnel_daily.sum_addon_value_inr: sum_addon_value_inr AggregateFunction(sum, Decimal(18, 4)) on mv_instant_forex_funnel_daily. _[source: context_agent, confidence 1.00, refs: mv_instant_forex_funnel_daily, sum_addon_value_inr]_
- **`column.mv_instant_forex_funnel_daily.uniq_entities` v1** (column_doc) - mv_instant_forex_funnel_daily.uniq_entities: uniq_entities AggregateFunction(uniq, String) on mv_instant_forex_funnel_daily. _[source: context_agent, confidence 1.00, refs: mv_instant_forex_funnel_daily, uniq_entities]_
- **`table.agg_instant_forex_funnel_daily` v1** (table_doc) - agg_instant_forex_funnel_daily: Auto-documented from the live schema: 6 columns; 640 rows at first observation. Columns: day, event, city, events_state, uniq_entities, sum_addon_value_inr. _[source: context_agent, confidence 1.00, refs: agg_instant_forex_funnel_daily]_
- **`table.mv_instant_forex_funnel_daily` v1** (table_doc) - mv_instant_forex_funnel_daily: Auto-documented from the live schema: 6 columns. Columns: day, event, city, events_state, uniq_entities, sum_addon_value_inr. _[source: context_agent, confidence 1.00, refs: mv_instant_forex_funnel_daily]_

### Updated

- **`business_def.instant_forex.funnel` v2** (business_def) - instant_forex funnel: Ordered steps on `atlys.f_instant_forex_events`: forex_offer_shown -> currency_selected -> amount_entered -> forex_added_to_cart -> forex_purchased (step order source: spec). Segment dimensions: client_lib, app_version, device_type, city, geoip_country_code, to_currency, destination, os. Event discriminator column: `event`. _[source: instrumentation_agent, confidence 1.00, refs: app_version, city, client_lib, destination, device_type, event, f_instant_forex_events, geoip_country_code, os, to_currency]_
- **`entity.instant_forex.entity_key` v2** (entity) - instant_forex entity key: user_id: The grain of `atlys.f_instant_forex_events` is `user_id` (confidence 0.70); secondary keys: application_id. Derived from the spec and the raw events by the instrumentation agent, not assumed. _[source: instrumentation_agent, confidence 0.70, refs: application_id, f_instant_forex_events, user_id]_
- **`table.f_instant_forex_events` v3** (table_doc) - f_instant_forex_events: Auto-documented from the live schema: 17 columns; 6,237 rows at first observation; ORDER BY (event, timestamp, user_id); PARTITION BY toYYYYMM(timestamp); TTL toDateTime(timestamp) + INTERVAL 18 MONTH; order_by rationale: ORDER BY (event, timestamp, user_id). The 8 existing tables use (id, timestamp, user_id); id is unique, so the primary index prunes nothing for queries that filter by time and segment and never by id. Leading with the event discriminator (5 values) prunes hard and compresses well, timestamp second matches every time-windowed query, and user_id last keeps each entity's step sequence co-located for windowFunnel.. Columns: addon_value_inr, amount, app_version, application_id, city, client_lib, destination, device_type, event, from_currency, fx_rate, geoip_country_code, id, os, timestamp, to_currency, user_id. _[source: context_agent, confidence 1.00, refs: f_instant_forex_events]_

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

#### [HIGH] `f_instant_forex_events` cannot be joined to the existing tables on `application_id`

- **Kind:** `join_assumption_violated` (detected by rule)
- **The context claims:** The documented join map asserts every table joins on `application_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.f_abandoned_checkout_recovery_events.segment_join, relationship.f_express_checkout_events.segment_join).
- **The data says:** `f_instant_forex_events` has 6237 rows, of which 0 (0.0%) carry `application_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 2900 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 3), ('city', 7), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.f_abandoned_checkout_recovery_events.segment_join`, `relationship.f_express_checkout_events.segment_join`, `relationship.f_group_family_events.segment_join`, `relationship.f_instant_forex_events.segment_join`
- **Proposed resolution:** Analytics must NOT join this table to the existing tables on `application_id`. Cross-reference at segment level only (app_version, city, client_lib and day). Corroborating query: SELECT count() AS shared_values FROM (SELECT DISTINCT app_version AS v FROM atlys.f_instant_forex_events WHERE app_version != '') a INNER JOIN (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.destination_card_clicked) b USING (v) -> app_version=3, city=7, client_lib=2

Verification SQL:

```sql
SELECT
  count() AS new_rows,
  countIf(application_id = '') AS anonymous_rows,
  round(countIf(application_id = '') / count(), 4) AS anonymous_frac,
  uniqIf(application_id, application_id != '') AS distinct_identities,
  countIf(application_id != '' AND application_id IN (SELECT ifNull(application_id, '') FROM atlys.destination_card_clicked)) AS rows_joinable_to_destination_card_clicked,
  countIf(application_id != '' AND application_id IN (SELECT ifNull(application_id, '') FROM atlys.search_typed)) AS rows_joinable_to_search_typed
FROM atlys.f_instant_forex_events
```

Result: `[{"new_rows": 6237, "anonymous_rows": 0, "anonymous_frac": 0.0, "distinct_identities": 2900, "rows_joinable_to_destination_card_clicked": 0, "rows_joinable_to_search_typed": 0}]`

#### [HIGH] `f_instant_forex_events` cannot be joined to the existing tables on `user_id`

- **Kind:** `join_assumption_violated` (detected by rule)
- **The context claims:** The documented join map asserts every table joins on `user_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.f_abandoned_checkout_recovery_events.segment_join, relationship.f_express_checkout_events.segment_join).
- **The data says:** `f_instant_forex_events` has 6237 rows, of which 0 (0.0%) carry `user_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 2900 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 3), ('city', 7), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.f_abandoned_checkout_recovery_events.segment_join`, `relationship.f_express_checkout_events.segment_join`, `relationship.f_group_family_events.segment_join`, `relationship.f_instant_forex_events.segment_join`
- **Proposed resolution:** Analytics must NOT join this table to the existing tables on `user_id`. Cross-reference at segment level only (app_version, city, client_lib and day). Corroborating query: SELECT count() AS shared_values FROM (SELECT DISTINCT app_version AS v FROM atlys.f_instant_forex_events WHERE app_version != '') a INNER JOIN (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.destination_card_clicked) b USING (v) -> app_version=3, city=7, client_lib=2

Verification SQL:

```sql
SELECT
  count() AS new_rows,
  countIf(user_id = '') AS anonymous_rows,
  round(countIf(user_id = '') / count(), 4) AS anonymous_frac,
  uniqIf(user_id, user_id != '') AS distinct_identities,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.destination_card_clicked)) AS rows_joinable_to_destination_card_clicked,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.search_typed)) AS rows_joinable_to_search_typed
FROM atlys.f_instant_forex_events
```

Result: `[{"new_rows": 6237, "anonymous_rows": 0, "anonymous_frac": 0.0, "distinct_identities": 2900, "rows_joinable_to_destination_card_clicked": 0, "rows_joinable_to_search_typed": 0}]`

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

- join_assumption_violated: `f_instant_forex_events` cannot be joined to the existing tables on `application_id`
- join_assumption_violated: `f_instant_forex_events` cannot be joined to the existing tables on `user_id`
- uncomputable_metric: 'Conversion rate' is not computable as defined
- uncomputable_metric: 'On-time delivery rate' is documented as a metric but cannot be computed here
- undefined_term: 'sessions' is used in a metric definition but never defined

## Unanswered questions

- Attach rate: offer_shown → forex_purchased, overall and by `destination`.
- AOV uplift: distribution of `addon_value_inr` among attachers.
- Where is the drop — offer → amount_entered, or added_to_cart → purchased?
- Which destinations / currencies attach best; any segment (device/geo) skew?

## How this feature was read (provenance)

- **Entity key** `user_id` - user_id: present on 5/5 event types, 100.0% of rows, 2,900 distinct values, 36% of values span >1 step. Runner-up application_id (5/5 event types, 100.0% rows); decided on first mention order in spec.md. Co-extensive alternatives application_id partition the rows identically (2,900 values, same coverage), so every funnel and ORDER BY is numerically identical whichever is chosen -- the pick is arbitrary but harmless, hence confidence is not penalised below 0.80. Row-unique id columns were excluded as entity keys (house_rules.md section 2). [confidence=0.80]
- **Funnel derived as** forex_offer_shown -> currency_selected -> amount_entered -> forex_added_to_cart -> forex_purchased
- **Derivation method:** [source=spec] spec bullets named 5/5 observed event types. agreement spec~timestamp=1.00, spec~volume=0.90, volume~timestamp=0.90; pairwise timestamp decisiveness=0.97 over 7,458 ordered entity pairs. volume order inverts currency_selected<->amount_entered vs the spec (expected where steps share a count). volume order=forex_offer_shown > amount_entered > currency_selected > forex_added_to_cart > forex_purchased. timestamp order=forex_offer_shown > currency_selected > amount_entered > forex_added_to_cart > forex_purchased.
- **Event types:** `forex_offer_shown` (2,900), `currency_selected` (1,033), `amount_entered` (1,033), `forex_added_to_cart` (725), `forex_purchased` (546)
- **Raw events profiled:** 6,237 across 17 distinct fields

---

_Generated by the Atlys agentic analytics pipeline, run `7534cf5b2bde4111977eeb3720af7e38`, context layer v8._
