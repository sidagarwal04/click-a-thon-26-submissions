# Insight report - express_checkout

> ### Scanned 179,830 rows / 4.7 MB in ClickHouse; sent 364 rows to the model.
> 
> That is 179.83K rows aggregated in the database against 364 aggregate rows crossing into the prompt -- a **494x** reduction before a single token was spent.
> Total model tokens for the whole run: **47,613**.
> 
> Scan figures are `read_rows` / `read_bytes` for this run's queries, summed from `system.query_log` by `query_id` -- measured, not estimated.

| | |
| --- | --- |
| Run id | `f0ee8056039147d59b1811b363005402` |
| Feature | `express_checkout` (Express Checkout) |
| Trace | [https://us.cloud.langfuse.com/trace/dd6eed844cef3136c9f225d3745acca3](https://us.cloud.langfuse.com/trace/dd6eed844cef3136c9f225d3745acca3) |
| Context version used | **v4** (diff v3 -> v4) |
| Feature table | `f_express_checkout_events` |
| Rows loaded | 5,507 of 5,507 read |
| Event window | 2026-06-08 06:00:00 -> 2026-06-28 23:11:00 |
| Entity key | `user_id` |

## Stage status

| # | stage | status | detail |
| ---: | --- | --- | --- |
| 1 | `context.load` | ok | 82 entries |
| 2 | `instrumentation` | ok | 5507 rows into f_express_checkout_events |
| 3 | `context.reconcile` | ok | 8 contradictions |
| 4 | `analytics` | ok | 4 findings, 0 ungrounded |
| 5 | `report` | ok | this document and its sibling artifacts |

## Executive summary

- Express checkout completes payment for 50.
- 7% of the 1,650 users who see it (836/1650).
- The single biggest leak is iOS: once users reach the OTP step, iOS confirms payment 16pp less often than Android (73.
- 8% vs 89.6%), consistent with the known iOS WebKit OTP autofill bug (K1).
- A second leak sits earlier: 39% of users who see Express never select it.

_4 findings: 1 ACT NOW, 2 WATCH, 1 INFO._

**Read these findings with the following caveats:**
- f_express_checkout_events shares no user_id/application_id identity with the core 8-table funnel (gap.data_quality.f_express_checkout_events.user_id_join / .application_id_join, both measured at 0.0% joinable); any comparison to standard checkout must be segment-level (app_version/city/client_lib/day), never an identity join.
- The t09_crossref_* 'baseline' columns are degenerate (100% in every row shown) and should not be used for lift claims this run.
- os is empty-string for 6.9% of rows (381/5507) — an unattributed bucket, not a real 'unknown OS' user cohort.
- saved_method_type (81.7% empty), currency (70.0% empty), and payment_currency (84.8% empty) are structurally empty for events before the step that populates them (selection / confirmation), not missing data.
- user_id and application_id coverage inside f_express_checkout_events itself is 100% (t01_volume_coverage, t10_data_quality), so counts and funnel numbers within this table are real counts, not floors.
- Feature identities have no overlap with the 8 production tables, so all cross-referencing here is segment-level (shared vocabulary + calendar), never a join.

## Findings

Ordered by severity, then by confidence. Every confidence score below is shown with its four components so the arithmetic can be checked without reading code.

| # | severity | headline | metric | value | confidence |
| ---: | --- | --- | --- | ---: | ---: |
| 1 | ACT NOW | iOS confirms payment in only 73.8% of OTP attempts vs 89.6% for Android (428 vs 269 users) | `otp_confirm_step_through_rate_by_os` | 0.7383 | 0.93 |
| 2 | WATCH | 39% of the 1,650 users shown Express (643 users) never select it | `selection_step_through_rate` | 0.6103 | 0.77 |
| 3 | WATCH | Express-vs-standard-checkout baseline is degenerate: 100% conversion in all 106 comparison rows | `express_vs_standard_baseline_conversion` | 1.0000 | 0.67 |
| 4 | INFO | India is 61% of Express volume (1,007 of 1,650 shown users); next-largest geo is 9% | `geo_adoption_share` | 0.6103 | 0.77 |

### 1. [ACT NOW] iOS confirms payment in only 73.8% of OTP attempts vs 89.6% for Android (428 vs 269 users)

**Metric:** `otp_confirm_step_through_rate_by_os` = **0.7383** (iOS 0.738318 vs Android 0.895911 (otp_entered -> express_payment_confirmed)) | segment: os=iOS  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** Among users who reached otp_entered, 73.8% of iOS users (316/428) went on to express_payment_confirmed, vs 89.6% of Android users (241/269). Full shown→confirmed completion is also lower for iOS: 45.0% (316/702) vs 56.6% for Android (241/426).

**Why:** known_issue.K1: iOS WebKit OTP autofill regression causes the payment OTP field to fail to autofill on recent iOS builds, and Express's otp_entered→express_payment_confirmed step is exactly the pay-step K1 says to watch on iOS.
  
_Context cited:_ `known_issue.K1@v1`

**So what:** iOS accounts for 702 of 1,650 Express-shown users (42.5%) — the single largest device cohort. A 16pp confirmation gap at the OTP step means a large share of Express's target users are being lost to a known, fixable bug, undercutting the feature's speed/simplicity pitch.

**Recommended action:** Escalate K1 with engineering as the likely root cause of the iOS OTP gap; ship an iOS fallback (manual OTP entry prompt when autofill fails) and re-pull this step-through cut after the fix to confirm the gap closes.

**Confidence 0.93** (method: `two_proportion_ztest`, n = 269, p = 0.0000)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.81 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 1.00 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 1.00 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 0.93 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.93** | |

Check the arithmetic: arithmetic mean = 0.9352, geometric mean = 0.9318, product = 0.7539. This reproduces the published score via **geometric mean** (delta 0.0027).

**Supporting queries:** `t03_funnel_by_os`, `t03_funnel_by_device_type`, `t04_segment_vs_baseline_os`

**Caveats:**
- os is empty for 6.9% of rows (381/5507, an unattributed bucket shown as '(unknown)' in t03/t04); those rows are folded into the 'rest' pool in t04, not used as a comparison arm.
- OTP-level otp_success was not broken out by segment in the frames provided; this finding uses the otp_entered->confirmed step as the closest available proxy.

### 2. [WATCH] 39% of the 1,650 users shown Express (643 users) never select it

**Metric:** `selection_step_through_rate` = **0.6103**  
**Metric definition used:** `metric.step_through_rate@v1` (exact context entry + version)

**What:** 1,007 of 1,650 users (61.0%) who saw express_checkout_shown went on to express_checkout_selected; 643 users (39.0%) dropped off at that first step, the largest single drop in the Express funnel (larger than the 16.9% drop from otp_entered to express_payment_confirmed).

**Why:** hypothesis, unverified
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** Downstream conversion from selection onward is strong (83.0% otp_entered->confirmed overall), so the ceiling on Express's impact is set almost entirely by this selection step, not by payment execution.

**Recommended action:** Instrument a decline/dismiss reason on express_checkout_shown (or run a lightweight exit prompt) and A/B test the offer's placement/copy to find and close the 39% non-selection gap.

**Confidence 0.77** (method: `descriptive`, n = 1,650)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 1.00 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.50 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.77** | |

Check the arithmetic: arithmetic mean = 0.7750, geometric mean = 0.7401, product = 0.3000. This does **not** match a standard aggregation; closest is arithmetic mean at 0.7750 (delta 0.0050) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t02_funnel_overall`

### 3. [WATCH] Express-vs-standard-checkout baseline is degenerate: 100% conversion in all 106 comparison rows

**Metric:** `express_vs_standard_baseline_conversion` = **1.0000** (baseline_rate == 1.0 in 106/106 visible rows)  
**Metric definition used:** `no context definition; ad-hoc` (exact context entry + version)

**What:** Across every visible row of t09_crossref_destination (16), t09_crossref_device_type (63, 3 more omitted), and t09_crossref_geoip_country_code (30) — 106 rows checked — baseline_converted_users equals baseline_top_users exactly, making the reported 'standard checkout' baseline_rate exactly 1.0 in every cut, with rate_gap always negative by construction.

**Why:** gap.data_quality.f_express_checkout_events.user_id_join and gap.data_quality.f_express_checkout_events.application_id_join document that this table shares no identity (user_id/application_id) with the core funnel tables; relationship.f_express_checkout_events.segment_join says any cross-reference must be segment-level only. A baseline built by reusing the same converted-user set as both its numerator and denominator is consistent with that missing-identity constraint being worked around incorrectly upstream.
  
_Context cited:_ `gap.data_quality.f_express_checkout_events.user_id_join@v1`, `gap.data_quality.f_express_checkout_events.application_id_join@v1`, `relationship.f_express_checkout_events.segment_join@v1`

**So what:** The PM's core question — does Express lift conversion vs standard checkout, and by how much — cannot be answered from this run's data. Any 'lift' number quoted from the t09_crossref rate_gap column right now is an artifact, not a real effect.

**Recommended action:** Send this to data engineering as a pipeline bug: the t09_crossref_* baseline computation needs to define 'standard checkout' as a genuinely separate segment-matched cohort (via app_version/city/client_lib/day per the documented join), not the already-converted set. Do not report an Express lift % until it's fixed.

**Confidence 0.67** (method: `descriptive`, n = 106)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 0.68 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.50 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.67** | |

Check the arithmetic: arithmetic mean = 0.6938, geometric mean = 0.6708, product = 0.2025. This reproduces the published score via **geometric mean** (delta 0.0017).

**Supporting queries:** `t09_crossref_destination`, `t09_crossref_device_type`, `t09_crossref_geoip_country_code`

**Caveats:**
- This is a data-quality finding about the frames themselves, not a business result — treat rate_gap values in t09_crossref_* as invalid until the pipeline is fixed.
- Downgraded to unlinked: no active known_issue/metric entry was cited for the stated mechanism.
- No context-layer metric definition was cited; the metric is defined only by the SQL that produced it, so a change in definition would be invisible across runs.

### 4. [INFO] India is 61% of Express volume (1,007 of 1,650 shown users); next-largest geo is 9%

**Metric:** `geo_adoption_share` = **0.6103** (IN 1007 vs next-largest AE 153) | segment: geoip_country_code=IN  
**Metric definition used:** `no context definition; ad-hoc` (exact context entry + version)

**What:** 1,007 of 1,650 users (61.0%) shown Express are geolocated to IN. The next-largest geo is AE at 153 users (9.3%), then SG at 147 (8.9%); AU, GB, SA, US each sit between 65-122 users.

**Why:** hypothesis, unverified
  
_Context cited:_ none -- treat the mechanism as an unverified hypothesis.

**So what:** Any headline Express number this window (overall 50.7% shown->confirmed, adoption rates, etc.) is effectively an India-weighted read; smaller geos (AU 81, GB 75, SA 65 shown users) don't have enough volume to detect platform or payment issues specific to them.

**Recommended action:** Set a minimum sample-size gate (e.g. 200+ shown users) before reporting a geo-level Express result externally, and consider a targeted push to grow non-IN Express volume so those cuts become trustworthy.

**Confidence 0.77** (method: `descriptive`, n = 1,650)

| component | value | what it measures |
| --- | ---: | --- |
| sample adequacy | 1.00 | is n big enough (capped at 0.40 below n=100) |
| statistical strength | 0.50 | 1 - p, or \|z\|/3 for anomaly tests |
| context support | 0.60 | 1.0 corroborated by a known issue, 0.3 if contradicted |
| data quality | 1.00 | 1 - worst null/empty rate among the columns used |
| **published score** | **0.77** | |

Check the arithmetic: arithmetic mean = 0.7750, geometric mean = 0.7401, product = 0.3000. This does **not** match a standard aggregation; closest is arithmetic mean at 0.7750 (delta 0.0050) -- the analytics agent's weighting is non-uniform and should be read from its source.

**Supporting queries:** `t03_funnel_by_geoip_country_code`, `t02_funnel_overall`

**Caveats:**
- No context entry defines an 'adoption share' metric; this is a straightforward count ratio over t03_funnel_by_geoip_country_code step-1 entities.
- No context-layer metric definition was cited; the metric is defined only by the SQL that produced it, so a change in definition would be invisible across runs.

## Schema generated for this feature

| | |
| --- | --- |
| Table | `f_express_checkout_events` |
| Engine | `MergeTree` |
| ORDER BY | `(event, timestamp, user_id)` |
| PARTITION BY | `toYYYYMM(timestamp)` |
| TTL | `toDateTime(timestamp) + INTERVAL 18 MONTH` |
| Columns | 21 (11 LowCardinality, 0 Nullable, 4 with a codec) |
| Materialized views | 1 |

**Table settings:** `ratio_of_defaults_for_sparse_serialization = 0.8333`

### Columns

| column | type | source path | codec | note |
| --- | --- | --- | --- | --- |
| `id` | `String` | `id` | `ZSTD(1)` | 32-char hex id, no dashes (e.g. f105934b4c083002827058f3). String, NOT UUID -- the 8 legacy tables declare id UUID and would reject this literal. |
| `timestamp` | `DateTime64(3)` | `timestamp` | `Delta, ZSTD(1)` | ISO-8601 with milliseconds; DateTime64(3) preserves precision that plain DateTime would truncate. |
| `event` | `LowCardinality(String)` | `event` | `-` | discriminator; E=5 values: express_checkout_shown, express_checkout_selected, saved_method_used, otp_entered, express_payment_confirmed. |
| `user_id` | `String` | `user_id` | `ZSTD(1)` | entity_key. 100% coverage across all 5 event types in this feature (no anonymous rows) -- confirmed by spec's 'events with a partial envelope: none'. |
| `application_id` | `String` | `application_id` | `ZSTD(1)` | secondary key, 100% coverage; joins to application_started/document_uploaded/pay_now_clicked/purchase_completed in the legacy tables. |
| `device_type` | `LowCardinality(String)` | `device_type` | `-` | 4 distinct values observed (Desktop, android, web-user-b2c, ios). |
| `os` | `LowCardinality(String)` | `os` | `-` | 93.1% coverage (some rows have null os); default '' rather than Nullable since every query scopes by device/segment, not by os-presence itself. |
| `geoip_country_code` | `LowCardinality(String)` | `geoip_country_code` | `-` | 7 distinct values (IN, SG, AU, AE, ...). |
| `destination` | `LowCardinality(String)` | `destination` | `-` | 14 distinct ISO-2 destination codes; shares vocabulary with destination_card_clicked/application_started. |
| `city` | `LowCardinality(String)` | `city` | `-` | 7 distinct values. |
| `app_version` | `LowCardinality(String)` | `app_version` | `-` | 3 distinct values. |
| `client_lib` | `LowCardinality(String)` | `client_lib` | `-` | 2 distinct values (mobile-rn, web-js). |
| `shown_amount` | `Decimal(18, 4)` | `shown_amount` | `-` | express_checkout_shown only (30.0% coverage = 1650/5507); currency-denominated, summed for adoption-value questions -> Decimal not Float. |
| `currency` | `LowCardinality(String)` | `currency` | `-` | express_checkout_shown only (30.0% coverage); pairs with shown_amount. |
| `eligible` | `UInt8` | `eligible` | `-` | boolean flag on express_checkout_shown only (30.0% coverage); JSON true/false -> UInt8 DEFAULT 0 per house rule 4. |
| `saved_method_type` | `LowCardinality(String)` | `saved_method_type` | `-` | express_checkout_selected only (18.3% coverage = 1007/5507); 3 values card/upi/wallet -- the segment cut for 'which segments adopt Express most'. |
| `otp_attempts` | `UInt8` | `otp_attempts` | `-` | otp_entered only (18.3% coverage); observed values 1-3, fits UInt8. |
| `otp_success` | `UInt8` | `otp_success` | `-` | otp_entered only (18.3% coverage); JSON boolean -> UInt8 DEFAULT 0. Drives the iOS OTP-failure question (K1). |
| `payment_amount` | `Decimal(18, 4)` | `payment.amount` | `-` | express_payment_confirmed only (15.2% coverage = 836/5507); nested payment.amount, summed -> Decimal not Float. |
| `payment_currency` | `LowCardinality(String)` | `payment.currency` | `-` | express_payment_confirmed only (15.2% coverage); nested payment.currency, 7 distinct values. |
| `payment_latency_ms` | `UInt32` | `payment.latency_ms` | `-` | express_payment_confirmed only (15.2% coverage); nested payment.latency_ms, observed up to ~8000ms -- the 'how much faster is Express' metric. |

### Rationale, decision by decision

**`order_by`** - ORDER BY (event, timestamp, user_id). event first: only E=5 distinct values, and every PM question (conversion lift, OTP/confirmation failure by platform, latency, segment adoption) filters or groups by event/step, so it prunes hard and dictionary-compresses well. timestamp second because all 4 questions are time-windowed (sample spans 2026-06-08..06-28, ongoing daily cuts). user_id third: it's the derived entity_key -- present on 100% of rows across all 5 event types, 1,650 distinct values, chosen over the co-extensive application_id only by first-mention order (both partition the 5,507 rows identically, confidence 0.80 per the derivation note) -- and it's the funnel grouping key for windowFunnel(shown->selected->saved_method_used->otp_entered->confirmed). Never id: id is 1 value per row (5,507 distinct / 5,507 rows), so an id-first key -- what the 8 legacy tables do with ORDER BY (id, timestamp, user_id) -- makes the primary index useless; base_context.md itself admits queries 'filter by time/segment, never by id'.

**`partition_by`** - toYYYYMM(timestamp), matching all 8 existing tables so cross-table date-range queries prune consistently. The sample is 5,507 rows over a 20-day window (~275 rows/day); daily partitions would produce ~20 tiny parts for the sample alone and thousands per year at scale, which fragments merges for no pruning benefit at this row count. Monthly keeps parts few and large, matching the other feature/legacy tables' partitioning so a query spanning Express + standard checkout doesn't hit mismatched partition granularities.

**`types`** - E=5 event types (shown/selected/saved_method_used/otp_entered/confirmed). An event-scoped column such as otp_attempts (present only on otp_entered, 1,007/5,507 = 18.3% of rows) is a default value on the other 4 event types, i.e. default ratio (1 - 0.183) = 0.817 -- under the MergeTree auto-sparse threshold of 0.9375, so it would NOT sparsify on its own. Setting ratio_of_defaults_for_sparse_serialization = min(0.9, 1 - 1/(E+1)) = min(0.9, 1 - 1/6) = min(0.9, 0.8333) = 0.8333 lowers the bar below every event-scoped column's actual default ratio: shown_amount/currency/eligible at 0.300 coverage -> 0.700 defaults; saved_method_type/otp_attempts/otp_success at 0.183 coverage -> 0.817 defaults; payment_amount/payment_currency/payment_latency_ms at 0.152 coverage -> 0.848 defaults. All three groups now clear 0.8333 and sparsify, combined with event-first ORDER BY clustering each event type into contiguous runs. id is String (32-char hex, e.g. 'f105934b4c083002827058f3'), not UUID -- the legacy tables' UUID type would reject this literal, the single most likely load failure per the house rules. Money fields (shown_amount, payment_amount) are Decimal(18,4) because they are currency-denominated and summed; payment_latency_ms is UInt32, an exact millisecond count (observed up to ~8,000ms), not a Float-worthy approximation.

**`nullable`** - Zero Nullable columns. user_id and application_id are 100% covered on all 5 event types (spec: 'events with a partial envelope: none'), so DEFAULT '' loses no information and avoids the null-map overhead the 8 legacy tables pay on 30-35 of their ~33-38 columns. Event-scoped fields (shown_amount, otp_attempts, otp_success, payment_amount, payment_currency, payment_latency_ms, saved_method_type, currency, eligible) default to 0/'' rather than Null because every consumer scopes them to their owning event via semantics.measures.scoped_to_events (e.g. otp_success is only read WHERE event = 'otp_entered'), so 0-vs-absent is never ambiguous in practice. Because identity columns default to '' instead of NULL, all identity aggregation must use uniqIf(user_id, user_id != '') rather than bare uniq(user_id) -- in this feature user_id happens to be 100% covered so partial_identity_columns is empty and no metric is actually inflated today, but the guarded form is still mandated so the same query templates don't silently break if a future anonymous event is added to this table.

**`ttl`** - TTL toDateTime(timestamp) + INTERVAL 18 MONTH on the raw table (the default). agg_express_checkout_funnel_segment_daily is a separate rollup target with no matching TTL, so day/event/segment funnel, OTP-failure, latency and adoption trends keep working after raw rows expire -- that pairing is the entire justification for the MV under house rule 7, not just a nice-to-have.

**`mvs`** - One MV, mv_express_checkout_funnel_segment_daily -> agg_express_checkout_funnel_segment_daily, grouped by (day, event, device_type, os, geoip_country_code, destination, saved_method_type). It answers all 4 spec questions from one AggregatingMergeTree: countState()/uniqStateIf(user_id,user_id!='') per (day,event,segment) drives the funnel and conversion-lift question; uniqStateIf(user_id, event='otp_entered' AND otp_success=1) against users_state at otp_entered, cut by device_type/os/geoip_country_code, drives the OTP/confirmation-failure-by-platform question (directly relevant to K1, the iOS WebKit OTP autofill regression); avgIfState/sumIfState(payment_latency_ms/payment_amount, event='express_payment_confirmed') drives the speed question; grouping by device_type/geoip_country_code/saved_method_type at event=express_checkout_selected drives the adoption question. All non-key outputs are *State aggregate functions per the AggregatingMergeTree requirement (a bare count()/avg() would be rejected). At the observed sample (5,507 rows / 20 days), the distinct (day,event,device_type,os,geo,destination,saved_method_type) key space is comparable in order of magnitude to the row count itself, so a measured reduction_factor at this volume is likely to land under the 5x keep bar -- that is expected and is exactly why house rule 7 says to judge against projected_annual_rows, not the sample: extrapolating 275 rows/day to ~100k raw rows/year while the realized (not combinatorial-ceiling) segment/day key space grows much more slowly should push the ratio well past 5x. I did not have a live ClickHouse connection in this proposal step to actually load and count, so measured_source_rows/measured_target_rows/reduction_factor/kept are left null rather than fabricated -- they must be filled from a real load-time measurement, and the MV dropped (kept=false) if reduction is under 5x at that point. I declined a second MV for 'shown -> confirmed elapsed time per user': that requires a per-user sequence (windowFunnel/sequenceMatch over min/max timestamp per user), not a summable aggregate, so rolling it into a daily counter table would either lose per-user granularity or amount to a near-copy of the raw table (836 confirmed rows in-sample) -- both fail house rule 7's 'not a straight copy' bar; payment_latency_ms already answers the 'how much faster' question directly via the kept MV's avg state.

**`contrast_with_legacy`** - The 8 existing tables are one-table-per-event, ORDER BY (id, timestamp, user_id), with 30-35 of ~33-38 columns Nullable -- instrumentation_notes.md calls this 'a legacy of the event-table template', not a deliberate design, and base_context.md admits queries never filter by id. f_express_checkout_events departs on all three axes: (1) one wide table unions all 5 Express event types instead of 5 separate tables, so shown->selected->saved_method_used->otp_entered->confirmed is a single windowFunnel with zero joins instead of a 5-way join per PM question; (2) ORDER BY (event, timestamp, user_id) puts the two columns every query actually filters/groups by first, with id nowhere in the key; (3) zero Nullable columns, using DEFAULT ''/0 plus explicit event-scoping and guarded uniqIf(user_id, user_id != '') instead of the null-map overhead the legacy tables carry on nearly every column.

**`naming`** - Table named f_express_checkout_events (feature-table prefix), MV target agg_express_checkout_funnel_segment_daily, MV itself mv_express_checkout_funnel_segment_daily -- none of these collide with the 8 existing table names (destination_card_clicked, search_typed, landing_page_scrolled, auth_completed, application_started, document_uploaded, pay_now_clicked, purchase_completed). This matters concretely here: Express Checkout's own event names (express_checkout_shown, otp_entered, etc.) don't collide today, but the f_/agg_/mv_ prefixing is the general defense the house rules call out after spec 04's drop_step values literally matched existing table names -- applying it uniformly avoids relying on a per-feature check for name collisions.

**`generation_log`** - attempt 0: lint clean, dry run OK

### How this differs from the legacy event tables

The 8 existing tables are one-table-per-event, ORDER BY (id, timestamp, user_id), with 30-35 of ~33-38 columns Nullable -- instrumentation_notes.md calls this 'a legacy of the event-table template', not a deliberate design, and base_context.md admits queries never filter by id. f_express_checkout_events departs on all three axes: (1) one wide table unions all 5 Express event types instead of 5 separate tables, so shown->selected->saved_method_used->otp_entered->confirmed is a single windowFunnel with zero joins instead of a 5-way join per PM question; (2) ORDER BY (event, timestamp, user_id) puts the two columns every query actually filters/groups by first, with id nowhere in the key; (3) zero Nullable columns, using DEFAULT ''/0 plus explicit event-scoping and guarded uniqIf(user_id, user_id != '') instead of the null-map overhead the legacy tables carry on nearly every column.

Structural differences a reviewer can verify directly against `SHOW CREATE TABLE` on any of the 8 pre-existing tables:

| dimension | legacy event tables | this feature table |
| --- | --- | --- |
| shape | one table per event type | one wide table per feature, `event` as the discriminator |
| ORDER BY | leads with the unique `id`, so the primary index cannot prune the time/segment filters that are actually run | `(event, timestamp, user_id)` |
| Nullable | nearly every column Nullable, costing a null map and weakening the index | 0 of 21 columns Nullable |
| enum columns | plain `String` | 11 columns as `LowCardinality(String)` |
| codecs | none declared | 4 columns carry an explicit codec |
| retention | none | `toDateTime(timestamp) + INTERVAL 18 MONTH`, paired with a rollup that outlives raw expiry |

### Generated DDL

```sql
CREATE TABLE IF NOT EXISTS f_express_checkout_events
(
    `id` String COMMENT 'json_path=id; 32-char hex id, no dashes (e.g. f105934b4c083002827058f3). String, NOT UUID -- the 8 legacy tables declare id UUID and would reject this literal.' CODEC(ZSTD(1)),
    `timestamp` DateTime64(3) COMMENT 'json_path=timestamp; ISO-8601 with milliseconds; DateTime64(3) preserves precision that plain DateTime would truncate.' CODEC(Delta, ZSTD(1)),
    `event` LowCardinality(String) COMMENT 'json_path=event; discriminator; E=5 values: express_checkout_shown, express_checkout_selected, saved_method_used, otp_entered, express_payment_confirmed.',
    `user_id` String DEFAULT '' COMMENT 'json_path=user_id; entity_key. 100% coverage across all 5 event types in this feature (no anonymous rows) -- confirmed by spec''s ''events with a partial envelope: none''.' CODEC(ZSTD(1)),
    `application_id` String DEFAULT '' COMMENT 'json_path=application_id; secondary key, 100% coverage; joins to application_started/document_uploaded/pay_now_clicked/purchase_completed in the legacy tables.' CODEC(ZSTD(1)),
    `device_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=device_type; 4 distinct values observed (Desktop, android, web-user-b2c, ios).',
    `os` LowCardinality(String) DEFAULT '' COMMENT 'json_path=os; 93.1% coverage (some rows have null os); default '''' rather than Nullable since every query scopes by device/segment, not by os-presence itself.',
    `geoip_country_code` LowCardinality(String) DEFAULT '' COMMENT 'json_path=geoip_country_code; 7 distinct values (IN, SG, AU, AE, ...).',
    `destination` LowCardinality(String) DEFAULT '' COMMENT 'json_path=destination; 14 distinct ISO-2 destination codes; shares vocabulary with destination_card_clicked/application_started.',
    `city` LowCardinality(String) DEFAULT '' COMMENT 'json_path=city; 7 distinct values.',
    `app_version` LowCardinality(String) DEFAULT '' COMMENT 'json_path=app_version; 3 distinct values.',
    `client_lib` LowCardinality(String) DEFAULT '' COMMENT 'json_path=client_lib; 2 distinct values (mobile-rn, web-js).',
    `shown_amount` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=shown_amount; express_checkout_shown only (30.0% coverage = 1650/5507); currency-denominated, summed for adoption-value questions -> Decimal not Float.',
    `currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=currency; express_checkout_shown only (30.0% coverage); pairs with shown_amount.',
    `eligible` UInt8 DEFAULT 0 COMMENT 'json_path=eligible; boolean flag on express_checkout_shown only (30.0% coverage); JSON true/false -> UInt8 DEFAULT 0 per house rule 4.',
    `saved_method_type` LowCardinality(String) DEFAULT '' COMMENT 'json_path=saved_method_type; express_checkout_selected only (18.3% coverage = 1007/5507); 3 values card/upi/wallet -- the segment cut for ''which segments adopt Express most''.',
    `otp_attempts` UInt8 DEFAULT 0 COMMENT 'json_path=otp_attempts; otp_entered only (18.3% coverage); observed values 1-3, fits UInt8.',
    `otp_success` UInt8 DEFAULT 0 COMMENT 'json_path=otp_success; otp_entered only (18.3% coverage); JSON boolean -> UInt8 DEFAULT 0. Drives the iOS OTP-failure question (K1).',
    `payment_amount` Decimal(18, 4) DEFAULT 0 COMMENT 'json_path=payment.amount; express_payment_confirmed only (15.2% coverage = 836/5507); nested payment.amount, summed -> Decimal not Float.',
    `payment_currency` LowCardinality(String) DEFAULT '' COMMENT 'json_path=payment.currency; express_payment_confirmed only (15.2% coverage); nested payment.currency, 7 distinct values.',
    `payment_latency_ms` UInt32 DEFAULT 0 COMMENT 'json_path=payment.latency_ms; express_payment_confirmed only (15.2% coverage); nested payment.latency_ms, observed up to ~8000ms -- the ''how much faster is Express'' metric.'
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (event, timestamp, user_id)
TTL toDateTime(timestamp) + INTERVAL 18 MONTH
SETTINGS ratio_of_defaults_for_sparse_serialization = 0.8333;

CREATE TABLE IF NOT EXISTS agg_express_checkout_funnel_segment_daily
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(day)
ORDER BY (day, event, device_type, os, geoip_country_code, destination, saved_method_type)
EMPTY AS
SELECT toDate(timestamp) AS day, event, device_type, os, geoip_country_code, destination, saved_method_type, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state, uniqStateIf(user_id, event = 'otp_entered' AND otp_success = 1) AS otp_success_users_state, avgIfState(payment_latency_ms, event = 'express_payment_confirmed') AS avg_payment_latency_ms_state, sumIfState(payment_amount, event = 'express_payment_confirmed') AS payment_amount_sum_state FROM f_express_checkout_events GROUP BY day, event, device_type, os, geoip_country_code, destination, saved_method_type;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_express_checkout_funnel_segment_daily
TO agg_express_checkout_funnel_segment_daily AS
SELECT toDate(timestamp) AS day, event, device_type, os, geoip_country_code, destination, saved_method_type, countState() AS events_state, uniqStateIf(user_id, user_id != '') AS users_state, uniqStateIf(user_id, event = 'otp_entered' AND otp_success = 1) AS otp_success_users_state, avgIfState(payment_latency_ms, event = 'express_payment_confirmed') AS avg_payment_latency_ms_state, sumIfState(payment_amount, event = 'express_payment_confirmed') AS payment_amount_sum_state FROM f_express_checkout_events GROUP BY day, event, device_type, os, geoip_country_code, destination, saved_method_type;
```

### Materialized views: measured, then kept or dropped

| materialized view | target table | source rows | target rows | reduction | verdict |
| --- | --- | ---: | ---: | ---: | --- |
| `mv_express_checkout_funnel_segment_daily` | `agg_express_checkout_funnel_segment_daily` | 5,507 | 4,693 | 1.2x | **DROPPED** |

The gate is a measured 5x reduction. An MV dropped **with** its measurement is a stronger result than one kept on faith.

**`mv_express_checkout_funnel_segment_daily`** - Single AggregatingMergeTree rollup that answers all 4 spec questions without touching raw rows: (a) uniqMergeIf(users_state) per day/event gives the shown->selected->saved_method_used->otp_entered->confirmed funnel and its conversion lift vs standard checkout (join on day+segment against purchase_completed/pay_now_clicked); (b) otp_success_users_state vs users_state at event=otp_entered, cut by device_type/os/geoip_country_code, surfaces the iOS OTP-failure pattern (K1) cheaply; (c) avgMerge(avg_payment_latency_ms_state) gives the speed metric without scanning payment_latency_ms row-by-row; (d) grouping by device_type/geoip_country_code/saved_method_type at event=express_checkout_selected answers adoption-by-segment. It survives the raw table's 18-month TTL so long-range trend queries keep working after raw rows expire.
- serves PM question: _Does Express lift checkout -> success conversion vs standard checkout, and by how much?_
- serves PM question: _Is there a platform where OTP / payment fails more (e.g. iOS)? Cut otp_success and confirmation rate by device_type / os / geoip_country_code._
- serves PM question: _How much faster is Express (payment.latency_ms, time from shown -> confirmed)?_
- serves PM question: _Which segments adopt Express most (device, geo, saved-method type)?_

## Context changes this run

Context layer moved **v3 -> v4**: 27 added, 0 updated, 0 superseded, 8 contradictions, 5 gaps.

### Added

- **`business_def.express_checkout.funnel` v1** (business_def) - express_checkout funnel: Ordered steps on `atlys.f_express_checkout_events`: express_checkout_shown -> express_checkout_selected -> saved_method_used -> otp_entered -> express_payment_confirmed (step order source: spec). Segment dimensions: device_type, os, geoip_country_code, destination, saved_method_type. Event discriminator column: `event`. _[source: instrumentation_agent, confidence 1.00, refs: destination, device_type, event, f_express_checkout_events, geoip_country_code, os, saved_method_type]_
- **`column.f_express_checkout_events.app_version` v1** (column_doc) - f_express_checkout_events.app_version: app_version LowCardinality(String) on f_express_checkout_events. _[source: context_agent, confidence 1.00, refs: app_version, f_express_checkout_events]_
- **`column.f_express_checkout_events.application_id` v1** (column_doc) - f_express_checkout_events.application_id: application_id String on f_express_checkout_events. _[source: context_agent, confidence 1.00, refs: application_id, f_express_checkout_events]_
- **`column.f_express_checkout_events.city` v1** (column_doc) - f_express_checkout_events.city: city LowCardinality(String) on f_express_checkout_events. _[source: context_agent, confidence 1.00, refs: city, f_express_checkout_events]_
- **`column.f_express_checkout_events.client_lib` v1** (column_doc) - f_express_checkout_events.client_lib: client_lib LowCardinality(String) on f_express_checkout_events. _[source: context_agent, confidence 1.00, refs: client_lib, f_express_checkout_events]_
- **`column.f_express_checkout_events.currency` v1** (column_doc) - f_express_checkout_events.currency: currency LowCardinality(String) on f_express_checkout_events. _[source: context_agent, confidence 1.00, refs: currency, f_express_checkout_events]_
- **`column.f_express_checkout_events.destination` v1** (column_doc) - f_express_checkout_events.destination: destination LowCardinality(String) on f_express_checkout_events. _[source: context_agent, confidence 1.00, refs: destination, f_express_checkout_events]_
- **`column.f_express_checkout_events.device_type` v1** (column_doc) - f_express_checkout_events.device_type: device_type LowCardinality(String) on f_express_checkout_events. _[source: context_agent, confidence 1.00, refs: device_type, f_express_checkout_events]_
- **`column.f_express_checkout_events.eligible` v1** (column_doc) - f_express_checkout_events.eligible: eligible UInt8 on f_express_checkout_events. _[source: context_agent, confidence 1.00, refs: eligible, f_express_checkout_events]_
- **`column.f_express_checkout_events.event` v1** (column_doc) - f_express_checkout_events.event: event LowCardinality(String) on f_express_checkout_events. _[source: context_agent, confidence 1.00, refs: event, f_express_checkout_events]_
- **`column.f_express_checkout_events.geoip_country_code` v1** (column_doc) - f_express_checkout_events.geoip_country_code: geoip_country_code LowCardinality(String) on f_express_checkout_events. _[source: context_agent, confidence 1.00, refs: f_express_checkout_events, geoip_country_code]_
- **`column.f_express_checkout_events.id` v1** (column_doc) - f_express_checkout_events.id: id String on f_express_checkout_events. _[source: context_agent, confidence 1.00, refs: f_express_checkout_events, id]_
- **`column.f_express_checkout_events.os` v1** (column_doc) - f_express_checkout_events.os: os LowCardinality(String) on f_express_checkout_events. _[source: context_agent, confidence 1.00, refs: f_express_checkout_events, os]_
- **`column.f_express_checkout_events.otp_attempts` v1** (column_doc) - f_express_checkout_events.otp_attempts: otp_attempts UInt8 on f_express_checkout_events. _[source: context_agent, confidence 1.00, refs: f_express_checkout_events, otp_attempts]_
- **`column.f_express_checkout_events.otp_success` v1** (column_doc) - f_express_checkout_events.otp_success: otp_success UInt8 on f_express_checkout_events. _[source: context_agent, confidence 1.00, refs: f_express_checkout_events, otp_success]_
- **`column.f_express_checkout_events.payment_amount` v1** (column_doc) - f_express_checkout_events.payment_amount: payment_amount Decimal(18, 4) on f_express_checkout_events. _[source: context_agent, confidence 1.00, refs: f_express_checkout_events, payment_amount]_
- **`column.f_express_checkout_events.payment_currency` v1** (column_doc) - f_express_checkout_events.payment_currency: payment_currency LowCardinality(String) on f_express_checkout_events. _[source: context_agent, confidence 1.00, refs: f_express_checkout_events, payment_currency]_
- **`column.f_express_checkout_events.payment_latency_ms` v1** (column_doc) - f_express_checkout_events.payment_latency_ms: payment_latency_ms UInt32 on f_express_checkout_events. _[source: context_agent, confidence 1.00, refs: f_express_checkout_events, payment_latency_ms]_
- **`column.f_express_checkout_events.saved_method_type` v1** (column_doc) - f_express_checkout_events.saved_method_type: saved_method_type LowCardinality(String) on f_express_checkout_events. _[source: context_agent, confidence 1.00, refs: f_express_checkout_events, saved_method_type]_
- **`column.f_express_checkout_events.shown_amount` v1** (column_doc) - f_express_checkout_events.shown_amount: shown_amount Decimal(18, 4) on f_express_checkout_events. _[source: context_agent, confidence 1.00, refs: f_express_checkout_events, shown_amount]_
- **`column.f_express_checkout_events.timestamp` v1** (column_doc) - f_express_checkout_events.timestamp: timestamp DateTime64(3) on f_express_checkout_events. _[source: context_agent, confidence 1.00, refs: f_express_checkout_events, timestamp]_
- **`column.f_express_checkout_events.user_id` v1** (column_doc) - f_express_checkout_events.user_id: user_id String on f_express_checkout_events. _[source: context_agent, confidence 1.00, refs: f_express_checkout_events, user_id]_
- **`entity.express_checkout.entity_key` v1** (entity) - express_checkout entity key: user_id: The grain of `atlys.f_express_checkout_events` is `user_id` (confidence 0.80); secondary keys: application_id. Derived from the spec and the raw events by the instrumentation agent, not assumed. _[source: instrumentation_agent, confidence 0.80, refs: application_id, f_express_checkout_events, user_id]_
- **`gap.data_quality.f_express_checkout_events.application_id_join` v1** (gap) - data_quality: f_express_checkout_events.application_id is not joinable to the existing tables: MEASURED, not assumed. 0.0% of `f_express_checkout_events` rows have `application_id = ''` (anonymous events; empty string, not NULL). Rows joinable to the existing tables on `application_id`: destination_card_clicked=0, search_typed=0. Every identity-level metric on this table MUST use uniqIf(application_id, application_id != ''), and every cross-reference to the eight pre-existing tables MUST be segment-level (app_version, city, client_lib / day), never an identity join. Findings that compare this feature to the existing funnel must carry this as a caveat. _[source: context_agent, confidence 1.00, refs: application_id, destination_card_clicked, f_express_checkout_events, search_typed]_
- **`gap.data_quality.f_express_checkout_events.user_id_join` v1** (gap) - data_quality: f_express_checkout_events.user_id is not joinable to the existing tables: MEASURED, not assumed. 0.0% of `f_express_checkout_events` rows have `user_id = ''` (anonymous events; empty string, not NULL). Rows joinable to the existing tables on `user_id`: destination_card_clicked=0, search_typed=0. Every identity-level metric on this table MUST use uniqIf(user_id, user_id != ''), and every cross-reference to the eight pre-existing tables MUST be segment-level (app_version, city, client_lib / day), never an identity join. Findings that compare this feature to the existing funnel must carry this as a caveat. _[source: context_agent, confidence 1.00, refs: destination_card_clicked, f_express_checkout_events, search_typed, user_id]_
- **`relationship.f_express_checkout_events.segment_join` v1** (relationship) - f_express_checkout_events -> existing tables (segment-level only): `f_express_checkout_events` shares no identities with the eight pre-existing tables, but shares these segment vocabularies (measured overlap of distinct values against `destination_card_clicked`): `app_version` (3 shared values), `city` (7 shared values), `client_lib` (2 shared values). Join on those plus toDate(timestamp). This supersedes the documented user_id join map for feature tables. _[source: context_agent, confidence 1.00, refs: app_version, city, client_lib, destination_card_clicked, f_express_checkout_events]_
- **`table.f_express_checkout_events` v1** (table_doc) - f_express_checkout_events: Auto-documented from the live schema: 21 columns; 5,507 rows at first observation; ORDER BY (event, timestamp, user_id); PARTITION BY toYYYYMM(timestamp); TTL toDateTime(timestamp) + INTERVAL 18 MONTH; order_by rationale: ORDER BY (event, timestamp, user_id). event first: only E=5 distinct values, and every PM question (conversion lift, OTP/confirmation failure by platform, latency, segment adoption) filters or groups by event/step, so it prunes hard and dictionary-compresses well. timestamp second because all 4 questions are time-windowed (sample spans 2026-06-08..06-28, ongoing daily cuts). user_id third: it's the derived entity_key -- present on 100% of rows across all 5 event types, 1,650 distinct values, chosen over the co-extensive application_id only by first-mention order (both partition the 5,507 rows identically, confidence 0.80 per the derivation note) -- and it's the funnel grouping key for windowFunnel(shown->selected->saved_method_used->otp_entered->confirmed). Never id: id is 1 value per row (5,507 distinct / 5,507 rows), so an id-first key -- what the 8 legacy tables do with ORDER BY (id, timestamp, user_id) -- makes the primary index useless; base_context.md itself admits queries 'filter by time/segment, never by id'.. Columns: id, timestamp, event, user_id, application_id, device_type, os, geoip_country_code, destination, city, app_version, client_lib, shown_amount, currency, eligible, saved_method_type, otp_attempts, otp_success, payment_amount, payment_currency, payment_latency_ms. _[source: context_agent, confidence 1.00, refs: f_express_checkout_events]_

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

#### [HIGH] `f_express_checkout_events` cannot be joined to the existing tables on `application_id`

- **Kind:** `join_assumption_violated` (detected by rule)
- **The context claims:** The documented join map asserts every table joins on `application_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.f_instant_forex_events.segment_join, relationship.funnel_order_timestamp_ascending).
- **The data says:** `f_express_checkout_events` has 5507 rows, of which 0 (0.0%) carry `application_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 1650 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 3), ('city', 7), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.f_instant_forex_events.segment_join`, `relationship.funnel_order_timestamp_ascending`, `relationship.segment_cuts_device_type`, `relationship.supporting_tables_search_typed`
- **Proposed resolution:** Analytics must NOT join this table to the existing tables on `application_id`. Cross-reference at segment level only (app_version, city, client_lib and day). Corroborating query: SELECT count() AS shared_values FROM (SELECT DISTINCT app_version AS v FROM atlys.f_express_checkout_events WHERE app_version != '') a INNER JOIN (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.destination_card_clicked) b USING (v) -> app_version=3, city=7, client_lib=2

Verification SQL:

```sql
SELECT
  count() AS new_rows,
  countIf(application_id = '') AS anonymous_rows,
  round(countIf(application_id = '') / count(), 4) AS anonymous_frac,
  uniqIf(application_id, application_id != '') AS distinct_identities,
  countIf(application_id != '' AND application_id IN (SELECT ifNull(application_id, '') FROM atlys.destination_card_clicked)) AS rows_joinable_to_destination_card_clicked,
  countIf(application_id != '' AND application_id IN (SELECT ifNull(application_id, '') FROM atlys.search_typed)) AS rows_joinable_to_search_typed
FROM atlys.f_express_checkout_events
```

Result: `[{"new_rows": 5507, "anonymous_rows": 0, "anonymous_frac": 0.0, "distinct_identities": 1650, "rows_joinable_to_destination_card_clicked": 0, "rows_joinable_to_search_typed": 0}]`

#### [HIGH] `f_express_checkout_events` cannot be joined to the existing tables on `user_id`

- **Kind:** `join_assumption_violated` (detected by rule)
- **The context claims:** The documented join map asserts every table joins on `user_id` (entries: relationship.application_started_application_id, relationship.destination_card_clicked_user_id, relationship.f_instant_forex_events.segment_join, relationship.funnel_order_timestamp_ascending).
- **The data says:** `f_express_checkout_events` has 5507 rows, of which 0 (0.0%) carry `user_id = ''` -- anonymous events, empty string rather than NULL because house rules forbid Nullable on hot columns. Of the remaining 1650 distinct identities, the number of rows joinable to the existing tables is: destination_card_clicked=0, search_typed=0. Identity-level joins between this feature table and the existing tables return nothing -- silently, which is the dangerous part. Segment-level vocabularies DO overlap: [('app_version', 3), ('city', 7), ('client_lib', 2)].
- **Verified against the database:** **yes**
- **Entries affected:** `relationship.application_started_application_id`, `relationship.destination_card_clicked_user_id`, `relationship.f_instant_forex_events.segment_join`, `relationship.funnel_order_timestamp_ascending`, `relationship.segment_cuts_device_type`, `relationship.supporting_tables_search_typed`
- **Proposed resolution:** Analytics must NOT join this table to the existing tables on `user_id`. Cross-reference at segment level only (app_version, city, client_lib and day). Corroborating query: SELECT count() AS shared_values FROM (SELECT DISTINCT app_version AS v FROM atlys.f_express_checkout_events WHERE app_version != '') a INNER JOIN (SELECT DISTINCT ifNull(app_version, '') AS v FROM atlys.destination_card_clicked) b USING (v) -> app_version=3, city=7, client_lib=2

Verification SQL:

```sql
SELECT
  count() AS new_rows,
  countIf(user_id = '') AS anonymous_rows,
  round(countIf(user_id = '') / count(), 4) AS anonymous_frac,
  uniqIf(user_id, user_id != '') AS distinct_identities,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.destination_card_clicked)) AS rows_joinable_to_destination_card_clicked,
  countIf(user_id != '' AND user_id IN (SELECT user_id FROM atlys.search_typed)) AS rows_joinable_to_search_typed
FROM atlys.f_express_checkout_events
```

Result: `[{"new_rows": 5507, "anonymous_rows": 0, "anonymous_frac": 0.0, "distinct_identities": 1650, "rows_joinable_to_destination_card_clicked": 0, "rows_joinable_to_search_typed": 0}]`

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

- join_assumption_violated: `f_express_checkout_events` cannot be joined to the existing tables on `application_id`
- join_assumption_violated: `f_express_checkout_events` cannot be joined to the existing tables on `user_id`
- uncomputable_metric: 'Conversion rate' is not computable as defined
- uncomputable_metric: 'On-time delivery rate' is documented as a metric but cannot be computed here
- undefined_term: 'sessions' is used in a metric definition but never defined

## Unanswered questions

- Does Express lift shown->confirmed conversion vs standard (non-Express) checkout, and by how much? Blocked by the degenerate baseline in t09_crossref_*.
- How much faster is Express (payment_latency_ms, shown->confirmed) than standard checkout? No standard-checkout latency baseline was provided, and the payment_latency_ms figures in t05 are averaged across all 5 Express event types (not filtered to express_payment_confirmed), so even the Express-only number is not yet a clean 'time to pay' figure.
- Is raw otp_success (as opposed to step completion) different by device/os/geo? No segment-level otp_success breakout was available in the frames.

## How this feature was read (provenance)

- **Entity key** `user_id` - user_id: present on 5/5 event types, 100.0% of rows, 1,650 distinct values, 61% of values span >1 step. Runner-up application_id (5/5 event types, 100.0% rows); decided on first mention order in spec.md. Co-extensive alternatives application_id partition the rows identically (1,650 values, same coverage), so every funnel and ORDER BY is numerically identical whichever is chosen -- the pick is arbitrary but harmless, hence confidence is not penalised below 0.80. Row-unique id columns were excluded as entity keys (house_rules.md section 2). [confidence=0.80]
- **Funnel derived as** express_checkout_shown -> express_checkout_selected -> saved_method_used -> otp_entered -> express_payment_confirmed
- **Derivation method:** [source=spec] spec bullets named 5/5 observed event types. agreement spec~timestamp=1.00, spec~volume=0.90, volume~timestamp=0.90; pairwise timestamp decisiveness=1.00 over 9,386 ordered entity pairs. volume order inverts saved_method_used<->otp_entered vs the spec (expected where steps share a count). volume order=express_checkout_shown > express_checkout_selected > otp_entered > saved_method_used > express_payment_confirmed. timestamp order=express_checkout_shown > express_checkout_selected > saved_method_used > otp_entered > express_payment_confirmed.
- **Event types:** `express_checkout_shown` (1,650), `express_checkout_selected` (1,007), `saved_method_used` (1,007), `otp_entered` (1,007), `express_payment_confirmed` (836)
- **Raw events profiled:** 5,507 across 21 distinct fields
- **Cross-references into the pre-existing tables:**
    - `user_id` -> pay_now_clicked, purchase_completed via `user_id` (shared_key): Express Checkout is an alternative path to the same conversion event captured by the legacy pay_now_clicked -> purchase_completed funnel; both share the 28-char user_id identity space, so answering 'does Express lift conversion vs standard checkout' requires joining f_express_checkout_events against purchase_completed/pay_now_clicked on user_id + time window rather than treating Express as the only checkout path.
    - `destination` -> destination_card_clicked, application_started via `destination` (existing_column_values): destination is the same ISO-2 vocabulary (14 distinct values observed here: AU, SG, FR, TR, ...) used in destination_card_clicked and application_started, enabling a segment-level (not identity-level) comparison of Express adoption/performance by destination against the overall funnel, consistent with business_def's 'always cut by device, geo, destination'.

---

_Generated by the Atlys agentic analytics pipeline, run `f0ee8056039147d59b1811b363005402`, context layer v4._
