# Insight report - status_sharing

> ### Scanned 698,049 rows / 29.1 MB in ClickHouse; sent 272 rows to the model.
> 
> That is 698.05K rows aggregated in the database against 272 aggregate rows crossing into the prompt -- a **2,566x** reduction before a single token was spent.
> Total model tokens for the whole run: **0**.
> 
> Scan figures are `read_rows` / `read_bytes` for this run's queries, summed from `system.query_log` by `query_id` -- measured, not estimated.

| | |
| --- | --- |
| Run id | `84d55343f482409b832cfa720c7f848f` |
| Feature | `status_sharing` (Visa Status Sharing) |
| Trace | [https://us.cloud.langfuse.com/trace/af793f629f285963e9ec3a4f6aacb7f6](https://us.cloud.langfuse.com/trace/af793f629f285963e9ec3a4f6aacb7f6) |
| Context version used | **v6** (diff v5 -> v6) |
| Feature table | `f_status_sharing_events` |
| Rows loaded | 6,503 of 6,503 read |
| Event window | 2026-06-08 06:00:00 -> 2026-07-01 09:21:00 |
| Entity key | `share_id` |

## Stage status

| # | stage | status | detail |
| ---: | --- | --- | --- |
| 1 | `context.load` | ok | 133 entries |
| 2 | `instrumentation` | ok | 6503 rows into f_status_sharing_events |
| 3 | `context.reconcile` | ok | 8 contradictions |
| 4 | `analytics` | ok | 8 findings, 3 ungrounded |
| 5 | `report` | ok | this document and its sibling artifacts |

## Executive summary

- Deterministic fallback analysis of status_sharing over 6503 events (2026-06-08 to 2026-07-01).
- 8 finding(s) below, each scored by the same published confidence formula as a normal run.
- No business mechanism is attached to any of them because the interpretation model was unavailable.

_8 findings: 3 WATCH, 5 INFO._

**Read these findings with the following caveats:**
- 3 finding(s) failed numeric grounding and were demoted to informational; their numbers do not appear in the queries they cite.
- Interpretation LLM unavailable (RuntimeError: analytics.interpret: failed to produce a valid DraftReport: RuntimeError: claude CLI failed (1): ); findings below were computed deterministically in Python from the same aggregates.
- Identity coverage: `application_id` is empty on 40.2% of rows across the feature table. It is empty on up to 100% of rows within a single event type, so whole events carry no identity at all. Those rows are unattributed, not anonymous users; every distinct count over `application_id` uses uniqIf(col, col != '') and is therefore a floor.
- Identity coverage: `user_id` is empty on 40.2% of rows across the feature table. It is empty on up to 100% of rows within a single event type, so whole events carry no identity at all. Those rows are unattributed, not anonymous users; every distinct count over `user_id` uses uniqIf(col, col != '') and is therefore a floor.
- Feature identities have no overlap with the 8 production tables, so all cross-referencing here is segment-level (shared vocabulary + calendar), never a join.
- Query plan came from the deterministic fallback, not the planner LLM (RuntimeError: analytics.plan_queries: failed to produce a valid QueryPlan: RuntimeError: claude CLI failed (1): ); coverage of the PM's questions may be narrower than requested.

## Findings

Ordered by severity, then by confidence. Every confidence score below is shown with its four components so the arithmetic can be checked without reading code.

| # | severity | headline | metric | value | confidence |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | WATCH | destination=TR converts at 0.0% vs 2.2% for everyone else | `step_through_rate` | 0.0224 | 0.80 |
| 2 | WATCH | client_lib=web-js converts at 0.3% vs 2.5% for everyone else | `step_through_rate` | 0.0211 | 0.78 |
| 3 | WATCH | destination=EG converts at 40.3% vs 61.0% for US | `step_through_rate` | 0.2068 | 0.73 |
| 4 | INFO | 27.88% of 1600 share_ids reach recipient_cta_clicked | `funnel_completion_rate` | 0.2787 | 0.77 |
| 5 | INFO | channel=copy_link converts at 46.1% vs 52.3% for whatsapp | `step_through_rate` | 0.0621 | 0.73 |
| 6 | INFO | client_lib=web-js converts at 81.4% vs 88.0% for mobile-rn | `step_through_rate` | 0.0661 | 0.25 |
| 7 | INFO | destination=GR converts at 51.7% vs 72.0% for FR | `step_through_rate` | 0.2033 | 0.25 |
| 8 | INFO | destination=US converts at 77.4% vs 94.9% for ID | `step_through_rate` | 0.1758 | 0.25 |

### 1. [WATCH] destination=TR converts at 0.0% vs 2.2% for everyone else

**Metric:** `step_through_rate` = **0.0224** (TR vs everyone else) | segment: destination=TR  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** destination=TR on share_clicked -> recipient_cta_clicked converts at 0.00% (0/126) against 2.24% (33/1474) for everyone else -- a 2.24% absolute gap.

**Why:** Mechanism not established by this query (hypothesis, unverified).
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** If the gap is causal, lifting TR to the everyone else rate would recover about 2 entities.

**Recommended action:** Check destination=TR against the known-issues log before assuming a product cause; if nothing matches, instrument that transition directly.

**Confidence 0.80** (method: `two_proportion_ztest`, n = 126, p = 0.0897)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.70 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.91 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.80** | |

Check the arithmetic: arithmetic mean = 0.8026, geometric mean = 0.7864, product = 0.3824. This reproduces the published score via **arithmetic mean** (delta 0.0005).

**Supporting queries:** `t04_segment_vs_baseline_destination`

**Caveats:**
- Generated without the interpretation LLM; no business mechanism attached.

### 2. [WATCH] client_lib=web-js converts at 0.3% vs 2.5% for everyone else

**Metric:** `step_through_rate` = **0.0211** (web-js vs everyone else) | segment: client_lib=web-js  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** client_lib=web-js on share_clicked -> recipient_cta_clicked converts at 0.34% (1/294) against 2.45% (32/1306) for everyone else -- a 2.11% absolute gap.

**Why:** Mechanism not established by this query (hypothesis, unverified).
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** If the gap is causal, lifting web-js to the everyone else rate would recover about 6 entities.

**Recommended action:** Check client_lib=web-js against the known-issues log before assuming a product cause; if nothing matches, instrument that transition directly.

**Confidence 0.78** (method: `two_proportion_ztest`, n = 294, p = 0.0215)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.82 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.98 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 0.60 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.78** | |

Check the arithmetic: arithmetic mean = 0.7498, geometric mean = 0.7331, product = 0.2888. This does **not** match a standard aggregation; closest is arithmetic mean at 0.7498 (delta 0.0302) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t04_segment_vs_baseline_client_lib`

**Caveats:**
- Generated without the interpretation LLM; no business mechanism attached.

### 3. [WATCH] destination=EG converts at 40.3% vs 61.0% for US

**Metric:** `step_through_rate` = **0.2068** (EG vs US) | segment: destination=EG  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** destination=EG on 4 link_opened converts at 40.30% (27/67) against 60.98% (25/41) for US -- a 20.68% absolute gap.

**Why:** Mechanism not established by this query (hypothesis, unverified).
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** If the gap is causal, lifting EG to the US rate would recover about 13 entities.

**Recommended action:** Check destination=EG against the known-issues log before assuming a product cause; if nothing matches, instrument that transition directly.

**Confidence 0.73** (method: `two_proportion_ztest`, n = 41, p = 0.0369)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.40 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.96 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.73** | |

Check the arithmetic: arithmetic mean = 0.7408, geometric mean = 0.6934, product = 0.2311. This does **not** match a standard aggregation; closest is arithmetic mean at 0.7408 (delta 0.0119) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t03_funnel_by_destination`

**Caveats:**
- Generated without the interpretation LLM; no business mechanism attached.

### 4. [INFO] 27.88% of 1600 share_ids reach recipient_cta_clicked

**Metric:** `funnel_completion_rate` = **0.2787**  
**Metric definition used:** `metric.conversion_rate@v2` (exact context entry + version)

**What:** 1600 distinct share_id values entered the funnel and 446 reached recipient_cta_clicked (27.88%). The single worst transition is into recipient_cta_clicked (7.40% step-through).

**Why:** Baseline volume only; no mechanism tested (hypothesis, unverified).
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** This is the denominator every segment cut below is measured against.

**Recommended action:** Agree with the PM that recipient_cta_clicked is the right success event before this number becomes a target, then dig into the drop into recipient_cta_clicked.

**Confidence 0.77** (method: `descriptive`, n = 1,600)

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

### 5. [INFO] channel=copy_link converts at 46.1% vs 52.3% for whatsapp

**Metric:** `step_through_rate` = **0.0621** (copy_link vs whatsapp) | segment: channel=copy_link  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** channel=copy_link on 4 link_opened converts at 46.11% (77/167) against 52.32% (248/474) for whatsapp -- a 6.21% absolute gap.

**Why:** Mechanism not established by this query (hypothesis, unverified).
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** If the gap is causal, lifting copy_link to the whatsapp rate would recover about 10 entities.

**Recommended action:** Check channel=copy_link against the known-issues log before assuming a product cause; if nothing matches, instrument that transition directly.

**Confidence 0.73** (method: `two_proportion_ztest`, n = 167, p = 0.1673)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.74 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.83 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 0.71 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.73** | |

Check the arithmetic: arithmetic mean = 0.7202, geometric mean = 0.7153, product = 0.2617. This does **not** match a standard aggregation; closest is arithmetic mean at 0.7202 (delta 0.0133) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t03_funnel_by_channel`

**Caveats:**
- Generated without the interpretation LLM; no business mechanism attached.

### 6. [INFO] client_lib=web-js converts at 81.4% vs 88.0% for mobile-rn

**Metric:** `step_through_rate` = **0.0661** (web-js vs mobile-rn) | segment: client_lib=web-js  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** client_lib=web-js on 3 link_generated converts at 81.42% (149/183) against 88.03% (728/827) for mobile-rn -- a 6.61% absolute gap.

**Why:** Mechanism not established by this query (hypothesis, unverified).
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** If the gap is causal, lifting web-js to the mobile-rn rate would recover about 12 entities.

**Recommended action:** Check client_lib=web-js against the known-issues log before assuming a product cause; if nothing matches, instrument that transition directly.

**Confidence 0.25** (method: `two_proportion_ztest`, n = 183, p = 0.0167)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.75 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.98 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 0.60 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.25** | |

Check the arithmetic: arithmetic mean = 0.7339, geometric mean = 0.7182, product = 0.2660. This does **not** match a standard aggregation; closest is product at 0.2660 (delta 0.0160) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t03_funnel_by_client_lib`

**Caveats:**
- UNVERIFIED: this finding's headline number could not be matched to its own cited query results (asserts step_through_rate=0.066083, which does not appear in t03_funnel_by_client_lib). Treat as a lead, not a fact.
- Generated without the interpretation LLM; no business mechanism attached.

### 7. [INFO] destination=GR converts at 51.7% vs 72.0% for FR

**Metric:** `step_through_rate` = **0.2033** (GR vs FR) | segment: destination=GR  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** destination=GR on 2 channel_selected converts at 51.67% (62/120) against 72.00% (72/100) for FR -- a 20.33% absolute gap.

**Why:** Mechanism not established by this query (hypothesis, unverified).
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** If the gap is causal, lifting GR to the FR rate would recover about 24 entities.

**Recommended action:** Check destination=GR against the known-issues log before assuming a product cause; if nothing matches, instrument that transition directly.

**Confidence 0.25** (method: `two_proportion_ztest`, n = 100, p = 0.0021)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.67 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 1.00 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.25** | |

Check the arithmetic: arithmetic mean = 0.8161, geometric mean = 0.7949, product = 0.3992. This does **not** match a standard aggregation; closest is product at 0.3992 (delta 0.1492) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t03_funnel_by_destination`

**Caveats:**
- UNVERIFIED: this finding's headline number could not be matched to its own cited query results (asserts step_through_rate=0.203333, which does not appear in t03_funnel_by_destination). Treat as a lead, not a fact.
- Generated without the interpretation LLM; no business mechanism attached.

### 8. [INFO] destination=US converts at 77.4% vs 94.9% for ID

**Metric:** `step_through_rate` = **0.1758** (US vs ID) | segment: destination=US  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** destination=US on 3 link_generated converts at 77.36% (41/53) against 94.94% (75/79) for ID -- a 17.58% absolute gap.

**Why:** Mechanism not established by this query (hypothesis, unverified).
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** If the gap is causal, lifting US to the ID rate would recover about 9 entities.

**Recommended action:** Check destination=US against the known-issues log before assuming a product cause; if nothing matches, instrument that transition directly.

**Confidence 0.25** (method: `two_proportion_ztest`, n = 53, p = 0.0024)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.40 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 1.00 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.25** | |

Check the arithmetic: arithmetic mean = 0.7494, geometric mean = 0.6995, product = 0.2394. This does **not** match a standard aggregation; closest is product at 0.2394 (delta 0.0106) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t03_funnel_by_destination`

**Caveats:**
- UNVERIFIED: this finding's headline number could not be matched to its own cited query results (asserts step_through_rate=0.175782, which does not appear in t03_funnel_by_destination). Treat as a lead, not a fact.
- Generated without the interpretation LLM; no business mechanism attached.

## Schema generated for this feature

| | |
| --- | --- |
| Table | `f_status_sharing_events` |
| Engine | `MergeTree` |
| ORDER BY | `(event, timestamp, share_id)` |
| PARTITION BY | `toYYYYMM(timestamp)` |
| TTL | `toDateTime(timestamp) + INTERVAL 18 MONTH` |
| Columns | 17 (11 LowCardinality, 0 Nullable, 5 with a codec) |
| Materialized views | 1 |

**Table settings:** `ratio_of_defaults_for_sparse_serialization = 0.8333`, `index_granularity = 8192`

### Columns

| column | type | source path | codec | note |
| --- | --- | --- | --- | --- |
| `app_version` | `LowCardinality(String)` | `app_version` | `-` | events: share_clicked,channel_selected,link_generated; coverage=0.60; distinct=3 |
| `application_id` | `String` | `application_id` | `(ZSTD(1))` | events: share_clicked,channel_selected,link_generated; coverage=0.60; distinct=1600 |
| `channel` | `LowCardinality(String)` | `channel` | `-` | events: link_opened,channel_selected,link_generated; coverage=0.71; distinct=4 |
| `city` | `LowCardinality(String)` | `city` | `-` | events: share_clicked,channel_selected,link_generated; coverage=0.60; distinct=7 |
| `client_lib` | `LowCardinality(String)` | `client_lib` | `-` | events: share_clicked,channel_selected,link_generated; coverage=0.60; distinct=2 |
| `cta` | `LowCardinality(String)` | `cta` | `-` | events: recipient_cta_clicked; coverage=0.05; distinct=1 |
| `destination` | `LowCardinality(String)` | `destination` | `-` | events: link_opened,share_clicked,channel_selected,link_generated,recipient_cta_clicked; coverage=1.00; distinct=14 |
| `device_type` | `LowCardinality(String)` | `device_type` | `-` | events: share_clicked,channel_selected,link_generated; coverage=0.60; distinct=4 |
| `event` | `LowCardinality(String)` | `event` | `-` | events: link_opened,share_clicked,channel_selected,link_generated,recipient_cta_clicked; coverage=1.00; distinct=5 |
| `geoip_country_code` | `LowCardinality(String)` | `geoip_country_code` | `-` | events: share_clicked,channel_selected,link_generated; coverage=0.60; distinct=7 |
| `id` | `String` | `id` | `(ZSTD(1))` | events: link_opened,share_clicked,channel_selected,link_generated,recipient_cta_clicked; coverage=1.00; distinct=6503 |
| `os` | `LowCardinality(String)` | `os` | `-` | events: share_clicked,channel_selected,link_generated; coverage=0.57; distinct=4 |
| `recipient_is_new_user` | `UInt8` | `recipient_is_new_user` | `-` | events: link_opened; coverage=0.36; distinct=2 |
| `share_id` | `String` | `share_id` | `(ZSTD(1))` | events: link_opened,share_clicked,channel_selected,link_generated,recipient_cta_clicked; coverage=1.00; distinct=1600 |
| `status_shared` | `LowCardinality(String)` | `status_shared` | `-` | events: share_clicked,channel_selected,link_generated; coverage=0.60; distinct=3 |
| `timestamp` | `DateTime64(3)` | `timestamp` | `(Delta, ZSTD(1))` | events: link_opened,share_clicked,channel_selected,link_generated,recipient_cta_clicked; coverage=1.00; distinct=3915 |
| `user_id` | `String` | `user_id` | `(ZSTD(1))` | events: share_clicked,channel_selected,link_generated; coverage=0.60; distinct=1600 |

### Rationale, decision by decision

**`order_by`** - ORDER BY (event, timestamp, share_id). The 8 existing tables use (id, timestamp, user_id); id is unique, so the primary index prunes nothing for queries that filter by time and segment and never by id. Leading with the event discriminator (5 values) prunes hard and compresses well, timestamp second matches every time-windowed query, and share_id last keeps each entity's step sequence co-located for windowFunnel.

**`partition_by`** - toYYYYMM(timestamp), matching the existing tables so cross-table segment queries prune consistently. Daily partitions would create thousands of tiny parts at this volume and slow merges for no pruning benefit over a monthly part.

**`types`** - E=5 event types in one wide table, so an event-scoped column is ~(1 - 1/5) = 0.80 defaults -- under ClickHouse's 0.9375 sparse threshold, so it would stay dense. ratio_of_defaults_for_sparse_serialization is set to min(0.9, 1 - 1/(E+1)) = 0.8333 so those columns actually go sparse. id is a 32-char hex string with no dashes and is typed String, not UUID, which would reject the literal outright. timestamp is DateTime64(3) because the source carries milliseconds. Enums are LowCardinality(String); high-cardinality ids are plain String with ZSTD(1); currency-denominated values are Decimal(18,4) so sums are exact; genuinely approximate ratios stay Float64.

**`nullable`** - No Nullable columns. A null map is a second column to read and it weakens index usage on exactly the columns we filter by; absent values use DEFAULT ''/0 instead. The trap this creates is recorded, not ignored: partial-coverage identity columns are ['application_id', 'user_id'], and every distinct-user metric on them must be uniqIf(col, col != '') because a bare uniq() would count the empty string as a real user.

**`ttl`** - TTL toDateTime(timestamp) + INTERVAL 18 MONTH on raw events, paired with a rollup that has no TTL. That pairing is what makes the MV worth its cost: the aggregate outlives raw expiry, so long-range trend queries keep answering.

**`mvs`** - One daily per-step, per-segment rollup. Dimensions are chosen under a row budget (days x event types x cardinality <= row_count/8) so the rollup is materially smaller than the source; anything that fails the 5x measured reduction gate after load is dropped with the number recorded. At sample volume the MV is unnecessary; it is justified against projected annual volume, not against these rows.

**`contrast_with_legacy`** - One wide table per feature instead of one table per event: every PM question here is a within-feature funnel, which is one windowFunnel on a wide table and an N-way join on the legacy shape. The existing one-table-per-event layout is an SDK artifact, not a design decision, and the id-first sorting key is a bug we do not copy.

**`generation_log`** - attempt 0: LLM call failed: propose_ddl:status_sharing: failed to produce a valid DDLProposal: RuntimeError: claude CLI failed (1):  ; fell back to the deterministic rule-based proposal ; fallback dry run ok=True 

### How this differs from the legacy event tables

One wide table per feature instead of one table per event: every PM question here is a within-feature funnel, which is one windowFunnel on a wide table and an N-way join on the legacy shape. The existing one-table-per-event layout is an SDK artifact, not a design decision, and the id-first sorting key is a bug we do not copy.

Structural differences a reviewer can verify directly against `SHOW CREATE TABLE` on any of the 8 pre-existing tables:

| dimension | legacy event tables | this feature table |
| --- | --- | --- |
| shape | one table per event type | one wide table per feature, `event` as the discriminator |
| ORDER BY | leads with the unique `id`, so the primary index cannot prune the time/segment filters that are actually run | `(event, timestamp, share_id)` |
| Nullable | nearly every column Nullable, costing a null map and weakening the index | 0 of 17 columns Nullable |
| enum columns | plain `String` | 11 columns as `LowCardinality(String)` |
| codecs | none declared | 5 columns carry an explicit codec |
| retention | none | `toDateTime(timestamp) + INTERVAL 18 MONTH`, paired with a rollup that outlives raw expiry |

### Generated DDL

```sql
CREATE TABLE IF NOT EXISTS f_status_sharing_events
(
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version; events: share_clicked,channel_selected,link_generated; coverage=0.60; distinct=3',
    `application_id` String DEFAULT '' COMMENT 'json_path=application_id; events: share_clicked,channel_selected,link_generated; coverage=0.60; distinct=1600' CODEC(ZSTD(1)),
    `channel` LowCardinality(String) DEFAULT '' COMMENT 'json_path=channel; events: link_opened,channel_selected,link_generated; coverage=0.71; distinct=4',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city; events: share_clicked,channel_selected,link_generated; coverage=0.60; distinct=7',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib; events: share_clicked,channel_selected,link_generated; coverage=0.60; distinct=2',
    `cta` LowCardinality(String) DEFAULT '' COMMENT 'json_path=cta; events: recipient_cta_clicked; coverage=0.05; distinct=1',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination; events: link_opened,share_clicked,channel_selected,link_generated,recipient_cta_clicked; coverage=1.00; distinct=14',
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type; events: share_clicked,channel_selected,link_generated; coverage=0.60; distinct=4',
    `event` LowCardinality(String) DEFAULT '' COMMENT 'json_path=event; events: link_opened,share_clicked,channel_selected,link_generated,recipient_cta_clicked; coverage=1.00; distinct=5',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code; events: share_clicked,channel_selected,link_generated; coverage=0.60; distinct=7',
    `id` String DEFAULT '' COMMENT 'json_path=id; events: link_opened,share_clicked,channel_selected,link_generated,recipient_cta_clicked; coverage=1.00; distinct=6503' CODEC(ZSTD(1)),
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; events: share_clicked,channel_selected,link_generated; coverage=0.57; distinct=4',
    `recipient_is_new_user` UInt8 DEFAULT 0 COMMENT 'json_path=recipient_is_new_user; events: link_opened; coverage=0.36; distinct=2',
    `share_id` String DEFAULT '' COMMENT 'json_path=share_id; events: link_opened,share_clicked,channel_selected,link_generated,recipient_cta_clicked; coverage=1.00; distinct=1600' CODEC(ZSTD(1)),
    `status_shared` LowCardinality(String) DEFAULT '' COMMENT 'json_path=status_shared; events: share_clicked,channel_selected,link_generated; coverage=0.60; distinct=3',
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp; events: link_opened,share_clicked,channel_selected,link_generated,recipient_cta_clicked; coverage=1.00; distinct=3915' CODEC(Delta, ZSTD(1)),
    `user_id` String DEFAULT '' COMMENT 'json_path=user_id; events: share_clicked,channel_selected,link_generated; coverage=0.60; distinct=1600' CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, share_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.8333, index_granularity = 8192;

CREATE TABLE IF NOT EXISTS agg_status_sharing_funnel_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, channel)
EMPTY AS
SELECT
    toDate(timestamp) AS day,
    event,
    channel,
    countState() AS events_state,
    uniqStateIf(share_id, share_id != '') AS uniq_entities,
    uniqStateIf(user_id, user_id != '') AS uniq_users
FROM f_status_sharing_events
GROUP BY day, event, channel;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_status_sharing_funnel_daily
TO agg_status_sharing_funnel_daily AS
SELECT
    toDate(timestamp) AS day,
    event,
    channel,
    countState() AS events_state,
    uniqStateIf(share_id, share_id != '') AS uniq_entities,
    uniqStateIf(user_id, user_id != '') AS uniq_users
FROM f_status_sharing_events
GROUP BY day, event, channel;
```

### Materialized views: measured, then kept or dropped

| materialized view | target table | source rows | target rows | reduction | verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `mv_status_sharing_funnel_daily` | `agg_status_sharing_funnel_daily` | 6,503 | 305 | 21.3x | **KEPT** |

The gate is a measured 5x reduction. An MV dropped **with** its measurement is a stronger result than one kept on faith.

**`mv_status_sharing_funnel_daily`** - Daily per-step, per-segment funnel counters. Every PM question in this spec is 'step X -> step Y, cut by a segment, over time', which this answers by reading the rollup instead of the raw stream. It is also the retention pair for the raw TTL: raw events expire at 18 months, this survives, so long-range trend queries keep working on a fraction of the bytes. Distinct counts are stored as uniqState and must be read with uniqMerge -- summing distinct counts across parts is wrong.
- serves PM question: _Share rate, and does it vary by `status_shared` (do approvals get shared more)?_
- serves PM question: _Channel mix, and which channel drives the most **new-user** opens?_
- serves PM question: _Recipient → new-application conversion (a K-factor): opens → `recipient_cta_clicked` among `recipient_is_new_user`._
- serves PM question: _Which destinations spread most?_

## Context changes this run

Context layer moved **v5 -> v6**: 24 added, 0 updated, 0 superseded, 8 contradictions, 5 gaps.

### Added

- **`business_def.status_sharing.funnel` v1** (business_def) - status_sharing funnel: Ordered steps on `atlys.f_status_sharing_events`: share_clicked -> channel_selected -> link_generated -> link_opened -> recipient_cta_clicked (step order source: spec). Segment dimensions: destination, channel, client_lib, app_version, status_shared, device_type, city, geoip_country_code. Event discriminator column: `event`. _[source: instrumentation_agent, confidence 1.00, refs: app_version, channel, city, client_lib, destination, device_type, event, f_status_sharing_events, geoip_country_code, status_shared]_
- **`column.f_status_sharing_events.app_version` v1** (column_doc) - f_status_sharing_events.app_version: app_version LowCardinality(String) on f_status_sharing_events. _[source: context_agent, confidence 1.00, refs: app_version, f_status_sharing_events]_
- **`column.f_status_sharing_events.application_id` v1** (column_doc) - f_status_sharing_events.application_id: application_id String on f_status_sharing_events. _[source: context_agent, confidence 1.00, refs: application_id, f_status_sharing_events]_
- **`column.f_status_sharing_events.channel` v1** (column_doc) - f_status_sharing_events.channel: channel LowCardinality(String) on f_status_sharing_events. _[source: context_agent, confidence 1.00, refs: channel, f_status_sharing_events]_
- **`column.f_status_sharing_events.city` v1** (column_doc) - f_status_sharing_events.city: city LowCardinality(String) on f_status_sharing_events. _[source: context_agent, confidence 1.00, refs: city, f_status_sharing_events]_
- **`column.f_status_sharing_events.client_lib` v1** (column_doc) - f_status_sharing_events.client_lib: client_lib LowCardinality(String) on f_status_sharing_events. _[source: context_agent, confidence 1.00, refs: client_lib, f_status_sharing_events]_
- **`column.f_status_sharing_events.cta` v1** (column_doc) - f_status_sharing_events.cta: cta LowCardinality(String) on f_status_sharing_events. _[source: context_agent, confidence 1.00, refs: cta, f_status_sharing_events]_
- **`column.f_status_sharing_events.destination` v1** (column_doc) - f_status_sharing_events.destination: destination LowCardinality(String) on f_status_sharing_events. _[source: context_agent, confidence 1.00, refs: destination, f_status_sharing_events]_
- **`column.f_status_sharing_events.device_type` v1** (column_doc) - f_status_sharing_events.device_type: device_type LowCardinality(String) on f_status_sharing_events. _[source: context_agent, confidence 1.00, refs: device_type, f_status_sharing_events]_
- **`column.f_status_sharing_events.event` v1** (column_doc) - f_status_sharing_events.event: event LowCardinality(String) on f_status_sharing_events. _[source: context_agent, confidence 1.00, refs: event, f_status_sharing_events]_
- **`column.f_status_sharing_events.geoip_country_code` v1** (column_doc) - f_status_sharing_events.geoip_country_code: geoip_country_code LowCardinality(String) on f_status_sharing_events. _[source: context_agent, confidence 1.00, refs: f_status_sharing_events, geoip_country_code]_
- **`column.f_status_sharing_events.id` v1** (column_doc) - f_status_sharing_events.id: id String on f_status_sharing_events. _[source: context_agent, confidence 1.00, refs: f_status_sharing_events, id]_
- **`column.f_status_sharing_events.os` v1** (column_doc) - f_status_sharing_events.os: os LowCardinality(String) on f_status_sharing_events. _[source: context_agent, confidence 1.00, refs: f_status_sharing_events, os]_
- **`column.f_status_sharing_events.recipient_is_new_user` v1** (column_doc) - f_status_sharing_events.recipient_is_new_user: recipient_is_new_user UInt8 on f_status_sharing_events. _[source: context_agent, confidence 1.00, refs: f_status_sharing_events, recipient_is_new_user]_
- **`column.f_status_sharing_events.share_id` v1** (column_doc) - f_status_sharing_events.share_id: share_id String on f_status_sharing_events. _[source: context_agent, confidence 1.00, refs: f_status_sharing_events, share_id]_
- **`column.f_status_sharing_events.status_shared` v1** (column_doc) - f_status_sharing_events.status_shared: status_shared LowCardinality(String) on f_status_sharing_events. _[source: context_agent, confidence 1.00, refs: f_status_sharing_events, status_shared]_
- **`column.f_status_sharing_events.timestamp` v1** (column_doc) - f_status_sharing_events.timestamp: timestamp DateTime64(3) on f_status_sharing_events. _[source: context_agent, confidence 1.00, refs: f_status_sharing_events, timestamp]_
- **`column.f_status_sharing_events.user_id` v1** (column_doc) - f_status_sharing_events.user_id: user_id String on f_status_sharing_events. _[source: context_agent, confidence 1.00, refs: f_status_sharing_events, user_id]_
- **`entity.status_sharing.entity_key` v1** (entity) - status_sharing entity key: share_id: The grain of `atlys.f_status_sharing_events` is `share_id` (confidence 0.70); secondary keys: application_id, user_id. Derived from the spec and the raw events by the instrumentation agent, not assumed. _[source: instrumentation_agent, confidence 0.70, refs: application_id, f_status_sharing_events, share_id, user_id]_
- **`gap.data_quality.f_status_sharing_events.application_id_join` v1** (gap) - data_quality: f_status_sharing_events.application_id is not joinable to the existing tables: MEASURED, not assumed. 40.2% of `f_status_sharing_events` rows have `application_id = ''` (anonymous events; empty string, not NULL). Rows joinable to the existing tables on `application_id`: destination_card_clicked=0, search_typed=0. Every identity-level metric on this table MUST use uniqIf(application_id, application_id != ''), and every cross-reference to the eight pre-existing tables MUST be segment-level (app_version, city, client_lib / day), never an identity join. Findings that compare this feature to the existing funnel must carry this as a caveat. _[source: context_agent, confidence 1.00, refs: application_id, destination_card_clicked, f_status_sharing_events, search_typed]_
- **`gap.data_quality.f_status_sharing_events.partial_identity` v1** (gap) - f_status_sharing_events: partial identity coverage: Columns with < 100% coverage on `f_status_sharing_events`: application_id, user_id. House rules forbid Nullable on hot columns, so these default to the empty string. Every distinct count over them MUST be uniqIf(col, col != ''); a bare uniq() would count '' as a real identity. Disconnected event types: none. _[source: instrumentation_agent, confidence 1.00, refs: application_id, f_status_sharing_events, user_id]_
- **`gap.data_quality.f_status_sharing_events.user_id_join` v1** (gap) - data_quality: f_status_sharing_events.user_id is not joinable to the existing tables: MEASURED, not assumed. 40.2% of `f_status_sharing_events` rows have `user_id = ''` (anonymous events; empty string, not NULL). Rows joinable to the existing tables on `user_id`: destination_card_clicked=0, search_typed=0. Every identity-level metric on this table MUST use uniqIf(user_id, user_id != ''), and every cross-reference to the eight pre-existing tables MUST be segment-level (app_version, city, client_lib / day), never an identity join. Findings that compare this feature to the existing funnel must carry this as a caveat. _[source: context_agent, confidence 1.00, refs: destination_card_clicked, f_status_sharing_events, search_typed, user_id]_
- **`relationship.f_status_sharing_events.segment_join` v1** (relationship) - f_status_sharing_events -> existing tables (segment-level only): `f_status_sharing_events` shares no identities with the eight pre-existing tables, but shares these segment vocabularies (measured overlap of distinct values against `destination_card_clicked`): `app_version` (3 shared values), `city` (7 shared values), `client_lib` (2 shared values). Join on those plus toDate(timestamp). This supersedes the documented user_id join map for feature tables. _[source: context_agent, confidence 1.00, refs: app_version, city, client_lib, destination_card_clicked, f_status_sharing_events]_
- **`table.f_status_sharing_events` v1** (table_doc) - f_status_sharing_events: Auto-documented from the live schema: 17 columns; 6,503 rows at first observation; ORDER BY (event, timestamp, share_id); PARTITION BY toYYYYMM(timestamp); TTL toDateTime(timestamp) + INTERVAL 18 MONTH; order_by rationale: ORDER BY (event, timestamp, share_id). The 8 existing tables use (id, timestamp, user_id); id is unique, so the primary index prunes nothing for queries that filter by time and segment and never by id. Leading with the event discriminator (5 values) prunes hard and compresses well, timestamp second matches every time-windowed query, and share_id last keeps each entity's step sequence co-located for windowFunnel.. Columns: app_version, application_id, channel, city, client_lib, cta, destination, device_type, event, geoip_country_code, id, os, recipient_is_new_user, share_id, status_shared, timestamp, user_id. _[source: context_agent, confidence 1.00, refs: f_status_sharing_events]_

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

#### [HIGH] `f_status_sharing_events` cannot be joined to the existing tables on `application_id`

- **Kind:** `join_assumption_violated` (detected by rule)
- **The context claims:** The documented join map asserts every table joins on `application_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.f_express_checkout_events.segment_join, relationship.f_group_family_events.segment_join).
- **The data says:** `f_status_sharing_events` has 6503 rows, of which 2615 (40.2%) carry `application_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 1600 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 3), ('city', 7), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.f_express_checkout_events.segment_join`, `relationship.f_group_family_events.segment_join`, `relationship.f_instant_forex_events.segment_join`, `relationship.funnel_order_timestamp_ascending`
- **Proposed resolution:** Analytics must NOT join this table to the existing tables on `application_id`. Cross-reference at segment level only (app_version, city, client_lib and day). Corroborating query: SELECT count() AS shared_values FROM (SELECT DISTINCT app_version AS v FROM atlys.f_status_sharing_events WHERE app_version != '') a INNER JOIN (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.destination_card_clicked) b USING (v) -> app_version=3, city=7, client_lib=2

Verification SQL:

```sql
SELECT
  count() AS new_rows,
  countIf(application_id = '') AS anonymous_rows,
  round(countIf(application_id = '') / count(), 4) AS anonymous_frac,
  uniqIf(application_id, application_id != '') AS distinct_identities,
  countIf(application_id != '' AND application_id IN (SELECT ifNull(application_id, '') FROM atlys.destination_card_clicked)) AS rows_joinable_to_destination_card_clicked,
  countIf(application_id != '' AND application_id IN (SELECT ifNull(application_id, '') FROM atlys.search_typed)) AS rows_joinable_to_search_typed
FROM atlys.f_status_sharing_events
```

Result: `[{"new_rows": 6503, "anonymous_rows": 2615, "anonymous_frac": 0.4021, "distinct_identities": 1600, "rows_joinable_to_destination_card_clicked": 0, "rows_joinable_to_search_typed": 0}]`

#### [HIGH] `f_status_sharing_events` cannot be joined to the existing tables on `user_id`

- **Kind:** `join_assumption_violated` (detected by rule)
- **The context claims:** The documented join map asserts every table joins on `user_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.f_express_checkout_events.segment_join, relationship.f_group_family_events.segment_join).
- **The data says:** `f_status_sharing_events` has 6503 rows, of which 2615 (40.2%) carry `user_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 1600 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 3), ('city', 7), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.f_express_checkout_events.segment_join`, `relationship.f_group_family_events.segment_join`, `relationship.f_instant_forex_events.segment_join`, `relationship.funnel_order_timestamp_ascending`
- **Proposed resolution:** Analytics must NOT join this table to the existing tables on `user_id`. Cross-reference at segment level only (app_version, city, client_lib and day). Corroborating query: SELECT count() AS shared_values FROM (SELECT DISTINCT app_version AS v FROM atlys.f_status_sharing_events WHERE app_version != '') a INNER JOIN (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.destination_card_clicked) b USING (v) -> app_version=3, city=7, client_lib=2

Verification SQL:

```sql
SELECT
  count() AS new_rows,
  countIf(user_id = '') AS anonymous_rows,
  round(countIf(user_id = '') / count(), 4) AS anonymous_frac,
  uniqIf(user_id, user_id != '') AS distinct_identities,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.destination_card_clicked)) AS rows_joinable_to_destination_card_clicked,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.search_typed)) AS rows_joinable_to_search_typed
FROM atlys.f_status_sharing_events
```

Result: `[{"new_rows": 6503, "anonymous_rows": 2615, "anonymous_frac": 0.4021, "distinct_identities": 1600, "rows_joinable_to_destination_card_clicked": 0, "rows_joinable_to_search_typed": 0}]`

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

- join_assumption_violated: `f_status_sharing_events` cannot be joined to the existing tables on `application_id`
- join_assumption_violated: `f_status_sharing_events` cannot be joined to the existing tables on `user_id`
- uncomputable_metric: 'Conversion rate' is not computable as defined
- uncomputable_metric: 'On-time delivery rate' is documented as a metric but cannot be computed here
- undefined_term: 'sessions' is used in a metric definition but never defined

## Unanswered questions

- Share rate, and does it vary by `status_shared` (do approvals get shared more)?
- Channel mix, and which channel drives the most **new-user** opens?
- Recipient → new-application conversion (a K-factor): opens → `recipient_cta_clicked` among `recipient_is_new_user`.
- Which destinations spread most?

## How this feature was read (provenance)

- **Entity key** `share_id` - share_id: present on 5/5 event types, 100.0% of rows, 1,600 distinct values, 72% of values span >1 step. Runner-up user_id (3/5 event types, 59.8% rows); decided on event-type coverage. Row-unique id columns were excluded as entity keys (house_rules.md section 2). [confidence=0.95]
- **Funnel derived as** share_clicked -> channel_selected -> link_generated -> link_opened -> recipient_cta_clicked
- **Derivation method:** [source=spec] spec bullets named 5/5 observed event types. agreement spec~timestamp=1.00, spec~volume=0.70, volume~timestamp=0.70; pairwise timestamp decisiveness=0.91 over 7,250 ordered entity pairs. volume order inverts share_clicked<->link_opened, channel_selected<->link_opened, link_generated<->link_opened vs the spec (expected where steps share a count). volume order=link_opened > share_clicked > channel_selected > link_generated > recipient_cta_clicked. timestamp order=share_clicked > channel_selected > link_generated > link_opened > recipient_cta_clicked.
- **Event types:** `share_clicked` (1,600), `channel_selected` (1,144), `link_generated` (1,144), `link_opened` (2,310), `recipient_cta_clicked` (305)
- **Raw events profiled:** 6,503 across 17 distinct fields
- **Partial-envelope events** (missing part of the standard envelope): `link_opened`, `recipient_cta_clicked`
- **Identity columns below 100% coverage** (all aggregation over these is guarded with `uniqIf(col, col != '')`): `application_id`, `user_id`

---

_Generated by the Atlys agentic analytics pipeline, run `84d55343f482409b832cfa720c7f848f`, context layer v6._
